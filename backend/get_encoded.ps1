$code = @'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager, Windows.Media.Control, ContentType=WindowsRuntime]
$null = [Windows.Media.Control.GlobalSystemMediaTransportControlsMediaProperties, Windows.Media.Control, ContentType=WindowsRuntime]

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

$mgr = AwaitWinRT ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager]::RequestAsync()) ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager])
$sessions = $mgr.GetSessions()

if ($sessions.Count -eq 0) {
    [PSCustomObject]@{ status = "none" } | ConvertTo-Json -Compress
    return
}

$s = $sessions[0]
$props = AwaitWinRT ($s.TryGetMediaPropertiesAsync()) ([Windows.Media.Control.GlobalSystemMediaTransportControlsMediaProperties])
$playback = $s.GetPlaybackInfo()
$timeline = $s.GetTimelineProperties()

$thumb = ""
try {
    $stream = AwaitWinRT ($props.Thumbnail.OpenReadAsync()) ([Windows.Storage.Streams.IRandomAccessStreamWithContentType])
    $reader = [Windows.Storage.Streams.DataReader]::new($stream)
    $null = AwaitWinRT ($reader.LoadAsync([uint]$stream.Size)) ([uint32])
    $buf = [byte[]]::new([int]$stream.Size)
    $reader.ReadBytes($buf)
    $thumb = [Convert]::ToBase64String($buf)
} catch {}

$posMs = [long]($timeline.Position.Ticks / 10000)
$durMs = [long]($timeline.EndTime.Ticks / 10000)

[PSCustomObject]@{
    status    = "ok"
    title     = if ($props.Title) { $props.Title } else { "" }
    artist    = if ($props.Artist) { $props.Artist } else { "" }
    album     = if ($props.AlbumTitle) { $props.AlbumTitle } else { "" }
    playback  = $playback.PlaybackStatus.ToString()
    position  = $posMs
    duration  = $durMs
    thumbnail = $thumb
} | ConvertTo-Json -Compress
'@

$bytes = [System.Text.Encoding]::Unicode.GetBytes($code)
$encoded = [Convert]::ToBase64String($bytes)
Write-Output $encoded
