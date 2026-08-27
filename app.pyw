import webview
import os
import sys
import json
import threading
import time
import pystray
from PIL import Image
import socket

# Ensure streams never fail on Unicode/emojis in Windows console
try:
    for stream in (sys.stdout, sys.stderr):
        if stream and hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

# Import from sys_utils
from backend.sys_utils import (
    logger, setup_crash_recovery, update_heartbeat,
    ROOT_DIR, DB_DIR
)

# Import proactive engine and wake word
from backend.proactive_engine import (
    start_proactive_engine, stop_proactive_engine, record_interaction
)
from backend.wake_word import (
    start_wake_word, stop_wake_word, set_wake_word_enabled,
    is_wake_word_running, get_wake_word_status
)


# ─── Cross-window state tracking for the sphere ───
_sphere_state = {
    "listening": True,
    "speaking": True,
    "processing": True
}
_sphere_state_lock = threading.Lock()

should_exit_app = False
tray_icon = None

# When bundled by PyInstaller, assets are extracted to sys._MEIPASS
if getattr(sys, 'frozen', False):
    DIRECTORY = sys._MEIPASS
    FRONTEND_DIR = os.path.join(DIRECTORY, "frontend")
else:
    DIRECTORY = ROOT_DIR
    FRONTEND_DIR = os.path.join(DIRECTORY, "frontend")

# ──────────────────────────────────────────────────────────────
# JasvaAPI Class
# ──────────────────────────────────────────────────────────────
class JasvaAPI:
    """Python backend exposed directly to the JavaScript frontend via pywebview bridge."""

    def __init__(self):
        self._windows = {}  # name -> window reference
        self._window_visibility = {
            "chat": True,
            "top": True,
            "sphere": True,
            "bottom": True,
            "monitor": True,
            "control": True,
            "dashboard": True,
            "settings": False
        }

    def register_window(self, name, window):
        self._windows[name] = window

    def broadcast_js(self, js_code):
        """Evaluate JavaScript code in all active windows."""
        for win in self._windows.values():
            try:
                win.evaluate_js(js_code)
            except Exception as e:
                logger.debug(f"broadcast_js error: {e}")

    def toggle_panel_window(self, panel_name):
        """Toggle the visibility of a panel window."""
        win = self._windows.get(panel_name)
        if win:
            try:
                current_state = self._window_visibility.get(panel_name, True)
                new_state = not current_state
                if new_state:
                    win.show()
                    win.restore()
                else:
                    win.hide()
                self._window_visibility[panel_name] = new_state
                self.broadcast_js(f"if (window.syncWindowVisibilityState) window.syncWindowVisibilityState('{panel_name}', {str(new_state).lower()});")
            except Exception as e:
                print(f"Error toggling window {panel_name}: {e}")
        return json.dumps({"status": "success", "visible": self._window_visibility.get(panel_name, False)})

    def set_window(self, window):
        self._window = window

    def wake_up(self):
        """Show and restore all JASVA windows."""
        for name, win in self._windows.items():
            if name != "settings":
                try:
                    win.show()
                    win.restore()
                    self._window_visibility[name] = True
                except Exception as e:
                    logger.debug(f"wake_up error for '{name}': {e}")
        self.broadcast_js("if (window.syncWindowVisibilityState) { "
                         "window.syncWindowVisibilityState('chat', true); "
                         "window.syncWindowVisibilityState('top', true); "
                         "window.syncWindowVisibilityState('sphere', true); "
                         "window.syncWindowVisibilityState('bottom', true); "
                         "window.syncWindowVisibilityState('dashboard', true); "
                         "}")
        # Focus chat input
        chat_win = self._windows.get("chat") or self._windows.get("main")
        if chat_win:
            try:
                chat_win.evaluate_js("const el = document.querySelector('input, textarea'); if (el) el.focus();")
            except Exception:
                pass
        return json.dumps({"status": "success"})

    def hide_to_tray(self):
        """Hide all JASVA windows to system tray."""
        for name, win in self._windows.items():
            try:
                win.hide()
                self._window_visibility[name] = False
            except Exception as e:
                logger.debug(f"hide_to_tray error for '{name}': {e}")
        return json.dumps({"status": "success"})

    def toggle_visibility(self):
        """Toggle showing/hiding JASVA floating windows."""
        is_visible = self._window_visibility.get("chat", True)
        if is_visible:
            return self.hide_to_tray()
        else:
            return self.wake_up()

    def get_autostart_status(self):
        """Check if JASVA autostart is enabled."""
        from backend.command_router import is_autostart_enabled
        from backend.sys_utils import load_config
        cfg = load_config()
        enabled = bool(cfg.get("autostart", False) or is_autostart_enabled())
        return json.dumps({"status": "success", "enabled": enabled})

    def set_autostart(self, enabled):
        """Set autostart on Windows boot."""
        from backend.command_router import set_autostart
        from backend.sys_utils import load_config, save_config
        success = set_autostart(bool(enabled))
        if success:
            cfg = load_config()
            cfg["autostart"] = bool(enabled)
            save_config(cfg)
        return json.dumps({"status": "success" if success else "error", "enabled": bool(enabled)})

    def is_autostart_boot(self):
        """Check if the app was launched with the autostart flag."""
        return "--autostart" in sys.argv

    def execute_command(self, text, quiet=False, image_base64=None, image_mime=None):
        from backend.command_router import execute_command
        # Record user interaction for proactive engine
        record_interaction()
        # Create a streaming callback that pushes tokens to the chat window
        def _stream_cb(token):
            self.stream_token(token)
        result = execute_command(text, quiet=quiet, image_base64=image_base64, image_mime=image_mime, window=self._window, stream_callback=_stream_cb)
        return json.dumps(result)

    def see_pc_screen(self, prompt=None):
        """Analyze what is currently visible on the live PC screen into memory."""
        from backend.pc_agent import describe_pc_screen
        res = describe_pc_screen(prompt=prompt, window=self._window)
        return json.dumps(res)

    def run_pc_agent(self, task):
        """Run the autonomous PC desktop agent."""
        from backend.pc_agent import run_pc_agent
        res = run_pc_agent(task, window=self._window)
        return json.dumps(res)

    # ─── Wake Word Control ───

    def get_wake_word_status(self):
        """Return the current wake word detection status."""
        return json.dumps(get_wake_word_status())

    def set_wake_word_enabled(self, enabled):
        """Enable or disable wake word detection."""
        set_wake_word_enabled(bool(enabled))
        return json.dumps({"status": "success", "enabled": bool(enabled)})

    def record_user_interaction(self):
        """Record a user interaction event for the proactive engine."""
        record_interaction()
        return json.dumps({"status": "success"})

    def get_tts_audio(self, text):
        """Generate TTS audio base64 for frontend playback."""
        from backend.ai_services import call_edge_tts
        try:
            audio_b64 = call_edge_tts(text)
            if audio_b64:
                return json.dumps({"status": "success", "audio": audio_b64})
        except Exception as e:
            logger.warning(f"get_tts_audio error: {e}")
        return json.dumps({"status": "error"})

    def launch_scrcpy(self, device_type='phone'):
        """Launch optimized native scrcpy mirror for phone or TV."""
        from backend.sys_utils import launch_phone_mirror, load_config
        try:
            config = load_config()
            target = ""
            if device_type == 'tv':
                target = config.get("tv_ip", "")
            else:
                target = config.get("phone_ip", "")
            res = launch_phone_mirror(target)
            return json.dumps(res)
        except Exception as e:
            return json.dumps({"status": "error", "output": str(e)})

    def get_settings(self):
        from backend.sys_utils import get_credential_manager, load_config, BACKEND_DIR
        from backend.ai_services import get_all_elevenlabs_keys, fetch_elevenlabs_voices
        gemini_key = ""
        groq_key = ""
        puter_key = ""
        elevenlabs_key = ""
        
        # Try credential manager first
        try:
            cred_manager = get_credential_manager()
            gemini_key = cred_manager.get_api_key("gemini") or ""
            groq_key = cred_manager.get_api_key("groq") or ""
            puter_key = cred_manager.get_api_key("puter") or ""
            elevenlabs_key = cred_manager.get_api_key("elevenlabs") or ""
        except Exception:
            pass
        
        # Fallback to .env file
        if not gemini_key or not groq_key or not puter_key or not elevenlabs_key:
            env_path = os.path.join(BACKEND_DIR, ".env")
            if os.path.exists(env_path):
                try:
                    with open(env_path, "r") as f:
                        for line in f:
                            if "=" in line:
                                parts = line.strip().split("=", 1)
                                key = parts[0].strip()
                                val = parts[1].strip().strip('"').strip("'")
                                if key in ["GEMINI_API_KEY", "GOOGLE_API_KEY"]:
                                    gemini_key = val
                                elif key == "GROQ_API_KEY":
                                    groq_key = val
                                elif key == "PUTER_API_KEY":
                                    puter_key = val
                                elif key == "ELEVENLABS_API_KEY":
                                    elevenlabs_key = val
                except Exception:
                    pass
                
        config = load_config()
        config["gemini_key"] = gemini_key
        config["groq_key"] = groq_key
        config["puter_key"] = puter_key
        config["elevenlabs_key"] = elevenlabs_key
        
        # Fetch ElevenLabs voices using key rotation
        elevenlabs_voices = []
        try:
            el_keys = get_all_elevenlabs_keys()
            for key in el_keys:
                try:
                    voices = fetch_elevenlabs_voices(key)
                    if voices:
                        elevenlabs_voices = voices
                        break
                except Exception:
                    pass
        except Exception:
            pass
        config["elevenlabs_voices"] = elevenlabs_voices
        
        return json.dumps(config)

    def save_settings(self, config_json):
        from backend.sys_utils import get_credential_manager, save_config, load_config, BACKEND_DIR
        try:
            config = json.loads(config_json)

            # Merge over the existing config so device addresses (tv_ip, phone_ip)
            # and other non-settings keys are never wiped by a settings save.
            existing = load_config()
            existing.update(config)

            # Write JSON config file — API keys are persisted to credential manager, never to config.json
            config_no_keys = {k: v for k, v in existing.items() if k not in ("gemini_key", "groq_key", "puter_key", "elevenlabs_key")}
            save_config(config_no_keys)

            # Persist API keys to credential manager
            try:
                cred_manager = get_credential_manager()
                if "gemini_key" in config:
                    cred_manager.set_api_key("gemini", config["gemini_key"])
                if "groq_key" in config:
                    cred_manager.set_api_key("groq", config["groq_key"])
                if "puter_key" in config:
                    cred_manager.set_api_key("puter", config["puter_key"])
                if "elevenlabs_key" in config:
                    cred_manager.set_api_key("elevenlabs", config["elevenlabs_key"])
            except Exception:
                # Fallback to .env file if credential manager fails
                env_path = os.path.join(BACKEND_DIR, ".env")
                existing_lines = {}
                if os.path.exists(env_path):
                    with open(env_path, "r") as f:
                        for line in f:
                            if "=" in line:
                                parts = line.strip().split("=", 1)
                                existing_lines[parts[0].strip()] = parts[1].strip()

                if "gemini_key" in config:
                    existing_lines["GEMINI_API_KEY"] = f"\"{config['gemini_key']}\""
                if "groq_key" in config:
                    existing_lines["GROQ_API_KEY"] = f"\"{config['groq_key']}\""
                if "puter_key" in config:
                    existing_lines["PUTER_API_KEY"] = f"\"{config['puter_key']}\""
                if "elevenlabs_key" in config:
                    existing_lines["ELEVENLABS_API_KEY"] = f"\"{config['elevenlabs_key']}\""

                with open(env_path, "w") as f:
                    for k, v in existing_lines.items():
                        f.write(f"{k}={v}\n")
                    
            if "autostart" in config:
                try:
                    from backend.command_router import set_autostart
                    set_autostart(bool(config["autostart"]))
                except Exception as e:
                    logger.error(f"Error applying autostart on save: {e}")

            if "always_listening" in config:
                try:
                    set_wake_word_enabled(bool(config["always_listening"]))
                except Exception as e:
                    logger.error(f"Error applying wake word on save: {e}")

            return json.dumps({"status": "success"})
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    def get_notifications(self):
        """Retrieve and clear unread background notifications/alerts."""
        from backend.memory_scheduler import pop_unread_notifications
        notifs = pop_unread_notifications()
        return json.dumps(notifs)

    def get_recent_notifications(self, limit=5):
        """Retrieve recent notifications without clearing the unread flag."""
        from backend.memory_scheduler import load_notifications
        try:
            limit = int(limit)
        except Exception:
            limit = 5
        notifs = load_notifications()
        return json.dumps(notifs[-limit:])


    def get_active_schedules(self):
        """Retrieve active (unfired) alarms and timers."""
        from backend.memory_scheduler import get_active_schedules
        schedules = get_active_schedules()
        return json.dumps(schedules)

    def remove_schedule(self, schedule_id):
        """Cancel/delete an alarm or timer by ID."""
        from backend.memory_scheduler import remove_schedule
        success = remove_schedule(schedule_id)
        return json.dumps({"status": "success" if success else "error"})

    def get_memory_stats(self):
        """Retrieve statistics about the memory database."""
        from backend.memory_scheduler import get_memory_stats
        stats = get_memory_stats()
        return json.dumps(stats)

    def get_system_metrics(self):
        """Retrieve live system metrics for the graphs."""
        from backend.sys_utils import get_system_metrics
        try:
            return json.dumps(get_system_metrics())
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    def minimize_window(self):
        """Minimize the main JASVA window."""
        if hasattr(self, '_window') and self._window:
            self._window.minimize()
        return json.dumps({"status": "success"})

    def close_window(self):
        """Terminate the entire JASVA application."""
        os._exit(0)

    def close_current_window(self):
        """Hide the active window and update its visibility state."""
        active = webview.active_window()
        if active:
            for name, win in self._windows.items():
                if win == active:
                    try:
                        win.hide()
                        self._window_visibility[name] = False
                        self.broadcast_js(f"if (window.syncWindowVisibilityState) window.syncWindowVisibilityState('{name}', false);")
                    except Exception:
                        pass
                    break
        return json.dumps({"status": "success"})

    def close_panel_window(self, panel_name):
        """Hide the specified panel window."""
        win = self._windows.get(panel_name)
        if win:
            try:
                win.hide()
                self._window_visibility[panel_name] = False
                self.broadcast_js(f"if (window.syncWindowVisibilityState) window.syncWindowVisibilityState('{panel_name}', false);")
            except Exception as e:
                print(f"Error hiding window {panel_name}: {e}")
        return json.dumps({"status": "success"})

    def set_panel_window_visibility(self, panel_name, is_visible):
        """Set the visibility of a panel window explicitly."""
        win = self._windows.get(panel_name)
        if win:
            try:
                if is_visible:
                    win.show()
                    win.restore()
                else:
                    win.hide()
                self._window_visibility[panel_name] = is_visible
                self.broadcast_js(f"if (window.syncWindowVisibilityState) window.syncWindowVisibilityState('{panel_name}', {str(is_visible).lower()});")
            except Exception as e:
                print(f"Error setting visibility of window {panel_name}: {e}")
        return json.dumps({"status": "success", "visible": self._window_visibility.get(panel_name, False)})

    def minimize_current_window(self):
        """Minimize the window that made this request."""
        active = webview.active_window()
        if active:
            active.minimize()
        return json.dumps({"status": "success"})

    def show_settings_window(self):
        """Show the settings window."""
        settings_win = self._windows.get("settings")
        if settings_win:
            try:
                settings_win.show()
                settings_win.restore()
            except Exception:
                pass
        return json.dumps({"status": "success"})

    def hide_settings_window(self):
        """Hide the settings window."""
        settings_win = self._windows.get("settings")
        if settings_win:
            try:
                settings_win.hide()
            except Exception:
                pass
        return json.dumps({"status": "success"})

    def quick_button(self, device, button):
        """Fast direct button press - bypasses command router for instant response."""
        import time
        start = time.time()
        try:
            if device == "tv":
                from backend.tv_manager import tv_manager
                result = tv_manager.send_button(button)
            elif device == "phone":
                from backend.adb_manager import adb_manager
                from backend.sys_utils import load_config
                # Never target the TV: it is often listed FIRST in adb devices.
                tv_ip = load_config().get("tv_ip", "")
                tv_target = f"{tv_ip}:5555" if tv_ip else ""
                # Cache the phone serial so repeated presses skip the adb scan.
                target = getattr(self, "_cached_phone_serial", "")
                if not target:
                    devices = adb_manager.list_devices()
                    active = [d for d in devices if d["status"] == "device" and d["id"] != tv_target]
                    if not active:
                        result = {"status": "error", "message": "No phone connected"}
                        self._cached_phone_serial = ""
                    else:
                        target = active[0]["id"]
                        self._cached_phone_serial = target
                if target:
                    res = adb_manager.send_key_fast(target, button)
                    if res["status"] == "error":
                        # Phone may have dropped; re-scan and retry once.
                        self._cached_phone_serial = ""
                        devices = adb_manager.list_devices()
                        active = [d for d in devices if d["status"] == "device" and d["id"] != tv_target]
                        if active:
                            self._cached_phone_serial = active[0]["id"]
                            adb_manager.send_key_fast(self._cached_phone_serial, button)
                    result = {"status": "success"}
            else:
                result = {"status": "error", "message": "Unknown device"}
            elapsed = time.time() - start
            return json.dumps({"status": "ok", "ms": int(elapsed * 1000)})
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    def show_ctrl_window(self, device):
        """Show the control window for phone or tv."""
        win_name = f"{device}_ctrl"
        win = self._windows.get(win_name)
        if win:
            try:
                win.show()
                win.restore()
            except Exception:
                pass
        # Pre-warm the persistent adb shell in the background so the first
        # button press is instant instead of waiting for the shell spawn.
        try:
            from backend.adb_manager import adb_manager
            from backend.sys_utils import load_config

            def _warm():
                try:
                    if device == "tv":
                        tv_ip = load_config().get("tv_ip", "")
                        if tv_ip:
                            adb_manager.prewarm_shell(tv_ip)
                    else:
                        tv_ip = load_config().get("tv_ip", "")
                        tv_target = f"{tv_ip}:5555" if tv_ip else ""
                        for d in adb_manager.list_devices():
                            if d["status"] == "device" and d["id"] != tv_target:
                                adb_manager.prewarm_shell(d["id"])
                                break
                except Exception:
                    pass

            threading.Thread(target=_warm, daemon=True).start()
        except Exception:
            pass
        return json.dumps({"status": "success"})

    def hide_ctrl_window(self, device):
        """Hide the control window for phone or tv."""
        win_name = f"{device}_ctrl"
        win = self._windows.get(win_name)
        if win:
            try:
                win.hide()
            except Exception:
                pass
        return json.dumps({"status": "success"})

    def get_scratchpad(self):
        """Retrieve persistent scratchpad content."""
        txt_path = os.path.join(DB_DIR, "scratchpad.txt")
        if os.path.exists(txt_path):
            try:
                with open(txt_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                pass
        return ""

    def save_scratchpad(self, text):
        """Save persistent scratchpad content."""
        txt_path = os.path.join(DB_DIR, "scratchpad.txt")
        try:
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(text)
            return json.dumps({"status": "success"})
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    def get_memory_profile(self):
        """Retrieve user context, role, goals, and facts from memory."""
        from backend.memory_scheduler import load_profile
        try:
            profile = load_profile()
            return json.dumps(profile)
        except Exception as e:
            return json.dumps({"identity": {}, "facts": [], "preferences": {}})

    def save_memory_profile(self, profile_json):
        """Save updated user context, role, goals, and rules to memory."""
        from backend.memory_scheduler import save_profile
        try:
            profile = json.loads(profile_json)
            save_profile(profile)
            return json.dumps({"status": "success"})
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    def add_memory_fact(self, fact_text):
        """Add a new fact to memory."""
        from backend.memory_scheduler import add_fact
        try:
            if fact_text and str(fact_text).strip():
                add_fact(str(fact_text).strip())
            return json.dumps({"status": "success"})
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    def update_memory_fact(self, old_fact, new_fact):
        """Edit an existing fact in memory."""
        from backend.memory_scheduler import edit_fact
        try:
            edit_fact(str(old_fact), str(new_fact))
            return json.dumps({"status": "success"})
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    def delete_memory_fact(self, fact_text):
        """Delete a fact from memory."""
        from backend.memory_scheduler import delete_fact
        try:
            delete_fact(str(fact_text))
            return json.dumps({"status": "success"})
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    def clear_memory(self):
        """Clear all memory and facts."""
        from backend.memory_scheduler import clear_all_memory
        try:
            clear_all_memory()
            return json.dumps({"status": "success"})
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    def get_plugins_list(self):
        """Retrieve list of active skills and plugins."""
        from backend.plugins import get_all_plugins_info, load_plugins
        try:
            plugins = get_all_plugins_info()
            if not plugins:
                load_plugins()
                plugins = get_all_plugins_info()
            return json.dumps(plugins)
        except Exception as e:
            return json.dumps([])

    # ─── Cross-window state bridge for the sphere ───

    def set_sphere_state(self, listening, speaking, processing, recognizing=False):
        """Called by the chat window JS to update the sphere's visual state."""
        global _sphere_state
        with _sphere_state_lock:
            _sphere_state["listening"] = bool(listening)
            _sphere_state["speaking"] = bool(speaking)
            _sphere_state["processing"] = bool(processing)
            _sphere_state["recognizing"] = bool(recognizing)
        return json.dumps({"status": "success"})

    def get_sphere_state(self):
        """Called by the sphere window JS to read the current state."""
        with _sphere_state_lock:
            return json.dumps(_sphere_state)

    def toggle_mic(self):
        """Called by the sphere window when user clicks the blob.
        Evaluates JS in the chat window to toggle its microphone."""
        chat_win = self._windows.get("chat")
        if chat_win:
            try:
                chat_win.evaluate_js("if(typeof toggleMic==='function') toggleMic();")
            except Exception as e:
                print(f"toggle_mic cross-window error: {e}")
        return json.dumps({"status": "success"})

    def get_tts_audio(self, text):
        """Generates TTS audio on a background thread without blocking main command execution."""
        from backend.ai_services import call_edge_tts
        try:
            audio = call_edge_tts(text)
            return json.dumps({"status": "success", "audio": audio})
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    # ─── Streaming Token Bridge ───

    def stream_token(self, token):
        """Push a partial LLM token to the chat window for incremental display."""
        chat_win = self._windows.get("chat")
        if chat_win:
            try:
                # Escape for safe JS string injection
                safe_token = json.dumps(token)
                chat_win.evaluate_js(f"if(window.onStreamToken)window.onStreamToken({safe_token});")
            except Exception:
                pass

    def stream_start(self):
        """Signal the chat window that streaming has begun."""
        chat_win = self._windows.get("chat")
        if chat_win:
            try:
                chat_win.evaluate_js("if(window.onStreamStart)window.onStreamStart();")
            except Exception:
                pass

    def stream_end(self):
        """Signal the chat window that streaming has finished."""
        chat_win = self._windows.get("chat")
        if chat_win:
            try:
                chat_win.evaluate_js("if(window.onStreamEnd)window.onStreamEnd();")
            except Exception:
                pass

    def get_device_screen_base64(self, device_id=None):
        """High-speed compressed screen capture for any ADB device (Phone, TV, Tablet)."""
        from backend.adb_manager import adb_manager
        from backend.command_router import get_active_phone_id, get_active_tv_id
        
        target_id = device_id
        if not target_id or target_id == "phone":
            target_id = get_active_phone_id()
        elif target_id == "tv":
            target_id = get_active_tv_id()

        devices = [d for d in adb_manager.list_devices() if d["status"] == "device"]
        if not target_id and devices:
            target_id = devices[0]["id"]

        if not target_id:
            return json.dumps({"status": "error", "message": "No connected device found", "devices": []})

        try:
            import subprocess
            import io
            from PIL import Image
            import base64

            cmd = [adb_manager.adb_path, "-s", target_id, "exec-out", "screencap", "-p"]
            proc = subprocess.run(cmd, capture_output=True, timeout=3, creationflags=subprocess.CREATE_NO_WINDOW)
            if proc.returncode == 0 and proc.stdout:
                img = Image.open(io.BytesIO(proc.stdout))
                orig_w, orig_h = img.size
                
                # Landscape (TV / Tablet) vs Portrait (Phone)
                if orig_w > orig_h:
                    new_w = 480
                    new_h = int(orig_h * (480 / orig_w))
                else:
                    new_w = 360
                    new_h = int(orig_h * (360 / orig_w))

                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                buf = io.BytesIO()
                img.convert("RGB").save(buf, format="JPEG", quality=55, optimize=True)
                b64_data = base64.b64encode(buf.getvalue()).decode("utf-8")

                return json.dumps({
                    "status": "success",
                    "image": f"data:image/jpeg;base64,{b64_data}",
                    "device_id": target_id,
                    "devices": devices,
                    "orig_width": orig_w,
                    "orig_height": orig_h,
                    "is_landscape": orig_w > orig_h
                })
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e), "devices": devices})

        return json.dumps({"status": "error", "message": "Screencap failed", "devices": devices})

    def get_phone_screen_base64(self, device_id=None):
        """Fetch screen specifically for Phone (strictly excluding TV)."""
        from backend.command_router import get_active_phone_id
        from backend.sys_utils import load_config
        target = device_id or get_active_phone_id()
        raw_res = self.get_device_screen_base64(target)
        try:
            parsed = json.loads(raw_res)
            tv_ip = load_config().get("tv_ip", "").strip()
            if "devices" in parsed and isinstance(parsed["devices"], list):
                parsed["devices"] = [d for d in parsed["devices"] if not (tv_ip and (d["id"] == tv_ip or d["id"] == f"{tv_ip}:5555" or tv_ip in d["id"]))]
            return json.dumps(parsed)
        except Exception:
            return raw_res

    def get_tv_screen_base64(self, tv_ip=None):
        """Fetch screen specifically for Smart TV (ignoring Phone)."""
        from backend.command_router import get_active_tv_id
        target_ip = tv_ip or get_active_tv_id()
        return self.get_device_screen_base64(target_ip)

    def phone_tap(self, x, y, device_id=None):
        """Direct low-latency phone tap via persistent ADB shell."""
        from backend.adb_manager import adb_manager
        from backend.command_router import get_active_phone_id
        target = device_id or get_active_phone_id()
        if not target:
            return json.dumps({"status": "error", "message": "No phone attached"})
        res = adb_manager.send_tap_fast(target, int(x), int(y))
        return json.dumps(res)

    def phone_swipe(self, x1, y1, x2, y2, duration=300, device_id=None):
        """Direct low-latency phone swipe/drag via persistent ADB shell."""
        from backend.adb_manager import adb_manager
        from backend.command_router import get_active_phone_id
        target = device_id or get_active_phone_id()
        if not target:
            return json.dumps({"status": "error", "message": "No phone attached"})
        res = adb_manager.send_swipe_fast(target, int(x1), int(y1), int(x2), int(y2), int(duration))
        return json.dumps(res)

    def phone_key(self, keycode, device_id=None):
        """Direct low-latency keyevent via persistent ADB shell."""
        from backend.adb_manager import adb_manager
        from backend.command_router import get_active_phone_id
        target = device_id or get_active_phone_id()
        if not target:
            return json.dumps({"status": "error", "message": "No phone attached"})
        res = adb_manager.send_key_fast(target, str(keycode))
        return json.dumps(res)

    def phone_text(self, text, device_id=None):
        """Direct low-latency text input via persistent ADB shell."""
        from backend.adb_manager import adb_manager
        from backend.command_router import get_active_phone_id
        target = device_id or get_active_phone_id()
        if not target:
            return json.dumps({"status": "error", "message": "No phone attached"})
        res = adb_manager.send_text_fast(target, str(text))
        return json.dumps(res)

    def launch_scrcpy(self, device_id=None):
        """Launch standalone native scrcpy mirror window with device separation."""
        from backend.sys_utils import launch_phone_mirror
        from backend.command_router import get_active_phone_id, get_active_tv_id
        
        target = device_id
        if target == "tv" or target == "smart_tv":
            target = get_active_tv_id()
        elif not target or target == "phone":
            target = get_active_phone_id()

        res = launch_phone_mirror(target or "")
        return json.dumps(res)

    def launch_all_scrcpy(self):
        """Launch standalone native scrcpy mirror windows for all connected devices at once."""
        from backend.sys_utils import launch_all_mirrors
        res = launch_all_mirrors()
        return json.dumps(res)

    # ─── Media Player Control Endpoints ───

    def get_media_status(self):
        """Retrieve live metadata of currently playing media."""
        from backend.music_monitor import music_monitor
        try:
            state = music_monitor.get_current_state()
            return json.dumps(state)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    def control_media(self, action):
        """Control media playback (toggle, next, prev, play, pause)."""
        from backend.music_monitor import control_playback
        from backend.sys_utils import send_media_key
        try:
            action_lower = str(action).lower().strip()
            res = control_playback(action_lower)
            if res.get("status") == "error":
                # Fallback to standard Windows virtual keys
                if action_lower in ("toggle", "play", "pause"):
                    send_media_key(0xB3)
                elif action_lower in ("next", "skip"):
                    send_media_key(0xB0)
                elif action_lower in ("prev", "previous"):
                    send_media_key(0xB1)
                res = {"status": "ok"}
            return json.dumps(res)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    def seek_media(self, position_ms):
        """Seek playback position forward or backward in milliseconds."""
        from backend.music_monitor import control_playback
        try:
            pos = int(position_ms)
            res = control_playback("seek", position_ms=pos)
            return json.dumps(res)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    def get_media_lyrics(self, title, artist):
        """Fetch synchronized lyrics for track from LRCLIB."""
        from backend.music_monitor import music_monitor
        try:
            lyrics = music_monitor.fetch_lyrics(str(title), str(artist))
            return json.dumps({"status": "success", "lyrics": lyrics})
        except Exception as e:
            return json.dumps({"status": "error", "lyrics": [], "message": str(e)})

    def set_system_volume(self, level):
        """Set Windows master audio volume (0-100)."""
        from backend.sys_utils import set_windows_volume
        try:
            val = int(level)
            set_windows_volume(val)
            return json.dumps({"status": "success", "volume": val})
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    def get_system_volume(self):
        """Get Windows master audio volume."""
        from backend.sys_utils import get_windows_volume
        try:
            vol = get_windows_volume()
            return json.dumps({"status": "success", "volume": vol})
        except Exception as e:
            return json.dumps({"status": "error", "volume": 50, "message": str(e)})

    def launch_media_app(self, app_name):
        """Launch Spotify, YouTube Music, Apple Music, VLC, etc."""
        from backend.music_monitor import launch_media_app
        try:
            res = launch_media_app(str(app_name))
            return json.dumps(res)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    # ─── Calendar & Agenda Endpoints ───

    def get_calendar_events(self, month_str=None):
        """Retrieve calendar events, optionally filtered by YYYY-MM."""
        from backend.calendar_manager import load_calendar_events, get_events_for_month
        try:
            if month_str and "-" in month_str:
                parts = month_str.split("-")
                events = get_events_for_month(int(parts[0]), int(parts[1]))
            else:
                events = load_calendar_events()
            return json.dumps(events)
        except Exception as e:
            return json.dumps([])

    def get_calendar_agenda(self):
        """Retrieve upcoming agenda timeline."""
        from backend.calendar_manager import get_upcoming_agenda
        try:
            agenda = get_upcoming_agenda(limit=15)
            return json.dumps(agenda)
        except Exception as e:
            return json.dumps([])

    def save_calendar_event(self, event_json):
        """Add or save a calendar event."""
        from backend.calendar_manager import add_event
        try:
            data = json.loads(event_json) if isinstance(event_json, str) else event_json
            ev = add_event(
                title=data.get("title", ""),
                event_date=data.get("date", ""),
                event_time=data.get("time", "09:00"),
                category=data.get("category", "WORK"),
                description=data.get("description", ""),
                duration_mins=int(data.get("duration_mins", 60)),
                set_reminder=bool(data.get("set_reminder", True))
            )
            return json.dumps({"status": "success", "event": ev})
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    def delete_calendar_event(self, event_id):
        """Delete a calendar event by ID."""
        from backend.calendar_manager import delete_event
        try:
            ok = delete_event(str(event_id))
            return json.dumps({"status": "success" if ok else "error"})
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    def toggle_calendar_event(self, event_id):
        """Toggle completed status of a calendar event."""
        from backend.calendar_manager import toggle_event_status
        try:
            ev = toggle_event_status(str(event_id))
            return json.dumps({"status": "success" if ev else "error", "event": ev})
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    def sync_google_calendar(self):
        """Trigger sync with linked Google Calendar (OAuth or iCal)."""
        from backend.calendar_manager import sync_from_google
        try:
            res = sync_from_google()
            return json.dumps(res)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    def get_google_calendar_status(self):
        """Check if Google Calendar is linked and get stats."""
        from backend.calendar_manager import get_google_calendar_status
        try:
            res = get_google_calendar_status()
            return json.dumps(res)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    def get_calendar_feeds(self):
        """Get all configured calendar feeds."""
        from backend.calendar_manager import get_calendar_feeds
        try:
            feeds = get_calendar_feeds()
            return json.dumps(feeds)
        except Exception as e:
            return json.dumps([])

    def add_calendar_feed(self, feed_json):
        """Add or update a calendar feed (supports up to 5+ simultaneous calendars)."""
        from backend.calendar_manager import add_calendar_feed
        try:
            data = json.loads(feed_json) if isinstance(feed_json, str) else feed_json
            res = add_calendar_feed(
                name=data.get("name", "Google Calendar"),
                url=data.get("url", ""),
                color=data.get("color")
            )
            return json.dumps(res)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    def remove_calendar_feed(self, feed_id):
        """Remove a calendar feed by ID."""
        from backend.calendar_manager import remove_calendar_feed
        try:
            res = remove_calendar_feed(str(feed_id))
            return json.dumps(res)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    def set_google_ical_url(self, url):
        """Link Google Calendar via Secret address in iCal format."""
        from backend.calendar_manager import add_calendar_feed
        try:
            res = add_calendar_feed(name="Primary", url=str(url))
            return json.dumps(res)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    def start_google_oauth(self, credentials_json=None):
        """Start Google Calendar OAuth login flow."""
        from backend.calendar_manager import start_google_oauth_flow
        try:
            res = start_google_oauth_flow(credentials_json)
            return json.dumps(res)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    def export_calendar_ics(self):
        """Export calendar to local .ics file."""
        from backend.calendar_manager import export_to_ics
        try:
            path = export_to_ics()
            return json.dumps({"status": "success", "file_path": path})
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    def quick_button(self, device, button):
        """Fast direct button press - bypasses command router for instant response."""
        import time
        start = time.time()
        try:
            if device == "tv":
                from backend.tv_manager import tv_manager
                result = tv_manager.send_button(button)
            elif device == "phone":
                from backend.adb_manager import adb_manager
                from backend.sys_utils import load_config
                # Never target the TV: it is often listed FIRST in adb devices.
                tv_ip = load_config().get("tv_ip", "")
                tv_target = f"{tv_ip}:5555" if tv_ip else ""
                # Cache the phone serial so repeated presses skip the adb scan.
                target = getattr(self, "_cached_phone_serial", "")
                if not target:
                    devices = adb_manager.list_devices()
                    active = [d for d in devices if d["status"] == "device" and d["id"] != tv_target]
                    if not active:
                        result = {"status": "error", "message": "No phone connected"}
                        self._cached_phone_serial = ""
                    else:
                        target = active[0]["id"]
                        self._cached_phone_serial = target
                if target:
                    res = adb_manager.send_key_fast(target, button)
                    if res["status"] == "error":
                        # Phone may have dropped; re-scan and retry once.
                        self._cached_phone_serial = ""
                        devices = adb_manager.list_devices()
                        active = [d for d in devices if d["status"] == "device" and d["id"] != tv_target]
                        if active:
                            self._cached_phone_serial = active[0]["id"]
                            adb_manager.send_key_fast(self._cached_phone_serial, button)
                    result = {"status": "success"}
            else:
                result = {"status": "error", "message": "Unknown device"}
            elapsed = time.time() - start
            return json.dumps({"status": "ok", "ms": int(elapsed * 1000)})
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    def toggle_fullscreen(self):
        """Toggle fullscreen mode on the main window."""
        win = self._windows.get("main")
        if win:
            try:
                win.toggle_fullscreen()
                return json.dumps({"status": "success"})
            except Exception as e:
                return json.dumps({"status": "error", "message": str(e)})
        return json.dumps({"status": "error", "message": "Main window not found"})

    def show_ctrl_window(self, device):
        """Pre-warm device adb connection without spawning extra windows."""
        try:
            from backend.adb_manager import adb_manager
            from backend.sys_utils import load_config

            def _warm():
                try:
                    if device == "tv":
                        tv_ip = load_config().get("tv_ip", "")
                        if tv_ip:
                            adb_manager.prewarm_shell(tv_ip)
                    else:
                        tv_ip = load_config().get("tv_ip", "")
                        tv_target = f"{tv_ip}:5555" if tv_ip else ""
                        for d in adb_manager.list_devices():
                            if d["status"] == "device" and d["id"] != tv_target:
                                adb_manager.prewarm_shell(d["id"])
                                break
                except Exception:
                    pass

            threading.Thread(target=_warm, daemon=True).start()
        except Exception:
            pass
        return json.dumps({"status": "success"})

    def hide_ctrl_window(self, device):
        """No-op when running unified single-window layout."""
        return json.dumps({"status": "success"})
        if win:
            try:
                win.hide()
            except Exception:
                pass
        return json.dumps({"status": "success"})

    def export_calendar_ics(self):
        """Export all calendar events to standard iCalendar (.ics) file."""
        from backend.calendar_manager import export_to_ics
        try:
            path = export_to_ics()
            return json.dumps({"status": "success", "path": path})
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})





def main():
    api = JasvaAPI()
    
    # ─── Single Instance Lock & Wakeup ───
    import socket
    try:
        instance_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        instance_socket.bind(('127.0.0.1', 13579))
        instance_socket.listen(1)
        
        def listen_for_wakeup():
            while not should_exit_app:
                try:
                    conn, addr = instance_socket.accept()
                    conn.close()
                    # Wake up existing window
                    api.wake_up()
                except Exception:
                    break
        
        threading.Thread(target=listen_for_wakeup, daemon=True).start()
    except socket.error:
        # Send wake signal to the running instance by connecting to port 13579
        try:
            wake_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            wake_conn.connect(('127.0.0.1', 13579))
            wake_conn.close()
        except Exception:
            pass
        print("JASVA is already running. Waking existing instance and exiting.")
        sys.exit(0)

    is_autostart = "--autostart" in sys.argv
    icon_path = os.path.join(FRONTEND_DIR, "icon.ico")
    tray_started = False

    # ─── Create Main Application Window ───
    main_window = webview.create_window(
        title="JASVA Quantum OS",
        url=os.path.join(FRONTEND_DIR, "index.html"),
        width=1380,
        height=880,
        min_size=(900, 600),
        fullscreen=True,
        frameless=False,
        easy_drag=True,
        hidden=False,
        background_color="#020408",
        text_select=True,
        js_api=api
    )

    for name in ["main", "chat", "top", "sphere", "bottom", "monitor", "dashboard", "control", "settings", "phone_ctrl", "tv_ctrl"]:
        api.register_window(name, main_window)
    api.set_window(main_window)

    def setup_tray():
        global tray_icon
        try:
            # Initialize COM in STA (Single-Threaded Apartment) mode for this thread
            import ctypes
            try:
                ctypes.windll.ole32.CoInitializeEx(None, 0x2) # 0x2 = COINIT_APARTMENTTHREADED
            except Exception:
                try:
                    ctypes.windll.ole32.CoInitialize(None)
                except Exception:
                    pass

            icon_file = os.path.join(FRONTEND_DIR, "icon.ico")
            if os.path.exists(icon_file):
                img = Image.open(icon_file)
            else:
                img = Image.new('RGB', (64, 64), color=(0, 242, 254))
                
            def on_show_window(icon, item):
                def run_show():
                    api.wake_up()
                threading.Thread(target=run_show, daemon=True).start()

            def on_hide_window(icon, item):
                def run_hide():
                    api.hide_to_tray()
                threading.Thread(target=run_hide, daemon=True).start()

            def on_toggle_autostart(icon, item):
                def run_toggle():
                    from backend.command_router import is_autostart_enabled, set_autostart
                    from backend.sys_utils import load_config, save_config
                    new_val = not is_autostart_enabled()
                    set_autostart(new_val)
                    cfg = load_config()
                    cfg["autostart"] = new_val
                    save_config(cfg)
                threading.Thread(target=run_toggle, daemon=True).start()

            def get_autostart_checked(item):
                from backend.command_router import is_autostart_enabled
                return is_autostart_enabled()

            def on_toggle_wakeword(icon, item):
                def run_toggle_ww():
                    from backend.wake_word import set_wake_word_enabled, get_wake_word_status
                    from backend.sys_utils import load_config, save_config
                    status = get_wake_word_status()
                    new_val = not status.get("enabled", True)
                    set_wake_word_enabled(new_val)
                    cfg = load_config()
                    cfg["always_listening"] = new_val
                    save_config(cfg)
                threading.Thread(target=run_toggle_ww, daemon=True).start()

            def get_wakeword_checked(item):
                from backend.wake_word import get_wake_word_status
                return get_wake_word_status().get("enabled", False)

            def on_exit(icon, item):
                global should_exit_app
                should_exit_app = True
                def run_exit():
                    try:
                        icon.stop()
                    except Exception:
                        pass
                    os._exit(0)
                threading.Thread(target=run_exit, daemon=True).start()

            menu = pystray.Menu(
                pystray.MenuItem('Show JASVA', on_show_window, default=True),
                pystray.MenuItem('Hide to Tray', on_hide_window),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem('Run on Windows Startup', on_toggle_autostart, checked=get_autostart_checked),
                pystray.MenuItem('Wake Word Listening', on_toggle_wakeword, checked=get_wakeword_checked),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem('Exit', on_exit)
            )
            
            tray_icon = pystray.Icon("JASVA", img, "JASVA Holographic Interface", menu)
            tray_icon.run()
        except Exception as e:
            print(f"Error setting up system tray icon: {e}")

    def configure_webview_permissions(window):
        """Auto-grant microphone permissions on WebView2."""
        try:
            if not hasattr(window, 'native') or not window.native:
                return
            webview_control = window.native.webview
            if not webview_control:
                return
            
            def configure_permissions():
                try:
                    core_webview2 = webview_control.CoreWebView2
                    if not core_webview2:
                        return
                    
                    def handle_permission(sender, args):
                        try:
                            args.State = args.State.Allow
                            args.Handled = True
                        except Exception as ex:
                            print(f"Error handling permission: {ex}")
                    
                    core_webview2.PermissionRequested += handle_permission
                except Exception as ex:
                    print(f"Inner configure permissions error: {ex}")

            try:
                from System import Action
                if webview_control.InvokeRequired:
                    webview_control.Invoke(Action(configure_permissions))
                else:
                    configure_permissions()
            except ImportError:
                if webview_control.InvokeRequired:
                    webview_control.Invoke(configure_permissions)
                else:
                    configure_permissions()
        except Exception as e:
            print(f"Could not configure native WebView2 permissions: {e}")

    def on_loaded():
        configure_webview_permissions(main_window)
        nonlocal tray_started
        if not tray_started:
            tray_started = True
            tray_thread = threading.Thread(target=setup_tray, daemon=True)
            tray_thread.start()

    def on_closing():
        global should_exit_app
        if not should_exit_app:
            main_window.hide()
            try:
                main_window.evaluate_js("if (window.onWindowVisibilityChanged) window.onWindowVisibilityChanged(false);")
            except Exception:
                pass
            return False
        return True

    def on_closed():
        print("Stopping background scheduler...")
        from backend.memory_scheduler import stop_scheduler
        stop_scheduler()

        # Stop proactive engine and wake word
        try:
            stop_proactive_engine()
        except Exception:
            pass
        try:
            stop_wake_word()
        except Exception:
            pass
        
        # Stop multi-device HTTP/WS server
        try:
            from backend.multi_device_server import device_server
            device_server.stop()
        except Exception:
            pass
            
        global tray_icon
        if tray_icon:
            try:
                tray_icon.stop()
            except Exception:
                pass
        os._exit(0)

    # Bind event hooks
    main_window.events.loaded += on_loaded
    main_window.events.closing += on_closing
    main_window.events.closed += on_closed

    # Start the background scheduler
    print("Starting background scheduler...")
    from backend.memory_scheduler import start_scheduler
    start_scheduler()

    # Start Google Calendar background auto-sync
    try:
        from backend.calendar_manager import start_calendar_auto_sync
        start_calendar_auto_sync()
    except Exception as e:
        print(f"Error starting calendar auto sync: {e}")

    # Start the multi-device integration server
    print("Starting multi-device integration server...")
    try:
        from backend.multi_device_server import device_server
        device_server.start()
    except Exception as e:
        print(f"Error starting multi-device server: {e}")

    # Start proactive intelligence engine
    print("Starting proactive intelligence engine...")
    try:
        start_proactive_engine(api)
    except Exception as e:
        print(f"Error starting proactive engine: {e}")

    # Start wake word detection
    print("Starting wake word detection...")
    def _on_wake_detected():
        """Called when the wake word is heard — triggers mic in the chat window."""
        logger.info("Wake word detected — activating speech recognition.")
        # Update sphere to listening state
        api.set_sphere_state(True, False, False, False)
        # Trigger speech recognition in the chat/main window
        chat_win = api._windows.get("chat") or api._windows.get("main")
        if chat_win:
            try:
                chat_win.evaluate_js(
                    "if(window.onWakeWordDetected) window.onWakeWordDetected();"
                )
            except Exception as e:
                logger.debug(f"Wake word JS eval error: {e}")

    try:
        start_wake_word(callback=_on_wake_detected)
    except Exception as e:
        print(f"Wake word detection not available: {e}")

    # Auto-connect to saved TV and phone IPs on startup
    def auto_connect_devices():
        try:
            from backend.sys_utils import load_config
            from backend.adb_manager import adb_manager
            from backend.tv_manager import tv_manager
            config = load_config()

            # Connect TV (fixed home IP, port 5555)
            tv_ip = config.get("tv_ip", "")
            if tv_ip:
                logger.info(f"Auto-connecting to TV at {tv_ip}...")
                result = adb_manager.connect(tv_ip)
                logger.info(f"TV auto-connect: {result.get('message', '')}")

            # Connect phone — try auto-detection first
            # ADB remembers previously paired devices, so check adb devices list
            devices = adb_manager.list_devices()
            tv_target = f"{tv_ip}:5555" if tv_ip else ""
            phone_found = False
            for dev in devices:
                if dev["status"] == "device" and dev["id"] != tv_target:
                    logger.info(f"Phone auto-detected: {dev['id']}")
                    phone_found = True
                    break

            if not phone_found:
                # Fallback to saved phone IP
                phone_ip = config.get("phone_ip", "")
                if phone_ip:
                    logger.info(f"Auto-connecting to phone at {phone_ip}...")
                    result = adb_manager.connect(phone_ip)
                    logger.info(f"Phone auto-connect: {result.get('message', '')}")
        except Exception as e:
            logger.error(f"Auto-connect error: {e}")

    auto_connect_thread = threading.Thread(target=auto_connect_devices, daemon=True)
    auto_connect_thread.start()

    # Start crash recovery monitor
    print("Starting crash recovery monitor...")
    setup_crash_recovery()

    # ─── Global Hotkey (Win+J / Ctrl+Shift+J to summon/hide JASVA) ───
    def register_global_hotkey():
        """Register global hotkeys (Win+J and Ctrl+Shift+J) to toggle JASVA from anywhere."""
        try:
            import ctypes
            from ctypes import wintypes

            MOD_ALT = 0x0001
            MOD_CONTROL = 0x0002
            MOD_SHIFT = 0x0004
            MOD_WIN = 0x0008
            VK_J = 0x4A

            HOTKEY_ID_WIN_J = 1
            HOTKEY_ID_CTRL_SHIFT_J = 2

            user32 = ctypes.windll.user32
            reg_win_j = user32.RegisterHotKey(None, HOTKEY_ID_WIN_J, MOD_WIN, VK_J)
            reg_ctrl_shift_j = user32.RegisterHotKey(None, HOTKEY_ID_CTRL_SHIFT_J, MOD_CONTROL | MOD_SHIFT, VK_J)

            if reg_win_j:
                logger.info("Global hotkey Win+J registered.")
            if reg_ctrl_shift_j:
                logger.info("Global hotkey Ctrl+Shift+J registered.")
            if not reg_win_j and not reg_ctrl_shift_j:
                logger.warning("Global hotkey registration failed (keys may be bound by another app).")
                return

            msg = wintypes.MSG()
            while not should_exit_app:
                # Blocking message queue read
                if user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
                    if msg.message == 0x0312:  # WM_HOTKEY
                        api.toggle_visibility()
            # Cleanup
            if reg_win_j:
                user32.UnregisterHotKey(None, HOTKEY_ID_WIN_J)
            if reg_ctrl_shift_j:
                user32.UnregisterHotKey(None, HOTKEY_ID_CTRL_SHIFT_J)
        except Exception as e:
            logger.error(f"Global hotkey error: {e}")

    hotkey_thread = threading.Thread(target=register_global_hotkey, daemon=True)
    hotkey_thread.start()

    # Start heartbeat update timer
    def heartbeat_updater():
        while not should_exit_app:
            update_heartbeat()
            time.sleep(15)  # Update heartbeat every 15 seconds
    
    heartbeat_thread = threading.Thread(target=heartbeat_updater, daemon=True)
    heartbeat_thread.start()

    # ─── Live Windows Media Monitor Daemon ───
    try:
        from backend.music_monitor import music_monitor
        music_monitor.start()
    except Exception as e:
        print(f"Failed to start music_monitor: {e}")

    # ─── Live Hot Reload Watcher (Auto-updates UI on asset changes) ───
    def run_hot_reload():
        file_mtimes = {}
        def get_files():
            files = []
            for root, _, filenames in os.walk(FRONTEND_DIR):
                for f in filenames:
                    if f.endswith(('.html', '.js', '.css')):
                        files.append(os.path.join(root, f))
            return files
            
        try:
            for f in get_files():
                file_mtimes[f] = os.path.getmtime(f)
        except Exception:
            pass
            
        while not should_exit_app:
            time.sleep(1.0)
            try:
                current_files = get_files()
                changed = False
                for f in current_files:
                    mtime = os.path.getmtime(f)
                    if f not in file_mtimes or mtime > file_mtimes[f]:
                        file_mtimes[f] = mtime
                        changed = True
                if changed:
                    logger.info("Hot reload: Frontend file change detected. Reloading webview...")
                    for win in api._windows.values():
                        try:
                            win.evaluate_js("window.location.reload();")
                        except Exception:
                            pass
            except Exception:
                pass
                
    hot_reload_thread = threading.Thread(target=run_hot_reload, daemon=True)
    hot_reload_thread.start()

    print("Starting JASVA unified interface...")
    webview.start(debug=False, http_server=True, icon=icon_path)


if __name__ == "__main__":
    main()
