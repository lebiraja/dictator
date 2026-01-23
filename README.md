# Dictator

A system-wide voice dictation application for GNOME on Linux. Press a keyboard shortcut to record your speech, and it will be transcribed locally using AI and automatically typed into any focused application.

**Privacy-first**: All processing happens locally on your machine. No audio is sent to the cloud.

## Features

- **Global keyboard shortcut** (Ctrl+Shift+Space) to toggle recording
- **Local AI transcription** using OpenAI's Whisper model via faster-whisper
- **Works everywhere** - types directly into any application (browsers, editors, terminals)
- **Wayland & X11 compatible** - uses kernel-level input injection
- **Visual feedback** - panel icon and overlay show recording status
- **Fully offline** - no internet required after initial model download (~140MB)
- **GPU acceleration** - automatically uses CUDA if available, falls back to CPU

## Requirements

- **GNOME Shell 45+** (Ubuntu 24.04+, Fedora 40+, etc.)
- **PipeWire** (default on most modern Linux distros)
- **Python 3.10+**

## Quick Start

### One-Command Installation

```bash
git clone https://github.com/lebi/dictator.git
cd dictator
./install.sh --full
```

The `--full` flag sets up everything including uinput permissions (requires sudo).

After installation, **log out and log back in**, then press **Ctrl+Shift+Space** to start dictating!

### Manual Installation

If you prefer more control:

```bash
# Clone the repository
git clone https://github.com/lebi/dictator.git
cd dictator

# Install without uinput setup
./install.sh

# Set up uinput separately (requires sudo)
sudo ./scripts/setup_uinput.sh

# Log out and back in for group membership to take effect
```

## Usage

1. **Press `Ctrl+Shift+Space`** to start recording
2. **Speak** your text
3. **Press `Ctrl+Shift+Space`** again to stop
4. The transcribed text is automatically typed into the focused application

You can also click the microphone icon in the top panel to access controls.

### First Run

On first use, the Whisper model (~140MB) will be downloaded automatically. This only happens once.

## System Requirements

### Supported Distributions

| Distribution | Version | Status |
|-------------|---------|--------|
| Ubuntu | 24.04+ | ✅ Tested |
| Fedora | 40+ | ✅ Tested |
| Arch Linux | Rolling | ✅ Tested |
| Debian | 13+ | Should work |
| Pop!_OS | 24.04+ | Should work |

### Dependencies

The install script will check for these and guide you to install any missing:

**Ubuntu/Debian:**
```bash
sudo apt install python3 python3-venv python3-pip pipewire libglib2.0-dev-bin libevdev-dev
```

**Fedora:**
```bash
sudo dnf install python3 python3-pip pipewire glib2-devel libevdev-devel
```

**Arch:**
```bash
sudo pacman -S python python-pip pipewire glib2 libevdev
```

## Configuration

### Changing the Keyboard Shortcut

```bash
# View current shortcut
gsettings --schemadir ~/.local/share/gnome-shell/extensions/dictator@lebi/schemas \
  get org.gnome.shell.extensions.dictator shortcut

# Change to Super+D
gsettings --schemadir ~/.local/share/gnome-shell/extensions/dictator@lebi/schemas \
  set org.gnome.shell.extensions.dictator shortcut "['<Super>d']"

# Change to Ctrl+Alt+V
gsettings --schemadir ~/.local/share/gnome-shell/extensions/dictator@lebi/schemas \
  set org.gnome.shell.extensions.dictator shortcut "['<Control><Alt>v']"
```

### Available Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `shortcut` | string array | `['<Control><Shift>space']` | Keyboard shortcut |
| `model` | string | `base.en` | Whisper model size |
| `show-overlay` | boolean | `true` | Show visual overlay |
| `show-notifications` | boolean | `true` | Show notifications |

### Whisper Models

| Model | Size | Speed | Accuracy |
|-------|------|-------|----------|
| `tiny.en` | ~75MB | Fastest | Good |
| `base.en` | ~140MB | Fast | Better (default) |
| `small.en` | ~460MB | Slower | Best |

## Architecture

```
┌──────────────────────────────────────┐
│   GNOME Shell Extension              │
│   • Panel indicator                  │
│   • Keyboard shortcut (Ctrl+Shift+Space)
│   • Recording overlay                │
└─────────────────┬────────────────────┘
                  │ D-Bus IPC
                  ▼
┌──────────────────────────────────────┐
│   Python D-Bus Service               │
│   • State machine                    │
│   • Orchestration                    │
└───────┬──────────┬──────────┬────────┘
        │          │          │
        ▼          ▼          ▼
   ┌────────┐ ┌─────────┐ ┌───────┐
   │Recorder│ │Transcri-│ │ Typer │
   │        │ │  ber    │ │       │
   └────────┘ └─────────┘ └───────┘
        │          │          │
        ▼          ▼          ▼
   PipeWire    Whisper    /dev/uinput
   (pw-record)  (AI)      (keyboard)
```

## Troubleshooting

### Shortcut not working

```bash
# Check extension status
gnome-extensions show dictator@lebi

# Reload extension
gnome-extensions disable dictator@lebi
gnome-extensions enable dictator@lebi
```

On Wayland, you may need to log out and back in.

### "No speech detected"

1. Check your microphone is set as default input
2. Test PipeWire is working:
   ```bash
   pw-record --format s16 --rate 16000 --channels 1 test.wav
   # Speak, then Ctrl+C
   # File should be > 1KB
   ```

### Permission denied for /dev/uinput

```bash
# Run uinput setup
sudo ./scripts/setup_uinput.sh

# Verify group membership (after re-login)
groups | grep uinput

# Check device permissions
ls -la /dev/uinput
# Should show: crw-rw---- 1 root uinput
```

### Service errors

```bash
# Check service logs
journalctl --user | grep -i dictator | tail -30

# Test D-Bus manually
dbus-send --session --print-reply --dest=org.lebi.Dictator \
  /org/lebi/Dictator org.lebi.Dictator.GetState
```

### CUDA/GPU issues

If you see `libcublas.so.12 not found`, the app will automatically fall back to CPU. For GPU acceleration, ensure NVIDIA drivers are installed:

```bash
# Check NVIDIA driver
nvidia-smi

# Reinstall CUDA libraries
~/.local/share/dictator/venv/bin/pip install --force-reinstall nvidia-cublas-cu12 nvidia-cudnn-cu12
```

## Uninstallation

```bash
./scripts/uninstall.sh
```

Or manually:
```bash
# Remove extension
rm -rf ~/.local/share/gnome-shell/extensions/dictator@lebi

# Remove service
rm -rf ~/.local/share/dictator
rm ~/.local/share/dbus-1/services/org.lebi.Dictator.service
rm ~/.config/systemd/user/dictator.service

# Disable extension
gnome-extensions disable dictator@lebi
```

## Development

### Project Structure

```
dictate/
├── extension/                 # GNOME Shell extension
│   ├── extension.js           # Main extension code
│   ├── metadata.json          # Extension metadata
│   ├── stylesheet.css         # UI styling
│   └── schemas/               # GSettings schema
├── service/                   # Python D-Bus service
│   ├── dictator_service.py    # Main service entry point
│   ├── recorder.py            # Audio recording via PipeWire
│   ├── transcriber.py         # Whisper transcription
│   └── typer.py               # Virtual keyboard input
├── scripts/                   # Utility scripts
│   ├── install.sh             # Legacy installer
│   ├── uninstall.sh           # Uninstaller
│   └── setup_uinput.sh        # uinput permission setup
├── systemd/                   # Systemd service file
├── install.sh                 # Main installer
└── README.md
```

### Running from Source

```bash
# Create venv and install deps
python3 -m venv venv
source venv/bin/activate
pip install dbus-next evdev faster-whisper

# Run service
python service/dictator_service.py

# Test via D-Bus
dbus-send --session --print-reply --dest=org.lebi.Dictator \
  /org/lebi/Dictator org.lebi.Dictator.Toggle
```

### D-Bus API

Service: `org.lebi.Dictator`
Path: `/org/lebi/Dictator`

| Method | Returns | Description |
|--------|---------|-------------|
| `Toggle()` | string | Toggle recording, returns new state |
| `StartRecording()` | boolean | Start recording |
| `StopRecording()` | string | Stop and transcribe |
| `Cancel()` | boolean | Cancel operation |
| `GetState()` | string | Current state |

States: `idle` → `recording` → `transcribing` → `typing` → `idle`

## Contributing

Contributions welcome! Please open an issue or PR on GitHub.

## License

MIT License - see LICENSE file.

## Acknowledgments

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) - Optimized Whisper implementation
- [python-evdev](https://github.com/gvalkov/python-evdev) - Linux input device library
- [dbus-next](https://github.com/altdesktop/python-dbus-next) - Modern async D-Bus library
