#!/usr/bin/env python3

# Do not forget makle it executable! 
# chmod +x ~/Dev/system/Switcher/run.py


import subprocess
import sys

# Define layout mappings
en_layout = "`qwertyuiop[]asdfghjkl;'zxcvbnm,./~@#$^&QWERTYUIOP{}ASDFGHJKL:\"ZXCVBNM<>?"
ua_layout = "'йцукенгшщзхїфівапролджєячсмитьбю.₴\"№;%:?ЙЦУКЕНГШЩЗХЇФІВАПРОЛДЖЄЯЧСМИТЬБЮ,"

# Create translation tables for both directions
# We merge them into one map: EN->UA and UA->EN
layout_map = str.maketrans(
    en_layout + ua_layout,
    ua_layout + en_layout
)

def convert_layout(text: str) -> str:
    # Translate the text using the combined map
    return text.translate(layout_map)

def main():
    try:
        # 1. Get current clipboard content (using wl-paste)
        result = subprocess.run(
            ['wl-paste'], 
            capture_output=True, 
            text=True, 
            check=True, 
            encoding='utf-8'
        )
        original_text = result.stdout
        
        if not original_text.strip():
            # Clipboard is empty, nothing to do
            return

        # 2. Get the very last non-empty line
        last_line = original_text.rstrip().split('\n')[-1]
        
        if not last_line:
            # Last line is empty, nothing to do
            return
            
        # 3. Convert only the last line
        converted_line = convert_layout(last_line)

        # 4. Put the converted line back onto the clipboard (using wl-copy)
        subprocess.run(
            ['wl-copy'], 
            input=converted_line, 
            text=True, 
            check=True, 
            encoding='utf-8'
        )

    except FileNotFoundError:
        # This happens if wl-paste/wl-copy are not installed
        # (but they are in your config)
        print("Error: 'wl-paste' or 'wl-copy' not found.", file=sys.stderr)
    except subprocess.CalledProcessError as e:
        # Handle errors from the clipboard tools
        print(f"Clipboard tool error: {e}", file=sys.stderr)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
