"""Tests for the transcriber wrapper."""

import threading
from types import SimpleNamespace

import numpy as np
import pytest
import transcriber as transcriber_mod
from transcriber import Transcriber, TranscriptionCancelled


@pytest.fixture(autouse=True)
def force_cpu(monkeypatch):
    monkeypatch.setattr(transcriber_mod, "cuda_available", lambda: False)


def make_model(segment_texts, fail=False):
    """A WhisperModel stand-in yielding the given segment texts."""

    class FakeModel:
        instances = []

        def __init__(self, model_size, device="cpu", compute_type="int8"):
            self.model_size = model_size
            self.device = device
            FakeModel.instances.append(self)

        def transcribe(self, audio, **kwargs):
            if fail and self.device == "cuda":
                raise RuntimeError("CUDA out of memory")
            segments = (SimpleNamespace(text=t) for t in segment_texts)
            info = SimpleNamespace(language="en", language_probability=0.99)
            return segments, info

    return FakeModel


AUDIO = np.zeros(16000, dtype=np.float32)


def test_cpu_defaults():
    t = Transcriber()
    assert t.device == "cpu"
    assert t.compute_type == "int8"
    assert t.beam_size == 1
    assert t.model_size == "small.en"


def test_transcribe_joins_segments(monkeypatch):
    monkeypatch.setattr(transcriber_mod, "WhisperModel", make_model([" Hello", " world."]))
    t = Transcriber()
    assert t.transcribe(AUDIO) == "Hello world."


def test_cancellation_between_segments(monkeypatch):
    monkeypatch.setattr(transcriber_mod, "WhisperModel", make_model([" a", " b"]))
    t = Transcriber()
    event = threading.Event()
    event.set()
    with pytest.raises(TranscriptionCancelled):
        t.transcribe(AUDIO, cancel_event=event)


def test_model_loaded_once(monkeypatch):
    model_cls = make_model([" hi"])
    monkeypatch.setattr(transcriber_mod, "WhisperModel", model_cls)
    t = Transcriber()
    t.transcribe(AUDIO)
    t.transcribe(AUDIO)
    assert len(model_cls.instances) == 1


def test_set_model_triggers_reload(monkeypatch):
    model_cls = make_model([" hi"])
    monkeypatch.setattr(transcriber_mod, "WhisperModel", model_cls)
    t = Transcriber()
    t.transcribe(AUDIO)
    assert t.set_model("tiny.en") is True
    assert t.set_model("tiny.en") is False  # unchanged
    assert not t.is_loaded
    t.transcribe(AUDIO)
    assert len(model_cls.instances) == 2
    assert model_cls.instances[-1].model_size == "tiny.en"


def test_cuda_failure_falls_back_to_cpu(monkeypatch):
    model_cls = make_model([" recovered"], fail=True)
    monkeypatch.setattr(transcriber_mod, "WhisperModel", model_cls)
    t = Transcriber()
    # pretend init detected CUDA
    t.device = "cuda"
    t.compute_type = "float16"
    assert t.transcribe(AUDIO) == "recovered"
    assert t.device == "cpu"


def test_model_is_cached(tmp_path, monkeypatch):
    monkeypatch.setenv("HF_HOME", str(tmp_path))
    assert transcriber_mod.model_is_cached("small.en") is False
    (tmp_path / "hub" / "models--Systran--faster-whisper-small.en").mkdir(parents=True)
    assert transcriber_mod.model_is_cached("small.en") is True
