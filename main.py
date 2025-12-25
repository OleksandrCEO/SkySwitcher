#!/usr/bin/env python3
import evdev
from evdev import UInput, ecodes as e
import subprocess
import time
import sys

# --- КОНФІГУРАЦІЯ ---
# Встав сюди свій шлях, який ми знайшли раніше (SIGMACHIP USB Keyboard)
KEYBOARD_DEVICE = '/dev/input/event2'

# Клавіша-тригер (наприклад, KEY_LEFTSHIFT або KEY_RIGHTSHIFT)
TRIGGER_KEY = e.KEY_RIGHTSHIFT
DOUBLE_PRESS_DELAY = 0.5  # Секунди

# Розкладки
EN_LAYOUT = "`qwertyuiop[]asdfghjkl;'zxcvbnm,./~@#$^&QWERTYUIOP{}ASDFGHJKL:\"ZXCVBNM<>?"
UA_LAYOUT = "'йцукенгшщзхїфівапролджєячсмитьбю.₴\"№;%:?ЙЦУКЕНГШЩЗХЇФІВАПРОЛДЖЄЯЧСМИТЬБЮ,"

# Мапа перекладу (в обидві сторони)
TRANS_MAP = str.maketrans(EN_LAYOUT + UA_LAYOUT, UA_LAYOUT + EN_LAYOUT)

class LayoutSwitcher:
    def __init__(self, device_path):
        try:
            self.dev = evdev.InputDevice(device_path)
            print(f"✅ Слухаю пристрій: {self.dev.name}")
        except FileNotFoundError:
            print(f"❌ Пристрій {device_path} не знайдено! Перевір шлях.")
            sys.exit(1)

        # Створення віртуальної клавіатури для відправки команд
        # Ми оголошуємо, які кнопки плануємо натискати
        cap = {
            e.EV_KEY: [e.KEY_LEFTCTRL, e.KEY_LEFTSHIFT, e.KEY_C, e.KEY_V,
                       e.KEY_HOME, e.KEY_BACKSPACE, e.KEY_INSERT]
        }
        try:
            self.ui = UInput(cap, name="My-AI-Switcher-Virtual-Kbd")
        except evdev.uinput.UInputError:
            print("❌ Помилка доступу до uinput. Перевір 'hardware.uinput.enable = true' та групи користувача.")
            sys.exit(1)

        self.last_press_time = 0

    def convert_text(self, text):
        return text.translate(TRANS_MAP)

    def clipboard_read(self):
        try:
            # -n щоб не було зайвих newlines
            res = subprocess.run(['wl-paste', '-n'], capture_output=True, text=True)
            return res.stdout
        except Exception as err:
            print(f"Clipboard error: {err}")
            return ""

    def clipboard_write(self, text):
        try:
            # -n щоб не додавати новий рядок
            p = subprocess.Popen(['wl-copy', '-n'], stdin=subprocess.PIPE, text=True)
            p.communicate(input=text)
        except Exception as err:
            print(f"Clipboard write error: {err}")

    def send_combo(self, *keys):
        """Натискає комбінацію клавіш"""
        # Затискаємо всі
        for k in keys:
            self.ui.write(e.EV_KEY, k, 1)
        self.ui.syn()
        time.sleep(0.05) # Трошки чекаємо
        # Відпускаємо у зворотному порядку
        for k in reversed(keys):
            self.ui.write(e.EV_KEY, k, 0)
        self.ui.syn()
        time.sleep(0.05)

    def process_switch(self):
        print("⚡ Double Shift Detected! Processing...")

        # 1. Виділяємо рядок (Shift + Home)
        # Важливо: спочатку переконаємось, що фізичний Shift відпущено,
        # інакше він може сплутати карти. Але ми і так це робимо після key_up події?
        # Для надійності просто емулюємо:

        self.send_combo(e.KEY_LEFTSHIFT, e.KEY_HOME)

        # 2. Копіюємо (Ctrl + C)
        self.send_combo(e.KEY_LEFTCTRL, e.KEY_C)

        # Даємо системі час подумати (Wayland clipboard is async)
        time.sleep(0.1)

        # 3. Обробка тексту
        original = self.clipboard_read()
        if not original:
            print("Clipboard empty or read failed.")
            return

        converted = self.convert_text(original)
        if original == converted:
            print("No changes needed.")
            return

        print(f"Converting: '{original}' -> '{converted}'")
        self.clipboard_write(converted)
        time.sleep(0.1)

        # 4. Видаляємо старе (Backspace) і вставляємо нове (Ctrl + V)
        self.send_combo(e.KEY_BACKSPACE)
        self.send_combo(e.KEY_LEFTCTRL, e.KEY_V)

    def run(self):
        print("Очікую подвійний Shift...")
        # read_loop читає події блокуючи
        for event in self.dev.read_loop():
            if event.type == e.EV_KEY and event.code == TRIGGER_KEY:
                # 1 = Key Down, 0 = Key Up.
                # Реагуємо на натискання (1)
                if event.value == 1:
                    now = time.time()
                    diff = now - self.last_press_time

                    if diff < DOUBLE_PRESS_DELAY:
                        self.process_switch()
                        # Скидаємо таймер, щоб не спрацювало третій раз підряд
                        self.last_press_time = 0
                    else:
                        self.last_press_time = now

if __name__ == "__main__":
    app = LayoutSwitcher(KEYBOARD_DEVICE)
    try:
        app.run()
    except KeyboardInterrupt:
        print("\nBye!")
