"""Tests for the typer module (paste + type output)."""

import string
import threading

import pytest
import typer as typer_mod
from conftest import FakeUInput
from typer import Typer, TyperError, TypingCancelled, _build_keymap


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(typer_mod.time, "sleep", lambda s: None)


@pytest.fixture
def fake_uinput(monkeypatch):
    created: list[FakeUInput] = []

    def factory(caps=None, name=""):
        ui = FakeUInput(caps, name)
        created.append(ui)
        return ui

    monkeypatch.setattr(typer_mod, "UInput", factory)
    return created


# ----------------------------------------------------------------- keymap


def test_keymap_covers_all_printable_ascii():
    keymap = _build_keymap()
    expected = string.ascii_letters + string.digits + string.punctuation + " \n\t"
    missing = [c for c in expected if c not in keymap]
    assert missing == []


def test_keymap_shift_pairs():
    keymap = _build_keymap()
    ec = typer_mod.ec
    # uppercase shares the keycode of lowercase, with shift
    assert keymap["A"] == (keymap["a"][0], True)
    assert keymap["a"][1] is False
    # the punctuation that was silently dropped before the rewrite
    assert keymap[":"] == (ec.KEY_SEMICOLON, True)
    assert keymap[";"] == (ec.KEY_SEMICOLON, False)
    assert keymap["?"] == (ec.KEY_SLASH, True)
    assert keymap["@"] == (ec.KEY_2, True)
    assert keymap["{"] == (ec.KEY_LEFTBRACE, True)


# -------------------------------------------------------------- type mode


def test_type_mode_emits_press_release(fake_uinput):
    t = Typer(output_mode="type")
    t.type_text("hi")
    ui = fake_uinput[0]
    ec = typer_mod.ec
    presses = [(code, val) for etype, code, val in ui.events if etype == ec.EV_KEY]
    h, i = t._keymap["h"][0], t._keymap["i"][0]
    assert presses == [(h, 1), (h, 0), (i, 1), (i, 0)]


def test_type_mode_wraps_shift_chars(fake_uinput):
    t = Typer(output_mode="type")
    t.type_text("A")
    ec = typer_mod.ec
    a_code = t._keymap["a"][0]
    events = [(code, val) for etype, code, val in fake_uinput[0].events]
    assert events == [
        (ec.KEY_LEFTSHIFT, 1),
        (a_code, 1),
        (a_code, 0),
        (ec.KEY_LEFTSHIFT, 0),
    ]


def test_type_mode_skips_unsupported_chars(fake_uinput):
    t = Typer(output_mode="type")
    t.type_text("aé")  # é is not mappable on a US layout
    presses = [e for e in fake_uinput[0].events if e[2] == 1]
    assert len(presses) == 1


def test_type_mode_cancellation(fake_uinput):
    t = Typer(output_mode="type")
    event = threading.Event()
    event.set()
    with pytest.raises(TypingCancelled):
        t.type_text("hello", cancel_event=event)


def test_uinput_permission_error_becomes_typer_error(monkeypatch):
    def denied(caps=None, name=""):
        raise PermissionError()

    monkeypatch.setattr(typer_mod, "UInput", denied)
    t = Typer(output_mode="type")
    with pytest.raises(TyperError, match="uinput"):
        t.type_text("x")


def test_empty_text_is_noop(fake_uinput):
    Typer(output_mode="type").type_text("")
    assert fake_uinput == []


# ------------------------------------------------------------- paste mode


def test_paste_mode_sets_clipboard_taps_ctrl_v_and_restores(fake_uinput, monkeypatch):
    t = Typer(output_mode="paste")
    monkeypatch.setattr(t, "_clipboard_tools", lambda: (["copy"], ["paste"]))

    writes: list[bytes] = []
    monkeypatch.setattr(
        typer_mod.Typer, "_read_clipboard", staticmethod(lambda cmd: b"old contents")
    )
    monkeypatch.setattr(
        typer_mod.Typer, "_write_clipboard", staticmethod(lambda cmd, data: writes.append(data))
    )

    t.type_text("new text")

    ec = typer_mod.ec
    events = [(code, val) for etype, code, val in fake_uinput[0].events]
    assert (ec.KEY_LEFTCTRL, 1) in events and (ec.KEY_V, 1) in events
    assert events.index((ec.KEY_LEFTCTRL, 1)) < events.index((ec.KEY_V, 1))
    assert writes == [b"new text", b"old contents"]


def test_paste_mode_without_clipboard_tool_falls_back_to_typing(fake_uinput, monkeypatch):
    t = Typer(output_mode="paste")
    monkeypatch.setattr(t, "_clipboard_tools", lambda: None)
    t.type_text("ok")
    presses = [e for e in fake_uinput[0].events if e[2] == 1]
    assert len(presses) == 2  # typed char-by-char, no ctrl+v


def test_paste_clipboard_failure_raises(fake_uinput, monkeypatch):
    t = Typer(output_mode="paste")
    monkeypatch.setattr(t, "_clipboard_tools", lambda: (["copy"], ["paste"]))
    monkeypatch.setattr(typer_mod.Typer, "_read_clipboard", staticmethod(lambda cmd: None))

    def boom(cmd, data):
        raise OSError("no display")

    monkeypatch.setattr(typer_mod.Typer, "_write_clipboard", staticmethod(boom))
    with pytest.raises(TyperError, match="clipboard"):
        t.type_text("text")
