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

# Only re-read the (potentially large) thumbnail when the track changes.
$lastKey = ""
$lastThumb = ""

function Get-MediaJson {
    $mgr = AwaitWinRT ($mgrType::RequestAsync()) $mgrType
    $sessions = $mgr.GetSessions()

    if ($sessions.Count -eq 0) {
        return [PSCustomObject]@{ status = "none" }
    }

    $s = $sessions[0]
    $props = AwaitWinRT ($s.TryGetMediaPropertiesAsync()) $propsType
    $playback = $s.GetPlaybackInfo()
    $timeline = $s.GetTimelineProperties()

    $title  = if ($props.Title) { $props.Title } else { "" }
    $artist = if ($props.Artist) { $props.Artist } else { "" }
    $album  = if ($props.AlbumTitle) { $props.AlbumTitle } else { "" }

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

    $posMs = [long]($timeline.Position.Ticks / 10000)
    $durMs = [long]($timeline.EndTime.Ticks / 10000)

    return [PSCustomObject]@{
        status    = "ok"
        title     = $title
        artist    = $artist
        album     = $album
        playback  = $playback.PlaybackStatus.ToString()
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

Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager, Windows.Media.Control, ContentType=WindowsRuntime]
$mgrType = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager]
$sessionType = $mgrType.GetMethod('GetSessions').ReturnType.GetGenericArguments()[0]

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

$mgr = AwaitWinRT ($mgrType::RequestAsync()) $mgrType
$sessions = $mgr.GetSessions()
if ($sessions.Count -eq 0) {
    Write-Output '{"status":"none"}'
} else {
    $s = $sessions[0]
    switch ($env:JASVA_MEDIA_ACTION) {
        "toggle" { $op = $s.TryTogglePlayPauseAsync() }
        "next"   { $op = $s.TrySkipNextAsync() }
        "prev"   { $op = $s.TrySkipPreviousAsync() }
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
            capture_output=True, text=True, timeout=8, encoding='utf-8',
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


def control_playback(action: str) -> dict:
    """Toggle play/pause, skip next, or skip previous via Windows SMTC."""
    try:
        import os
        env = dict(os.environ)
        env["JASVA_MEDIA_ACTION"] = action
        result = subprocess.run(
            ['powershell', '-NoProfile', '-NonInteractive', '-EncodedCommand', _encode_ps(CONTROL_PS_SCRIPT)],
            capture_output=True, text=True, timeout=8, encoding='utf-8',
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
        if not data or data.get('status') in ('error', 'none'):
            return

        # Track playback state for the frontend's own smooth ticker.
        self._is_playing = data.get('playback', '').lower() == 'playing'
        if self._is_playing:
            self._current_position = data.get('position', 0)
            self._current_duration = data.get('duration', 0)

        if data != self._last_data:
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


# Singleton instance
music_monitor = MusicMonitor()


if __name__ == '__main__':
    data = query_media_once()
    print(json.dumps(data, indent=2))
