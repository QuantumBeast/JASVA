# JASVA

A Windows desktop AI assistant with a frameless, multi-window holographic interface — built with Python ([pywebview](https://pywebview.flowrl.com/)) and a custom HTML/CSS/JS frontend. Talks to you, remembers things, and controls your PC, Android phone, and Android TV.

## Features

- AI conversation & NLP (intent, sentiment, entities) with Gemini, Groq, Puter, OpenRouter + offline mode
- Persistent memory, notes, alarms, timers, notifications
- PC control: apps, files, volume, brightness, media keys, clipboard, Wi-Fi/Bluetooth, screenshots
- Phone & TV control over ADB, including an autonomous "phone do …" vision agent
- Web automations: YouTube, Spotify, Netflix, GitHub, Google, weather
- System tray, autostart, single-instance lock, crash recovery, multi-device HTTP/WS server

## Quick Start

```bash
pip install -r requirements.txt
python app.pyw            # or: pythonw app.pyw (no console) | --dev for hot-reload
```

Add API keys in the **Settings** panel or in `backend/.env` (git-ignored):

```env
GEMINI_API_KEY=...
GROQ_API_KEY=...
PUTER_API_KEY=...
ELEVENLABS_API_KEY=...
```

Connect devices (optional): `phone connect <ip:port>` / `tv connect <ip>` after enabling ADB over Wi-Fi.

## Build EXE

```bash
pyinstaller JASVA.spec    # → dist/JASVA.exe
```

## Structure

- `app.pyw` — main launcher: creates the webview windows, tray, autostart, crash recovery
- `backend/` — Python engine (commands, AI, NLP, memory, ADB, TV, phone agent)
- `frontend/` — UI panels (chat, sphere, monitor, control, settings, remotes)

> Windows only. No virtual environments — run Python and PyInstaller directly (see `.agents/AGENTS.md`).
