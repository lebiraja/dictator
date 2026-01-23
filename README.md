# Dictator

<p align="center">
  <img src="https://raw.githubusercontent.com/lebiraja/dictator/main/assets/icon.svg" width="128" height="128" alt="Dictator Icon">
</p>

<p align="center">
  <strong>System-wide voice dictation for GNOME on Linux</strong>
</p>

<p align="center">
  <a href="https://extensions.gnome.org/extension/XXXX/dictator/">
    <img src="https://img.shields.io/badge/GNOME%20Extensions-Install-blue?logo=gnome" alt="Get it on GNOME Extensions">
  </a>
  <a href="https://github.com/lebiraja/dictator/releases">
    <img src="https://img.shields.io/github/v/release/lebiraja/dictator" alt="GitHub Release">
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/github/license/lebiraja/dictator" alt="License">
  </a>
</p>

---

Press a keyboard shortcut to record your speech, and it will be transcribed locally using AI and automatically typed into any focused application.

**Privacy-first**: All processing happens locally on your machine. No audio is sent to the cloud.

## Features

- 🎤 **Global keyboard shortcut** (Ctrl+Shift+Space) to toggle recording
- 🤖 **Local AI transcription** using OpenAI's Whisper model
- ⌨️ **Works everywhere** - types directly into any application
- 🖥️ **Wayland & X11 compatible** - uses kernel-level input injection
- 👁️ **Visual feedback** - panel icon and overlay show recording status
- 🔒 **Fully offline** - no internet required after initial setup
- ⚡ **GPU acceleration** - uses CUDA if available, falls back to CPU

## Demo

<p align="center">
  <img src="https://raw.githubusercontent.com/lebiraja/dictator/main/assets/demo.gif" alt="Dictator Demo" width="600">
</p>

## Installation

### Method 1: Quick Install (Recommended)

```bash
git clone https://github.com/lebiraja/dictator.git
cd dictator
./install.sh --full
```

Then **log out and log back in**.

### Method 2: GNOME Extensions + Manual Backend

1. **Install the extension** from [GNOME Extensions](https://extensions.gnome.org/extension/XXXX/dictator/)

2. **Install the backend service:**
   ```bash
   git clone https://github.com/lebiraja/dictator.git
   cd dictator
   ./install.sh --backend-only
   ```

3. **Set up permissions and restart:**
   ```bash
   sudo ./scripts/setup_uinput.sh
   # Log out and log back in
   ```

### Method 3: From GitHub Releases

1. Download the latest release from [Releases](https://github.com/lebiraja/dictator/releases)
2. Extract and run:
   ```bash
   tar -xzf dictator-*.tar.gz
   cd dictator
   ./install.sh --full
   ```

## Usage

1. **Press `Ctrl+Shift+Space`** to start recording
2. **Speak** your text
3. **Press `Ctrl+Shift+Space`** again to stop
4. The transcribed text is automatically typed into the focused application

### First Run

On first use, the Whisper AI model (~140MB) will download automatically. This only happens once.

## Requirements

- **GNOME Shell 45+** (Ubuntu 24.04+, Fedora 40+, Arch, etc.)
- **PipeWire** (default on most modern distros)
- **Python 3.10+**

### Installing Dependencies

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
# Change to Super+D
gsettings --schemadir ~/.local/share/gnome-shell/extensions/dictator@lebi/schemas \
  set org.gnome.shell.extensions.dictator shortcut "['<Super>d']"
```

### Available Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `shortcut` | `Ctrl+Shift+Space` | Keyboard shortcut |
| `model` | `base.en` | Whisper model (tiny.en, base.en, small.en) |
| `show-overlay` | `true` | Show visual overlay when recording |
| `show-notifications` | `true` | Show notifications |

## Troubleshooting

### Shortcut not working

```bash
# Reload extension
gnome-extensions disable dictator@lebi
gnome-extensions enable dictator@lebi
```

On Wayland, log out and back in.

### "No speech detected"

Check your microphone:
```bash
pw-record --format s16 --rate 16000 --channels 1 test.wav
# Speak, then Ctrl+C - file should be > 1KB
```

### Permission denied for /dev/uinput

```bash
sudo ./scripts/setup_uinput.sh
# Log out and log back in
groups | grep uinput  # Should show uinput
```

### Check logs

```bash
journalctl --user | grep -i dictator | tail -30
```

## Architecture

```
┌────────────────────────────────────┐
│     GNOME Shell Extension          │
│  • Panel indicator                 │
│  • Keyboard shortcut               │
│  • Visual overlay                  │
└──────────────┬─────────────────────┘
               │ D-Bus
               ▼
┌────────────────────────────────────┐
│     Python D-Bus Service           │
└──────┬───────────┬───────────┬─────┘
       ▼           ▼           ▼
   Recorder    Transcriber   Typer
   (PipeWire)   (Whisper)   (uinput)
```

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## Roadmap

- [ ] Preferences UI (GTK settings dialog)
- [ ] Multi-language support
- [ ] Clipboard mode option
- [ ] Dictation history
- [ ] Voice commands (punctuation, formatting)
- [ ] Quick Settings integration

## License

MIT License - see [LICENSE](LICENSE)

## Acknowledgments

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) - Optimized Whisper implementation
- [python-evdev](https://github.com/gvalkov/python-evdev) - Linux input device library
- [dbus-next](https://github.com/altdesktop/python-dbus-next) - Async D-Bus library

---

<p align="center">
  Made with ❤️ for the Linux community
</p>
