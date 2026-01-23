"""Global hotkey listener."""

import threading
from typing import Callable, Optional


class HotkeyListener:
    """Listens for global keyboard shortcuts."""

    def __init__(self, callback: Callable[[], None]):
        """Initialize hotkey listener.

        Args:
            callback: Function to call when hotkey is pressed.
        """
        self.callback = callback
        self._listener = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

        # Track modifier state
        self._ctrl_pressed = False
        self._shift_pressed = False

    def start(self):
        """Start listening for hotkeys."""
        try:
            from pynput import keyboard

            def on_press(key):
                try:
                    # Track modifiers
                    if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
                        self._ctrl_pressed = True
                    elif key == keyboard.Key.shift_l or key == keyboard.Key.shift_r:
                        self._shift_pressed = True
                    elif key == keyboard.Key.space:
                        # Check if Ctrl+Shift+Space
                        if self._ctrl_pressed and self._shift_pressed:
                            self.callback()
                except Exception as e:
                    print(f"Hotkey press error: {e}")

            def on_release(key):
                try:
                    if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
                        self._ctrl_pressed = False
                    elif key == keyboard.Key.shift_l or key == keyboard.Key.shift_r:
                        self._shift_pressed = False
                except Exception:
                    pass

            self._listener = keyboard.Listener(on_press=on_press, on_release=on_release)
            self._listener.start()
            self._running = True
            print("Hotkey listener started: Ctrl+Shift+Space")

        except ImportError:
            print("Note: pynput not installed - global hotkey disabled")
            print("  Install with: pip install pynput --break-system-packages")
            print("  Or use pipx: pipx install pynput")
            print("  For now, just click the mic button!")
            self._running = False
        except Exception as e:
            print(f"Failed to start hotkey listener: {e}")
            self._running = False

    def stop(self):
        """Stop listening for hotkeys."""
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None
        self._running = False

    @property
    def is_running(self) -> bool:
        """Check if listener is running."""
        return self._running
