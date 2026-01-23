import time
import logging
from typing import Optional
from evdev import UInput, ecodes as e

logger = logging.getLogger("dictator.typer")

class Typer:
    """
    Simulates keyboard input using /dev/uinput via python-evdev.
    This works on both Wayland and X11 by injecting events at the kernel level.
    """
    def __init__(self):
        self._uinput: Optional[UInput] = None

        # Map common characters to key codes
        # This is a basic mapping; for a full solution we might need a more comprehensive map
        # or a library that handles layout, but evdev operates on keycodes, not characters.
        # We'll implement a basic ASCII mapping for now.
        self._char_map = {
            ' ': e.KEY_SPACE,
            '\n': e.KEY_ENTER,
            '.': e.KEY_DOT,
            ',': e.KEY_COMMA,
            '?': e.KEY_SLASH, # Shift+Slash usually
            '!': e.KEY_1,     # Shift+1
            '-': e.KEY_MINUS,
            '_': e.KEY_MINUS, # Shift+Minus
            "'": e.KEY_APOSTROPHE,
            '"': e.KEY_APOSTROPHE, # Shift+Apostrophe
            # Numbers
            '0': e.KEY_0, '1': e.KEY_1, '2': e.KEY_2, '3': e.KEY_3,
            '4': e.KEY_4, '5': e.KEY_5, '6': e.KEY_6, '7': e.KEY_7,
            '8': e.KEY_8, '9': e.KEY_9,
        }

        # Add lowercase letters
        for i, char in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self._char_map[char] = getattr(e, f'KEY_{char.upper()}')

        # Add uppercase letters (same keycodes, but we'll handle Shift separately)
        for i, char in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self._char_map[char] = getattr(e, f'KEY_{char}')

    def _ensure_uinput(self):
        """Initialize UInput device if not already done."""
        if self._uinput is None:
            try:
                cap = {
                    e.EV_KEY: [e.KEY_LEFTSHIFT] + list(self._char_map.values())
                }
                self._uinput = UInput(cap, name="Dictator Virtual Keyboard")
                logger.info("Initialized virtual keyboard")
            except PermissionError:
                logger.error("Permission denied accessing /dev/uinput. Ensure udev rules are set.")
                raise
            except Exception as e:
                logger.error(f"Failed to initialize UInput: {e}")
                raise

    def type_text(self, text: str):
        """Type the given text string."""
        if not text:
            return

        try:
            self._ensure_uinput()

            # Small delay to ensure the device is ready and focus is stable
            time.sleep(0.1)

            for char in text:
                if char in self._char_map:
                    keycode = self._char_map[char]
                    is_upper = char.isupper() or char in '!@#$%^&*()_+{}|:"<>?'

                    # Special handling for some punctuation that requires shift on standard US layout
                    if char in '?!":_+{}|<>@#$%^&*()':
                        is_upper = True
                        if char == '?': keycode = e.KEY_SLASH
                        elif char == '!': keycode = e.KEY_1
                        elif char == '@': keycode = e.KEY_2
                        elif char == '#': keycode = e.KEY_3
                        elif char == '$': keycode = e.KEY_4
                        elif char == '%': keycode = e.KEY_5
                        elif char == '^': keycode = e.KEY_6
                        elif char == '&': keycode = e.KEY_7
                        elif char == '*': keycode = e.KEY_8
                        elif char == '(': keycode = e.KEY_9
                        elif char == ')': keycode = e.KEY_0
                        elif char == '_': keycode = e.KEY_MINUS
                        elif char == '+': keycode = e.KEY_EQUAL
                        elif char == '{': keycode = e.KEY_LEFTBRACE
                        elif char == '}': keycode = e.KEY_RIGHTBRACE
                        elif char == '|': keycode = e.KEY_BACKSLASH
                        elif char == ':': keycode = e.KEY_SEMICOLON
                        elif char == '"': keycode = e.KEY_APOSTROPHE
                        elif char == '<': keycode = e.KEY_COMMA
                        elif char == '>': keycode = e.KEY_DOT

                    if is_upper:
                        self._uinput.write(e.EV_KEY, e.KEY_LEFTSHIFT, 1)
                        self._uinput.syn()

                    self._uinput.write(e.EV_KEY, keycode, 1) # Press
                    self._uinput.syn()
                    self._uinput.write(e.EV_KEY, keycode, 0) # Release
                    self._uinput.syn()

                    if is_upper:
                        self._uinput.write(e.EV_KEY, e.KEY_LEFTSHIFT, 0)
                        self._uinput.syn()
                else:
                    logger.warning(f"Ignoring unsupported character: {char}")

            # Add a trailing space automatically? The user might want this.
            # For now, we type exactly what is given.

        except Exception as e:
            logger.error(f"Error typing text: {e}")
            # Try to re-initialize next time
            if self._uinput:
                self._uinput.close()
                self._uinput = None

    def close(self):
        """Release resources."""
        if self._uinput:
            self._uinput.close()
            self._uinput = None
