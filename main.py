#!/usr/bin/env python3
"""
SkySwitcher v0.2.1
A minimal Wayland/Linux layout switcher & corrector.

Features:
1. Double Tap [Right Shift]:
   - Selects last word (Ctrl+Shift+Left).
   - Translates text (EN <-> UA).
   - Switches system layout (Meta+Space).

2. Hold [Right Ctrl] + Tap [Right Shift]:
   - Translates currently selected text.
   - Does NOT switch system layout.

Requirements:
- 'evdev' python library.
- 'wl-clipboard' installed in system.
- User must be in 'input' and 'uinput' groups.
"""

import evdev
from evdev import UInput, ecodes as e
import subprocess
import time
import sys
import argparse

# --- CONFIGURATION ---
TRIGGER_BTN = e.KEY_RIGHTSHIFT  # Primary Trigger
MODE2_MODIFIER = e.KEY_RIGHTCTRL  # Modifier for Selection Mode

DOUBLE_PRESS_DELAY = 0.5  # Max time between shifts (seconds)
LAYOUT_SWITCH_COMBO = [e.KEY_LEFTMETA, e.KEY_SPACE]

# --- LAYOUT MAPPINGS ---
# Row 1: ` -> ' (Backtick/Tilde line)
# Row 2: QWERTY...
# Row 3: ASDF... (Including backslash '\' mapping to 'ґ')
# Row 4: ZXCV...
EN_LAYOUT = "`qwertyuiop[]\\asdfghjkl;'zxcvbnm,./~@#$^&QWERTYUIOP{}|ASDFGHJKL:\"ZXCVBNM<>?"
UA_LAYOUT = "'йцукенгшщзхїґфівапролджєячсмитьбю.₴\"№;%:?ЙЦУКЕНГШЩЗХЇҐФІВАПРОЛДЖЄЯЧСМИТЬБЮ,"
TRANS_MAP = str.maketrans(EN_LAYOUT + UA_LAYOUT, UA_LAYOUT + EN_LAYOUT)

# Devices to ignore during auto-detection
IGNORED_KEYWORDS = [
    'mouse', 'webcam', 'audio', 'video', 'consumer',
    'control', 'headset', 'receiver', 'solaar', 'hotkeys'
]


def list_devices():
    """Prints all available input devices for debugging."""
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    devices.sort(key=lambda x: x.path)
    print(f"{'PATH':<20} | {'NAME'}")
    print("-" * 50)
    for dev in devices:
        print(f"{dev.path:<20} | {dev.name}")


def find_keyboard_device():
    """Auto-detects the most likely physical keyboard."""
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    possible_candidates = []

    for dev in devices:
        name = dev.name.lower()
        if any(bad in name for bad in IGNORED_KEYWORDS): continue
        if e.EV_KEY not in dev.capabilities(): continue

        keys = dev.capabilities()[e.EV_KEY]
        # Must have basic typing keys to be considered a keyboard
        if {e.KEY_SPACE, e.KEY_ENTER, e.KEY_A, e.KEY_Z}.issubset(keys):
            # Priority: Name contains 'keyboard'
            if 'keyboard' in name or 'kbd' in name: return dev.path, dev.name
            possible_candidates.append((dev.path, dev.name))

    return possible_candidates[0] if possible_candidates else (None, None)


class SkySwitcher:
    def __init__(self, device_path, verbose=False):
        self.verbose = verbose
        try:
            self.dev = evdev.InputDevice(device_path)
            self.log(f"✅ Connected to: {self.dev.name}")
        except OSError as err:
            self.error(f"Failed to open device: {err}")
            sys.exit(1)

        # Register keys that the Virtual Keyboard needs to press
        all_keys = [
            e.KEY_LEFTCTRL, e.KEY_LEFTSHIFT, e.KEY_RIGHTCTRL, e.KEY_RIGHTSHIFT,
            e.KEY_C, e.KEY_V,
            e.KEY_LEFT, e.KEY_RIGHT, e.KEY_BACKSPACE,
            e.KEY_LEFTMETA, e.KEY_SPACE
        ]

        try:
            self.ui = UInput({e.EV_KEY: all_keys}, name="SkySwitcher-Virtual")
        except Exception as err:
            self.error(f"Failed to create UInput device: {err}")
            self.error("Ensure 'uinput' module is loaded and user has permissions.")
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
            self.error("wl-paste not found. Please install wl-clipboard.")
            return ""

    def clear_clipboard(self):
        """Clears clipboard to ensure we detect NEW copy events."""
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
        """Simulates pressing a combination of keys."""
        for k in keys: self.ui.write(e.EV_KEY, k, 1)
        self.ui.syn()
        time.sleep(0.02)
        for k in reversed(keys): self.ui.write(e.EV_KEY, k, 0)
        self.ui.syn()
        time.sleep(0.02)

    def release_all_modifiers(self):
        """Releases physical modifiers to prevent interference (e.g. F12/Inspector)."""
        for key in [e.KEY_LEFTSHIFT, e.KEY_RIGHTSHIFT, e.KEY_LEFTCTRL, e.KEY_RIGHTCTRL]:
            self.ui.write(e.EV_KEY, key, 0)
        self.ui.syn()
        time.sleep(0.05)

    def wait_for_new_content(self, timeout=0.5):
        """Waits for ANY content to appear in clipboard."""
        start = time.time()
        while time.time() - start < timeout:
            content = self.get_clipboard()
            if content: return content
            time.sleep(0.02)
        return None

    def process_text_replacement(self, mode="last_word"):
        # 1. Safety: Release modifiers immediately
        self.release_all_modifiers()

        # 2. Backup current clipboard (to restore if copy fails)
        backup_clipboard = self.get_clipboard()

        # 3. Clear clipboard to avoid reading stale data
        self.clear_clipboard()
        time.sleep(0.05)

        # 4. Perform Selection & Copy
        if mode == "last_word":
            # Select last word (Ctrl+Shift+Left) -> Copy
            self.send_combo(e.KEY_LEFTCTRL, e.KEY_LEFTSHIFT, e.KEY_LEFT)
            self.send_combo(e.KEY_LEFTCTRL, e.KEY_C)
        else:
            # Selection mode: Just Copy
            self.send_combo(e.KEY_LEFTCTRL, e.KEY_C)

        # 5. Wait for copy to succeed
        original = self.wait_for_new_content()

        if not original:
            self.log("Copy failed or timed out. Restoring backup.")
            self.set_clipboard(backup_clipboard)
            # Deselect to restore UI state
            if mode == "last_word": self.send_combo(e.KEY_RIGHT)
            return

        # 6. Transliterate
        converted = original.translate(TRANS_MAP)
        if original == converted:
            self.log("No transliteration needed.")
            self.send_combo(e.KEY_RIGHT)
            return

        self.log(f"Correcting: '{original}' -> '{converted}'")
        self.set_clipboard(converted)
        time.sleep(0.05)  # Wait for wl-copy to write

        # 7. Replace Text
        self.send_combo(e.KEY_BACKSPACE)
        self.send_combo(e.KEY_LEFTCTRL, e.KEY_V)
        self.send_combo(e.KEY_RIGHT)  # Fix blinking selection

        # 8. Switch Layout (Only in Last Word mode)
        if mode == "last_word":
            self.log("Switching system layout...")
            time.sleep(0.1)
            self.send_combo(*LAYOUT_SWITCH_COMBO)

    def run(self):
        self.log("🚀 SkySwitcher v0.2.1 running...")

        # Attempt to grab device exclusively (optional check)
        try:
            self.dev.grab()
            self.dev.ungrab()
        except IOError:
            self.log("⚠️  Warning: Device grabbed by another process. Running in passive mode.")

        for event in self.dev.read_loop():
            if event.type == e.EV_KEY:

                # Update Modifier State (R_Ctrl)
                if event.code == MODE2_MODIFIER:
                    self.modifier_down = (event.value == 1 or event.value == 2)  # Down or Hold

                # Check Trigger (R_Shift)
                if event.code == TRIGGER_BTN and event.value == 1:  # Key Down

                    if self.modifier_down:
                        # MODE 2: Modifier + Trigger
                        self.log("✨ Mode 2: Selection Fix (R_Ctrl + R_Shift)")
                        self.process_text_replacement(mode="selection")
                        self.last_press_time = 0
                    else:
                        # MODE 1: Double Tap Logic
                        now = time.time()
                        if now - self.last_press_time < DOUBLE_PRESS_DELAY:
                            self.log("⚡ Mode 1: Double Shift")
                            self.process_text_replacement(mode="last_word")
                            self.last_press_time = 0
                        else:
                            self.last_press_time = now


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SkySwitcher Layout Corrector")
    parser.add_argument("-d", "--device", help="Path to input device")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--list", action="store_true", help="List available devices")
    args = parser.parse_args()

    if args.list:
        list_devices()
        sys.exit(0)

    path = args.device
    if not path:
        path, _ = find_keyboard_device()
        if not path:
            print("❌ Keyboard not found automatically.", file=sys.stderr)
            print("   Use --list to find it, then --device to specify path.", file=sys.stderr)
            sys.exit(1)

    try:
        SkySwitcher(path, args.verbose).run()
    except KeyboardInterrupt:
        print("\n🛑 Stopped by user.")
        sys.exit(0)