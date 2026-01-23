#!/bin/bash
#
# Dictator Installation Script
# Installs the GNOME Shell extension and D-Bus service
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Installation paths
EXTENSION_DIR="$HOME/.local/share/gnome-shell/extensions/dictator@lebi"
DICTATOR_DIR="$HOME/.local/share/dictator"
SERVICE_DIR="$DICTATOR_DIR/service"
VENV_DIR="$DICTATOR_DIR/venv"
DBUS_SERVICE_DIR="$HOME/.local/share/dbus-1/services"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"

echo "=== Dictator Installation ==="
echo ""

# Check dependencies
echo "Checking dependencies..."

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is required but not installed."
    exit 1
fi

# Check PipeWire
if ! command -v pw-record &> /dev/null; then
    echo "WARNING: pw-record not found. Please install PipeWire:"
    echo "  sudo apt install pipewire pipewire-audio-client-libraries"
    echo ""
fi

# Check system dependencies for evdev
if ! pkg-config --exists libevdev; then
    echo "Note: You might need 'libevdev-dev' (Ubuntu) or 'libevdev-devel' (Fedora) for python-evdev."
fi

echo ""
echo "Installing components..."

# Create directories
mkdir -p "$EXTENSION_DIR"
mkdir -p "$EXTENSION_DIR/schemas"
mkdir -p "$SERVICE_DIR"
mkdir -p "$DBUS_SERVICE_DIR"
mkdir -p "$SYSTEMD_USER_DIR"

# Set up Python virtual environment
echo "Setting up Python virtual environment..."
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi

# Install Python dependencies in venv
echo "Installing Python dependencies..."
"$VENV_DIR/bin/pip" install --upgrade pip > /dev/null
"$VENV_DIR/bin/pip" install dbus-next evdev faster-whisper > /dev/null

# Check for NVIDIA GPU
if command -v nvidia-smi &> /dev/null; then
    echo "NVIDIA GPU detected. Installing CUDA libraries..."
    "$VENV_DIR/bin/pip" install nvidia-cublas-cu12 nvidia-cudnn-cu12 > /dev/null
else
    echo "No NVIDIA GPU detected. Using CPU mode."
fi

# Install extension
echo "Installing GNOME Shell extension..."
cp "$PROJECT_DIR/extension/extension.js" "$EXTENSION_DIR/"
cp "$PROJECT_DIR/extension/metadata.json" "$EXTENSION_DIR/"
cp "$PROJECT_DIR/extension/stylesheet.css" "$EXTENSION_DIR/"
cp "$PROJECT_DIR/extension/schemas/"*.xml "$EXTENSION_DIR/schemas/"

# Compile schemas
echo "Compiling GSettings schemas..."
glib-compile-schemas "$EXTENSION_DIR/schemas/"

# Install service
echo "Installing D-Bus service..."
cp "$PROJECT_DIR/service/dictator_service.py" "$SERVICE_DIR/"
cp "$PROJECT_DIR/service/recorder.py" "$SERVICE_DIR/"
cp "$PROJECT_DIR/service/transcriber.py" "$SERVICE_DIR/"
cp "$PROJECT_DIR/service/typer.py" "$SERVICE_DIR/"
cp "$PROJECT_DIR/service/__init__.py" "$SERVICE_DIR/"

# Make service executable
chmod +x "$SERVICE_DIR/dictator_service.py"

# Install D-Bus service file (with correct path)
sed "s|%h|$HOME|g" "$PROJECT_DIR/service/org.lebi.Dictator.service" > "$DBUS_SERVICE_DIR/org.lebi.Dictator.service"

# Install systemd user service
sed "s|%h|$HOME|g" "$PROJECT_DIR/systemd/dictator.service" > "$SYSTEMD_USER_DIR/dictator.service"

# Reload systemd
echo "Reloading systemd user daemon..."
systemctl --user daemon-reload

echo ""
echo "=== Installation Complete ==="
echo ""
echo "IMPORTANT STEPS REQUIRED:"
echo ""
echo "1. Set up uinput permissions (requires sudo):"
echo "   sudo $SCRIPT_DIR/setup_uinput.sh"
echo "   (Then log out and log back in for group changes to take effect)"
echo ""
echo "2. Enable the extension:"
echo "   gnome-extensions enable dictator@lebi"
echo ""
echo "3. Restart GNOME Shell:"
echo "   - On X11: Press Alt+F2, type 'r', press Enter"
echo "   - On Wayland: Log out and log back in"
echo ""
echo "4. Usage:"
echo "   - Press Super+H to start recording"
echo "   - Speak"
echo "   - Press Super+H again to stop. The text will be typed automatically."
echo ""
