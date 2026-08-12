import os
import urllib.parse
from backend.sys_utils import load_config, save_config, logger
from backend.adb_manager import adb_manager

# Mapping of common buttons to Android TV keycodes
KEY_MAP = {
    "power": 26,
    "up": 19,
    "down": 20,
    "left": 21,
    "right": 22,
    "select": 23,
    "enter": 23,
    "back": 4,
    "home": 3,
    "volume_up": 24,
    "volume_down": 25,
    "mute": 164,
    "play": 85,
    "pause": 85,
    "play_pause": 85,
    "menu": 82,
    "fast_forward": 90,
    "rewind": 89
}

# Mapping of friendly names to package IDs on Android TV/Fire TV
APP_MAP = {
    "youtube": "com.google.android.youtube.tv",
    "netflix": "com.netflix.ninja",
    "prime": "com.amazon.amazonvideo.livingroom",
    "prime video": "com.amazon.amazonvideo.livingroom",
    "spotify": "com.spotify.tv.android",
    "disney": "com.disney.disneyplus",
    "kodi": "org.xbmc.kodi"
}

class TVManager:
    """Orchestrates controls for smart TV devices, fallback to ADB command relay."""
    
    def __init__(self):
        self.tv_ip = self.get_tv_ip()
        logger.info(f"TV Manager initialized. Configured TV IP: {self.tv_ip}")

    def get_tv_ip(self):
        """Load configured TV IP address from config.json."""
        config = load_config()
        return config.get("tv_ip", "")

    def set_tv_ip(self, ip):
        """Save TV IP address to config.json and update active IP."""
        self.tv_ip = ip
        config = load_config()
        config["tv_ip"] = ip
        save_config(config)
        logger.info(f"TV IP updated to: {ip}")
        # Try to connect asynchronously
        self.connect()
        return {"status": "success", "message": f"TV IP set to {ip}"}

    def connect(self):
        """Attempt connection to TV."""
        if not self.tv_ip:
            return {"status": "error", "message": "No TV IP configured."}
        return adb_manager.connect(self.tv_ip)

    def is_connected(self):
        """Checks if the configured TV is in the active ADB devices list."""
        if not self.tv_ip:
            return False
        devices = adb_manager.list_devices()
        target = self.tv_ip if ":" in self.tv_ip else f"{self.tv_ip}:5555"
        for dev in devices:
            if dev["id"] == target and dev["status"] == "device":
                return True
        return False

    def send_button(self, button_name):
        """Send virtual remote control keypress to TV."""
        if not self.tv_ip:
            return {"status": "error", "message": "TV IP not set."}

        btn = button_name.lower().strip()
        if btn not in KEY_MAP:
            return {"status": "error", "message": f"Unknown remote button: '{button_name}'"}

        if btn == "power":
            # Fire TV ignores KEYCODE_POWER (26); use SLEEP(223)/WAKEUP(224)
            # based on the device's current wakefulness.
            keycode = 223 if self._is_tv_awake() else 224
        else:
            keycode = KEY_MAP[btn]

        # Single adb call per press for instant response (persistent shell).
        # Only if the TV is not reachable, reconnect and retry once.
        res = adb_manager.send_key_fast(self.tv_ip, keycode)
        if res["status"] == "error":
            self.connect()
            res = adb_manager.send_key_fast(self.tv_ip, keycode)
        return res

    def _is_tv_awake(self):
        """True when the TV's display is awake (dumpsys power query)."""
        try:
            target = self.tv_ip if ":" in self.tv_ip else f"{self.tv_ip}:5555"
            res = adb_manager.run_cmd(["-s", target, "shell", "dumpsys", "power"])
            return "mWakefulness=Awake" in res.get("stdout", "")
        except Exception:
            return True

    def launch_app(self, app_name):
        """Launch specified app on TV."""
        if not self.tv_ip:
            return {"status": "error", "message": "TV IP not set."}
        if not self.is_connected():
            self.connect()
            
        name = app_name.lower().strip()
        package = APP_MAP.get(name, name)
        logger.info(f"Launching app '{name}' (package: {package}) on TV...")
        return adb_manager.launch_app(self.tv_ip, package)

    def play_on_youtube(self, query):
        """Search and play a video directly on YouTube TV."""
        if not self.tv_ip:
            return {"status": "error", "message": "TV IP not set."}
        if not self.is_connected():
            self.connect()
            
        logger.info(f"Searching YouTube on TV for '{query}'...")
        # Android TV search intent format:
        # am start -n com.google.android.youtube.tv/com.google.android.youtube.tv.activity.ShellActivity -a android.intent.action.SEARCH --es query "query"
        args = [
            "-s", self.tv_ip, "shell", "am", "start", 
            "-n", "com.google.android.youtube.tv/com.google.android.youtube.tv.activity.ShellActivity",
            "-a", "android.intent.action.SEARCH",
            "--es", "query", query
        ]
        return adb_manager.run_cmd(args)

    def play_media_link(self, link):
        """Open web URL or direct stream link on TV."""
        if not self.tv_ip:
            return {"status": "error", "message": "TV IP not set."}
        if not self.is_connected():
            self.connect()
            
        return adb_manager.play_media_uri(self.tv_ip, link)

    def mirror(self):
        """Launch scrcpy to mirror and control TV screen."""
        if not self.tv_ip:
            return {"status": "error", "message": "TV IP not set."}
        # launch_phone_mirror handles the adb connect itself (connects if needed,
        # reuses the existing connection otherwise), so no pre-checks here.
        from backend.sys_utils import launch_phone_mirror
        return launch_phone_mirror(f"{self.tv_ip}:5555")

# Global instance
tv_manager = TVManager()
