#!/usr/bin/env python3
"""
SkySwitcher v0.3.1
Key-buffer based layout switcher with Time-based reset.

Changes in v0.3.1:
- LOGIC CHANGE: 'Space' no longer resets the buffer. You can now correct phrases!
- NEW FEATURE: Buffer resets only after IDLE_TIMEOUT (default 3.0s) or non-text keys (Esc, Arrows).
- BUGFIX: Increased delay after Layout Switch to preventing typing before OS switches language.
"""

import evdev
from evdev import UInput, ecodes as e
import time
import sys
import argparse
from collections import deque

# --- CONFIGURATION ---
TRIGGER_BTN = e.KEY_RIGHTSHIFT
DOUBLE_PRESS_DELAY = 0.5

# How long to wait for OS to switch layout (Super+Space) before retyping.
# Increase this if text is retyped in the WRONG layout.
LAYOUT_SWITCH_DELAY = 0.3

# If you stop typing for this many seconds, the buffer clears.
BUFFER_IDLE_TIMEOUT = 3.0

# Max characters to remember (sliding window)
MAX_BUFFER_SIZE = 200

LAYOUT_SWITCH_COMBO = [e.KEY_LEFTMETA, e.KEY_SPACE]

# Keys to record (Letters + Numbers + Symbols + SPACE)
PRINTABLE_KEYS = {
    e.KEY_1, e.KEY_2, e.KEY_3, e.KEY_4, e.KEY_5, e.KEY_6, e.KEY_7, e.KEY_8, e.KEY_9, e.KEY_0,
    e.KEY_MINUS, e.KEY_EQUAL, e.KEY_BACKSPACE, e.KEY_SPACE,  # Space is now printable!
    e.KEY_Q, e.KEY_W, e.KEY_E, e.KEY_R, e.KEY_T, e.KEY_Y, e.KEY_U, e.KEY_I, e.KEY_O, e.KEY_P,
    e.KEY_LEFTBRACE, e.KEY_RIGHTBRACE, e.KEY_BACKSLASH,
    e.KEY_A, e.KEY_S, e.KEY_D, e.KEY_F, e.KEY_G, e.KEY_H, e.KEY_J, e.KEY_K, e.KEY_L,
    e.KEY_SEMICOLON, e.KEY_APOSTROPHE,
    e.KEY_Z, e.KEY_X, e.KEY_C, e.KEY_V, e.KEY_B, e.KEY_N, e.KEY_M,
    e.KEY_COMMA, e.KEY_DOT, e.KEY_SLASH,
    e.KEY_GRAVE, e.KEY_102ND  # Typical on ISO keyboards
}

# Keys that HARD RESET the buffer (Navigation, Esc, Tab)
RESET_KEYS = {
    e.KEY_ENTER, e.KEY_TAB, e.KEY_ESC,
    e.KEY_UP, e.KEY_DOWN, e.KEY_LEFT, e.KEY_RIGHT,
    e.KEY_HOME, e.KEY_END, e.KEY_PAGEUP, e.KEY_PAGEDOWN,
    e.KEY_DELETE
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
    def __init__(self, device_path, verbose=False):
        self.verbose = verbose

        # Buffer stores tuples: (key_code, is_shift_held)
        self.key_buffer = deque(maxlen=MAX_BUFFER_SIZE)

        # State tracking
        self.last_press_time = 0  # For Double Shift
        self.last_typing_time = 0  # For Idle Timeout
        self.shift_pressed = False

        # --- Device Setup ---
        try:
            self.dev = evdev.InputDevice(device_path)
            self.log(f"✅ Connected to: {self.dev.name}")
        except OSError as err:
            self.error(f"Failed to open device: {err}")
            sys.exit(1)

        # Virtual Keyboard
        try:
            self.ui = UInput(name="SkySwitcher-Virtual")
        except Exception as err:
            self.error(f"Failed to create UInput: {err}")
            sys.exit(1)

    def log(self, msg):
        if self.verbose: print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

    def error(self, msg):
        print(f"❌ {msg}", file=sys.stderr)

    def send_combo(self, *keys):
        for k in keys: self.ui.write(e.EV_KEY, k, 1)
        self.ui.syn()
        time.sleep(0.02)
        for k in reversed(keys): self.ui.write(e.EV_KEY, k, 0)
        self.ui.syn()
        time.sleep(0.02)

    def correct_last_phrase(self):
        if not self.key_buffer:
            self.log("Buffer empty.")
            return

        chars_to_delete = len(self.key_buffer)
        self.log(f"⚡ Correcting phrase ({chars_to_delete} chars)...")

        # 1. Backspace everything
        # Optimized for speed, but safe enough not to skip
        for _ in range(chars_to_delete):
            self.ui.write(e.EV_KEY, e.KEY_BACKSPACE, 1)
            self.ui.syn()
            self.ui.write(e.EV_KEY, e.KEY_BACKSPACE, 0)
            self.ui.syn()
            time.sleep(0.002)  # Very fast backspace

        time.sleep(0.05)

        # 2. Switch Layout
        self.log("Switching layout...")
        self.send_combo(*LAYOUT_SWITCH_COMBO)

        # CRITICAL: Wait for OS to actually switch input methods
        time.sleep(LAYOUT_SWITCH_DELAY)

        # 3. Replay Keys
        self.log("Replaying...")
        for key_code, was_shifted in self.key_buffer:
            if was_shifted:
                self.ui.write(e.EV_KEY, e.KEY_LEFTSHIFT, 1)
                self.ui.syn()

            self.ui.write(e.EV_KEY, key_code, 1)
            self.ui.syn()
            self.ui.write(e.EV_KEY, key_code, 0)
            self.ui.syn()

            if was_shifted:
                self.ui.write(e.EV_KEY, e.KEY_LEFTSHIFT, 0)
                self.ui.syn()

            time.sleep(0.005)  # Typing speed

        self.log("Done.")

        # Clear buffer to avoid double-correction loops
        # (Since we replayed keys, we don't want to re-add them to our own buffer if we were listening to virtual)
        # But we listen to HARDWARE. So we don't hear our own typing.
        # However, logically, after correction, we start "fresh".
        self.key_buffer.clear()
        self.last_typing_time = time.time()  # Reset idle timer

    def run(self):
        self.log(f"🚀 SkySwitcher v0.3.1 (Timeout {BUFFER_IDLE_TIMEOUT}s) running...")

        try:
            self.dev.grab()
            self.dev.ungrab()
        except IOError:
            self.log("⚠️  Device grabbed. Running passive.")

        for event in self.dev.read_loop():
            if event.type == e.EV_KEY:
                # --- 1. Track Shift State ---
                if event.code in [e.KEY_LEFTSHIFT, e.KEY_RIGHTSHIFT]:
                    self.shift_pressed = (event.value == 1 or event.value == 2)

                # --- 2. Key Down Logic ---
                if event.value == 1:
                    now = time.time()

                    # A. Check Idle Timeout
                    if now - self.last_typing_time > BUFFER_IDLE_TIMEOUT:
                        if len(self.key_buffer) > 0 and self.verbose:
                            self.log("⏳ Buffer expired (Idle). Cleared.")
                        self.key_buffer.clear()

                    # B. Trigger (Double Shift)
                    if event.code == TRIGGER_BTN:
                        if now - self.last_press_time < DOUBLE_PRESS_DELAY:
                            self.correct_last_phrase()
                            self.last_press_time = 0
                        else:
                            self.last_press_time = now

                    # C. Buffer Logic
                    elif event.code in RESET_KEYS:
                        self.key_buffer.clear()
                        self.last_press_time = 0
                        self.last_typing_time = now  # Update activity time

                    elif event.code in PRINTABLE_KEYS:
                        if event.code == e.KEY_BACKSPACE:
                            if self.key_buffer:
                                self.key_buffer.pop()
                        else:
                            self.key_buffer.append((event.code, self.shift_pressed))

                        self.last_press_time = 0  # Typing breaks double-tap chain
                        self.last_typing_time = now  # Update activity time


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SkySwitcher v0.3.1")
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
            print("❌ Keyboard not found automatically. Use --list", file=sys.stderr)
            sys.exit(1)

    try:
        SkySwitcher(path, args.verbose).run()
    except KeyboardInterrupt:
        print("\n🛑 Stopped by user.")
        sys.exit(0)