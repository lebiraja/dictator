#!/bin/bash
#
# Dictator - One-Click Installation Script
#
# This script installs everything needed for Dictator voice dictation.
# Run with: ./install.sh
#
# Usage:
#   ./install.sh          # Interactive installation
#   ./install.sh --full   # Non-interactive, installs everything
#   ./install.sh --remove # Uninstall Dictator
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"

# Installation paths
EXTENSION_DIR="$HOME/.local/share/gnome-shell/extensions/dictator@lebi"
DICTATOR_DIR="$HOME/.local/share/dictator"
SERVICE_DIR="$DICTATOR_DIR/service"
VENV_DIR="$DICTATOR_DIR/venv"
DBUS_SERVICE_DIR="$HOME/.local/share/dbus-1/services"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"

# Flags
AUTO_YES=false
UNINSTALL=false

# Parse arguments
for arg in "$@"; do
    case $arg in
        --full|-y|--yes)
            AUTO_YES=true
            ;;
        --remove|--uninstall)
            UNINSTALL=true
            ;;
        --help|-h)
            echo ""
            echo -e "${BOLD}Dictator - Voice Dictation for GNOME${NC}"
            echo ""
            echo "Usage: ./install.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --full, -y    Non-interactive installation (answer yes to all)"
            echo "  --remove      Uninstall Dictator completely"
            echo "  -h, --help    Show this help message"
            echo ""
            echo "Examples:"
            echo "  ./install.sh          # Interactive installation"
            echo "  ./install.sh --full   # Automatic full installation"
            echo "  ./install.sh --remove # Uninstall"
            echo ""
            exit 0
            ;;
    esac
done

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

print_banner() {
    echo ""
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}  ${BOLD}🎤 Dictator - Voice Dictation for GNOME${NC}                     ${BLUE}║${NC}"
    echo -e "${BLUE}║${NC}     Local AI-powered speech to text                          ${BLUE}║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_header() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

print_step() {
    echo -e "${GREEN}▶${NC} $1"
}

print_substep() {
    echo -e "  ${BLUE}→${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

confirm() {
    if [ "$AUTO_YES" = true ]; then
        return 0
    fi
    read -p "$1 [Y/n] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        return 1
    fi
    return 0
}

check_command() {
    command -v "$1" &> /dev/null
}

# ============================================================================
# UNINSTALL
# ============================================================================

if [ "$UNINSTALL" = true ]; then
    print_banner
    print_header "Uninstalling Dictator"

    echo "This will remove:"
    echo "  • GNOME Shell extension"
    echo "  • Python service and virtual environment"
    echo "  • D-Bus and systemd service files"
    echo ""

    if ! confirm "Continue with uninstallation?"; then
        echo "Cancelled."
        exit 0
    fi

    # Stop service
    print_step "Stopping service..."
    systemctl --user stop dictator 2>/dev/null || true
    pkill -f dictator_service.py 2>/dev/null || true

    # Disable extension
    print_step "Disabling extension..."
    gnome-extensions disable dictator@lebi 2>/dev/null || true

    # Remove files
    print_step "Removing files..."
    rm -rf "$EXTENSION_DIR"
    rm -rf "$DICTATOR_DIR"
    rm -f "$DBUS_SERVICE_DIR/org.lebi.Dictator.service"
    rm -f "$SYSTEMD_USER_DIR/dictator.service"

    # Reload systemd
    systemctl --user daemon-reload 2>/dev/null || true

    print_success "Dictator has been uninstalled!"
    echo ""
    echo "Note: The Whisper model cache (~/.cache/huggingface) was preserved."
    echo "Note: uinput permissions were preserved (other apps may use them)."
    echo ""
    exit 0
fi

# ============================================================================
# INSTALLATION
# ============================================================================

print_banner

echo "This script will install:"
echo "  • GNOME Shell extension (panel icon, keyboard shortcut)"
echo "  • Python backend service (audio recording, AI transcription)"
echo "  • System permissions for keyboard simulation"
echo ""
echo -e "After installation, press ${BOLD}Ctrl+Shift+Space${NC} to dictate!"
echo ""

if ! confirm "Start installation?"; then
    echo "Installation cancelled."
    exit 0
fi

# ============================================================================
# PRE-FLIGHT CHECKS
# ============================================================================

print_header "Checking System Requirements"

ERRORS=0

# Check not root
if [ "$EUID" -eq 0 ]; then
    print_error "Don't run as root! Run as your normal user."
    exit 1
fi

# Check GNOME Shell
if check_command gnome-shell; then
    GNOME_VERSION=$(gnome-shell --version 2>/dev/null | grep -oP '\d+' | head -1 || echo "unknown")
    if [ "$GNOME_VERSION" != "unknown" ] && [ "$GNOME_VERSION" -ge 45 ] 2>/dev/null; then
        print_success "GNOME Shell $GNOME_VERSION"
    else
        print_warning "GNOME Shell $GNOME_VERSION (tested on 45+, may still work)"
    fi
else
    print_error "GNOME Shell not found"
    ERRORS=$((ERRORS + 1))
fi

# Check Python - need 3.10-3.13 for faster-whisper/onnxruntime compatibility
PYTHON_CMD=""
for v in python3.13 python3.12 python3.11 python3.10; do
    if command -v "$v" &>/dev/null; then
        PYTHON_CMD="$v"
        break
    fi
done

# Fall back to python3 if it's in the compatible range
if [ -z "$PYTHON_CMD" ] && check_command python3; then
    PY_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)' 2>/dev/null || echo "99")
    if [ "$PY_MINOR" -ge 10 ] && [ "$PY_MINOR" -le 13 ] 2>/dev/null; then
        PYTHON_CMD="python3"
    fi
fi

if [ -n "$PYTHON_CMD" ]; then
    PYTHON_VERSION=$($PYTHON_CMD --version 2>/dev/null | grep -oP '\d+\.\d+' || echo "unknown")
    print_success "Python $PYTHON_VERSION ($PYTHON_CMD)"
else
    SYSTEM_PY=$(python3 --version 2>/dev/null | grep -oP '\d+\.\d+' || echo "unknown")
    print_error "Python 3.10-3.13 required (found $SYSTEM_PY)"
    echo ""
    echo -e "  ${YELLOW}Python $SYSTEM_PY is too new for faster-whisper dependencies.${NC}"
    echo -e "  ${YELLOW}Install a compatible version:${NC}"
    if check_command dnf; then
        echo -e "    ${CYAN}sudo dnf install python3.13${NC}"
    elif check_command apt; then
        echo -e "    ${CYAN}sudo apt install python3.12${NC}"
    elif check_command pacman; then
        echo -e "    ${CYAN}sudo pacman -S python${NC}"
    fi
    echo ""
    ERRORS=$((ERRORS + 1))
fi

# Check python3-venv (only if we found a compatible Python)
if [ -n "$PYTHON_CMD" ]; then
    if "$PYTHON_CMD" -m venv --help &>/dev/null; then
        print_success "python3-venv"
    else
        print_error "python3-venv not found for $PYTHON_CMD"
        ERRORS=$((ERRORS + 1))
    fi
fi

# Check PipeWire
if check_command pw-record; then
    print_success "PipeWire"
else
    print_error "PipeWire (pw-record) not found"
    ERRORS=$((ERRORS + 1))
fi

# Check glib-compile-schemas
if check_command glib-compile-schemas; then
    print_success "glib-compile-schemas"
else
    print_error "glib-compile-schemas not found"
    ERRORS=$((ERRORS + 1))
fi

# Show install commands if missing deps
if [ $ERRORS -gt 0 ]; then
    echo ""
    print_error "Missing $ERRORS required dependencies!"
    echo ""
    echo "Install them with:"
    echo ""
    if check_command apt; then
        echo -e "  ${YELLOW}sudo apt install python3 python3-venv python3-pip pipewire libglib2.0-dev-bin libevdev-dev${NC}"
    elif check_command dnf; then
        echo -e "  ${YELLOW}sudo dnf install python3 python3-pip pipewire glib2-devel libevdev-devel${NC}"
    elif check_command pacman; then
        echo -e "  ${YELLOW}sudo pacman -S python python-pip pipewire glib2 libevdev${NC}"
    else
        echo "  Install: python3, python3-venv, pipewire, glib2 development tools"
    fi
    echo ""
    if ! confirm "Try to continue anyway?"; then
        exit 1
    fi
fi

# ============================================================================
# UINPUT PERMISSIONS
# ============================================================================

print_header "Setting Up Keyboard Permissions"

echo "Dictator needs access to /dev/uinput to type text."
echo "This requires adding your user to the 'uinput' group."
echo ""

NEED_RELOGIN=false
UINPUT_SETUP_NEEDED=false

# Check if already set up
if groups | grep -q uinput 2>/dev/null; then
    if [ -e /dev/uinput ] && [ -r /dev/uinput ] && [ -w /dev/uinput ]; then
        print_success "uinput permissions already configured"
    else
        UINPUT_SETUP_NEEDED=true
    fi
else
    UINPUT_SETUP_NEEDED=true
fi

if [ "$UINPUT_SETUP_NEEDED" = true ]; then
    echo "This step requires sudo privileges."
    echo ""

    if confirm "Set up uinput permissions now?"; then
        # Create uinput group if needed
        if ! getent group uinput > /dev/null 2>&1; then
            print_substep "Creating uinput group..."
            sudo groupadd uinput
        fi

        # Add user to group
        if ! groups | grep -q uinput; then
            print_substep "Adding $USER to uinput group..."
            sudo usermod -aG uinput "$USER"
            NEED_RELOGIN=true
        fi

        # Create udev rule
        UDEV_RULE="/etc/udev/rules.d/99-dictator-uinput.rules"
        if [ ! -f "$UDEV_RULE" ]; then
            print_substep "Creating udev rule..."
            echo 'KERNEL=="uinput", GROUP="uinput", MODE="0660", OPTIONS+="static_node=uinput"' | sudo tee "$UDEV_RULE" > /dev/null
        fi

        # Reload udev
        print_substep "Reloading udev rules..."
        sudo udevadm control --reload-rules
        sudo udevadm trigger

        # Load module
        if ! lsmod | grep -q uinput; then
            print_substep "Loading uinput module..."
            sudo modprobe uinput
        fi

        # Auto-load on boot
        if [ ! -f /etc/modules-load.d/uinput.conf ]; then
            echo "uinput" | sudo tee /etc/modules-load.d/uinput.conf > /dev/null
        fi

        print_success "uinput permissions configured"
    else
        print_warning "Skipped. You'll need to run this later:"
        echo "  sudo $PROJECT_DIR/scripts/setup_uinput.sh"
        NEED_RELOGIN=true
    fi
fi

# ============================================================================
# CREATE DIRECTORIES
# ============================================================================

print_header "Installing Dictator"

print_step "Creating directories..."
mkdir -p "$EXTENSION_DIR/schemas"
mkdir -p "$SERVICE_DIR"
mkdir -p "$DBUS_SERVICE_DIR"
mkdir -p "$SYSTEMD_USER_DIR"

# ============================================================================
# PYTHON ENVIRONMENT
# ============================================================================

print_step "Setting up Python environment..."

if [ ! -d "$VENV_DIR" ]; then
    print_substep "Creating virtual environment..."
    "$PYTHON_CMD" -m venv "$VENV_DIR"
fi

print_substep "Installing Python packages..."
"$VENV_DIR/bin/pip" install --upgrade pip --quiet 2>/dev/null

if ! "$VENV_DIR/bin/pip" install dbus-next evdev faster-whisper --quiet 2>&1; then
    echo ""
    print_error "Failed to install Python packages!"
    echo ""
    echo -e "  ${YELLOW}This may be due to missing build dependencies.${NC}"
    echo -e "  ${YELLOW}Install them and retry:${NC}"
    if check_command dnf; then
        echo -e "    ${CYAN}sudo dnf install python${PYTHON_VERSION}-devel libevdev-devel${NC}"
    elif check_command apt; then
        echo -e "    ${CYAN}sudo apt install python${PYTHON_VERSION}-dev libevdev-dev${NC}"
    elif check_command pacman; then
        echo -e "    ${CYAN}sudo pacman -S python libevdev${NC}"
    fi
    echo ""
    exit 1
fi

# Check for NVIDIA GPU
if check_command nvidia-smi; then
    print_substep "NVIDIA GPU detected, installing CUDA support..."
    "$VENV_DIR/bin/pip" install nvidia-cublas-cu12 nvidia-cudnn-cu12 --quiet 2>/dev/null || {
        print_warning "CUDA libraries failed to install. Will use CPU mode."
    }
else
    print_substep "No NVIDIA GPU detected, will use CPU mode"
fi

print_success "Python environment ready"

# ============================================================================
# INSTALL EXTENSION
# ============================================================================

print_step "Installing GNOME Shell extension..."

cp "$PROJECT_DIR/extension/extension.js" "$EXTENSION_DIR/"
cp "$PROJECT_DIR/extension/metadata.json" "$EXTENSION_DIR/"
cp "$PROJECT_DIR/extension/stylesheet.css" "$EXTENSION_DIR/"
cp "$PROJECT_DIR/extension/schemas/"*.xml "$EXTENSION_DIR/schemas/"

print_substep "Compiling GSettings schemas..."
glib-compile-schemas "$EXTENSION_DIR/schemas/"

print_success "Extension installed"

# ============================================================================
# INSTALL SERVICE
# ============================================================================

print_step "Installing backend service..."

cp "$PROJECT_DIR/service/dictator_service.py" "$SERVICE_DIR/"
cp "$PROJECT_DIR/service/recorder.py" "$SERVICE_DIR/"
cp "$PROJECT_DIR/service/transcriber.py" "$SERVICE_DIR/"
cp "$PROJECT_DIR/service/typer.py" "$SERVICE_DIR/"
touch "$SERVICE_DIR/__init__.py"

chmod +x "$SERVICE_DIR/dictator_service.py"

# D-Bus service file
print_substep "Installing D-Bus service..."
sed "s|%h|$HOME|g" "$PROJECT_DIR/service/org.lebi.Dictator.service" > "$DBUS_SERVICE_DIR/org.lebi.Dictator.service"

# Systemd service file
print_substep "Installing systemd service..."
sed "s|%h|$HOME|g" "$PROJECT_DIR/systemd/dictator.service" > "$SYSTEMD_USER_DIR/dictator.service"

# Reload systemd
systemctl --user daemon-reload

print_success "Backend service installed"

# ============================================================================
# ENABLE EXTENSION
# ============================================================================

print_step "Enabling extension..."

# Kill any existing service
pkill -f dictator_service.py 2>/dev/null || true

# Enable extension
gnome-extensions enable dictator@lebi 2>/dev/null || {
    print_warning "Could not auto-enable. Will need manual enable after login."
}

# ============================================================================
# COMPLETION
# ============================================================================

print_header "Installation Complete! 🎉"

echo -e "${GREEN}${BOLD}Dictator has been installed successfully!${NC}"
echo ""

# Check if relogin needed
if [ "$NEED_RELOGIN" = true ] || [ "$XDG_SESSION_TYPE" = "wayland" ]; then
    echo -e "${YELLOW}${BOLD}⚠ ACTION REQUIRED:${NC}"
    echo ""
    echo -e "  You must ${BOLD}log out and log back in${NC} for changes to take effect."
    echo ""
    if [ "$NEED_RELOGIN" = true ]; then
        echo "  This is needed for:"
        echo "  • uinput group membership (keyboard simulation)"
    fi
    if [ "$XDG_SESSION_TYPE" = "wayland" ]; then
        echo "  • Wayland requires re-login to load new extensions"
    fi
    echo ""
fi

echo -e "${BOLD}How to use:${NC}"
echo ""
echo -e "  1. Press ${CYAN}Ctrl+Shift+Space${NC} to start recording"
echo "  2. Speak your text"
echo -e "  3. Press ${CYAN}Ctrl+Shift+Space${NC} again to stop"
echo "  4. Text will be typed into the focused application"
echo ""
echo -e "${BOLD}First run:${NC}"
echo ""
echo "  The AI model (~140MB) will download automatically on first use."
echo ""
echo -e "${BOLD}Troubleshooting:${NC}"
echo ""
echo "  • Check logs: journalctl --user | grep -i dictator"
echo "  • Reload extension: gnome-extensions disable dictator@lebi && gnome-extensions enable dictator@lebi"
echo "  • More help: https://github.com/lebiraja/dictator"
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
