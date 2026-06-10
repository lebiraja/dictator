"""Speech-to-text transcription using faster-whisper.

The model is loaded once (off the hot path, see DictatorService.preload) and
kept warm. Transcription accepts in-memory float32 PCM and supports
cooperative cancellation between decoded segments.
"""

import logging
import os
import threading
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel

logger = logging.getLogger("dictator.transcriber")

DEFAULT_MODEL = "small.en"


class TranscriptionCancelled(Exception):
    """Raised when a transcription is aborted via the cancel event."""


def cuda_available() -> bool:
    """True if ctranslate2 can actually see a CUDA device."""
    try:
        import ctranslate2

        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False


def model_is_cached(model_size: str) -> bool:
    """True if the faster-whisper model is already in the local HF cache."""
    hf_home = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface"))
    repo_dir = hf_home / "hub" / f"models--Systran--faster-whisper-{model_size}"
    return repo_dir.is_dir()


class Transcriber:
    """Wraps a warm WhisperModel with device fallback and cancellation."""

    def __init__(self, model_size: str = DEFAULT_MODEL) -> None:
        self.model_size = model_size
        self._model: WhisperModel | None = None
        self._model_lock = threading.Lock()

        if cuda_available():
            self.device = "cuda"
            self.compute_type = "float16"
            self.beam_size = 5
        else:
            self.device = "cpu"
            self.compute_type = "int8"
            self.beam_size = 1  # greedy decoding: ~2x faster on CPU
        logger.info(
            "Transcriber: device=%s compute=%s beam=%d model=%s",
            self.device, self.compute_type, self.beam_size, self.model_size,
        )

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def needs_download(self) -> bool:
        return not model_is_cached(self.model_size)

    def set_model(self, model_size: str) -> bool:
        """Switch model; returns True if it changed (reload needed)."""
        if model_size == self.model_size:
            return False
        logger.info("Model changed: %s -> %s", self.model_size, model_size)
        with self._model_lock:
            self.model_size = model_size
            self._model = None
        return True

    def load_model(self) -> None:
        """Blocking model load. Call from an executor thread."""
        with self._model_lock:
            if self._model is not None:
                return
            logger.info("Loading model '%s' on %s...", self.model_size, self.device)
            try:
                self._model = WhisperModel(
                    self.model_size, device=self.device, compute_type=self.compute_type
                )
            except Exception as e:
                if self.device != "cuda":
                    raise
                logger.error("CUDA load failed (%s), falling back to CPU int8", e)
                self.device = "cpu"
                self.compute_type = "int8"
                self.beam_size = 1
                self._model = WhisperModel(
                    self.model_size, device=self.device, compute_type=self.compute_type
                )
            logger.info("Model loaded")

    def transcribe(
        self, audio: np.ndarray, cancel_event: threading.Event | None = None
    ) -> str:
        """Transcribe float32 PCM (16 kHz mono). Blocking; run in executor.

        Raises:
            TranscriptionCancelled: if cancel_event is set mid-transcription.
        """
        self.load_model()
        try:
            return self._run(audio, cancel_event)
        except TranscriptionCancelled:
            raise
        except Exception as e:
            if self.device != "cuda":
                raise
            logger.error("CUDA transcription failed (%s), retrying on CPU", e)
            with self._model_lock:
                self.device = "cpu"
                self.compute_type = "int8"
                self.beam_size = 1
                self._model = None
            self.load_model()
            return self._run(audio, cancel_event)

    def _run(self, audio: np.ndarray, cancel_event: threading.Event | None) -> str:
        assert self._model is not None
        segments, info = self._model.transcribe(
            audio,
            beam_size=self.beam_size,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
        )
        parts = []
        for segment in segments:  # lazy generator — decode happens here
            if cancel_event is not None and cancel_event.is_set():
                raise TranscriptionCancelled()
            parts.append(segment.text)

        text = "".join(parts).strip()
        logger.info(
            "Transcribed %.1fs -> %d chars (lang=%s p=%.2f)",
            audio.size / 16000, len(text), info.language, info.language_probability,
        )
        return text
