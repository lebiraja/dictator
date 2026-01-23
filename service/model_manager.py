"""Model manager for downloading and managing Whisper models."""

import asyncio
import hashlib
import os
from pathlib import Path
from typing import Callable, Optional
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError


# Model download URLs (HuggingFace)
MODELS = {
    "base.en": {
        "url": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin",
        "size": 147_951_465,  # ~141 MB
        "sha256": None,  # Can add checksum verification later
    },
    "small.en": {
        "url": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.en.bin",
        "size": 488_181_545,  # ~466 MB
        "sha256": None,
    },
    "tiny.en": {
        "url": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.en.bin",
        "size": 77_691_713,  # ~74 MB
        "sha256": None,
    },
}

DEFAULT_MODEL = "base.en"


class ModelManager:
    """Manages Whisper model downloads and storage."""

    def __init__(self, models_dir: Optional[Path] = None):
        """Initialize the model manager.

        Args:
            models_dir: Directory to store models. Defaults to
                       ~/.local/share/dictator/models/
        """
        if models_dir is None:
            xdg_data = os.environ.get(
                "XDG_DATA_HOME",
                os.path.expanduser("~/.local/share")
            )
            self.models_dir = Path(xdg_data) / "dictator" / "models"
        else:
            self.models_dir = Path(models_dir)

    def get_model_path(self, model_name: str = DEFAULT_MODEL) -> Path:
        """Get the path where a model should be stored.

        Args:
            model_name: Name of the model (e.g., "base.en")

        Returns:
            Path to the model file.
        """
        return self.models_dir / f"ggml-{model_name}.bin"

    def is_model_available(self, model_name: str = DEFAULT_MODEL) -> bool:
        """Check if a model is downloaded and ready.

        Args:
            model_name: Name of the model to check.

        Returns:
            True if the model file exists.
        """
        model_path = self.get_model_path(model_name)
        return model_path.exists() and model_path.stat().st_size > 0

    async def ensure_model(
        self,
        model_name: str = DEFAULT_MODEL,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Path:
        """Ensure a model is available, downloading if necessary.

        Args:
            model_name: Name of the model to ensure.
            progress_callback: Optional callback(bytes_downloaded, total_bytes)

        Returns:
            Path to the model file.

        Raises:
            ValueError: If model_name is not recognized.
            RuntimeError: If download fails.
        """
        if model_name not in MODELS:
            raise ValueError(
                f"Unknown model: {model_name}. "
                f"Available: {', '.join(MODELS.keys())}"
            )

        model_path = self.get_model_path(model_name)

        if self.is_model_available(model_name):
            return model_path

        # Download in a thread pool to not block the event loop
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            self._download_model,
            model_name,
            progress_callback,
        )

        return model_path

    def _download_model(
        self,
        model_name: str,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> None:
        """Download a model (blocking, run in executor).

        Args:
            model_name: Name of the model to download.
            progress_callback: Optional progress callback.
        """
        model_info = MODELS[model_name]
        url = model_info["url"]
        expected_size = model_info["size"]
        model_path = self.get_model_path(model_name)

        # Ensure directory exists
        self.models_dir.mkdir(parents=True, exist_ok=True)

        # Download to temp file first, then rename
        temp_path = model_path.with_suffix(".tmp")

        try:
            request = Request(url)
            request.add_header("User-Agent", "Dictator/1.0")

            with urlopen(request, timeout=30) as response:
                total_size = int(response.headers.get("Content-Length", expected_size))
                downloaded = 0
                chunk_size = 8192

                with open(temp_path, "wb") as f:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)

                        if progress_callback:
                            progress_callback(downloaded, total_size)

            # Rename temp file to final path
            temp_path.rename(model_path)

        except (URLError, HTTPError) as e:
            if temp_path.exists():
                temp_path.unlink()
            raise RuntimeError(f"Failed to download model: {e}")
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise RuntimeError(f"Download error: {e}")

    def list_available_models(self) -> list[str]:
        """List models that are downloaded and available.

        Returns:
            List of available model names.
        """
        available = []
        for model_name in MODELS:
            if self.is_model_available(model_name):
                available.append(model_name)
        return available

    def get_model_size(self, model_name: str = DEFAULT_MODEL) -> int:
        """Get the expected size of a model in bytes.

        Args:
            model_name: Name of the model.

        Returns:
            Size in bytes.
        """
        if model_name not in MODELS:
            raise ValueError(f"Unknown model: {model_name}")
        return MODELS[model_name]["size"]
