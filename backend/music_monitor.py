import subprocess
import json
import base64
import threading
import time
import io
from typing import Optional, Callable

# ─── Persistent PowerShell script for Windows Media Control ───
# Launched ONCE (hidden), loops forever, writes one JSON line to stdout every
# poll. Python reads lines from the pipe — no more spawning a process each poll.
PERSISTENT_PS_SCRIPT = r'''
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager, Windows.Media.Control, ContentType=WindowsRuntime]
$mgrType = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager]

# Discover WinRT types via reflection (type literals fail to resolve at
# parse-time inside loop/function bodies; reflection avoids them entirely).
$sessionType = $mgrType.GetMethod('GetSessions').ReturnType.GetGenericArguments()[0]
$propsType = $sessionType.GetMethod('TryGetMediaPropertiesAsync').ReturnType.GetGenericArguments()[0]
$streamType = $propsType.GetProperty('Thumbnail').PropertyType.GetMethod('OpenReadAsync').ReturnType.GetGenericArguments()[0]
$rasType = [System.IO.WindowsRuntimeStreamExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsStream' -and $_.GetParameters()[0].ParameterType.FullName -eq 'Windows.Storage.Streams.IRandomAccessStream'
} | Select-Object -First 1

$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and
    $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name.StartsWith('IAsyncOperation')
})[0]

function AwaitWinRT($WinRtTask, $ResultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    $netTask.Result
}

function Write-Line($obj) {
    try {
        $json = $obj | ConvertTo-Json -Compress
        [Console]::Out.WriteLine($json)
        [Console]::Out.Flush()
    } catch {}
}

function Get-ActiveSession($mgr) {
    $sessionList = @()
    foreach ($sess in $mgr.GetSessions()) {
        $sessionList += $sess
    }
    if ($sessionList.Count -eq 0) { return $null }

    # 1. Look for a session that is Playing AND has a valid title
    foreach ($sess in $sessionList) {
        try {
            $pb = $sess.GetPlaybackInfo()
            if ($pb -and $pb.PlaybackStatus.ToString() -eq 'Playing') {
                $p = AwaitWinRT ($sess.TryGetMediaPropertiesAsync()) $propsType
                if ($p -and $p.Title) { return $sess }
            }
        } catch {}
    }

    # 2. Look for any session that is currently Playing
    foreach ($sess in $sessionList) {
        try {
            $pb = $sess.GetPlaybackInfo()
            if ($pb -and $pb.PlaybackStatus.ToString() -eq 'Playing') {
                return $sess
            }
        } catch {}
    }

    # 3. Look for any session with a valid Title (paused)
    foreach ($sess in $sessionList) {
        try {
            $p = AwaitWinRT ($sess.TryGetMediaPropertiesAsync()) $propsType
            if ($p -and $p.Title) { return $sess }
        } catch {}
    }

    # 4. Fallback to current session or first
    try {
        $curr = $mgr.GetCurrentSession()
        if ($curr) { return $curr }
    } catch {}
    return $sessionList[0]
}

# Only re-read the (potentially large) thumbnail when the track changes.
$lastKey = ""
$lastThumb = ""

function Get-MediaJson {
    $mgr = AwaitWinRT ($mgrType::RequestAsync()) $mgrType
    $s = Get-ActiveSession $mgr

    if ($null -eq $s) {
        return [PSCustomObject]@{ status = "none" }
    }

    $props = AwaitWinRT ($s.TryGetMediaPropertiesAsync()) $propsType
    $playback = $s.GetPlaybackInfo()
    $timeline = $s.GetTimelineProperties()

    $appId  = if ($s.SourceAppId) { $s.SourceAppId } else { "" }
    $title  = if ($props.Title) { $props.Title } else { "" }
    $artist = if ($props.Artist) { $props.Artist } else { "" }
    $album  = if ($props.AlbumTitle) { $props.AlbumTitle } else { "" }

    if (-not $title -and $appId) {
        $cleanApp = ($appId -split '\\')[-1] -replace '\.exe$', ''
        $title = "$cleanApp Audio"
    }

    $key = "$title|$artist|$album"
    if ($key -ne $script:lastKey) {
        $script:lastKey = $key
        $script:lastThumb = ""
        if ($props.Thumbnail) {
            try {
                $stream = AwaitWinRT ($props.Thumbnail.OpenReadAsync()) $streamType
                $netStream = $rasType.Invoke($null, @($stream))
                $ms = [System.IO.MemoryStream]::new()
                $netStream.CopyTo($ms)
                $script:lastThumb = [Convert]::ToBase64String($ms.ToArray())
            } catch {}
        }
    }

    $posTicks = if ($timeline.Position) { $timeline.Position.Ticks } else { 0 }
    $durTicks = if ($timeline.EndTime) { $timeline.EndTime.Ticks } else { 0 }

    $pbStatus = if ($playback -and $playback.PlaybackStatus) { $playback.PlaybackStatus.ToString() } else { "Paused" }

    if ($pbStatus -eq "Playing" -and $timeline) {
        $now = [DateTimeOffset]::UtcNow
        $delta = $now - $timeline.LastUpdatedTime
        if ($delta.TotalMilliseconds -gt 0 -and $delta.TotalMilliseconds -lt 86400000) {
            $posTicks = $posTicks + $delta.Ticks
            if ($durTicks -gt 0 -and $posTicks -gt $durTicks) {
                $posTicks = $durTicks
            }
        }
    }

    $posMs = [long]($posTicks / 10000)
    $durMs = [long]($durTicks / 10000)

    return [PSCustomObject]@{
        status    = "ok"
        title     = $title
        artist    = $artist
        album     = $album
        playback  = $pbStatus
        position  = $posMs
        duration  = $durMs
        thumbnail = $script:lastThumb
    }
}

while ($true) {
    try {
        Write-Line (Get-MediaJson)
    } catch {
        $msg = $_.Exception.Message -replace "`n", " " -replace '"', "'"
        Write-Line ([PSCustomObject]@{ status = "error"; message = $msg })
    }
    Start-Sleep -Milliseconds 2000
}
'''.strip()

# One-shot variant: same helpers, but runs a single query instead of looping.
ONE_SHOT_PS_SCRIPT = PERSISTENT_PS_SCRIPT.split('while ($true) {')[0].strip() + "\nWrite-Line (Get-MediaJson)\n"

# Playback control (toggle play/pause, next, prev). Run one-shot, hidden.
CONTROL_PS_SCRIPT = r'''
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager, Windows.Media.Control, ContentType=WindowsRuntime]
$mgrType = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager]
$sessionType = $mgrType.GetMethod('GetSessions').ReturnType.GetGenericArguments()[0]
$propsType = $sessionType.GetMethod('TryGetMediaPropertiesAsync').ReturnType.GetGenericArguments()[0]

$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and
    $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name.StartsWith('IAsyncOperation')
})[0]

function AwaitWinRT($WinRtTask, $ResultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    $netTask.Result
}

function Get-ActiveSession($mgr) {
    $sessionList = @()
    foreach ($sess in $mgr.GetSessions()) {
        $sessionList += $sess
    }
    if ($sessionList.Count -eq 0) { return $null }

    foreach ($sess in $sessionList) {
        try {
            $pb = $sess.GetPlaybackInfo()
            if ($pb -and $pb.PlaybackStatus.ToString() -eq 'Playing') {
                $p = AwaitWinRT ($sess.TryGetMediaPropertiesAsync()) $propsType
                if ($p -and $p.Title) { return $sess }
            }
        } catch {}
    }

    foreach ($sess in $sessionList) {
        try {
            $pb = $sess.GetPlaybackInfo()
            if ($pb -and $pb.PlaybackStatus.ToString() -eq 'Playing') {
                return $sess
            }
        } catch {}
    }

    foreach ($sess in $sessionList) {
        try {
            $p = AwaitWinRT ($sess.TryGetMediaPropertiesAsync()) $propsType
            if ($p -and $p.Title) { return $sess }
        } catch {}
    }

    try {
        $curr = $mgr.GetCurrentSession()
        if ($curr) { return $curr }
    } catch {}
    return $sessionList[0]
}

$mgr = AwaitWinRT ($mgrType::RequestAsync()) $mgrType
$s = Get-ActiveSession $mgr
if ($null -eq $s) {
    Write-Output '{"status":"none"}'
} else {
    switch ($env:JASVA_MEDIA_ACTION) {
        "toggle" { $op = $s.TryTogglePlayPauseAsync() }
        "play"   { $op = $s.TryPlayAsync() }
        "pause"  { $op = $s.TryPauseAsync() }
        "next"   { $op = $s.TrySkipNextAsync() }
        "prev"   { $op = $s.TrySkipPreviousAsync() }
        "seek"   {
            $posMs = [long]$env:JASVA_MEDIA_POS
            $ticks = $posMs * 10000
            $op = $s.TryChangePlaybackPositionAsync($ticks)
        }
        default  { Write-Output '{"status":"error","message":"bad action"}'; exit }
    }
    $null = AwaitWinRT $op ([bool])
    Write-Output '{"status":"ok"}'
}
'''.strip()


def _encode_ps(script: str) -> str:
    return base64.b64encode(script.encode('utf-16-le')).decode('ascii')


def _hidden_startupinfo():
    """Suppress the console window of child processes."""
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0  # SW_HIDE
    return si


def query_media_once() -> dict:
    """One-shot media query (used as fallback / initial check)."""
    try:
        result = subprocess.run(
            ['powershell', '-NoProfile', '-NonInteractive', '-EncodedCommand', _encode_ps(ONE_SHOT_PS_SCRIPT)],
            capture_output=True, text=True, timeout=8, encoding='utf-8', errors='replace',
            startupinfo=_hidden_startupinfo(),
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        stdout = result.stdout.strip()
        if stdout:
            for line in stdout.splitlines():
                line = line.strip()
                if line.startswith('{'):
                    return json.loads(line)
    except Exception:
        pass
    return {"status": "error"}


def control_playback(action: str, position_ms: Optional[int] = None) -> dict:
    """Toggle play/pause, skip next, skip previous, or seek position via Windows SMTC."""
    try:
        import os
        env = dict(os.environ)
        env["JASVA_MEDIA_ACTION"] = action
        if position_ms is not None:
            env["JASVA_MEDIA_POS"] = str(int(position_ms))
            try:
                if isinstance(music_monitor._last_data, dict):
                    music_monitor._last_data["position"] = int(position_ms)
                music_monitor._current_position = int(position_ms)
            except Exception:
                pass
        result = subprocess.run(
            ['powershell', '-NoProfile', '-NonInteractive', '-EncodedCommand', _encode_ps(CONTROL_PS_SCRIPT)],
            capture_output=True, text=True, timeout=8, encoding='utf-8', errors='replace',
            startupinfo=_hidden_startupinfo(),
            creationflags=subprocess.CREATE_NO_WINDOW,
            env=env
        )
        stdout = result.stdout.strip()
        if stdout:
            for line in stdout.splitlines():
                line = line.strip()
                if line.startswith('{'):
                    return json.loads(line)
    except Exception:
        pass
    return {"status": "error"}


def extract_colors_from_base64(b64_data: str, num_colors: int = 3) -> list:
    """Extract dominant colors from base64 image data using Pillow."""
    try:
        from PIL import Image
        img_bytes = base64.b64decode(b64_data)
        img = Image.open(io.BytesIO(img_bytes)).convert('RGB')
        img = img.resize((50, 50))
        pixels = list(img.getdata())

        from collections import Counter
        color_counts = Counter(pixels)
        dominant = [c for c, _ in color_counts.most_common(num_colors)]

        while len(dominant) < num_colors:
            dominant.append((30, 15, 40))

        return dominant
    except Exception:
        return [(30, 15, 40), (60, 20, 60), (20, 10, 30)]


def rgb_to_css(colors: list) -> str:
    """Convert RGB tuples to a CSS gradient string."""
    if not colors:
        return "linear-gradient(135deg, #1a0a2e 0%, #0d0518 50%, #0a0310 100%)"
    stops = []
    for i, (r, g, b) in enumerate(colors):
        pct = int((i / max(len(colors) - 1, 1)) * 100)
        stops.append(f"rgb({r},{g},{b}) {pct}%")
    return f"linear-gradient(135deg, {', '.join(stops)})"


class MusicMonitor:
    """Runs ONE hidden PowerShell process and reads media info from its pipe."""

    def __init__(self, on_update: Optional[Callable] = None, poll_interval: float = 2.0):
        self.on_update = on_update
        self.poll_interval = poll_interval
        self._proc = None
        self._reader_thread = None
        self._running = False
        self._last_data = {}
        self._lyrics_cache = {}
        self._is_playing = False
        self._current_position = 0
        self._current_duration = 0

    def start(self):
        if self._running:
            return
        self._running = True
        threading.Thread(target=self._spawn_and_read, daemon=True).start()

    def stop(self):
        self._running = False
        if self._proc:
            try:
                self._proc.terminate()
            except Exception:
                pass
            try:
                self._proc.kill()
            except Exception:
                pass
            self._proc = None

    def _spawn(self):
        """Launch the single hidden PowerShell process."""
        return subprocess.Popen(
            ['powershell', '-NoProfile', '-NonInteractive', '-EncodedCommand', _encode_ps(PERSISTENT_PS_SCRIPT)],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            encoding='utf-8',
            errors='replace',
            startupinfo=_hidden_startupinfo(),
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

    def _spawn_and_read(self):
        """Start the process, read lines, restart it if it dies (rate-limited)."""
        while self._running:
            try:
                proc = self._spawn()
                self._proc = proc
            except Exception:
                time.sleep(3)
                continue

            try:
                for raw in proc.stdout:
                    line = raw.strip()
                    if not line.startswith('{'):
                        continue
                    try:
                        data = json.loads(line)
                    except Exception:
                        continue
                    self._handle_data(data)
            except Exception:
                pass

            # Process died or pipe closed; wait before restarting (avoid popup storms)
            time.sleep(3)

    def _handle_data(self, data):
        if not data:
            return
        if data.get('status') == 'none':
            self._last_data = {"status": "none", "title": "", "artist": "", "album": "", "playback": "Paused", "position": 0, "duration": 0, "thumbnail": ""}
            self._is_playing = False
            self._current_position = 0
            self._current_duration = 0
            return
        if data.get('status') == 'error':
            return

        # Track playback state for the frontend's own smooth ticker.
        self._is_playing = data.get('playback', '').lower() == 'playing'
        self._current_position = data.get('position', 0)
        self._current_duration = data.get('duration', 0)
        self._last_data = data

        if self.on_update:
            try:
                self.on_update(data)
            except Exception:
                pass

    def fetch_lyrics(self, title: str, artist: str) -> list:
        """Fetch synced lyrics from LRCLIB API."""
        cache_key = f"{title}|{artist}"
        if cache_key in self._lyrics_cache:
            return self._lyrics_cache[cache_key]

        try:
            import requests
            resp = requests.get(
                "https://lrclib.net/api/get",
                params={"track_name": title, "artist_name": artist},
                headers={"User-Agent": "JASVA/4.2"},
                timeout=5
            )
            if resp.status_code == 200:
                data = resp.json()
                synced = data.get('syncedLyrics', '')
                if synced:
                    lyrics = []
                    for line in synced.split('\n'):
                        if '] ' in line:
                            time_str, text = line.split('] ', 1)
                            time_str = time_str.strip('[')
                            parts = time_str.split(':')
                            if len(parts) == 2:
                                mins, secs = parts
                                ms = int(float(mins) * 60 * 1000 + float(secs) * 1000)
                                lyrics.append({"time": ms, "text": text})
                    self._lyrics_cache[cache_key] = lyrics
                    return lyrics
        except Exception:
            pass

        self._lyrics_cache[cache_key] = []
        return []

    def get_current_state(self) -> dict:
        """Return the latest cached media info or query immediately if empty."""
        if not self._running:
            self.start()
        if self._last_data and self._last_data.get('status') == 'ok':
            return self._last_data
        fresh = query_media_once()
        if fresh and fresh.get('status') == 'ok':
            self._last_data = fresh
            return fresh
        return {"status": "none", "title": "", "artist": "", "album": "", "playback": "Paused", "position": 0, "duration": 0, "thumbnail": ""}


def launch_media_app(app_name: str) -> dict:
    """Launch popular media player applications."""
    import os
    import webbrowser
    app_lower = app_name.strip().lower()
    try:
        if "spotify" in app_lower:
            os.system("start spotify:")
            return {"status": "success", "output": "Opening Spotify..."}
        elif "ytmusic" in app_lower or "youtube music" in app_lower or "yt music" in app_lower:
            webbrowser.open("https://music.youtube.com")
            return {"status": "success", "output": "Opening YouTube Music..."}
        elif "apple" in app_lower:
            os.system("start itunes: || start itms:")
            return {"status": "success", "output": "Opening Apple Music..."}
        elif "vlc" in app_lower:
            os.system("start vlc")
            return {"status": "success", "output": "Opening VLC Media Player..."}
        else:
            os.system(f"start {app_name}")
            return {"status": "success", "output": f"Opening {app_name}..."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# Singleton instance
music_monitor = MusicMonitor()


if __name__ == '__main__':
    data = query_media_once()
    print(json.dumps(data, indent=2))

