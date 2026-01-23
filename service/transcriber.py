import logging
import os
import subprocess
from typing import Optional
from faster_whisper import WhisperModel

logger = logging.getLogger("dictator.transcriber")

class Transcriber:
    """
    Handles speech-to-text transcription using faster-whisper.
    """
    def __init__(self, model_size: str = "base.en", device: str = "auto", compute_type: str = "auto"):
        self.model_size = model_size
        self._model: Optional[WhisperModel] = None

        # Determine device
        if device == "auto":
            # Simple check for nvidia-smi to guess if we have a GPU
            try:
                subprocess.run(["nvidia-smi"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                self.device = "cuda"
            except (subprocess.CalledProcessError, FileNotFoundError):
                self.device = "cpu"
        else:
            self.device = device

        # Determine compute type
        if compute_type == "auto":
            if self.device == "cuda":
                self.compute_type = "float16"
            else:
                self.compute_type = "int8"
        else:
            self.compute_type = compute_type

        logger.info(f"Transcriber initialized. Target device: {self.device}, Compute type: {self.compute_type}")

    def _ensure_model(self):
        """Lazy load the model."""
        if self._model is None:
            logger.info(f"Loading faster-whisper model '{self.model_size}'...")
            try:
                self._model = WhisperModel(
                    self.model_size,
                    device=self.device,
                    compute_type=self.compute_type
                )
                logger.info("Model loaded successfully.")
            except Exception as e:
                logger.error(f"Failed to load model: {e}")
                # Fallback to CPU int8 if CUDA fails
                if self.device == "cuda":
                    logger.warning("Falling back to CPU int8...")
                    self.device = "cpu"
                    self.compute_type = "int8"
                    self._model = WhisperModel(
                        self.model_size,
                        device=self.device,
                        compute_type=self.compute_type
                    )
                else:
                    raise

    def transcribe(self, audio_path: str) -> str:
        """
        Transcribe the audio file at the given path.
        """
        if not os.path.exists(audio_path):
            logger.error(f"Audio file not found: {audio_path}")
            return ""

        self._ensure_model()

        try:
            logger.info(f"Transcribing {audio_path}...")
            # vad_filter=True ignores silence
            segments, info = self._model.transcribe(
                audio_path,
                beam_size=5,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500)
            )

            text_segments = []
            for segment in segments:
                text_segments.append(segment.text)

            full_text = " ".join(text_segments).strip()
            logger.info(f"Transcription result: '{full_text}' (Language: {info.language}, Probability: {info.language_probability:.2f})")

            return full_text

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return ""

    def is_available(self) -> bool:
        """Check if library is available (model might need download)."""
        return True
