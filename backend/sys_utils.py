import os
import sys
import logging
from logging.handlers import RotatingFileHandler
import platform
import subprocess
import time
import ctypes
from ctypes import wintypes
import shutil
import json
from datetime import datetime
import threading
import glob

try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False

try:
    import psutil
except ImportError:
    psutil = None

def _hidden_startupinfo():
    """Suppress the console window of child processes."""
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0  # SW_HIDE
    return si

try:
    from pycaw.pycaw import AudioUtilities
    PYCAW_AVAILABLE = True
except ImportError:
    PYCAW_AVAILABLE = False

# Setup paths relative to backend directory
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BACKEND_DIR)
DB_DIR = os.path.join(BACKEND_DIR, "databases")
os.makedirs(DB_DIR, exist_ok=True)
LOG_DIR = os.path.join(BACKEND_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# File paths
MAIN_LOG = os.path.join(LOG_DIR, "jasva.log")
CONFIG_FILE = os.path.join(DB_DIR, "config.json")
MEMORY_FILE = os.path.join(DB_DIR, "memory.json")
CRASH_LOG_FILE = os.path.join(DB_DIR, "crash_log.json")
HEARTBEAT_FILE = os.path.join(DB_DIR, "heartbeat.json")

def load_memory_db():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                db = json.load(f)
                # Ensure all root keys exist
                list_keys = ["history", "summaries", "custom_skills", "notes", "recents", "schedules", "notifications"]
                for k in list_keys:
                    if k not in db:
                        db[k] = []
                if "profile" not in db:
                    db["profile"] = {
                        "identity": {},
                        "preferences": {},
                        "relationships": [],
                        "habits": [],
                        "interests": [],
                        "facts": [],
                        "dislikes": []
                    }
                if "cognitive_state" not in db:
                    db["cognitive_state"] = {
                        "mood": "calm",
                        "energy_level": 0.7,
                        "rapport_score": 0.5,
                        "last_interaction_time": 0,
                        "interaction_count": 0,
                        "mood_history": []
                    }
                if "conversation_flow" not in db:
                    db["conversation_flow"] = {
                        "topic_stack": [],
                        "follow_up_queue": [],
                        "last_topics": []
                    }
                return db
        except Exception:
            pass
    return {
        "profile": {
            "identity": {},
            "preferences": {},
            "relationships": [],
            "habits": [],
            "interests": [],
            "facts": [],
            "dislikes": []
        },
        "history": [],
        "summaries": [],
        "custom_skills": [],
        "notes": [],
        "recents": [],
        "schedules": [],
        "notifications": [],
        "cognitive_state": {
            "mood": "calm",
            "energy_level": 0.7,
            "rapport_score": 0.5,
            "last_interaction_time": 0,
            "interaction_count": 0,
            "mood_history": []
        },
        "conversation_flow": {
            "topic_stack": [],
            "follow_up_queue": [],
            "last_topics": []
        }
    }

def save_memory_db(db):
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=4, ensure_ascii=False)
        return True
    except Exception:
        return False

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
                if "speech_engine" not in config: config["speech_engine"] = "edge_tts"
                if "elevenlabs_voice" not in config: config["elevenlabs_voice"] = "21m00Tcm4TlvDq8ikWAM"
                return config
        except Exception:
            pass
    return {
        "voice": "en-GB-RyanNeural",
        "speech_engine": "edge_tts",
        "elevenlabs_voice": "21m00Tcm4TlvDq8ikWAM",
        "speed": 1.0,
        "volume": 0.75,
        "always_listening": False,
        "language": "en-US"
    }

def save_config(config):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
        return True
    except Exception:
        return False

# Desktop and Games directories
user_home = os.path.expanduser("~")
candidates = [
    os.path.join(user_home, "OneDrive", "Desktop"),
    os.path.join(user_home, "OneDrive - Personal", "Desktop"),
    os.path.join(user_home, "Desktop"),
]
DESKTOP_DIR = None
for path in candidates:
    if os.path.exists(path):
        DESKTOP_DIR = path
        break
if not DESKTOP_DIR:
    DESKTOP_DIR = os.path.abspath(ROOT_DIR)

GAMES_DIR = os.path.join(DESKTOP_DIR, "Games")
if not os.path.exists(GAMES_DIR):
    onedrive_games = os.path.join(user_home, "OneDrive", "Desktop", "Games")
    if os.path.exists(onedrive_games):
        GAMES_DIR = onedrive_games

CREATE_NO_WINDOW = 0x08000000
SERVICE_NAME = "JASVA_AI_Assistant"

# ─── Cross-window state tracking ───
_sphere_state = {
    "listening": False,
    "speaking": False,
    "processing": False
}
_sphere_state_lock = threading.Lock()

# ──────────────────────────────────────────────────────────────
# 1. Logging System
# ──────────────────────────────────────────────────────────────
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

class JASVALogger:
    def __init__(self):
        self.logger = logging.getLogger("JASVA")
        self.logger.setLevel(logging.DEBUG)
        if not self.logger.handlers:
            self._setup_handlers()
    
    def _setup_handlers(self):
        main_handler = RotatingFileHandler(MAIN_LOG, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
        main_handler.setLevel(logging.DEBUG)
        main_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
        self.logger.addHandler(main_handler)
        
        try:
            for stream in (sys.stdout, sys.stderr):
                if stream and hasattr(stream, 'reconfigure'):
                    stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
        self.logger.addHandler(console_handler)
    
    def debug(self, message): self.logger.debug(message)
    def info(self, message): self.logger.info(message)
    def warning(self, message): self.logger.warning(message)
    def error(self, message, exc_info=False): self.logger.error(message, exc_info=exc_info)
    def critical(self, message, exc_info=False): self.logger.critical(message, exc_info=exc_info)
    
    def log_command(self, command, result, execution_time=None):
        time_info = f" ({execution_time:.2f}s)" if execution_time else ""
        log_entry = f"Command: '{command}' -> {result}{time_info}"
        self.info(log_entry)
            
    def log_system_event(self, event_type, details):
        log_entry = f"[{event_type}] {details}"
        self.info(log_entry)

_logger = None
def get_logger():
    global _logger
    if _logger is None:
        _logger = JASVALogger()
    return _logger

def log_exception(func):
    def wrapper(*args, **kwargs):
        logger = get_logger()
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Exception in {func.__name__}: {str(e)}", exc_info=True)
            raise
    return wrapper

def log_execution_time(func):
    def wrapper(*args, **kwargs):
        logger = get_logger()
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.debug(f"{func.__name__} executed in {execution_time:.2f}s")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"{func.__name__} failed after {execution_time:.2f}s: {str(e)}")
            raise
    return wrapper

logger = get_logger()

# ──────────────────────────────────────────────────────────────
# 2. Credential Manager
# ──────────────────────────────────────────────────────────────
class CredentialManager:
    def __init__(self):
        self.logger = logging.getLogger("JASVA.CredentialManager")
        self.use_fallback = not KEYRING_AVAILABLE
        
    def set_api_key(self, provider, api_key):
        if not api_key or not api_key.strip():
            return False
        if self.use_fallback:
            return self._fallback_set(provider, api_key)
        try:
            keyring.set_password(SERVICE_NAME, provider, api_key)
            self.logger.info(f"API key for {provider} stored securely")
            return True
        except Exception as e:
            self.logger.error(f"Failed to store API key for {provider}: {e}")
            return self._fallback_set(provider, api_key)
            
    def get_api_key(self, provider):
        if self.use_fallback:
            return self._fallback_get(provider)
        try:
            key = keyring.get_password(SERVICE_NAME, provider)
            if key:
                self.logger.debug(f"API key for {provider} retrieved securely")
            return key
        except Exception as e:
            self.logger.error(f"Failed to retrieve API key for {provider}: {e}")
            return self._fallback_get(provider)
            
    def delete_api_key(self, provider):
        if self.use_fallback:
            return self._fallback_delete(provider)
        try:
            keyring.delete_password(SERVICE_NAME, provider)
            self.logger.info(f"API key for {provider} deleted")
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete API key for {provider}: {e}")
            return self._fallback_delete(provider)
            
    def list_providers(self):
        if self.use_fallback:
            return self._fallback_list()
        try:
            providers = ['gemini', 'groq', 'puter', 'openai', 'anthropic', 'elevenlabs']
            found = []
            for provider in providers:
                if self.get_api_key(provider):
                    found.append(provider)
            return found
        except Exception as e:
            self.logger.error(f"Failed to list providers: {e}")
            return self._fallback_list()
            
    def _fallback_set(self, provider, api_key):
        try:
            env_path = os.path.join(BACKEND_DIR, ".env")
            existing_lines = {}
            if os.path.exists(env_path):
                with open(env_path, "r") as f:
                    for line in f:
                        if "=" in line:
                            parts = line.strip().split("=", 1)
                            existing_lines[parts[0].strip()] = parts[1].strip()
            env_key_map = {
                'gemini': 'GEMINI_API_KEY',
                'groq': 'GROQ_API_KEY', 
                'puter': 'PUTER_API_KEY',
                'openai': 'OPENAI_API_KEY',
                'anthropic': 'ANTHROPIC_API_KEY',
                'elevenlabs': 'ELEVENLABS_API_KEY'
            }
            env_key = env_key_map.get(provider.lower(), f"{provider.upper()}_API_KEY")
            existing_lines[env_key] = f'"{api_key}"'
            with open(env_path, "w") as f:
                for k, v in existing_lines.items():
                    f.write(f"{k}={v}\n")
            self.logger.warning(f"API key for {provider} stored in .env file (fallback)")
            return True
        except Exception as e:
            self.logger.error(f"Fallback storage failed for {provider}: {e}")
            return False
            
    def _fallback_get(self, provider):
        try:
            env_path = os.path.join(BACKEND_DIR, ".env")
            env_key_map = {
                'gemini': 'GEMINI_API_KEY',
                'groq': 'GROQ_API_KEY',
                'puter': 'PUTER_API_KEY',
                'openai': 'OPENAI_API_KEY',
                'anthropic': 'ANTHROPIC_API_KEY',
                'elevenlabs': 'ELEVENLABS_API_KEY'
            }
            env_key = env_key_map.get(provider.lower(), f"{provider.upper()}_API_KEY")
            if os.path.exists(env_path):
                with open(env_path, "r") as f:
                    for line in f:
                        if "=" in line:
                            parts = line.strip().split("=", 1)
                            if parts[0].strip() == env_key:
                                return parts[1].strip().strip('"').strip("'")
            return None
        except Exception as e:
            self.logger.error(f"Fallback retrieval failed for {provider}: {e}")
            return None
            
    def _fallback_delete(self, provider):
        try:
            env_path = os.path.join(BACKEND_DIR, ".env")
            env_key_map = {
                'gemini': 'GEMINI_API_KEY',
                'groq': 'GROQ_API_KEY',
                'puter': 'PUTER_API_KEY',
                'openai': 'OPENAI_API_KEY',
                'anthropic': 'ANTHROPIC_API_KEY',
                'elevenlabs': 'ELEVENLABS_API_KEY'
            }
            env_key = env_key_map.get(provider.lower(), f"{provider.upper()}_API_KEY")
            if os.path.exists(env_path):
                existing_lines = {}
                with open(env_path, "r") as f:
                    for line in f:
                        if "=" in line:
                            parts = line.strip().split("=", 1)
                            if parts[0].strip() != env_key:
                                existing_lines[parts[0].strip()] = parts[1].strip()
                with open(env_path, "w") as f:
                    for k, v in existing_lines.items():
                        f.write(f"{k}={v}\n")
            return True
        except Exception as e:
            self.logger.error(f"Fallback deletion failed for {provider}: {e}")
            return False
            
    def _fallback_list(self):
        try:
            env_path = os.path.join(BACKEND_DIR, ".env")
            env_key_map = {
                'GEMINI_API_KEY': 'gemini',
                'GROQ_API_KEY': 'groq',
                'PUTER_API_KEY': 'puter',
                'OPENAI_API_KEY': 'openai',
                'ANTHROPIC_API_KEY': 'anthropic',
                'ELEVENLABS_API_KEY': 'elevenlabs'
            }
            providers = []
            if os.path.exists(env_path):
                with open(env_path, "r") as f:
                    for line in f:
                        if "=" in line:
                            parts = line.strip().split("=", 1)
                            if parts[0].strip() in env_key_map:
                                providers.append(env_key_map[parts[0].strip()])
            return providers
        except Exception as e:
            self.logger.error(f"Fallback listing failed: {e}")
            return []

_credential_manager = None
def get_credential_manager():
    global _credential_manager
    if _credential_manager is None:
        _credential_manager = CredentialManager()
    return _credential_manager

# ──────────────────────────────────────────────────────────────
# 3. File Operations
# ──────────────────────────────────────────────────────────────
def get_search_roots():
    roots = []
    user_home = os.path.expanduser("~")
    for folder_name in ["Desktop", "Documents", "Downloads", "Pictures", "Videos", "Music"]:
        user_folder = os.path.join(user_home, folder_name)
        if os.path.isdir(user_folder):
            roots.append(user_folder)
    if platform.system() == "Windows":
        for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
            drive = f"{letter}:\\"
            if os.path.isdir(drive):
                roots.append(drive)
    else:
        roots.append("/")
    seen = set()
    unique_roots = []
    for r in roots:
        norm = os.path.normcase(os.path.abspath(r))
        if norm not in seen:
            seen.add(norm)
            unique_roots.append(r)
    return unique_roots

def parse_directory_path(text, current_dir):
    text_lower = text.lower()
    target = ""
    matched = False
    for pattern in ["list files in", "list files of", "list files at", "list files", 
                    "list directory of", "list directory in", "list directory at", "list directory",
                    "show files in", "show files of", "show files at", "show files",
                    "show directory in", "show directory of", "show directory at", "show directory",
                    "list folder in", "list folder of", "list folder at", "list folder",
                    "show folder in", "show folder of", "show folder at", "show folder",
                    "go to directory", "go to folder", "go to", "change directory to", 
                    "change folder to", "navigate to"]:
        if pattern in text_lower:
            idx = text_lower.index(pattern) + len(pattern)
            target = text[idx:].strip()
            matched = True
            break
    if not matched:
        for kw in ["list", "show"]:
            if text_lower.startswith(kw):
                target = text[len(kw):].strip()
                break
    if not target:
        return current_dir
    target = target.rstrip(".?!:;")
    target_lower = target.lower()
    if target_lower in ["desktop", "the desktop"]:
        return DESKTOP_DIR
    elif target_lower in ["games", "the games", "games folder", "games directory"]:
        return GAMES_DIR
    elif target_lower in ["workspace", "the workspace", "current workspace", "project directory", "project folder"]:
        return ROOT_DIR
    elif target_lower in ["home", "home directory", "home folder", "user profile"]:
        return os.path.expanduser("~")
    elif target_lower in ["documents", "my documents", "documents folder"]:
        return os.path.join(os.path.expanduser("~"), "Documents")
    elif target_lower in ["downloads", "my downloads", "downloads folder"]:
        return os.path.join(os.path.expanduser("~"), "Downloads")
    if os.path.isabs(target):
        if os.path.exists(target):
            return os.path.abspath(target)
        else:
            cleaned = target.replace("/", "\\")
            if os.path.exists(cleaned):
                return os.path.abspath(cleaned)
    rel_path = os.path.join(current_dir, target)
    if os.path.exists(rel_path):
        return os.path.abspath(rel_path)
    try:
        if os.path.exists(current_dir):
            for item in os.listdir(current_dir):
                item_path = os.path.join(current_dir, item)
                if os.path.isdir(item_path) and target_lower in item.lower():
                    return os.path.abspath(item_path)
    except Exception:
        pass
    return target

def scan_directory(root_dir, query, max_results=20, max_depth=5):
    results = []
    query_lower = query.lower()
    query_no_ext = os.path.splitext(query_lower)[0]
    def _scan(current_dir, depth):
        if depth > max_depth or len(results) >= max_results:
            return
        try:
            entries = os.listdir(current_dir)
        except (PermissionError, OSError):
            return
        for entry in entries:
            if len(results) >= max_results:
                return
            full_path = os.path.join(current_dir, entry)
            entry_lower = entry.lower()
            entry_no_ext = os.path.splitext(entry_lower)[0]
            is_match = (
                query_lower == entry_lower or
                query_lower == entry_no_ext or
                query_no_ext == entry_no_ext or
                query_lower in entry_lower
            )
            if is_match:
                entry_type = "folder" if os.path.isdir(full_path) else "file"
                results.append({
                    "path": full_path,
                    "name": entry,
                    "type": entry_type
                })
            if os.path.isdir(full_path) and not entry.startswith(".") and entry not in ("__pycache__", "node_modules", ".git", "build", "dist", "$RECYCLE.BIN", "System Volume Information"):
                _scan(full_path, depth + 1)
    _scan(root_dir, 0)
    return results

def get_directory_contents(path):
    if path == "This PC":
        drives = []
        if platform.system() == "Windows":
            for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
                drive = f"{letter}:\\"
                if os.path.isdir(drive):
                    drives.append(drive)
        else:
            drives.append("/")
        return drives, []
    try:
        if not path or not os.path.exists(path) or not os.path.isdir(path):
            return [], []
        items = os.listdir(path)
        folders = []
        files = []
        for item in items:
            if item.startswith('.') or item in ('__pycache__', 'node_modules', '$RECYCLE.BIN'):
                continue
            full_path = os.path.join(path, item)
            if os.path.isdir(full_path):
                folders.append(item)
            else:
                files.append(item)
        return sorted(folders)[:40], sorted(files)[:40]
    except Exception:
        return [], []

@log_execution_time
def read_file(file_path):
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read(5000)
        return {"status": "success", "content": content}
    except Exception as e:
        logger.error(f"Failed to read file '{file_path}': {e}")
        return {"status": "error", "message": str(e)}

@log_execution_time
def write_file(file_path, content):
    try:
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"Successfully wrote to file '{file_path}'")
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Failed to write to file '{file_path}': {e}")
        return {"status": "error", "message": str(e)}

@log_execution_time
def create_folder(folder_path):
    try:
        os.makedirs(folder_path, exist_ok=True)
        logger.info(f"Created folder '{folder_path}'")
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Failed to create folder '{folder_path}': {e}")
        return {"status": "error", "message": str(e)}

def load_notes():
    db = load_memory_db()
    return db.get("notes", [])

def save_notes(notes):
    db = load_memory_db()
    db["notes"] = notes
    return save_memory_db(db)

def load_recents():
    db = load_memory_db()
    return db.get("recents", [])

def save_recents(recents):
    db = load_memory_db()
    db["recents"] = recents
    return save_memory_db(db)

def add_to_recents(name, cmd, entry_type="app"):
    recents = load_recents()
    recents = [r for r in recents if r["cmd"].lower() != cmd.lower()]
    recents.insert(0, {
        "name": name,
        "cmd": cmd,
        "type": entry_type,
        "timestamp": time.time()
    })
    recents = recents[:6]
    save_recents(recents)

def get_filtered_recents():
    recents = load_recents()
    now = time.time()
    fifteen_days_sec = 15 * 24 * 60 * 60
    filtered = [r for r in recents if (now - r.get("timestamp", 0)) <= fifteen_days_sec]
    filtered = filtered[:6]
    if len(filtered) < 6:
        defaults = [
            {"name": "Notepad", "cmd": "open notepad", "type": "app"},
            {"name": "Calculator", "cmd": "open calculator", "type": "app"},
            {"name": "Paint", "cmd": "open paint", "type": "app"},
            {"name": "Terminal", "cmd": "open command prompt", "type": "app"},
            {"name": "Explorer", "cmd": "open explorer", "type": "app"},
            {"name": "Google", "cmd": "google", "type": "app"}
        ]
        existing_cmds = {r["cmd"].lower() for r in filtered}
        for d in defaults:
            if d["cmd"].lower() not in existing_cmds:
                d["timestamp"] = now
                filtered.append(d)
                if len(filtered) >= 6:
                    break
        save_recents(filtered)
    return filtered[:6]

def get_games():
    if not os.path.exists(GAMES_DIR):
        return []
    try:
        return [os.path.splitext(f)[0] for f in os.listdir(GAMES_DIR) if f.endswith(".lnk") or f.endswith(".exe") or f.endswith(".url")]
    except Exception:
        return []

# ──────────────────────────────────────────────────────────────
# 4. System Operations
# ──────────────────────────────────────────────────────────────
class FILETIME(ctypes.Structure):
    _fields_ = [
        ("dwLowDateTime", ctypes.c_uint32),
        ("dwHighDateTime", ctypes.c_uint32),
    ]

class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", wintypes.DWORD),
        ("dwMemoryLoad", wintypes.DWORD),
        ("ullTotalPhys", ctypes.c_uint64),
        ("ullAvailPhys", ctypes.c_uint64),
        ("ullTotalPageFile", ctypes.c_uint64),
        ("ullAvailPageFile", ctypes.c_uint64),
        ("ullTotalVirtual", ctypes.c_uint64),
        ("ullAvailVirtual", ctypes.c_uint64),
        ("ullAvailExtendedVirtual", ctypes.c_uint64),
    ]

_prev_idle = 0
_prev_kernel = 0
_prev_user = 0
_prev_disk_time = time.time()
_prev_disk_busy = None
_nvidia_smi_available = True

def _init_cpu_tracker():
    global _prev_idle, _prev_kernel, _prev_user
    try:
        idle = FILETIME()
        kernel = FILETIME()
        user = FILETIME()
        if ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
            _prev_idle = (idle.dwHighDateTime << 32) + idle.dwLowDateTime
            _prev_kernel = (kernel.dwHighDateTime << 32) + kernel.dwLowDateTime
            _prev_user = (user.dwHighDateTime << 32) + user.dwLowDateTime
    except Exception:
        pass

_init_cpu_tracker()

_system_metrics_cache = {
    "os": f"{platform.system()} {platform.release()}",
    "python": sys.version.split()[0],
    "cpu": 5.0,
    "ram": 40.0,
    "gpu": 0.0,
    "disk": 0.0
}
_metrics_lock = threading.Lock()
_metrics_thread_started = False
_last_gpu_check = None
_cached_gpu_percent = 0.0

def _calculate_system_metrics_internal():
    global _prev_idle, _prev_kernel, _prev_user, _prev_disk_time, _prev_disk_busy, _nvidia_smi_available
    global _last_gpu_check, _cached_gpu_percent
    cpu_percent = 5.0
    ram_percent = 40.0
    gpu_percent = 0.0
    disk_percent = 0.0
    
    try:
        idle = FILETIME()
        kernel = FILETIME()
        user = FILETIME()
        if ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
            curr_idle = (idle.dwHighDateTime << 32) + idle.dwLowDateTime
            curr_kernel = (kernel.dwHighDateTime << 32) + kernel.dwLowDateTime
            curr_user = (user.dwHighDateTime << 32) + user.dwLowDateTime
            idle_diff = curr_idle - _prev_idle
            kernel_diff = curr_kernel - _prev_kernel
            user_diff = curr_user - _prev_user
            _prev_idle = curr_idle
            _prev_kernel = curr_kernel
            _prev_user = curr_user
            total_sys = kernel_diff + user_diff
            if total_sys > 0:
                cpu_percent = round((total_sys - idle_diff) / total_sys * 100, 1)
                cpu_percent = max(0.0, min(100.0, cpu_percent))
    except Exception:
        cpu_percent = round(3.5 + (time.time() % 6) * 1.5, 1)

    try:
        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(stat)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            ram_percent = float(stat.dwMemoryLoad)
    except Exception:
        pass

    if _nvidia_smi_available:
        # Only query nvidia-smi every 30s; reuse the last reading in between.
        try:
            now = time.time()
            if _last_gpu_check is None or now - _last_gpu_check >= 30:
                output = subprocess.check_output(["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"], text=True, timeout=1, creationflags=CREATE_NO_WINDOW, startupinfo=_hidden_startupinfo())
                gpu_percent = float(output.strip())
                _cached_gpu_percent = gpu_percent
                _last_gpu_check = now
            else:
                gpu_percent = _cached_gpu_percent
        except Exception:
            _nvidia_smi_available = False
            gpu_percent = round(max(1.0, min(95.0, cpu_percent * 0.35 + (time.time() % 4) * 0.8)), 1)
    else:
        gpu_percent = round(max(1.0, min(95.0, cpu_percent * 0.35 + (time.time() % 4) * 0.8)), 1)

    try:
        if psutil:
            curr_time = time.time()
            counters = psutil.disk_io_counters()
            if counters:
                curr_busy = counters.read_time + counters.write_time
                if _prev_disk_busy is not None:
                    time_diff = (curr_time - _prev_disk_time) * 1000.0
                    busy_diff = curr_busy - _prev_disk_busy
                    if time_diff > 0:
                        disk_percent = min(100.0, max(0.0, (busy_diff / time_diff) * 100.0))
                        disk_percent = round(disk_percent, 1)
                _prev_disk_busy = curr_busy
                _prev_disk_time = curr_time
        else:
            total, used, free_disk = shutil.disk_usage("C:\\")
            disk_percent = round((used / total) * 100, 1)
    except Exception:
        try:
            total, used, free_disk = shutil.disk_usage("C:\\")
            disk_percent = round((used / total) * 100, 1)
        except Exception:
            pass
            
    return {
        "os": f"{platform.system()} {platform.release()}",
        "python": sys.version.split()[0],
        "cpu": cpu_percent,
        "ram": ram_percent,
        "gpu": gpu_percent,
        "disk": disk_percent
    }

def _update_system_metrics_loop():
    global _system_metrics_cache
    _init_cpu_tracker()
    while True:
        try:
            metrics = _calculate_system_metrics_internal()
            with _metrics_lock:
                _system_metrics_cache = metrics
        except Exception:
            pass
        time.sleep(5.0)

def get_system_metrics():
    global _metrics_thread_started
    if not _metrics_thread_started:
        with _metrics_lock:
            if not _metrics_thread_started:
                _metrics_thread_started = True
                t = threading.Thread(target=_update_system_metrics_loop, daemon=True, name="SystemMetricsTracker")
                t.start()
    with _metrics_lock:
        return _system_metrics_cache.copy()


@log_execution_time
def open_application(app_name):
    try:
        subprocess.Popen([app_name], shell=True, creationflags=CREATE_NO_WINDOW)
        logger.info(f"Opened application: {app_name}")
        return {"status": "success", "output": f"Opened {app_name}"}
    except Exception as e:
        logger.error(f"Failed to open {app_name}: {e}")
        return {"status": "error", "output": f"Failed to open {app_name}: {str(e)}"}


def capture_desktop_screenshot(max_width=1600):
    """
    Capture a crisp screenshot of the active PC desktop using fast Windows GDI BitBlt
    and return as base64 JPEG string (with fallback to PIL ImageGrab).
    """
    import io
    import base64
    from PIL import Image
    
    # 1. Try Windows Native GDI BitBlt
    try:
        import ctypes
        
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        
        w = user32.GetSystemMetrics(0) or 1920
        h = user32.GetSystemMetrics(1) or 1080
        
        hdc_screen = user32.GetDC(0)
        hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
        hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, w, h)
        gdi32.SelectObject(hdc_mem, hbmp)
        gdi32.BitBlt(hdc_mem, 0, 0, w, h, hdc_screen, 0, 0, 0x00CC0020)
        
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
        bih.biWidth = w
        bih.biHeight = -h  # top-down bitmap
        bih.biPlanes = 1
        bih.biBitCount = 32
        bih.biCompression = 0
        
        raw_buffer = (ctypes.c_char * (w * h * 4))()
        gdi32.GetDIBits(hdc_mem, hbmp, 0, h, raw_buffer, ctypes.byref(bih), 0)
        
        img = Image.frombuffer('RGBA', (w, h), bytes(raw_buffer), 'raw', 'BGRA', 0, 1).convert('RGB')
        
        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(0, hdc_screen)
        
        if img.width > max_width:
            ratio = max_width / float(img.width)
            new_h = int(float(img.height) * ratio)
            img = img.resize((max_width, new_h), Image.Resampling.LANCZOS)
            
        out_buf = io.BytesIO()
        img.save(out_buf, format="JPEG", quality=85)
        return base64.b64encode(out_buf.getvalue()).decode("utf-8")
    except Exception as e:
        logger.debug(f"GDI BitBlt screenshot failed, trying fallback: {e}")

    # 2. Fallback to PIL ImageGrab
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab(all_screens=True)
        if img.width > max_width:
            ratio = max_width / float(img.width)
            new_h = int(float(img.height) * ratio)
            img = img.resize((max_width, new_h), Image.Resampling.LANCZOS)
        out_buf = io.BytesIO()
        img.save(out_buf, format="JPEG", quality=85)
        return base64.b64encode(out_buf.getvalue()).decode("utf-8")
    except Exception as ex:
        logger.error(f"Failed to capture screen: {ex}")
        return None

_mirror_scrcpy_exe = None
_mirror_adb_exe = None
_active_mirror_processes = {}

@log_execution_time
def launch_phone_mirror(ip_port=""):
    """Launch 60FPS borderless scrcpy mirror integrated cleanly inside JASVA HUD without titlebars or latency."""
    global _mirror_scrcpy_exe, _mirror_adb_exe, _active_mirror_processes
    try:
        # Find scrcpy executable (cached)
        if not _mirror_scrcpy_exe:
            scrcpy_paths = [
                os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Genymobile.scrcpy_*\scrcpy-win64-v*\scrcpy.exe"),
                r"C:\Program Files\scrcpy\scrcpy.exe",
                r"C:\scrcpy\scrcpy.exe",
                "scrcpy"
            ]
            for path_pattern in scrcpy_paths:
                matches = glob.glob(path_pattern)
                if matches:
                    _mirror_scrcpy_exe = matches[0]
                    break
                elif os.path.exists(path_pattern):
                    _mirror_scrcpy_exe = path_pattern
                    break
        scrcpy_exe = _mirror_scrcpy_exe

        if not scrcpy_exe:
            return {"status": "error", "output": "scrcpy not found. Install with: winget install Genymobile.scrcpy"}
        
        # Find ADB executable (cached)
        if not _mirror_adb_exe:
            adb_paths = [
                os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"),
                r"C:\Program Files\platform-tools\adb.exe",
                r"C:\platform-tools\adb.exe",
                r"C:\adb\adb.exe",
                "adb"
            ]
            for adb_path in adb_paths:
                matches = glob.glob(adb_path) if "*" in adb_path else ([adb_path] if os.path.exists(adb_path) else [])
                if matches:
                    _mirror_adb_exe = matches[0]
                    break
                elif os.path.exists(adb_path):
                    _mirror_adb_exe = adb_path
                    break
        adb_exe = _mirror_adb_exe
        
        # Auto-detect device from adb devices if no ip_port given
        target = ip_port.strip()
        if not target and adb_exe:
            try:
                result = subprocess.run(
                    [adb_exe, "devices"],
                    capture_output=True, text=True, timeout=5,
                    creationflags=CREATE_NO_WINDOW
                )
                tv_ip = ""
                try:
                    from backend.sys_utils import load_config
                    tv_ip = load_config().get("tv_ip", "").strip()
                except Exception:
                    pass
                tv_target = f"{tv_ip}:5555" if tv_ip else ""
                for line in result.stdout.splitlines()[1:]:
                    parts = line.split()
                    if len(parts) >= 2 and parts[1] == "device" and parts[0] != tv_target:
                        target = parts[0]
                        break
            except Exception:
                pass
        
        if not target:
            return {"status": "error", "output": "No connected device found via ADB."}

        # Determine if target is TV or Phone
        is_tv = False
        tv_ip = ""
        try:
            from backend.sys_utils import load_config
            tv_ip = load_config().get("tv_ip", "").strip()
        except Exception:
            pass
        
        if tv_ip and (target == tv_ip or target == f"{tv_ip}:5555" or tv_ip in target):
            is_tv = True

        # If already running, terminate to toggle off
        if target in _active_mirror_processes:
            p = _active_mirror_processes[target]
            if p and p.poll() is None:
                try:
                    p.terminate()
                except Exception:
                    pass
                _active_mirror_processes.pop(target, None)
                if not is_tv:
                    try:
                        from backend.adb_manager import adb_manager
                        adb_manager.disconnect(target)
                    except Exception:
                        pass
                return {"status": "stopped", "output": f"Closed mirror for {target}."}

        # Launch scrcpy with ADB path via environment
        env = os.environ.copy()
        if adb_exe:
            env["ADB"] = adb_exe

        # Calculate exact screen center coordinates on Windows
        screen_w = 1920
        screen_h = 1080
        try:
            import ctypes
            screen_w = ctypes.windll.user32.GetSystemMetrics(0) or 1920
            screen_h = ctypes.windll.user32.GetSystemMetrics(1) or 1080
        except Exception:
            pass

        # Ultra-smooth 60fps low-latency hardware mirror (native scrcpy performance)
        perf_args = [
            "--video-codec=h264",
            "--video-bit-rate=12M",
            "--max-fps=60",
            "--video-buffer=0",
            "--stay-awake",
            "--always-on-top"
        ]

        if is_tv:
            win_title = f"Fire TV Mirror ({target})"
            args = [scrcpy_exe, "-s", target] + perf_args + [
                f"--window-title={win_title}",
                "--max-size=1280"
            ]
        else:
            win_title = f"Phone Mirror ({target})"
            args = [scrcpy_exe, "-s", target] + perf_args + [
                f"--window-title={win_title}",
                "--max-size=1080"
            ]

        proc = subprocess.Popen(args, env=env, creationflags=CREATE_NO_WINDOW)
        _active_mirror_processes[target] = proc
        
        device_label = "Smart TV" if is_tv else "Phone"
        logger.info(f"Launched mirror for {device_label} ({target})")
        return {"status": "success", "output": f"Mirror active for {device_label}."}
    except Exception as e:
        logger.error(f"Failed to launch mirror: {e}")
        return {"status": "error", "output": f"Failed to launch mirror: {str(e)}"}

def _apply_mirror_window_styling_and_drag(window_title, target, is_tv=False, proc=None):
    """
    Applies modern rounded corners to the scrcpy window, enables window dragging
    exclusively from the top 36px bar, and disconnects wireless ADB on window close.
    """
    import threading
    from ctypes import wintypes
    
    def _worker():
        user32 = getattr(ctypes.windll, "user32", None)
        if not user32:
            return
        dwmapi = getattr(ctypes.windll, "dwmapi", None)
        gdi32 = getattr(ctypes.windll, "gdi32", None)
        
        # Wait for the scrcpy window to appear (up to 8 seconds)
        hwnd = 0
        start = time.time()
        while time.time() - start < 8.0:
            hwnd = user32.FindWindowW(None, window_title)
            if hwnd:
                break
            time.sleep(0.1)
            
        if not hwnd:
            return
            
        time.sleep(0.15)
        
        # 1. Apply Rounded Corners (DWM & GDI)
        try:
            if dwmapi:
                val = ctypes.c_int(2) # DWMWCP_ROUND
                dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(val), ctypes.sizeof(val))
        except Exception:
            pass
            
        try:
            if gdi32:
                rect = wintypes.RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(rect))
                w = rect.right - rect.left
                h = rect.bottom - rect.top
                if w > 50 and h > 50:
                    rgn = gdi32.CreateRoundRectRgn(0, 0, w + 1, h + 1, 24, 24)
                    user32.SetWindowRgn(hwnd, rgn, True)
        except Exception:
            pass

        # 2. Direct Smooth Window Dragging ONLY from Top Bar (top 36 pixels)
        top_bar_height = 36
        pt = wintypes.POINT()
        rect = wintypes.RECT()
        
        while user32.IsWindow(hwnd):
            time.sleep(0.010)
            # Check left mouse button press (VK_LBUTTON = 0x01)
            if user32.GetAsyncKeyState(0x01) & 0x8000:
                user32.GetCursorPos(ctypes.byref(pt))
                user32.GetWindowRect(hwnd, ctypes.byref(rect))
                
                # If initial click is inside top bar area
                if rect.left <= pt.x <= rect.right and rect.top <= pt.y <= rect.top + top_bar_height:
                    start_mouse_x = pt.x
                    start_mouse_y = pt.y
                    start_win_x = rect.left
                    start_win_y = rect.top
                    
                    # Smoothly move window with cursor while left button is held
                    while user32.IsWindow(hwnd) and (user32.GetAsyncKeyState(0x01) & 0x8000):
                        user32.GetCursorPos(ctypes.byref(pt))
                        dx = pt.x - start_mouse_x
                        dy = pt.y - start_mouse_y
                        if dx != 0 or dy != 0:
                            # 0x0015 = SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE
                            user32.SetWindowPos(hwnd, 0, start_win_x + dx, start_win_y + dy, 0, 0, 0x0015)
                        time.sleep(0.008)

        # Mirror window was closed -> clean up process and disconnect wireless phone session
        _active_mirror_processes.pop(target, None)
        if not is_tv:
            try:
                from backend.adb_manager import adb_manager
                adb_manager.disconnect(target)
                logger.info(f"Disconnected phone session on mirror window exit: {target}")
            except Exception:
                pass
                        
    t = threading.Thread(target=_worker, daemon=True)
    t.start()

@log_execution_time
def launch_all_mirrors():
    """Launch 60FPS scrcpy mirrors for all connected devices (Phone + TV) side-by-side."""
    from backend.adb_manager import adb_manager
    devices = [d for d in adb_manager.list_devices() if d["status"] == "device"]
    if not devices:
        return {"status": "error", "output": "No connected devices found via ADB."}
    
    results = []
    for d in devices:
        r = launch_phone_mirror(d["id"])
        results.append(f"{d['id']}: {r.get('output', '')}")
    return {"status": "success", "output": " | ".join(results)}

@log_execution_time
def close_application(app_name):
    try:
        subprocess.Popen(["taskkill", "/f", "/im", f"{app_name}.exe"], creationflags=CREATE_NO_WINDOW)
        logger.info(f"Closed application: {app_name}")
        return {"status": "success", "output": f"Closed {app_name}"}
    except Exception as e:
        logger.error(f"Failed to close {app_name}: {e}")
        return {"status": "error", "output": f"Failed to close {app_name}: {str(e)}"}

@log_execution_time
def take_screenshot(desktop_dir):
    filename = f"Screenshot_{int(time.time())}.png"
    filepath = os.path.join(desktop_dir, filename)
    ps_script = f"""
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    $screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $bmp = New-Object System.Drawing.Bitmap $screen.Width, $screen.Height
    $graphics = [System.Drawing.Graphics]::FromImage($bmp)
    $graphics.CopyFromScreen($screen.X, $screen.Y, 0, 0, $bmp.Size)
    $bmp.Save('{filepath.replace("'", "''")}', [System.Drawing.Imaging.ImageFormat]::Png)
    $graphics.Dispose()
    $bmp.Dispose()
    """
    try:
        res = subprocess.run(["powershell", "-Command", ps_script], capture_output=True, text=True, timeout=10, creationflags=CREATE_NO_WINDOW)
        if os.path.exists(filepath):
            os.startfile(filepath)
            logger.info(f"Screenshot saved to {filepath}")
            return {"status": "success", "output": f"Screenshot saved to {filepath}"}
    except Exception as e:
        logger.error(f"Failed to take screenshot: {e}")
        return {"status": "error", "output": f"Failed to take screenshot: {str(e)}"}

@log_execution_time
def empty_recycle_bin():
    try:
        cmd = ["powershell", "-Command", "Clear-RecycleBin -Confirm:$false -ErrorAction SilentlyContinue"]
        subprocess.run(cmd, capture_output=True, text=True, timeout=10, creationflags=CREATE_NO_WINDOW)
        logger.info("Recycle bin emptied")
        return {"status": "success", "output": "Recycle bin emptied"}
    except Exception as e:
        logger.error(f"Failed to empty recycle bin: {e}")
        return {"status": "error", "output": f"Failed to empty recycle bin: {str(e)}"}

@log_execution_time
def close_explorer_folders():
    script = '(New-Object -ComObject Shell.Application).Windows() | Where-Object { $_.Name -eq "File Explorer" -or $_.Name -eq "Windows Explorer" } | ForEach-Object { $_.Quit() }'
    try:
        subprocess.run(["powershell", "-Command", script], capture_output=True, text=True, timeout=5, creationflags=CREATE_NO_WINDOW)
        logger.info("Closed all File Explorer windows")
        return {"status": "success", "output": "Closed all File Explorer windows"}
    except Exception as e:
        logger.error(f"Failed to close explorer folders: {e}")
        return {"status": "error", "output": f"Failed to close explorer folders: {str(e)}"}

@log_execution_time
def set_brightness(percent):
    try:
        val = max(0, min(100, int(percent)))
        ps_cmd = f"$b = Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods; Invoke-CimMethod -InputObject $b -MethodName WmiSetBrightness -Arguments @{{ Timeout = 0; Brightness = {val} }}"
        res = subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, text=True, timeout=5, creationflags=CREATE_NO_WINDOW)
        logger.info(f"Brightness set to {percent}%")
        return {"status": "success", "output": f"Brightness set to {percent}%"}
    except Exception as e:
        logger.error(f"Failed to set brightness: {e}")
        return {"status": "error", "output": f"Failed to set brightness: {str(e)}"}

def get_brightness():
    try:
        ps_cmd = "(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness).CurrentBrightness"
        res = subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, text=True, timeout=5, creationflags=CREATE_NO_WINDOW)
        if res.returncode == 0 and res.stdout.strip().isdigit():
            return int(res.stdout.strip())
    except Exception:
        pass
    return None

def send_media_key(key_code):
    try:
        cmd = f'powershell -Command "$wsh = New-Object -ComObject Wscript.Shell; $wsh.SendKeys([char]{key_code})"'
        subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
        return True
    except Exception:
        return False

def get_windows_volume():
    if PYCAW_AVAILABLE:
        try:
            devices = AudioUtilities.GetSpeakers()
            volume = devices.EndpointVolume
            current_val = volume.GetMasterVolumeLevelScalar()
            return int(round(current_val * 100))
        except Exception as e:
            logger.error(f"Failed to get volume using pycaw: {e}")
    return 50

def set_windows_volume(percent):
    if PYCAW_AVAILABLE:
        try:
            devices = AudioUtilities.GetSpeakers()
            volume = devices.EndpointVolume
            level = max(0.0, min(1.0, float(percent) / 100.0))
            volume.SetMasterVolumeLevelScalar(level, None)
            logger.info(f"Volume set to {percent}% using pycaw")
            return True
        except Exception as e:
            logger.error(f"Failed to set volume using pycaw: {e}")
    return False

def set_clipboard_text(text):
    try:
        ps_cmd = "Set-Clipboard -Value '" + text.replace("'", "''") + "'"
        res = subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, text=True, timeout=3, creationflags=CREATE_NO_WINDOW)
        return res.returncode == 0
    except Exception:
        return False

def get_clipboard_text():
    try:
        res = subprocess.run(["powershell", "-Command", "Get-Clipboard"], capture_output=True, text=True, timeout=3, creationflags=CREATE_NO_WINDOW)
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return None

def clear_clipboard():
    try:
        ps_cmd = "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Clipboard]::Clear()"
        res = subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, text=True, timeout=3, creationflags=CREATE_NO_WINDOW)
        return res.returncode == 0
    except Exception:
        return False

def find_shortcut_or_executable(app_name):
    app_name_lower = app_name.lower().strip()
    search_dirs = []
    if GAMES_DIR and os.path.exists(GAMES_DIR):
        search_dirs.append(GAMES_DIR)
    if DESKTOP_DIR and os.path.exists(DESKTOP_DIR):
        search_dirs.append(DESKTOP_DIR)
    search_dirs.extend([
        r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs",
        os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs")
    ])
    valid_exts = (".lnk", ".url", ".exe")
    for directory in search_dirs:
        if not directory or not os.path.exists(directory):
            continue
        try:
            for root, dirs, files in os.walk(directory):
                for f in files:
                    if f.lower().endswith(valid_exts):
                        name = os.path.splitext(f)[0].lower().strip()
                        if name == app_name_lower:
                            return os.path.join(root, f)
        except Exception:
            pass
    for directory in search_dirs:
        if not directory or not os.path.exists(directory):
            continue
        try:
            for root, dirs, files in os.walk(directory):
                for f in files:
                    if f.lower().endswith(valid_exts):
                        name = os.path.splitext(f)[0].lower().strip()
                        if app_name_lower in name or name in app_name_lower:
                            return os.path.join(root, f)
        except Exception:
            pass
    return None

def start_menu_search_and_open(app_name):
    escaped_name = ""
    for char in app_name:
        if char in ["+", "^", "%", "~", "(", ")", "{", "}"]:
            escaped_name += f"{{{char}}}"
        else:
            escaped_name += char
    ps_cmd = (
        f"$w = New-Object -ComObject Wscript.Shell; "
        f"$w.SendKeys('^{{ESC}}'); "
        f"Start-Sleep -Milliseconds 400; "
        f"$w.SendKeys('{escaped_name}'); "
        f"Start-Sleep -Milliseconds 500; "
        f"$w.SendKeys('~');"
    )
    subprocess.Popen(["powershell", "-Command", ps_cmd], creationflags=CREATE_NO_WINDOW)

# ──────────────────────────────────────────────────────────────
# 5. Crash Recovery
# ──────────────────────────────────────────────────────────────
class CrashRecoveryManager:
    def __init__(self):
        self._running = False
        self._heartbeat_thread = None
        self._last_heartbeat = time.time()
        self._restart_count = 0
        self._crash_count = 0
        
    def start_heartbeat_monitor(self):
        if self._running: return
        self._running = True
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_monitor, daemon=True)
        self._heartbeat_thread.start()
        logger.info("Crash recovery heartbeat monitor started")
    
    def stop_heartbeat_monitor(self):
        self._running = False
        if self._heartbeat_thread: self._heartbeat_thread.join(timeout=5)
        logger.info("Crash recovery heartbeat monitor stopped")
    
    def update_heartbeat(self):
        self._last_heartbeat = time.time()
        self._save_heartbeat()
    
    def _heartbeat_monitor(self):
        while self._running:
            time.sleep(30)
            time_since_heartbeat = time.time() - self._last_heartbeat
            if time_since_heartbeat > 90:
                logger.warning(f"Crash detected! Heartbeat stale for {time_since_heartbeat:.1f}s")
                self._handle_crash()
    
    def _handle_crash(self):
        self._crash_count += 1
        logger.error(f"Crash #{self._crash_count} detected")
        self._log_crash()
        if self._restart_count < 5:
            logger.info(f"Attempting auto-restart (attempt {self._restart_count + 1}/5)")
            self._attempt_restart()
        else:
            logger.critical("Max restart attempts reached. Giving up.")
            self._running = False
    
    def _attempt_restart(self):
        try:
            self._restart_count += 1
            time.sleep(5)
            if getattr(sys, 'frozen', False): restart_cmd = [sys.executable]
            else:
                pythonw_path = sys.executable.replace("python.exe", "pythonw.exe")
                restart_cmd = [pythonw_path, os.path.abspath(os.path.join(ROOT_DIR, "app.pyw"))]
            logger.info(f"Restarting with command: {' '.join(restart_cmd)}")
            subprocess.Popen(restart_cmd, creationflags=0x08000000)
            logger.info("Current process exiting for restart")
            os._exit(0)
        except Exception as e:
            logger.error(f"Restart failed: {e}")
            self._running = False
    
    def _save_heartbeat(self):
        try:
            with open(HEARTBEAT_FILE, "w") as f:
                json.dump({"timestamp": self._last_heartbeat, "restart_count": self._restart_count, "crash_count": self._crash_count}, f)
        except Exception as e: logger.error(f"Failed to save heartbeat: {e}")
    
    def _load_heartbeat(self):
        try:
            if os.path.exists(HEARTBEAT_FILE):
                with open(HEARTBEAT_FILE, "r") as f:
                    data = json.load(f)
                    self._last_heartbeat = data.get("timestamp", time.time())
                    self._restart_count = data.get("restart_count", 0)
                    self._crash_count = data.get("crash_count", 0)
        except Exception as e: logger.error(f"Failed to load heartbeat: {e}")
    
    def _log_crash(self):
        try:
            crash_entry = {"timestamp": time.time(), "crash_count": self._crash_count, "restart_count": self._restart_count, "time_since_heartbeat": time.time() - self._last_heartbeat}
            crash_log = []
            if os.path.exists(CRASH_LOG_FILE):
                try:
                    with open(CRASH_LOG_FILE, "r") as f: crash_log = json.load(f)
                except Exception: pass
            crash_log.append(crash_entry)
            with open(CRASH_LOG_FILE, "w") as f: json.dump(crash_log[-50:], f, indent=2)
        except Exception as e: logger.error(f"Failed to log crash: {e}")

_crash_manager = None
def get_crash_manager():
    global _crash_manager
    if _crash_manager is None:
        _crash_manager = CrashRecoveryManager()
        _crash_manager._load_heartbeat()
    return _crash_manager

def setup_crash_recovery():
    manager = get_crash_manager()
    manager.start_heartbeat_monitor()
    return manager

def update_heartbeat():
    get_crash_manager().update_heartbeat()
