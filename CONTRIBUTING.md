# Contributing to Dictator

Thank you for your interest in contributing to Dictator! This document provides guidelines for contributing.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR-USERNAME/dictator.git
   cd dictator
   ```
3. **Set up development environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install dbus-next evdev faster-whisper
   ```

## Development Workflow

### Running from Source

```bash
# Terminal 1: Run the service
source venv/bin/activate
python service/dictator_service.py

# Terminal 2: Test via D-Bus
dbus-send --session --print-reply --dest=org.lebi.Dictator \
  /org/lebi/Dictator org.lebi.Dictator.Toggle
```

### Installing the Extension for Testing

```bash
# Copy extension to local extensions directory
cp -r extension ~/.local/share/gnome-shell/extensions/dictator@lebi

# Compile schemas
glib-compile-schemas ~/.local/share/gnome-shell/extensions/dictator@lebi/schemas/

# Enable extension
gnome-extensions enable dictator@lebi
```

### Viewing Logs

```bash
# Service logs
journalctl --user | grep -i dictator

# GNOME Shell logs (for extension)
journalctl -f /usr/bin/gnome-shell
```

## Code Style

### Python (Service)

- Follow PEP 8
- Use type hints
- Use async/await for I/O operations
- Keep functions focused and small

### JavaScript (Extension)

- Follow GNOME Shell extension conventions
- Use ES6+ features (const, let, arrow functions, async/await)
- Add JSDoc comments for public methods

## Submitting Changes

1. **Create a feature branch**:
   ```bash
   git checkout -b feature/my-new-feature
   ```

2. **Make your changes** with clear, atomic commits

3. **Test thoroughly**:
   - Test on both Wayland and X11 if possible
   - Test shortcut registration after reboot
   - Test error scenarios (no microphone, permission denied, etc.)

4. **Push and create a Pull Request**:
   ```bash
   git push origin feature/my-new-feature
   ```

## Pull Request Guidelines

- **Title**: Clear, concise description of the change
- **Description**: Explain what and why, not just how
- **Testing**: Describe how you tested the changes
- **Screenshots**: Include for UI changes

## Reporting Issues

When reporting issues, please include:

1. **System info**: GNOME version, distro, Wayland/X11
2. **Steps to reproduce**
3. **Expected vs actual behavior**
4. **Logs**: `journalctl --user | grep -i dictator`

## Feature Requests

Feature requests are welcome! Please:

1. Check existing issues first
2. Describe the use case
3. Suggest implementation approach if you have one

## Project Structure

```
dictator/
├── extension/           # GNOME Shell extension (JavaScript)
│   ├── extension.js     # Main extension code
│   ├── metadata.json    # Extension metadata
│   ├── stylesheet.css   # UI styling
│   └── schemas/         # GSettings schema
├── service/             # Python D-Bus service
│   ├── dictator_service.py  # Main entry point
│   ├── recorder.py      # Audio recording
│   ├── transcriber.py   # Whisper transcription
│   └── typer.py         # Virtual keyboard
├── scripts/             # Installation scripts
├── systemd/             # Systemd service file
└── assets/              # Icons and images
```

## Areas for Contribution

### Good First Issues

- Improve error messages
- Add more keyboard layouts to typer.py
- Add unit tests
- Improve documentation

### Larger Projects

- Preferences UI (prefs.js)
- Multi-language support
- Voice commands
- Dictation history

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help newcomers get started

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
