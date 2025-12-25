#!/usr/bin/env python3
import evdev
import subprocess
import time

# --- Налаштування ---
DEVICE_PATH = '/dev/input/by-id/usb-SIGMACHIP_USB_Keyboard-event-kbd'
KEY = evdev.ecodes.KEY_RIGHTSHIFT
DOUBLE_PRESS_DELAY = 0.4

LAYOUTS = ['us', 'ua']
current_layout_index = 0

# Транслітерація
en_to_ua = str.maketrans(
    "qwertyuiop[]asdfghjkl;'zxcvbnm,.",
    "йцукенгшщзхїфівапролджєячсмитьбю"
)
ua_to_en = {v: k for k, v in en_to_ua.items()}
ua_to_en_map = str.maketrans(ua_to_en)

# --- Лог ---
def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

# --- Перемикання розкладки ---
def switch_layout():
    global current_layout_index
    current_layout_index = (current_layout_index + 1) % len(LAYOUTS)
    layout = LAYOUTS[current_layout_index]
    log(f"Switched layout → {layout}")
    return layout

# --- Транслітерація ---
def correct_text(text, layout):
    if layout == 'us':
        return text.translate(en_to_ua)
    else:
        return text.translate(ua_to_en_map)

# --- Отримати виділений текст або останнє слово ---
def get_text_under_cursor():
    # Спробуємо виділений текст
    selected = subprocess.run(['wl-paste'], capture_output=True, text=True).stdout.strip()
    if selected:
        log(f"Selected text detected: '{selected}'")
        return selected
    # Якщо немає виділення, беремо останнє слово
    subprocess.run(['ydotool', 'key', 'CTRL+SHIFT+LEFT'])
    subprocess.run(['ydotool', 'key', 'CTRL+c'])
    time.sleep(0.05)
    last_word = subprocess.run(['wl-paste'], capture_output=True, text=True).stdout.strip()
    log(f"No selection, last word captured: '{last_word}'")
    return last_word

# --- Копіюємо у буфер ---
def copy_to_clipboard(text):
    if text:
        subprocess.run(['wl-copy'], input=text.encode())
        log(f"Copied corrected text to clipboard: '{text}'")
    else:
        log("No text to copy")

# --- Обробка тексту ---
def handle_text(layout):
    text = get_text_under_cursor()
    if text:
        corrected = correct_text(text, layout)
        copy_to_clipboard(corrected)

# --- Основний цикл ---
def main():
    log(f"Listening for Right Shift double press on {DEVICE_PATH}")
    dev = evdev.InputDevice(DEVICE_PATH)
    last_press = 0

    for event in dev.read_loop():
        if event.type == evdev.ecodes.EV_KEY and event.code == KEY and event.value == 1:
            now = time.time()
            if now - last_press < DOUBLE_PRESS_DELAY:
                log("Double Right Shift detected")
                layout = switch_layout()
                handle_text(layout)
            last_press = now

if __name__ == "__main__":
    main()
