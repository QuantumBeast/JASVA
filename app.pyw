import webview
import os
import sys
import json
import threading
import time
import pystray
from PIL import Image
import socket

# Import from sys_utils
from backend.sys_utils import (
    logger, setup_crash_recovery, update_heartbeat,
    ROOT_DIR, DB_DIR
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
            except Exception:
                pass

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
                except Exception:
                    pass
        self.broadcast_js("if (window.syncWindowVisibilityState) { "
                         "window.syncWindowVisibilityState('chat', true); "
                         "window.syncWindowVisibilityState('top', true); "
                         "window.syncWindowVisibilityState('sphere', true); "
                         "window.syncWindowVisibilityState('bottom', true); "
                         "window.syncWindowVisibilityState('dashboard', true); "
                         "}")
        return json.dumps({"status": "success"})

    def is_autostart_boot(self):
        """Check if the app was launched with the autostart flag."""
        return "--autostart" in sys.argv

    def execute_command(self, text, quiet=False, image_base64=None, image_mime=None):
        from backend.command_router import execute_command
        result = execute_command(text, quiet=quiet, image_base64=image_base64, image_mime=image_mime, window=self._window)
        return json.dumps(result)

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

    # ─── Create the separate floating windows ───
    chat_window = webview.create_window(
        title="JASVA Chat Core",
        url=os.path.join(FRONTEND_DIR, "index.html?panel=chat"),
        width=580,
        height=980,
        x=20,
        y=50,
        frameless=True,
        easy_drag=False,
        hidden=is_autostart,
        background_color="#030508",
        text_select=True,
        js_api=api
    )
    
    top_window = webview.create_window(
        title="JASVA Portal Greeting",
        url=os.path.join(FRONTEND_DIR, "index.html?panel=top"),
        width=680,
        height=230,
        x=610,
        y=50,
        frameless=True,
        easy_drag=False,
        hidden=is_autostart,
        background_color="#030508",
        text_select=True,
        js_api=api
    )
    
    sphere_window = webview.create_window(
        title="JASVA Active Sphere",
        url=os.path.join(FRONTEND_DIR, "index.html?panel=sphere"),
        width=520,
        height=543,
        x=650,
        y=280,
        frameless=True,
        easy_drag=False,
        hidden=is_autostart,
        background_color="#030508",
        text_select=True,
        js_api=api
    )
    
    bottom_window = webview.create_window(
        title="JASVA Cognition Log",
        url=os.path.join(FRONTEND_DIR, "index.html?panel=bottom"),
        width=680,
        height=200,
        x=610,
        y=840,
        frameless=True,
        easy_drag=False,
        hidden=is_autostart,
        background_color="#030508",
        text_select=True,
        js_api=api
    )
    
    system_window = webview.create_window(
        title="JASVA Resource Monitor",
        url=os.path.join(FRONTEND_DIR, "index.html?panel=monitor"),
        width=630,
        height=480,
        x=1290,
        y=50,
        frameless=True,
        easy_drag=False,
        hidden=is_autostart,
        background_color="#030508",
        text_select=True,
        js_api=api
    )
    
    control_window = webview.create_window(
        title="JASVA Device Control",
        url=os.path.join(FRONTEND_DIR, "index.html?panel=control"),
        width=630,
        height=490,
        x=1290,
        y=550,
        frameless=True,
        easy_drag=False,
        hidden=is_autostart,
        background_color="#030508",
        text_select=True,
        js_api=api
    )
    
    settings_window = webview.create_window(
        title="JASVA Settings",
        url=os.path.join(FRONTEND_DIR, "index.html?panel=settings"),
        width=480,
        height=700,
        x=720,
        y=280,
        frameless=True,
        easy_drag=False,
        hidden=True,
        background_color="#030508",
        text_select=True,
        js_api=api
    )
    
    phone_ctrl_window = webview.create_window(
        title="JASVA Phone Controls",
        url=os.path.join(FRONTEND_DIR, "controls.html?device=phone&t=5"),
        width=190,
        height=450,
        x=1500,
        y=400,
        frameless=True,
        easy_drag=False,
        hidden=True,
        background_color="#060c18",
        text_select=False,
        js_api=api
    )
    
    tv_ctrl_window = webview.create_window(
        title="JASVA TV Controls",
        url=os.path.join(FRONTEND_DIR, "controls.html?device=tv&t=4"),
        width=190,
        height=510,
        x=1500,
        y=400,
        frameless=True,
        easy_drag=False,
        hidden=True,
        background_color="#060c18",
        text_select=False,
        js_api=api
    )
    
    api.register_window("chat", chat_window)
    api.register_window("top", top_window)
    api.register_window("sphere", sphere_window)
    api.register_window("bottom", bottom_window)
    api.register_window("monitor", system_window)
    api.register_window("control", control_window)
    api.register_window("dashboard", system_window)
    api.register_window("settings", settings_window)
    api.register_window("phone_ctrl", phone_ctrl_window)
    api.register_window("tv_ctrl", tv_ctrl_window)
    api.set_window(chat_window)
    main_window = chat_window

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
                # Decouple the GUI interaction to a separate thread to prevent deadlocking the pystray message loop
                def run_show():
                    for name in ["chat", "top", "sphere", "bottom", "dashboard"]:
                        win = api._windows.get(name)
                        if win:
                            try:
                                win.show()
                                win.restore()
                                api._window_visibility[name] = True
                            except Exception:
                                pass
                    api.broadcast_js("if (window.syncWindowVisibilityState) { "
                                     "window.syncWindowVisibilityState('chat', true); "
                                     "window.syncWindowVisibilityState('top', true); "
                                     "window.syncWindowVisibilityState('sphere', true); "
                                     "window.syncWindowVisibilityState('bottom', true); "
                                     "window.syncWindowVisibilityState('dashboard', true); "
                                     "}")
                threading.Thread(target=run_show, daemon=True).start()

            def on_exit(icon, item):
                global should_exit_app
                should_exit_app = True
                # Decouple cleanup to a separate thread to guarantee pystray returns immediately and clears cleanly
                def run_exit():
                    try:
                        icon.stop()
                    except Exception:
                        pass
                    os._exit(0)
                threading.Thread(target=run_exit, daemon=True).start()

            menu = pystray.Menu(
                pystray.MenuItem('open JASVA', on_show_window, default=True),
                pystray.MenuItem('exit', on_exit)
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

    def on_shown():
        configure_webview_permissions(chat_window)
        configure_webview_permissions(top_window)
        configure_webview_permissions(sphere_window)
        configure_webview_permissions(bottom_window)
        configure_webview_permissions(system_window)
        configure_webview_permissions(settings_window)
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
    main_window.events.loaded += on_shown
    main_window.events.shown += on_shown
    main_window.events.closing += on_closing
    main_window.events.closed += on_closed

    # Start the background scheduler
    print("Starting background scheduler...")
    from backend.memory_scheduler import start_scheduler
    start_scheduler()

    # Start the multi-device integration server
    print("Starting multi-device integration server...")
    try:
        from backend.multi_device_server import device_server
        device_server.start()
    except Exception as e:
        print(f"Error starting multi-device server: {e}")

    # Auto-connect to saved TV and phone IPs on startup
    def auto_connect_devices():
        try:
            from backend.sys_utils import load_config
            from backend.adb_manager import adb_manager
            from backend.tv_manager import tv_manager
            config = load_config()

            # Connect TV (fixed port 5555)
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

    # Start heartbeat update timer
    def heartbeat_updater():
        while not should_exit_app:
            update_heartbeat()
            time.sleep(15)  # Update heartbeat every 15 seconds
    
    heartbeat_thread = threading.Thread(target=heartbeat_updater, daemon=True)
    heartbeat_thread.start()

    # Dev-only hot reload watcher (walks FRONTEND_DIR checking mtimes).
    # Disabled by default to save CPU/memory in normal use; enable with --dev.
    if "--dev" in sys.argv or os.environ.get("JASVA_DEV", "") == "1":
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
                time.sleep(2.0)
                try:
                    current_files = get_files()
                    changed = False
                    for f in current_files:
                        mtime = os.path.getmtime(f)
                        if f not in file_mtimes or mtime > file_mtimes[f]:
                            file_mtimes[f] = mtime
                            changed = True
                    if changed:
                        print("Hot reload: Frontend file change detected. Reloading webview...")
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
    webview.start(debug=False, icon=icon_path)


if __name__ == "__main__":
    main()
