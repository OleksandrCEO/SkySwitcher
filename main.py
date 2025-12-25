#!/usr/bin/env python3
"""
SkySwitcher v0.3.1
A minimal Wayland/Linux layout switcher & corrector.

Changes in v0.3.1:
- REVERT: Removed Left Ctrl support to keep code simple (User Request).
- FIXED: 'F12/Console' issue. Added delays and aggressive modifier release before
  copy commands to prevent OS from detecting 'Ctrl+Shift+C'.

Features:
1. Double Tap [Right Shift]:
   - Selects line part -> Smart translates -> Switches Layout.
2. Hold [Right Ctrl] + Tap [Right Shift]:
   - Smart translates selection -> NO Layout switch.
"""

import evdev
from evdev import UInput, ecodes as e
import subprocess
import time
import sys
import argparse

# --- CONFIGURATION ---
TRIGGER_BTN = e.KEY_RIGHTSHIFT
MODE2_MODIFIER = e.KEY_RIGHTCTRL  # Only Right Ctrl

DOUBLE_PRESS_DELAY = 0.5
LAYOUT_SWITCH_COMBO = [e.KEY_LEFTMETA, e.KEY_SPACE]

# --- LAYOUT DATABASE ---
LAYOUT_US = "`qwertyuiop[]\\asdfghjkl;'zxcvbnm,./~@#$%^&QWERTYUIOP{}|ASDFGHJKL:\"ZXCVBNM<>?"
LAYOUT_UA = "'йцукенгшщзхїґфівапролджєячсмитьбю.₴\"№;%:?ЙЦУКЕНГШЩЗХЇҐФІВАПРОЛДЖЄЯЧСМИТЬБЮ,"

LAYOUTS_DB = {
    'us': LAYOUT_US,
    'en': LAYOUT_US,
    'ua': LAYOUT_UA,
    'ru': "ёйцукенгшщзхъ\\фывапролджэячсмитьбю.Ё\"№;%:?ЙЦУКЕНГШЩЗХЪ/ФЫВАПРОЛДЖЭЯЧСМИТЬБЮ,",
    'de': "^qwertzuiopü+#asdfghjklöäyxcvbnm,.-°!\"§$%&QWERTZUIOPÜ*'ASDFGHJKLÖÄYXCVBNM;:_",
}

IGNORED_KEYWORDS = [
    'mouse', 'webcam', 'audio', 'video', 'consumer',
    'control', 'headset', 'receiver', 'solaar', 'hotkeys'
]


def list_devices():
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    devices.sort(key=lambda x: x.path)
    print(f"{'PATH':<20} | {'NAME'}")
    print("-" * 50)
    for dev in devices:
        print(f"{dev.path:<20} | {dev.name}")


def find_keyboard_device():
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    possible_candidates = []

    for dev in devices:
        name = dev.name.lower()
        if any(bad in name for bad in IGNORED_KEYWORDS): continue
        if e.EV_KEY not in dev.capabilities(): continue

        keys = dev.capabilities()[e.EV_KEY]
        if {e.KEY_SPACE, e.KEY_ENTER, e.KEY_A, e.KEY_Z}.issubset(keys):
            if 'keyboard' in name or 'kbd' in name: return dev.path, dev.name
            possible_candidates.append((dev.path, dev.name))

    return possible_candidates[0] if possible_candidates else (None, None)


class SkySwitcher:
    def __init__(self, device_path, layout_pair, verbose=False):
        self.verbose = verbose

        # --- Layout Setup ---
        self.src_name, self.dst_name = layout_pair

        if not layout_pair or self.src_name not in LAYOUTS_DB or self.dst_name not in LAYOUTS_DB:
            self.error(f"Unknown layouts: {layout_pair}")
            sys.exit(1)

        self.src_chars = LAYOUTS_DB[self.src_name]
        self.dst_chars = LAYOUTS_DB[self.dst_name]

        self.map_src_to_dst = str.maketrans(self.src_chars, self.dst_chars)
        self.map_dst_to_src = str.maketrans(self.dst_chars, self.src_chars)

        self.src_unique = set(self.src_chars) - set(self.dst_chars)
        self.dst_unique = set(self.dst_chars) - set(self.src_chars)

        self.log(f"🌍 Languages: {self.src_name.upper()} <-> {self.dst_name.upper()}")

        # --- Device Setup ---
        try:
            self.dev = evdev.InputDevice(device_path)
            self.log(f"✅ Connected to: {self.dev.name}")
        except OSError as err:
            self.error(f"Failed to open device: {err}")
            sys.exit(1)

        all_keys = [
            e.KEY_LEFTCTRL, e.KEY_LEFTSHIFT, e.KEY_RIGHTCTRL, e.KEY_RIGHTSHIFT,
            e.KEY_C, e.KEY_V,
            e.KEY_LEFT, e.KEY_RIGHT, e.KEY_BACKSPACE, e.KEY_HOME,
            e.KEY_LEFTMETA, e.KEY_SPACE, e.KEY_INSERT, e.KEY_LEFTALT
        ]

        try:
            self.ui = UInput({e.EV_KEY: all_keys}, name="SkySwitcher-Virtual")
        except Exception as err:
            self.error(f"Failed to create UInput device: {err}")
            sys.exit(1)

        self.last_press_time = 0
        self.modifier_down = False

    def log(self, msg):
        if self.verbose: print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

    def error(self, msg):
        print(f"❌ {msg}", file=sys.stderr)

    def get_clipboard(self):
        try:
            return subprocess.run(['wl-paste', '-n'], capture_output=True, text=True).stdout
        except FileNotFoundError:
            return ""

    def clear_clipboard(self):
        try:
            subprocess.run(['wl-copy', '--clear'], check=False)
        except:
            pass

    def set_clipboard(self, text):
        try:
            p = subprocess.Popen(['wl-copy', '-n'], stdin=subprocess.PIPE, text=True)
            p.communicate(input=text)
        except:
            pass

    def send_combo(self, *keys):
        for k in keys: self.ui.write(e.EV_KEY, k, 1)
        self.ui.syn()
        time.sleep(0.02)
        for k in reversed(keys): self.ui.write(e.EV_KEY, k, 0)
        self.ui.syn()
        time.sleep(0.02)

    def release_all_modifiers(self):
        """
        Aggressively release all modifiers to prevent 'Ghost Keys'.
        Crucial for avoiding Ctrl+Shift+C (Inspector) issues.
        """
        modifiers = [e.KEY_LEFTSHIFT, e.KEY_RIGHTSHIFT, e.KEY_LEFTCTRL, e.KEY_RIGHTCTRL, e.KEY_LEFTALT]
        for key in modifiers:
            self.ui.write(e.EV_KEY, key, 0)
        self.ui.syn()
        time.sleep(0.05)

    def wait_for_new_content(self, timeout=0.5):
        start = time.time()
        while time.time() - start < timeout:
            content = self.get_clipboard()
            if content: return content
            time.sleep(0.02)
        return None

    def smart_translate(self, text):
        src_score = sum(1 for c in text if c in self.src_unique)
        dst_score = sum(1 for c in text if c in self.dst_unique)

        if src_score >= dst_score:
            return text.translate(self.map_src_to_dst)
        else:
            return text.translate(self.map_dst_to_src)

    def process_text_replacement(self, mode="last_word"):
        # 1. Critical: Release physical modifiers virtually
        self.release_all_modifiers()

        # 2. Wait slightly longer to ensure OS sees Shift as UP
        # This prevents Ctrl+C becoming Ctrl+Shift+C (Inspector)
        time.sleep(0.15)

        backup_clipboard = self.get_clipboard()
        self.clear_clipboard()

        if mode == "last_word":
            self.send_combo(e.KEY_LEFTSHIFT, e.KEY_HOME)
            self.release_all_modifiers()
            time.sleep(0.1)
            self.send_combo(e.KEY_LEFTCTRL, e.KEY_C)
        else:
            self.send_combo(e.KEY_LEFTCTRL, e.KEY_C)

        full_text = self.wait_for_new_content()

        if not full_text:
            self.log("Copy failed/timed out.")
            self.set_clipboard(backup_clipboard)
            if mode == "last_word": self.send_combo(e.KEY_RIGHT)
            return

        target_text = full_text
        if mode == "last_word":
            if not full_text.strip():
                self.set_clipboard(backup_clipboard)
                self.send_combo(e.KEY_RIGHT)
                return
            target_text = full_text.split()[-1]

        converted = self.smart_translate(target_text)

        if mode == "last_word":
            self.send_combo(e.KEY_RIGHT)

        if target_text == converted:
            self.log("No change needed.")
            return

        self.log(f"Correcting: '{target_text}' -> '{converted}'")
        self.set_clipboard(converted)
        time.sleep(0.1)

        if mode == "last_word":
            for _ in range(len(target_text)):
                self.ui.write(e.EV_KEY, e.KEY_BACKSPACE, 1)
                self.ui.syn()
                time.sleep(0.005)
                self.ui.write(e.EV_KEY, e.KEY_BACKSPACE, 0)
                self.ui.syn()
        else:
            self.send_combo(e.KEY_BACKSPACE)

        self.release_all_modifiers()
        time.sleep(0.05)
        self.send_combo(e.KEY_LEFTCTRL, e.KEY_V)

        if mode == "last_word":
            self.log("Switching system layout...")
            time.sleep(0.1)
            self.send_combo(*LAYOUT_SWITCH_COMBO)

    def run(self):
        self.log(f"🚀 SkySwitcher v0.2.8 running...")

        try:
            self.dev.grab()
            self.dev.ungrab()
        except IOError:
            self.log("⚠️  Device grabbed. Running passive.")

        for event in self.dev.read_loop():
            if event.type == e.EV_KEY:
                # 1. Update Modifier State
                if event.code == MODE2_MODIFIER:
                    self.modifier_down = (event.value == 1 or event.value == 2)

                # 2. Trigger Logic (R_SHIFT)
                if event.code == TRIGGER_BTN:
                    if event.value == 1:  # Key Down
                        if self.modifier_down:
                            self.log("✨ Mode 2: Selection Fix (Right Ctrl)")
                            self.process_text_replacement(mode="selection")
                            self.last_press_time = 0
                        else:
                            now = time.time()
                            if now - self.last_press_time < DOUBLE_PRESS_DELAY:
                                self.log("⚡ Mode 1: Double Shift")
                                self.process_text_replacement(mode="last_word")
                                self.last_press_time = 0
                            else:
                                self.last_press_time = now

                # 3. INTERRUPTION LOGIC
                elif event.value == 1 and event.code != MODE2_MODIFIER:
                    if self.last_press_time > 0:
                        self.last_press_time = 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SkySwitcher Layout Corrector")
    parser.add_argument("-d", "--device", help="Path to input device")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--list", action="store_true", help="List available devices")
    parser.add_argument("--langs", default="us,ua", help="Comma separated layout codes (default: us,ua)")

    args = parser.parse_args()
    langs = None

    if args.list:
        list_devices()
        sys.exit(0)

    try:
        langs = args.langs.split(',')
        if len(langs) != 2: raise ValueError
    except:
        print("❌ Error: --langs must be two codes separated by comma (e.g. 'us,ua')", file=sys.stderr)
        sys.exit(1)

    path = args.device
    if not path:
        path, _ = find_keyboard_device()
        if not path:
            print("❌ Keyboard not found automatically. Use --list", file=sys.stderr)
            sys.exit(1)

    try:
        SkySwitcher(path, langs, args.verbose).run()
    except KeyboardInterrupt:
        print("\n🛑 Stopped by user.")
        sys.exit(0)