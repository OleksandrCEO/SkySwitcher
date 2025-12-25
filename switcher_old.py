#!/usr/bin/env python

import subprocess
import time
import os
from collections import deque
from evdev import InputDevice, ecodes, list_devices
import sys


# ====== Налаштування ======
def find_keyboard_device():
    user_specific_path = '/dev/input/by-id/usb-SIGMACHIP_USB_Keyboard-event-kbd'
    if os.path.exists(user_specific_path):
        print(f"Found user-specific keyboard: {user_specific_path}")
        return user_specific_path
    print(f"Path {user_specific_path} not found. Trying auto-discovery...")
    devices = [InputDevice(path) for path in list_devices()]
    for device in devices:
        if 'event-kbd' in device.path:
            print(f"Found keyboard by 'event-kbd' in path: {device.path} ({device.name})")
            return device.path
    for device in devices:
        name_lower = device.name.lower()
        if 'keyboard' in name_lower and 'system control' not in name_lower:
            print(f"Found keyboard by name (excluding controls): {device.path} ({device.name})")
            return device.path
    print("Auto-discovery FAILED. Using fallback path (may not work).")
    return user_specific_path


# Перевірка наявності Wayland-інструментів
def check_dependencies():
    # === ВИПРАВЛЕНО 'qdbus6' на 'qdbus' ===
    deps = ['qdbus', 'ydotool', 'wl-paste']
    missing = []
    for dep in deps:
        if subprocess.run(['which', dep], capture_output=True).returncode != 0:
            missing.append(dep)
    if missing:
        print(f"ПОМИЛКА: Не знайдено необхідні програми: {', '.join(missing)}", file=sys.stderr)
        print("Будь ласка, додайте їх до configuration.nix та перезберіть систему.", file=sys.stderr)
        sys.exit(1)

    # Перевірка, чи запущений ydotd
    try:
        subprocess.run(['ydotool', 'list'], capture_output=True, check=True, timeout=1)
    except Exception:
        print("ПОМИЛКА: Не вдалося підключитися до 'ydotd'.", file=sys.stderr)
        print("Переконайтеся, що сервіс ydotoold налаштований у configuration.nix", file=sys.stderr)
        print("І що ваш користувач у групах 'uinput' та 'ydotd' (потрібне перезавантаження).", file=sys.stderr)
        sys.exit(1)

    print("Усі залежності (qdbus, ydotool, wl-paste) знайдено.")


DEVICE = find_keyboard_device()
RIGHT_SHIFT = ecodes.KEY_RIGHTSHIFT
RIGHT_CTRL = ecodes.KEY_RIGHTCTRL
DOUBLE_TAP_INTERVAL = 0.4  # 400ms
CACHE_SIZE = 50

# Розкладки, як вони визначені у вашому configuration.nix
# 0 = 'us', 1 = 'ua'
LAYOUTS = ['us', 'ua']

# ====== Мапи розкладок ======
LAYOUT_MAPS = {
    'us': {
        ecodes.KEY_Q: 'q', ecodes.KEY_W: 'w', ecodes.KEY_E: 'e', ecodes.KEY_R: 'r',
        ecodes.KEY_T: 't', ecodes.KEY_Y: 'y', ecodes.KEY_U: 'u', ecodes.KEY_I: 'i',
        ecodes.KEY_O: 'o', ecodes.KEY_P: 'p', ecodes.KEY_LEFTBRACE: '[', ecodes.KEY_RIGHTBRACE: ']',
        ecodes.KEY_A: 'a', ecodes.KEY_S: 's', ecodes.KEY_D: 'd', ecodes.KEY_F: 'f',
        ecodes.KEY_G: 'g', ecodes.KEY_H: 'h', ecodes.KEY_J: 'j', ecodes.KEY_K: 'k',
        ecodes.KEY_L: 'l', ecodes.KEY_SEMICOLON: ';', ecodes.KEY_APOSTROPHE: "'", ecodes.KEY_GRAVE: '`',
        ecodes.KEY_Z: 'z', ecodes.KEY_X: 'x', ecodes.KEY_C: 'c', ecodes.KEY_V: 'v',
        ecodes.KEY_B: 'b', ecodes.KEY_N: 'n', ecodes.KEY_M: 'm', ecodes.KEY_COMMA: ',',
        ecodes.KEY_DOT: '.', ecodes.KEY_SLASH: '/',
        ecodes.KEY_SPACE: ' ', ecodes.KEY_MINUS: '-', ecodes.KEY_EQUAL: '=',
        ecodes.KEY_1: '1', ecodes.KEY_2: '2', ecodes.KEY_3: '3', ecodes.KEY_4: '4',
        ecodes.KEY_5: '5', ecodes.KEY_6: '6', ecodes.KEY_7: '7', ecodes.KEY_8: '8',
        ecodes.KEY_9: '9', ecodes.KEY_0: '0',
    },
    'ua': {
        ecodes.KEY_Q: 'й', ecodes.KEY_W: 'ц', ecodes.KEY_E: 'у', ecodes.KEY_R: 'к',
        ecodes.KEY_T: 'е', ecodes.KEY_Y: 'н', ecodes.KEY_U: 'г', ecodes.KEY_I: 'ш',
        ecodes.KEY_O: 'щ', ecodes.KEY_P: 'з', ecodes.KEY_LEFTBRACE: 'х', ecodes.KEY_RIGHTBRACE: 'ї',
        ecodes.KEY_A: 'ф', ecodes.KEY_S: 'і', ecodes.KEY_D: 'в', ecodes.KEY_F: 'а',
        ecodes.KEY_G: 'п', ecodes.KEY_H: 'р', ecodes.KEY_J: 'о', ecodes.KEY_K: 'л',
        ecodes.KEY_L: 'д', ecodes.KEY_SEMICOLON: 'ж', ecodes.KEY_APOSTROPHE: "є", ecodes.KEY_GRAVE: "'",
        ecodes.KEY_Z: 'я', ecodes.KEY_X: 'ч', ecodes.KEY_C: 'с', ecodes.KEY_V: 'м',
        ecodes.KEY_B: 'и', ecodes.KEY_N: 'т', ecodes.KEY_M: 'ь', ecodes.KEY_COMMA: 'б',
        ecodes.KEY_DOT: 'ю', ecodes.KEY_SLASH: '.',
        ecodes.KEY_SPACE: ' ', ecodes.KEY_MINUS: '-', ecodes.KEY_EQUAL: '=',
        ecodes.KEY_1: '1', ecodes.KEY_2: '2', ecodes.KEY_3: '3', ecodes.KEY_4: '44',
        ecodes.KEY_5: '5', ecodes.KEY_6: '6', ecodes.KEY_7: '7', ecodes.KEY_8: '8',
        ecodes.KEY_9: '9', ecodes.KEY_0: '0',
    }
}
REVERSE_LAYOUT_MAPS = {lang: {char: code for code, char in layout_map.items()} for lang, layout_map in
                       LAYOUT_MAPS.items()}
NON_CLEARING_KEYS = {
    ecodes.KEY_LEFTSHIFT, ecodes.KEY_RIGHTSHIFT,
    ecodes.KEY_LEFTCTRL, ecodes.KEY_RIGHTCTRL,
    ecodes.KEY_LEFTALT, ecodes.KEY_RIGHTALT,
    ecodes.KEY_LEFTMETA, ecodes.KEY_RIGHTMETA,
    ecodes.KEY_CAPSLOCK,
}

# ====== Глобальні змінні ======
last_shift_press = 0
last_ctrl_press = 0
cache = deque(maxlen=CACHE_SIZE)


# ====== Wayland-специфічні функції ======
def get_current_layout_index():
    try:
        # === ВИПРАВЛЕНО 'qdbus6' на 'qdbus' ===
        output = subprocess.run(
            ['qdbus', 'org.kde.keyboard', '/Layouts', 'getLayout'],
            capture_output=True, text=True, check=True
        )
        return int(output.stdout.strip())
    except Exception as e:
        print(f"Error getting layout index: {e}")
        return 0  # Повертаємо 0 ('us') за замовчуванням


def set_layout_index(index):
    try:
        # === ВИПРАВЛЕНО 'qdbus6' на 'qdbus' ===
        subprocess.run(
            ['qdbus', 'org.kde.keyboard', '/Layouts', 'setLayout', str(index)],
            check=True
        )
        print(f"Switched layout to index {index} ({LAYOUTS[index]})")
    except Exception as e:
        print(f"Error setting layout: {e}")


def wayland_type(text):
    try:
        for char in text:
            subprocess.run(['ydotool', 'type', char], check=True)
            time.sleep(0.005)
    except Exception as e:
        print(f"Error typing with ydotool: {e}")


def wayland_backspace(count):
    try:
        command = []
        for _ in range(count):
            command.extend(['14:1', '14:0'])  # 14 = KEY_BACKSPACE
        subprocess.run(['ydotool', 'key'] + command, check=True)
    except Exception as e:
        print(f"Error backspacing with ydotool: {e}")


# ====== Основні функції ======
def correct_last_typed():
    global cache

    current_index = get_current_layout_index()
    current_layout = LAYOUTS[current_index]

    next_index = (current_index + 1) % len(LAYOUTS)
    next_layout = LAYOUTS[next_index]

    from_map = LAYOUT_MAPS.get(current_layout)
    to_map = LAYOUT_MAPS.get(next_layout)

    if not from_map or not to_map:
        print(f"Error: Layout maps for '{current_layout}' or '{next_layout}' not found.")
        cache.clear()
        return

    codes_to_translate = list(cache)
    cache.clear()

    if not codes_to_translate:
        set_layout_index(next_index)
        return

    correct_string_chars = [to_map.get(code, from_map.get(code, '')) for code in codes_to_translate]
    correct_string = "".join(correct_string_chars)

    wayland_backspace(len(codes_to_translate))
    set_layout_index(next_index)

    time.sleep(0.05)
    wayland_type(correct_string)
    print(f"Typed: {correct_string}")


def correct_selection():
    current_index = get_current_layout_index()
    current_layout = LAYOUTS[current_index]

    prev_index = (current_index - 1 + len(LAYOUTS)) % len(LAYOUTS)
    from_lang = LAYOUTS[prev_index]
    to_lang = current_layout

    print(f"Correcting selection: from {from_lang} to {to_lang}")

    from_reverse_map = REVERSE_LAYOUT_MAPS.get(from_lang)
    to_map = LAYOUT_MAPS.get(to_lang)

    if not from_reverse_map or not to_map:
        print(f"Error: Layout maps for '{from_lang}' or '{to_lang}' not found.")
        return

    try:
        selection_bytes = subprocess.run(['wl-paste'], capture_output=True, check=True).stdout
        selected_text = selection_bytes.decode('utf-8')
    except Exception as e:
        print(f"Could not get selection: {e}")
        return

    if not selected_text:
        print("No text selected.")
        return

    corrected_chars = []
    for char in selected_text:
        is_upper = char.isupper()
        char_lower = char.lower()
        code = from_reverse_map.get(char_lower)

        if code:
            corrected_char = to_map.get(code, char)
            corrected_chars.append(corrected_char.upper() if is_upper else corrected_char)
        else:
            corrected_chars.append(char)

    corrected_string = "".join(corrected_chars)

    if corrected_string != selected_text:
        print(f"Replacing '{selected_text}' with '{corrected_string}'")
        wayland_type(corrected_string)
    else:
        print("No correction needed or possible.")


def wait_for_key_release(dev, key_code):
    """Чекаємо на ВІДПУСКАННЯ клавіші, щоб уникнути 'залипання'."""
    print(f"Waiting for key release: {key_code}")
    try:
        for event in dev.read_loop():
            if event.type == ecodes.EV_KEY and \
                    event.code == key_code and \
                    event.value == 0:  # 0 = release
                print("Key released. Proceeding.")
                return True
    except (IOError, StopIteration, OSError) as e:
        # OSError може виникнути, якщо пристрій відключено
        print(f"Error in wait_for_key_release: {e}")
        return False


# ====== Основний цикл ======
def main():
    global last_shift_press, last_ctrl_press, cache

    check_dependencies()
    print(f"Starting switcher. Layouts: {LAYOUTS}")

    try:
        dev = InputDevice(DEVICE)
        print(f"Listening on {dev.path} ({dev.name})...")
    except PermissionError:
        print(f"Permission denied for {DEVICE}. Перевірте групу 'input'.", file=sys.stderr)
        return
    except Exception as e:
        print(f"Failed to open device: {e}", file=sys.stderr)
        return

    try:
        for event in dev.read_loop():
            if event.type != ecodes.EV_KEY:
                continue

            # --- Логіка для Правого Shift ---
            if event.code == RIGHT_SHIFT:
                if event.value == 1:  # Тільки натискання (press)
                    now = time.time()
                    if now - last_shift_press < DOUBLE_TAP_INTERVAL:
                        if wait_for_key_release(dev, RIGHT_SHIFT):
                            correct_last_typed()
                        last_shift_press = 0
                    else:
                        last_shift_press = now
                    last_ctrl_press = 0

            # --- Логіка для Правого Ctrl ---
            elif event.code == RIGHT_CTRL:
                if event.value == 1:  # Тільки натискання (press)
                    now = time.time()
                    if now - last_ctrl_press < DOUBLE_TAP_INTERVAL:
                        if wait_for_key_release(dev, RIGHT_CTRL):
                            correct_selection()
                        last_ctrl_press = 0
                    else:
                        last_ctrl_press = now
                    last_shift_press = 0

            # --- Логіка для інших клавіш (наповнення кешу) ---
            elif event.value == 1:  # Лише натискання
                last_shift_press = 0
                last_ctrl_press = 0

                if event.code == ecodes.KEY_BACKSPACE:
                    if cache: cache.pop()
                elif event.code in LAYOUT_MAPS['us']:
                    cache.append(event.code)
                elif event.code not in NON_CLEARING_KEYS:
                    cache.clear()

    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        print("Script stopped.")


if __name__ == "__main__":
    main()