import subprocess
import os
import re
import shutil
import threading
from backend.sys_utils import logger, CREATE_NO_WINDOW

class _PersistentAdbShell:
    """One long-lived `adb shell` process for near-instant repeated commands."""

    def __init__(self, adb_path, target):
        self.adb_path = adb_path
        self.target = target
        self.proc = None
        self._ready = False

    def start(self, timeout=3.0):
        """Spawn the shell and handshake; returns True when ready."""
        try:
            self.proc = subprocess.Popen(
                [self.adb_path, "-s", self.target, "shell"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, creationflags=CREATE_NO_WINDOW, bufsize=1
            )
        except Exception:
            return False
        ready_evt = threading.Event()

        def _reader():
            try:
                for line in self.proc.stdout:
                    if line.strip() == "JASVA_READY":
                        ready_evt.set()
            except Exception:
                pass

        threading.Thread(target=_reader, daemon=True).start()
        try:
            self.proc.stdin.write("echo JASVA_READY\n")
            self.proc.stdin.flush()
        except Exception:
            return False
        self._ready = ready_evt.wait(timeout)
        return self._ready

    def write(self, command):
        """Fire-and-forget shell command."""
        if not self._ready or not self.proc or self.proc.poll() is not None:
            raise RuntimeError("shell not ready")
        self.proc.stdin.write(command + "\n")
        self.proc.stdin.flush()

    def is_alive(self):
        return self._ready and self.proc is not None and self.proc.poll() is None

    def close(self):
        try:
            if self.proc:
                self.proc.terminate()
        except Exception:
            pass
        self._ready = False


class ADBManager:
    """Manages Android Debug Bridge (ADB) commands for wireless phone and TV control."""
    
    def __init__(self):
        self.adb_path = self._find_adb()
        self.connected_devices = {}  # IP -> Device Name / Info
        logger.info(f"ADB Manager initialized. Path: {self.adb_path}")

    def _find_adb(self):
        """Locates the ADB executable in system PATH or custom location."""
        # 1. Check system PATH
        adb_in_path = shutil.which("adb")
        if adb_in_path:
            return adb_in_path
            
        # 2. Check common Windows paths
        common_paths = [
            os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"),
            r"C:\platform-tools\adb.exe",
            r"C:\adb\adb.exe"
        ]
        for path in common_paths:
            if os.path.exists(path):
                return path
                
        # Return default string, hoping it is in PATH
        return "adb"

    def is_available(self):
        """Check if ADB command works."""
        try:
            res = subprocess.run([self.adb_path, "version"], capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
            return res.returncode == 0
        except Exception:
            return False

    def run_cmd(self, args):
        """Run an ADB command and return stdout/stderr."""
        if not self.is_available():
            return {"status": "error", "message": "ADB is not installed or not in PATH."}
        try:
            full_args = [self.adb_path] + args
            res = subprocess.run(full_args, capture_output=True, text=True, timeout=8, creationflags=CREATE_NO_WINDOW)
            return {
                "status": "success" if res.returncode == 0 else "error",
                "stdout": res.stdout.strip(),
                "stderr": res.stderr.strip(),
                "code": res.returncode
            }
        except subprocess.TimeoutExpired:
            return {"status": "error", "message": "ADB command timed out"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def list_devices(self):
        """List currently connected adb devices."""
        res = self.run_cmd(["devices"])
        if res["status"] == "error":
            return []
        
        devices = []
        lines = res["stdout"].splitlines()
        for line in lines[1:]: # Skip 'List of devices attached'
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 2:
                devices.append({
                    "id": parts[0],
                    "status": parts[1]
                })
        return devices

    def connect(self, ip_port):
        """Connect to wireless ADB device (e.g. '192.168.1.100:5555')."""
        if ":" not in ip_port:
            ip_port = f"{ip_port}:5555"
        res = self.run_cmd(["connect", ip_port])
        if res["status"] == "success" and "connected to" in res["stdout"].lower():
            # Query device model
            model_res = self.run_cmd(["-s", ip_port, "shell", "getprop", "ro.product.model"])
            model = model_res.get("stdout", "Unknown Device").strip()
            self.connected_devices[ip_port] = model
            return {"status": "success", "message": f"Connected to {model} ({ip_port})"}
        return {"status": "error", "message": res.get("stdout") or res.get("stderr") or "Connection failed"}

    def disconnect(self, ip_port):
        """Disconnect wireless ADB device."""
        res = self.run_cmd(["disconnect", ip_port])
        if ip_port in self.connected_devices:
            del self.connected_devices[ip_port]
        return res

    def pair(self, ip_port, pairing_code):
        """Pair with wireless ADB device (new Android wireless debugging flow)."""
        # Run adb pair
        res = self.run_cmd(["pair", ip_port, pairing_code])
        return res

    def send_key(self, ip_port, keycode):
        """Send keyevent command."""
        return self.run_cmd(["-s", ip_port, "shell", "input", "keyevent", str(keycode)])

    def send_key_fast(self, ip_port, keycode):
        """Fast keyevent wrapper."""
        return self.send_key(ip_port, keycode)

    def send_tap(self, ip_port, x, y):
        """Send tap command."""
        return self.run_cmd(["-s", ip_port, "shell", "input", "tap", str(x), str(y)])

    def send_swipe(self, ip_port, x1, y1, x2, y2, duration=300):
        """Send swipe command."""
        return self.run_cmd(["-s", ip_port, "shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration)])

    def send_text(self, ip_port, text):
        """Send text input (escaped for shell)."""
        # Replace space with %s or escape spaces/chars
        escaped = re.sub(r'([&|<>#*?()$])', r'\\\1', text)
        # Note: Android adb shell input text supports spaces but we can escape them or use %s for spaces
        # Better: use double quotes and escape quotes
        escaped = escaped.replace('"', '\\"').replace(' ', '%s')
        return self.run_cmd(["-s", ip_port, "shell", "input", "text", escaped])

    def send_text_fast(self, ip_port, text):
        """Fast text input wrapper."""
        return self.send_text(ip_port, text)

    def launch_app(self, ip_port, package_name):
        """Launch application by package name using monkey tool or am start."""
        # Using monkey is the easiest package-based launcher
        return self.run_cmd(["-s", ip_port, "shell", "monkey", "-p", package_name, "-c", "android.intent.category.LAUNCHER", "1"])

    def shell(self, ip_port, command):
        """Run an arbitrary adb shell command."""
        return self.run_cmd(["-s", ip_port, "shell", command])

    def get_screen_size(self, ip_port):
        """Return (width, height) of the device screen, or None."""
        res = self.run_cmd(["-s", ip_port, "shell", "wm", "size"])
        m = re.search(r"(\d+)x(\d+)", res.get("stdout", ""))
        if m:
            return int(m.group(1)), int(m.group(2))
        return None

    def screenshot(self, ip_port, output_path):
        """Capture a PNG screenshot of the device screen and save it to output_path."""
        try:
            full_args = [self.adb_path, "-s", ip_port, "exec-out", "screencap", "-p"]
            res = subprocess.run(full_args, capture_output=True, timeout=15, creationflags=CREATE_NO_WINDOW)
            if res.returncode == 0 and res.stdout:
                with open(output_path, "wb") as f:
                    f.write(res.stdout)
                return {"status": "success", "path": output_path}
            err = res.stderr.decode(errors="ignore").strip() or "Screencap failed"
            return {"status": "error", "message": err}
        except subprocess.TimeoutExpired:
            return {"status": "error", "message": "Screencap timed out"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def play_media_uri(self, ip_port, uri):
        """Send intent to play URI (e.g. youtube video or netflix link)."""
        return self.run_cmd(["-s", ip_port, "shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", uri])

    def force_stop_app(self, ip_port, package_name):
        """Force stop package."""
        return self.run_cmd(["-s", ip_port, "shell", "am", "force-stop", package_name])

    # ─── Persistent adb shell (near-instant repeated commands) ───

    @staticmethod
    def _normalize_target(ip_port):
        """Append :5555 only for plain IPv4 addresses; serials pass through."""
        if ":" in ip_port:
            return ip_port
        if re.match(r"^\d+\.\d+\.\d+\.\d+$", ip_port):
            return f"{ip_port}:5555"
        return ip_port

    def _get_or_create_shell(self, target):
        """Return a live persistent `adb shell` for target, spawning it if needed."""
        with self._shell_lock:
            shell = self._shells.get(target)
            if shell is None:
                shell = _PersistentAdbShell(self.adb_path, target)
                if not shell.start(timeout=3.0):
                    return None
                self._shells[target] = shell
            elif not shell.is_alive():
                shell.close()
                shell = _PersistentAdbShell(self.adb_path, target)
                if not shell.start(timeout=3.0):
                    return None
                self._shells[target] = shell
            return shell

    def prewarm_shell(self, ip_port):
        """Spawn (in the caller's thread) a persistent shell for a target."""
        try:
            self._get_or_create_shell(self._normalize_target(ip_port))
        except Exception:
            pass

    def send_tap_fast(self, ip_port, x, y):
        """Send a tap through the persistent shell - instant without subprocess overhead."""
        target = self._normalize_target(ip_port)
        shell = self._get_or_create_shell(target)
        if shell is None:
            return self.send_tap(ip_port, x, y)
        try:
            shell.write(f"input tap {x} {y}")
            return {"status": "success"}
        except Exception as e:
            shell.close()
            with self._shell_lock:
                self._shells.pop(target, None)
            return self.send_tap(ip_port, x, y)

    def send_swipe_fast(self, ip_port, x1, y1, x2, y2, duration=300):
        """Send a swipe/drag through the persistent shell - instant without subprocess overhead."""
        target = self._normalize_target(ip_port)
        shell = self._get_or_create_shell(target)
        if shell is None:
            return self.send_swipe(ip_port, x1, y1, x2, y2, duration)
        try:
            shell.write(f"input swipe {x1} {y1} {x2} {y2} {duration}")
            return {"status": "success"}
        except Exception as e:
            shell.close()
            with self._shell_lock:
                self._shells.pop(target, None)
            return self.send_swipe(ip_port, x1, y1, x2, y2, duration)

    def send_text_fast(self, ip_port, text):
        """Send text through the persistent shell - instant without subprocess overhead."""
        target = self._normalize_target(ip_port)
        shell = self._get_or_create_shell(target)
        if shell is None:
            return self.send_text(ip_port, text)
        try:
            escaped = re.sub(r'([&|<>#*?()$])', r'\\\1', text).replace('"', '\\"').replace(' ', '%s')
            shell.write(f"input text {escaped}")
            return {"status": "success"}
        except Exception as e:
            shell.close()
            with self._shell_lock:
                self._shells.pop(target, None)
            return self.send_text(ip_port, text)

    def set_auto_rotate(self, ip_port, enable=False):
        """Enable or disable device auto-rotate (0 = locked portrait/current, 1 = auto-rotate)."""
        val = "1" if enable else "0"
        return self.run_cmd(["-s", ip_port, "shell", "settings", "put", "system", "accelerometer_rotation", val])

    def get_auto_rotate(self, ip_port):
        """Get device auto-rotate setting (0 or 1)."""
        res = self.run_cmd(["-s", ip_port, "shell", "settings", "get", "system", "accelerometer_rotation"])
        if res.get("status") == "success":
            val = res.get("output", "").strip()
            return {"status": "success", "auto_rotate": val == "1"}
        return res

# Global instance
adb_manager = ADBManager()
# Persistent shell cache (needs the instance's adb path, so init after instance)
adb_manager._shells = {}
adb_manager._shell_lock = threading.Lock()

