"""Audio recorder module using PipeWire's pw-record."""

import asyncio
import os
import tempfile
from pathlib import Path
from typing import Optional


class Recorder:
    """Handles audio recording via pw-record subprocess."""

    def __init__(self):
        self._process: Optional[asyncio.subprocess.Process] = None
        self._audio_file: Optional[Path] = None
        self._recording = False

    @property
    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self._recording

    @property
    def audio_file(self) -> Optional[Path]:
        """Get the path to the recorded audio file."""
        return self._audio_file

    async def start(self) -> Path:
        """Start recording audio from the default microphone.

        Returns:
            Path to the temporary WAV file being recorded.

        Raises:
            RuntimeError: If already recording or pw-record fails to start.
        """
        if self._recording:
            raise RuntimeError("Already recording")

        # Create temp file for audio
        fd, path = tempfile.mkstemp(suffix=".wav", prefix="dictator_")
        os.close(fd)
        self._audio_file = Path(path)

        # Start pw-record
        # Format: 16-bit signed LE, 16kHz mono (optimal for Whisper)
        cmd = [
            "pw-record",
            "--format", "s16",
            "--rate", "16000",
            "--channels", "1",
            str(self._audio_file),
        ]

        try:
            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            self._recording = True
            return self._audio_file
        except FileNotFoundError:
            self._cleanup_file()
            raise RuntimeError(
                "pw-record not found. Please install PipeWire: "
                "sudo apt install pipewire pipewire-audio-client-libraries"
            )
        except Exception as e:
            self._cleanup_file()
            raise RuntimeError(f"Failed to start recording: {e}")

    async def stop(self) -> Path:
        """Stop recording and return the audio file path.

        Returns:
            Path to the recorded WAV file.

        Raises:
            RuntimeError: If not currently recording.
        """
        if not self._recording or self._process is None:
            raise RuntimeError("Not recording")

        # Send SIGTERM to stop recording gracefully
        self._process.terminate()

        try:
            # Wait for process to finish (with timeout)
            await asyncio.wait_for(self._process.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            # Force kill if it doesn't respond
            self._process.kill()
            await self._process.wait()

        self._recording = False
        self._process = None

        if self._audio_file and self._audio_file.exists():
            return self._audio_file
        else:
            raise RuntimeError("Recording failed: no audio file created")

    async def cancel(self) -> None:
        """Cancel recording and clean up."""
        if self._process is not None:
            self._process.kill()
            try:
                await self._process.wait()
            except Exception:
                pass
            self._process = None

        self._recording = False
        self._cleanup_file()

    def _cleanup_file(self) -> None:
        """Remove the temporary audio file."""
        if self._audio_file and self._audio_file.exists():
            try:
                self._audio_file.unlink()
            except Exception:
                pass
        self._audio_file = None

    def cleanup(self) -> None:
        """Clean up resources. Call after transcription is complete."""
        self._cleanup_file()
