"""
pc_agent.py — Vision-guided PC Desktop Agent for JASVA.
──────────────────────────────────────────────────────────
JASVA sees the PC screen live in-memory (zero files on disk),
sends live screenshot frames to multimodal AI, and controls the
mouse and keyboard across any browser, app, or window with
precision coordinate scaling and native Windows input events.
"""

import io
import time
import base64
import os
import re
import ctypes
from PIL import Image

try:
    import pyautogui
    pyautogui.FAILSAFE = False
    pyautogui.PAUSE = 0.05
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False

try:
    import pyperclip
    PYPERCLIP_AVAILABLE = True
except ImportError:
    PYPERCLIP_AVAILABLE = False

from backend.ai_services import (
    call_gemini_api_direct, extract_json_response,
    emit_agent_event, get_all_available_keys
)
from backend.sys_utils import logger

MAX_PC_STEPS = 8

# Win32 Mouse Event Constants
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_ABSOLUTE = 0x8000


def get_screen_dimensions():
    """Get physical screen resolution aware of DPI scaling."""
    try:
        user32 = ctypes.windll.user32
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor DPI aware
        except Exception:
            try:
                user32.SetProcessDPIAware()
            except Exception:
                pass
        w = user32.GetSystemMetrics(0) or 1920
        h = user32.GetSystemMetrics(1) or 1080
        return w, h
    except Exception:
        return 1920, 1080


def capture_pc_screen_live(max_width=1920, quality=85):
    """
    Capture the PC desktop directly into an in-memory buffer without saving any
    temporary files to disk. Returns (base64_str, mime_type, img_w, img_h, phys_w, phys_h).
    """
    phys_w, phys_h = get_screen_dimensions()

    # 1. Native Windows GDI BitBlt
    try:
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32

        hdc_screen = user32.GetDC(0)
        hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
        hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, phys_w, phys_h)
        gdi32.SelectObject(hdc_mem, hbmp)
        gdi32.BitBlt(hdc_mem, 0, 0, phys_w, phys_h, hdc_screen, 0, 0, 0x00CC0020)

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ('biSize', ctypes.c_uint32),
                ('biWidth', ctypes.c_int32),
                ('biHeight', ctypes.c_int32),
                ('biPlanes', ctypes.c_uint16),
                ('biBitCount', ctypes.c_uint16),
                ('biCompression', ctypes.c_uint32),
                ('biSizeImage', ctypes.c_uint32),
                ('biXPelsPerMeter', ctypes.c_int32),
                ('biYPelsPerMeter', ctypes.c_int32),
                ('biClrUsed', ctypes.c_uint32),
                ('biClrImportant', ctypes.c_uint32)
            ]

        bih = BITMAPINFOHEADER()
        bih.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bih.biWidth = phys_w
        bih.biHeight = -phys_h  # top-down
        bih.biPlanes = 1
        bih.biBitCount = 32
        bih.biCompression = 0

        raw_buffer = (ctypes.c_char * (phys_w * phys_h * 4))()
        gdi32.GetDIBits(hdc_mem, hbmp, 0, phys_h, raw_buffer, ctypes.byref(bih), 0)

        img = Image.frombuffer('RGBA', (phys_w, phys_h), bytes(raw_buffer), 'raw', 'BGRA', 0, 1).convert('RGB')

        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(0, hdc_screen)

        img_w, img_h = img.width, img.height
        if img.width > max_width:
            ratio = max_width / float(img.width)
            new_h = int(float(img.height) * ratio)
            img = img.resize((max_width, new_h), Image.Resampling.LANCZOS)
            img_w, img_h = img.width, img.height

        out_buf = io.BytesIO()
        img.save(out_buf, format="JPEG", quality=quality)
        b64 = base64.b64encode(out_buf.getvalue()).decode("utf-8")
        return b64, "image/jpeg", img_w, img_h, phys_w, phys_h
    except Exception as e:
        logger.debug(f"GDI BitBlt capture fallback: {e}")

    # 2. Fallback to PIL ImageGrab
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab(all_screens=False)
        img_w, img_h = img.width, img.height
        if img.width > max_width:
            ratio = max_width / float(img.width)
            new_h = int(float(img.height) * ratio)
            img = img.resize((max_width, new_h), Image.Resampling.LANCZOS)
            img_w, img_h = img.width, img.height
        out_buf = io.BytesIO()
        img.save(out_buf, format="JPEG", quality=quality)
        b64 = base64.b64encode(out_buf.getvalue()).decode("utf-8")
        return b64, "image/jpeg", img_w, img_h, phys_w, phys_h
    except Exception as e:
        logger.error(f"Live screen capture error: {e}")
        return None, None, 1920, 1080, 1920, 1080


def describe_pc_screen(prompt=None, window=None):
    """
    Capture the PC screen live into memory and describe it using Gemini vision.
    Zero files saved to disk.
    """
    b64, mime, img_w, img_h, phys_w, phys_h = capture_pc_screen_live()
    if not b64:
        return {"status": "error", "output": "Failed to capture PC screen."}

    user_query = prompt or "Describe what is currently visible on my desktop screen in detail, highlighting open apps, browser pages, code, text, or errors."
    
    available = get_all_available_keys()
    gemini_keys = [k for k in available if k["provider"] == "gemini"]
    if not gemini_keys:
        return {"status": "error", "output": "No Gemini API key configured. Screen vision requires a Gemini key — set one in Settings."}

    system = (
        "You are JASVA, an advanced holographic desktop AI assistant with live vision of the user's PC screen.\n"
        "The user is showing you their active computer display.\n"
        "Analyze the screenshot carefully. Identify open applications, browser content, IDE/code, terminals, "
        "active windows, error messages, or buttons. Provide a crisp, structured, and helpful response."
    )

    contents = [
        {"role": "user", "parts": [{"text": system}]},
        {"role": "model", "parts": [{"text": "Understood. I can see your live PC screen clearly. How can I assist with what's visible?"}]},
        {"role": "user", "parts": [{"text": f"[LIVE PC SCREEN RESOLUTION: {phys_w}x{phys_h}]\n\n{user_query}"}]}
    ]

    last_error = None
    for key_info in gemini_keys:
        api_key = key_info["key"]
        try:
            llm_res = call_gemini_api_direct(
                user_query, api_key, contents=contents,
                system_instruction=system,
                image_base64=b64, image_mime=mime
            )
            if isinstance(llm_res, dict) and llm_res.get("reply"):
                reply_text = llm_res["reply"]
                if any(err in reply_text.lower() for err in ("api error", "rate limit", "quota", "authentication failed")):
                    last_error = reply_text
                    continue
                return {"status": "success", "output": reply_text}
        except Exception as e:
            last_error = str(e)
            logger.error(f"PC screen vision error: {e}")

    if last_error:
        return {"status": "error", "output": last_error}
    return {"status": "error", "output": "Screen vision service temporarily unavailable."}


def _execute_pc_action(action, img_w, img_h, phys_w, phys_h):
    """
    Execute a single atomic PC automation action using Windows native API
    with automatic coordinate scaling from image coordinates to physical screen.
    """
    a = action.strip()
    low = a.lower()
    user32 = ctypes.windll.user32

    def scale_coords(x_model, y_model):
        sx = int(x_model * (phys_w / float(img_w)))
        sy = int(y_model * (phys_h / float(img_h)))
        sx = max(0, min(phys_w - 1, sx))
        sy = max(0, min(phys_h - 1, sy))
        return sx, sy

    # Click
    if low.startswith("click "):
        parts = low.split()
        if len(parts) >= 3 and parts[1].isdigit() and parts[2].isdigit():
            sx, sy = scale_coords(int(parts[1]), int(parts[2]))
            user32.SetCursorPos(sx, sy)
            time.sleep(0.06)
            user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            time.sleep(0.04)
            user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            return {"status": "success", "output": f"Clicked at ({sx}, {sy})"}
        return {"status": "error", "output": "Invalid click format. Use: click x y"}

    # Double click
    if low.startswith("double_click ") or low.startswith("doubleclick "):
        parts = low.split()
        if len(parts) >= 3 and parts[1].isdigit() and parts[2].isdigit():
            sx, sy = scale_coords(int(parts[1]), int(parts[2]))
            user32.SetCursorPos(sx, sy)
            time.sleep(0.06)
            for _ in range(2):
                user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                time.sleep(0.03)
                user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                time.sleep(0.05)
            return {"status": "success", "output": f"Double-clicked at ({sx}, {sy})"}
        return {"status": "error", "output": "Invalid double_click format. Use: double_click x y"}

    # Right click
    if low.startswith("right_click ") or low.startswith("rightclick "):
        parts = low.split()
        if len(parts) >= 3 and parts[1].isdigit() and parts[2].isdigit():
            sx, sy = scale_coords(int(parts[1]), int(parts[2]))
            user32.SetCursorPos(sx, sy)
            time.sleep(0.06)
            user32.mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
            time.sleep(0.04)
            user32.mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
            return {"status": "success", "output": f"Right-clicked at ({sx}, {sy})"}
        return {"status": "error", "output": "Invalid right_click format. Use: right_click x y"}

    # Drag / Swipe
    if low.startswith("drag ") or low.startswith("swipe "):
        parts = low.split()
        if len(parts) >= 5 and all(p.isdigit() for p in parts[1:5]):
            x1, y1 = scale_coords(int(parts[1]), int(parts[2]))
            x2, y2 = scale_coords(int(parts[3]), int(parts[4]))
            user32.SetCursorPos(x1, y1)
            time.sleep(0.05)
            user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            time.sleep(0.05)
            # Smooth drag in steps
            steps = 10
            for i in range(1, steps + 1):
                cur_x = int(x1 + (x2 - x1) * (i / float(steps)))
                cur_y = int(y1 + (y2 - y1) * (i / float(steps)))
                user32.SetCursorPos(cur_x, cur_y)
                time.sleep(0.02)
            user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            return {"status": "success", "output": f"Dragged from ({x1},{y1}) to ({x2},{y2})"}
        return {"status": "error", "output": "Invalid drag format. Use: drag x1 y1 x2 y2"}

    # Type text
    if low.startswith("type "):
        text = a[5:]
        if not text:
            return {"status": "error", "output": "Nothing to type."}
        if PYPERCLIP_AVAILABLE:
            pyperclip.copy(text)
            time.sleep(0.05)
            if PYAUTOGUI_AVAILABLE:
                pyautogui.hotkey('ctrl', 'v')
            else:
                user32.keybd_event(0x11, 0, 0, 0) # VK_CONTROL down
                user32.keybd_event(0x56, 0, 0, 0) # 'V' down
                time.sleep(0.02)
                user32.keybd_event(0x56, 0, 2, 0) # 'V' up
                user32.keybd_event(0x11, 0, 2, 0) # VK_CONTROL up
        elif PYAUTOGUI_AVAILABLE:
            pyautogui.write(text, interval=0.02)
        return {"status": "success", "output": f"Typed '{text}'"}

    # Press single key
    if low.startswith("press "):
        key = low[6:].strip()
        if PYAUTOGUI_AVAILABLE:
            pyautogui.press(key)
            return {"status": "success", "output": f"Pressed key '{key}'"}
        return {"status": "error", "output": "Key press failed"}

    # Hotkey
    if low.startswith("hotkey "):
        keys = low[7:].strip().split()
        if keys and PYAUTOGUI_AVAILABLE:
            pyautogui.hotkey(*keys)
            return {"status": "success", "output": f"Pressed hotkey {'+'.join(keys)}"}
        return {"status": "error", "output": "Invalid hotkey format. Use: hotkey ctrl v"}

    # Scroll
    if low.startswith("scroll "):
        parts = low.split()
        if len(parts) >= 2:
            try:
                amt = int(parts[1])
                user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, amt, 0)
                return {"status": "success", "output": f"Scrolled {amt}"}
            except ValueError:
                pass
        return {"status": "error", "output": "Invalid scroll format. Use: scroll -300 or scroll 300"}

    # Open App or Website
    if low.startswith("open ") or low.startswith("launch "):
        target = a[a.index(" ") + 1:].strip()
        try:
            from backend.sys_utils import find_shortcut_or_executable
            exe = find_shortcut_or_executable(target)
            if exe:
                os.startfile(exe)
                return {"status": "success", "output": f"Launched '{target}'."}
            else:
                import webbrowser
                if target.startswith("http://") or target.startswith("https://") or "." in target:
                    url = target if target.startswith("http") else f"https://{target}"
                    webbrowser.open(url)
                    return {"status": "success", "output": f"Opened {url}."}
                else:
                    os.system(f"start {target}")
                    return {"status": "success", "output": f"Opening {target}."}
        except Exception as e:
            return {"status": "error", "output": f"Failed to open '{target}': {e}"}

    # Wait
    if low.startswith("wait "):
        try:
            sec = float(low.split()[1])
            time.sleep(min(sec, 5.0))
            return {"status": "success", "output": f"Waited {sec}s"}
        except Exception:
            time.sleep(1.0)
            return {"status": "success", "output": "Waited 1s"}

    return {"status": "error", "output": f"Unknown PC action: {action}"}


def _build_pc_prompt(task, width, height, steps, step, max_steps):
    history_text = ""
    if steps:
        lines = []
        for i, s in enumerate(steps):
            result = str(s.get("result", "")).strip()
            lines.append(f"{i + 1}. {s['action']} — result: {result[:140]}")
        history_text = "Actions executed so far:\n" + "\n".join(lines) + "\n\n"
    return (
        f"Live PC Screen Coordinate Space: {width}x{height} pixels. Top-left coordinate is (0,0).\n"
        f"Goal: {task}\n"
        f"Step {step} of {max_steps}.\n"
        f"{history_text}"
        f"Here is the live screenshot of the PC desktop/browser. Analyze the UI and decide the single best next action."
    )


def _ask_pc_vision(task, image_b64, mime, img_w, img_h, steps, step, max_steps):
    """Send live desktop screenshot to Gemini and receive next action JSON."""
    available = get_all_available_keys()
    gemini_keys = [k for k in available if k["provider"] == "gemini"]
    if not gemini_keys:
        return {"error": "No Gemini API key configured. PC vision requires a Gemini key."}

    system = (
        "You are JASVA, an autonomous AI desktop agent operating a Windows PC and web browser.\n"
        "You receive live screenshots of the user's screen in-memory. Choose exactly ONE action per step "
        "based strictly on what you see on the screen to accomplish the user's task.\n\n"
        "Available actions (return ONE):\n"
        "- click <x> <y>  — Left-click at exact pixel coordinates (e.g. click 450 320)\n"
        "- double_click <x> <y>  — Double-click at coordinates\n"
        "- right_click <x> <y>  — Right-click for context menu\n"
        "- drag <x1> <y1> <x2> <y2>  — Drag mouse\n"
        "- type <text>  — Type text into active focused element/input\n"
        "- press <key>  — Press a single key (e.g. press enter, press esc, press tab, press backspace)\n"
        "- hotkey <k1> <k2>  — Press shortcut (e.g. hotkey ctrl s, hotkey ctrl t, hotkey alt f4, hotkey win r)\n"
        "- scroll <amount>  — Scroll page (e.g. scroll -500 to scroll down, scroll 500 to scroll up)\n"
        "- open <app_or_url>  — Launch app or website directly (e.g. open chrome, open notepad, open youtube.com)\n"
        "- wait <seconds>  — Wait for an app or page to load (e.g. wait 2)\n"
        "- done  — The task is completely accomplished\n\n"
        "Rules:\n"
        "1. Click input fields/search bars first before typing.\n"
        "2. If an action fails or button isn't visible, scroll down/up.\n"
        "3. Reply with ONLY valid JSON without markdown formatting:\n"
        '{"reason": "observation and rationale", "action": "exact single action string", "reply": "short status for user; final answer when done"}'
    )

    contents = [
        {"role": "user", "parts": [{"text": system}]},
        {"role": "model", "parts": [{"text": "Understood. I will examine each live PC screenshot and choose one precise action at a time."}]},
        {"role": "user", "parts": [{"text": _build_pc_prompt(task, img_w, img_h, steps, step, max_steps)}]}
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
            logger.error(f"PC agent Gemini call failed: {e}")
    if last_error:
        return {"error": last_error}
    return {"error": "PC vision model unavailable."}


def run_pc_agent(task, window=None):
    """
    Autonomously operate the PC desktop and browser using live vision and mouse control.
    """
    logger.info(f"PC Agent starting for task: '{task}'")
    emit_agent_event(window, "start", {"goal": f"On PC: {task}"})

    # Momentarily minimize JASVA if needed so desktop & browser are in view
    if window:
        try:
            window.minimize()
            time.sleep(0.3)
        except Exception:
            pass

    steps = []
    final_reply = ""
    last_action = None
    repeats = 0

    for step in range(1, MAX_PC_STEPS + 1):
        b64, mime, img_w, img_h, phys_w, phys_h = capture_pc_screen_live()
        if not b64:
            err_msg = "Could not capture PC desktop screen."
            emit_agent_event(window, "stop", {"reply": err_msg})
            return {"status": "error", "output": err_msg}

        llm_res = _ask_pc_vision(task, b64, mime, img_w, img_h, steps, step, MAX_PC_STEPS)

        if isinstance(llm_res, dict) and llm_res.get("error"):
            emit_agent_event(window, "stop", {"reply": llm_res["error"]})
            if window:
                try:
                    window.restore()
                except Exception:
                    pass
            return {"status": "error", "output": llm_res["error"]}

        # If LLM returned raw text in reply, try extracting JSON
        if isinstance(llm_res, dict) and not llm_res.get("action") and llm_res.get("reply"):
            parsed = extract_json_response(llm_res["reply"])
            if parsed and isinstance(parsed, dict) and parsed.get("action"):
                llm_res = parsed

        if not isinstance(llm_res, dict) or not llm_res.get("action"):
            msg = "Could not determine next action on PC screen."
            emit_agent_event(window, "stop", {"reply": msg})
            if window:
                try:
                    window.restore()
                except Exception:
                    pass
            return {"status": "error", "output": msg}

        action = str(llm_res.get("action", "")).strip()
        reason = str(llm_res.get("reason", "")).strip()
        reply = str(llm_res.get("reply", "")).strip()
        final_reply = reply or "Executing action on PC..."

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
            final_reply = f"Detected loop on PC screen action. State: {reply}"
            emit_agent_event(window, "action", {"command": action, "status": "Retry limit", "output": ""})
            break

        result = _execute_pc_action(action, img_w, img_h, phys_w, phys_h)
        status_str = "Success" if result.get("status") == "success" else "Error"
        out_str = result.get("output", "")

        emit_agent_event(window, "action" if status_str == "Success" else "observation", {
            "command": action, "status": status_str, "output": out_str[:500]
        })
        steps.append({"action": action, "reason": reason, "result": out_str})

        if status_str == "Error" and step >= MAX_PC_STEPS:
            final_reply = f"Could not complete PC task. Last error: {out_str}"
            break

        time.sleep(0.8)

    if not final_reply:
        final_reply = "PC task finished, sir."

    if window:
        try:
            window.restore()
        except Exception:
            pass

    emit_agent_event(window, "stop", {"reply": final_reply})
    return {"status": "success", "output": final_reply}
