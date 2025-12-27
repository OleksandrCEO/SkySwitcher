#!/bin/bash
# SkySwitcher installer for standard Linux distros (Ubuntu/Fedora/Arch)
# This script installs SkySwitcher to /usr/local/bin and configures permissions

set -e

INSTALL_DIR="/usr/local/bin"
RULE_FILE="/etc/udev/rules.d/99-skyswitcher.rules"
SCRIPT_NAME="skyswitcher"

echo "=== SkySwitcher Installer ==="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Error: This script must be run as root (use sudo)"
    exit 1
fi

# Get the real user who ran sudo
REAL_USER="${SUDO_USER:-$USER}"

# Detect package manager and install python3-evdev
echo "[1/5] Installing python3-evdev dependency..."
if command -v apt &> /dev/null; then
    apt update
    apt install -y python3-evdev
    echo "✓ Installed via apt"
elif command -v dnf &> /dev/null; then
    dnf install -y python3-evdev
    echo "✓ Installed via dnf"
elif command -v pacman &> /dev/null; then
    pacman -S --noconfirm python-evdev
    echo "✓ Installed via pacman"
else
    echo "Warning: Unknown package manager. Please install python3-evdev manually."
fi

# Copy main.py to /usr/local/bin/skyswitcher
echo ""
echo "[2/5] Installing SkySwitcher to $INSTALL_DIR/$SCRIPT_NAME..."
cp main.py "$INSTALL_DIR/$SCRIPT_NAME"
chmod +x "$INSTALL_DIR/$SCRIPT_NAME"
echo "✓ Installed"

# Create uinput group if it doesn't exist
echo ""
echo "[3/5] Creating uinput group..."
if ! getent group uinput > /dev/null 2>&1; then
    groupadd uinput
    echo "✓ Created uinput group"
else
    echo "✓ uinput group already exists"
fi

# Add user to input and uinput groups
echo ""
echo "[4/5] Adding user '$REAL_USER' to input and uinput groups..."
usermod -aG input "$REAL_USER"
usermod -aG uinput "$REAL_USER"
echo "✓ User added to groups"

# Create udev rules for uinput group permissions
echo ""
echo "[5/5] Installing udev rules to $RULE_FILE..."
cat > "$RULE_FILE" <<EOF
# SkySwitcher udev rules - Grant access to uinput device for uinput group
KERNEL=="uinput", SUBSYSTEM=="misc", GROUP="uinput", MODE="0660"
EOF
echo "✓ Created udev rules"

# Reload udev
udevadm control --reload-rules
udevadm trigger

echo ""
echo "=== Installation Complete! ==="
echo ""
echo "IMPORTANT: You MUST log out and log back in for group permissions to take effect!"
echo ""
echo "After logging back in, you can run:"
echo "  skyswitcher              # Start the program"
echo "  skyswitcher --list       # List available keyboards"
echo "  skyswitcher --verbose    # Run with detailed logging"
echo ""
echo "To autostart on login, add 'skyswitcher' to your desktop environment's autostart."
echo ""