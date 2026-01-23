# GNOME Dictation App (Speech‑to‑Text) using OpenAI Whisper **base.en**  
*A detailed implementation report + references to similar open-source projects*

> Goal: Build a **system-wide dictation** experience on **Linux GNOME**, similar to **Windows + H** — a global shortcut toggles the microphone, recognizes speech using **Whisper base.en**, and inserts the text into the currently focused app.

---

## 1) What you’re building (Product Definition)

### Core UX (Windows + H equivalent)
- Press a global shortcut (example: `Super+H`)
- A small GNOME overlay appears: *Listening…*
- Speak
- Press shortcut again (or auto-stop on silence)
- Transcription happens locally
- Result is either:
  1) **Inserted at cursor** (preferred), OR  
  2) Copied to clipboard with a notification + paste hint

### Why GNOME-specific?
GNOME provides:
- Shell overlay UI
- Global shortcuts via GNOME Shell extension
- Clipboard access via St APIs
- Ability to coordinate a **D‑Bus service** for privileged operations (audio capture, typing)

---

## 2) Architecture Overview

You have 2 strong architectural options:

### Option A — GNOME Shell Extension + Companion D‑Bus Service (Recommended)
This is the pattern used by existing Whisper dictation extensions.

**Components**
1. **GNOME Shell Extension**  
   - Registers global shortcut
   - Shows overlay / indicator
   - Calls D‑Bus service to start/stop recording + transcribe
   - Receives transcription result
   - Places result into clipboard and/or auto-types

2. **D‑Bus Service (User Service via systemd --user)**
   - Captures mic audio (PipeWire / PulseAudio)
   - Saves audio to temp file
   - Runs Whisper base.en transcription locally
   - Emits result back to extension

**Pros**
- Best GNOME integration
- Global shortcut is clean
- Allows UI overlay + tray indicator
- Robust and maintainable

**Cons**
- Requires two pieces (extension + service)

---

### Option B — Standalone GTK App with a Global Shortcut
- GTK4/Libadwaita app runs in background
- Registers global shortcut (less clean than GNOME extension)
- Uses Whisper base.en
- Injects text via clipboard / typing

**Pros**
- Easier to distribute on Flathub/Snap
- Pure app (no extension approval/reviews)

**Cons**
- Global shortcut integration is messy in GNOME  
- Not as “system-level” as Windows dictation UX

---

## 3) Speech-to-Text Engine (Whisper base.en)

### The model
- Use Whisper **base.en** (English-only, good accuracy, lightweight)
- Full offline transcription

### Implementation choices

#### Choice 1: `openai-whisper` Python package
- Install: `pip install -U openai-whisper`
- Pros: official & stable Python API
- Cons: requires Python runtime, torch dependencies (heavier)

#### Choice 2: `whisper.cpp` (recommended for Linux desktop)
- Faster & lighter, no Python required
- Many GNOME dictation projects already use it
- Model: `base.en`

This report focuses on Whisper-based **.en** models; whisper.cpp is strongly recommended for performance and packaging.

---

## 4) Key GNOME Constraints You Must Handle

### Wayland vs X11
**Text injection** differs:

- **X11**: can “type” text using `xdotool` or AT-SPI reliably.
- **Wayland**: direct typing is restricted by design.

✅ Best cross-session approach:
- Always copy transcript to clipboard
- Show notification: “Transcribed — press Ctrl+V to paste”
- Optional Wayland injection via:
  - `wtype` (wlroots based, not universal)
  - AT-SPI if possible
  - “Insert only on X11” fallback (many projects do this)

📌 This should be a first-class design:  
**Auto-insert works on X11. Clipboard mode works everywhere.**

---

## 5) Feature Specification (Full List)

### 5.1 Input / Recording
- Toggle recording from shortcut
- Toggle recording from panel icon
- Auto-stop on silence (configurable)
- Cancel recording (ESC)
- Audio device selection
- Visible mic activity indicator

### 5.2 Transcription Features
- base.en model by default
- Configurable language (future)
- Punctuation & casing toggle
- Remove filler words option (post-processing)
- Streaming partial results (future enhancement)
- Cache model in local storage

### 5.3 Output Modes
1. **Clipboard mode** (default)
2. **Auto-type mode** (X11 only by default)
3. “Append to active field” mode (if AT-SPI can be used)

### 5.4 GNOME UI
- Top panel icon:
  - Gray: idle
  - Red: recording
  - Blue: transcribing
- GNOME modal overlay:
  - “Listening…”
  - timer + waveform (nice-to-have)
- Notifications:
  - “Transcription ready”
  - error notifications
  - “Model missing — click to download”

### 5.5 Preferences UI
- Shortcut remap
- Toggle modes: clipboard vs insert
- Select Whisper model size
- Silence timeout
- Noise suppression
- Enable “auto copy + paste hint”

### 5.6 Logging & Debug
- Verbose logs to `journalctl --user`
- “Diagnostics” page in preferences
- Collect latency metrics: record time, decode time, total time

---

## 6) Detailed Implementation Plan

### Phase 0 — Proof-of-Concept CLI (2–3 days)
Build a CLI that:
1. Records audio from mic
2. Saves to WAV
3. Runs Whisper base.en transcription
4. Copies text to clipboard

**Tools**
- PipeWire: `pw-record`
- Whisper.cpp: `whisper-cli`

Example commands:
```bash
# record audio
pw-record --target 0 --format s16le --rate 16000 /tmp/dictation.wav

# transcribe
./whisper-cli -m models/ggml-base.en.bin -f /tmp/dictation.wav -otxt
```

Success criteria: fast and accurate transcription locally.

---

### Phase 1 — D‑Bus Service + systemd user service (5–7 days)

#### 1) D‑Bus interface design
Service name: `org.lebi.Dictation`  
Object path: `/org/lebi/Dictation`  
Interface:
- `StartRecording() -> ()`
- `StopRecording() -> (s transcript, b ok, s error)`
- Signal: `StateChanged(s state)` where state ∈ {idle, recording, transcribing}

#### 2) Recording method
Use one of:
- `pw-record` subprocess
- PipeWire API bindings (future)

#### 3) Transcription method
Use `whisper.cpp`:
- spawn `whisper-cli`
- parse output text
- return via D‑Bus

#### 4) systemd user service unit
`~/.config/systemd/user/dictation.service`
```ini
[Unit]
Description=GNOME Dictation Whisper D-Bus service

[Service]
ExecStart=/usr/bin/python3 /opt/dictation/service.py
Restart=on-failure

[Install]
WantedBy=default.target
```

---

### Phase 2 — GNOME Shell Extension (7–14 days)

#### 1) Create extension skeleton
```bash
gnome-extensions create dictation@lebi \
  --template=indicator \
  --gettext-domain=dictation
```

#### 2) Implement global shortcut
- Use GNOME Shell keybinding system
- Bind to `toggleDictation()`

#### 3) UI overlay
- Simple modal overlay using St widgets
- Show listening/transcribing state

#### 4) Connect to D‑Bus
- Call service methods Start/Stop
- Listen to StateChanged signal

#### 5) Output handling
- Clipboard: `St.Clipboard.get_default().set_text(...)`
- Auto-type (X11): call helper script

---

### Phase 3 — Auto-insert Text (X11) + fallback (5–7 days)

**X11 insertion**
- Use `xdotool type --clearmodifiers --delay 1 "<text>"`

**Wayland**
- Clipboard-only mode  
- Optional attempt with AT-SPI or `wtype`

---

### Phase 4 — Preferences & Distribution (7–21 days)

#### Preferences UI
- GNOME extension prefs (Gtk4)
- Map shortcut, set mode, silence timeout

#### Packaging
- For GNOME extension:  
  - extension zip bundle
- For service:  
  - install script or Flatpak helper

---

## 7) Security & Privacy Considerations
- Audio stays local
- No network access
- Permission transparency:
  - mic access via PipeWire
  - clipboard access declared in GNOME extension
- Logs should avoid storing raw audio paths or long transcripts unless explicitly enabled

---

## 8) Performance Strategy

### Low latency requirements
- Target: < 1.5× realtime decode for smooth experience
- Use:
  - 16kHz mono
  - short segments (auto-stop silence)
  - optional VAD

### Optimizations
- Use `whisper.cpp` with:
  - BLAS enabled
  - CUDA (optional)
- Keep model resident (future): whisper.cpp server mode

---

## 9) “Similar Projects” to Learn From (Web Research)

Below are real projects that already solve many parts of your problem. Reviewing them will save huge time.

### 9.1 GNOME Speech2Text (Whisper-based)
- GNOME Shell extension using Whisper
- Captures mic audio, runs transcription locally, copies to clipboard
- Requires a companion D‑Bus service  
Sources: GNOME Extensions listings and GitHub.  
- GNOME Extensions: Speech2Text citeturn0search2  
- GitHub: GNOME Speech2Text citeturn0search3  
- OpenAI Whisper discussion pointing to it citeturn0search20  

**Why it matters:**  
This is the closest to your target architecture (extension + D‑Bus).

---

### 9.2 “Speech2Text with Whisper.cpp”
- GNOME extension built specifically around whisper.cpp
- Shortcut toggles record → transcribe → clipboard/typing  
Source: GNOME extension reviews linking repo citeturn0search4turn0search8turn0search17  

---

### 9.3 Blurt (GNOME Shell Extension using whisper.cpp)
- Accurate offline dictation in GNOME
- Keybinding toggle + panel icon
- Uses helper script (`wsi`) and whisper.cpp
Sources: GNOME extension listing + GitHub citeturn0search11turn0search10  

---

### 9.4 whisper.cpp (core engine)
Main repo:
- ggml-org/whisper.cpp citeturn0search7  

This is the best engine option if you want a smooth desktop dictation.

---

### 9.5 Whisper App (Snap)
- GUI app that records and transcribes with Whisper (whisper.cpp)
- Auto-copies transcript to clipboard  
Source: Snap Store listing citeturn0search9  

---

### 9.6 SpeechNote (dictation app)
Mentioned as solution in GNOME community discussions.  
Source: Reddit thread citeturn0search5  

---

### 9.7 Other voice-control tools (inspiration)
A How-To Geek article discusses a newer Linux voice-control app using wake-word, faster-whisper, etc.  
Source: HowToGeek citeturn0search14  

Not dictation-focused, but helpful for wake-word and background service patterns.

---

## 10) Recommended Implementation Stack (Best Practical Choice)

If you want this to be **real-world usable** and ship-quality:

### “Best stack”
- **GNOME Shell extension (JS)** for shortcut + UI
- **D‑Bus service (Python)** for recording + Whisper
- **whisper.cpp base.en** as inference engine
- Clipboard output default + X11 typing optional

### Why
- Mirrors existing proven projects (Speech2Text / Blurt)
- Avoids GNOME’s Wayland restrictions pain
- Fast and offline

---

## 11) Suggested Repo Structure

```text
gnome-dictation/
├── extension/
│   ├── extension.js
│   ├── prefs.js
│   ├── metadata.json
│   ├── schemas/
│   └── stylesheet.css
├── service/
│   ├── dictation_service.py
│   ├── recorder.py
│   ├── whisper_runner.py
│   ├── org.lebi.Dictation.service
│   └── systemd/dictation.service
├── scripts/
│   ├── install.sh
│   ├── uninstall.sh
│   └── x11_type.sh
└── docs/
    └── DESIGN.md
```

---

## 12) Roadmap Enhancements (Future)

### Streaming dictation
- Show partial text while speaking
- Requires chunked inference + buffer management

### VAD
- WebRTC VAD or Silero VAD
- Auto-stop on silence becomes smart

### Post-processing LLM
- Optional: grammar correction / formatting
- “convert to email tone”, “convert to code comment” etc.

### Wake-word activation
- Like voice assistants
- Use `openWakeWord` style approach (inspiration only)

---

## 13) Deliverables Checklist

### MVP
- [ ] Shortcut toggle dictation
- [ ] overlay UI + indicator
- [ ] record audio (PipeWire)
- [ ] transcribe base.en
- [ ] clipboard output

### v1.0
- [ ] preferences UI
- [ ] install script (systemd user service)
- [ ] robust errors
- [ ] X11 auto insert

### v2.0
- [ ] streaming partial results
- [ ] VAD
- [ ] multi-language

---

## References (Web)
- GNOME Speech2Text extension listings citeturn0search2turn0search0turn0search16  
- GNOME Speech2Text GitHub repo citeturn0search3  
- OpenAI Whisper discussion referencing GNOME Speech2Text citeturn0search20  
- Blurt GNOME extension + GitHub citeturn0search11turn0search10  
- whisper.cpp repository citeturn0search7  
- Speech2Text with Whisper.cpp review pages citeturn0search4turn0search8turn0search17  
- Whisper App (Snap) citeturn0search9  
- SpeechNote mention in GNOME community citeturn0search5  
- Voice dictation article (Ubuntu/Wayland workflow inspiration) citeturn0search13  
- Voice-control inspiration citeturn0search14  

---
