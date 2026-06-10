"""Tests for the in-memory recorder."""

import asyncio

import numpy as np
import pytest
import recorder as recorder_mod
from recorder import BYTES_PER_SECOND, Recorder, RecorderError


class FakeStream:
    def __init__(self, chunks):
        self._chunks = list(chunks)
        self._eof = asyncio.Event()

    async def read(self, n=-1):
        if self._chunks:
            return self._chunks.pop(0)
        await self._eof.wait()
        return b""

    def set_eof(self):
        self._eof.set()


class FakeProcess:
    def __init__(self, chunks=(), stderr=b""):
        self.stdout = FakeStream(chunks)
        self.stderr = FakeStream([stderr] if stderr else [])
        self.returncode = None
        self._done = asyncio.Event()

    def terminate(self):
        self._finish(0)

    def kill(self):
        self._finish(-9)

    def _finish(self, rc):
        self.returncode = rc
        self.stdout.set_eof()
        self.stderr.set_eof()
        self._done.set()

    async def wait(self):
        await self._done.wait()
        return self.returncode


def patch_spawn(monkeypatch, proc):
    async def spawn(*args, **kwargs):
        return proc

    monkeypatch.setattr(recorder_mod.asyncio, "create_subprocess_exec", spawn)


def pcm(seconds: float, value: int = 1000) -> bytes:
    return np.full(int(seconds * 16000), value, dtype=np.int16).tobytes()


# ----------------------------------------------------------------- levels


def test_chunk_level_silence_is_zero():
    assert Recorder._chunk_level(b"\x00" * 3200) == 0.0


def test_chunk_level_full_scale_is_one():
    loud = np.full(1600, 32767, dtype=np.int16).tobytes()
    assert Recorder._chunk_level(loud) == pytest.approx(1.0, abs=0.001)


# ------------------------------------------------------------ start/stop


async def test_start_fails_fast_when_process_dies(monkeypatch):
    proc = FakeProcess(stderr=b"no default source")
    proc._finish(1)  # already dead at spawn
    patch_spawn(monkeypatch, proc)

    rec = Recorder()
    with pytest.raises(RecorderError, match="no default source"):
        await rec.start()
    assert not rec.is_recording


async def test_missing_pw_record(monkeypatch):
    async def spawn(*args, **kwargs):
        raise FileNotFoundError()

    monkeypatch.setattr(recorder_mod.asyncio, "create_subprocess_exec", spawn)
    rec = Recorder()
    with pytest.raises(RecorderError, match="PipeWire"):
        await rec.start()


async def test_record_and_stop_returns_float32(monkeypatch):
    monkeypatch.setattr(recorder_mod, "STARTUP_GRACE_SECONDS", 0.01)
    proc = FakeProcess(chunks=[pcm(0.5, 16384)])
    patch_spawn(monkeypatch, proc)

    rec = Recorder()
    await rec.start()
    assert rec.is_recording
    await asyncio.sleep(0.05)  # let the reader drain the chunk

    audio = await rec.stop()
    assert audio.dtype == np.float32
    assert audio.size == 8000
    assert audio.max() == pytest.approx(0.5, abs=0.01)
    assert not rec.is_recording


async def test_too_short_recording_raises(monkeypatch):
    monkeypatch.setattr(recorder_mod, "STARTUP_GRACE_SECONDS", 0.01)
    proc = FakeProcess(chunks=[pcm(0.05)])
    patch_spawn(monkeypatch, proc)

    rec = Recorder()
    await rec.start()
    await asyncio.sleep(0.05)
    with pytest.raises(RecorderError, match="too short"):
        await rec.stop()


async def test_stop_when_idle_raises():
    with pytest.raises(RecorderError, match="Not recording"):
        await Recorder().stop()


async def test_double_start_raises(monkeypatch):
    monkeypatch.setattr(recorder_mod, "STARTUP_GRACE_SECONDS", 0.01)
    proc = FakeProcess()
    patch_spawn(monkeypatch, proc)
    rec = Recorder()
    await rec.start()
    with pytest.raises(RecorderError, match="Already recording"):
        await rec.start()
    await rec.cancel()


async def test_cancel_discards_audio(monkeypatch):
    monkeypatch.setattr(recorder_mod, "STARTUP_GRACE_SECONDS", 0.01)
    proc = FakeProcess(chunks=[pcm(1.0)])
    patch_spawn(monkeypatch, proc)

    rec = Recorder()
    await rec.start()
    await asyncio.sleep(0.05)
    await rec.cancel()
    assert rec.duration == 0.0
    assert not rec.is_recording


# ------------------------------------------------------------ max duration


async def test_level_callback_and_max_duration(monkeypatch):
    monkeypatch.setattr(recorder_mod, "STARTUP_GRACE_SECONDS", 0.01)
    levels = []
    limit_hits = []

    async def on_limit():
        limit_hits.append(True)

    # 3 chunks of 1s each against a 2s cap
    proc = FakeProcess(chunks=[pcm(1.0), pcm(1.0), pcm(1.0)])
    patch_spawn(monkeypatch, proc)

    rec = Recorder(on_level=levels.append, on_limit=on_limit)
    rec.max_duration = 2.0
    await rec.start()
    await asyncio.sleep(0.05)

    assert len(levels) == 3
    assert limit_hits == [True]
    assert rec.duration <= 2.0 + 1.0  # capped: third chunk not appended

    audio = await rec.stop()
    assert audio.size <= 2 * 16000 + 16000
    assert len(rec._buffer) == 0


async def test_buffer_stops_growing_at_cap(monkeypatch):
    monkeypatch.setattr(recorder_mod, "STARTUP_GRACE_SECONDS", 0.01)
    proc = FakeProcess(chunks=[pcm(1.0)] * 5)
    patch_spawn(monkeypatch, proc)

    rec = Recorder()
    rec.max_duration = 1.0
    await rec.start()
    await asyncio.sleep(0.05)
    # first chunk fills the 1s cap; the rest must be dropped
    assert len(rec._buffer) <= BYTES_PER_SECOND
    await rec.cancel()
