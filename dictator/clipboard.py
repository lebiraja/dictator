"""Clipboard and auto-paste functionality."""

import subprocess
import shutil
from typing import Optional

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gtk, Gdk, GLib


class ClipboardManager:
    """Handles clipboard operations and auto-paste."""

    def __init__(self):
        self._wtype_available: Optional[bool] = None

    def is_wtype_available(self) -> bool:
        """Check if wtype is available for auto-paste."""
        if self._wtype_available is None:
            self._wtype_available = shutil.which("wtype") is not None
        return self._wtype_available

    def copy_to_clipboard(self, text: str, display: Gdk.Display) -> bool:
        """Copy text to clipboard.

        Args:
            text: Text to copy.
            display: Gdk display for clipboard access.

        Returns:
            True if successful.
        """
        try:
            clipboard = display.get_clipboard()
            clipboard.set(text)
            return True
        except Exception as e:
            print(f"Clipboard error: {e}")
            return False

    def auto_paste(self) -> bool:
        """Simulate Ctrl+V to paste clipboard content.

        Returns:
            True if paste was triggered.
        """
        if not self.is_wtype_available():
            print("wtype not available - install with: sudo apt install wtype")
            return False

        try:
            # Small delay to ensure clipboard is ready
            # wtype -M ctrl v -m ctrl = hold ctrl, press v, release ctrl
            subprocess.run(
                ["wtype", "-M", "ctrl", "v", "-m", "ctrl"],
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"wtype error: {e}")
            return False
        except Exception as e:
            print(f"Auto-paste error: {e}")
            return False

    def copy_and_paste(self, text: str, display: Gdk.Display) -> bool:
        """Copy text to clipboard and auto-paste it.

        Args:
            text: Text to copy and paste.
            display: Gdk display for clipboard access.

        Returns:
            True if successful.
        """
        if not text:
            return False

        # Copy to clipboard
        if not self.copy_to_clipboard(text, display):
            return False

        # Small delay before paste to ensure clipboard is set
        GLib.timeout_add(100, self._delayed_paste)
        return True

    def _delayed_paste(self) -> bool:
        """Delayed paste callback."""
        self.auto_paste()
        return False  # Don't repeat
