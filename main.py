#!/usr/bin/env python3
"""
SkySwitcher v0.8
- Mode 1: Double Tap [R_Shift] -> Last word fix + Layout Switch.
- Mode 2: Hold [R_Ctrl] + Tap [R_Shift] -> Selection fix (No Switch).
- Fix: Aggressively releases modifiers to prevent "Ctrl+Shift+C" (Firefox Inspector).
"""

import evdev
from evdev import UInput, ecodes as e
import subprocess
import time
import sys
import argparse

# --- Configuration ---
# Main trigger button
TRIGGER_BTN = e.KEY_RIGHTSHIFT

# Modifier for Mode 2 (Must be held down)
MODE2_MODIFIER = e.KEY_RIGHTCTRL

DOUBLE_PRESS_DELAY = 0.5
LAYOUT_SWITCH_COMBO = [e.KEY_LEFTMETA, e.KEY_SPACE]

# --- MAPPINGS ---
EN_LAYOUT = "`qwertyuiop[]\\asdfghjkl;'zxcvbnm,./~@#$^&QWERTYUIOP{}|ASDFGHJKL:\"ZXCVBNM<>?"
UA_LAYOUT = "'йцукенгшщзхїґфівапролджєячсмитьбю.₴\"№;%:?ЙЦУКЕНГШЩЗХЇҐФІВАПРОЛДЖЄЯЧСМИТЬБЮ,"
TRANS_MAP = str.maketrans(EN_LAYOUT + UA_LAYOUT, UA_LAYOUT + EN_LAYOUT)

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
    def __init__(self, device_path, verbose=False):
        self.verbose = verbose
        try:
            self.dev = evdev.InputDevice(device_path)
            self.log(f"✅ Connected to: {self.dev.name}")
        except OSError as err:
            self.error(f"Failed: {err}")
            sys.exit(1)

        all_keys = [
            e.KEY_LEFTCTRL, e.KEY_LEFTSHIFT, e.KEY_RIGHTCTRL, e.KEY_RIGHTSHIFT,
            e.KEY_C, e.KEY_V,
            e.KEY_LEFT, e.KEY_RIGHT, e.KEY_BACKSPACE, e.KEY_INSERT,
            e.KEY_LEFTMETA, e.KEY_SPACE
        ]

        try:
            self.ui = UInput({e.EV_KEY: all_keys}, name="SkySwitcher-Virtual")
        except Exception as err:
            self.error(f"UInput Error: {err}")
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
        except:
            return ""

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

    def wait_for_clipboard_change(self, old_content, timeout=0.3):
        start = time.time()
        while time.time() - start < timeout:
            new = self.get_clipboard()
            if new != old_content: return new
            time.sleep(0.02)
        return None

    def release_all_modifiers(self):
        """
        Crucial FIX: Logically releases all physical modifiers
        so they don't interfere with virtual keystrokes.
        Prevents 'Ctrl+Shift+C' (Firefox Inspector) when Shift is physically held.
        """
        for key in [e.KEY_LEFTSHIFT, e.KEY_RIGHTSHIFT, e.KEY_LEFTCTRL, e.KEY_RIGHTCTRL]:
            self.ui.write(e.EV_KEY, key, 0)
        self.ui.syn()
        time.sleep(0.05)

    def process_text_replacement(self, mode="last_word"):
        # 1. CLEANUP: Ensure no modifiers are stuck
        self.release_all_modifiers()

        prev_clipboard = self.get_clipboard()

        # 2. Select / Copy
        if mode == "last_word":
            self.send_combo(e.KEY_LEFTCTRL, e.KEY_LEFTSHIFT, e.KEY_LEFT)
            self.send_combo(e.KEY_LEFTCTRL, e.KEY_C)
        else:
            self.send_combo(e.KEY_LEFTCTRL, e.KEY_C)

        # 3. Wait & Check
        original = self.wait_for_clipboard_change(prev_clipboard)

        if not original:
            self.log("Clipboard empty/unchanged.")
            if mode == "last_word": self.send_combo(e.KEY_RIGHT)
            return

        # 4. Translate
        converted = original.translate(TRANS_MAP)
        if original == converted:
            self.log("No transliteration needed.")
            self.send_combo(e.KEY_RIGHT)
            return

        self.log(f"Correcting: '{original}' -> '{converted}'")
        self.set_clipboard(converted)
        time.sleep(0.05)

        # 5. Paste & Cleanup
        self.send_combo(e.KEY_BACKSPACE)
        self.send_combo(e.KEY_LEFTCTRL, e.KEY_V)
        self.send_combo(e.KEY_RIGHT)  # Fix blinking

        # 6. Switch Layout (Only last_word mode)
        if mode == "last_word":
            self.log("Switching layout...")
            time.sleep(0.1)
            self.send_combo(*LAYOUT_SWITCH_COMBO)

    def run(self):
        self.log("🚀 SkySwitcher v0.8 running...")
        try:
            self.dev.grab()
            self.dev.ungrab()
        except:
            pass

        for event in self.dev.read_loop():
            if event.type == e.EV_KEY:

                # Track Modifier (Right Ctrl)
                if event.code == MODE2_MODIFIER:
                    self.modifier_down = (event.value == 1 or event.value == 2)

                # Check Trigger (Right Shift)
                if event.code == TRIGGER_BTN and event.value == 1:

                    # MODE 2: Modifier is held + Trigger pressed
                    if self.modifier_down:
                        self.log("✨ Mode 2: Selection Fix (R_Ctrl + R_Shift)")
                        self.process_text_replacement(mode="selection")
                        # Reset timer so we don't accidentally trigger Mode 1 immediately after
                        self.last_press_time = 0

                        # MODE 1: Just Trigger (Double tap logic)
                    else:
                        now = time.time()
                        if now - self.last_press_time < DOUBLE_PRESS_DELAY:
                            self.log("⚡ Mode 1: Double Shift")
                            self.process_text_replacement(mode="last_word")
                            self.last_press_time = 0
                        else:
                            self.last_press_time = now


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--device", help="Device path")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    if args.list:
        list_devices()
        sys.exit(0)

    path = args.device
    if not path:
        path, _ = find_keyboard_device()
        if not path:
            print("❌ Keyboard not found.", file=sys.stderr)
            sys.exit(1)

    SkySwitcher(path, args.verbose).run()