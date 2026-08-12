import http.server
import socketserver
import threading
import json
import os
import socket
import hashlib
import base64
import ctypes
from urllib.parse import urlparse, parse_qs
from backend.sys_utils import logger, ROOT_DIR, load_config
from backend.tv_manager import tv_manager
from backend.adb_manager import adb_manager

# ─── Windows INPUT structures for simulated mouse/keyboard events ───
class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))
    ]

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.c_ulong),
        ("wParamL", ctypes.c_short),
        ("wParamH", ctypes.c_ushort)
    ]

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))
    ]

class INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("ki", KEYBDINPUT),
        ("mi", MOUSEINPUT),
        ("hi", HARDWAREINPUT)
    ]

class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("union", INPUT_UNION)
    ]

# Mouse Event Flags
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

def get_mouse_pos():
    pt = POINT()
    try:
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y
    except Exception:
        return 0, 0

def move_mouse_relative(dx, dy):
    x, y = get_mouse_pos()
    try:
        ctypes.windll.user32.SetCursorPos(int(x + dx), int(y + dy))
    except Exception as e:
        logger.error(f"Error moving mouse: {e}")

def click_mouse(button="left"):
    try:
        if button == "left":
            ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        elif button == "right":
            ctypes.windll.user32.mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
            ctypes.windll.user32.mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
    except Exception as e:
        logger.error(f"Error clicking mouse: {e}")

def send_unicode_char(char):
    try:
        inputs = (INPUT * 2)()
        inputs[0].type = 1
        inputs[0].union.ki.wVk = 0
        inputs[0].union.ki.wScan = ord(char)
        inputs[0].union.ki.dwFlags = 0x0004  # KEYEVENTF_UNICODE
        
        inputs[1].type = 1
        inputs[1].union.ki.wVk = 0
        inputs[1].union.ki.wScan = ord(char)
        inputs[1].union.ki.dwFlags = 0x0004 | 0x0002  # KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
        
        ctypes.windll.user32.SendInput(2, ctypes.byref(inputs), ctypes.sizeof(INPUT))
    except Exception as e:
        logger.error(f"Error sending Unicode char: {e}")

def send_vk_key(vk):
    try:
        inputs = (INPUT * 2)()
        inputs[0].type = 1
        inputs[0].union.ki.wVk = vk
        inputs[0].union.ki.dwFlags = 0
        
        inputs[1].type = 1
        inputs[1].union.ki.wVk = vk
        inputs[1].union.ki.dwFlags = 0x0002
        
        ctypes.windll.user32.SendInput(2, ctypes.byref(inputs), ctypes.sizeof(INPUT))
    except Exception as e:
        logger.error(f"Error sending VK key: {e}")

# Virtual Keycodes for Keyboard Event relays
VK_MAP = {
    "backspace": 0x08,
    "tab": 0x09,
    "enter": 0x0D,
    "escape": 0x1B,
    "space": 0x20,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "delete": 0x2E
}

# ─── HTTP & WebSocket Request Handler ───
class MultiDeviceHTTPRequestHandler(http.server.BaseHTTPRequestHandler):
    
    def log_message(self, format, *args):
        # Override to suppress standard HTTP logging to terminal
        pass

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        parsed_url = urlparse(self.path)
        if parsed_url.path == "/api/command":
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length).decode('utf-8')
            try:
                data = json.loads(post_data)
                command_text = data.get("command", "")
                
                # Execute command via routing pipeline
                from backend.command_router import _execute_command_internal
                res = _execute_command_internal(command_text, allow_llm_fallback=True)
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(res).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        
        # 1. Check for WebSocket Upgrade
        if path == "/ws" and self.headers.get("Upgrade", "").lower() == "websocket":
            self.handle_websocket_handshake()
            self.handle_websocket_loop()
            return

        # 2. API endpoints
        if path == "/api/status":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            # Fetch statuses
            tv_ip = tv_manager.get_tv_ip()
            tv_connected = tv_manager.is_connected()
            adb_devices = adb_manager.list_devices()
            
            status_data = {
                "status": "online",
                "tv_ip": tv_ip,
                "tv_connected": tv_connected,
                "adb_devices": adb_devices,
                "pc_ip": get_local_ip()
            }
            self.wfile.write(json.dumps(status_data).encode('utf-8'))
            return

        elif path == "/api/set_tv_ip":
            query = parse_qs(parsed_url.query)
            ip = query.get("ip", [""])[0]
            res = tv_manager.set_tv_ip(ip)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(res).encode('utf-8'))
            return

        # 3. Static Files serving
        frontend_dir = os.path.join(ROOT_DIR, "frontend")
        
        if path in ("/", "/remote", "/remote.html"):
            file_to_serve = os.path.join(frontend_dir, "remote.html")
            content_type = "text/html"
        elif path == "/remote.js":
            file_to_serve = os.path.join(frontend_dir, "remote.js")
            content_type = "application/javascript"
        else:
            # Map other static files like index.css, shared.js, etc.
            filename = path.lstrip("/")
            file_to_serve = os.path.join(frontend_dir, filename)
            if filename.endswith(".css"):
                content_type = "text/css"
            elif filename.endswith(".js"):
                content_type = "application/javascript"
            elif filename.endswith(".ico"):
                content_type = "image/x-icon"
            else:
                content_type = "text/plain"

        if os.path.exists(file_to_serve) and os.path.isfile(file_to_serve):
            try:
                with open(file_to_serve, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(content)
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(f"Error reading file: {e}".encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"File not found.")

    def handle_websocket_handshake(self):
        key = self.headers.get('Sec-WebSocket-Key', '')
        guid = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
        accept_val = base64.b64encode(hashlib.sha1((key + guid).encode('utf-8')).digest()).decode('utf-8')
        
        self.send_response(101, "Switching Protocols")
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", accept_val)
        self.end_headers()
        logger.info("WebSocket handshake successful.")

    def handle_websocket_loop(self):
        sock = self.request
        sock.setblocking(True)
        try:
            while True:
                header = sock.recv(2)
                if not header or len(header) < 2:
                    break
                
                b1, b2 = header[0], header[1]
                opcode = b1 & 0x0f
                masked = (b2 & 0x80) != 0
                payload_len = b2 & 0x7f
                
                if opcode == 8: # Close frame
                    break
                    
                if payload_len == 126:
                    len_bytes = sock.recv(2)
                    payload_len = int.from_bytes(len_bytes, byteorder='big')
                elif payload_len == 127:
                    len_bytes = sock.recv(8)
                    payload_len = int.from_bytes(len_bytes, byteorder='big')
                    
                if masked:
                    mask_key = sock.recv(4)
                else:
                    mask_key = None
                    
                payload = bytearray()
                while len(payload) < payload_len:
                    chunk = sock.recv(payload_len - len(payload))
                    if not chunk:
                        break
                    payload.extend(chunk)
                    
                if len(payload) < payload_len:
                    break
                    
                if masked and mask_key:
                    unmasked = bytearray(b ^ mask_key[i % 4] for i, b in enumerate(payload))
                else:
                    unmasked = payload
                    
                if opcode == 1: # Text frame
                    msg = unmasked.decode('utf-8', errors='ignore')
                    self.process_ws_message(msg)
        except Exception as e:
            logger.error(f"WebSocket execution exception: {e}")
        finally:
            logger.info("WebSocket connection closed.")

    def process_ws_message(self, message):
        try:
            data = json.loads(message)
            msg_type = data.get("type")
            
            # 1. Trackpad moves
            if msg_type == "mouse_move":
                dx = data.get("dx", 0)
                dy = data.get("dy", 0)
                move_mouse_relative(dx, dy)
                
            # 2. Trackpad clicks
            elif msg_type == "mouse_click":
                btn = data.get("button", "left")
                click_mouse(btn)
                
            # 3. Unicode Keyboard Input
            elif msg_type == "keyboard_input":
                text = data.get("text", "")
                for c in text:
                    send_unicode_char(c)
                    
            # 4. Keyboard Key Events (e.g. backspace, enter)
            elif msg_type == "key_event":
                key = data.get("key", "").lower()
                if key in VK_MAP:
                    send_vk_key(VK_MAP[key])
                    
            # 5. Smart TV direct button triggers
            elif msg_type == "tv_button":
                btn = data.get("button", "")
                tv_manager.send_button(btn)

            # 6. Smart TV app launching
            elif msg_type == "tv_app":
                app = data.get("app", "")
                tv_manager.launch_app(app)
                
        except Exception as e:
            logger.error(f"Error processing WS message: {e}")

# ─── Server Manager ───
class MultiDeviceServer:
    def __init__(self, port=8080):
        self.port = port
        self.server = None
        self.thread = None

    def start(self):
        def run():
            # Allow address reuse to prevent socket errors on hot restarts
            socketserver.TCPServer.allow_reuse_address = True
            with socketserver.TCPServer(("0.0.0.0", self.port), MultiDeviceHTTPRequestHandler) as httpd:
                self.server = httpd
                logger.info(f"Multi-device server listening on http://0.0.0.0:{self.port}")
                httpd.serve_forever()
                
        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            logger.info("Multi-device server stopped.")

def get_local_ip():
    """Retrieve local network IPv4 address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Doesn't need to actually connect to the IP
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

# Global instance
device_server = MultiDeviceServer(8080)
