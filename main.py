# main.py

# SkySwitcher v0.4.3 (No-Clipboard Edition)
# Evolution:
# - Removed: wl-clipboard dependency, TextProcessor, Selection Mode.
# - Added: InputBuffer to track physical keystrokes.
# - Strategy: "Replay" logic. Instead of translating text, we simply
#   delete the wrong keystrokes, switch layout, and re-type them.

import sys
import time
import logging
import argparse
from evdev import InputDevice, UInput, ecodes as e, list_devices

# --- Configuration ---
VERSION = "0.4.3"
DOUBLE_PRESS_DELAY = 0.5
LAYOUT_SWITCH_COMBO = [e.KEY_LEFTMETA, e.KEY_SPACE]


# --- Logging Setup ---
class EmojiFormatter(logging.Formatter):
    def format(self, record):
        log_time = time.strftime("%H:%M:%S", time.localtime(record.created))
        return f"[{log_time}] {record.getMessage()}"


handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(EmojiFormatter())
logger = logging.getLogger("SkySwitcher")
logger.addHandler(handler)


class DeviceManager:
    IGNORED_KEYWORDS = [
        'mouse', 'webcam', 'audio', 'video', 'consumer',
        'control', 'headset', 'receiver', 'solaar', 'hotkeys',
        'button', 'switch', 'hda', 'dock', 'deck', 'touchpad'
    ]
    REQUIRED_KEYS = {e.KEY_SPACE, e.KEY_ENTER, e.KEY_A, e.KEY_Z}

    @staticmethod
    def list_available():
        devices = []
        try:
            devices = [InputDevice(path) for path in list_devices()]
        except OSError:
            print("❌ Failed to list devices.", file=sys.stderr)
            return
        devices.sort(key=lambda x: x.path)
        print(f"{'PATH':<20} | {'NAME'}")
        print("-" * 60)
        for dev in devices:
            print(f"{dev.path:<20} | {dev.name}")

    @staticmethod
    def find_keyboard() -> InputDevice:
        devices = []
        try:
            devices = [InputDevice(path) for path in list_devices()]
        except OSError:
            logger.error("❌ Failed to list devices. Check permissions.")
            sys.exit(1)

        devices.sort(key=lambda x: x.path)
        possible_candidates = []

        for dev in devices:
            name_lower = dev.name.lower()
            if any(bad in name_lower for bad in DeviceManager.IGNORED_KEYWORDS):
                continue
            if e.EV_KEY not in dev.capabilities():
                continue
            supported_keys = set(dev.capabilities()[e.EV_KEY])
            if DeviceManager.REQUIRED_KEYS.issubset(supported_keys):
                if 'keyboard' in name_lower or 'kbd' in name_lower:
                    logger.info(f"✅ Auto-detected: {dev.name}")
                    return dev
                possible_candidates.append(dev)

        if possible_candidates:
            logger.info(f"✅ Auto-detected (best guess): {possible_candidates[0].name}")
            return possible_candidates[0]

        logger.error("❌ No keyboard found. Use --list.")
        sys.exit(1)


class InputBuffer:
    """
    Tracks the history of typed keys to allow 'replay' on a different layout.
    Stores tuples: (keycode, is_shifted)
    """

    def __init__(self):
        self.buffer = []
        # Keys that reset the buffer (safety mechanism)
        self.reset_keys = {
            e.KEY_ENTER, e.KEY_ESC, e.KEY_TAB,
            e.KEY_UP, e.KEY_DOWN, e.KEY_LEFT, e.KEY_RIGHT,
            e.KEY_HOME, e.KEY_END, e.KEY_PAGEUP, e.KEY_PAGEDOWN
        }
        # Keys that we want to track for replay (letters, numbers, punctuation, space)
        # We define a range or logic check in the `add` method, but here are explicit ones:
        self.trackable_range = range(e.KEY_1, e.KEY_SLASH + 1)  # Covers most main block keys

    def add(self, keycode, is_shifted):
        # If it's a "Reset" key (like Enter or Arrows), clear history
        if keycode in self.reset_keys:
            self.clear()
            return

        # If Backspace, remove last item
        if keycode == e.KEY_BACKSPACE:
            if self.buffer:
                self.buffer.pop()
            return

        # If it's a standard typing key, add to buffer
        if keycode == e.KEY_SPACE or keycode in self.trackable_range:
            self.buffer.append((keycode, is_shifted))
            # Limit buffer size to prevent memory issues (though unlikely)
            if len(self.buffer) > 100:
                self.buffer.pop(0)

    def clear(self):
        self.buffer = []

    def get_last_phrase(self):
        """
        Returns the keys for the last 'word' plus any trailing spaces.
        Example: [k_H, k_I, k_SPACE, k_T, k_H, k_E, k_R, k_E, k_SPACE, k_SPACE]
        Returns: [k_T, k_H, k_E, k_R, k_E, k_SPACE, k_SPACE]
        """
        if not self.buffer:
            return []

        # Iterate backwards
        result = []
        found_char = False

        for item in reversed(self.buffer):
            code, shift = item

            if code == e.KEY_SPACE:
                if found_char:
                    # We found a space AFTER finding characters -> Word boundary
                    break
                else:
                    # We are in trailing spaces
                    result.insert(0, item)
            else:
                # Normal character
                found_char = True
                result.insert(0, item)

        return result


class SkySwitcher:
    def __init__(self, device_path=None):
        if device_path:
            try:
                self.device = InputDevice(device_path)
                logger.info(f"✅ Manual Device: {self.device.name}")
            except OSError:
                sys.exit(1)
        else:
            self.device = DeviceManager.find_keyboard()

        # Virtual Input Setup
        self.uinput_keys = [
            e.KEY_LEFTCTRL, e.KEY_LEFTSHIFT, e.KEY_RIGHTCTRL, e.KEY_RIGHTSHIFT,
            e.KEY_LEFTMETA, e.KEY_LEFTALT, e.KEY_BACKSPACE, e.KEY_SPACE,
            # Add all standard keys to UInput capability
            *range(e.KEY_ESC, e.KEY_MICMUTE)
        ]

        try:
            self.ui = UInput({e.EV_KEY: self.uinput_keys}, name="SkySwitcher-Virtual")
        except OSError:
            logger.error("❌ Failed to create UInput.")
            sys.exit(1)

        self.input_buffer = InputBuffer()
        self.last_press_time = 0
        self.trigger_released = True
        self.trigger_btn = e.KEY_RIGHTSHIFT

        # Modifier tracking
        self.shift_pressed = False

    def send_combo(self, *keys):
        for k in keys:
            self.ui.write(e.EV_KEY, k, 1)
        self.ui.syn()
        time.sleep(0.02)
        for k in reversed(keys):
            self.ui.write(e.EV_KEY, k, 0)
        self.ui.syn()
        time.sleep(0.02)

    def replay_keys(self, key_sequence):
        """Re-types the keys from the buffer."""
        for code, use_shift in key_sequence:
            if use_shift:
                self.ui.write(e.EV_KEY, e.KEY_LEFTSHIFT, 1)
                self.ui.syn()

            self.ui.write(e.EV_KEY, code, 1)
            self.ui.syn()
            self.ui.write(e.EV_KEY, code, 0)
            self.ui.syn()

            if use_shift:
                self.ui.write(e.EV_KEY, e.KEY_LEFTSHIFT, 0)
                self.ui.syn()

            time.sleep(0.005)  # Tiny delay for stability

    def fix_last_word(self):
        # 1. Get keys to fix
        keys_to_replay = self.input_buffer.get_last_phrase()

        if not keys_to_replay:
            logger.info("⚠️ Buffer empty or no word found.")
            return

        count = len(keys_to_replay)
        logger.info(f"🔄 Replaying {count} keys on new layout...")

        # 2. Delete current wrong text (Backspace x Count)
        for _ in range(count):
            self.ui.write(e.EV_KEY, e.KEY_BACKSPACE, 1)
            self.ui.syn()
            self.ui.write(e.EV_KEY, e.KEY_BACKSPACE, 0)
            self.ui.syn()
            time.sleep(0.002)

        # 3. Switch Layout
        self.send_combo(*LAYOUT_SWITCH_COMBO)
        time.sleep(0.1)  # Wait for OS to switch

        # 4. Replay keys (OS will map them to new layout)
        self.replay_keys(keys_to_replay)

        # 5. Clear buffer so we don't double-fix
        self.input_buffer.clear()

    def run(self):
        logger.info(f"🚀 SkySwitcher v{VERSION} (No-Clipboard Mode)")

        try:
            self.device.grab()
            self.device.ungrab()
        except Exception:
            logger.warning("⚠️ Device grabbed. Running passive.")

        try:
            for event in self.device.read_loop():
                if event.type == e.EV_KEY:

                    # Track Modifier State (Shift)
                    if event.code in [e.KEY_LEFTSHIFT, e.KEY_RIGHTSHIFT]:
                        self.shift_pressed = (event.value == 1 or event.value == 2)

                    # Trigger Logic (Right Shift)
                    if event.code == self.trigger_btn:
                        if event.value == 0:
                            self.trigger_released = True
                        elif event.value == 1:
                            now = time.time()
                            if (now - self.last_press_time < DOUBLE_PRESS_DELAY) and self.trigger_released:
                                self.fix_last_word()
                                self.last_press_time = 0
                                self.trigger_released = False
                            else:
                                self.last_press_time = now
                                self.trigger_released = False

                    # Buffer Tracking Logic
                    # Only process key DOWN (1) or REPEAT (2) events
                    elif event.value in [1, 2]:
                        # Don't add the trigger key itself to buffer
                        if event.code != self.trigger_btn:
                            self.input_buffer.add(event.code, self.shift_pressed)

                        # Reset double-press timer if user types other keys
                        if self.last_press_time > 0:
                            self.last_press_time = 0

        except KeyboardInterrupt:
            print("\n🛑 Stopped by user.")
        except OSError as err:
            logger.error(f"❌ Device error: {err}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--device", help="Path to input device")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--list", action="store_true", help="List available devices")
    args = parser.parse_args()

    if args.list:
        DeviceManager.list_available()
        sys.exit(0)

    if args.verbose:
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.WARNING)

    SkySwitcher(device_path=args.device).run()
