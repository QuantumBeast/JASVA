import React, { useState, useEffect, useRef } from 'react';
import { callBackend } from '../utils/pywebviewBridge';
import {
  Play,
  Pause,
  SkipBack,
  SkipForward,
  Volume2,
  VolumeX,
  Music,
  Disc,
  FileText,
  ExternalLink,
  Radio
} from 'lucide-react';

export const MediaTab = () => {
  const [media, setMedia] = useState({
    status: 'none',
    title: 'NO MEDIA DETECTED',
    artist: 'Windows SMTC Standby',
    album: '',
    playback: 'Paused',
    position: 0,
    duration: 0,
    thumbnail: ''
  });

  const [volume, setVolume] = useState(50);
  const [isMuted, setIsMuted] = useState(false);
  const [prevVolume, setPrevVolume] = useState(50);
  const [showLyrics, setShowLyrics] = useState(false);
  const [lyrics, setLyrics] = useState([]);
  const [isLoadingLyrics, setIsLoadingLyrics] = useState(false);
  const [lyricsActiveIndex, setLyricsActiveIndex] = useState(-1);
  const lyricsContainerRef = useRef(null);

  // Poll Media Status every 2 seconds
  useEffect(() => {
    let isMounted = true;
    const fetchStatus = async () => {
      try {
        const res = await callBackend('get_media_status');
        if (res && res.status !== 'error' && isMounted) {
          setMedia(prev => {
            // If track changed, reset lyrics
            if (res.title && (res.title !== prev.title || res.artist !== prev.artist)) {
              setLyrics([]);
              setLyricsActiveIndex(-1);
            }
            return {
              ...prev,
              ...res,
              title: res.title || 'NO MEDIA DETECTED',
              artist: res.artist || 'Windows SMTC Standby',
              playback: res.playback || 'Paused'
            };
          });
        }
      } catch (err) {
        console.warn('Error fetching media status:', err);
      }
    };

    fetchStatus();
    const interval = setInterval(fetchStatus, 2000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  // Fetch initial system volume
  useEffect(() => {
    const fetchVol = async () => {
      try {
        const res = await callBackend('get_system_volume');
        if (res && res.status === 'success' && typeof res.volume === 'number') {
          setVolume(res.volume);
          setIsMuted(res.volume === 0);
        }
      } catch (_) {}
    };
    fetchVol();
  }, []);

  // Sync lyrics highlight based on position
  useEffect(() => {
    if (!lyrics.length || !media.position) return;
    const pos = media.position;
    let currIdx = -1;
    for (let i = 0; i < lyrics.length; i++) {
      if (pos >= lyrics[i].time) {
        currIdx = i;
      } else {
        break;
      }
    }
    if (currIdx !== lyricsActiveIndex) {
      setLyricsActiveIndex(currIdx);
      if (lyricsContainerRef.current && currIdx >= 0) {
        const activeElem = lyricsContainerRef.current.children[currIdx];
        if (activeElem) {
          activeElem.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      }
    }
  }, [media.position, lyrics, lyricsActiveIndex]);

  // Load Synced Lyrics
  const handleToggleLyrics = async () => {
    const nextState = !showLyrics;
    setShowLyrics(nextState);
    if (nextState && !lyrics.length && media.title && media.title !== 'NO MEDIA DETECTED') {
      setIsLoadingLyrics(true);
      try {
        const res = await callBackend('get_media_lyrics', media.title, media.artist);
        if (res && res.status === 'success' && Array.isArray(res.lyrics)) {
          setLyrics(res.lyrics);
        }
      } catch (e) {
        console.warn('Failed to load lyrics:', e);
      } finally {
        setIsLoadingLyrics(false);
      }
    }
  };

  // Playback Control Actions
  const handleControl = async (action) => {
    try {
      await callBackend('control_media', action);
      // Optimistic state toggle
      if (action === 'toggle') {
        setMedia(prev => ({
          ...prev,
          playback: prev.playback.toLowerCase() === 'playing' ? 'Paused' : 'Playing'
        }));
      }
    } catch (e) {
      console.error('Media control failed:', e);
    }
  };

  // Volume Change
  const handleVolumeChange = async (newVal) => {
    const val = parseInt(newVal, 10);
    setVolume(val);
    setIsMuted(val === 0);
    try {
      await callBackend('set_system_volume', val);
    } catch (_) {}
  };

  // Mute Toggle
  const handleToggleMute = async () => {
    if (isMuted) {
      const restore = prevVolume || 40;
      setVolume(restore);
      setIsMuted(false);
      await callBackend('set_system_volume', restore);
    } else {
      setPrevVolume(volume);
      setVolume(0);
      setIsMuted(true);
      await callBackend('set_system_volume', 0);
    }
  };

  // Launch App
  const handleLaunchApp = async (appName) => {
    try {
      await callBackend('launch_media_app', appName);
    } catch (_) {}
  };

  // Format Milliseconds to MM:SS
  const formatTime = (ms) => {
    if (!ms || isNaN(ms)) return '0:00';
    const totalSecs = Math.floor(ms / 1000);
    const mins = Math.floor(totalSecs / 60);
    const secs = totalSecs % 60;
    return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
  };

  const isPlaying = media.playback && media.playback.toLowerCase() === 'playing';
  const progressPercent = media.duration > 0 ? Math.min(100, (media.position / media.duration) * 100) : 0;

  return (
    <div className="panel-content media-hub-panel">
      {/* ─── NOW PLAYING HOLOGRAPHIC CARD ─── */}
      <div className="media-track-card">
        {/* Album Artwork / Disc Hologram */}
        <div className={`media-art-container ${isPlaying ? 'spinning' : ''}`}>
          {media.thumbnail ? (
            <img
              src={`data:image/jpeg;base64,${media.thumbnail}`}
              alt="Cover Art"
              className="media-art-img"
            />
          ) : (
            <div className="media-art-placeholder">
              <Disc size={28} className="media-disc-icon" />
            </div>
          )}
          <div className="media-art-glow"></div>
        </div>

        {/* Track Details */}
        <div className="media-meta-info">
          <div className="media-status-pill">
            <span className={`media-status-dot ${isPlaying ? 'live' : ''}`}></span>
            <span className="media-status-label">
              {isPlaying ? 'PLAYING' : 'PAUSED'}
            </span>
          </div>

          <div className="media-track-title" title={media.title}>
            {media.title}
          </div>
          <div className="media-track-artist" title={media.artist}>
            {media.artist || 'Unknown Artist'}
          </div>
          {media.album && (
            <div className="media-track-album" title={media.album}>
              {media.album}
            </div>
          )}
        </div>
      </div>

      {/* ─── TIMELINE SCRUBBER & DURATION ─── */}
      <div className="media-timeline-section">
        <div className="media-progress-bar-bg">
          <div
            className="media-progress-fill"
            style={{ width: `${progressPercent}%` }}
          ></div>
        </div>
        <div className="media-time-labels">
          <span>{formatTime(media.position)}</span>
          <span>{formatTime(media.duration)}</span>
        </div>
      </div>

      {/* ─── PRIMARY PLAYBACK CONTROLS ─── */}
      <div className="media-controls-row">
        <button
          className="media-ctrl-btn"
          onClick={() => handleControl('prev')}
          title="Previous Track"
        >
          <SkipBack size={16} />
          <span>PREV</span>
        </button>

        <button
          className={`media-play-core-btn ${isPlaying ? 'active' : ''}`}
          onClick={() => handleControl('toggle')}
          title={isPlaying ? 'Pause' : 'Play'}
        >
          {isPlaying ? <Pause size={18} /> : <Play size={18} />}
          <span>{isPlaying ? 'PAUSE' : 'PLAY'}</span>
        </button>

        <button
          className="media-ctrl-btn"
          onClick={() => handleControl('next')}
          title="Next Track"
        >
          <SkipForward size={16} />
          <span>NEXT</span>
        </button>

        <button
          className={`media-ctrl-btn ${showLyrics ? 'active' : ''}`}
          onClick={handleToggleLyrics}
          title="Synced Lyrics"
        >
          <FileText size={16} />
          <span>LYRICS</span>
        </button>
      </div>

      {/* ─── MASTER VOLUME SLIDER ─── */}
      <div className="media-volume-section">
        <button
          className="media-vol-icon-btn"
          onClick={handleToggleMute}
          title={isMuted ? 'Unmute' : 'Mute'}
        >
          {isMuted || volume === 0 ? <VolumeX size={14} /> : <Volume2 size={14} />}
        </button>
        <input
          type="range"
          min="0"
          max="100"
          value={volume}
          onChange={(e) => handleVolumeChange(e.target.value)}
          className="media-volume-slider"
        />
        <span className="media-volume-badge">{volume}%</span>
      </div>

      {/* ─── SYNCED LYRICS CONTAINER (COLLAPSIBLE) ─── */}
      {showLyrics && (
        <div className="media-lyrics-drawer">
          <div className="media-lyrics-header">
            <span>SYNCED LYRICS (LRCLIB)</span>
            {isLoadingLyrics && <span className="lyrics-loading-pulse">SYNCING...</span>}
          </div>

          <div className="media-lyrics-list" ref={lyricsContainerRef}>
            {isLoadingLyrics ? (
              <div className="lyrics-empty-notice">Fetching live lyrics...</div>
            ) : lyrics.length > 0 ? (
              lyrics.map((line, idx) => (
                <div
                  key={idx}
                  className={`lyrics-line ${idx === lyricsActiveIndex ? 'active' : ''}`}
                >
                  {line.text}
                </div>
              ))
            ) : (
              <div className="lyrics-empty-notice">
                {media.title !== 'NO MEDIA DETECTED'
                  ? 'No synchronized lyrics available for this track.'
                  : 'Start audio to load synchronized lyrics.'}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ─── QUICK APP LAUNCHERS ─── */}
      <div className="media-launchers-section">
        <div className="media-section-subhead">QUICK LAUNCH</div>
        <div className="media-launcher-grid">
          <button
            className="media-app-chip"
            onClick={() => handleLaunchApp('spotify')}
            title="Launch Spotify"
          >
            <span>SPOTIFY</span>
          </button>
          <button
            className="media-app-chip"
            onClick={() => handleLaunchApp('ytmusic')}
            title="Launch YouTube Music"
          >
            <span>YT MUSIC</span>
          </button>
          <button
            className="media-app-chip"
            onClick={() => handleLaunchApp('apple')}
            title="Launch Apple Music"
          >
            <span>APPLE</span>
          </button>
          <button
            className="media-app-chip"
            onClick={() => handleLaunchApp('vlc')}
            title="Launch VLC Media Player"
          >
            <span>VLC</span>
          </button>
        </div>
      </div>
    </div>
  );
};
