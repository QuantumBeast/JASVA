Add-Type -AssemblyName System.Runtime.WindowsRuntime

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

$null = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager, Windows.Media.Control, ContentType=WindowsRuntime]

# Resolve types at runtime
$sessionManagerType = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager]
$mediaPropsType = [Windows.Media.Control.GlobalSystemMediaTransportControlsMediaProperties]
$irastType = [Windows.Storage.Streams.IRandomAccessStreamWithContentType]

$mgr = AwaitWinRT ($sessionManagerType::RequestAsync()) $sessionManagerType
$sessions = $mgr.GetSessions()

if ($sessions.Count -eq 0) {
    [PSCustomObject]@{ status = "none" } | ConvertTo-Json -Compress
    return
}

$s = $sessions[0]
$propsTask = $s.TryGetMediaPropertiesAsync()
$props = AwaitWinRT $propsTask $mediaPropsType
$playback = $s.GetPlaybackInfo()
$timeline = $s.GetTimelineProperties()

$thumb = ""
if ($props.Thumbnail -ne $null) {
    try {
        $streamTask = $props.Thumbnail.OpenReadAsync()
        $stream = AwaitWinRT $streamTask $irastType
        $reader = [Windows.Storage.Streams.DataReader]::new($stream)
        $loadTask = $reader.LoadAsync([uint]$stream.Size)
        $null = AwaitWinRT $loadTask ([uint32])
        $buf = [byte[]]::new([int]$stream.Size)
        $reader.ReadBytes($buf)
        $thumb = [Convert]::ToBase64String($buf)
    } catch {}
}

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
