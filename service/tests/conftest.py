"""Shared fixtures: make service modules importable and stub hardware deps.

The suite must run anywhere (CI containers without /dev/uinput, PipeWire,
or the heavyweight faster-whisper wheel), so missing third-party modules
are replaced with light fakes before the service modules import them.
"""

import sys
import types
from pathlib import Path

SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_DIR))


class FakeEcodes:
    """Stands in for evdev.ecodes: every KEY_* gets a distinct int."""

    EV_KEY = 1

    def __init__(self) -> None:
        self._codes: dict[str, int] = {}

    def __getattr__(self, name: str) -> int:
        if name.startswith("KEY_"):
            return self._codes.setdefault(name, 100 + len(self._codes))
        raise AttributeError(name)


class FakeUInput:
    """Records key events instead of writing to /dev/uinput."""

    def __init__(self, caps=None, name=""):
        self.caps = caps
        self.name = name
        self.events: list[tuple[int, int, int]] = []
        self.closed = False

    def write(self, etype: int, code: int, value: int) -> None:
        self.events.append((etype, code, value))

    def syn(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True


def _ensure_module(name: str, builder) -> None:
    try:
        __import__(name)
    except ImportError:
        sys.modules[name] = builder()


def _fake_evdev() -> types.ModuleType:
    mod = types.ModuleType("evdev")
    mod.ecodes = FakeEcodes()
    mod.UInput = FakeUInput
    return mod


def _fake_faster_whisper() -> types.ModuleType:
    mod = types.ModuleType("faster_whisper")

    class WhisperModel:  # replaced per-test via monkeypatch
        def __init__(self, *args, **kwargs):
            raise RuntimeError("WhisperModel must be monkeypatched in tests")

    mod.WhisperModel = WhisperModel
    return mod


_ensure_module("evdev", _fake_evdev)
_ensure_module("faster_whisper", _fake_faster_whisper)
