"""Dictator D-Bus Service - Main entry point."""

import asyncio
import logging
import signal
from enum import Enum
from dbus_next.aio import MessageBus
from dbus_next.service import ServiceInterface, method, signal as dbus_signal, dbus_property
from dbus_next.constants import PropertyAccess
from dbus_next import Variant, BusType

from recorder import Recorder
from transcriber import Transcriber
from typer import Typer

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
    TYPING = "typing"
    ERROR = "error"


class DictatorService(ServiceInterface):
    """D-Bus service interface for Dictator."""

    def __init__(self):
        super().__init__("org.lebi.Dictator")
        self._state = State.IDLE
        self._last_error = ""
        self._last_transcription = ""

        self.recorder = Recorder()
        self.transcriber = Transcriber()
        self.typer = Typer()

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

    @method()
    async def StopRecording(self) -> "s":
        """Stop recording, transcribe, and type.

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
            # Run blocking transcription in executor to avoid blocking the event loop
            loop = asyncio.get_running_loop()
            text = await loop.run_in_executor(None, self.transcriber.transcribe, str(audio_path))

            # Clean up audio file
            self.recorder.cleanup()

            if text:
                # Type the text
                self._set_state(State.TYPING)
                logger.info(f"Typing text: '{text}'")
                await loop.run_in_executor(None, self.typer.type_text, text)

            # Store and emit result
            self._last_transcription = text
            self._set_state(State.IDLE)
            self.TranscriptionReady(text)

            return text

        except Exception as e:
            self._last_error = str(e)
            logger.error(f"Process failed: {e}")
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
            await self.StartRecording()
        elif self._state == State.RECORDING:
            await self.StopRecording()
        # If transcribing or typing, do nothing
        return self._state.value


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

    # Handle signals for graceful shutdown
    loop = asyncio.get_running_loop()

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
        if service.typer:
            service.typer.close()
        logger.info("Dictator service stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
