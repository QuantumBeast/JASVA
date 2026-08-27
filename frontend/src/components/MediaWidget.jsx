import React, { useState, useEffect, useRef } from 'react';
import { DraggableWidget } from './DraggableWidget';
import { callBackend } from '../utils/pywebviewBridge';
import {
  Music,
  Play,
  Pause,
  SkipBack,
  SkipForward,
  Volume2,
  VolumeX,
  Disc
} from 'lucide-react';

const formatTime = (ms) => {
  if (!ms || isNaN(ms) || ms < 0) return '0:00';
  const totalSec = Math.floor(ms / 1000);
  const m = Math.floor(totalSec / 60);
  const s = totalSec % 60;
  return `${m}:${s < 10 ? '0' : ''}${s}`;
};

export const MediaWidget = ({ initialPos = { x: 40, y: 70 } }) => {
  const [media, setMedia] = useState({
    status: 'none',
    title: 'STANDBY',
    artist: 'Windows Media',
    playback: 'Paused',
    position: 0,
    duration: 0,
    thumbnail: ''
  });

  const [volume, setVolume] = useState(50);
  const [isMuted, setIsMuted] = useState(false);
  const [isSeeking, setIsSeeking] = useState(false);
  const [seekPos, setSeekPos] = useState(0);

  const seekLockUntilRef = useRef(0);
  const isPlaying = media.playback && media.playback.toLowerCase() === 'playing';

  // 1. Polling backend for SMTC metadata updates
  useEffect(() => {
    let mounted = true;
    const fetchStatus = async () => {
      try {
        const res = await callBackend('get_media_status');
        if (res && res.status !== 'error' && mounted) {
          const isLocked = Date.now() < seekLockUntilRef.current;
          const isPlayingState = res.playback && res.playback.toLowerCase() === 'playing';
          const hasTitle = res.title && res.title.trim().length > 0;

          setMedia(prev => {
            const fallbackTitle = isPlayingState ? (prev.title !== 'STANDBY' ? prev.title : 'Active Playback') : 'STANDBY';
            const fallbackArtist = isPlayingState ? (prev.artist !== 'Windows Media' ? prev.artist : 'System Audio') : 'Windows Media';
            return {
              ...prev,
              ...res,
              title: hasTitle ? res.title : fallbackTitle,
              artist: res.artist || fallbackArtist,
              playback: res.playback || 'Paused',
              position: isLocked ? prev.position : (res.position || 0),
              duration: res.duration || 0
            };
          });
          if (!isSeeking && !isLocked && res.position !== undefined) {
            setSeekPos(res.position);
          }
        }
      } catch (_) {}
    };

    fetchStatus();
    const interval = setInterval(fetchStatus, 1500);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, [isSeeking]);

  // 2. Smooth real-time advancement while song is playing
  useEffect(() => {
    if (!isPlaying) return;
    const tick = setInterval(() => {
      if (!isSeeking && Date.now() >= seekLockUntilRef.current) {
        setMedia(prev => {
          if (!prev.duration || prev.position >= prev.duration) return prev;
          const nextPos = Math.min(prev.duration, prev.position + 250);
          setSeekPos(nextPos);
          return { ...prev, position: nextPos };
        });
      }
    }, 250);

    return () => clearInterval(tick);
  }, [isPlaying, isSeeking]);

  // 3. Fetch initial system volume
  useEffect(() => {
    const fetchVolume = async () => {
      try {
        const res = await callBackend('get_system_volume');
        if (res && res.volume !== undefined) {
          setVolume(res.volume);
          setIsMuted(res.volume === 0);
        }
      } catch (_) {}
    };
    fetchVolume();
  }, []);

  const handleControl = async (action) => {
    try {
      await callBackend('control_media', action);
      if (action === 'toggle') {
        setMedia(prev => ({
          ...prev,
          playback: prev.playback.toLowerCase() === 'playing' ? 'Paused' : 'Playing'
        }));
      }
    } catch (_) {}
  };

  const handleVolume = async (val) => {
    const v = parseInt(val, 10);
    setVolume(v);
    setIsMuted(v === 0);
    try {
      await callBackend('set_system_volume', v);
    } catch (_) {}
  };

  // 4. Seek handlers (optimistic lock prevents slider snap-back)
  const handleSeekStart = () => {
    setIsSeeking(true);
  };

  const handleSeekChange = (e) => {
    const newPos = parseInt(e.target.value, 10);
    setSeekPos(newPos);
  };

  const handleSeekEnd = async (e) => {
    const finalPos = parseInt(e.target.value, 10);
    setIsSeeking(false);
    seekLockUntilRef.current = Date.now() + 2500;
    setSeekPos(finalPos);
    setMedia(prev => ({ ...prev, position: finalPos }));
    try {
      await callBackend('seek_media', finalPos);
    } catch (_) {}
  };

  const maxDuration = Math.max(1, media.duration || 1000);
  const currentPos = isSeeking ? seekPos : (media.position || 0);
  const progressPercent = Math.min(100, Math.max(0, (currentPos / maxDuration) * 100));

  return (
    <DraggableWidget
      id="media"
      title="AUDIO // SMTC"
      icon={Music}
      initialPos={initialPos}
      width={320}
    >
      <div className="media-widget-content">
        <div className="media-widget-row">
          {/* Vinyl / Cover Art Hologram */}
          <div className={`media-vinyl-disc ${isPlaying ? 'spinning' : ''}`}>
            {media.thumbnail ? (
              <img src={`data:image/jpeg;base64,${media.thumbnail}`} alt="Art" className="media-vinyl-art" />
            ) : (
              <Disc size={22} className="media-disc-placeholder" />
            )}
            <div className="media-vinyl-ring"></div>
          </div>

          {/* Meta Info */}
          <div className="media-widget-meta">
            <div className="media-widget-title" title={media.title}>
              {media.title}
            </div>
            <div className="media-widget-artist" title={media.artist}>
              {media.artist}
            </div>
          </div>
        </div>

        {/* Interactive Music Track Seek Slider */}
        <div className="media-seek-container">
          <span className="media-time-text">{formatTime(currentPos)}</span>
          <div className="media-seek-slider-wrap">
            <input
              type="range"
              min="0"
              max={maxDuration}
              value={currentPos}
              onMouseDown={handleSeekStart}
              onTouchStart={handleSeekStart}
              onPointerDown={handleSeekStart}
              onChange={handleSeekChange}
              onInput={handleSeekChange}
              onMouseUp={handleSeekEnd}
              onTouchEnd={handleSeekEnd}
              onPointerUp={handleSeekEnd}
              className="media-seek-slider"
              title="Seek Track Position"
              style={{
                background: `linear-gradient(to right, var(--accent-color) 0%, var(--accent-color) ${progressPercent}%, rgba(255, 255, 255, 0.18) ${progressPercent}%, rgba(255, 255, 255, 0.18) 100%)`
              }}
            />
          </div>
          <span className="media-time-text total">{formatTime(media.duration)}</span>
        </div>

        {/* Control Icons & Contained Volume Slider */}
        <div className="media-widget-controls">
          <div className="media-playback-btns">
            <button className="widget-icon-btn" onClick={() => handleControl('prev')} title="Previous Track">
              <SkipBack size={14} />
            </button>
            <button
              className={`widget-icon-btn play-btn ${isPlaying ? 'active' : ''}`}
              onClick={() => handleControl('toggle')}
              title={isPlaying ? 'Pause' : 'Play'}
            >
              {isPlaying ? <Pause size={16} /> : <Play size={16} />}
            </button>
            <button className="widget-icon-btn" onClick={() => handleControl('next')} title="Next Track">
              <SkipForward size={14} />
            </button>
          </div>

          {/* Volume Slider Contained */}
          <div className="media-vol-inline">
            <button
              className="vol-icon"
              onClick={() => handleVolume(isMuted ? 40 : 0)}
              title={isMuted ? "Unmute" : "Mute"}
            >
              {isMuted || volume === 0 ? <VolumeX size={13} /> : <Volume2 size={13} />}
            </button>
            <input
              type="range"
              min="0"
              max="100"
              value={volume}
              onChange={(e) => handleVolume(e.target.value)}
              className="widget-vol-slider"
              title="Volume"
            />
            <span className="vol-val-text">{volume}%</span>
          </div>
        </div>
      </div>
    </DraggableWidget>
  );
};
