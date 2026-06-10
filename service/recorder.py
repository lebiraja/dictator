"""In-memory audio capture via PipeWire's pw-record.

Audio is streamed from pw-record's stdout straight into RAM — nothing is
written to disk. The recorder reports a smoothed RMS level per chunk so the
UI can render a live meter, and enforces a hard duration cap.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable

import numpy as np

logger = logging.getLogger("dictator.recorder")

SAMPLE_RATE = 16000
SAMPLE_WIDTH = 2  # s16
BYTES_PER_SECOND = SAMPLE_RATE * SAMPLE_WIDTH
CHUNK_BYTES = BYTES_PER_SECOND // 10  # 100 ms => ~10 level updates/sec
MIN_AUDIO_SECONDS = 0.25
STARTUP_GRACE_SECONDS = 0.3

LevelCallback = Callable[[float], None]
LimitCallback = Callable[[], Awaitable[None]]


class RecorderError(RuntimeError):
    """Raised when recording cannot start, stop, or produced no audio."""


class Recorder:
    """Records 16 kHz mono s16 PCM from the default source into memory."""

    def __init__(
        self,
        on_level: LevelCallback | None = None,
        on_limit: LimitCallback | None = None,
    ) -> None:
        self._process: asyncio.subprocess.Process | None = None
        self._reader_task: asyncio.Task | None = None
        self._buffer = bytearray()
        self._recording = False
        self._limit_hit = False
        self.max_duration: float = 120.0
        self._on_level = on_level
        self._on_limit = on_limit

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def duration(self) -> float:
        """Seconds of audio captured so far."""
        return len(self._buffer) / BYTES_PER_SECOND

    async def start(self) -> None:
        """Start capturing audio.

        Raises:
            RecorderError: if already recording, pw-record is missing, or
                pw-record exits immediately (no microphone / no session).
        """
        if self._recording:
            raise RecorderError("Already recording")

        self._buffer = bytearray()
        self._limit_hit = False

        cmd = [
            "pw-record",
            "--format", "s16",
            "--rate", str(SAMPLE_RATE),
            "--channels", "1",
            "-",
        ]
        try:
            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            raise RecorderError(
                "pw-record not found. Install PipeWire: "
                "sudo apt install pipewire pipewire-audio-client-libraries"
            )

        # Fail fast if pw-record dies right away (PipeWire down, no source).
        try:
            await asyncio.wait_for(self._process.wait(), timeout=STARTUP_GRACE_SECONDS)
        except asyncio.TimeoutError:
            pass  # still running — good
        else:
            stderr = b""
            if self._process.stderr:
                stderr = await self._process.stderr.read()
            self._process = None
            detail = stderr.decode(errors="replace").strip() or "unknown error"
            raise RecorderError(f"Audio capture failed to start: {detail}")

        self._recording = True
        self._reader_task = asyncio.create_task(self._read_stream())
        logger.info("Recording started (max %.0fs)", self.max_duration)

    async def _read_stream(self) -> None:
        """Drain pw-record stdout into the buffer, emitting level updates."""
        assert self._process is not None and self._process.stdout is not None
        max_bytes = int(self.max_duration * BYTES_PER_SECOND)
        try:
            while True:
                chunk = await self._process.stdout.read(CHUNK_BYTES)
                if not chunk:
                    break
                if len(self._buffer) < max_bytes:
                    self._buffer.extend(chunk)
                elif not self._limit_hit:
                    self._limit_hit = True
                    logger.warning("Max duration reached (%.0fs)", self.max_duration)
                    if self._on_limit is not None:
                        asyncio.ensure_future(self._on_limit())
                if self._on_level is not None and self._recording:
                    self._on_level(self._chunk_level(chunk))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Audio stream reader failed")

    @staticmethod
    def _chunk_level(chunk: bytes) -> float:
        """RMS level of a PCM chunk, normalized to 0.0–1.0."""
        samples = np.frombuffer(chunk[: len(chunk) - len(chunk) % 2], dtype=np.int16)
        if samples.size == 0:
            return 0.0
        rms = float(np.sqrt(np.mean(np.square(samples.astype(np.float64)))))
        return min(1.0, rms / 32768.0)

    async def stop(self) -> np.ndarray:
        """Stop capturing and return the audio as float32 in [-1, 1].

        Raises:
            RecorderError: if not recording or no usable audio was captured.
        """
        if not self._recording or self._process is None:
            raise RecorderError("Not recording")

        self._recording = False
        await self._shutdown_process(graceful=True)

        if self.duration < MIN_AUDIO_SECONDS:
            self._buffer = bytearray()
            raise RecorderError("No audio captured — recording was too short")

        pcm = bytes(self._buffer)
        self._buffer = bytearray()
        audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        logger.info("Recording stopped: %.1fs of audio", audio.size / SAMPLE_RATE)
        return audio

    async def cancel(self) -> None:
        """Abort recording and discard captured audio."""
        self._recording = False
        if self._process is not None:
            await self._shutdown_process(graceful=False)
        self._buffer = bytearray()
        logger.info("Recording cancelled")

    async def _shutdown_process(self, graceful: bool) -> None:
        assert self._process is not None
        try:
            if graceful:
                self._process.terminate()
            else:
                self._process.kill()
        except ProcessLookupError:
            pass

        if self._reader_task is not None:
            # Reader exits at stdout EOF once the process dies.
            try:
                await asyncio.wait_for(self._reader_task, timeout=5.0)
            except asyncio.TimeoutError:
                self._reader_task.cancel()
            self._reader_task = None

        try:
            await asyncio.wait_for(self._process.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            self._process.kill()
            await self._process.wait()
        self._process = None
