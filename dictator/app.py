"""Main Dictator application."""

import asyncio
import threading
import sys
from pathlib import Path

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Gio

from .window import DictatorWindow
from .recorder import Recorder
from .transcriber import Transcriber
from .model_manager import ModelManager
from .clipboard import ClipboardManager
from .hotkey import HotkeyListener


class DictatorApp(Gtk.Application):
    """Main Dictator application."""

    def __init__(self):
        super().__init__(
            application_id="org.lebi.Dictator",
            flags=Gio.ApplicationFlags.FLAGS_NONE
        )

        self.window = None
        self.recorder = Recorder()
        self.model_manager = ModelManager()
        self.transcriber = Transcriber(model_manager=self.model_manager)
        self.clipboard = ClipboardManager()
        self.hotkey_listener = None

        self._is_recording = False
        self._async_loop = None
        self._async_thread = None

    def do_activate(self):
        """Called when the application is activated."""
        if not self.window:
            self.window = DictatorWindow(self, self._on_toggle)

        # Start async event loop in background thread
        self._start_async_loop()

        # Start hotkey listener
        self._start_hotkey_listener()

        # Check dependencies
        self._check_dependencies()

        # Show the window
        self.window.show_popup()

        print("Dictator started!")
        print("  - Click the mic button to record")
        print("  - Click again to stop and transcribe")
        print("  - Press ESC to cancel and hide")

    def _start_async_loop(self):
        """Start asyncio event loop in background thread."""
        def run_loop():
            self._async_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._async_loop)
            self._async_loop.run_forever()

        self._async_thread = threading.Thread(target=run_loop, daemon=True)
        self._async_thread.start()

    def _start_hotkey_listener(self):
        """Start the global hotkey listener."""
        def on_hotkey():
            # Run toggle in main GTK thread
            GLib.idle_add(self._on_toggle)

        self.hotkey_listener = HotkeyListener(on_hotkey)
        self.hotkey_listener.start()

    def _check_dependencies(self):
        """Check if all dependencies are available."""
        # Check whisper
        if not self.transcriber.is_available():
            print("WARNING: whisper.cpp not found!")
            print("  Install: see https://github.com/ggerganov/whisper.cpp")

        # Check model
        if not self.model_manager.is_model_available():
            print("INFO: Whisper model will be downloaded on first use")

        # Check wtype
        if not self.clipboard.is_wtype_available():
            print("WARNING: wtype not found - auto-paste disabled")
            print("  Install: sudo apt install wtype")

    def _on_toggle(self):
        """Toggle recording state."""
        if self._is_recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        """Start recording audio."""
        if self._is_recording:
            return

        # Show window
        self.window.show_popup()
        self.window.set_state(DictatorWindow.STATE_RECORDING)

        # Ensure model exists (download if needed)
        if not self.model_manager.is_model_available():
            self.window.status_label.set_text("Downloading model...")
            # Download in background
            future = asyncio.run_coroutine_threadsafe(
                self._ensure_model_and_record(),
                self._async_loop
            )
        else:
            # Start recording directly
            future = asyncio.run_coroutine_threadsafe(
                self._do_start_recording(),
                self._async_loop
            )

    async def _ensure_model_and_record(self):
        """Ensure model is downloaded, then start recording."""
        try:
            await self.model_manager.ensure_model()
            GLib.idle_add(self._update_after_model_download)
        except Exception as e:
            GLib.idle_add(self._show_error, str(e))

    def _update_after_model_download(self):
        """Called after model is downloaded."""
        # Now start recording
        future = asyncio.run_coroutine_threadsafe(
            self._do_start_recording(),
            self._async_loop
        )

    async def _do_start_recording(self):
        """Actually start recording."""
        try:
            await self.recorder.start()
            self._is_recording = True
            GLib.idle_add(self._update_recording_started)
        except Exception as e:
            GLib.idle_add(self._show_error, str(e))

    def _update_recording_started(self):
        """Update UI after recording started."""
        self.window.set_state(DictatorWindow.STATE_RECORDING)

    def _stop_recording(self):
        """Stop recording and transcribe."""
        if not self._is_recording:
            return

        self._is_recording = False
        self.window.set_state(DictatorWindow.STATE_TRANSCRIBING)

        # Stop and transcribe in background
        future = asyncio.run_coroutine_threadsafe(
            self._do_stop_and_transcribe(),
            self._async_loop
        )

    async def _do_stop_and_transcribe(self):
        """Stop recording and run transcription."""
        try:
            # Stop recording
            audio_file = await self.recorder.stop()

            # Transcribe
            text = await self.transcriber.transcribe(audio_file)

            # Clean up
            self.recorder.cleanup()

            # Handle result in main thread
            GLib.idle_add(self._handle_transcription_result, text)

        except Exception as e:
            GLib.idle_add(self._show_error, str(e))

    def _handle_transcription_result(self, text: str):
        """Handle successful transcription."""
        if text:
            # Copy to clipboard and auto-paste
            display = self.window.get_display()
            self.clipboard.copy_and_paste(text, display)
            self.window.show_result(text, success=True)
        else:
            self.window.show_result("", success=True)  # No speech detected

    def _show_error(self, error: str):
        """Show error message."""
        print(f"Error: {error}")
        self.window.set_state(DictatorWindow.STATE_IDLE)
        self.window.show_result(error, success=False)

    def do_shutdown(self):
        """Called when application is shutting down."""
        # Stop hotkey listener
        if self.hotkey_listener:
            self.hotkey_listener.stop()

        # Stop async loop
        if self._async_loop:
            self._async_loop.call_soon_threadsafe(self._async_loop.stop)

        Gtk.Application.do_shutdown(self)


def main():
    """Main entry point."""
    app = DictatorApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    main()
