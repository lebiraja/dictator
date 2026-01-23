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
MODELS_DIR="$DICTATOR_DIR/models"

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

# Check whisper.cpp (including ~/.local/bin)
WHISPER_BIN=""
for bin in whisper-cli whisper-cpp whisper main; do
    if command -v "$bin" &> /dev/null; then
        WHISPER_BIN="$bin"
        break
    fi
done

# Also check ~/.local/bin explicitly
if [ -z "$WHISPER_BIN" ] && [ -x "$HOME/.local/bin/whisper-cli" ]; then
    WHISPER_BIN="$HOME/.local/bin/whisper-cli"
fi

if [ -z "$WHISPER_BIN" ]; then
    echo "WARNING: whisper.cpp not found in PATH."
    echo "Please install whisper.cpp:"
    echo ""
    echo "  # Build from source:"
    echo "  git clone https://github.com/ggerganov/whisper.cpp"
    echo "  cd whisper.cpp && cmake -B build && cmake --build build -j\$(nproc)"
    echo "  cp build/bin/whisper-cli ~/.local/bin/"
    echo ""
else
    echo "Found whisper.cpp: $WHISPER_BIN"
fi

echo ""
echo "Installing components..."

# Create directories
mkdir -p "$EXTENSION_DIR"
mkdir -p "$EXTENSION_DIR/schemas"
mkdir -p "$SERVICE_DIR"
mkdir -p "$DBUS_SERVICE_DIR"
mkdir -p "$SYSTEMD_USER_DIR"
mkdir -p "$MODELS_DIR"

# Set up Python virtual environment
echo "Setting up Python virtual environment..."
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi

# Install Python dependencies in venv
echo "Installing Python dependencies..."
"$VENV_DIR/bin/pip" install --upgrade pip > /dev/null
"$VENV_DIR/bin/pip" install dbus-next > /dev/null

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
cp "$PROJECT_DIR/service/model_manager.py" "$SERVICE_DIR/"
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
echo "Next steps:"
echo ""
echo "1. Restart GNOME Shell:"
echo "   - On X11: Press Alt+F2, type 'r', press Enter"
echo "   - On Wayland: Log out and log back in"
echo ""
echo "2. Enable the extension:"
echo "   gnome-extensions enable dictator@lebi"
echo ""
echo "3. Test dictation:"
echo "   - Press Super+H to start recording"
echo "   - Speak"
echo "   - Press Super+H again to stop and transcribe"
echo "   - Paste with Ctrl+V"
echo ""
if [ -z "$WHISPER_BIN" ]; then
    echo "IMPORTANT: Install whisper.cpp before using!"
    echo ""
fi
echo "The Whisper model will be downloaded automatically on first use."
echo ""
