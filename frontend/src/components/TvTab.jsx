import React, { useState } from 'react';
import { useJasva } from '../context/JasvaContext';
import { isPyWebView } from '../utils/pywebviewBridge';
import {
  Tv,
  Power,
  Home,
  ArrowLeft,
  Menu,
  VolumeX,
  Volume2,
  Maximize2,
  ChevronUp,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Link2
} from 'lucide-react';

export const TvTab = () => {
  const { tvStatus, setTvStatus, sendCommand, showToast } = useJasva();
  const [tvIp, setTvIp] = useState('');

  const sendTvCmd = (cmd) => {
    if (isPyWebView() && window.pywebview.api && window.pywebview.api.quick_button) {
      window.pywebview.api.quick_button('tv', cmd);
    } else {
      sendCommand(`tv ${cmd}`, true);
    }
  };

  const handleConnect = () => {
    if (!tvIp.trim()) return;
    sendCommand(`connect tv ${tvIp.trim()}`, true);
    setTvStatus({ connected: true, ip: tvIp.trim() });
    showToast({ title: 'SMART TV', message: `Connecting to ${tvIp.trim()}...` });
  };

  const handleAppLaunch = (appName) => {
    sendCommand(`tv open ${appName}`, true);
    showToast({ title: 'SMART TV', message: `Launching ${appName.toUpperCase()}...` });
  };

  return (
    <div className="tab-pane">
      {/* TV Connection Header & IP Input */}
      <div className="device-section">
        <div className="device-section-header">
          <div className="device-section-title-row">
            <Tv size={13} />
            <span>SMART TV</span>
          </div>
          <div className="device-status-badge">
            <span className={`device-status-dot ${tvStatus.connected ? 'connected' : ''}`}></span>
            <span>{tvStatus.connected ? 'CONNECTED' : 'DISCONNECTED'}</span>
          </div>
        </div>

        <div className="device-ip-row">
          <input
            type="text"
            className="device-ip-input"
            placeholder="TV IP address (e.g. 192.168.1.100)"
            value={tvIp}
            onChange={(e) => setTvIp(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleConnect()}
          />
          <button
            className="device-connect-btn"
            onClick={handleConnect}
            title="Connect TV"
          >
            <Link2 size={12} />
            <span>LINK</span>
          </button>
        </div>
      </div>

      {/* Cyber D-Pad Navigation Controller */}
      <div className="device-section">
        <div className="device-section-header" style={{ marginBottom: '4px' }}>
          <div className="device-section-title-row">
            <span>NAVIGATION CONTROLLER</span>
          </div>
        </div>

        <div className="cyber-dpad-wrapper">
          <div className="cyber-dpad-container">
            <button
              className="dpad-nav-btn dpad-up"
              onClick={() => sendTvCmd('up')}
              title="Up"
            >
              <ChevronUp size={16} />
            </button>
            <button
              className="dpad-nav-btn dpad-left"
              onClick={() => sendTvCmd('left')}
              title="Left"
            >
              <ChevronLeft size={16} />
            </button>
            <button
              className="dpad-center-btn"
              onClick={() => sendTvCmd('select')}
              title="OK / Select"
            >
              OK
            </button>
            <button
              className="dpad-nav-btn dpad-right"
              onClick={() => sendTvCmd('right')}
              title="Right"
            >
              <ChevronRight size={16} />
            </button>
            <button
              className="dpad-nav-btn dpad-down"
              onClick={() => sendTvCmd('down')}
              title="Down"
            >
              <ChevronDown size={16} />
            </button>
          </div>
        </div>

        {/* 8-Button Secondary Keypad including MENU button */}
        <div className="phone-remote-grid" style={{ marginTop: '8px' }}>
          <button
            className="phone-remote-btn power-btn"
            onClick={() => sendTvCmd('power')}
            title="Power"
          >
            <Power size={13} />
            <span>POWER</span>
          </button>
          <button
            className="phone-remote-btn"
            onClick={() => sendTvCmd('home')}
            title="Home"
          >
            <Home size={13} />
            <span>HOME</span>
          </button>
          <button
            className="phone-remote-btn"
            onClick={() => sendTvCmd('back')}
            title="Back"
          >
            <ArrowLeft size={13} />
            <span>BACK</span>
          </button>
          <button
            className="phone-remote-btn"
            onClick={() => sendTvCmd('menu')}
            title="Menu"
          >
            <Menu size={13} />
            <span>MENU</span>
          </button>
          <button
            className="phone-remote-btn"
            onClick={() => sendTvCmd('mute')}
            title="Mute"
          >
            <VolumeX size={13} />
            <span>MUTE</span>
          </button>
          <button
            className="phone-remote-btn"
            onClick={() => sendTvCmd('volume_up')}
            title="Volume Up"
          >
            <Volume2 size={13} />
            <span>VOL +</span>
          </button>
          <button
            className="phone-remote-btn"
            onClick={() => sendTvCmd('volume_down')}
            title="Volume Down"
          >
            <Volume2 size={13} />
            <span>VOL -</span>
          </button>
          <button
            className="phone-remote-btn"
            onClick={() => sendTvCmd('mirror')}
            title="Screen Mirror"
          >
            <Maximize2 size={13} />
            <span>MIRROR</span>
          </button>
        </div>
      </div>

      {/* TV Quick App Launch Grid */}
      <div className="device-section">
        <div className="device-section-header" style={{ marginBottom: '4px' }}>
          <div className="device-section-title-row">
            <span>QUICK APPS</span>
          </div>
        </div>

        <div className="tv-apps-grid">
          <button
            className="tv-app-btn"
            onClick={() => handleAppLaunch('youtube')}
            title="Launch YouTube TV"
          >
            <svg viewBox="0 0 24 24" width="16" height="16" fill="#ff0000">
              <path d="M23.498 6.163a3.003 3.003 0 0 0-2.11-2.11C19.517 3.545 12 3.545 12 3.545s-7.516 0-9.387.507A3.002 3.002 0 0 0 .503 6.163C0 8.037 0 12 0 12s0 3.963.502 5.837a3.002 3.002 0 0 0 2.111 2.11C4.483 20.455 12 20.455 12 20.455s7.517 0 9.387-.508a3.003 3.003 0 0 0 2.11-2.11c.501-1.874.501-5.837.501-5.837s0-3.963-.501-5.837zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
            </svg>
            <span>YouTube</span>
          </button>
          <button
            className="tv-app-btn"
            onClick={() => handleAppLaunch('netflix')}
            title="Launch Netflix"
          >
            <span style={{ color: '#e50914', fontWeight: 900, fontSize: '14px', lineHeight: 1 }}>N</span>
            <span>Netflix</span>
          </button>
          <button
            className="tv-app-btn"
            onClick={() => handleAppLaunch('prime video')}
            title="Launch Prime Video"
          >
            <span style={{ color: '#00a8e1', fontWeight: 800, fontSize: '13px' }}>prime</span>
            <span>Prime</span>
          </button>
          <button
            className="tv-app-btn"
            onClick={() => handleAppLaunch('spotify')}
            title="Launch Spotify TV"
          >
            <span style={{ color: '#1db954', fontWeight: 800, fontSize: '14px' }}>●</span>
            <span>Spotify</span>
          </button>
        </div>
      </div>
    </div>
  );
};
