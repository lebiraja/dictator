"""Transcriber module using whisper.cpp."""

import asyncio
import os
import shutil
from pathlib import Path
from typing import Optional

try:
    from .model_manager import ModelManager, DEFAULT_MODEL
except ImportError:
    from model_manager import ModelManager, DEFAULT_MODEL


# Common whisper.cpp binary names (in order of preference)
WHISPER_BINARIES = [
    "whisper-cli",  # Current default name from whisper.cpp build
    "whisper-cpp",
    "whisper",
    "main",  # Old default build name
]


class Transcriber:
    """Handles audio transcription using whisper.cpp."""

    def __init__(
        self,
        model_manager: Optional[ModelManager] = None,
        whisper_binary: Optional[str] = None,
    ):
        """Initialize the transcriber.

        Args:
            model_manager: ModelManager instance for model paths.
            whisper_binary: Path to whisper.cpp binary. If None, searches PATH.
        """
        self.model_manager = model_manager or ModelManager()
        self._whisper_binary = whisper_binary
        self._cached_binary: Optional[str] = None

    def find_whisper_binary(self) -> Optional[str]:
        """Find the whisper.cpp binary.

        Returns:
            Path to the binary, or None if not found.
        """
        if self._cached_binary:
            return self._cached_binary

        if self._whisper_binary:
            if shutil.which(self._whisper_binary):
                self._cached_binary = self._whisper_binary
                return self._cached_binary

        # Search for common binary names
        for name in WHISPER_BINARIES:
            path = shutil.which(name)
            if path:
                self._cached_binary = path
                return self._cached_binary

        # Check common installation locations
        common_paths = [
            os.path.expanduser("~/.local/bin/whisper-cli"),
            os.path.expanduser("~/.local/bin/whisper"),
            "/usr/local/bin/whisper-cli",
            "/usr/local/bin/whisper",
            "/usr/bin/whisper",
            os.path.expanduser("~/whisper.cpp/build/bin/whisper-cli"),
            os.path.expanduser("~/whisper.cpp/build/bin/main"),
        ]

        for path in common_paths:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                self._cached_binary = path
                return self._cached_binary

        return None

    def is_available(self) -> bool:
        """Check if whisper.cpp is available.

        Returns:
            True if the binary is found.
        """
        return self.find_whisper_binary() is not None

    async def transcribe(
        self,
        audio_file: Path,
        model_name: str = DEFAULT_MODEL,
        language: str = "en",
    ) -> str:
        """Transcribe an audio file.

        Args:
            audio_file: Path to the WAV audio file.
            model_name: Whisper model to use.
            language: Language code (default: "en").

        Returns:
            Transcribed text.

        Raises:
            RuntimeError: If whisper.cpp is not available or transcription fails.
        """
        binary = self.find_whisper_binary()
        if not binary:
            raise RuntimeError(
                "whisper.cpp not found. Please install it:\n"
                "  git clone https://github.com/ggerganov/whisper.cpp\n"
                "  cd whisper.cpp && make\n"
                "  sudo cp main /usr/local/bin/whisper"
            )

        model_path = self.model_manager.get_model_path(model_name)
        if not model_path.exists():
            raise RuntimeError(
                f"Model not found: {model_path}\n"
                "Run the service to auto-download, or download manually."
            )

        if not audio_file.exists():
            raise RuntimeError(f"Audio file not found: {audio_file}")

        # Build command
        cmd = [
            binary,
            "--model", str(model_path),
            "--file", str(audio_file),
            "--language", language,
            "--no-timestamps",
            "--no-prints",
            "--output-txt",
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=120.0,  # 2 minute timeout
            )

            if process.returncode != 0:
                error_msg = stderr.decode().strip() if stderr else "Unknown error"
                raise RuntimeError(f"Transcription failed: {error_msg}")

            # Parse output
            text = self._parse_output(stdout.decode(), audio_file)
            return text.strip()

        except asyncio.TimeoutError:
            raise RuntimeError("Transcription timed out (>2 minutes)")
        except FileNotFoundError:
            raise RuntimeError(f"whisper.cpp binary not executable: {binary}")

    def _parse_output(self, stdout: str, audio_file: Path) -> str:
        """Parse whisper.cpp output.

        The --output-txt flag creates a .txt file next to the input.
        But stdout also contains the transcription.

        Args:
            stdout: Standard output from whisper.cpp.
            audio_file: Path to the audio file (for .txt lookup).

        Returns:
            Transcribed text.
        """
        # First, try to read the .txt file if created
        txt_file = audio_file.with_suffix(".wav.txt")
        if txt_file.exists():
            text = txt_file.read_text().strip()
            # Clean up the txt file
            try:
                txt_file.unlink()
            except Exception:
                pass
            if text:
                return text

        # Fallback: parse stdout
        # whisper.cpp outputs lines like "[00:00:00.000 --> 00:00:02.000] text"
        # or just plain text depending on flags
        lines = []
        for line in stdout.strip().split("\n"):
            line = line.strip()
            # Skip empty lines and metadata
            if not line:
                continue
            if line.startswith("[") and "-->" in line:
                # Timestamped line, extract text after the timestamp
                if "]" in line:
                    text_part = line.split("]", 1)[-1].strip()
                    if text_part:
                        lines.append(text_part)
            else:
                # Plain text line
                lines.append(line)

        return " ".join(lines)

    async def get_version(self) -> Optional[str]:
        """Get whisper.cpp version if available.

        Returns:
            Version string or None.
        """
        binary = self.find_whisper_binary()
        if not binary:
            return None

        try:
            process = await asyncio.create_subprocess_exec(
                binary, "--help",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await process.communicate()
            # Version is usually in the first line
            first_line = stdout.decode().split("\n")[0]
            return first_line.strip()
        except Exception:
            return None
