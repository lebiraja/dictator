# Dictator — Codebase Audit (2026-06-10)

> **Status: RESOLVED** — all findings below were addressed in the 2026-06-10
> overhaul. See [FIXES.md](FIXES.md) for what was done per issue and the few
> intentional limitations that remain. This file is kept as the historical audit.

Full review of service/, extension/, debian/, systemd/, and install scripts.
Severity: 🔴 broken/bug · 🟠 reliability/correctness risk · 🟡 quality/UX · 🔵 missing feature.

---

## 🔴 Critical bugs

### 1. Typer: shift-punctuation code is dead — most punctuation is silently dropped
`service/typer.py:72-99` — the loop gates on `if char in self._char_map:`, but `:` `;` `@ # $ % ^ & * ( ) + { } | < > / \ = [ ]` are **not** in `_char_map`. The entire shift-handling block (lines 78–99) that maps them is unreachable; those characters hit the `else` and are logged as "unsupported". Whisper output containing `:` or `;` loses characters.
Also: assumes US QWERTY layout only; no support for non-ASCII at all.
**Fix direction:** build the map completely (or generate from a layout table), or switch strategy: copy to clipboard + inject Ctrl+V, with char-typing as fallback.

### 2. `apt-get install` inside debian postinst can never work
`debian/postinst` runs `apt-get install -y nvidia-cuda-toolkit` while dpkg holds the lock — it will always fail (and is a Debian Policy violation). The GPU debconf option is therefore non-functional. Use `Recommends:`/`Suggests:` or instruct the user instead.

### 3. ERROR state is sticky — service bricks itself until manual Cancel
`service/dictator_service.py:86` — `_do_start_recording` requires `IDLE`, and `Toggle` only acts on `IDLE`/`RECORDING`. After any error the service sits in `ERROR` and the keyboard shortcut does nothing forever. The user must find the panel menu → Cancel. `Toggle` should treat `ERROR` as `IDLE` (or auto-reset to IDLE after emitting the error).

### 4. Race condition: concurrent StartRecording/Toggle calls
`dictator_service.py:84-103` — the state check and `await self.recorder.start()` are not atomic. Two rapid D-Bus calls both pass the `IDLE` check before state flips to `RECORDING` → two `pw-record` processes, one leaked along with its temp file (and `Recorder.start` raises "Already recording" into an inconsistent state). Needs an `asyncio.Lock` around the state machine.

### 5. Extension notifications likely crash on GNOME 45
`extension/extension.js:302-317` — `new MessageTray.Source({title, iconName})` / `new MessageTray.Notification({source, title, body})` is the GNOME 46+ constructor API; GNOME 45 uses positional args (`new MessageTray.Source('Dictator', 'icon-name')`). `metadata.json` claims 45–49 support. Either drop 45 or branch on shell version. Also a **new Source is added to the message tray for every notification and never destroyed** — leaks sources.

### 6. Shutdown crash on SIGTERM/SIGINT
`dictator_service.py:227-232` — the signal handler calls `loop.stop()` while `asyncio.run()` is awaiting `wait_for_disconnect()`. That raises `RuntimeError: Event loop stopped before Future completed`, so every systemd stop "fails". Set an `asyncio.Event` (or cancel the main task) instead of `loop.stop()`.

---

## 🟠 Reliability / correctness

### 7. Settings exist but are ignored by the service
`extension/schemas/...gschema.xml` defines `model` (default `small.en`), `output-mode` (default `clipboard`!), `show-overlay`, `show-notifications` — **none are read anywhere**:
- Service hardcodes `Transcriber(model_size="base.en")` (`transcriber.py:13`), contradicting both the schema default and commit a70ceff ("set default model to small.en").
- `output-mode` default is `clipboard` but the service always types via uinput.
- Overlay and notifications always show regardless of the toggles.
The extension should pass config to the service (D-Bus properties/method args) and respect the booleans locally.

### 8. Typer swallows all errors — service reports success on failure
`typer.py:119-124` — `type_text` catches every exception and just logs. If `/dev/uinput` permission is missing (the #1 setup failure), the user gets state TYPING → IDLE → "Dictation Complete" notification and **nothing typed**, with no error surfaced. Re-raise so `_do_stop_recording` reports it.

### 9. Recorder never checks that pw-record actually started capturing
`recorder.py:56-62` — if `pw-record` exits immediately (no mic, PipeWire down), `start()` still returns success; the failure only surfaces at `stop()` as "no audio file created" (or worse, an empty/header-only WAV that Whisper chokes on). After spawn, poll `returncode` briefly and read the captured stderr for diagnostics. Also `stderr=PIPE` is never drained (potential pipe-buffer stall on chatty output) and there's no max-duration cap — a forgotten recording fills `/tmp` and produces a huge transcription job.

### 10. Whisper model is loaded lazily on first use, inside the hot path
`transcriber.py:39` — first dictation pays model download+load time (tens of seconds to minutes) while the user waits in `TRANSCRIBING` with no feedback; the schema/extension even define a `downloading` state/color that is never emitted. Preload at service start (background task) and emit `downloading`.

### 11. CUDA detection via `nvidia-smi` is insufficient
`transcriber.py:21` — `nvidia-smi` existing doesn't mean cuBLAS/cuDNN wheels are present (install.sh only adds them sometimes). The fallback paths exist but a CUDA failure mid-transcription pays a full retry; worse, `transcribe()` recursion after fallback re-checks `os.path.exists` etc. Detect by attempting `ctranslate2.get_cuda_device_count()` once at startup.

### 12. Dual service launch: systemd unit + D-Bus activation
`systemd/dictator.service` and `service/org.lebi.Dictator.service` both launch the same script. If systemd's copy is running and D-Bus activation triggers (or vice-versa), the second instance fails `request_name` and exits; with `Restart=on-failure` this can loop. Use `Type=dbus` + `BusName=org.lebi.Dictator` in the unit and `SystemdService=` in the D-Bus service file.

### 13. Extension: synchronous D-Bus proxy construction blocks the shell
`extension.js:149` — `new DictatorProxy(...)` without an async ready-callback does blocking I/O on the compositor thread. Pass the async callback form. Also no `g-name-owner` watch: if the service crashes/restarts, the panel keeps stale state and never re-syncs.

---

## 🟡 Quality / UX / packaging

14. **No tests at all.** No pytest, no CI. The state machine, typer mapping, and recorder lifecycle are all unit-testable.
15. **Unpinned runtime pip installs.** `scripts/install.sh:63` and install.sh install `dbus-next evdev faster-whisper` unpinned at install time; debian package installs deps "automatically on first use". One upstream release can break every user. Ship a pinned `requirements.txt`.
16. `systemd/dictator.service` Documentation URL points to `github.com/lebi/dictator` (wrong user, should be `lebiraja`).
17. `extension.js:141` — opens prefs by spawning `gnome-extensions prefs`; GNOME ships `this._extension.openPreferences()` for exactly this.
18. `extension.js` uses deprecated `log()`; use `console.log/console.error`.
19. Overlay (`_showOverlay`) positions itself using `this._overlay.width` before first layout → first show can be off-center; it is also never destroyed on hide, and ignores `show-overlay`.
20. `prefs.js` has no UI for `model`, `output-mode`, `show-overlay`, `show-notifications` — only the shortcut. Settings page should expose all schema keys.
21. `Cancel` D-Bus method can't cancel transcription/typing (only recording); the menu shows Cancel during those states but it just flips the label.
22. `transcriber.py` / `typer.py` are missing type hints in places and `is_available()` is a stub returning `True` — dead code.
23. README promises "zero configuration" and Ctrl+Shift+Space, while the default everywhere else is now Shift+Ctrl+Space; postinst banner still says Ctrl+Shift+Space. Trivial but confusing.
24. Two parallel install paths (`install.sh` and `scripts/install.sh`) have drifted (venv pkgs, messaging). Keep one.

---

## 🔵 Cross-platform reality check

Current design is **GNOME-Shell-only** (extension, Main.wm keybinding, St overlay). uinput typing itself is desktop-agnostic, so broadening support means:
- **KDE / other Wayland DEs:** ship a small CLI (`dictator toggle`) that calls the D-Bus method; users bind it to a key via their DE. Costs ~30 lines, unlocks every desktop.
- **X11-only environments without GNOME:** same CLI + optional tray via `StatusNotifierItem`.
- **Layouts/non-English:** the uinput char-map approach fundamentally can't do non-US layouts; clipboard-paste output mode (already in the schema as `output-mode=clipboard`!) is the portable answer and should be implemented first.

---

## Suggested fix order

1. Typer rewrite (clipboard mode + complete char map) — #1, #8, partially 🔵
2. State machine hardening (lock, ERROR recovery, clean shutdown, cancel during transcribe) — #3, #4, #6, #21
3. Wire settings end-to-end (model/output-mode/overlay/notifications + prefs UI) — #7, #20
4. Recorder robustness + model preload with `downloading` state — #9, #10
5. Extension fixes (GNOME 45 notify API, async proxy, name-owner watch, source leak) — #5, #13, #19
6. Packaging cleanup (postinst, systemd Type=dbus, pinned deps, single installer) — #2, #12, #15, #16, #24
7. Tests (pytest for service modules) + CI — #14
8. Cross-desktop CLI entry point — 🔵
