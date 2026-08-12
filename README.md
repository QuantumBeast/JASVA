# JASVA — Holographic Desktop AI Assistant

JASVA is a Windows desktop AI assistant presented as a frameless, multi-window
**"holographic" interface**. It is built with Python
([pywebview](https://pywebview.flowrl.com/)) and a custom HTML/CSS/JS frontend,
and it bridges AI conversation with real control of your PC, Android phone, and
Android TV.

![JASVA](frontend/icon.ico)

## ✨ Features

- **Multi-window holographic UI** — ten frameless floating panels (chat core,
  greeting portal, active sphere, cognition log, resource monitor, device
  control, settings, phone/TV remotes) synchronized over a shared JS bridge.
- **AI conversation & NLP** — custom intent classifier, sentiment analysis,
  entity extraction, coreference resolution, and slang normalization that
  routes requests to the right handler fast.
- **Multiple AI backends** — Gemini, Groq, Puter, OpenRouter, OpenAI and
  Anthropic fallbacks with response caching, plus an offline mode with local
  command intercepts.
- **Persistent memory** — remembers facts, identity, preferences, relationships,
  interests, and habits; maintains chat history, conversation summaries, alarms,
  timers, and notifications.
- **Android phone control (ADB)** — remote buttons, taps, typing, app launch,
  screenshots, mirroring — plus an **autonomous vision agent** that looks at the
  phone screen and completes tasks ("phone do open YouTube and play jazz").
- **Android TV control (ADB)** — D-pad/OK/home/back/power, app launch, YouTube
  search & playback, and screen mirroring.
- **PC automation** — open/close apps, file search, notes, clipboard, volume,
  brightness, media keys, Wi-Fi/Bluetooth toggles, lock/sleep, screenshots,
  recycle bin, Start-menu search.
- **Web automations** — YouTube, Spotify, Netflix, GitHub, Slack, Discord, and
  Google search; weather and network status.
- **System extras** — system tray icon, launch-on-boot, single-instance lock &
  wake-up, crash recovery, heartbeat monitoring, media-sync monitor, and a
  multi-device HTTP/WebSocket integration server.

## 🗂 Architecture

```
app.pyw               Entry point — creates all webview windows + system tray,
                      autostart, crash recovery, and the JasvaAPI JS bridge
backend/
  sys_utils.py        Config, credentials, system metrics, PC control helpers
  ai_services.py      AI providers, TTS (ElevenLabs / Edge TTS), web & media
  nlp_engine.py       Intent classification, sentiment, entities, coreference
  command_router.py   Routes commands to handlers, offline fallback, automations
  memory_scheduler.py Memory profile, facts, alarms/timers, notifications
  adb_manager.py      Persistent ADB shell + Android device management
  tv_manager.py       Android TV control (buttons, apps, YouTube, mirror)
  phone_agent.py      Vision-based autonomous phone task agent
  music_monitor.py    Media playback monitoring & control
  multi_device_server.py  HTTP/WebSocket server for remote device integration
frontend/
  index.html          Chat / sphere / monitor / control / settings panels
  chat.js, sphere.js  UI logic and cross-window state sync
  controls.html       Phone & TV remote controls
  music.html, remote.html
JASVA.spec            PyInstaller build spec
```

## 🚀 Getting Started

> **Platform:** Windows (uses `winreg`, `ctypes.windll`, PowerShell, and ADB).
> **Python:** 3.10+ (no virtual environment — see [Project Rules](#project-rules)).

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Add API keys

Open the **Settings** panel inside the app, or create `backend/.env`:

```env
GEMINI_API_KEY=...
GROQ_API_KEY=...
PUTER_API_KEY=...
ELEVENLABS_API_KEY=...
```

API keys are never written to `config.json` — they live in the Windows
credential manager with a `.env` fallback, and `.env` is git-ignored.

### 3. Run

```bash
python app.pyw          # or pythonw app.pyw to run without a console
python app.pyw --dev    # enable frontend hot-reload
python app.pyw --autostart
```

### 4. Connect devices (optional)

- **Android phone / TV:** enable ADB over Wi-Fi on the device, then say
  `phone connect <ip:port>` / `tv connect <ip>` (or set the IPs in Settings).
  Saved IPs auto-connect on startup.

## 🗣 Example Commands

```
open spotify and play jazz        play the first YouTube result
phone do open YouTube and play lo-fi    (autonomous phone task agent)
tv launch netflix                 tv play youtube "trailer"
set a timer for 5 minutes         remember my coffee order
what's the weather in tokyo       lock pc / volume 40 / screenshot
```

## 📦 Building a standalone EXE

```bash
pyinstaller JASVA.spec
```

The spec bundles the frontend assets and icon, producing `dist/JASVA.exe`.

## 🤝 Project Rules

- **No virtual environments** — run Python and PyInstaller directly on the
  local system environment (see `.agents/AGENTS.md`).

## 📄 License

This project is currently unlicensed — all rights reserved by the author.
