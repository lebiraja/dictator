"""Dictator D-Bus Service - Main entry point."""

import asyncio
import logging
import os
import signal
import sys
from enum import Enum
from pathlib import Path
from typing import Optional

from dbus_next.aio import MessageBus
from dbus_next.service import ServiceInterface, method, signal as dbus_signal, dbus_property
from dbus_next.constants import PropertyAccess
from dbus_next import Variant, BusType

from recorder import Recorder
from transcriber import Transcriber
from model_manager import ModelManager, DEFAULT_MODEL


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("dictator")


class State(str, Enum):
    """Dictation service states."""
    IDLE = "idle"
    RECORDING = "recording"
    TRANSCRIBING = "transcribing"
    DOWNLOADING = "downloading"
    ERROR = "error"


class DictatorService(ServiceInterface):
    """D-Bus service interface for Dictator."""

    def __init__(self):
        super().__init__("org.lebi.Dictator")
        self._state = State.IDLE
        self._last_error = ""
        self._last_transcription = ""

        self.recorder = Recorder()
        self.model_manager = ModelManager()
        self.transcriber = Transcriber(model_manager=self.model_manager)

    @dbus_property(access=PropertyAccess.READ)
    def State(self) -> "s":
        """Current service state."""
        return self._state.value

    @dbus_property(access=PropertyAccess.READ)
    def LastError(self) -> "s":
        """Last error message, if any."""
        return self._last_error

    @dbus_property(access=PropertyAccess.READ)
    def LastTranscription(self) -> "s":
        """Last transcription result."""
        return self._last_transcription

    @dbus_property(access=PropertyAccess.READ)
    def IsModelAvailable(self) -> "b":
        """Check if the Whisper model is downloaded."""
        return self.model_manager.is_model_available()

    @dbus_property(access=PropertyAccess.READ)
    def IsWhisperAvailable(self) -> "b":
        """Check if whisper.cpp binary is available."""
        return self.transcriber.is_available()

    def _set_state(self, state: State) -> None:
        """Update state and emit signal."""
        if self._state != state:
            self._state = state
            self.StateChanged(state.value)
            logger.info(f"State changed to: {state.value}")

    @dbus_signal()
    def StateChanged(self, state: "s") -> "s":
        """Emitted when the service state changes."""
        return state

    @dbus_signal()
    def TranscriptionReady(self, text: "s") -> "s":
        """Emitted when transcription is complete."""
        return text

    @dbus_signal()
    def Error(self, message: "s") -> "s":
        """Emitted when an error occurs."""
        return message

    @dbus_signal()
    def DownloadProgress(self, downloaded: "x", total: "x") -> "xx":
        """Emitted during model download."""
        return [downloaded, total]

    @method()
    async def StartRecording(self) -> "b":
        """Start audio recording.

        Returns:
            True if recording started successfully.
        """
        if self._state != State.IDLE:
            self._last_error = f"Cannot start: currently {self._state.value}"
            self.Error(self._last_error)
            return False

        try:
            # Check if model is available
            if not self.model_manager.is_model_available():
                logger.info("Model not found, downloading...")
                self._set_state(State.DOWNLOADING)
                try:
                    await self.model_manager.ensure_model(
                        progress_callback=self._on_download_progress
                    )
                except Exception as e:
                    self._last_error = str(e)
                    self._set_state(State.ERROR)
                    self.Error(self._last_error)
                    return False

            # Check whisper.cpp
            if not self.transcriber.is_available():
                self._last_error = "whisper.cpp not found in PATH"
                self._set_state(State.ERROR)
                self.Error(self._last_error)
                return False

            # Start recording
            audio_path = await self.recorder.start()
            logger.info(f"Recording to: {audio_path}")
            self._set_state(State.RECORDING)
            return True

        except Exception as e:
            self._last_error = str(e)
            logger.error(f"Failed to start recording: {e}")
            self._set_state(State.ERROR)
            self.Error(self._last_error)
            return False

    def _on_download_progress(self, downloaded: int, total: int) -> None:
        """Callback for download progress."""
        self.DownloadProgress(downloaded, total)

    @method()
    async def StopRecording(self) -> "s":
        """Stop recording and transcribe.

        Returns:
            Transcribed text, or empty string on error.
        """
        if self._state != State.RECORDING:
            self._last_error = f"Cannot stop: not recording (state={self._state.value})"
            self.Error(self._last_error)
            return ""

        try:
            # Stop recording
            audio_path = await self.recorder.stop()
            logger.info(f"Recording stopped: {audio_path}")

            # Transcribe
            self._set_state(State.TRANSCRIBING)
            text = await self.transcriber.transcribe(audio_path)

            # Clean up audio file
            self.recorder.cleanup()

            # Store and emit result
            self._last_transcription = text
            self._set_state(State.IDLE)
            self.TranscriptionReady(text)
            logger.info(f"Transcription complete: {text[:50]}...")

            return text

        except Exception as e:
            self._last_error = str(e)
            logger.error(f"Transcription failed: {e}")
            self.recorder.cleanup()
            self._set_state(State.ERROR)
            self.Error(self._last_error)
            return ""

    @method()
    async def Cancel(self) -> "b":
        """Cancel current operation.

        Returns:
            True if cancelled successfully.
        """
        try:
            if self._state == State.RECORDING:
                await self.recorder.cancel()
            self._set_state(State.IDLE)
            logger.info("Operation cancelled")
            return True
        except Exception as e:
            self._last_error = str(e)
            logger.error(f"Cancel failed: {e}")
            return False

    @method()
    def GetState(self) -> "s":
        """Get current state.

        Returns:
            Current state string.
        """
        return self._state.value

    @method()
    async def Toggle(self) -> "s":
        """Toggle between recording and idle.

        Convenient method for keyboard shortcut.

        Returns:
            New state after toggle.
        """
        if self._state == State.IDLE:
            # Call the internal logic directly, not the D-Bus method
            await self._start_recording_internal()
        elif self._state == State.RECORDING:
            await self._stop_recording_internal()
        # If transcribing or downloading, do nothing
        return self._state.value

    @method()
    async def EnsureModel(self) -> "b":
        """Ensure the Whisper model is downloaded.

        Returns:
            True if model is available.
        """
        if self.model_manager.is_model_available():
            return True

        try:
            self._set_state(State.DOWNLOADING)
            await self.model_manager.ensure_model(
                progress_callback=self._on_download_progress
            )
            self._set_state(State.IDLE)
            return True
        except Exception as e:
            self._last_error = str(e)
            self._set_state(State.ERROR)
            self.Error(self._last_error)
            return False

    @method()
    def GetDiagnostics(self) -> "a{sv}":
        """Get diagnostic information.

        Returns:
            Dictionary of diagnostic info.
        """
        return {
            "state": Variant("s", self._state.value),
            "model_available": Variant("b", self.model_manager.is_model_available()),
            "whisper_available": Variant("b", self.transcriber.is_available()),
            "whisper_binary": Variant("s", self.transcriber.find_whisper_binary() or ""),
            "model_path": Variant("s", str(self.model_manager.get_model_path())),
            "last_error": Variant("s", self._last_error),
        }


async def main():
    """Main entry point."""
    logger.info("Starting Dictator D-Bus service...")

    # Connect to session bus
    bus = await MessageBus(bus_type=BusType.SESSION).connect()

    # Create and export service
    service = DictatorService()
    bus.export("/org/lebi/Dictator", service)

    # Request the well-known name
    await bus.request_name("org.lebi.Dictator")
    logger.info("Service registered as org.lebi.Dictator")

    # Log diagnostic info
    logger.info(f"Whisper available: {service.transcriber.is_available()}")
    logger.info(f"Model available: {service.model_manager.is_model_available()}")
    if service.transcriber.is_available():
        logger.info(f"Whisper binary: {service.transcriber.find_whisper_binary()}")

    # Handle signals for graceful shutdown
    loop = asyncio.get_event_loop()

    def handle_signal():
        logger.info("Received shutdown signal")
        loop.stop()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, handle_signal)

    # Run forever
    try:
        await bus.wait_for_disconnect()
    except asyncio.CancelledError:
        pass
    finally:
        logger.info("Dictator service stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
