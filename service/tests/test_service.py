"""Tests for the D-Bus service state machine (bus-free)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest
from dictator_service import DictatorService, State
from transcriber import TranscriptionCancelled
from typer import TyperError

AUDIO = np.zeros(16000, dtype=np.float32)


@pytest.fixture
def service():
    svc = DictatorService()
    svc.recorder = MagicMock()
    svc.recorder.start = AsyncMock()
    svc.recorder.stop = AsyncMock(return_value=AUDIO)
    svc.recorder.cancel = AsyncMock()
    svc.recorder.is_recording = False
    svc.transcriber = MagicMock()
    svc.transcriber.transcribe = MagicMock(return_value="hello world")
    svc.typer = MagicMock()
    # capture emitted D-Bus signals
    svc.Error = MagicMock()
    svc.StateChanged = MagicMock()
    svc.TranscriptionReady = MagicMock()
    return svc


# ------------------------------------------------------------ happy path


async def test_full_dictation_flow(service):
    assert await service._do_start_recording() is True
    assert service._state == State.RECORDING

    text = await service._do_stop_recording()
    assert text == "hello world"
    assert service._state == State.IDLE
    service.typer.type_text.assert_called_once()
    service.TranscriptionReady.assert_called_once_with("hello world")
    assert service._last_transcription == "hello world"


async def test_empty_transcription_skips_typing(service):
    service.transcriber.transcribe.return_value = ""
    await service._do_start_recording()
    text = await service._do_stop_recording()
    assert text == ""
    service.typer.type_text.assert_not_called()
    assert service._state == State.IDLE


# ----------------------------------------------------------------- races


async def test_concurrent_starts_only_one_wins(service):
    async def slow_start():
        await asyncio.sleep(0.05)

    service.recorder.start = AsyncMock(side_effect=slow_start)
    results = await asyncio.gather(
        service._do_start_recording(), service._do_start_recording()
    )
    assert sorted(results) == [False, True]
    assert service.recorder.start.await_count == 1
    assert service._state == State.RECORDING


async def test_toggle_starts_then_stops(service):
    assert await service.toggle() == "recording"
    assert await service.toggle() == "idle"


# --------------------------------------------------------- error recovery


async def test_error_state_is_not_sticky(service):
    service._state = State.ERROR
    assert await service._do_start_recording() is True
    assert service._state == State.RECORDING


async def test_recorder_failure_sets_error_state(service):
    service.recorder.start = AsyncMock(side_effect=RuntimeError("mic broken"))
    assert await service._do_start_recording() is False
    assert service._state == State.ERROR
    service.Error.assert_called_once()
    # and the next attempt recovers
    service.recorder.start = AsyncMock()
    assert await service._do_start_recording() is True


async def test_typer_failure_surfaces_as_error(service):
    service.typer.type_text = MagicMock(side_effect=TyperError("no uinput"))
    await service._do_start_recording()
    text = await service._do_stop_recording()
    assert text == ""
    assert service._state == State.ERROR
    service.Error.assert_called_once()
    service.TranscriptionReady.assert_not_called()


async def test_busy_start_is_rejected(service):
    service._state = State.TRANSCRIBING
    assert await service._do_start_recording() is False
    service.recorder.start.assert_not_awaited()
    service.Error.assert_called_once()


async def test_stop_when_not_recording_is_rejected(service):
    assert await service._do_stop_recording() == ""
    service.recorder.stop.assert_not_awaited()


# ------------------------------------------------------------------ cancel


async def test_cancel_while_recording(service):
    await service._do_start_recording()
    assert await service.cancel() is True
    service.recorder.cancel.assert_awaited_once()
    assert service._state == State.IDLE


async def test_cancel_during_transcription(service):
    def transcribe(audio, cancel_event):
        # blocks in the executor until Cancel() sets the event
        cancel_event.wait(timeout=5)
        raise TranscriptionCancelled()

    service.transcriber.transcribe = MagicMock(side_effect=transcribe)
    await service._do_start_recording()

    stop_task = asyncio.create_task(service._do_stop_recording())
    while service._state != State.TRANSCRIBING:
        await asyncio.sleep(0.01)
    assert await service.cancel() is True

    text = await stop_task
    assert text == ""
    assert service._state == State.IDLE
    service.typer.type_text.assert_not_called()


async def test_cancel_clears_error_state(service):
    service._state = State.ERROR
    assert await service.cancel() is True
    assert service._state == State.IDLE


# ----------------------------------------------------------------- config


async def test_configure_applies_settings(service):
    class V:
        def __init__(self, value):
            self.value = value

    service.transcriber.set_model = MagicMock(return_value=False)
    service.configure({
        "model": V("tiny.en"),
        "output-mode": V("type"),
        "max-duration": V(60.0),
        "bogus": V("ignored"),
    })
    service.transcriber.set_model.assert_called_once_with("tiny.en")
    assert service.typer.output_mode == "type"
    assert service.recorder.max_duration == 60.0


# ---------------------------------------------------------------- preload


async def test_preload_emits_loading_then_idle(service):
    service.transcriber.is_loaded = False
    service.transcriber.needs_download.return_value = False
    service.transcriber.load_model = MagicMock()
    await service.preload_model()
    assert service._state == State.IDLE
    service.transcriber.load_model.assert_called_once()


async def test_preload_does_not_stomp_on_recording(service):
    service.transcriber.is_loaded = False
    service.transcriber.needs_download.return_value = False

    started = asyncio.Event()

    def slow_load():
        started.set()

    service.transcriber.load_model = slow_load

    preload = asyncio.create_task(service.preload_model())
    await asyncio.sleep(0)  # let preload set LOADING
    assert service._state == State.LOADING
    await service._do_start_recording()  # allowed during load
    assert service._state == State.RECORDING
    await preload
    assert service._state == State.RECORDING  # not reset to idle
