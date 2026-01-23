#!/bin/bash
#
# Dictator - Complete Installation Script
#
# This script installs everything needed for the Dictator voice dictation app.
# Run with: ./install.sh
#
# For a full installation including uinput permissions (recommended):
#   ./install.sh --full
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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
FULL_INSTALL=false
SKIP_DEPS=false

# Parse arguments
for arg in "$@"; do
    case $arg in
        --full)
            FULL_INSTALL=true
            shift
            ;;
        --skip-deps)
            SKIP_DEPS=true
            shift
            ;;
        --help|-h)
            echo "Dictator Installation Script"
            echo ""
            echo "Usage: ./install.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --full       Full installation including uinput setup (requires sudo)"
            echo "  --skip-deps  Skip system dependency checks"
            echo "  -h, --help   Show this help message"
            echo ""
            exit 0
            ;;
    esac
done

print_header() {
    echo ""
    echo -e "${BLUE}══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}══════════════════════════════════════════════════════════════${NC}"
    echo ""
}

print_step() {
    echo -e "${GREEN}▶${NC} $1"
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

check_command() {
    if command -v "$1" &> /dev/null; then
        return 0
    else
        return 1
    fi
}

# ============================================================================
# PRE-FLIGHT CHECKS
# ============================================================================

print_header "Dictator Voice Dictation - Installation"

echo "This script will install:"
echo "  • GNOME Shell extension for UI and keyboard shortcuts"
echo "  • Python service for audio recording and transcription"
echo "  • Whisper AI model for speech-to-text (~140MB, downloaded on first use)"
echo ""

# Check if running as root (we don't want that for most of the install)
if [ "$EUID" -eq 0 ] && [ "$FULL_INSTALL" = false ]; then
    print_error "Please don't run this script as root."
    print_error "Run without sudo: ./install.sh"
    print_error "For full install with uinput: ./install.sh --full"
    exit 1
fi

# Check GNOME Shell
if ! check_command gnome-shell; then
    print_error "GNOME Shell not found. This extension requires GNOME."
    exit 1
fi

GNOME_VERSION=$(gnome-shell --version | grep -oP '\d+' | head -1)
if [ "$GNOME_VERSION" -lt 45 ]; then
    print_warning "GNOME Shell version $GNOME_VERSION detected. This extension is tested on GNOME 45+."
fi

print_success "GNOME Shell $GNOME_VERSION detected"

# ============================================================================
# SYSTEM DEPENDENCIES
# ============================================================================

if [ "$SKIP_DEPS" = false ]; then
    print_header "Checking System Dependencies"

    MISSING_DEPS=()

    # Check Python
    if check_command python3; then
        PYTHON_VERSION=$(python3 --version | grep -oP '\d+\.\d+' | head -1)
        print_success "Python $PYTHON_VERSION found"
    else
        MISSING_DEPS+=("python3")
        print_error "Python 3 not found"
    fi

    # Check python3-venv
    if python3 -m venv --help &> /dev/null; then
        print_success "python3-venv available"
    else
        MISSING_DEPS+=("python3-venv")
        print_error "python3-venv not found"
    fi

    # Check PipeWire
    if check_command pw-record; then
        print_success "PipeWire (pw-record) found"
    else
        MISSING_DEPS+=("pipewire")
        print_error "PipeWire not found"
    fi

    # Check glib-compile-schemas
    if check_command glib-compile-schemas; then
        print_success "glib-compile-schemas found"
    else
        MISSING_DEPS+=("libglib2.0-dev-bin")
        print_error "glib-compile-schemas not found"
    fi

    # If missing dependencies, show install command
    if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
        echo ""
        print_error "Missing dependencies detected!"
        echo ""

        # Detect package manager and show appropriate command
        if check_command apt; then
            echo "Install with:"
            echo -e "  ${YELLOW}sudo apt install python3 python3-venv python3-pip pipewire libglib2.0-dev-bin libevdev-dev${NC}"
        elif check_command dnf; then
            echo "Install with:"
            echo -e "  ${YELLOW}sudo dnf install python3 python3-pip pipewire glib2-devel libevdev-devel${NC}"
        elif check_command pacman; then
            echo "Install with:"
            echo -e "  ${YELLOW}sudo pacman -S python python-pip pipewire glib2 libevdev${NC}"
        else
            echo "Please install: ${MISSING_DEPS[*]}"
        fi
        echo ""
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
fi

# ============================================================================
# UINPUT SETUP (requires sudo)
# ============================================================================

setup_uinput() {
    print_header "Setting Up uinput Permissions"

    echo "The application needs access to /dev/uinput to simulate keyboard input."
    echo "This requires creating a udev rule and adding you to the 'uinput' group."
    echo ""

    # Check if already set up
    if groups | grep -q uinput && [ -e /dev/uinput ]; then
        if [ -r /dev/uinput ] && [ -w /dev/uinput ]; then
            print_success "uinput already configured correctly"
            return 0
        fi
    fi

    echo "This step requires sudo privileges."
    echo ""

    # Create uinput group if it doesn't exist
    if ! getent group uinput > /dev/null; then
        print_step "Creating uinput group..."
        sudo groupadd uinput
    fi

    # Add user to uinput group
    if ! groups | grep -q uinput; then
        print_step "Adding $USER to uinput group..."
        sudo usermod -aG uinput "$USER"
        NEED_RELOGIN=true
    fi

    # Create udev rule
    UDEV_RULE="/etc/udev/rules.d/99-dictator-uinput.rules"
    if [ ! -f "$UDEV_RULE" ]; then
        print_step "Creating udev rule..."
        echo 'KERNEL=="uinput", GROUP="uinput", MODE="0660", OPTIONS+="static_node=uinput"' | sudo tee "$UDEV_RULE" > /dev/null
    fi

    # Reload udev rules
    print_step "Reloading udev rules..."
    sudo udevadm control --reload-rules
    sudo udevadm trigger

    # Load uinput module
    if ! lsmod | grep -q uinput; then
        print_step "Loading uinput kernel module..."
        sudo modprobe uinput
    fi

    # Ensure module loads on boot
    if [ ! -f /etc/modules-load.d/uinput.conf ]; then
        echo "uinput" | sudo tee /etc/modules-load.d/uinput.conf > /dev/null
    fi

    print_success "uinput configured successfully"
}

if [ "$FULL_INSTALL" = true ]; then
    setup_uinput
fi

# ============================================================================
# CREATE DIRECTORIES
# ============================================================================

print_header "Installing Dictator"

print_step "Creating directories..."
mkdir -p "$EXTENSION_DIR"
mkdir -p "$EXTENSION_DIR/schemas"
mkdir -p "$SERVICE_DIR"
mkdir -p "$DBUS_SERVICE_DIR"
mkdir -p "$SYSTEMD_USER_DIR"

# ============================================================================
# PYTHON VIRTUAL ENVIRONMENT
# ============================================================================

print_step "Setting up Python virtual environment..."
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi

print_step "Installing Python dependencies..."
"$VENV_DIR/bin/pip" install --upgrade pip --quiet
"$VENV_DIR/bin/pip" install dbus-next evdev faster-whisper --quiet

# Check for NVIDIA GPU and install CUDA libraries
if check_command nvidia-smi; then
    print_step "NVIDIA GPU detected, installing CUDA libraries..."
    "$VENV_DIR/bin/pip" install nvidia-cublas-cu12 nvidia-cudnn-cu12 --quiet 2>/dev/null || {
        print_warning "CUDA libraries installation failed. Will use CPU mode."
    }
else
    print_step "No NVIDIA GPU detected, will use CPU mode"
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

print_step "Compiling GSettings schemas..."
glib-compile-schemas "$EXTENSION_DIR/schemas/"

print_success "Extension installed"

# ============================================================================
# INSTALL SERVICE
# ============================================================================

print_step "Installing D-Bus service..."
cp "$PROJECT_DIR/service/dictator_service.py" "$SERVICE_DIR/"
cp "$PROJECT_DIR/service/recorder.py" "$SERVICE_DIR/"
cp "$PROJECT_DIR/service/transcriber.py" "$SERVICE_DIR/"
cp "$PROJECT_DIR/service/typer.py" "$SERVICE_DIR/"
cp "$PROJECT_DIR/service/__init__.py" "$SERVICE_DIR/" 2>/dev/null || touch "$SERVICE_DIR/__init__.py"

chmod +x "$SERVICE_DIR/dictator_service.py"

# Install D-Bus service file (replace %h with actual home)
sed "s|%h|$HOME|g" "$PROJECT_DIR/service/org.lebi.Dictator.service" > "$DBUS_SERVICE_DIR/org.lebi.Dictator.service"

# Install systemd user service
sed "s|%h|$HOME|g" "$PROJECT_DIR/systemd/dictator.service" > "$SYSTEMD_USER_DIR/dictator.service"

print_step "Reloading systemd..."
systemctl --user daemon-reload

print_success "Service installed"

# ============================================================================
# ENABLE EXTENSION
# ============================================================================

print_step "Enabling extension..."
gnome-extensions enable dictator@lebi 2>/dev/null || {
    print_warning "Could not enable extension automatically."
    print_warning "You may need to log out and back in, then run:"
    print_warning "  gnome-extensions enable dictator@lebi"
}

# ============================================================================
# FINAL STATUS
# ============================================================================

print_header "Installation Complete!"

echo -e "${GREEN}Dictator has been installed successfully!${NC}"
echo ""

# Check what else needs to be done
NEXT_STEPS=()

# Check uinput
if [ "$FULL_INSTALL" = false ]; then
    if ! groups | grep -q uinput; then
        NEXT_STEPS+=("Set up uinput permissions (required for typing):\n   ${YELLOW}sudo $PROJECT_DIR/scripts/setup_uinput.sh${NC}\n   Then log out and back in.")
    fi
fi

# Check if relogin needed
if [ "${NEED_RELOGIN:-false}" = true ]; then
    NEXT_STEPS+=("Log out and log back in for group membership to take effect.")
fi

# Check if on Wayland
if [ "$XDG_SESSION_TYPE" = "wayland" ]; then
    NEXT_STEPS+=("On Wayland, log out and back in to fully load the extension.")
fi

if [ ${#NEXT_STEPS[@]} -gt 0 ]; then
    echo -e "${YELLOW}Next steps:${NC}"
    echo ""
    for i in "${!NEXT_STEPS[@]}"; do
        echo -e "  $((i+1)). ${NEXT_STEPS[$i]}"
        echo ""
    done
else
    echo "You're all set! Start using Dictator:"
    echo ""
fi

echo -e "${BLUE}Usage:${NC}"
echo "  1. Press ${GREEN}Ctrl+Shift+Space${NC} to start recording"
echo "  2. Speak your text"
echo "  3. Press ${GREEN}Ctrl+Shift+Space${NC} again to stop"
echo "  4. The text will be typed into the focused application"
echo ""
echo -e "${BLUE}First run:${NC}"
echo "  The Whisper AI model (~140MB) will download automatically on first use."
echo ""
echo -e "${BLUE}Troubleshooting:${NC}"
echo "  Check logs: journalctl --user | grep -i dictator"
echo "  More help:  See README.md"
echo ""
