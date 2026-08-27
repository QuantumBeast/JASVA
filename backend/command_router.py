import os
import sys
import json
import time
import re
import subprocess
import ctypes
import webbrowser
import urllib.parse
import urllib.request

# Imports from sys_utils
from backend.sys_utils import (
    logger, log_execution_time, DESKTOP_DIR, GAMES_DIR, ROOT_DIR,
    CREATE_NO_WINDOW, read_file, write_file, get_directory_contents,
    get_filtered_recents, get_games, get_system_metrics,
    close_application, take_screenshot, empty_recycle_bin,
    close_explorer_folders, set_brightness, get_brightness,
    send_media_key, get_windows_volume, set_windows_volume,
    set_clipboard_text, get_clipboard_text, clear_clipboard,
    find_shortcut_or_executable, start_menu_search_and_open,
    load_notes, save_notes
)

# Imports from memory_scheduler
from backend.memory_scheduler import (
    add_fact, get_user_profile_string, add_schedule,
    clear_all_memory, forget_about, get_memory_stats
)

# Imports from ai_services
from backend.ai_services import (
    get_cached_network_status, search_youtube, search_spotify,
    play_youtube_first_result, search_web, get_weather,
    run_agentic_loop
)

# Plugin system
from backend.plugins import execute_plugin_command

# Router State
PENDING_SYSTEM_ACTION = None
CURRENT_EXPLORE_DIR = "This PC"
LAST_SCAN_RESULTS = []
SYSTEM_LOGS = []
USER_COMMANDS_HISTORY = []

def add_system_log(message):
    timestamp = time.strftime("%H:%M:%S")
    SYSTEM_LOGS.append(f"[{timestamp}] {message}")
    while len(SYSTEM_LOGS) > 15:
        SYSTEM_LOGS.pop(0)

def add_user_command_history(text):
    if text.strip().lower() not in ("initialize", "init", ""):
        USER_COMMANDS_HISTORY.append(text.strip())
        while len(USER_COMMANDS_HISTORY) > 5:
            USER_COMMANDS_HISTORY.pop(0)

def clean_error_message(e):
    msg = str(e)
    if "]" in msg:
        parts = msg.split("]", 1)
        cleaned = parts[1].strip()
        if cleaned:
            cleaned = cleaned.lstrip(":- ").strip()
            if cleaned:
                return cleaned[0].upper() + cleaned[1:]
    return msg

def is_autostart_enabled():
    """Check if JASVA is currently registered in Windows HKCU Run registry key."""
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
        try:
            val, _ = winreg.QueryValueEx(key, "JASVA")
            winreg.CloseKey(key)
            return bool(val)
        except FileNotFoundError:
            winreg.CloseKey(key)
            return False
    except Exception:
        return False

def set_autostart(enabled):
    """Register or unregister JASVA to run on Windows startup."""
    try:
        import winreg
    except ImportError:
        return False
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    app_name = "JASVA"
    if getattr(sys, 'frozen', False):
        cmd = f'"{sys.executable}" --autostart'
    else:
        pythonw_path = sys.executable.replace("python.exe", "pythonw.exe")
        if not os.path.exists(pythonw_path):
            pythonw_path = sys.executable
        script_path = os.path.abspath(os.path.join(ROOT_DIR, "app.pyw"))
        cmd = f'"{pythonw_path}" "{script_path}" --autostart'
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
        if enabled:
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, cmd)
            logger.info(f"Registered JASVA autostart command: {cmd}")
        else:
            try:
                winreg.DeleteValue(key, app_name)
                logger.info("Unregistered JASVA autostart from Windows registry.")
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        return True
    except Exception as e:
        logger.error(f"Error setting autostart: {e}")
        return False

def load_memory_facts():
    from backend.memory_scheduler import load_profile
    profile = load_profile()
    return profile.get("facts", [])

def save_memory_facts(facts):
    from backend.memory_scheduler import load_profile, save_profile
    profile = load_profile()
    profile["facts"] = facts
    save_profile(profile)

def get_active_phone_id():
    """Get connected ADB device that is specifically a Phone (not the Smart TV)."""
    from backend.adb_manager import adb_manager
    from backend.sys_utils import load_config
    tv_ip = load_config().get("tv_ip", "").strip()
    devices = [d for d in adb_manager.list_devices() if d["status"] == "device"]
    for d in devices:
        dev_id = d["id"]
        if not (tv_ip and (dev_id == tv_ip or dev_id == f"{tv_ip}:5555" or tv_ip in dev_id)):
            return dev_id
    return None

def get_active_tv_id():
    """Get connected ADB device that is specifically the Smart TV."""
    from backend.adb_manager import adb_manager
    from backend.sys_utils import load_config
    tv_ip = load_config().get("tv_ip", "").strip()
    if not tv_ip:
        return None
    devices = [d for d in adb_manager.list_devices() if d["status"] == "device"]
    for d in devices:
        dev_id = d["id"]
        if tv_ip in dev_id or dev_id == f"{tv_ip}:5555":
            return dev_id
    return f"{tv_ip}:5555"

def handle_offline_fallback(prompt):
    from backend.sys_utils import load_config
    prompt_lower = prompt.lower().strip()
    matched_cmd = None
    if "open notepad" in prompt_lower or "launch notepad" in prompt_lower:
        matched_cmd = "open notepad"
    elif "open calculator" in prompt_lower or "launch calculator" in prompt_lower:
        matched_cmd = "open calculator"
    elif "open paint" in prompt_lower or "launch paint" in prompt_lower:
        matched_cmd = "open paint"
    elif "lock pc" in prompt_lower or "lock computer" in prompt_lower:
        matched_cmd = "lock pc"
    elif "turn off wifi" in prompt_lower or "disable wifi" in prompt_lower:
        matched_cmd = "turn off wifi"
    elif "turn on wifi" in prompt_lower or "enable wifi" in prompt_lower:
        matched_cmd = "turn on wifi"
    elif "screenshot" in prompt_lower or "take screenshot" in prompt_lower:
        matched_cmd = "screenshot"
    elif "enable autostart" in prompt_lower or "start on boot" in prompt_lower or "turn on autostart" in prompt_lower or "launch on startup" in prompt_lower:
        matched_cmd = "enable autostart"
    elif "disable autostart" in prompt_lower or "turn off autostart" in prompt_lower or "disable startup" in prompt_lower:
        matched_cmd = "disable autostart"
    elif "autostart status" in prompt_lower or "is autostart enabled" in prompt_lower or "check autostart" in prompt_lower:
        matched_cmd = "autostart status"
    elif "mute" in prompt_lower and "unmute" not in prompt_lower:
        matched_cmd = "mute"
    elif "unmute" in prompt_lower:
        matched_cmd = "unmute"
    elif "volume up" in prompt_lower or "increase volume" in prompt_lower:
        matched_cmd = "volume up"
    elif "volume down" in prompt_lower or "decrease volume" in prompt_lower:
        matched_cmd = "volume down"
    elif "set volume to" in prompt_lower or "volume to" in prompt_lower:
        nums = re.findall(r"\d+", prompt_lower)
        if nums:
            matched_cmd = f"volume {nums[0]}"
            
    if matched_cmd:
        add_system_log(f"Offline Intercept: {matched_cmd}")
        res = _execute_command_internal(matched_cmd, allow_llm_fallback=False)
        res["output"] = f"[OFFLINE MODE ACTIVE] {res.get('output', '')}"
        return res
    else:
        res_dummy = {
            "status": "success", "output": "", "notes": load_notes(), "games": get_games(),
            "recents": get_filtered_recents(), "system_info": get_system_metrics(),
            "time": time.strftime("%I:%M %p"), "date": time.strftime("%A, %B %d, %Y"),
            "explore_dir": CURRENT_EXPLORE_DIR,
            "folders": get_directory_contents(CURRENT_EXPLORE_DIR)[0],
            "files": get_directory_contents(CURRENT_EXPLORE_DIR)[1]
        }
        from backend.ai_services import clean_and_summarize_for_speech
        # Run local automations matching spotify/youtube/netflix
        auto_res = handle_automation(prompt_lower, res_dummy)
        if auto_res is not None:
            auto_res["output"] = f"[OFFLINE MODE ACTIVE] {auto_res.get('output', '')}"
            return auto_res
        return {
            "status": "success",
            "output": "[OFFLINE MODE ACTIVE] I am unable to connect to the core network right now. Local terminal control commands are still operational."
        }

def handle_automation(text_lower, res):
    # If the command explicitly targets TV or Phone, route directly to that device
    if any(k in text_lower for k in ("on tv", "on my tv", "on the tv")):
        from backend.tv_manager import tv_manager
        clean = re.sub(r"\b(on|to)\s+(the\s+|my\s+)?tv\b", "", text_lower, flags=re.IGNORECASE).strip()
        if "netflix" in clean:
            return tv_manager.launch_app("netflix")
        elif "youtube" in clean:
            query = clean.replace("open youtube", "").replace("play", "").replace("search", "").replace("youtube", "").strip()
            if query:
                return tv_manager.play_youtube(query)
            return tv_manager.launch_app("youtube")
        elif "play" in clean:
            query = clean.replace("play", "").strip()
            return tv_manager.play_youtube(query)

    if any(k in text_lower for k in ("on phone", "on my phone", "on the phone")):
        from backend.phone_agent import run_phone_agent
        clean = re.sub(r"\b(on|to)\s+(the\s+|my\s+)?phone\b", "", text_lower, flags=re.IGNORECASE).strip()
        return run_phone_agent(clean)

    if "netflix" in text_lower:
        query = text_lower
        patterns = [r"\bopen netflix and search for\b", r"\bopen netflix and search\b", r"\bopen netflix and play\b", r"\bsearch netflix for\b", r"\bsearch for\b", r"\bplay\b", r"\bon netflix\b", r"\bopen netflix\b", r"\bnetflix\b"]
        for p in patterns:
            query = re.sub(p, " ", query, flags=re.IGNORECASE)
        query = re.sub(r'\b(and|the|for|please|to)\b', ' ', query, flags=re.IGNORECASE)
        query = " ".join(query.split()).strip()
        if query:
            webbrowser.open(f"https://www.netflix.com/search?q={urllib.parse.quote(query)}")
            res["output"] = f"Searching Netflix for '{query}', sir."
        else:
            webbrowser.open("https://www.netflix.com")
            res["output"] = "Opening Netflix, sir."
        return res
    elif "github" in text_lower:
        query = text_lower
        patterns = [r"\bopen github and search for\b", r"\bopen github and search\b", r"\bsearch github for\b", r"\bsearch for\b", r"\bopen github\b", r"\bgithub\b"]
        for p in patterns:
            query = re.sub(p, " ", query, flags=re.IGNORECASE)
        query = re.sub(r'\b(and|the|for|please|to)\b', ' ', query, flags=re.IGNORECASE)
        query = " ".join(query.split()).strip()
        if query:
            webbrowser.open(f"https://github.com/search?q={urllib.parse.quote(query)}")
            res["output"] = f"Searching GitHub for '{query}', sir."
        else:
            webbrowser.open("https://github.com")
            res["output"] = "Opening GitHub, sir."
        return res
    elif "slack" in text_lower:
        try:
            slack_path = find_shortcut_or_executable("slack")
            if slack_path:
                os.startfile(slack_path)
                res["output"] = "Opening Slack, sir."
                return res
        except Exception:
            pass
        webbrowser.open("https://slack.com")
        res["output"] = "Opening Slack web, sir."
        return res
    elif "discord" in text_lower:
        try:
            discord_path = find_shortcut_or_executable("discord")
            if discord_path:
                os.startfile(discord_path)
                res["output"] = "Opening Discord, sir."
                return res
        except Exception:
            pass
        webbrowser.open("https://discord.com/app")
        res["output"] = "Opening Discord web, sir."
        return res
    elif "youtube" in text_lower:
        query = text_lower
        patterns = [r"\bopen youtube and search for\b", r"\bopen youtube and search\b", r"\bopen youtube and play\b", r"\bsearch youtube for\b", r"\bsearch for\b", r"\bplay\b", r"\bon youtube\b", r"\bopen youtube\b", r"\byoutube\b"]
        for p in patterns:
            query = re.sub(p, " ", query, flags=re.IGNORECASE)
        query = re.sub(r'\b(and|the|for|please|to)\b', ' ', query, flags=re.IGNORECASE)
        query = " ".join(query.split()).strip()
        if query:
            webbrowser.open(f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}")
            res["output"] = f"Searching YouTube for '{query}', sir."
        else:
            webbrowser.open("https://www.youtube.com")
            res["output"] = "Opening YouTube, sir."
        return res
    elif "spotify" in text_lower:
        query = text_lower
        patterns = [r"\bopen spotify and search for\b", r"\bopen spotify and search\b", r"\bopen spotify and play\b", r"\bsearch spotify for\b", r"\bsearch for\b", r"\bplay\b", r"\bon spotify\b", r"\bopen spotify\b", r"\bspotify\b"]
        for p in patterns:
            query = re.sub(p, " ", query, flags=re.IGNORECASE)
        query = re.sub(r'\b(and|the|for|please|to)\b', ' ', query, flags=re.IGNORECASE)
        query = " ".join(query.split()).strip()
        launched_locally = False
        try:
            spotify_path = find_shortcut_or_executable("spotify")
            if query:
                os.startfile(f"spotify:search:{urllib.parse.quote(query)}")
                res["output"] = f"Searching Spotify for '{query}', sir."
                launched_locally = True
            elif spotify_path:
                os.startfile(spotify_path)
                res["output"] = "Opening Spotify, sir."
                launched_locally = True
            else:
                os.startfile("spotify:")
                res["output"] = "Opening Spotify, sir."
                launched_locally = True
        except Exception:
            pass
        if launched_locally:
            return res
        if query:
            webbrowser.open(f"https://open.spotify.com/search/{urllib.parse.quote(query)}")
            res["output"] = f"Searching Spotify web player for '{query}', sir."
        else:
            webbrowser.open("https://open.spotify.com")
            res["output"] = "Opening Spotify web player, sir."
        return res
    elif "search for" in text_lower or ("google" in text_lower and "chrome" not in text_lower) or ("search" in text_lower and "file" not in text_lower):
        query = text_lower
        patterns = [r"\bgoogle search for\b", r"\bgoogle search\b", r"\bsearch for\b", r"\bgoogle\b", r"\bsearch\b"]
        for p in patterns:
            query = re.sub(p, " ", query, flags=re.IGNORECASE)
        query = re.sub(r'\b(and|the|for|please|to)\b', ' ', query, flags=re.IGNORECASE)
        query = " ".join(query.split()).strip()
        if query:
            webbrowser.open(f"https://www.google.com/search?q={urllib.parse.quote(query)}")
            res["output"] = f"Searching Google for '{query}', sir."
        else:
            res["status"] = "error"
            res["output"] = "What would you like me to search for, sir?"
        return res
    return None

def _execute_command_internal(text, allow_llm_fallback=True, image_base64=None, image_mime=None, window=None, stream_callback=None):
    global PENDING_SYSTEM_ACTION, CURRENT_EXPLORE_DIR, LAST_SCAN_RESULTS
    if allow_llm_fallback:
        text_lower = text.lower().strip()
        # Auto-capture desktop screenshot in-memory if user asks to see, analyze, or asks about what's on screen
        screen_triggers = (
            "look at my screen", "what is on my screen", "what's on my screen",
            "see my screen", "read my screen", "analyze my screen", "check my screen",
            "describe screen", "explain screen", "look at this screen", "look at screen",
            "what do you see on my screen", "what is on screen", "screen vision", "examine screen",
            "this error", "error on my screen", "what does this say", "look at this", "read this",
            "what am i looking at", "summarize this page", "summarize this window", "debug this code",
            "explain this code", "what is open", "read the text", "what is highlighted", "my display"
        )
        if not image_base64 and (any(st in text_lower for st in screen_triggers) or text_lower in ("look", "screen", "see", "screen vision", "pc look", "pc see")):
            from backend.pc_agent import capture_pc_screen_live
            image_base64, image_mime, _, _ = capture_pc_screen_live()
            if text_lower in ("look", "screen", "see", "screen vision", "pc look", "pc see"):
                text = "Analyze what is currently visible on my desktop screen in detail and summarize the key open windows, text, or errors."

        # Natural GUI action triggers (e.g. "click on the submit button", "fill out this form") -> route to PC Agent
        gui_action_triggers = (
            "click on ", "click the ", "double click ", "right click on ",
            "press the button", "press button", "type in the ", "fill out this ",
            "close the popup", "scroll down on ", "scroll up on "
        )
        if any(text_lower.startswith(gt) for gt in gui_action_triggers):
            from backend.pc_agent import run_pc_agent
            return run_pc_agent(text, window=window)

        # Smart clipboard inspection
        clipboard_triggers = (
            "check clipboard", "explain clipboard", "fix clipboard",
            "what is in clipboard", "what's in clipboard", "format clipboard",
            "summarize clipboard", "read clipboard", "analyze clipboard"
        )
        if any(ct in text_lower for ct in clipboard_triggers) or text_lower == "clipboard":
            from backend.sys_utils import get_clipboard_text
            cb_content = get_clipboard_text().strip()
            if not cb_content:
                return {"status": "success", "output": "Your clipboard is currently empty, sir."}
            text = f"{text}\n\n[USER CLIPBOARD CONTENT]:\n```\n{cb_content}\n```"

        return run_agentic_loop(text, window=window, image_base64=image_base64, image_mime=image_mime, stream_callback=stream_callback)

    # ── Check plugins before the built-in command chain ──
    plugin_result = execute_plugin_command(text, context={"window": window})
    if plugin_result is not None:
        add_system_log(f"Plugin handled: {text[:50]}")
        return plugin_result

    text_lower = text.lower().strip()
    folders, files = get_directory_contents(CURRENT_EXPLORE_DIR)
    res = {
        "status": "success", "output": "", "notes": load_notes(), "games": get_games(),
        "recents": get_filtered_recents(), "system_info": get_system_metrics(),
        "time": time.strftime("%I:%M %p"), "date": time.strftime("%A, %B %d, %Y"),
        "explore_dir": CURRENT_EXPLORE_DIR, "folders": folders, "files": files
    }
    
    if text_lower.startswith("run powershell ") or text_lower.startswith("powershell "):
        script = text[text_lower.index("powershell") + 10:].strip()
        try:
            result = subprocess.run(["powershell", "-Command", script], capture_output=True, text=True, timeout=10, creationflags=CREATE_NO_WINDOW)
            if result.returncode == 0:
                res["output"] = f"PowerShell output: {result.stdout.strip()}"
            else:
                res["status"] = "error"
                err_lines = result.stderr.strip().splitlines()
                res["output"] = f"PowerShell execution error: {err_lines[0] if err_lines else 'Unknown error'}"
        except subprocess.TimeoutExpired:
            res["status"] = "error"
            res["output"] = "PowerShell command timed out."
        except Exception as e:
            res["status"] = "error"
            res["output"] = f"PowerShell execution failed: {clean_error_message(e)}"
        return res
    elif text_lower.startswith("run python ") or text_lower.startswith("python "):
        code = text[text_lower.index("python") + 6:].strip()
        try:
            result = subprocess.run(["python", "-c", code], capture_output=True, text=True, timeout=10, creationflags=CREATE_NO_WINDOW)
            if result.returncode == 0:
                res["output"] = f"Python output: {result.stdout.strip()}"
            else:
                res["status"] = "error"
                err_lines = result.stderr.strip().splitlines()
                res["output"] = f"Python execution error: {err_lines[-1] if err_lines else 'Unknown error'}"
        except subprocess.TimeoutExpired:
            res["status"] = "error"
            res["output"] = "Python execution timed out."
        except Exception as e:
            res["status"] = "error"
            res["output"] = f"Python execution failed: {clean_error_message(e)}"
        return res
    elif text_lower.startswith("read file "):
        file_path = text[10:].strip().strip('"').strip("'")
        file_result = read_file(file_path)
        if file_result["status"] == "success":
            res["output"] = f"File content of '{file_path}':\n{file_result['content']}"
        else:
            res["status"] = "error"
            res["output"] = f"Failed to read file '{file_path}': {file_result['message']}"
        return res
    elif text_lower.startswith("write file "):
        rest = text[11:].strip()
        if " | " in rest:
            file_path, content = rest.split(" | ", 1)
            file_path = file_path.strip().strip('"').strip("'")
            file_result = write_file(file_path, content.strip())
            if file_result["status"] == "success":
                res["output"] = f"Successfully wrote to file '{file_path}'."
            else:
                res["status"] = "error"
                res["output"] = f"Failed to write to file '{file_path}': {file_result['message']}"
        else:
            res["status"] = "error"
            res["output"] = "Invalid write file format. Use: write file [file_path] | [content]"
        return res
    elif text_lower.startswith("append file "):
        rest = text[12:].strip()
        if " | " in rest:
            file_path, content = rest.split(" | ", 1)
            file_path = file_path.strip().strip('"').strip("'")
            try:
                with open(file_path, "a", encoding="utf-8") as f:
                    f.write("\n" + content.strip())
                res["output"] = f"Successfully appended to file '{file_path}'."
            except Exception as e:
                res["status"] = "error"
                res["output"] = f"Failed to append to file '{file_path}': {str(e)}"
        else:
            res["status"] = "error"
            res["output"] = "Invalid append file format. Use: append file [file_path] | [content]"
        return res
    elif text_lower.startswith("delete file ") or text_lower.startswith("remove file "):
        file_path = text.split(" ", 2)[-1].strip().strip('"').strip("'")
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                res["output"] = f"Successfully deleted file '{file_path}'."
            else:
                res["status"] = "error"
                res["output"] = f"File not found: '{file_path}'."
        except Exception as e:
            res["status"] = "error"
            res["output"] = f"Failed to delete file '{file_path}': {str(e)}"
        return res
    elif text_lower.startswith("list directory "):
        folder_path = text[15:].strip().strip('"').strip("'")
        try:
            folders_list, files_list = get_directory_contents(folder_path)
            res["output"] = f"Contents of '{folder_path}':\nFolders: {', '.join(folders_list[:20])}\nFiles: {', '.join(files_list[:20])}"
        except Exception as e:
            res["status"] = "error"
            res["output"] = f"Failed to list directory '{folder_path}': {clean_error_message(e)}"
        return res
    elif text_lower.startswith("remember "):
        fact = text[9:].strip()
        if fact.lower().startswith("that "):
            fact = fact[5:].strip()
        add_memory_fact(fact)
        res["output"] = f"Got it, I'll remember that: {fact}."
        return res
    elif text_lower in ("what do you remember about me", "show memory", "view memory"):
        profile_str = get_user_profile_string()
        res["output"] = profile_str.replace("\n", " ").strip() if profile_str else "I don't remember anything specific about you yet. Tell me something to remember!"
        return res
    elif text_lower.startswith("forget ") or text_lower == "clear memory":
        if text_lower.startswith("forget "):
            target = text[7:].strip()
            res["output"] = f"I've forgotten everything about {target}." if forget_about(target) else f"I couldn't find anything matching {target} in my memory."
        else:
            clear_all_memory()
            res["output"] = "All memory cleared. Starting fresh."
        return res
    elif text_lower in ("memory stats", "memory status"):
        stats = get_memory_stats()
        res["output"] = (
            f"Memory status: I remember {stats['total_memories']} things about you. "
            f"{stats['identity_fields']} identity details, {stats['preferences']} preferences, "
            f"{stats['relationships']} relationships, {stats['interests']} interests, "
            f"{stats['habits']} habits. Chat history has {stats['chat_history_length']} messages "
            f"with {stats['conversation_summaries']} conversation summaries archived."
        )
        return res
    elif text_lower.startswith("set timer ") or text_lower.startswith("timer "):
        from backend.memory_scheduler import parse_duration, format_duration
        duration_text = text_lower.replace("set timer ", "").replace("timer ", "").replace("for ", "").strip()
        seconds = parse_duration(duration_text)
        if seconds and seconds > 0:
            add_schedule("timer", f"Timer for {format_duration(seconds)}", time.time() + seconds)
            res["output"] = f"Timer set for {format_duration(seconds)}."
        else:
            res["status"] = "error"
            res["output"] = "Could not parse timer duration. Try 'set timer 5 minutes' or 'timer 30 seconds'."
        return res
    elif text_lower.startswith("add note "):
        note = text[9:].strip()
        notes = load_notes()
        notes.append({"text": note, "timestamp": time.time()})
        save_notes(notes)
        res["output"] = f"Note added: {note}"
        return res
    elif text_lower in ("show notes", "list notes", "my notes"):
        notes = load_notes()
        res["output"] = f"Your notes:\n" + "\n".join([f"{i+1}. {n['text']}" for i, n in enumerate(notes)]) if notes else "You have no notes yet."
        return res
    elif text_lower.startswith("delete note "):
        try:
            note_num = int(text[11:].strip())
            notes = load_notes()
            if 1 <= note_num <= len(notes):
                deleted = notes.pop(note_num - 1)
                save_notes(notes)
                res["output"] = f"Deleted note: {deleted['text']}"
            else:
                res["status"] = "error"
                res["output"] = f"Invalid note number. You have {len(notes)} notes."
        except ValueError:
            res["status"] = "error"
            res["output"] = "Please specify a note number. Use 'delete note 1' to delete the first note."
        return res
    elif text_lower == "clear notes":
        save_notes([])
        res["output"] = "All notes cleared."
        return res
    elif text_lower.startswith("open "):
        app_name = text[5:].strip()
        if app_name.lower().startswith(("http://", "https://", "www.")):
            try:
                url = app_name if not app_name.lower().startswith("www.") else "https://" + app_name
                webbrowser.open(url)
                res["output"] = f"Opened URL: {url}"
                from backend.sys_utils import add_to_recents
                add_to_recents(app_name, f"open {app_name}", "url")
                return res
            except Exception as e:
                res["status"] = "error"
                res["output"] = f"Failed to open URL {app_name}: {clean_error_message(e)}"
                return res
        if os.path.exists(app_name):
            try:
                os.startfile(app_name)
                res["output"] = f"Opened {app_name}"
                from backend.sys_utils import add_to_recents
                add_to_recents(os.path.basename(app_name), f"open {app_name}", "file")
                return res
            except Exception as e:
                res["status"] = "error"
                res["output"] = f"Failed to open {app_name}: {clean_error_message(e)}"
                return res
        app_path = find_shortcut_or_executable(app_name)
        if app_path:
            try:
                os.startfile(app_path)
                res["output"] = f"Opened {app_name}"
                from backend.sys_utils import add_to_recents
                add_to_recents(app_name, f"open {app_name}", "app")
                return res
            except Exception as e:
                res["status"] = "error"
                res["output"] = f"Failed to open {app_name}: {clean_error_message(e)}"
                return res
        else:
            start_menu_search_and_open(app_name)
            res["output"] = f"Searching for and opening {app_name}..."
            from backend.sys_utils import add_to_recents
            add_to_recents(app_name, f"open {app_name}", "app")
            return res
    elif text_lower.startswith("close "):
        return close_application(text[6:].strip())
    elif text_lower.startswith("find "):
        query = text[5:].strip()
        from backend.sys_utils import get_search_roots, scan_directory
        roots = get_search_roots()
        results = []
        for root in roots:
            if len(results) >= 20:
                break
            results.extend(scan_directory(root, query, max_results=20))
        if results:
            res["output"] = f"Found {len(results)} items matching '{query}':\n" + "\n".join([f"- {r['name']} ({r['type']})" for r in results[:15]])
            LAST_SCAN_RESULTS = results
        else:
            res["output"] = f"No items found matching '{query}'."
        return res
    elif text_lower == "screenshot":
        return take_screenshot(DESKTOP_DIR)
    elif text_lower.startswith("brightness "):
        try:
            return set_brightness(int(text[10:].strip()))
        except ValueError:
            res["status"] = "error"
            res["output"] = "Please specify a brightness value between 0 and 100."
            return res
    elif text_lower in ("dim screen", "lower brightness"):
        current = get_brightness()
        if current:
            new_brightness = max(0, current - 10)
            set_brightness(new_brightness)
            res["output"] = f"Brightness lowered to {new_brightness}%"
        else:
            res["output"] = "Could not get current brightness."
        return res
    elif text_lower in ("brighten screen", "increase brightness"):
        current = get_brightness()
        if current:
            new_brightness = min(100, current + 10)
            set_brightness(new_brightness)
            res["output"] = f"Brightness increased to {new_brightness}%"
        else:
            res["output"] = "Could not get current brightness."
        return res
    elif text_lower == "empty recycle bin":
        return empty_recycle_bin()
    elif text_lower == "close folders":
        return close_explorer_folders()
    elif text_lower == "mute":
        set_windows_volume(0)
        res["output"] = "Volume muted."
        return res
    elif text_lower == "unmute":
        set_windows_volume(75)
        res["output"] = "Volume unmuted to 75%."
        return res
    elif text_lower in ("volume up", "increase volume"):
        current = get_windows_volume()
        new_volume = min(100, current + 10)
        set_windows_volume(new_volume)
        res["output"] = f"Volume increased to {new_volume}%"
        return res
    elif text_lower in ("volume down", "decrease volume"):
        current = get_windows_volume()
        new_volume = max(0, current - 10)
        set_windows_volume(new_volume)
        res["output"] = f"Volume decreased to {new_volume}%"
        return res
    elif text_lower.startswith("volume "):
        try:
            vol_int = int(text[7:].strip())
            set_windows_volume(vol_int)
            res["output"] = f"Volume set to {vol_int}%"
            return res
        except ValueError:
            res["status"] = "error"
            res["output"] = "Please specify a volume value between 0 and 100."
            return res
    elif text_lower in ("play", "pause", "resume", "play music", "pause music", "resume music", "toggle media", "toggle music"):
        from backend.music_monitor import control_playback
        control_playback("toggle")
        send_media_key(0xB3)
        res["output"] = "Media playback toggled, sir."
        return res
    elif text_lower in ("next track", "next", "next song", "skip track", "skip song"):
        from backend.music_monitor import control_playback
        control_playback("next")
        send_media_key(0xB0)
        res["output"] = "Skipped to next track, sir."
        return res
    elif text_lower in ("previous track", "previous", "previous song", "prev track", "prev song"):
        from backend.music_monitor import control_playback
        control_playback("prev")
        send_media_key(0xB1)
        res["output"] = "Returned to previous track, sir."
        return res
    elif text_lower in ("what is playing", "what's playing", "current song", "now playing"):
        from backend.music_monitor import music_monitor
        state = music_monitor.get_current_state()
        if state and state.get("title"):
            res["output"] = f"Now playing: '{state.get('title')}' by {state.get('artist', 'Unknown Artist')}."
        else:
            res["output"] = "No active media track detected, sir."
        return res

    elif text_lower.startswith("copy to clipboard "):
        clipboard_text = text[18:].strip()
        if set_clipboard_text(clipboard_text):
            res["output"] = f"Copied to clipboard: {clipboard_text}"
        else:
            res["status"] = "error"
            res["output"] = "Failed to copy to clipboard."
        return res
    elif text_lower in ("read clipboard", "clipboard"):
        clipboard_content = get_clipboard_text()
        res["output"] = f"Clipboard content: {clipboard_content}" if clipboard_content else "Clipboard is empty or contains non-text content."
        return res
    elif text_lower == "clear clipboard":
        if clear_clipboard():
            res["output"] = "Clipboard cleared."
        else:
            res["status"] = "error"
            res["output"] = "Failed to clear clipboard."
        return res
    elif text_lower in ("check internet status", "internet status", "network status"):
        net_status = get_cached_network_status()
        res["output"] = f"Network Status: {net_status['status']}\nPing: {net_status['ping']}\nIP: {net_status['ip']}"
        return res
    elif text_lower == "my ip address":
        net_status = get_cached_network_status()
        res["output"] = f"Your IP address: {net_status['ip']}"
        return res
    elif text_lower.startswith("weather in "):
        location = text[11:].strip()
        weather_info = get_weather(location)
        res["output"] = f"Weather in {location}: {weather_info}" if weather_info else f"Could not fetch weather for {location}."
        return res
    elif text_lower == "weather":
        weather_info = get_weather(None)
        res["output"] = f"Current weather: {weather_info}" if weather_info else "Could not fetch weather information."
        return res
    elif text_lower.startswith("youtube "):
        query = text[8:].strip()
        if any(play_word in query.lower() for play_word in ("play ", "song ", "music ", "listen ")):
            clean_q = query
            for w in ("play", "song", "music", "listen", "to"):
                clean_q = re.sub(rf"\b{w}\b", "", clean_q, flags=re.IGNORECASE)
            return play_youtube_first_result(" ".join(clean_q.split()).strip() or query)
        return search_youtube(query)
    elif text_lower.startswith("spotify "):
        return search_spotify(text[8:].strip())
    elif text_lower.startswith("search "):
        return search_web(text[7:].strip())
    elif text_lower in ("lock pc", "lock computer"):
        try:
            ctypes.windll.user32.LockWorkStation()
            res["output"] = "Computer locked successfully."
        except Exception as e:
            res["status"] = "error"
            res["output"] = f"Failed to lock computer: {str(e)}"
        return res
    elif text_lower in ("enable autostart", "enable auto start", "turn on autostart", "start on boot", "launch on startup", "enable startup"):
        success = set_autostart(True)
        if success:
            from backend.sys_utils import load_config, save_config
            cfg = load_config()
            cfg["autostart"] = True
            save_config(cfg)
            res["output"] = "Auto-start on Windows boot is now enabled, sir."
        else:
            res["status"] = "error"
            res["output"] = "Failed to enable auto-start in Windows registry."
        return res
    elif text_lower in ("disable autostart", "disable auto start", "turn off autostart", "disable startup", "don't start on boot"):
        success = set_autostart(False)
        if success:
            from backend.sys_utils import load_config, save_config
            cfg = load_config()
            cfg["autostart"] = False
            save_config(cfg)
            res["output"] = "Auto-start on Windows boot is now disabled, sir."
        else:
            res["status"] = "error"
            res["output"] = "Failed to disable auto-start in Windows registry."
        return res
    elif text_lower in ("autostart status", "is autostart enabled", "check autostart"):
        from backend.sys_utils import load_config
        cfg = load_config()
        is_on = cfg.get("autostart", False) or is_autostart_enabled()
        res["output"] = f"Auto-start on boot is currently {'enabled' if is_on else 'disabled'}, sir."
        return res
    elif text_lower == "sleep":
        try:
            subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])
            res["output"] = "Putting PC to sleep..."
        except Exception as e:
            res["status"] = "error"
            res["output"] = f"Failed to put PC to sleep: {str(e)}"
        return res
    elif text_lower == "turn off wifi":
        try:
            subprocess.run(["powershell", "-Command", "Disable-NetAdapter -Name 'Wi-Fi' -Confirm:$false"], capture_output=True, text=True, timeout=5, creationflags=CREATE_NO_WINDOW)
            res["output"] = "Wi-Fi adapter disabled successfully."
        except Exception as e:
            res["status"] = "error"
            res["output"] = f"Failed to disable Wi-Fi adapter: {str(e)}"
        return res
    elif text_lower == "turn on wifi":
        try:
            subprocess.run(["powershell", "-Command", "Enable-NetAdapter -Name 'Wi-Fi' -Confirm:$false"], capture_output=True, text=True, timeout=5, creationflags=CREATE_NO_WINDOW)
            res["output"] = "Wi-Fi adapter enabled successfully."
        except Exception as e:
            res["status"] = "error"
            res["output"] = f"Failed to enable Wi-Fi adapter: {str(e)}"
        return res
    elif text_lower == "turn off bluetooth":
        try:
            subprocess.run(["powershell", "-Command", "Get-PnpDevice -FriendlyName '*Bluetooth*' -Status OK | Disable-PnpDevice -Confirm:$false"], capture_output=True, text=True, timeout=5, creationflags=CREATE_NO_WINDOW)
            res["output"] = "Bluetooth adapter disabled successfully."
        except Exception as e:
            res["status"] = "error"
            res["output"] = f"Failed to disable Bluetooth: {str(e)}"
        return res
    elif text_lower == "turn on bluetooth":
        try:
            subprocess.run(["powershell", "-Command", "Get-PnpDevice -FriendlyName '*Bluetooth*' | Enable-PnpDevice -Confirm:$false"], capture_output=True, text=True, timeout=5, creationflags=CREATE_NO_WINDOW)
            res["output"] = "Bluetooth adapter enabled successfully."
        except Exception as e:
            res["status"] = "error"
            res["output"] = f"Failed to enable Bluetooth: {str(e)}"
        return res
    elif text_lower.startswith("go to "):
        new_dir = parse_directory_path(text, CURRENT_EXPLORE_DIR)
        if new_dir and new_dir != CURRENT_EXPLORE_DIR:
            CURRENT_EXPLORE_DIR = new_dir
            folders, files = get_directory_contents(CURRENT_EXPLORE_DIR)
            res["explore_dir"] = CURRENT_EXPLORE_DIR
            res["folders"] = folders
            res["files"] = files
            res["output"] = f"Navigated to {CURRENT_EXPLORE_DIR}"
        else:
            res["output"] = f"Already at {CURRENT_EXPLORE_DIR}"
        return res
    elif text_lower.startswith("connect tv "):
        from backend.tv_manager import tv_manager
        ip_val = text[10:].strip()
        tv_res = tv_manager.set_tv_ip(ip_val)
        if tv_res["status"] == "success":
            res["output"] = f"TV IP set to {ip_val}."
        else:
            res["status"] = "error"
            res["output"] = f"Failed to connect TV: {tv_res.get('message')}"
        return res
    elif text_lower.startswith("device "):
        device_cmd = text_lower[7:].strip()
        if device_cmd == "status":
            from backend.tv_manager import tv_manager
            tv_connected = tv_manager.is_connected()
            tv_ip = tv_manager.get_tv_ip()
            phone_id = get_active_phone_id()
            tv_label = f"TV: {'Connected' if tv_connected else 'Disconnected'}"
            if tv_ip:
                tv_label += f" ({tv_ip})"
            phone_label = f"Phone: {'Connected (' + phone_id + ')' if phone_id else 'Disconnected'}"
            res["output"] = f"{tv_label}. {phone_label}."
        else:
            res["status"] = "error"
            res["output"] = f"Unknown device command: {device_cmd}"
        return res
    elif text_lower.startswith("tv "):
        from backend.tv_manager import tv_manager
        tv_cmd = text[3:].strip()
        tv_cmd_lower = tv_cmd.lower()
        if tv_cmd_lower.startswith("ip "):
            ip_val = tv_cmd[3:].strip()
            tv_res = tv_manager.set_tv_ip(ip_val)
            if tv_res["status"] == "success":
                res["output"] = f"TV IP address set to {ip_val}."
            else:
                res["status"] = "error"
                res["output"] = f"Failed to set TV IP: {tv_res.get('message')}"
        elif tv_cmd_lower == "connect":
            tv_res = tv_manager.connect()
            if tv_res["status"] == "success":
                res["output"] = tv_res["message"]
            else:
                res["status"] = "error"
                res["output"] = f"Failed to connect: {tv_res.get('message')}"
        elif tv_cmd_lower == "status":
            connected = tv_manager.is_connected()
            ip = tv_manager.get_tv_ip()
            res["output"] = f"TV IP: {ip}. Status: {'Connected' if connected else 'Disconnected'}."
        elif tv_cmd_lower == "mirror" or tv_cmd_lower == "screen":
            tv_res = tv_manager.mirror()
            res["status"] = tv_res["status"]
            res["output"] = tv_res.get("output", tv_res.get("message", ""))
        elif tv_cmd_lower.startswith("button "):
            btn = tv_cmd[7:].strip()
            tv_res = tv_manager.send_button(btn)
            if tv_res["status"] == "success":
                res["output"] = f"Sent TV button event: {btn}."
            else:
                res["status"] = "error"
                res["output"] = f"Failed to send button event: {tv_res.get('message')}"
        elif tv_cmd_lower.startswith("open ") or tv_cmd_lower.startswith("launch "):
            app = tv_cmd[tv_cmd_lower.index(" ") + 1:].strip()
            tv_res = tv_manager.launch_app(app)
            if tv_res["status"] == "success":
                res["output"] = f"Launched app '{app}' on TV."
            else:
                res["status"] = "error"
                res["output"] = f"Failed to launch app: {tv_res.get('message')}"
        elif tv_cmd_lower.startswith("play ") or tv_cmd_lower.startswith("youtube "):
            query = tv_cmd[tv_cmd_lower.index(" ") + 1:].strip()
            tv_res = tv_manager.play_on_youtube(query)
            if tv_res["status"] == "success":
                res["output"] = f"Searching YouTube on TV for '{query}'."
            else:
                res["status"] = "error"
                res["output"] = f"Failed to search YouTube: {tv_res.get('message')}"
        elif tv_cmd_lower.startswith("play link "):
            url = tv_cmd[10:].strip()
            tv_res = tv_manager.play_media_link(url)
            if tv_res["status"] == "success":
                res["output"] = f"Opening link '{url}' on TV."
            else:
                res["status"] = "error"
                res["output"] = f"Failed to open link: {tv_res.get('message')}"
        elif tv_cmd_lower in ("up", "down", "left", "right", "select", "ok", "home", "back", "power", "mute", "volume_up", "volume_down"):
            tv_res = tv_manager.send_button(tv_cmd_lower)
            if tv_res["status"] == "success":
                res["output"] = f"Sent TV button event: {tv_cmd_lower}."
            else:
                res["status"] = "error"
                res["output"] = f"Failed to send button event: {tv_res.get('message')}"
        else:
            res["status"] = "error"
            res["output"] = f"Unknown TV command: {tv_cmd}"
        return res

    elif text_lower.startswith("phone "):
        from backend.adb_manager import adb_manager
        phone_cmd = text[6:].strip()
        phone_cmd_lower = phone_cmd.lower()
        if phone_cmd_lower.startswith("connect "):
            addr = phone_cmd[8:].strip()
            phone_res = adb_manager.connect(addr)
            if phone_res["status"] == "success":
                # Save phone IP to config for auto-connect on next startup
                from backend.sys_utils import load_config, save_config
                cfg = load_config()
                cfg["phone_ip"] = addr
                save_config(cfg)
                res["output"] = phone_res["message"]
            else:
                res["status"] = "error"
                res["output"] = f"Failed to connect phone: {phone_res.get('message')}"
        elif phone_cmd_lower.startswith("pair "):
            parts = phone_cmd[5:].strip().split()
            if len(parts) >= 2:
                addr, code = parts[0], parts[1]
                phone_res = adb_manager.pair(addr, code)
                if phone_res["status"] == "success":
                    res["output"] = f"Successfully paired phone at {addr}."
                else:
                    res["status"] = "error"
                    res["output"] = f"Failed to pair phone: {phone_res.get('message')}"
            else:
                res["status"] = "error"
                res["output"] = "Invalid pairing format. Use: phone pair [ip:port] [pairing_code]"
        elif phone_cmd_lower == "status":
            devices = adb_manager.list_devices()
            device_strs = [f"{d['id']} ({d['status']})" for d in devices]
            res["output"] = f"Connected ADB devices: {', '.join(device_strs)}" if devices else "Connected ADB devices: None"
        elif phone_cmd_lower.startswith("mirror") or phone_cmd_lower.startswith("screen"):
            # phone mirror [ip:port]  OR  phone screen [ip:port]
            parts = phone_cmd.split()
            if len(parts) >= 2:
                ip_port = parts[1].strip()
            else:
                # Auto-detect: find non-TV device from adb devices
                from backend.tv_manager import tv_manager
                devices = adb_manager.list_devices()
                tv_ip = tv_manager.get_tv_ip()
                tv_target = f"{tv_ip}:5555" if tv_ip else ""
                phone_dev = None
                for d in devices:
                    if d["status"] == "device" and d["id"] != tv_target:
                        phone_dev = d["id"]
                        break
                if phone_dev:
                    ip_port = phone_dev
                else:
                    res["status"] = "error"
                    res["output"] = "No connected phone. Connect via ADB first."
                    return res
            from backend.sys_utils import launch_phone_mirror
            mirror_res = launch_phone_mirror(ip_port)
            res["status"] = mirror_res["status"]
            res["output"] = mirror_res["output"]
        elif phone_cmd_lower.startswith("button ") or phone_cmd_lower.startswith("key ") or phone_cmd_lower.startswith("keyevent "):
            if phone_cmd_lower.startswith("keyevent "):
                key = phone_cmd[9:].strip()
            else:
                key = phone_cmd[phone_cmd_lower.index(" ") + 1:].strip()
            target = get_active_phone_id()
            if target:
                phone_res = adb_manager.send_key(target, key)
                if phone_res["status"] == "success":
                    res["output"] = f"Sent keyevent {key} to device {target}."
                else:
                    res["status"] = "error"
                    res["output"] = f"Failed to send key: {phone_res.get('message')}"
            else:
                res["status"] = "error"
                res["output"] = "No connected phone found via ADB."
        elif phone_cmd_lower.startswith("tap "):
            coords = phone_cmd[4:].strip().split()
            if len(coords) >= 2:
                x, y = coords[0], coords[1]
                target = get_active_phone_id()
                if target:
                    phone_res = adb_manager.send_tap_fast(target, x, y)
                    if phone_res["status"] == "success":
                        res["output"] = f"Tapped screen at ({x}, {y}) on device {target}."
                    else:
                        res["status"] = "error"
                        res["output"] = f"Failed to tap screen: {phone_res.get('message')}"
                else:
                    res["status"] = "error"
                    res["output"] = "No connected phone found via ADB."
            else:
                res["status"] = "error"
                res["output"] = "Invalid coordinates. Use: phone tap [x] [y]"
        elif phone_cmd_lower.startswith("swipe ") or phone_cmd_lower.startswith("drag ") or phone_cmd_lower.startswith("scroll "):
            cmd_prefix = "swipe " if phone_cmd_lower.startswith("swipe ") else ("drag " if phone_cmd_lower.startswith("drag ") else "scroll ")
            parts = phone_cmd[len(cmd_prefix):].strip().split()
            if len(parts) >= 4:
                x1, y1, x2, y2 = parts[0], parts[1], parts[2], parts[3]
                dur = int(parts[4]) if len(parts) >= 5 and parts[4].isdigit() else 300
                target = get_active_phone_id()
                if target:
                    phone_res = adb_manager.send_swipe_fast(target, x1, y1, x2, y2, dur)
                    if phone_res["status"] == "success":
                        res["output"] = f"Swiped from ({x1}, {y1}) to ({x2}, {y2}) on {target}."
                    else:
                        res["status"] = "error"
                        res["output"] = f"Failed to swipe: {phone_res.get('message')}"
                else:
                    res["status"] = "error"
                    res["output"] = "No connected phone found via ADB."
            else:
                res["status"] = "error"
                res["output"] = "Invalid swipe coordinates. Use: phone swipe [x1] [y1] [x2] [y2] [duration]"
        elif phone_cmd_lower.startswith("type "):
            text_to_type = phone_cmd[5:].strip()
            target = get_active_phone_id()
            if target:
                phone_res = adb_manager.send_text(target, text_to_type)
                if phone_res["status"] == "success":
                    res["output"] = f"Typed '{text_to_type}' on phone screen."
                else:
                    res["status"] = "error"
                    res["output"] = f"Failed to type: {phone_res.get('message')}"
            else:
                res["status"] = "error"
                res["output"] = "No connected phone found via ADB."
        elif phone_cmd_lower.startswith("open ") or phone_cmd_lower.startswith("launch "):
            app = phone_cmd[phone_cmd_lower.index(" ") + 1:].strip()
            target = get_active_phone_id()
            if target:
                phone_res = adb_manager.launch_app(target, app)
                if phone_res["status"] == "success":
                    res["output"] = f"Launched app '{app}' on phone."
                else:
                    res["status"] = "error"
                    res["output"] = f"Failed to launch app: {phone_res.get('message')}"
            else:
                res["status"] = "error"
                res["output"] = "No connected phone found via ADB."
        elif phone_cmd_lower.startswith("do ") or phone_cmd_lower.startswith("execute "):
            # phone do <task> — see the screen and operate the phone autonomously
            task_text = phone_cmd[phone_cmd_lower.index(" ") + 1:].strip()
            if not task_text:
                res["status"] = "error"
                res["output"] = "Tell me what to do, e.g. 'phone do open YouTube and play jazz'."
            else:
                from backend.phone_agent import run_phone_agent
                phone_agent_res = run_phone_agent(task_text, window=window)
                res["status"] = phone_agent_res["status"]
                res["output"] = phone_agent_res["output"]
        elif phone_cmd_lower in ("look", "see", "describe", "describe screen"):
            from backend.phone_agent import run_phone_agent
            phone_agent_res = run_phone_agent("Describe what is currently on the phone screen.", window=window)
            res["status"] = phone_agent_res["status"]
            res["output"] = phone_agent_res["output"]
        elif phone_cmd_lower == "screenshot":
            target = get_active_phone_id()
            if not target:
                res["status"] = "error"
                res["output"] = "No connected phone found via ADB."
            else:
                from backend.phone_agent import PHONE_SCREENSHOTS_DIR
                os.makedirs(PHONE_SCREENSHOTS_DIR, exist_ok=True)
                path = os.path.join(PHONE_SCREENSHOTS_DIR, f"phone_{time.strftime('%Y%m%d_%H%M%S')}.png")
                shot = adb_manager.screenshot(target, path)
                if shot["status"] == "success":
                    res["output"] = f"Saved phone screenshot to {path}."
                else:
                    res["status"] = "error"
                    res["output"] = f"Failed to capture phone screen: {shot.get('message')}"
        elif phone_cmd_lower.startswith("rotate ") or phone_cmd_lower.startswith("autorotate ") or phone_cmd_lower in ("rotate", "autorotate"):
            action = phone_cmd_lower.replace("autorotate", "").replace("rotate", "").strip() or "toggle"
            target = get_active_phone_id()
            if not target:
                res["status"] = "error"
                res["output"] = "No connected phone found via ADB."
            else:
                if action in ("off", "lock", "disable", "portrait", "0"):
                    r = adb_manager.set_auto_rotate(target, enable=False)
                    res["output"] = f"Auto-rotate disabled (locked to portrait) on {target}."
                elif action in ("on", "enable", "unlock", "1"):
                    r = adb_manager.set_auto_rotate(target, enable=True)
                    res["output"] = f"Auto-rotate enabled on {target}."
                elif action in ("status", "get", "check"):
                    curr = adb_manager.get_auto_rotate(target)
                    state = "ENABLED" if curr.get("auto_rotate") else "DISABLED (LOCKED)"
                    res["output"] = f"Auto-rotate is currently {state} on {target}."
                else:
                    # Toggle
                    curr = adb_manager.get_auto_rotate(target)
                    new_state = not curr.get("auto_rotate", False)
                    adb_manager.set_auto_rotate(target, enable=new_state)
                    res["output"] = f"Auto-rotate {'enabled' if new_state else 'disabled (locked)'} on {target}."
        else:
            res["status"] = "error"
            res["output"] = f"Unknown Phone command: {phone_cmd}"
        return res

    elif text_lower.startswith("pc do ") or text_lower.startswith("computer do ") or text_lower.startswith("pc execute "):
        task_text = text[text_lower.index("do ") + 3:].strip() if "do " in text_lower else text[text_lower.index("execute ") + 8:].strip()
        from backend.pc_agent import run_pc_agent
        return run_pc_agent(task_text, window=window)

    elif text_lower in ("pc look", "pc see", "pc vision", "look at screen", "look at my screen", "what's on my screen", "what is on my screen", "describe screen", "read screen", "analyze screen", "see screen") or text_lower.startswith("pc describe"):
        from backend.pc_agent import describe_pc_screen
        return describe_pc_screen(prompt=text, window=window)

    res["status"] = "error"
    res["output"] = f"Unknown command: {text}"
    return res

def _is_direct_device_command(text_lower):
    """True for device-control commands that should run instantly without LLM or cache."""
    if text_lower.startswith("pc do ") or text_lower.startswith("computer do ") or text_lower.startswith("pc execute ") or text_lower in ("pc look", "pc see", "pc vision", "look at screen", "look at my screen", "what's on my screen", "what is on my screen", "describe screen", "read screen", "analyze screen", "see screen") or text_lower.startswith("pc describe"):
        return True
    if text_lower.startswith("phone "):
        rest = text_lower[6:].strip()
        for verb in ("connect", "pair", "status", "mirror", "screen", "button", "keyevent", "key", "tap", "type", "open", "launch", "do", "execute", "look", "see", "screenshot", "rotate", "autorotate"):
            if rest.startswith(verb):
                return True
        return False
    if text_lower.startswith("tv "):
        rest = text_lower[3:].strip()
        if rest in ("up", "down", "left", "right", "select", "ok", "home", "back", "power", "mute", "volume_up", "volume_down"):
            return True
        for verb in ("ip", "connect", "status", "mirror", "screen", "button", "open", "launch", "play", "youtube"):
            if rest.startswith(verb):
                return True
        return False
    if text_lower.startswith("connect tv "):
        return True
    if text_lower.startswith("device "):
        return text_lower[7:].strip() == "status"
    if text_lower in (
        "enable autostart", "enable auto start", "turn on autostart", "start on boot", "launch on startup", "enable startup",
        "disable autostart", "disable auto start", "turn off autostart", "disable startup", "don't start on boot",
        "autostart status", "is autostart enabled", "check autostart",
        "lock pc", "lock computer", "sleep", "mute", "unmute", "volume up", "volume down",
        "turn on wifi", "turn off wifi", "screenshot", "empty recycle bin", "close folders",
        "play", "pause", "resume", "play music", "pause music", "resume music", "toggle media",
        "next track", "next", "next song", "skip track", "previous track", "previous", "previous song"
    ) or text_lower.startswith("volume "):
        return True
    return False

def execute_command(text, quiet=False, image_base64=None, image_mime=None, window=None, stream_callback=None):
    add_user_command_history(text)
    from backend.sys_utils import logger
    logger.log_command(text, "processing")
    start_time = time.time()
    text_lower = text.lower().strip()
    if _is_direct_device_command(text_lower):
        result = _execute_command_internal(text, allow_llm_fallback=False, image_base64=image_base64, image_mime=image_mime, window=window)
    else:
        result = _execute_command_internal(text, allow_llm_fallback=True, image_base64=image_base64, image_mime=image_mime, window=window, stream_callback=stream_callback)
    execution_time = time.time() - start_time
    logger.log_command(text, f"completed in {execution_time:.2f}s", execution_time)
    if not quiet:
        add_system_log(f"Executed: {text[:50]}...")
    return result
