#!/bin/bash
#
# Dictator Uninstallation Script
# Removes the GNOME Shell extension and D-Bus service
#

set -e

# Installation paths
EXTENSION_DIR="$HOME/.local/share/gnome-shell/extensions/dictator@lebi"
SERVICE_DIR="$HOME/.local/share/dictator"
DBUS_SERVICE_FILE="$HOME/.local/share/dbus-1/services/org.lebi.Dictator.service"
SYSTEMD_SERVICE_FILE="$HOME/.config/systemd/user/dictator.service"

echo "=== Dictator Uninstallation ==="
echo ""

# Stop service if running
echo "Stopping Dictator service..."
systemctl --user stop dictator.service 2>/dev/null || true
systemctl --user disable dictator.service 2>/dev/null || true

# Disable extension
echo "Disabling GNOME extension..."
gnome-extensions disable dictator@lebi 2>/dev/null || true

# Remove extension
if [ -d "$EXTENSION_DIR" ]; then
    echo "Removing extension..."
    rm -rf "$EXTENSION_DIR"
fi

# Remove D-Bus service file
if [ -f "$DBUS_SERVICE_FILE" ]; then
    echo "Removing D-Bus service file..."
    rm -f "$DBUS_SERVICE_FILE"
fi

# Remove CLI
rm -f "$HOME/.local/bin/dictator"

# Remove systemd service
if [ -f "$SYSTEMD_SERVICE_FILE" ]; then
    echo "Removing systemd service..."
    rm -f "$SYSTEMD_SERVICE_FILE"
    systemctl --user daemon-reload
fi

# Ask about data removal
echo ""
read -p "Remove service files and models? (y/N): " remove_data
if [ "$remove_data" = "y" ] || [ "$remove_data" = "Y" ]; then
    if [ -d "$SERVICE_DIR" ]; then
        echo "Removing service directory and models..."
        rm -rf "$SERVICE_DIR"
    fi
else
    echo "Keeping service files and models at: $SERVICE_DIR"
fi

echo ""
echo "=== Uninstallation Complete ==="
echo ""
echo "Restart GNOME Shell to complete removal:"
echo "  - On X11: Press Alt+F2, type 'r', press Enter"
echo "  - On Wayland: Log out and log back in"
echo ""
