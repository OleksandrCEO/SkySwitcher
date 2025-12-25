#!/usr/bin/env python3
"""
SkySwitcher
Key-buffer based layout switcher with Time-based reset.

Changes in v0.3.3:
- Refactored into modular OOP architecture (DeviceManager, SkySwitcher).
- Restored strict device detection (checking EV_KEY & specific keys A, Z, Space).
- Removed all automatic triggers (manual control focus).
- Finalized 'Lazy Reset' logic for optimal performance.

"""

import sys
import os
import time
import logging
from typing import Optional, List, Set
from evdev import InputDevice, ecodes, list_devices

# --- Configuration ---
VERSION = "0.3.3"
TIMEOUT_SECONDS = 3.0  # Reset buffer only if typing resumes after this gap
LOG_LEVEL = logging.DEBUG

# --- Logging Setup ---
logging.basicConfig(
    level=LOG_LEVEL,
    format='[%(asctime)s] %(message)s',
    datefmt='%H:%M:%S',
    handlers=[logging.StreamHandler(sys.stdout)]
)
# Create a specific logger for our app
logger = logging.getLogger("SkySwitcher")


class DeviceManager:
    """
    Manages input device connection using capability detection.
    Robust against virtual devices, mice, and webcams.
    """

    IGNORED_KEYWORDS = [
        'mouse', 'webcam', 'audio', 'video', 'consumer',
        'control', 'headset', 'receiver', 'solaar', 'hotkeys',
        'button', 'switch', 'hda', 'dock'
    ]

    # Essential keys for a typing keyboard (A, Z, Space, Enter)
    REQUIRED_KEYS = {
        ecodes.KEY_SPACE, ecodes.KEY_ENTER,
        ecodes.KEY_A, ecodes.KEY_Z
    }

    @staticmethod
    def find_keyboard() -> InputDevice:
        """
        Scans input devices and returns the best candidate for a keyboard.
        """
        logger.info("🔍 Scanning for keyboards...")

        # Sort by path for deterministic behavior
        devices = [InputDevice(path) for path in list_devices()]
        devices.sort(key=lambda x: x.path)

        possible_candidates = []

        for dev in devices:
            name_lower = dev.name.lower()

            # 1. Filter out non-keyboards by name
            if any(bad in name_lower for bad in DeviceManager.IGNORED_KEYWORDS):
                continue

            # 2. Check capabilities (Must have EV_KEY)
            caps = dev.capabilities()
            if ecodes.EV_KEY not in caps:
                continue

            # 3. Check for specific keys
            supported_keys = set(caps[ecodes.EV_KEY])
            if DeviceManager.REQUIRED_KEYS.issubset(supported_keys):
                # Priority 1: Explicitly named "keyboard"
                if 'keyboard' in name_lower or 'kbd' in name_lower:
                    logger.info(f"✅ Primary keyboard found: {dev.name} ({dev.path})")
                    return dev

                # Priority 2: Fits criteria but generic name
                possible_candidates.append(dev)

        if possible_candidates:
            best_guess = possible_candidates[0]
            logger.warning(f"⚠️  Ambiguous device name, but looks like a keyboard: {best_guess.name}")
            return best_guess

        logger.error("❌ No suitable keyboard found! Check permissions (sudo).")
        sys.exit(1)


class CharacterMapper:
    """
    Maps hardware scancodes to simple characters for buffer tracking.
    Note: This does not handle Shift state (Case), as we only track raw keys for correction logic.
    """

    def __init__(self):
        self.map = {
            ecodes.KEY_A: 'a', ecodes.KEY_B: 'b', ecodes.KEY_C: 'c', ecodes.KEY_D: 'd',
            ecodes.KEY_E: 'e', ecodes.KEY_F: 'f', ecodes.KEY_G: 'g', ecodes.KEY_H: 'h',
            ecodes.KEY_I: 'i', ecodes.KEY_J: 'j', ecodes.KEY_K: 'k', ecodes.KEY_L: 'l',
            ecodes.KEY_M: 'm', ecodes.KEY_N: 'n', ecodes.KEY_O: 'o', ecodes.KEY_P: 'p',
            ecodes.KEY_Q: 'q', ecodes.KEY_R: 'r', ecodes.KEY_S: 's', ecodes.KEY_T: 't',
            ecodes.KEY_U: 'u', ecodes.KEY_V: 'v', ecodes.KEY_W: 'w', ecodes.KEY_X: 'x',
            ecodes.KEY_Y: 'y', ecodes.KEY_Z: 'z',
            ecodes.KEY_1: '1', ecodes.KEY_2: '2', ecodes.KEY_3: '3', ecodes.KEY_4: '4',
            ecodes.KEY_5: '5', ecodes.KEY_6: '6', ecodes.KEY_7: '7', ecodes.KEY_8: '8',
            ecodes.KEY_9: '9', ecodes.KEY_0: '0',
            ecodes.KEY_MINUS: '-', ecodes.KEY_EQUAL: '=',
            ecodes.KEY_LEFTBRACE: '[', ecodes.KEY_RIGHTBRACE: ']',
            ecodes.KEY_SEMICOLON: ';', ecodes.KEY_APOSTROPHE: "'",
            ecodes.KEY_COMMA: ',', ecodes.KEY_DOT: '.', ecodes.KEY_SLASH: '/',
            ecodes.KEY_GRAVE: '`', ecodes.KEY_BACKSLASH: '\\'
        }

    def get_char(self, scancode: int) -> Optional[str]:
        return self.map.get(scancode)


class SkySwitcher:
    def __init__(self):
        self.device = DeviceManager.find_keyboard()
        self.mapper = CharacterMapper()

        self.buffer = ""
        self.last_key_time = time.time()

        # Track modifiers to ignore shortcuts (Ctrl+C, etc)
        self.modifiers_state = {
            k: False for k in [
                ecodes.KEY_LEFTCTRL, ecodes.KEY_RIGHTCTRL,
                ecodes.KEY_LEFTALT, ecodes.KEY_RIGHTALT,
                ecodes.KEY_LEFTMETA, ecodes.KEY_RIGHTMETA
            ]
        }

    def _is_modifier_active(self) -> bool:
        return any(self.modifiers_state.values())

    def _handle_lazy_reset(self):
        """
        Checks if too much time has passed since the last keystroke.
        If yes, clears the buffer BEFORE processing the new key.
        """
        current_time = time.time()
        if (current_time - self.last_key_time) > TIMEOUT_SECONDS:
            if self.buffer:
                # Log only if we are discarding something, to avoid spam
                logger.debug(f"⏳ Timeout ({TIMEOUT_SECONDS}s). Buffer cleared.")
            self.buffer = ""
        self.last_key_time = current_time

    def run(self):
        logger.info(f"🚀 SkySwitcher {VERSION} running...")

        try:
            for event in self.device.read_loop():
                if event.type == ecodes.EV_KEY:
                    self.process_key_event(event)
        except KeyboardInterrupt:
            logger.info("\n🛑 Stopped by user.")
        except OSError as e:
            logger.error(f"❌ Device error: {e}")

    def process_key_event(self, event):
        code = event.code
        val = event.value

        # 1. Update Modifiers State
        if code in self.modifiers_state:
            self.modifiers_state[code] = (val > 0)  # 1=Down, 2=Hold
            return

        # We only care about Key Down (1)
        if val != 1:
            return

        # 2. Lazy Reset (Crucial fix for pauses)
        self._handle_lazy_reset()

        # 3. Handle Special Keys (Backspace, Space, etc.)
        if code == ecodes.KEY_BACKSPACE:
            self.buffer = self.buffer[:-1]
            logger.info(f"🔙 BS. Buffer: [{self.buffer}]")
            return

        if code in [ecodes.KEY_SPACE, ecodes.KEY_ENTER, ecodes.KEY_TAB, ecodes.KEY_ESC]:
            if self.buffer:
                logger.info(f"⏹️ Word End: [{self.buffer}]")
                self.buffer = ""  # Start fresh next time
            return

        # 4. Filter shortcuts
        if self._is_modifier_active():
            if self.buffer:
                logger.info("🔒 Shortcut detected. Buffer cleared.")
                self.buffer = ""
            return

        # 5. Add to Buffer
        char = self.mapper.get_char(code)
        if char:
            self.buffer += char
            # Log current state to verify logic
            logger.info(f"🔤 Typed: '{char}' | Buffer: [{self.buffer}]")


if __name__ == "__main__":
    if os.geteuid() != 0:
        logger.warning("⚠️  Script requires root privileges to read input devices.")
        logger.warning("   Run: sudo python3 main.py")

    app = SkySwitcher()
    app.run()