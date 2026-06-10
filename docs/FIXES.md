# Fixes — 2026-06-10 overhaul

All issue numbers refer to the audit in [ISSUES.md](ISSUES.md).

## Service

| # | Issue | Fix |
|---|---|---|
| 1 | Most punctuation silently dropped (dead shift-handling code) | `typer.py` rewritten: complete US-layout keymap built programmatically (`_build_keymap`), every printable ASCII char covered (tested). Default output is now clipboard-paste, which is layout-independent. |
| 3 | Sticky ERROR state bricked the shortcut | `error` is a startable state; `Cancel` also clears it. |
| 4 | Start-recording race (double pw-record) | All transitions behind `asyncio.Lock`; concurrency covered by tests. |
| 6 | SIGTERM crashed shutdown (`loop.stop()` inside `asyncio.run`) | Signal handlers set an `asyncio.Event`; clean teardown of recorder/typer/bus. |
| 8 | Typer swallowed errors (fake success on uinput permission failure) | `TyperError` raised and surfaced via the `Error` signal → notification. |
| 9 | pw-record failures undetected at start; stderr never drained; no duration cap | Recorder rewritten: in-memory stdout capture, 300 ms fail-fast startup check with stderr in the message, `max-duration` auto-stop. |
| 10 | Whisper model loaded lazily in the hot path | Background preload at service start with `loading`/`downloading` states; model kept warm. |
| 11 | CUDA detected via `nvidia-smi` | `ctranslate2.get_cuda_device_count()`; CPU fallback retained; greedy decoding (beam 1) on CPU for ~2x lower latency. |
| 21 | Cancel couldn't abort transcription/typing | `threading.Event` checked between Whisper segments and typed keys. |
| — | Audio written to /tmp | Audio now never touches disk (privacy + speed). |

## Extension

| # | Issue | Fix |
|---|---|---|
| 5 | GNOME 45 notification crash + Source leak | Version branch for the MessageTray API; one persistent source. |
| 7 | Settings defined but ignored | Extension pushes `model`/`output-mode`/`max-duration` via new `Configure(a{sv})`; overlay/notification toggles respected. |
| 13 | Sync proxy construction; no crash recovery | Async proxy callback; `Gio.bus_watch_name` re-syncs state when the service (re)appears. |
| 17 | Spawned `gnome-extensions prefs` | `this._extension.openPreferences()`. |
| 18 | Deprecated `log()` | `console.log`/`console.error`. |
| 19 | Overlay off-center on first show, never destroyed | New overlay pill repositions on `notify::width`, fades in/out, destroyed with the indicator. |
| 20 | Prefs only had the shortcut | Full Adwaita page: model, max duration, output mode, overlay/notification switches. |
| — | UI | New overlay: pulsing dot, live audio-level bars (AudioLevel signal), elapsed timer, transcription spinner, "✓ result" toast, error toast; optimistic overlay on shortcut press. |

## Packaging / install

| # | Issue | Fix |
|---|---|---|
| 2 | `apt-get install` inside postinst (impossible under dpkg lock) | Removed, along with the debconf GPU question; postinst prints pip-based GPU guidance. |
| 12 | systemd unit + D-Bus activation could fight | `Type=dbus` + `BusName=` paired with `SystemdService=`. |
| 15 | Unpinned pip installs at install time | `service/requirements.txt` (pinned); used by installer, deb setup, CI. |
| 16 | Wrong Documentation URL | Fixed. |
| 23 | Inconsistent shortcut naming | Shift+Ctrl+Space everywhere. |
| 24 | Two divergent installers | `scripts/install.sh` is now a wrapper for the root `install.sh`. |
| — | deb had no real first-run path | New `dictator-setup` (in `/usr/bin`) creates the per-user venv from pinned requirements and installs user units. |
| — | e.g.o zip missing prefs.js | `scripts/build-extension.sh` now ships it. |

## New

- `cli/dictator` — POSIX-sh D-Bus wrapper (`toggle|start|stop|cancel|status`)
  so KDE/Sway/any desktop can bind a hotkey (#cross-platform).
- `service/tests/` — 44 tests (state machine, races, cancel paths, keymap,
  recorder, transcriber fallback); `.github/workflows/ci.yml` runs ruff +
  pytest on Python 3.10–3.13.
- `docs/architecture.md` — component/state/D-Bus reference.

## Known remaining (#14 partially, by design)

- Type mode is US-layout only; non-ASCII text requires paste mode.
- Paste mode sends Ctrl+V, which terminals interpret literally; use type
  mode or the terminal's own paste shortcut.
- Clipboard restore on Wayland is best-effort (`wl-copy` ownership timing).
