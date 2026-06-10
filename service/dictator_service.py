"""Dictator D-Bus Service - Main entry point.

State machine:  idle -> recording -> transcribing -> typing -> idle
Extra states:   loading / downloading (model preload), error (recoverable —
                starting a recording from `error` is always allowed).

All transitions go through an asyncio.Lock so concurrent D-Bus calls
(e.g. rapid shortcut presses) can never double-start the recorder.
"""

import asyncio
import logging
import signal
import threading
from enum import Enum

from dbus_next import BusType
from dbus_next.aio import MessageBus
from dbus_next.constants import PropertyAccess
from dbus_next.service import ServiceInterface, dbus_property, method
from dbus_next.service import signal as dbus_signal
from recorder import Recorder, RecorderError
from transcriber import Transcriber, TranscriptionCancelled
from typer import Typer, TypingCancelled

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
    LOADING = "loading"
    DOWNLOADING = "downloading"
    ERROR = "error"


# States from which a new recording may begin. Recording during model
# load/download is allowed — transcription simply waits for the model.
STARTABLE = (State.IDLE, State.ERROR, State.LOADING, State.DOWNLOADING)


class DictatorService(ServiceInterface):
    """D-Bus service interface for Dictator."""

    def __init__(self):
        super().__init__("org.lebi.Dictator")
        self._state = State.IDLE
        self._last_error = ""
        self._last_transcription = ""
        self._lock = asyncio.Lock()
        self._cancel_event = threading.Event()

        self.recorder = Recorder(on_level=self._on_audio_level, on_limit=self._on_limit)
        self.transcriber = Transcriber()
        self.typer = Typer()

    # ------------------------------------------------------------- properties

    @dbus_property(access=PropertyAccess.READ)
    def State(self) -> "s":
        return self._state.value

    @dbus_property(access=PropertyAccess.READ)
    def LastError(self) -> "s":
        return self._last_error

    @dbus_property(access=PropertyAccess.READ)
    def LastTranscription(self) -> "s":
        return self._last_transcription

    # ---------------------------------------------------------------- signals

    @dbus_signal()
    def StateChanged(self, state: "s") -> "s":
        return state

    @dbus_signal()
    def TranscriptionReady(self, text: "s") -> "s":
        return text

    @dbus_signal()
    def Error(self, message: "s") -> "s":
        return message

    @dbus_signal()
    def AudioLevel(self, level: "d") -> "d":
        return level

    # ---------------------------------------------------------------- helpers

    def _set_state(self, state: State) -> None:
        if self._state != state:
            self._state = state
            self.StateChanged(state.value)
            logger.info("State changed to: %s", state.value)

    def _emit_error(self, message: str) -> None:
        self._last_error = message
        logger.error(message)
        self.Error(message)

    def _on_audio_level(self, level: float) -> None:
        self.AudioLevel(level)

    async def _on_limit(self) -> None:
        """Recorder hit max duration — stop and transcribe what we have."""
        if self._state == State.RECORDING:
            logger.info("Auto-stopping at max duration")
            await self._do_stop_recording()

    # ------------------------------------------------------------- operations

    async def _do_start_recording(self) -> bool:
        async with self._lock:
            if self._state == State.RECORDING:
                return False  # benign double-call
            if self._state not in STARTABLE:
                self._emit_error(f"Busy: {self._state.value}")
                return False
            try:
                await self.recorder.start()
            except Exception as e:
                self._emit_error(str(e))
                self._set_state(State.ERROR)
                return False
            self._set_state(State.RECORDING)
            return True

    async def _do_stop_recording(self) -> str:
        async with self._lock:
            if self._state != State.RECORDING:
                self._emit_error(f"Cannot stop: not recording ({self._state.value})")
                return ""
            self._cancel_event.clear()
            self._set_state(State.TRANSCRIBING)

        loop = asyncio.get_running_loop()
        try:
            audio = await self.recorder.stop()
        except RecorderError as e:
            # Benign (too-short recording, mic vanished) — back to idle.
            self._emit_error(str(e))
            self._set_state(State.IDLE)
            return ""

        try:
            text = await loop.run_in_executor(
                None, self.transcriber.transcribe, audio, self._cancel_event
            )
            if text:
                self._set_state(State.TYPING)
                logger.info("Typing %d chars", len(text))
                await loop.run_in_executor(
                    None, self.typer.type_text, text, self._cancel_event
                )
            self._last_transcription = text
            self._set_state(State.IDLE)
            self.TranscriptionReady(text)
            return text

        except (TranscriptionCancelled, TypingCancelled):
            logger.info("Operation cancelled")
            self._set_state(State.IDLE)
            return ""
        except Exception as e:
            self._emit_error(str(e))
            self._set_state(State.ERROR)
            return ""

    async def preload_model(self) -> None:
        """Load (and download if needed) the Whisper model off the hot path."""
        if self.transcriber.is_loaded:
            return
        preload_state = (
            State.DOWNLOADING if self.transcriber.needs_download() else State.LOADING
        )
        if self._state == State.IDLE:
            self._set_state(preload_state)
        try:
            await asyncio.get_running_loop().run_in_executor(
                None, self.transcriber.load_model
            )
        except Exception as e:
            if self._state in (State.LOADING, State.DOWNLOADING):
                self._emit_error(f"Model load failed: {e}")
                self._set_state(State.ERROR)
            return
        # Don't stomp on a recording the user started while we loaded.
        if self._state in (State.LOADING, State.DOWNLOADING):
            self._set_state(State.IDLE)

    # -------------------------------------------------- plain (testable) API

    async def toggle(self) -> str:
        if self._state == State.RECORDING:
            await self._do_stop_recording()
        else:
            await self._do_start_recording()
        return self._state.value

    async def cancel(self) -> bool:
        try:
            if self._state == State.RECORDING:
                async with self._lock:
                    if self._state == State.RECORDING:
                        await self.recorder.cancel()
                        self._set_state(State.IDLE)
            elif self._state in (State.TRANSCRIBING, State.TYPING):
                self._cancel_event.set()  # picked up between segments/keys
            elif self._state == State.ERROR:
                self._set_state(State.IDLE)
            logger.info("Cancel requested (state=%s)", self._state.value)
            return True
        except Exception as e:
            self._emit_error(f"Cancel failed: {e}")
            return False

    def configure(self, options: dict) -> None:
        """Apply settings pushed by the extension (or any client)."""
        for key, variant in options.items():
            value = variant.value
            if key == "model" and isinstance(value, str):
                if self.transcriber.set_model(value):
                    asyncio.ensure_future(self.preload_model())
            elif key == "output-mode" and isinstance(value, str):
                # schema value 'clipboard' == paste mode
                self.typer.output_mode = "type" if value == "type" else "paste"
                logger.info("Output mode: %s", self.typer.output_mode)
            elif key == "max-duration":
                self.recorder.max_duration = float(value)
                logger.info("Max duration: %.0fs", self.recorder.max_duration)
            else:
                logger.warning("Ignoring unknown config key: %s", key)

    # ----------------------------------------------------------- D-Bus methods

    @method()
    async def StartRecording(self) -> "b":
        return await self._do_start_recording()

    @method()
    async def StopRecording(self) -> "s":
        return await self._do_stop_recording()

    @method()
    async def Toggle(self) -> "s":
        return await self.toggle()

    @method()
    async def Cancel(self) -> "b":
        return await self.cancel()

    @method()
    def GetState(self) -> "s":
        return self._state.value

    @method()
    def Configure(self, options: "a{sv}"):
        self.configure(options)


async def main():
    logger.info("Starting Dictator D-Bus service...")

    bus = await MessageBus(bus_type=BusType.SESSION).connect()
    service = DictatorService()
    bus.export("/org/lebi/Dictator", service)
    await bus.request_name("org.lebi.Dictator")
    logger.info("Service registered as org.lebi.Dictator")

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop_event.set)

    preload_task = asyncio.create_task(service.preload_model())
    waiters = [
        asyncio.create_task(bus.wait_for_disconnect()),
        asyncio.create_task(stop_event.wait()),
    ]
    try:
        await asyncio.wait(waiters, return_when=asyncio.FIRST_COMPLETED)
    finally:
        logger.info("Shutting down...")
        for task in (*waiters, preload_task):
            task.cancel()
        if service.recorder.is_recording:
            await service.recorder.cancel()
        service.typer.close()
        bus.disconnect()
        logger.info("Dictator service stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
