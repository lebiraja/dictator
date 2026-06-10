"""Text output via /dev/uinput (kernel-level, works on Wayland and X11).

Two modes:
  - "paste" (default): put the text on the clipboard (wl-copy / xclip),
    inject Ctrl+V, then restore the previous clipboard. Instant for long
    text and independent of keyboard layout.
  - "type": inject each character as key events using a complete US-layout
    map. Fallback for apps that block paste (note: terminals usually want
    Ctrl+Shift+V, so paste mode may not suit them either).

Errors are raised, never swallowed — the service surfaces them to the UI.
"""

import logging
import os
import shutil
import subprocess
import threading
import time

from evdev import UInput
from evdev import ecodes as ec

logger = logging.getLogger("dictator.typer")

KEY_DELAY = 0.005  # seconds between typed characters
CLIPBOARD_TIMEOUT = 3  # seconds for clipboard tool calls
PASTE_SETTLE = 0.25  # let the focused app consume the paste before restore


class TyperError(RuntimeError):
    """Raised when text output fails (permissions, missing tools, ...)."""


class TypingCancelled(Exception):
    """Raised when type-mode output is aborted via the cancel event."""


def _build_keymap() -> dict[str, tuple[int, bool]]:
    """Map every printable ASCII char to (keycode, needs_shift) — US layout."""
    keymap: dict[str, tuple[int, bool]] = {
        " ": (ec.KEY_SPACE, False),
        "\n": (ec.KEY_ENTER, False),
        "\t": (ec.KEY_TAB, False),
    }
    for char in "abcdefghijklmnopqrstuvwxyz":
        code = getattr(ec, f"KEY_{char.upper()}")
        keymap[char] = (code, False)
        keymap[char.upper()] = (code, True)
    for char in "0123456789":
        keymap[char] = (getattr(ec, f"KEY_{char}"), False)

    unshifted = {
        "-": ec.KEY_MINUS, "=": ec.KEY_EQUAL,
        "[": ec.KEY_LEFTBRACE, "]": ec.KEY_RIGHTBRACE,
        "\\": ec.KEY_BACKSLASH, ";": ec.KEY_SEMICOLON,
        "'": ec.KEY_APOSTROPHE, "`": ec.KEY_GRAVE,
        ",": ec.KEY_COMMA, ".": ec.KEY_DOT, "/": ec.KEY_SLASH,
    }
    shifted = {
        "!": ec.KEY_1, "@": ec.KEY_2, "#": ec.KEY_3, "$": ec.KEY_4,
        "%": ec.KEY_5, "^": ec.KEY_6, "&": ec.KEY_7, "*": ec.KEY_8,
        "(": ec.KEY_9, ")": ec.KEY_0,
        "_": ec.KEY_MINUS, "+": ec.KEY_EQUAL,
        "{": ec.KEY_LEFTBRACE, "}": ec.KEY_RIGHTBRACE,
        "|": ec.KEY_BACKSLASH, ":": ec.KEY_SEMICOLON,
        '"': ec.KEY_APOSTROPHE, "~": ec.KEY_GRAVE,
        "<": ec.KEY_COMMA, ">": ec.KEY_DOT, "?": ec.KEY_SLASH,
    }
    for char, code in unshifted.items():
        keymap[char] = (code, False)
    for char, code in shifted.items():
        keymap[char] = (code, True)
    return keymap


class Typer:
    """Outputs text into the focused application."""

    def __init__(self, output_mode: str = "paste") -> None:
        self.output_mode = output_mode  # "paste" or "type"
        self._uinput: UInput | None = None
        self._keymap = _build_keymap()
        self._is_wayland = bool(os.environ.get("WAYLAND_DISPLAY"))

    # ------------------------------------------------------------------ uinput

    def _ensure_uinput(self) -> UInput:
        if self._uinput is None:
            keycodes = {code for code, _ in self._keymap.values()}
            keycodes.update({ec.KEY_LEFTSHIFT, ec.KEY_LEFTCTRL, ec.KEY_V})
            try:
                self._uinput = UInput(
                    {ec.EV_KEY: sorted(keycodes)}, name="Dictator Virtual Keyboard"
                )
            except PermissionError:
                raise TyperError(
                    "No permission for /dev/uinput. Add yourself to the 'uinput' "
                    "group (sudo usermod -aG uinput $USER) and log back in."
                )
            except Exception as e:
                raise TyperError(f"Could not create virtual keyboard: {e}")
            logger.info("Virtual keyboard initialized")
            # Give the compositor a moment to pick up the new input device.
            time.sleep(0.2)
        return self._uinput

    def _tap(self, ui: UInput, keycode: int, shift: bool = False, ctrl: bool = False) -> None:
        if shift:
            ui.write(ec.EV_KEY, ec.KEY_LEFTSHIFT, 1)
        if ctrl:
            ui.write(ec.EV_KEY, ec.KEY_LEFTCTRL, 1)
        ui.write(ec.EV_KEY, keycode, 1)
        ui.syn()
        ui.write(ec.EV_KEY, keycode, 0)
        if ctrl:
            ui.write(ec.EV_KEY, ec.KEY_LEFTCTRL, 0)
        if shift:
            ui.write(ec.EV_KEY, ec.KEY_LEFTSHIFT, 0)
        ui.syn()

    # --------------------------------------------------------------- clipboard

    def _clipboard_tools(self) -> tuple[list, list] | None:
        """(copy_cmd, paste_cmd) for this session, or None if unavailable."""
        if self._is_wayland and shutil.which("wl-copy"):
            return (["wl-copy"], ["wl-paste", "--no-newline"])
        if not self._is_wayland and shutil.which("xclip"):
            return (
                ["xclip", "-selection", "clipboard"],
                ["xclip", "-selection", "clipboard", "-o"],
            )
        return None

    @staticmethod
    def _read_clipboard(paste_cmd: list) -> bytes | None:
        try:
            result = subprocess.run(
                paste_cmd, capture_output=True, timeout=CLIPBOARD_TIMEOUT
            )
            return result.stdout if result.returncode == 0 else None
        except Exception:
            return None

    @staticmethod
    def _write_clipboard(copy_cmd: list, data: bytes) -> None:
        subprocess.run(copy_cmd, input=data, timeout=CLIPBOARD_TIMEOUT, check=True)

    # ------------------------------------------------------------------ output

    def type_text(self, text: str, cancel_event: threading.Event | None = None) -> None:
        """Output text into the focused app. Blocking; run in executor.

        Raises:
            TyperError: on uinput/clipboard failure.
            TypingCancelled: if cancel_event is set during type-mode output.
        """
        if not text:
            return

        if self.output_mode != "type":
            tools = self._clipboard_tools()
            if tools is not None:
                self._paste(text, *tools)
                return
            logger.warning("No clipboard tool (wl-copy/xclip); falling back to typing")

        self._type_chars(text, cancel_event)

    def _paste(self, text: str, copy_cmd: list, paste_cmd: list) -> None:
        ui = self._ensure_uinput()  # fail on permissions before touching clipboard
        previous = self._read_clipboard(paste_cmd)
        try:
            self._write_clipboard(copy_cmd, text.encode())
        except Exception as e:
            raise TyperError(f"Could not set clipboard: {e}")

        time.sleep(0.05)  # let the clipboard owner settle
        self._tap(ui, ec.KEY_V, ctrl=True)
        logger.info("Pasted %d chars", len(text))

        time.sleep(PASTE_SETTLE)
        if previous is not None:
            try:
                self._write_clipboard(copy_cmd, previous)
            except Exception:
                logger.warning("Could not restore previous clipboard")

    def _type_chars(self, text: str, cancel_event: threading.Event | None) -> None:
        ui = self._ensure_uinput()
        skipped = set()
        for char in text:
            if cancel_event is not None and cancel_event.is_set():
                raise TypingCancelled()
            mapping = self._keymap.get(char)
            if mapping is None:
                skipped.add(char)
                continue
            keycode, shift = mapping
            self._tap(ui, keycode, shift=shift)
            time.sleep(KEY_DELAY)
        if skipped:
            logger.warning("Skipped unsupported characters: %r", "".join(sorted(skipped)))
        logger.info("Typed %d chars", len(text))

    def close(self) -> None:
        if self._uinput is not None:
            self._uinput.close()
            self._uinput = None
