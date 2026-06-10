# Dictator

<p align="center">
  <img src="assets/icon.svg" width="128" height="128" alt="Dictator Icon">
</p>

<p align="center">
  <strong>🎤 Voice Dictation for GNOME Linux</strong><br>
  <em>Speak and let AI type for you. Locally. Privately.</em>
</p>

<p align="center">
  <a href="https://github.com/lebiraja/dictator/releases">
    <img src="https://img.shields.io/github/v/release/lebiraja/dictator?label=version" alt="Release">
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  </a>
  <img src="https://img.shields.io/badge/GNOME-45%2B-blue?logo=gnome" alt="GNOME 45+">
  <a href="https://launchpad.net/~lebiraja/+archive/ubuntu/dictator">
    <img src="https://img.shields.io/badge/Ubuntu-PPA-orange?logo=ubuntu" alt="Ubuntu PPA">
  </a>
</p>

---

Press **Shift+Ctrl+Space**, speak, press again — your words appear wherever you're typing.

- 🔒 **100% Local** — No cloud, no data leaves your machine
- ⚡ **Fast** — GPU-accelerated with CUDA, or runs on CPU
- 🖥️ **Universal** — Works on Wayland and X11, in any app
- 🎯 **Simple** — One shortcut, zero configuration needed

<p align="center">
  <img src="assets/demo.gif" alt="Dictator Demo" width="800">
</p>

## Installation

### Ubuntu 24.04+ (Recommended - via PPA)

```bash
# Add the PPA
sudo add-apt-repository ppa:lebiraja/dictator

# Update package list
sudo apt update

# Install Dictator
sudo apt install dictator
```

**Post-installation steps:**

1. **Add yourself to the uinput group** (required for keyboard input):
   ```bash
   sudo usermod -a -G uinput $USER
   ```

2. **Run the per-user setup** (creates the Python environment and enables the extension):
   ```bash
   dictator-setup
   ```

3. **Log out and log back in** (required for group membership to take effect)

4. **Start dictating** with **Shift+Ctrl+Space**! 🎤

   The AI model (~460MB) downloads automatically when the service first starts.

**Benefits of PPA installation:**
- ✅ Automatic updates via `apt upgrade`
- ✅ Clean uninstallation with `apt remove`
- ✅ All system dependencies handled automatically
- ✅ Follows Ubuntu packaging standards

**Optional - GPU Acceleration (NVIDIA users):**

For faster transcription, install the CUDA runtime wheels into Dictator's
environment (a few hundred MB — no 6GB toolkit needed):
```bash
~/.local/share/dictator/venv/bin/pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
```

The service automatically uses the GPU when CUDA is available, and falls
back to CPU otherwise.

---

## Getting Started

### First-Time Setup (Required)

After installation, complete these one-time setup steps:

**1. Add yourself to the uinput group:**
```bash
sudo usermod -a -G uinput $USER
```
This grants permission to simulate keyboard input.

**2. Log out and log back in** (or reboot)
```bash
gnome-session-quit --logout
```
Required for group membership to take effect.

**3. Enable the GNOME extension:**
```bash
gnome-extensions enable dictator@lebi
```
Or use the GNOME Extensions app (GUI).

**4. Verify installation:**
```bash
# Check extension is enabled
gnome-extensions list | grep dictator

# Check you're in uinput group
groups | grep uinput
```

### First Use

**Press Shift+Ctrl+Space** and speak. Press again when done.

On first use, Dictator will:
- Download the Whisper AI model (~140MB for base model)
- Install Python dependencies in a virtual environment
- This takes 2-3 minutes and only happens once

**What you'll see:**
1. Panel icon turns **red** = Recording
2. Speak your text clearly
3. Press **Shift+Ctrl+Space** again = Processing
4. Text appears in your focused application!

### Quick Test

```bash
# Open any text editor
gedit &

# Click in the editor window
# Press Shift+Ctrl+Space
# Say: "Hello world, this is a test"
# Press Shift+Ctrl+Space again
# Text should appear!
```

---

### Other Distros (Manual Install)

```bash
git clone https://github.com/lebiraja/dictator.git
cd dictator
./install.sh
```

The script handles everything:
- ✅ Installs GNOME extension
- ✅ Sets up Python backend with Whisper AI
- ✅ Configures keyboard permissions
- ✅ Downloads AI model when the service first starts (~460MB, small.en)

After install, **log out and log back in**, then press **Shift+Ctrl+Space** to start!

## How It Works

```
┌─────────────────────────────────────────────────────────┐
│  You press Shift+Ctrl+Space and speak                   │
└─────────────────────────┬───────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────┐
│  🎤 Microphone captures your voice (PipeWire)           │
└─────────────────────────┬───────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────┐
│  🤖 Whisper AI transcribes locally (no internet!)       │
└─────────────────────────┬───────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────┐
│  ⌨️ Text is pasted into your focused application        │
│     (clipboard is saved and restored automatically)     │
└─────────────────────────────────────────────────────────┘
```

Audio is processed entirely in memory — it never touches disk. While you
speak, a floating overlay shows a live audio level meter and elapsed time.

## Other Desktops (KDE, Sway, Hyprland, …)

The dictation service is plain D-Bus — only the panel UI is GNOME-specific.
On any desktop, bind the bundled CLI to a hotkey:

```bash
dictator toggle    # start recording / stop + transcribe + type
dictator status    # idle | recording | transcribing | ...
dictator cancel    # abort
```

(Installed to `~/.local/bin/dictator` by `install.sh`, `/usr/bin/dictator`
via the deb package.)

## Requirements

- **GNOME 45+** (Ubuntu 24.04+, Fedora 40+, Arch, etc.)
- **PipeWire** (default on modern distros)
- **Python 3.10+**

> **Note:** Ubuntu PPA installation handles all dependencies automatically!

<details>
<summary><strong>📦 Manual dependency installation (for non-Ubuntu distros)</strong></summary>

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

</details>

## Configuration

The easiest way: click the panel microphone icon → **Settings**. The
preferences window covers the shortcut, Whisper model, output mode, max
recording duration, and overlay/notification toggles.

Everything is also scriptable via `gsettings`:

### Keyboard Shortcut

Change the dictation toggle shortcut:

```bash
# Change to Super+D (Windows/Meta key + D)
gsettings --schemadir ~/.local/share/gnome-shell/extensions/dictator@lebi/schemas \
  set org.gnome.shell.extensions.dictator shortcut "['<Super>d']"

# Change to Ctrl+Alt+Space
gsettings --schemadir ~/.local/share/gnome-shell/extensions/dictator@lebi/schemas \
  set org.gnome.shell.extensions.dictator shortcut "['<Control><Alt>space']"
```

### Whisper AI Model

Choose between speed and accuracy:

```bash
# Tiny model - Fastest, less accurate (~39MB)
gsettings --schemadir ~/.local/share/gnome-shell/extensions/dictator@lebi/schemas \
  set org.gnome.shell.extensions.dictator model 'tiny.en'

# Base model - Balanced (~74MB)
gsettings --schemadir ~/.local/share/gnome-shell/extensions/dictator@lebi/schemas \
  set org.gnome.shell.extensions.dictator model 'base.en'

# Small model - Most accurate (default, ~244MB)
gsettings --schemadir ~/.local/share/gnome-shell/extensions/dictator@lebi/schemas \
  set org.gnome.shell.extensions.dictator model 'small.en'
```

### Output Mode

Control how transcribed text is inserted:

```bash
# Paste mode (default) — instant Ctrl+V paste, clipboard saved & restored,
# works with any keyboard layout (Wayland and X11)
gsettings --schemadir ~/.local/share/gnome-shell/extensions/dictator@lebi/schemas \
  set org.gnome.shell.extensions.dictator output-mode 'clipboard'

# Type mode — simulates each keystroke (US layout); use for apps that
# block pasting, e.g. terminals that expect Ctrl+Shift+V
gsettings --schemadir ~/.local/share/gnome-shell/extensions/dictator@lebi/schemas \
  set org.gnome.shell.extensions.dictator output-mode 'type'
```

### Visual Feedback

Toggle notifications and recording overlay:

```bash
# Disable notifications
gsettings --schemadir ~/.local/share/gnome-shell/extensions/dictator@lebi/schemas \
  set org.gnome.shell.extensions.dictator show-notifications false

# Disable recording overlay
gsettings --schemadir ~/.local/share/gnome-shell/extensions/dictator@lebi/schemas \
  set org.gnome.shell.extensions.dictator show-overlay false
```

### Quick Settings Reference

| Setting | Default | Options | Description |
|---------|---------|---------|-------------|
| `shortcut` | `<Shift><Control>space` | Any key combo | Keyboard shortcut to toggle recording |
| `model` | `small.en` | `tiny.en`, `base.en`, `small.en` | Whisper AI model (speed vs accuracy) |
| `output-mode` | `clipboard` | `clipboard`, `type` | Paste via Ctrl+V (fast) or simulate keystrokes |
| `max-duration` | `120` | 10–600 | Seconds before recording auto-stops |
| `show-overlay` | `true` | `true`, `false` | Floating pill with live level meter and timer |
| `show-notifications` | `true` | `true`, `false` | Show notification popups |

### View Current Settings

```bash
# Show all current settings
gsettings --schemadir ~/.local/share/gnome-shell/extensions/dictator@lebi/schemas \
  list-recursively org.gnome.shell.extensions.dictator
```

## Troubleshooting

<details>
<summary><strong>Extension not showing in top bar</strong></summary>

```bash
# 1. Check if extension is enabled
gnome-extensions list | grep dictator

# 2. If disabled, enable it
gnome-extensions enable dictator@lebi

# 3. Restart GNOME Shell
# On X11: Alt+F2, type 'r', press Enter
# On Wayland: Log out and log back in

# 4. Check for errors
journalctl --user -f | grep -i dictator
```

</details>

<details>
<summary><strong>Keyboard shortcut not working</strong></summary>

```bash
# 1. Check for conflicting shortcuts
gsettings get org.gnome.desktop.wm.keybindings switch-input-source

# 2. Reload extension
gnome-extensions disable dictator@lebi
gnome-extensions enable dictator@lebi

# 3. On Wayland, log out and back in

# 4. Try a different shortcut
gsettings --schemadir ~/.local/share/gnome-shell/extensions/dictator@lebi/schemas \
  set org.gnome.shell.extensions.dictator shortcut "['<Super>d']"
```

</details>

<details>
<summary><strong>Permission denied / Text not appearing</strong></summary>

```bash
# 1. Verify you're in uinput group
groups | grep uinput

# If not found:
sudo usermod -a -G uinput $USER
# Then log out and log back in

# 2. Check uinput device permissions
ls -l /dev/uinput
# Should show: crw-rw---- 1 root uinput

# 3. Verify udev rule exists
cat /etc/udev/rules.d/99-dictator-uinput.rules
# Should contain: KERNEL=="uinput", GROUP="uinput", MODE="0660"

# 4. Reload udev rules if needed
sudo udevadm control --reload-rules
sudo udevadm trigger
```

</details>

<details>
<summary><strong>"No speech detected" or no transcription</strong></summary>

Test your microphone:
```bash
# 1. Test microphone with PipeWire
pw-record --format s16 --rate 16000 --channels 1 test.wav
# Speak for a few seconds, then Ctrl+C
# File should be > 1KB

# 2. Check default microphone
pactl list sources short

# 3. Check PipeWire is running
systemctl --user status pipewire

# 4. Test with different Whisper model
gsettings --schemadir ~/.local/share/gnome-shell/extensions/dictator@lebi/schemas \
  set org.gnome.shell.extensions.dictator model 'small.en'
```

</details>

<details>
<summary><strong>Python dependencies not installing</strong></summary>

```bash
# 1. Check Python version (needs 3.10-3.13)
python3 --version

# 2. Check venv location
ls -la ~/.local/share/dictator/venv

# 3. Manual dependency install
cd ~/.local/share/dictator
python3 -m venv venv
source venv/bin/activate
pip install dbus-next evdev faster-whisper

# 4. For GPU support
pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
```

</details>

<details>
<summary><strong>Slow transcription / Want GPU acceleration</strong></summary>

```bash
# 1. Check if NVIDIA GPU is detected
nvidia-smi

# 2. Install CUDA toolkit
sudo apt install nvidia-cuda-toolkit

# 3. Reinstall dictator to trigger CUDA setup
sudo apt reinstall dictator
# Choose "GPU (CUDA)" when prompted

# 4. Verify CUDA is working
python3 -c "import torch; print(torch.cuda.is_available())"
```

</details>

<details>
<summary><strong>View logs for debugging</strong></summary>

```bash
# Real-time logs
journalctl --user -f | grep -i dictator

# Recent errors
journalctl --user -p err | grep -i dictator | tail -20

# Service status
systemctl --user status dictator.service

# Extension logs
journalctl /usr/bin/gnome-shell | grep -i dictator | tail -30
```

</details>

<details>
<summary><strong>Complete reset and reinstall</strong></summary>

```bash
# 1. Remove completely
sudo apt remove --purge dictator
rm -rf ~/.local/share/dictator
rm -rf ~/.local/share/gnome-shell/extensions/dictator@lebi

# 2. Clean install
sudo apt update
sudo apt install dictator

# 3. Follow first-time setup steps again
sudo usermod -a -G uinput $USER
# Log out and log back in
gnome-extensions enable dictator@lebi
```

</details>

## Quick Reference

### Essential Commands

```bash
# Start/stop dictation
Shift+Ctrl+Space (press to start, press again to stop)

# Enable extension
gnome-extensions enable dictator@lebi

# Disable extension
gnome-extensions disable dictator@lebi

# View logs
journalctl --user -f | grep dictator

# Check status
systemctl --user status dictator.service

# Add to uinput group (one-time)
sudo usermod -a -G uinput $USER
```

### Common Configurations

```bash
# Change shortcut to Super+D
gsettings --schemadir ~/.local/share/gnome-shell/extensions/dictator@lebi/schemas \
  set org.gnome.shell.extensions.dictator shortcut "['<Super>d']"

# Use faster tiny model
gsettings --schemadir ~/.local/share/gnome-shell/extensions/dictator@lebi/schemas \
  set org.gnome.shell.extensions.dictator model 'tiny.en'

# Disable notifications
gsettings --schemadir ~/.local/share/gnome-shell/extensions/dictator@lebi/schemas \
  set org.gnome.shell.extensions.dictator show-notifications false
```

### File Locations

```
~/.local/share/gnome-shell/extensions/dictator@lebi/  # Extension files
~/.local/share/dictator/                               # Backend service
~/.local/share/dictator/venv/                         # Python dependencies
~/.config/systemd/user/dictator.service               # Systemd service
/etc/udev/rules.d/99-dictator-uinput.rules           # uinput permissions
```

---

## Uninstall

### If installed via PPA:

```bash
sudo apt remove dictator
sudo add-apt-repository --remove ppa:lebiraja/dictator
```

### If installed manually:

```bash
cd dictator
./install.sh --remove
```

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT License — see [LICENSE](LICENSE)

---

<p align="center">
  <strong>Made with ❤️ for the Linux community</strong><br>
  <a href="https://github.com/lebiraja/dictator/issues">Report Bug</a> ·
  <a href="https://github.com/lebiraja/dictator/issues">Request Feature</a>
</p>
