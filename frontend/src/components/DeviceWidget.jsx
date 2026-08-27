import React, { useState } from 'react';
import { DraggableWidget } from './DraggableWidget';
import { useJasva } from '../context/JasvaContext';
import { isPyWebView } from '../utils/pywebviewBridge';
import {
  Tv,
  Smartphone,
  Power,
  Home,
  ArrowLeft,
  Square,
  Menu,
  Volume2,
  VolumeX,
  RotateCw,
  Maximize2,
  Sparkles,
  Link2,
  ChevronUp,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Layers
} from 'lucide-react';

export const DeviceWidget = ({ initialPos = { x: 40, y: 550 } }) => {
  const { tvStatus, setTvStatus, phoneStatus, setPhoneStatus, sendCommand, showToast } = useJasva();
  const [activeTab, setActiveTab] = useState('tv'); // 'tv' | 'phone'
  const [tvIp, setTvIp] = useState('');
  const [phoneIp, setPhoneIp] = useState('');
  const [phoneTask, setPhoneTask] = useState('');

  // ─── TV Remote Handlers ───
  const sendTvCmd = (cmd) => {
    if (isPyWebView() && window.pywebview.api && typeof window.pywebview.api.quick_button === 'function') {
      window.pywebview.api.quick_button('tv', cmd);
    } else {
      sendCommand(`tv ${cmd}`, true);
    }
  };

  const handleTvConnect = () => {
    if (!tvIp.trim()) return;
    sendCommand(`connect tv ${tvIp.trim()}`, true);
    setTvStatus({ connected: true, ip: tvIp.trim() });
    showToast({ title: 'SMART TV', message: `Connecting to ${tvIp.trim()}...` });
  };

  const handleTvApp = (app) => {
    sendCommand(`tv open ${app}`, true);
    showToast({ title: 'SMART TV', message: `Opening ${app.toUpperCase()}...` });
  };

  const handleTvMirror = () => {
    sendCommand('tv mirror', true);
    showToast({ title: 'SMART TV', message: 'Launching 60FPS TV Mirror...' });
  };

  // ─── Phone Remote Handlers ───
  const sendPhoneCmd = (keycode) => {
    const key = keycode.replace('keyevent ', '').trim();
    if (isPyWebView() && window.pywebview.api && typeof window.pywebview.api.quick_button === 'function') {
      window.pywebview.api.quick_button('phone', key);
    } else {
      sendCommand(`phone ${keycode}`, true);
    }
  };

  const handlePhoneConnect = () => {
    if (!phoneIp.trim()) return;
    sendCommand(`phone connect ${phoneIp.trim()}`, true);
    setPhoneStatus({ connected: true, ip: phoneIp.trim() });
    showToast({ title: 'PHONE LINK', message: `Connecting to ${phoneIp.trim()}...` });
  };

  const handlePhoneMirror = () => {
    sendCommand('phone mirror', true);
    showToast({ title: 'PHONE MIRROR', message: 'Launching 60FPS Phone Mirror...' });
  };

  const handleExecutePhoneTask = () => {
    if (!phoneTask.trim()) return;
    sendCommand(`phone do ${phoneTask.trim()}`);
    setPhoneTask('');
  };

  return (
    <DraggableWidget
      id="devices"
      title="DEVICES // REMOTE"
      icon={Layers}
      initialPos={initialPos}
      width={310}
    >
      <div className="device-widget-content">
        {/* Device Mode Switcher */}
        <div className="device-tab-switcher">
          <button
            className={`device-mode-btn ${activeTab === 'tv' ? 'active' : ''}`}
            onClick={() => setActiveTab('tv')}
          >
            <Tv size={12} />
            <span>SMART TV</span>
            <span className={`device-status-pip ${tvStatus.connected ? 'online' : ''}`}></span>
          </button>
          <button
            className={`device-mode-btn ${activeTab === 'phone' ? 'active' : ''}`}
            onClick={() => setActiveTab('phone')}
          >
            <Smartphone size={12} />
            <span>PHONE</span>
            <span className={`device-status-pip ${phoneStatus.connected ? 'online' : ''}`}></span>
          </button>
        </div>

        {/* ─── TV REMOTE PANEL ─── */}
        {activeTab === 'tv' && (
          <div className="device-panel-body">
            {/* IP Link Row */}
            <div className="device-ip-input-box">
              <input
                type="text"
                className="device-ip-field"
                placeholder="TV IP (e.g. 192.168.1.100)"
                value={tvIp}
                onChange={(e) => setTvIp(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleTvConnect()}
              />
              <button className="device-link-btn" onClick={handleTvConnect} title="Link TV">
                <Link2 size={11} />
                <span>LINK</span>
              </button>
            </div>

            {/* Quick Actions (Power + Mirror) */}
            <div className="device-action-row">
              <button className="device-power-btn" onClick={() => sendTvCmd('power')} title="Power TV">
                <Power size={12} />
                <span>POWER</span>
              </button>
              <button className="device-mirror-btn" onClick={handleTvMirror} title="Mirror TV Screen (60FPS)">
                <Maximize2 size={12} />
                <span>MIRROR</span>
              </button>
            </div>

            {/* TV Quick Launch Apps */}
            <div className="device-app-bar">
              <button className="device-app-pill" onClick={() => handleTvApp('youtube')}>YouTube</button>
              <button className="device-app-pill" onClick={() => handleTvApp('netflix')}>Netflix</button>
              <button className="device-app-pill" onClick={() => handleTvApp('prime video')}>Prime</button>
              <button className="device-app-pill" onClick={() => handleTvApp('spotify')}>Spotify</button>
            </div>

            {/* Cyber D-Pad Navigation */}
            <div className="cyber-dpad-stage">
              <div className="dpad-row dpad-row-top">
                <button className="dpad-circle-btn dpad-up" onClick={() => sendTvCmd('up')} title="Up">
                  <ChevronUp size={18} />
                </button>
              </div>
              <div className="dpad-row dpad-row-mid">
                <button className="dpad-circle-btn dpad-left" onClick={() => sendTvCmd('left')} title="Left">
                  <ChevronLeft size={18} />
                </button>
                <button className="dpad-ok-center" onClick={() => sendTvCmd('select')} title="OK / Select">
                  <span>OK</span>
                </button>
                <button className="dpad-circle-btn dpad-right" onClick={() => sendTvCmd('right')} title="Right">
                  <ChevronRight size={18} />
                </button>
              </div>
              <div className="dpad-row dpad-row-bottom">
                <button className="dpad-circle-btn dpad-down" onClick={() => sendTvCmd('down')} title="Down">
                  <ChevronDown size={18} />
                </button>
              </div>
            </div>

            {/* TV Function Keys (2 rows of 3) */}
            <div className="device-func-grid">
              <button className="device-func-tile" onClick={() => sendTvCmd('home')} title="Home">
                <Home size={12} />
                <span>HOME</span>
              </button>
              <button className="device-func-tile" onClick={() => sendTvCmd('back')} title="Back">
                <ArrowLeft size={12} />
                <span>BACK</span>
              </button>
              <button className="device-func-tile" onClick={() => sendTvCmd('menu')} title="Menu">
                <Menu size={12} />
                <span>MENU</span>
              </button>
              <button className="device-func-tile" onClick={() => sendTvCmd('mute')} title="Mute">
                <VolumeX size={12} />
                <span>MUTE</span>
              </button>
              <button className="device-func-tile" onClick={() => sendTvCmd('volume_up')} title="Volume Up">
                <Volume2 size={12} />
                <span>VOL +</span>
              </button>
              <button className="device-func-tile" onClick={() => sendTvCmd('volume_down')} title="Volume Down">
                <Volume2 size={12} />
                <span>VOL -</span>
              </button>
            </div>
          </div>
        )}

        {/* ─── PHONE REMOTE PANEL ─── */}
        {activeTab === 'phone' && (
          <div className="device-panel-body">
            {/* IP Link Row */}
            <div className="device-ip-input-box">
              <input
                type="text"
                className="device-ip-field"
                placeholder="Phone IP:Port (e.g. 192.168.1.50:5555)"
                value={phoneIp}
                onChange={(e) => setPhoneIp(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handlePhoneConnect()}
              />
              <button className="device-link-btn" onClick={handlePhoneConnect} title="Link Phone">
                <Link2 size={11} />
                <span>LINK</span>
              </button>
            </div>

            {/* Quick Actions (Power + 60FPS Mirror + Rotate) */}
            <div className="device-action-row">
              <button className="device-power-btn" onClick={() => sendPhoneCmd('26')} title="Power">
                <Power size={12} />
                <span>POWER</span>
              </button>
              <button className="device-mirror-btn" onClick={handlePhoneMirror} title="60FPS Phone Mirror">
                <Maximize2 size={12} />
                <span>MIRROR</span>
              </button>
              <button className="device-util-btn" onClick={() => sendCommand('phone rotate', true)} title="Rotate Screen">
                <RotateCw size={12} />
              </button>
            </div>

            {/* Phone Function Keys */}
            <div className="device-func-grid">
              <button className="device-func-tile" onClick={() => sendPhoneCmd('3')} title="Home">
                <Home size={12} />
                <span>HOME</span>
              </button>
              <button className="device-func-tile" onClick={() => sendPhoneCmd('4')} title="Back">
                <ArrowLeft size={12} />
                <span>BACK</span>
              </button>
              <button className="device-func-tile" onClick={() => sendPhoneCmd('187')} title="Recents">
                <Square size={12} />
                <span>RECENTS</span>
              </button>
              <button className="device-func-tile" onClick={() => sendPhoneCmd('164')} title="Mute">
                <VolumeX size={12} />
                <span>MUTE</span>
              </button>
              <button className="device-func-tile" onClick={() => sendPhoneCmd('24')} title="Volume Up">
                <Volume2 size={12} />
                <span>VOL +</span>
              </button>
              <button className="device-func-tile" onClick={() => sendPhoneCmd('25')} title="Volume Down">
                <Volume2 size={12} />
                <span>VOL -</span>
              </button>
            </div>

            {/* AI Screen Task Input */}
            <div className="device-ai-section">
              <div className="device-ai-title">
                <Sparkles size={11} />
                <span>AI SCREEN AGENT</span>
              </div>
              <div className="device-ip-input-box">
                <input
                  type="text"
                  className="device-ip-field"
                  placeholder="Ask JASVA (e.g. open Instagram & play)..."
                  value={phoneTask}
                  onChange={(e) => setPhoneTask(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleExecutePhoneTask()}
                />
                <button className="device-link-btn ai-run-btn" onClick={handleExecutePhoneTask} title="Execute on Phone">
                  <span>DO IT</span>
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </DraggableWidget>
  );
};
