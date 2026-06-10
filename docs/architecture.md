# Dictator — Architecture

## Components

```
┌──────────────────────────────┐        ┌────────────────────────────────────┐
│  GNOME Shell extension       │        │  Python service (user session)     │
│  extension/extension.js      │ D-Bus  │  service/dictator_service.py       │
│  • panel indicator + menu    │◄──────►│  org.lebi.Dictator                 │
│  • overlay pill (levels,     │        │  • state machine (asyncio.Lock)    │
│    timer, spinner)           │        │  • Recorder  → pw-record stdout    │
│  • keybinding (Shift+Ctrl+   │        │  • Transcriber → faster-whisper    │
│    Space)                    │        │  • Typer → clipboard+Ctrl+V or     │
│  • pushes settings via       │        │    per-char uinput events          │
│    Configure(a{sv})          │        └────────────────────────────────────┘
└──────────────────────────────┘                 ▲
        ▲                                        │ D-Bus (gdbus)
        │ GSettings (gschema)            ┌───────┴───────┐
┌───────┴───────────┐                    │  cli/dictator │  ← any desktop
│  prefs.js (Adw)   │                    └───────────────┘
└───────────────────┘
```

- **Audio never touches disk**: `pw-record` streams s16/16 kHz/mono PCM to
  stdout; the recorder buffers it in RAM and hands faster-whisper a float32
  numpy array.
- The recorder computes an RMS level per ~100 ms chunk → `AudioLevel(d)`
  D-Bus signal → live meter in the overlay.
- The Whisper model is preloaded in the background when the service starts
  (states `loading` / `downloading`) and kept warm.

## State machine

```
            ┌────────────── error ◄────────┐ (any failure)
            ▼                              │
loading/downloading ──► idle ──► recording ──► transcribing ──► typing ──► idle
  (preload at start)      ▲          │              │              │
                          └──────────┴── Cancel ────┴──────────────┘
```

- Starting a recording is allowed from `idle`, `error`, `loading`, and
  `downloading` (transcription waits on the model lock if needed).
- `error` is never sticky: the next Toggle/StartRecording proceeds.
- All transitions are guarded by an `asyncio.Lock`; concurrent D-Bus calls
  cannot double-start the recorder.
- `Cancel` kills the recorder while recording, and sets a `threading.Event`
  during transcription/typing that is checked between Whisper segments /
  typed keys.
- Recording auto-stops at `max-duration` (default 120 s) and transcribes
  what was captured.

## D-Bus API (`org.lebi.Dictator` at `/org/lebi/Dictator`)

| Member | Type | Description |
|---|---|---|
| `Toggle() → s` | method | Start, or stop+transcribe+type. Returns new state. |
| `StartRecording() → b` | method | Start capture. |
| `StopRecording() → s` | method | Stop, transcribe, type. Returns text. |
| `Cancel() → b` | method | Abort current operation (any state). |
| `GetState() → s` | method | Current state string. |
| `Configure(a{sv})` | method | Apply settings: `model` (s), `output-mode` (s: `clipboard`/`type`), `max-duration` (d). |
| `StateChanged(s)` | signal | State transitions. |
| `TranscriptionReady(s)` | signal | Final text (may be empty). |
| `Error(s)` | signal | Human-readable error. |
| `AudioLevel(d)` | signal | RMS 0–1, ~10 Hz while recording. |
| `State`, `LastError`, `LastTranscription` | properties | Read-only. |

## Settings flow

GSettings schema (`org.gnome.shell.extensions.dictator`) is owned by the
extension. On service appearance and on every change, the extension pushes
`model`, `output-mode`, and `max-duration` to the service via `Configure`.
`show-overlay` / `show-notifications` / `shortcut` are applied extension-side.
The service itself has no GSettings dependency (its venv has no PyGObject).

## Text output strategy

1. **Paste (default, `output-mode=clipboard`)**: save clipboard → set text
   (`wl-copy` on Wayland, `xclip` on X11) → inject Ctrl+V through uinput →
   restore clipboard. Instant for long text, keyboard-layout independent.
2. **Type (`output-mode=type`)**: per-character key events from a complete
   US-layout map (`typer._build_keymap`). Used as automatic fallback when no
   clipboard tool exists. Note: most terminals expect Ctrl+Shift+V to paste.

## Service lifecycle

`systemd/dictator.service` is `Type=dbus` with `BusName=org.lebi.Dictator`,
and the D-Bus activation file declares `SystemdService=dictator.service` —
so D-Bus activation and systemd manage a single instance. The extension also
watches the bus name to re-sync UI state if the service crashes/restarts.

## Tests

`service/tests/` (pytest + pytest-asyncio). Hardware deps (`evdev`,
`faster-whisper`) are stubbed in `conftest.py`, so the suite runs anywhere:

```bash
python3 -m venv .venv && .venv/bin/pip install -r service/dev-requirements.txt
.venv/bin/python -m pytest service/tests/
.venv/bin/ruff check service/
```

CI: `.github/workflows/ci.yml` (ruff + pytest on Python 3.10–3.13, shell
syntax checks, strict schema compile).
