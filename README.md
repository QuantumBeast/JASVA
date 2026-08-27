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


## 🚀 Getting Started

> **Windows only** · Python 3.10+ · no virtual environments (see [Project Rules](#project-rules))

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Add API keys

Create `backend/.env` (git-ignored), or set them in the **Settings** panel:

```env
GEMINI_API_KEY=...
ELEVENLABS_API_KEY=...
```

### 3. Run

```bash
python app.pyw    # pythonw app.pyw runs without a console
```

### 4. Connect devices (optional)

Enable ADB over Wi-Fi, then `phone connect <ip:port>` / `tv connect <ip>` — saved IPs auto-connect on startup.

## 🗣 Example Commands

```
open spotify and play jazz        play the first YouTube result
phone do open YouTube and play lo-fi    (autonomous phone task agent)
tv launch netflix                 tv play youtube "trailer"
set a timer for 5 minutes         remember my coffee order
what's the weather in tokyo       lock pc / volume 40 / screenshot
```


## 📄 License

This project is currently unlicensed — all rights reserved by the author.
