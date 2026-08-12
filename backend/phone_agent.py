"""
phone_agent.py — Vision-guided Android phone agent.

JASVA sees the phone screen (via ADB screenshots), sends the current screen to
a vision LLM along with the user's task, executes the single action the model
picks (tap/swipe/type/key/open/back/home...), re-screenshots, and repeats until
the task is complete.
"""

import os
import time
import base64

from backend.adb_manager import adb_manager
from backend.ai_services import (
    call_gemini_api_direct, extract_json_response,
    emit_agent_event, get_all_available_keys
)
from backend.sys_utils import logger, ROOT_DIR

PHONE_SCREENSHOTS_DIR = os.path.join(ROOT_DIR, "phone_screenshots")

MAX_STEPS = 8
_AGENT_CAPTURE = os.path.join(PHONE_SCREENSHOTS_DIR, "_agent_capture.png")

# Named Android keycodes the agent is allowed to send.
_KEYCODES = {
    "home": 3, "back": 4, "call": 5, "endcall": 6,
    "volumeup": 24, "volumedown": 25, "power": 26, "camera": 27,
    "clear": 28, "dpad_up": 19, "dpad_down": 20, "dpad_left": 21, "dpad_right": 22,
    "ok": 23, "center": 23, "tab": 61, "space": 62, "enter": 66, "backspace": 67,
    "menu": 82, "search": 84, "escape": 111, "del": 67, "recents": 187, "apps": 187,
}

# Common app names -> Android package names so the agent can launch them directly.
COMMON_APPS = {
    "youtube": "com.google.android.youtube",
    "whatsapp": "com.whatsapp",
    "instagram": "com.instagram.android",
    "twitter": "com.twitter.android",
    "x": "com.twitter.android",
    "facebook": "com.facebook.katana",
    "chrome": "com.android.chrome",
    "browser": "com.android.chrome",
    "spotify": "com.spotify.music",
    "gmail": "com.google.android.gm",
    "maps": "com.google.android.apps.maps",
    "camera": "com.android.camera",
    "phone": "com.android.dialer",
    "dialer": "com.android.dialer",
    "contacts": "com.android.contacts",
    "settings": "com.android.settings",
    "netflix": "com.netflix.ninja",
    "prime video": "com.amazon.avod.thirdpartyclient",
    "play store": "com.android.vending",
    "playstore": "com.android.vending",
    "files": "com.android.documentsui",
    "clock": "com.android.deskclock",
    "calculator": "com.android.calculator2",
    "messages": "com.android.messaging",
    "photos": "com.google.android.apps.photos",
    "gallery": "com.android.gallery3d",
    "yt music": "com.google.android.apps.youtube.music",
    "music": "com.google.android.apps.youtube.music",
    "samsung internet": "com.sec.android.app.sbrowser",
    "samsung gallery": "com.sec.android.gallery3d",
    "calculator samsung": "com.sec.android.app.popupcalculator",
    "clock samsung": "com.sec.android.app.clockpackage",
    "google": "com.google.android.googlequicksearchbox",
    "youtube music": "com.google.android.apps.youtube.music",
    "prime": "com.amazon.avod.thirdpartyclient",
}


def _get_target():
    devices = adb_manager.list_devices()
    active = [d for d in devices if d["status"] == "device"]
    if not active:
        return None
    # Prefer wireless (ip:port) targets over USB serials, like mirror auto-detect.
    for d in active:
        if ":" in d["id"]:
            return d["id"]
    return active[0]["id"]


def _capture(target):
    os.makedirs(PHONE_SCREENSHOTS_DIR, exist_ok=True)
    res = adb_manager.screenshot(target, _AGENT_CAPTURE)
    if res["status"] != "success":
        return {"status": "error", "message": res.get("message", "Screenshot failed")}
    return {"status": "success", "path": _AGENT_CAPTURE}


def _resolve_keycode(key_text):
    k = key_text.strip().lower()
    if k.isdigit():
        return int(k)
    if k in _KEYCODES:
        return _KEYCODES[k]
    if len(k) == 1 and k.isalpha():
        return 29 + (ord(k.upper()) - ord("A"))
    return None


def _execute_action(target, action, width, height):
    """Execute one agent action string via ADB. Returns a result dict."""
    a = action.strip()
    low = a.lower()

    if low in ("back",):
        return adb_manager.send_key(target, 4)
    if low in ("home", "home screen"):
        return adb_manager.send_key(target, 3)
    if low in ("recents", "apps", "recent"):
        return adb_manager.send_key(target, 187)
    if low in ("enter", "ok", "confirm"):
        return adb_manager.send_key(target, 66)
    if low.startswith("key "):
        keycode = _resolve_keycode(low[4:].strip())
        if keycode is None:
            return {"status": "error", "output": f"Unknown key: {low[4:]}"}
        return adb_manager.send_key(target, keycode)
    if low.startswith("tap "):
        parts = low.split()
        if len(parts) >= 3 and parts[1].isdigit() and parts[2].isdigit():
            return adb_manager.send_tap(target, int(parts[1]), int(parts[2]))
        return {"status": "error", "output": "Invalid tap. Format: tap x y"}
    if low.startswith("swipe "):
        parts = low.split()
        if len(parts) >= 5 and all(p.isdigit() for p in parts[1:5]):
            duration = int(parts[5]) if len(parts) > 5 and parts[5].isdigit() else 300
            return adb_manager.send_swipe(
                target, int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4]), duration
            )
        return {"status": "error", "output": "Invalid swipe. Format: swipe x1 y1 x2 y2 [duration_ms]"}
    if low.startswith("type "):
        text = a[5:]
        if not text:
            return {"status": "error", "output": "Nothing to type."}
        return adb_manager.send_text(target, text)
    if low.startswith("open ") or low.startswith("launch "):
        app = low[5:].strip()
        if "." in app:
            pkg = app
        else:
            pkg = COMMON_APPS.get(app, app)
        res = adb_manager.launch_app(target, pkg)
        if res["status"] == "success":
            return {"status": "success", "output": f"Launched '{app}'."}
        return {"status": "error", "output": f"Could not launch '{app}'. Navigate by tapping its icon on the home screen or app drawer instead."}
    return {"status": "error", "output": f"Unknown action: {action}"}


def _build_prompt(task, width, height, steps, step, max_steps):
    history_text = ""
    if steps:
        lines = []
        for i, s in enumerate(steps):
            result = str(s.get("result", "")).strip()
            lines.append(f"{i + 1}. {s['action']} — result: {result[:140]}")
        history_text = "Actions taken so far:\n" + "\n".join(lines) + "\n\n"
    return (
        f"Screen: {width}x{height} pixels. Coordinates (0,0) is the top-left corner. "
        f"Always tap/swipe using these pixel coordinates.\n"
        f"Task: {task}\n"
        f"Step {step}/{max_steps}.\n"
        f"{history_text}"
        f"Here is the current phone screen. Decide the single best next action."
    )


def _ask_vision(task, image_b64, mime, width, height, steps, step, max_steps):
    """Send the screenshot to Gemini and get the next action JSON."""
    available = get_all_available_keys()
    gemini_keys = [k for k in available if k["provider"] == "gemini"]
    if not gemini_keys:
        return {"error": "No Gemini API key is configured. Phone screen vision requires a Gemini key — add one in Settings."}

    system = (
        "You are JASVA, an autonomous assistant controlling an Android phone through ADB. "
        "You can SEE the phone's screen in every message. Choose exactly ONE action per turn, "
        "based only on what is visible in the screenshot, to complete the user's task step by step.\n\n"
        "Available actions (return exactly one):\n"
        "- tap <x> <y>  — tap a point (pixel coords)\n"
        "- swipe <x1> <y1> <x2> <y2> <duration_ms>  — scroll/drag\n"
        "- type <text>  — type text into the focused field (no quotes)\n"
        "- key <keycode>  — send a hardware key: 3=home, 4=back, 187=recents, 66=enter, 67=backspace, 61=tab, 29-54=letters A-Z\n"
        "- open <app>  — launch a known app, e.g. open youtube, open settings, open whatsapp\n"
        "- back | home | recents | enter\n"
        "- done  — the task is fully complete; give the final summary\n\n"
        "Rules:\n"
        "- Text fields: tap the field first, then use 'type'.\n"
        "- If you don't see what you need, scroll (swipe) or go back.\n"
        "- Do NOT repeat the exact same action twice in a row.\n"
        "- Reply with ONLY valid JSON:\n"
        '{"reason": "why this action", "action": "one action", "reply": "short status for the user; final summary when done"}'
    )

    contents = [
        {"role": "user", "parts": [{"text": system}]},
        {"role": "model", "parts": [{"text": "Understood. I will observe each screenshot and choose one action at a time."}]},
        {"role": "user", "parts": [{"text": _build_prompt(task, width, height, steps, step, max_steps)}]},
    ]

    last_error = None
    for key_info in gemini_keys:
        api_key = key_info["key"]
        try:
            llm_res = call_gemini_api_direct(
                task, api_key, contents=contents,
                system_instruction=system,
                image_base64=image_b64, image_mime=mime
            )
            if isinstance(llm_res, dict) and llm_res.get("reply") and any(
                err in llm_res.get("reply", "").lower()
                for err in ("api error", "rate limit", "quota", "authentication failed", "http error")
            ):
                last_error = llm_res["reply"]
                continue
            return llm_res
        except Exception as e:
            last_error = str(e)
            logger.error(f"Phone agent Gemini call failed: {e}")
    if last_error:
        return {"error": last_error}
    return {"error": "Phone vision model unavailable."}


def run_phone_agent(task, window=None):
    """See the phone screen and autonomously operate it to complete `task`."""
    target = _get_target()
    if not target:
        return {"status": "error", "output": "No connected phone found. Link your phone first, then ask me again."}

    size = adb_manager.get_screen_size(target)
    width, height = size if size else (1080, 2400)

    logger.info(f"Phone agent starting for task: {task} (target={target}, screen={width}x{height})")
    emit_agent_event(window, "start", {"goal": f"On phone: {task}"})

    steps = []
    final_reply = ""
    last_action = None
    repeats = 0

    for step in range(1, MAX_STEPS + 1):
        shot = _capture(target)
        if shot["status"] != "success":
            emit_agent_event(window, "stop", {"reply": shot["message"]})
            return {"status": "error", "output": shot["message"]}

        with open(shot["path"], "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode("ascii")

        llm_res = _ask_vision(task, image_b64, "image/png", width, height, steps, step, MAX_STEPS)
        if isinstance(llm_res, dict) and llm_res.get("error"):
            emit_agent_event(window, "stop", {"reply": llm_res["error"]})
            return {"status": "error", "output": llm_res["error"]}
        if not isinstance(llm_res, dict) or not llm_res.get("action"):
            msg = "The AI could not decide the next action on your phone."
            emit_agent_event(window, "stop", {"reply": msg})
            return {"status": "error", "output": msg}

        action = str(llm_res.get("action", "")).strip()
        reason = str(llm_res.get("reason", "")).strip()
        reply = str(llm_res.get("reply", "")).strip()
        final_reply = reply or "Working on it..."

        emit_agent_event(window, "thought", {
            "thought": reason, "current_step": action, "reply": reply, "emotion": "focused"
        })

        if not action or action.lower() in ("done", "complete", "finish", "stop"):
            break

        if action.lower() == last_action:
            repeats += 1
        else:
            repeats = 0
        last_action = action.lower()
        if repeats >= 2:
            final_reply = f"I might be stuck repeating the same action. Last screen state: {reply}"
            emit_agent_event(window, "action", {"command": action, "status": "Retry limit", "output": ""})
            break

        result = _execute_action(target, action, width, height)
        status_str = "Success" if result.get("status") == "success" else "Error"
        out_str = result.get("output", "")
        emit_agent_event(window, "action" if status_str == "Success" else "observation", {
            "command": action, "status": status_str, "output": out_str[:500]
        })
        steps.append({"action": action, "reason": reason, "result": out_str})

        if status_str == "Error":
            if step >= MAX_STEPS:
                final_reply = f"Could not complete the task. Last error: {out_str}"
                break
        time.sleep(1.0)

    if not final_reply:
        final_reply = "I finished operating the phone."
    emit_agent_event(window, "stop", {"reply": final_reply})
    return {"status": "success", "output": final_reply}
