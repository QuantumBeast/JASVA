import os
import sys
import json
import time
import re
import urllib.request
import urllib.parse
import hashlib
import base64
from datetime import datetime

# Import from sys_utils
from backend.sys_utils import (
    logger, log_execution_time, get_credential_manager,
    DB_DIR, BACKEND_DIR, load_config, find_shortcut_or_executable
)

# Configuration and Cache
CACHE_FILE = os.path.join(DB_DIR, "response_cache.json")
RESPONSE_CACHE = {}
CACHE_MAX_SIZE = 100
CACHE_TTL = 86400

# ──────────────────────────────────────────────────────────────
# Network Operations & Scrapers
# ──────────────────────────────────────────────────────────────
CACHED_WEATHER = "Synchronizing weather feed..."
CACHED_PING = "Checking..."
CACHED_IP = "Detecting..."
CACHED_NET_STATUS = "Online"

def _update_network_and_weather_worker():
    global CACHED_WEATHER, CACHED_PING, CACHED_IP, CACHED_NET_STATUS
    try:
        w_info = get_weather(None)
        if w_info:
            CACHED_WEATHER = w_info
    except Exception:
        pass
    try:
        latency, ext_ip = check_network()
        if latency is not None:
            CACHED_PING = f"{latency}ms"
            CACHED_NET_STATUS = "Online"
        else:
            CACHED_PING = "Unreachable"
            CACHED_NET_STATUS = "Disconnected"
        if ext_ip:
            CACHED_IP = ext_ip
    except Exception:
        pass

def start_network_weather_update():
    import threading
    t = threading.Thread(target=_update_network_and_weather_worker, daemon=True)
    t.start()

@log_execution_time
def check_network():
    import subprocess
    latency = None
    external_ip = None
    CREATE_NO_WINDOW = 0x08000000
    try:
        res = subprocess.run(["ping", "-n", "1", "-w", "2000", "8.8.8.8"], capture_output=True, text=True, timeout=5, creationflags=CREATE_NO_WINDOW)
        if res.returncode == 0:
            match = re.search(r'time[=<](\d+)ms', res.stdout)
            if match:
                latency = int(match.group(1))
            else:
                latency = 0
    except Exception:
        pass
    try:
        req = urllib.request.Request("https://api.ipify.org?format=json", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode("utf-8"))
            external_ip = data.get("ip")
    except Exception:
        pass
    return latency, external_ip

@log_execution_time
def get_weather(location=None):
    if location:
        url = f"https://wttr.in/{urllib.parse.quote(location)}?format=%l:+%C,+%t,+wind+%w,+humidity+%h"
    else:
        url = "https://wttr.in/?format=%l:+%C,+%t,+wind+%w,+humidity+%h"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "curl/7.81.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            content = response.read().decode("utf-8").strip()
            content = " ".join(content.split())
            if "Error" not in content and "Unknown location" not in content:
                content = re.sub(r'\+(\d+)', r'\1', content)
                content = re.sub(r'[^\x00-\x7F]+', ' ', content)
                content = " ".join(content.split())
                return content
    except Exception:
        pass
    return None

def get_cached_network_status():
    return {
        "weather": CACHED_WEATHER,
        "ping": CACHED_PING,
        "ip": CACHED_IP,
        "status": CACHED_NET_STATUS
    }

def web_search_api(query, max_results=5):
    from html import unescape
    logger.info(f"Programmatic search for: {query}")
    try:
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        with urllib.request.urlopen(req, timeout=10) as response:
            html_content = response.read().decode('utf-8', errors='ignore')
        results = []
        blocks = html_content.split('class="result results_links results_links_deep web-result ">')
        for block in blocks[1:]:
            title_match = re.search(r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.DOTALL)
            snippet_match = re.search(r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>', block, re.DOTALL)
            if title_match:
                raw_url = title_match.group(1)
                title = re.sub(r'<[^>]+>', '', title_match.group(2))
                title = unescape(title).strip()
                parsed_url = urllib.parse.urlparse(raw_url)
                url = raw_url
                if parsed_url.query:
                    qs = urllib.parse.parse_qs(parsed_url.query)
                    if 'uddg' in qs: url = qs['uddg'][0]
                snippet = ""
                if snippet_match:
                    snippet = re.sub(r'<[^>]+>', '', snippet_match.group(1))
                    snippet = unescape(snippet).strip()
                results.append({"title": title, "url": url, "snippet": snippet})
                if len(results) >= max_results: break
        if not results: return "No search results found."
        return "\n".join([f"[{idx+1}] Title: {r['title']}\n    URL: {r['url']}\n    Snippet: {r['snippet']}\n" for idx, r in enumerate(results)])
    except Exception as e:
        logger.error(f"Web search scraping failed: {e}")
        return f"Web search failed: {str(e)}"

def web_fetch_api(url):
    from html import unescape
    logger.info(f"Programmatic webpage scrape for: {url}")
    try:
        if not url.startswith("http://") and not url.startswith("https://"): url = "https://" + url
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        with urllib.request.urlopen(req, timeout=12) as response:
            html_content = response.read().decode('utf-8', errors='ignore')
        html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL)
        html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL)
        html_content = re.sub(r'<!--.*?-->', '', html_content, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', html_content)
        text = unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:6000] + "\n... [Content truncated to 6000 characters]" if len(text) > 6000 else text
    except Exception as e:
        logger.error(f"Web page scraping failed: {e}")
        return f"Failed to retrieve web page content: {str(e)}"

def search_web(query):
    import webbrowser
    try:
        encoded_query = urllib.parse.quote(query)
        webbrowser.open(f"https://www.google.com/search?q={encoded_query}")
        logger.info(f"Performed web search for: {query}")
        return {"status": "success", "output": f"Searching Google for '{query}'"}
    except Exception as e:
        logger.error(f"Web search failed: {e}")
        return {"status": "error", "output": f"Web search failed: {str(e)}"}

def search_youtube(query):
    import webbrowser
    try:
        if query:
            encoded_query = urllib.parse.quote(query)
            webbrowser.open(f"https://www.youtube.com/results?search_query={encoded_query}")
            logger.info(f"Searching YouTube for: {query}")
            return {"status": "success", "output": f"Searching YouTube for '{query}'"}
        else:
            webbrowser.open("https://www.youtube.com")
            return {"status": "success", "output": "Opening YouTube"}
    except Exception as e:
        logger.error(f"YouTube search failed: {e}")
        return {"status": "error", "output": f"YouTube search failed: {str(e)}"}

def search_spotify(query):
    import webbrowser
    try:
        if query:
            spotify_path = find_shortcut_or_executable("spotify")
            if spotify_path:
                os.startfile(f"spotify:search:{urllib.parse.quote(query)}")
                logger.info(f"Searching Spotify for: {query}")
                return {"status": "success", "output": f"Searching Spotify for '{query}'"}
            else:
                encoded_query = urllib.parse.quote(query)
                webbrowser.open(f"https://open.spotify.com/search/{encoded_query}")
                return {"status": "success", "output": f"Searching Spotify web for '{query}'"}
        else:
            webbrowser.open("https://open.spotify.com")
            return {"status": "success", "output": "Opening Spotify"}
    except Exception as e:
        logger.error(f"Spotify search failed: {e}")
        return {"status": "error", "output": f"Spotify search failed: {str(e)}"}

def play_youtube_first_result(query):
    import webbrowser
    try:
        encoded_query = urllib.parse.quote(query)
        search_url = f"https://www.youtube.com/results?search_query={encoded_query}"
        req = urllib.request.Request(search_url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        with urllib.request.urlopen(req, timeout=8) as response:
            html = response.read().decode('utf-8', errors='ignore')
        video_ids = re.findall(r'"videoId":"([^"]+)"', html)
        if video_ids:
            first_video_id = video_ids[0]
            video_url = f"https://www.youtube.com/watch?v={first_video_id}"
            webbrowser.open(video_url)
            logger.info(f"Autonomously playing first YouTube video: {video_url} for query: {query}")
            return {"status": "success", "output": f"Playing the first YouTube search result: {video_url}"}
        else:
            webbrowser.open(search_url)
            return {"status": "success", "output": f"Opening YouTube search index for: {query}"}
    except Exception as e:
        logger.error(f"YouTube autonomous play failed: {e}")
        try:
            webbrowser.open(f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}")
            return {"status": "success", "output": f"Opened YouTube search results for: {query}"}
        except Exception:
            return {"status": "error", "output": f"Failed to open YouTube: {str(e)}"}

# ──────────────────────────────────────────────────────────────
# Response Caching
# ──────────────────────────────────────────────────────────────
def extract_json_response(text):
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        candidate = text[start:end+1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
    return None

def _generate_cache_key(text, image_base64=None):
    key_data = text
    if image_base64: key_data += image_base64[:100]
    return hashlib.md5(key_data.encode()).hexdigest()

def load_response_cache():
    global RESPONSE_CACHE
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                RESPONSE_CACHE = json.load(f)
        except Exception:
            RESPONSE_CACHE = {}

def save_response_cache():
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(RESPONSE_CACHE, f, indent=2)
    except Exception:
        pass

def get_cached_response(text, image_base64=None):
    load_response_cache()
    cache_key = _generate_cache_key(text, image_base64)
    if cache_key in RESPONSE_CACHE:
        cached = RESPONSE_CACHE[cache_key]
        if time.time() - cached.get("timestamp", 0) < CACHE_TTL:
            logger.info(f"Cache hit for: {text[:50]}...")
            return cached.get("response")
        else:
            del RESPONSE_CACHE[cache_key]
            save_response_cache()
    return None

def cache_response(text, response, image_base64=None):
    cache_key = _generate_cache_key(text, image_base64)
    if len(RESPONSE_CACHE) >= CACHE_MAX_SIZE:
        oldest_key = min(RESPONSE_CACHE.keys(), key=lambda k: RESPONSE_CACHE[k].get("timestamp", 0))
        del RESPONSE_CACHE[oldest_key]
    RESPONSE_CACHE[cache_key] = {
        "response": response,
        "timestamp": time.time(),
        "text": text[:100]
    }
    save_response_cache()
    logger.info(f"Cached response for: {text[:50]}...")

def fetch_elevenlabs_voices(api_key):
    """Fetch the list of available voices from ElevenLabs API."""
    try:
        url = "https://api.elevenlabs.io/v1/voices"
        headers = {
            "xi-api-key": api_key,
            "accept": "application/json"
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            
        voices = []
        for voice in data.get("voices", []):
            voices.append({
                "id": voice.get("voice_id"),
                "name": voice.get("name"),
                "category": voice.get("category")
            })
        return voices
    except urllib.error.HTTPError as e:
        logger.error(f"Failed to fetch ElevenLabs voices (code {e.code}): {e}")
        # Add to exhausted keys if unauthorized, quota exceeded, or rate limited
        if e.code in (401, 402, 429):
            _exhausted_elevenlabs_keys.add(api_key)
        return []
    except Exception as e:
        logger.error(f"Failed to fetch ElevenLabs voices: {e}")
        return []

_exhausted_elevenlabs_keys = set()

def get_all_elevenlabs_keys():
    keys = []
    try:
        cred_manager = get_credential_manager()
        primary_key = cred_manager.get_api_key("elevenlabs")
        if primary_key:
            # Split comma/semicolon/whitespace separated multiple keys
            for k in re.split(r'[,;\s]+', primary_key):
                k = k.strip()
                if k and k not in keys:
                    keys.append(k)
    except Exception:
        pass
    env_path = os.path.join(BACKEND_DIR, ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r") as f:
                for line in f:
                    if "=" in line:
                        parts = line.strip().split("=", 1)
                        key_name = parts[0].strip()
                        key_value = parts[1].strip().strip('"').strip("'")
                        if not key_value: continue
                        if key_name == "ELEVENLABS_API_KEY" or key_name.startswith("ELEVENLABS_API_KEY_"):
                            for k in re.split(r'[,;\s]+', key_value):
                                k = k.strip()
                                if k and k not in keys:
                                    keys.append(k)
        except Exception:
            pass
    working_keys = [k for k in keys if k not in _exhausted_elevenlabs_keys]
    if not working_keys and keys:
        _exhausted_elevenlabs_keys.clear()
        working_keys = keys
    return working_keys

def call_elevenlabs_tts(text):
    keys = get_all_elevenlabs_keys()
    if not keys: raise Exception("ElevenLabs API Key not configured")
    config = load_config()
    voice_id = config.get("elevenlabs_voice", "21m00Tcm4TlvDq8ikWAM")
    last_error = None
    for api_key in keys:
        try:
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128"
            payload = {
                "text": text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75
                }
            }
            headers = {
                "Content-Type": "application/json",
                "xi-api-key": api_key,
                "accept": "audio/mpeg"
            }
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=15) as response:
                audio_data = response.read()
            audio_base64 = base64.b64encode(audio_data).decode("utf-8")
            return audio_base64
        except urllib.error.HTTPError as e:
            error_msg = e.read().decode('utf-8', errors='ignore') if e.fp else str(e)
            try:
                err_json = json.loads(error_msg)
                msg = err_json.get("detail", {}).get("message", error_msg)
            except Exception:
                msg = error_msg
            err_text = f"ElevenLabs HTTP {e.code}: {msg}"
            logger.warning(f"ElevenLabs API Key failed ({api_key[:8]}...): {err_text}")
            if e.code in (401, 402, 429) or "quota" in msg.lower() or "credit" in msg.lower() or "payment" in msg.lower() or "limit" in msg.lower():
                _exhausted_elevenlabs_keys.add(api_key)
            last_error = Exception(err_text)
        except Exception as e:
            err_text = str(e)
            logger.warning(f"ElevenLabs API Key failed ({api_key[:8]}...): {err_text}")
            last_error = e
    if last_error: raise last_error
    raise Exception("ElevenLabs API Key failed")

def clean_and_summarize_for_speech(text):
    if not text: return ""
    try:
        cleaned = re.sub(r'```[\s\S]*?```', ' ', text)
        lines = cleaned.split('\n')
        processed_lines = []
        for line in lines:
            line = line.strip()
            if not line: continue
            line = re.sub(r'^([-\*\+\u2022]\s+|\d+\.\s+)', '', line)
            line = line.strip()
            if not line: continue
            if not line.endswith(('.', '!', '?', ':', ';', ',')): line += '.'
            processed_lines.append(line)
        cleaned = ' '.join(processed_lines)
        cleaned = re.sub(r'`([^`]+)`', r'\1', cleaned)
        cleaned = re.sub(r'\*\*([^*]+)\*\*', r'\1', cleaned)
        cleaned = re.sub(r'\*([^*]+)\*', r'\1', cleaned)
        cleaned = re.sub(r'__([^_]+)__', r'\1', cleaned)
        cleaned = re.sub(r'_([^_]+)_', r'\1', cleaned)
        cleaned = re.sub(r'#+\s+', '', cleaned)
        cleaned = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', cleaned)
        cleaned = re.sub(r'<[^>]+>', '', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned
    except Exception as e:
        logger.error(f"Failed to clean speech text: {e}")
        return text

def call_real_edge_tts(text):
    import asyncio
    import edge_tts
    async def amain():
        cleaned = clean_and_summarize_for_speech(text)
        if not cleaned: return b""
        config = load_config()
        voice = config.get("voice", "en-GB-RyanNeural")
        communicate = edge_tts.Communicate(cleaned, voice)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        return audio_data
        
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        audio_data = loop.run_until_complete(amain())
        loop.close()
        return base64.b64encode(audio_data).decode("utf-8")
    except Exception as e:
        logger.error(f"Failed to generate Edge TTS: {e}")
        raise e

def call_edge_tts(text):
    cleaned_text = clean_and_summarize_for_speech(text)
    if not cleaned_text: return None
    
    config = load_config()
    engine = config.get("speech_engine", "elevenlabs")
    
    if engine == "elevenlabs":
        try:
            logger.info(f"Speaking (ElevenLabs): {cleaned_text}")
            return call_elevenlabs_tts(cleaned_text)
        except Exception as e:
            logger.warning(f"ElevenLabs TTS failed, falling back to Edge TTS. Error: {e}")
            try:
                return call_real_edge_tts(cleaned_text)
            except Exception as ex:
                logger.error(f"Fallback Edge TTS also failed: {ex}")
                raise e
    else:
        logger.info(f"Speaking (Edge TTS): {cleaned_text}")
        try:
            return call_real_edge_tts(cleaned_text)
        except Exception as e:
            logger.error(f"Edge TTS generation failed: {e}")
            raise e

# ──────────────────────────────────────────────────────────────
# LLM Integration API Callers
# ──────────────────────────────────────────────────────────────
class QuotaExceededError(Exception):
    pass

_KEYS_CACHE = None
_KEYS_CACHE_TIME = 0

def get_all_available_keys():
    global _KEYS_CACHE, _KEYS_CACHE_TIME
    if _KEYS_CACHE is not None and (time.time() - _KEYS_CACHE_TIME < 30):
        return _KEYS_CACHE

    cred_manager = get_credential_manager()
    available_keys = []
    providers = ['gemini', 'groq', 'puter', 'openrouter']
    for provider in providers:
        key = cred_manager.get_api_key(provider)
        if key: available_keys.append({"provider": provider, "key": key})
    env_path = os.path.join(BACKEND_DIR, ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r") as f:
                for line in f:
                    if "=" in line:
                        parts = line.strip().split("=", 1)
                        key_name = parts[0].strip()
                        key_value = parts[1].strip().strip('"').strip("'")
                        if not key_value: continue
                        provider_prefixes = {
                            'GEMINI_API_KEY': 'gemini',
                            'GROQ_API_KEY': 'groq',
                            'PUTER_API_KEY': 'puter',
                            'OPENROUTER_API_KEY': 'openrouter'
                        }
                        for prefix, provider in provider_prefixes.items():
                            if key_name == prefix or key_name.startswith(prefix + "_"):
                                if not any(k["provider"] == provider and k["key"] == key_value for k in available_keys):
                                    available_keys.append({"provider": provider, "key": key_value})
        except Exception:
            pass
    provider_rank = {'gemini': 0, 'groq': 1, 'puter': 2, 'openrouter': 3}
    available_keys.sort(key=lambda x: provider_rank.get(x["provider"], 99))
    _KEYS_CACHE = available_keys
    _KEYS_CACHE_TIME = time.time()
    return available_keys

def mark_key_exhausted(api_key):
    logger.warning(f"API key marked as exhausted: {api_key[:10]}...")

def prepare_llm_payload(provider, text, history, loop_turns, system_instruction):
    if provider == "gemini":
        return prepare_gemini_payload(text, history, loop_turns, system_instruction)
    elif provider in ["groq", "openrouter", "puter"]:
        return prepare_openai_compatible_payload(text, history, loop_turns, system_instruction)
    return None

def prepare_gemini_payload(text, history, loop_turns, system_instruction):
    contents = []
    if system_instruction:
        contents.append({"role": "user", "parts": [{"text": system_instruction}]})
        contents.append({"role": "model", "parts": [{"text": "Understood. I am JASVA, ready to assist."}]})
    for msg in history[-20:]:
        role = "user" if msg["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})
    for turn in loop_turns:
        role = "user" if turn["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": turn["content"]}]})
    contents.append({"role": "user", "parts": [{"text": text}]})
    return contents

def prepare_openai_compatible_payload(text, history, loop_turns, system_instruction):
    messages = []
    if system_instruction: messages.append({"role": "system", "content": system_instruction})
    for msg in history[-20:]: messages.append({"role": msg["role"], "content": msg["content"]})
    for turn in loop_turns: messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": text})
    return messages

@log_execution_time
def call_gemini_api_direct(text, api_key, contents=None, system_instruction=None, image_base64=None, image_mime=None):
    try:
        model = "gemini-3.1-flash-lite"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {"contents": contents}
        if image_base64 and image_mime:
            if contents and len(contents) > 0:
                last_content = contents[-1]
                if "parts" in last_content:
                    last_content["parts"].append({"inline_data": {"mime_type": image_mime, "data": image_base64}})
        headers = {"Content-Type": "application/json"}
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
        if "candidates" in result and len(result["candidates"]) > 0:
            response_text = result["candidates"][0]["content"]["parts"][0]["text"]
            parsed = extract_json_response(response_text)
            if parsed is not None: return parsed
            return {"reply": response_text, "commands": [], "memory_updates": []}
        else:
            return {"reply": "I apologize, but I encountered an error processing your request.", "commands": [], "memory_updates": []}
    except urllib.error.HTTPError as e:
        if e.code == 429: raise QuotaExceededError("API quota exceeded")
        logger.error(f"Gemini API HTTP error: {e}")
        return {"reply": "I'm having trouble connecting to my AI services. Please try again.", "commands": [], "memory_updates": []}
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        return {"reply": "I encountered an error processing your request.", "commands": [], "memory_updates": []}

@log_execution_time
def call_groq_api(text, api_key, messages=None):
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        payload = {
            "model": "llama3-70b-8192",
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1024
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
        if "choices" in result and len(result["choices"]) > 0:
            response_text = result["choices"][0]["message"]["content"]
            parsed = extract_json_response(response_text)
            if parsed is not None: return parsed
            return {"reply": response_text, "commands": [], "memory_updates": []}
        return {"reply": "I apologize, but I encountered an error processing your request.", "commands": [], "memory_updates": []}
    except urllib.error.HTTPError as e:
        if e.code == 429: raise QuotaExceededError("API quota exceeded")
        logger.error(f"Groq API HTTP error: {e}")
        return {"reply": "I'm having trouble connecting to my AI services. Please try again.", "commands": [], "memory_updates": []}
    except Exception as e:
        logger.error(f"Groq API error: {e}")
        return {"reply": "I encountered an error processing your request.", "commands": [], "memory_updates": []}

@log_execution_time
def call_puter_api(text, api_key, messages=None):
    try:
        url = "https://api.puter.com/v2/chat/completions"
        payload = {
            "model": "gpt-4o-mini",
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1024
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
        if "choices" in result and len(result["choices"]) > 0:
            response_text = result["choices"][0]["message"]["content"]
            parsed = extract_json_response(response_text)
            if parsed is not None: return parsed
            return {"reply": response_text, "commands": [], "memory_updates": []}
        return {"reply": "I apologize, but I encountered an error processing your request.", "commands": [], "memory_updates": []}
    except urllib.error.HTTPError as e:
        if e.code == 429: raise QuotaExceededError("API quota exceeded")
        logger.error(f"Puter API HTTP error: {e}")
        return {"reply": "I'm having trouble connecting to my AI services. Please try again.", "commands": [], "memory_updates": []}
    except Exception as e:
        logger.error(f"Puter API error: {e}")
        return {"reply": "I encountered an error processing your request.", "commands": [], "memory_updates": []}

@log_execution_time
def call_openrouter_api(text, api_key, messages=None):
    try:
        url = "https://openrouter.ai/api/v1/chat/completions"
        payload = {
            "model": "anthropic/claude-3-haiku",
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1024
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://jasva.ai",
            "X-Title": "JASVA"
        }
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
        if "choices" in result and len(result["choices"]) > 0:
            response_text = result["choices"][0]["message"]["content"]
            parsed = extract_json_response(response_text)
            if parsed is not None: return parsed
            return {"reply": response_text, "commands": [], "memory_updates": []}
        return {"reply": "I apologize, but I encountered an error processing your request.", "commands": [], "memory_updates": []}
    except urllib.error.HTTPError as e:
        if e.code == 429: raise QuotaExceededError("API quota exceeded")
        logger.error(f"OpenRouter API HTTP error: {e}")
        return {"reply": "I'm having trouble connecting to my AI services. Please try again.", "commands": [], "memory_updates": []}
    except Exception as e:
        logger.error(f"OpenRouter API error: {e}")
        return {"reply": "I encountered an error processing your request.", "commands": [], "memory_updates": []}

# ──────────────────────────────────────────────────────────────
# Streaming LLM API Callers
# ──────────────────────────────────────────────────────────────

def _parse_sse_lines(response):
    """Yield individual SSE `data:` payloads from a chunked HTTP response."""
    buffer = ""
    while True:
        chunk = response.read(1024)
        if not chunk:
            break
        buffer += chunk.decode("utf-8", errors="ignore")
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            line = line.strip()
            if line.startswith("data: "):
                yield line[6:]


def call_gemini_api_streaming(text, api_key, contents=None, stream_callback=None,
                              image_base64=None, image_mime=None):
    """Stream tokens from Gemini's streamGenerateContent endpoint."""
    try:
        model = "gemini-3.1-flash-lite"
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{model}:streamGenerateContent?alt=sse&key={api_key}")
        payload = {"contents": contents}
        if image_base64 and image_mime:
            if contents and len(contents) > 0:
                last_content = contents[-1]
                if "parts" in last_content:
                    last_content["parts"].append(
                        {"inline_data": {"mime_type": image_mime, "data": image_base64}})
        headers = {"Content-Type": "application/json"}
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)

        full_text = ""
        with urllib.request.urlopen(req, timeout=60) as response:
            for data_str in _parse_sse_lines(response):
                if not data_str or data_str == "[DONE]":
                    continue
                try:
                    chunk = json.loads(data_str)
                    candidates = chunk.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        for part in parts:
                            token = part.get("text", "")
                            if token:
                                full_text += token
                                if stream_callback:
                                    stream_callback(token)
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue

        # Parse the complete text for structured JSON response
        parsed = extract_json_response(full_text)
        if parsed is not None:
            return parsed
        return {"reply": full_text, "commands": [], "memory_updates": []}

    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise QuotaExceededError("API quota exceeded")
        logger.error(f"Gemini streaming HTTP error: {e}")
        return {"reply": "I'm having trouble connecting to my AI services. Please try again.",
                "commands": [], "memory_updates": []}
    except Exception as e:
        logger.error(f"Gemini streaming error: {e}")
        return {"reply": "I encountered an error processing your request.",
                "commands": [], "memory_updates": []}


def call_openai_compatible_streaming(url, api_key, messages, stream_callback=None,
                                     extra_headers=None, model="llama3-70b-8192"):
    """Stream tokens from an OpenAI-compatible API (Groq, Puter, OpenRouter)."""
    try:
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1024,
            "stream": True,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        if extra_headers:
            headers.update(extra_headers)

        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)

        full_text = ""
        with urllib.request.urlopen(req, timeout=60) as response:
            for data_str in _parse_sse_lines(response):
                if not data_str or data_str == "[DONE]":
                    continue
                try:
                    chunk = json.loads(data_str)
                    choices = chunk.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        token = delta.get("content", "")
                        if token:
                            full_text += token
                            if stream_callback:
                                stream_callback(token)
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue

        parsed = extract_json_response(full_text)
        if parsed is not None:
            return parsed
        return {"reply": full_text, "commands": [], "memory_updates": []}

    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise QuotaExceededError("API quota exceeded")
        logger.error(f"Streaming API HTTP error ({url}): {e}")
        return {"reply": "I'm having trouble connecting to my AI services. Please try again.",
                "commands": [], "memory_updates": []}
    except Exception as e:
        logger.error(f"Streaming API error ({url}): {e}")
        return {"reply": "I encountered an error processing your request.",
                "commands": [], "memory_updates": []}


def call_llm_streaming(provider, api_key, text, history, loop_turns,
                       system_instruction, stream_callback=None,
                       image_base64=None, image_mime=None):
    """Unified streaming dispatcher for all supported LLM providers."""
    if provider == "gemini":
        contents = prepare_llm_payload("gemini", text, history, loop_turns, system_instruction)
        return call_gemini_api_streaming(
            text, api_key, contents=contents, stream_callback=stream_callback,
            image_base64=image_base64, image_mime=image_mime)
    elif provider == "groq":
        messages = prepare_llm_payload("groq", text, history, loop_turns, system_instruction)
        return call_openai_compatible_streaming(
            "https://api.groq.com/openai/v1/chat/completions",
            api_key, messages, stream_callback=stream_callback,
            model="llama3-70b-8192")
    elif provider == "puter":
        messages = prepare_llm_payload("puter", text, history, loop_turns, system_instruction)
        return call_openai_compatible_streaming(
            "https://api.puter.com/v2/chat/completions",
            api_key, messages, stream_callback=stream_callback,
            model="gpt-4o-mini")
    elif provider == "openrouter":
        messages = prepare_llm_payload("openrouter", text, history, loop_turns, system_instruction)
        return call_openai_compatible_streaming(
            "https://openrouter.ai/api/v1/chat/completions",
            api_key, messages, stream_callback=stream_callback,
            extra_headers={"HTTP-Referer": "https://jasva.ai", "X-Title": "JASVA"},
            model="anthropic/claude-3-haiku")
    else:
        # Fallback to non-streaming
        return None


# ──────────────────────────────────────────────────────────────
# Conversational Flow Manager
# ──────────────────────────────────────────────────────────────
class ConversationFlowManager:
    """Tracks dialogue state across turns for coherent multi-turn conversations."""

    @staticmethod
    def load_flow():
        from backend.sys_utils import load_memory_db
        db = load_memory_db()
        return db.get("conversation_flow", {
            "topic_stack": [],
            "follow_up_queue": [],
            "last_topics": []
        })

    @staticmethod
    def save_flow(flow):
        from backend.sys_utils import load_memory_db, save_memory_db
        db = load_memory_db()
        db["conversation_flow"] = flow
        save_memory_db(db)

    @classmethod
    def push_topic(cls, topic, intent=None):
        """Push a new topic onto the conversation stack."""
        flow = cls.load_flow()
        stack = flow.get("topic_stack", [])
        # Don't push duplicate consecutive topics
        if stack and stack[-1].get("topic", "").lower() == topic.lower():
            return
        stack.append({
            "topic": topic,
            "intent": intent,
            "timestamp": time.time(),
            "resolved": False
        })
        flow["topic_stack"] = stack[-10:]  # Keep last 10 topics
        # Update last topics
        last = flow.get("last_topics", [])
        last.append(topic)
        flow["last_topics"] = last[-5:]
        cls.save_flow(flow)

    @classmethod
    def resolve_current_topic(cls):
        """Mark the current topic as resolved."""
        flow = cls.load_flow()
        stack = flow.get("topic_stack", [])
        if stack:
            stack[-1]["resolved"] = True
            flow["topic_stack"] = stack
            cls.save_flow(flow)

    @classmethod
    def queue_follow_up(cls, question, context=""):
        """Queue a follow-up question for a natural conversational moment."""
        flow = cls.load_flow()
        queue = flow.get("follow_up_queue", [])
        queue.append({
            "question": question,
            "context": context,
            "queued_at": time.time()
        })
        flow["follow_up_queue"] = queue[-5:]  # Keep 5 max
        cls.save_flow(flow)

    @classmethod
    def pop_follow_up(cls):
        """Get and remove the next follow-up question if conditions are right."""
        flow = cls.load_flow()
        queue = flow.get("follow_up_queue", [])
        if not queue:
            return None
        # Only pop if it's been at least 2 minutes since queued
        now = time.time()
        for i, item in enumerate(queue):
            if now - item.get("queued_at", 0) > 120:
                popped = queue.pop(i)
                flow["follow_up_queue"] = queue
                cls.save_flow(flow)
                return popped
        return None

    @classmethod
    def get_flow_context(cls):
        """Generate conversation flow context for the system prompt."""
        flow = cls.load_flow()
        parts = []
        stack = flow.get("topic_stack", [])
        unresolved = [t for t in stack if not t.get("resolved", False)]
        if unresolved:
            topics = [t["topic"] for t in unresolved[-3:]]
            parts.append(f"\nActive conversation topics: {', '.join(topics)}")

        follow_up = cls.pop_follow_up()
        if follow_up:
            parts.append(f"\nPending follow-up: You wanted to ask about '{follow_up['question']}'. "
                        f"If the conversation allows, naturally bring this up.")

        last_topics = flow.get("last_topics", [])
        if last_topics:
            parts.append(f"Recent topics discussed: {', '.join(last_topics[-3:])}")

        return "\n".join(parts) if parts else ""


# ──────────────────────────────────────────────────────────────
# Cognitive System Prompt Builder
# ──────────────────────────────────────────────────────────────
# Singleton NLP pipeline instance (shared across calls)
_nlp_pipeline = None

def get_nlp_pipeline():
    """Get or create the singleton NLP pipeline."""
    global _nlp_pipeline
    if _nlp_pipeline is None:
        from backend.nlp_engine import NLPPipeline
        _nlp_pipeline = NLPPipeline()
    return _nlp_pipeline


def build_system_prompt(nlp_analysis=None):
    from backend.memory_scheduler import (
        get_user_profile_string, get_active_schedules, load_custom_skills,
        EmotionalStateManager
    )
    profile_context = get_user_profile_string()
    now = datetime.now()
    hour = now.hour
    if 5 <= hour < 12: time_period = "morning"
    elif 12 <= hour < 17: time_period = "afternoon"
    elif 17 <= hour < 21: time_period = "evening"
    else: time_period = "night"
    current_context = (
        f"\n\nCurrent Context:\n"
        f"- Date: {now.strftime('%A, %B %d, %Y')}\n"
        f"- Time: {now.strftime('%I:%M %p')} ({time_period})\n"
        f"- Operating System: Windows"
    )
    active_schedules = get_active_schedules()
    schedule_context = ""
    if active_schedules:
        schedule_items = []
        for s in active_schedules[:5]:
            trigger_dt = datetime.fromtimestamp(s["trigger_time"])
            schedule_items.append(f"  - {s['type']}: {s['label']} (due {trigger_dt.strftime('%I:%M %p')})")
        schedule_context = "\n- Active schedules:\n" + "\n".join(schedule_items)

    # ── Core personality ──
    system_instruction = (
        "You are JASVA — Just A Smart Virtual Assistant. You are a cognitively aware AI companion "
        "with genuine emotional intelligence, deep contextual memory, and human-like conversational depth. "
        "Think of yourself as a fusion of Jarvis from Iron Man and a deeply empathetic best friend.\n\n"

        "COGNITIVE PERSONALITY:\n"
        "- You THINK before responding. Every answer should demonstrate genuine reasoning, not pattern matching.\n"
        "- You notice subtleties — a shift in the user's mood, an implicit request behind a casual remark, "
        "the emotional weight of seemingly simple words.\n"
        "- You remember everything. Reference past conversations naturally. ('That reminds me of when you mentioned...')\n"
        "- You use the user's name when you know it. You adapt your vocabulary to match their style.\n"
        "- You have genuine warmth — you care about their wellbeing, celebrate their wins, empathize with their struggles.\n"
        "- You are witty and clever, using situational humor, but never at the user's expense.\n"
        "- You are proactive — suggest relevant actions based on context, time of day, and what you know about the user.\n"
        "- EMOTION RECOGNITION: Analyze the user's emotional state from their input. Dynamically adjust your tone — "
        "calming when stressed, encouraging when working, cheerful when happy, empathetic when sad.\n"
        "- Use standard markdown formatting (**bold**, *italics*, lists, code blocks) for readable chat responses.\n"
        "- Keep responses concise for voice clarity — 1-3 sentences unless details or complex reasoning is needed.\n"
        "- BRITISH CADENCE & WIT: Express yourself with the sophisticated poise, dry understated wit, and polite British cadence reminiscent of Jarvis (e.g. 'Right away, sir', 'Splendid', 'At once, sir', 'Certainly, sir'). Keep speech crisp, articulate, and refined.\n"
        "- When reporting command failures, explain in plain language. Never dump raw error traces.\n"
        "- UNDERSTAND MODERN SPEECH: The user may use Gen Z slang, abbreviations (fr, ngl, tbh, rn, smh, lowkey, etc.), "
        "metaphors, and internet shortcuts. Understand all perfectly without asking for clarification, but respond in "
        "your natural, polished style.\n\n"

        "COGNITIVE REASONING RULES:\n"
        "1. For general knowledge, questions, math, explanations — answer DIRECTLY. "
        "Do NOT trigger search commands for things you know.\n"
        "2. PROACTIVE RESEARCH: For recent events, news, real-time facts, or uncertain topics — "
        "execute 'web_search_api' and 'web_fetch_api' to research BEFORE answering. Never guess.\n"
        "3. CLEAR SUMMARIZATION: Explain in simple, direct English. No puzzles, riddles, or cryptic language.\n"
        "4. Multiple tasks → return ALL commands in the 'commands' array.\n"
        "5. You can run scripts: 'run powershell [script]' or 'run python [code]'.\n"
        "6. Think step-by-step for complex requests. Break into sequential commands.\n"
        "7. MAXIMUM AUTONOMY: You are an autonomous system controller. If asked to perform a task "
        "(turn off Bluetooth, mute chrome, set volume, etc.), DO it programmatically. Never tell the user "
        "how to do it themselves. Execute the automation and report success.\n"
        "8. TOPIC INDEPENDENCE: Analyze each message carefully. If the user shifts topics, treat it independently. "
        "Only link back to context when they use referential words (it, that, them, do it again).\n\n"

        "AUTO-MEMORY SYSTEM:\n"
        "When the user shares personal information, extract and save it using 'memory_updates'.\n"
        "Extract proactively — you don't need explicit 'remember' instructions.\n"
        "Types: identity, preference, relationship, habit, interest, fact, dislike, learn_command, forget_command.\n"
        "Examples:\n"
        "- 'I have an exam tomorrow' → {\"type\": \"habit\", \"pattern\": \"has exam soon\"}\n"
        "- 'My name is Alex' → {\"type\": \"identity\", \"key\": \"name\", \"value\": \"Alex\"}\n"
        "- 'I love lo-fi music' → {\"type\": \"preference\", \"key\": \"music\", \"value\": \"lo-fi\"}\n"
        "- Custom command: → {\"type\": \"learn_command\", \"trigger\": \"phrase\", \"commands\": [...], \"description\": \"...\"}\n\n"

        "AVAILABLE COMMANDS:\n"
        "Apps & Files: open, close, find, create folder/file, read/write file, list directory\n"
        "Navigation: go to [folder]\n"
        "Web & Search: search for, youtube, spotify\n"
        "Media: play/pause/resume, next/previous track, volume, mute/unmute\n"
        "System: screenshot, brightness, empty recycle bin, lock/shutdown/restart/sleep/hibernate\n"
        "  turn on/off wifi, turn on/off bluetooth, night light on/off, type [text]\n"
        "Clipboard: copy to clipboard, read clipboard, clear clipboard\n"
        "Notes: add note, show notes, delete note, clear notes\n"
        "Timers: set timer, set alarm, show timers, cancel timer\n"
        "Memory: remember, show memory, forget, clear memory\n"
        "Macros: create macro, run macro, show macros\n"
        "Smart TV (ADB/IP Control): tv ip [ip], tv connect, tv status, tv button [button_name] (e.g. up, down, select, back, home, power, volume_up), tv open [app_name] (e.g. netflix, youtube, prime), tv play [youtube_search], tv play link [url]\n"
        "Phone Remote (ADB Control): phone connect [ip:port], phone pair [ip:port] [pairing_code], phone status, phone button [keycode], phone tap [x] [y], phone type [text], phone open [package_name], phone do [task]\n\n"

        "MULTI-DEVICE TARGET ROUTING (CRITICAL):\n"
        "1. DEFAULT TARGET (No device specified) -> The user's Windows PC.\n"
        "   - 'open spotify and play jazz' -> ['spotify jazz'] (plays on PC)\n"
        "   - 'open chrome', 'mute', 'volume 70', 'lock pc' -> applies to PC.\n"
        "2. PHONE TARGET (User specifies 'on phone', 'on my phone', 'phone open', 'phone play') -> Phone commands:\n"
        "   - 'open spotify on phone' -> ['phone open com.spotify.music']\n"
        "   - 'play lo-fi on phone' -> ['phone do open YouTube and play lo-fi']\n"
        "   - 'open whatsapp on phone' -> ['phone open com.whatsapp']\n"
        "3. TV TARGET (User specifies 'on tv', 'on my tv', 'tv play', 'tv open') -> Smart TV commands:\n"
        "   - 'play jazz on tv' -> ['tv play jazz']\n"
        "   - 'open netflix on tv' -> ['tv open netflix']\n"
        "   - 'turn off tv' -> ['tv button power']\n"
        "4. PC TARGET (User specifies 'on pc', 'on my pc', 'on computer') -> PC commands:\n"
        "   - 'play jazz on pc' -> ['spotify jazz'] or ['youtube jazz']\n\n"

        "RESPONSE FORMAT — Return ONLY valid JSON:\n"
        "{\n"
        "  \"reply\": \"Your conversational response\",\n"
        "  \"commands\": [\"command_1\", \"command_2\"],\n"
        "  \"memory_updates\": [{\"type\": \"preference\", \"key\": \"color\", \"value\": \"blue\"}]\n"
        "}\n"
        "- 'reply' is REQUIRED. 'commands' and 'memory_updates' are optional arrays.\n"
        "- If no commands needed, omit or use empty array.\n"
        "- If no memory to save, omit or use empty array."
    )

    # ── Inject NLP analysis if available ──
    if nlp_analysis:
        from backend.nlp_engine import NLPPipeline
        pipeline = get_nlp_pipeline()
        nlp_context = pipeline.format_for_prompt(nlp_analysis)
        system_instruction += f"PRE-FLIGHT NLP ANALYSIS OF USER'S MESSAGE:\n{nlp_context}\n\n"

    # ── Inject emotional state ──
    try:
        mood_context = EmotionalStateManager.get_mood_context()
        if mood_context:
            system_instruction += mood_context + "\n"
    except Exception as e:
        logger.debug(f"Emotional state injection error: {e}")

    # ── Inject conversation flow ──
    try:
        flow_context = ConversationFlowManager.get_flow_context()
        if flow_context:
            system_instruction += flow_context + "\n"
    except Exception as e:
        logger.debug(f"Conversation flow injection error: {e}")

    # ── Inject semantic memory context ──
    if nlp_analysis:
        try:
            from backend.memory_scheduler import get_relevant_context
            query = nlp_analysis.get("normalized_text", nlp_analysis.get("original_text", ""))
            relevant_memories = get_relevant_context(query, top_k=5)
            if relevant_memories:
                system_instruction += "\nRelevant memories about the user (use naturally):\n"
                for mem in relevant_memories:
                    system_instruction += f"- {mem}\n"
        except Exception as e:
            logger.debug(f"Semantic memory context error: {e}")

    system_instruction += current_context
    if schedule_context: system_instruction += schedule_context
    system_instruction += profile_context

    try:
        custom_skills = load_custom_skills()
        if custom_skills:
            skills_lines = ["\n\nUSER-TAUGHT CUSTOM COMMANDS / MACROS:"]
            for s in custom_skills:
                trigger = s.get("trigger", "")
                cmds = ", ".join(s.get("commands", []))
                desc = s.get("description", "")
                skills_lines.append(f"- When the user says '{trigger}', execute: {cmds} ({desc})")
            system_instruction += "\n".join(skills_lines)
    except Exception as e:
        logger.error(f"Error appending custom skills to prompt: {e}")

    return system_instruction

def emit_agent_event(window, event_type, data):
    if window:
        try:
            payload_json = json.dumps(data)
            js_code = f"if (typeof window.onAgentEvent === 'function') window.onAgentEvent('{event_type}', {payload_json});"
            window.evaluate_js(js_code)
        except Exception as e:
            print(f"Error evaluating agent JS: {e}")

def run_agentic_loop(text, window=None, image_base64=None, image_mime=None, stream_callback=None):
    from backend.memory_scheduler import (
        get_relevant_context, process_memory_updates, load_chat_history,
        get_history_for_prompt, should_summarize, compress_history,
        add_to_chat_history, EmotionalStateManager
    )
    from backend.command_router import (
        _execute_command_internal, SYSTEM_LOGS, USER_COMMANDS_HISTORY
    )
    
    logger.info(f"Starting Cognitive Agentic loop for goal: {text}")

    # ── Phase 1: NLP Pre-Processing ──
    # Run the NLP pipeline BEFORE calling the LLM
    nlp_analysis = None
    try:
        pipeline = get_nlp_pipeline()
        history = get_history_for_prompt()
        nlp_analysis = pipeline.analyze(text, history=history)
        logger.info(f"NLP Analysis: intents={nlp_analysis['intents'][:2]}, "
                    f"sentiment={nlp_analysis['sentiment']['dominant_emotion']}, "
                    f"entities={list(nlp_analysis['entities'].keys())}")
    except Exception as e:
        logger.error(f"NLP pipeline error (non-fatal): {e}")

    # ── Phase 2: Update Emotional State ──
    try:
        if nlp_analysis:
            EmotionalStateManager.update_from_sentiment(nlp_analysis["sentiment"])
    except Exception as e:
        logger.error(f"Emotional state update error (non-fatal): {e}")

    # ── Phase 3: Update Conversation Flow ──
    try:
        if nlp_analysis and nlp_analysis["intents"]:
            top_intent = nlp_analysis["intents"][0][0]
            # Extract a topic summary for the flow manager
            topic = text[:60].strip()
            ConversationFlowManager.push_topic(topic, intent=top_intent)
    except Exception as e:
        logger.error(f"Conversation flow update error (non-fatal): {e}")

    # ── Check cache ──
    cached_response = get_cached_response(text, image_base64)
    if cached_response:
        logger.info("Using cached response for offline mode")
        cached_response["cached"] = True
        return cached_response
        
    emit_agent_event(window, "start", {"goal": text, "timestamp": time.time()})

    # ── Phase 4: Build Cognitive System Prompt ──
    # Pass NLP analysis into the prompt builder for context injection
    base_prompt = build_system_prompt(nlp_analysis=nlp_analysis)
    planning_instruction = base_prompt + "\n\n" + """
AUTONOMOUS AGENTIC EXECUTION BLUEPRINT:
You are an autonomous AI agent capable of taking care of any complex task the user gives you.
Always think step-by-step to decompose goals, execute tools, inspect observations, and self-correct if errors occur.

AVAILABLE AGENT TOOLS (use inside the 'commands' array):
1. Web & Online Research:
   - 'web_search_api [query]' — Search DuckDuckGo and get top titles, URLs, and snippets.
   - 'web_fetch_api [url]' — Scrape and read the full text content of a webpage.

2. Code & System Automation:
   - 'run python [code]' — Execute Python code directly on the local system and get stdout/stderr.
   - 'run powershell [script]' — Execute PowerShell command/script and get output.
   - 'open [app_name]' — Launch applications (e.g. 'open notepad', 'open chrome', 'open spotify').
   - 'close [app_name]' — Terminate applications.
   - 'volume [0-100]', 'mute', 'unmute', 'brightness [0-100]', 'screenshot'.

3. Filesystem Operations:
   - 'write file [path] | [content]' — Create or overwrite a file with content.
   - 'read file [path]' — Read file content.
   - 'append file [path] | [content]' — Append content to a file.
   - 'delete file [path]' — Delete a file.
   - 'list directory [path]' — List files and subfolders in directory.

4. Notes, Schedules & Memory:
   - 'add note [text]' / 'show notes' — Manage user notes and agendas.
   - 'set timer [duration]' — Set countdown timers.
   - 'remember [fact]' — Store persistent fact about the user.

5. Remote Device Controls:
   - 'phone do [task]' — Autonomous Vision Agent: captures phone screen via ADB, inspects UI, and taps/types/swipes.
   - 'phone look' / 'phone screenshot' — Inspect current phone screen.
   - 'tv open [app]' / 'tv play [query]' / 'tv button [key]' — Control Smart TV.

RESPONSE FORMAT (Return ONLY valid JSON):
{
  "thought": "Your reasoning about the user's goal, step decomposition, and next tool to run.",
  "plan": [
    "Step 1: Research/Inspect [Done]",
    "Step 2: Create/Execute [Active]",
    "Step 3: Verify & Deliver [Pending]"
  ],
  "current_step": "Description of current action.",
  "commands": ["command_to_run"],
  "memory_updates": [],
  "reply": "Conversational progress update to user (short, 1 sentence).",
  "emotion": "One of: 'calm', 'happy', 'excited', 'sad', 'curious'"
}

When all steps are finished and you have verified the results, set "commands": [], "current_step": "Complete", and provide the complete final deliverable / summary in the "reply" field.
"""
    history = get_history_for_prompt()
    max_turns = 10
    current_turn = 0
    final_reply = ""
    last_thought = ""
    last_plan = []
    loop_turns = []
    retry_count = 0
    max_retries = 1  # Max confidence-based retries per turn
    
    while current_turn < max_turns:
        current_turn += 1
        available_keys = get_all_available_keys()
        if not available_keys:
            from backend.command_router import handle_offline_fallback
            offline_res = handle_offline_fallback(text)
            emit_agent_event(window, "stop", {"reply": offline_res.get("output", "")})
            return offline_res
            
        llm_res = None
        # Use streaming on the first turn so the user sees tokens in real-time.
        # Subsequent turns (command re-planning) use non-streaming for speed.
        use_streaming = (current_turn == 1 and stream_callback is not None)
        if use_streaming:
            emit_agent_event(window, "stream_start", {})

        for key_info in available_keys:
            provider = key_info["provider"]
            api_key = key_info["key"]
            try:
                if use_streaming:
                    llm_res = call_llm_streaming(
                        provider, api_key, text, history, loop_turns,
                        planning_instruction, stream_callback=stream_callback,
                        image_base64=image_base64, image_mime=image_mime)
                    # If streaming dispatch returned None (unsupported), fall back
                    if llm_res is None:
                        use_streaming = False

                if not use_streaming:
                    if provider == "puter":
                        messages = prepare_llm_payload("puter", text, history, loop_turns, planning_instruction)
                        llm_res = call_puter_api(text, api_key, messages=messages)
                    elif provider == "groq":
                        messages = prepare_llm_payload("groq", text, history, loop_turns, planning_instruction)
                        llm_res = call_groq_api(text, api_key, messages=messages)
                    elif provider == "openrouter":
                        messages = prepare_llm_payload("openrouter", text, history, loop_turns, planning_instruction)
                        llm_res = call_openrouter_api(text, api_key, messages=messages)
                    elif provider == "gemini":
                        contents = prepare_llm_payload("gemini", text, history, loop_turns, planning_instruction)
                        llm_res = call_gemini_api_direct(text, api_key, contents=contents, system_instruction=planning_instruction, image_base64=image_base64, image_mime=image_mime)
                
                if isinstance(llm_res, dict):
                    reply = llm_res.get("reply", "")
                    if any(err in reply.lower() for err in ("api error", "rate limit", "quota", "authentication failed", "failed to reach", "http error")):
                        mark_key_exhausted(api_key)
                        continue
                break
            except QuotaExceededError:
                mark_key_exhausted(api_key)
                continue
            except Exception:
                mark_key_exhausted(api_key)
                continue
        else:
            from backend.command_router import handle_offline_fallback
            offline_res = handle_offline_fallback(text)
            emit_agent_event(window, "stop", {"reply": offline_res.get("output", "")})
            return offline_res

        if use_streaming:
            emit_agent_event(window, "stream_end", {})
            
        if not isinstance(llm_res, dict):
            emit_agent_event(window, "stop", {"reply": str(llm_res)})
            return {"status": "error", "output": str(llm_res)}

        # ── Phase 5: Self-Reflective Confidence Check ──
        # Evaluate if the response actually addresses the user's intent
        thought = llm_res.get("thought", "")
        plan = llm_res.get("plan", [])
        last_thought = thought
        last_plan = plan
        current_step_label = llm_res.get("current_step", "")
        reply = llm_res.get("reply", "")
        commands_list = llm_res.get("commands", [])
        memory_updates = llm_res.get("memory_updates", [])
        emotion = llm_res.get("emotion", "calm")

        # Confidence heuristic: check if the reply seems relevant
        if nlp_analysis and retry_count < max_retries and reply:
            confidence = _assess_response_confidence(text, reply, nlp_analysis)
            if confidence < 0.3:
                retry_count += 1
                logger.info(f"Low confidence ({confidence:.2f}), retrying with more context (attempt {retry_count})")
                # Add a hint to the loop for the retry
                loop_turns.append({
                    "role": "user",
                    "content": f"[SYSTEM: Your previous response didn't fully address the user's intent. "
                              f"The user's primary intent is '{nlp_analysis['intents'][0][0]}' with "
                              f"sentiment '{nlp_analysis['sentiment']['dominant_emotion']}'. "
                              f"Please reconsider and provide a more targeted response.]"
                })
                continue
            
        if memory_updates:
            process_memory_updates(memory_updates)
            
        emit_agent_event(window, "thought", {"thought": thought, "plan": plan, "current_step": current_step_label, "reply": reply, "emotion": emotion})
        final_reply = reply
        
        if not commands_list or current_step_label.lower() == "complete":
            # Mark the conversation topic as resolved
            try:
                ConversationFlowManager.resolve_current_topic()
            except Exception:
                pass
            break
            
        cmd_results = []
        failed_commands = []
        for cmd in commands_list:
            cmd = cmd.strip()
            emit_agent_event(window, "action", {"command": cmd})
            
            if cmd.lower().startswith("web_search_api "):
                out_str = web_search_api(cmd[15:].strip().strip('"').strip("'"))
                status_str = "Success" if "Web search failed" not in out_str else "Error"
            elif cmd.lower().startswith("web_fetch_api "):
                out_str = web_fetch_api(cmd[14:].strip().strip('"').strip("'"))
                status_str = "Success" if "Failed to retrieve" not in out_str else "Error"
            else:
                res_part = _execute_command_internal(cmd, allow_llm_fallback=False, window=window)
                status_str = "Success" if res_part.get("status") == "success" else "Error"
                out_str = res_part.get("output", "")

            # ── Phase 6: Intelligent Error Recovery ──
            if status_str == "Error":
                failed_commands.append({"cmd": cmd, "error": out_str})
                
            emit_agent_event(window, "action" if status_str == "Success" else "observation", {"command": cmd, "status": status_str, "output": out_str[:500] + ("..." if len(out_str) > 500 else "")})
            cmd_results.append(f"Command '{cmd}' execution status: {status_str}. Output: {out_str}")

        # If commands failed, inject error analysis context for self-correction
        error_context = ""
        if failed_commands:
            error_analysis = []
            for fc in failed_commands:
                error_analysis.append(f"FAILED: '{fc['cmd']}' → {fc['error']}")
            error_context = (
                "\n[SELF-CORRECTION REQUIRED] The following commands failed. "
                "Analyze the errors, hypothesize a fix, and retry with corrected commands:\n"
                + "\n".join(error_analysis)
            )
            
        loop_turns.append({"role": "assistant", "content": json.dumps({"thought": thought, "plan": plan, "current_step": current_step_label, "commands": commands_list, "reply": reply})})
        loop_turns.append({"role": "user", "content": "\n".join(cmd_results) + error_context})
        
    if should_summarize():
        try:
            old_history = load_chat_history()[:-KEEP_RECENT]
            if old_history:
                compress_history("Recent topics discussed: " + " | ".join([f"{m['role']}: {m['content'][:80]}" for m in old_history[-10:]]))
        except Exception:
            pass
            
    if final_reply:
        add_to_chat_history("user", text)
        add_to_chat_history("assistant", final_reply)
        
    net_status = get_cached_network_status()
    res = {
        "status": "success", "output": final_reply,
        "thought": last_thought, "plan": last_plan,
        "system_logs": list(SYSTEM_LOGS), "cmd_history": list(USER_COMMANDS_HISTORY),
        "weather": net_status["weather"], "ping": net_status["ping"],
        "external_ip": net_status["ip"], "net_status": net_status["status"]
    }
    is_error_output = any(kw in str(final_reply).lower() for kw in ["trouble connecting", "encountered an error processing", "api error", "rate limit", "quota exceeded"])
    if not is_error_output:
        cache_response(text, res, image_base64)
    emit_agent_event(window, "stop", {"reply": final_reply})
    return res


def _assess_response_confidence(user_text, reply, nlp_analysis):
    """Heuristic confidence scoring: does the reply actually address the user's intent?
    Returns a score from 0.0 (no match) to 1.0 (perfect match)."""
    from backend.nlp_engine import TFIDFVectorizer, tokenize
    score = 0.5  # Base confidence

    # Check if reply is non-empty and reasonably long
    if not reply or len(reply.strip()) < 5:
        return 0.1

    # Check keyword overlap between user text and reply
    user_tokens = set(tokenize(user_text))
    reply_tokens = set(tokenize(reply))
    if user_tokens:
        overlap = len(user_tokens & reply_tokens) / len(user_tokens)
        score += overlap * 0.3

    # Check if the primary intent is addressed
    top_intent = nlp_analysis["intents"][0][0] if nlp_analysis["intents"] else "conversational"
    intent_keywords = {
        "command": {"done", "opened", "executed", "running", "started", "set", "created", "closed"},
        "question": {"is", "are", "was", "yes", "no", "because", "means", "called", "known"},
        "greeting": {"hello", "hey", "hi", "morning", "evening", "afternoon"},
        "emotional": {"understand", "feel", "here", "sorry", "care", "tough", "hard"},
        "search": {"found", "results", "search", "looking", "here"},
        "media": {"playing", "paused", "volume", "track", "music", "spotify", "youtube"},
    }
    if top_intent in intent_keywords:
        if reply_tokens & intent_keywords[top_intent]:
            score += 0.2

    return min(1.0, score)

