#!/bin/bash
set -e

# Setup uinput permissions for Dictator app
# This script must be run with sudo

if [ "$EUID" -ne 0 ]; then
  echo "Please run as root"
  exit 1
fi

echo "Setting up uinput permissions..."

# Create uinput group if it doesn't exist
if ! getent group uinput >/dev/null; then
    groupadd uinput
    echo "Created 'uinput' group"
fi

# Add current user to uinput group
# Note: $SUDO_USER holds the username of the user who invoked sudo
if [ -n "$SUDO_USER" ]; then
    usermod -aG uinput "$SUDO_USER"
    echo "Added user '$SUDO_USER' to 'uinput' group"
else
    echo "Warning: Could not determine original user. Please add your user to 'uinput' group manually."
fi

# Create udev rule
cat > /etc/udev/rules.d/99-dictator-uinput.rules <<EOF
KERNEL=="uinput", GROUP="uinput", MODE="0660"
EOF

echo "Created /etc/udev/rules.d/99-dictator-uinput.rules"

# Reload udev rules
udevadm control --reload-rules
udevadm trigger

# Load uinput module
modprobe uinput
echo "uinput" > /etc/modules-load.d/uinput.conf

echo "Done! You may need to log out and back in for group changes to take effect."
