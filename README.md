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

- **GNOME Shell 45-48** (Ubuntu 24.04+, Fedora 40+, etc.)
- **PipeWire** (default on most modern Linux distros)
- **Python 3.10+**

## Installation

### Quick Install

```bash
git clone https://github.com/lebi/dictator.git
cd dictator
./scripts/install.sh
```

### Set up permissions

The application needs access to `/dev/uinput` for typing. Run:

```bash
sudo ./scripts/setup_uinput.sh
```

Then **log out and log back in** for the group membership to take effect.

### Enable the extension

```bash
gnome-extensions enable dictator@lebi
```

On Wayland, you may need to log out and back in for the extension to fully load.

## Usage

1. **Press `Ctrl+Shift+Space`** to start recording
2. **Speak** your text
3. **Press `Ctrl+Shift+Space`** again to stop
4. The transcribed text is automatically typed into the focused application

You can also click the microphone icon in the top panel to access controls.

### First Run

On first use, the Whisper model (~140MB) will be downloaded automatically. This only happens once.

## Architecture

```
+---------------------------+
|   GNOME Extension         |  <- Panel icon, overlay, keyboard shortcut
|   (extension.js)          |
+-----------+---------------+
            | D-Bus (org.lebi.Dictator)
            v
+---------------------------+
|   Python D-Bus Service    |  <- Orchestrates recording, transcription, typing
|   (dictator_service.py)   |
+-----+--------+-------+----+
      |        |       |
      v        v       v
  Recorder  Transcriber  Typer
  (pw-record) (whisper)  (uinput)
```

### Components

| Component | File | Description |
|-----------|------|-------------|
| Extension | `extension/extension.js` | GNOME Shell UI, keyboard shortcut, D-Bus client |
| Service | `service/dictator_service.py` | D-Bus server, state machine, orchestration |
| Recorder | `service/recorder.py` | Audio capture via PipeWire (pw-record) |
| Transcriber | `service/transcriber.py` | Speech-to-text using faster-whisper |
| Typer | `service/typer.py` | Virtual keyboard via /dev/uinput |

## Configuration

Settings are stored in GSettings. You can modify them using `dconf-editor` or `gsettings`:

```bash
# View current shortcut
gsettings --schemadir ~/.local/share/gnome-shell/extensions/dictator@lebi/schemas \
  get org.gnome.shell.extensions.dictator shortcut

# Change shortcut (example: Super+D)
gsettings --schemadir ~/.local/share/gnome-shell/extensions/dictator@lebi/schemas \
  set org.gnome.shell.extensions.dictator shortcut "['<Super>d']"
```

### Available Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `shortcut` | string array | `['<Control><Shift>space']` | Keyboard shortcut to toggle dictation |
| `model` | string | `base.en` | Whisper model: `tiny.en`, `base.en`, `small.en` |
| `show-overlay` | boolean | `true` | Show visual overlay when recording |
| `show-notifications` | boolean | `true` | Show notifications for results/errors |

## Troubleshooting

### Shortcut not working

1. Make sure the extension is enabled:
   ```bash
   gnome-extensions show dictator@lebi
   ```

2. Try disabling and re-enabling:
   ```bash
   gnome-extensions disable dictator@lebi
   gnome-extensions enable dictator@lebi
   ```

3. On Wayland, log out and back in after installation.

### "No speech detected"

- Make sure your microphone is working and set as the default input device
- Check PipeWire is running: `systemctl --user status pipewire`
- Test recording: `pw-record --format s16 --rate 16000 --channels 1 test.wav`

### Permission denied for /dev/uinput

Run the uinput setup script and re-login:
```bash
sudo ./scripts/setup_uinput.sh
# Then log out and log back in
```

Verify you're in the uinput group:
```bash
groups | grep uinput
```

### Service not starting

Check service logs:
```bash
journalctl --user -u dictator -f
```

Or check D-Bus activation:
```bash
journalctl --user | grep -i dictator | tail -20
```

### CUDA errors

If you see `libcublas.so.12 not found`, the application will automatically fall back to CPU mode. To use GPU acceleration, ensure NVIDIA drivers and CUDA libraries are properly installed.

## Uninstallation

```bash
./scripts/uninstall.sh
```

This will remove:
- GNOME Shell extension
- D-Bus service files
- Systemd user service
- Python virtual environment (optional, will prompt)

The Whisper model cache in `~/.cache/huggingface/` is preserved.

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
│   ├── dictator_service.py    # Main service
│   ├── recorder.py            # Audio recording
│   ├── transcriber.py         # Whisper transcription
│   └── typer.py               # Virtual keyboard
├── scripts/                   # Installation scripts
├── systemd/                   # Systemd service file
└── README.md
```

### Running from source

```bash
# Install dependencies
python3 -m venv venv
source venv/bin/activate
pip install dbus-next evdev faster-whisper

# Run service manually
python service/dictator_service.py

# In another terminal, test via D-Bus
dbus-send --session --print-reply --dest=org.lebi.Dictator \
  /org/lebi/Dictator org.lebi.Dictator.Toggle
```

### D-Bus Interface

The service exposes these methods on `org.lebi.Dictator`:

| Method | Returns | Description |
|--------|---------|-------------|
| `Toggle()` | string | Toggle recording on/off, returns new state |
| `StartRecording()` | boolean | Start recording |
| `StopRecording()` | string | Stop and transcribe, returns text |
| `Cancel()` | boolean | Cancel current operation |
| `GetState()` | string | Get current state |

States: `idle`, `recording`, `transcribing`, `typing`, `error`

## License

MIT License

## Acknowledgments

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) - Fast Whisper implementation
- [python-evdev](https://github.com/gvalkov/python-evdev) - Linux input device access
- [dbus-next](https://github.com/altdesktop/python-dbus-next) - Modern D-Bus library
