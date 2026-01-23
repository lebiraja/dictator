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
</p>

---

Press **Ctrl+Shift+Space**, speak, press again — your words appear wherever you're typing.

- 🔒 **100% Local** — No cloud, no data leaves your machine
- ⚡ **Fast** — GPU-accelerated with CUDA, or runs on CPU
- 🖥️ **Universal** — Works on Wayland and X11, in any app
- 🎯 **Simple** — One shortcut, zero configuration needed

## Quick Install

```bash
git clone https://github.com/lebiraja/dictator.git
cd dictator
./install.sh
```

That's it! The script handles everything:
- ✅ Installs GNOME extension
- ✅ Sets up Python backend with Whisper AI
- ✅ Configures keyboard permissions
- ✅ Downloads AI model on first use (~140MB)

After install, **log out and log back in**, then press **Ctrl+Shift+Space** to start!

### One-liner Install

```bash
git clone https://github.com/lebiraja/dictator.git && cd dictator && ./install.sh --full
```

## How It Works

```
┌─────────────────────────────────────────────────────────┐
│  You press Ctrl+Shift+Space and speak                   │
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
│  ⌨️ Text is typed into your focused application         │
└─────────────────────────────────────────────────────────┘
```

## Requirements

- **GNOME 45+** (Ubuntu 24.04+, Fedora 40+, Arch, etc.)
- **PipeWire** (default on modern distros)
- **Python 3.10+**

<details>
<summary><strong>📦 Install dependencies if needed</strong></summary>

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

### Change Keyboard Shortcut

```bash
# Change to Super+D
gsettings --schemadir ~/.local/share/gnome-shell/extensions/dictator@lebi/schemas \
  set org.gnome.shell.extensions.dictator shortcut "['<Super>d']"
```

### Available Settings

| Setting | Default | Options |
|---------|---------|---------|
| `shortcut` | `Ctrl+Shift+Space` | Any key combo |
| `model` | `base.en` | `tiny.en`, `base.en`, `small.en` |
| `show-overlay` | `true` | `true`, `false` |
| `show-notifications` | `true` | `true`, `false` |

## Troubleshooting

<details>
<summary><strong>Shortcut not working</strong></summary>

```bash
# Reload extension
gnome-extensions disable dictator@lebi && gnome-extensions enable dictator@lebi

# On Wayland, log out and back in
```

</details>

<details>
<summary><strong>"No speech detected"</strong></summary>

Test your microphone:
```bash
pw-record --format s16 --rate 16000 --channels 1 test.wav
# Speak, then Ctrl+C — file should be > 1KB
```

</details>

<details>
<summary><strong>Permission denied</strong></summary>

```bash
# Run uinput setup
sudo ./scripts/setup_uinput.sh

# Log out and back in
# Verify with:
groups | grep uinput
```

</details>

<details>
<summary><strong>Check logs</strong></summary>

```bash
journalctl --user | grep -i dictator | tail -30
```

</details>

## Uninstall

```bash
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
