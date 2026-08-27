import React, { useState } from 'react';
import { useJasva } from '../context/JasvaContext';
import { isPyWebView } from '../utils/pywebviewBridge';
import {
  Smartphone,
  Power,
  Home,
  ArrowLeft,
  Square,
  Volume2,
  VolumeX,
  RotateCw,
  Maximize2,
  Sparkles,
  Link2
} from 'lucide-react';

export const PhoneTab = () => {
  const { phoneStatus, setPhoneStatus, sendCommand, showToast, setIsPhoneOverlayOpen } = useJasva();
  const [phoneIp, setPhoneIp] = useState('');
  const [phoneTask, setPhoneTask] = useState('');

  const sendPhoneCmd = (keycode) => {
    const key = keycode.replace('keyevent ', '').trim();
    if (isPyWebView() && window.pywebview.api && window.pywebview.api.quick_button) {
      window.pywebview.api.quick_button('phone', key);
    } else {
      sendCommand(`phone ${keycode}`, true);
    }
  };

  const handleConnect = () => {
    if (!phoneIp.trim()) return;
    sendCommand(`phone connect ${phoneIp.trim()}`, true);
    setPhoneStatus({ connected: true, ip: phoneIp.trim() });
    showToast({ title: 'PHONE LINK', message: `Connecting to ${phoneIp.trim()}...` });
  };

  const handleExecuteTask = () => {
    if (!phoneTask.trim()) return;
    sendCommand(`phone do ${phoneTask.trim()}`);
    setPhoneTask('');
  };

  const toggleRotate = () => {
    sendCommand('phone rotate', true);
  };

  return (
    <div className="tab-pane">
      {/* Phone Remote Controls Section */}
      <div className="device-section">
        <div className="device-section-header">
          <div className="device-section-title-row">
            <Smartphone size={13} />
            <span>PHONE MIRROR</span>
          </div>
          <div className="device-status-badge">
            <span className={`device-status-dot ${phoneStatus.connected ? 'connected' : ''}`}></span>
            <span>{phoneStatus.connected ? 'CONNECTED' : 'STANDBY'}</span>
          </div>
        </div>

        {/* 8-Button Remote Grid */}
        <div className="phone-remote-grid" style={{ marginTop: '6px' }}>
          <button
            className="phone-remote-btn power-btn"
            onClick={() => sendPhoneCmd('26')}
            title="Power"
          >
            <Power size={13} />
            <span>POWER</span>
          </button>
          <button
            className="phone-remote-btn"
            onClick={() => sendPhoneCmd('3')}
            title="Home"
          >
            <Home size={13} />
            <span>HOME</span>
          </button>
          <button
            className="phone-remote-btn"
            onClick={() => sendPhoneCmd('4')}
            title="Back"
          >
            <ArrowLeft size={13} />
            <span>BACK</span>
          </button>
          <button
            className="phone-remote-btn"
            onClick={() => sendPhoneCmd('187')}
            title="Recent Apps"
          >
            <Square size={13} />
            <span>RECENTS</span>
          </button>
          <button
            className="phone-remote-btn"
            onClick={() => sendPhoneCmd('24')}
            title="Volume Up"
          >
            <Volume2 size={13} />
            <span>VOL +</span>
          </button>
          <button
            className="phone-remote-btn"
            onClick={() => sendPhoneCmd('25')}
            title="Volume Down"
          >
            <VolumeX size={13} />
            <span>VOL -</span>
          </button>
          <button
            className="phone-remote-btn"
            onClick={toggleRotate}
            title="Rotate Screen"
          >
            <RotateCw size={13} />
            <span>ROTATE</span>
          </button>
          <button
            className="phone-remote-btn"
            onClick={() => setIsPhoneOverlayOpen(true)}
            title="Toggle Live Mirror Stream"
          >
            <Maximize2 size={13} />
            <span>MIRROR</span>
          </button>
        </div>
      </div>

      {/* AI Phone Agent Section */}
      <div className="device-section">
        <div className="device-section-header">
          <div className="device-section-title-row">
            <Sparkles size={13} />
            <span>AI PHONE AGENT</span>
          </div>
        </div>
        <div className="device-ip-row">
          <input
            type="text"
            className="device-ip-input"
            placeholder="Ask JASVA (e.g. open Instagram & search)..."
            value={phoneTask}
            onChange={(e) => setPhoneTask(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleExecuteTask()}
          />
          <button
            className="device-connect-btn"
            onClick={handleExecuteTask}
            title="Execute Vision AI Agent"
          >
            <Sparkles size={12} />
            <span>EXECUTE</span>
          </button>
        </div>
      </div>

      {/* Wireless ADB Link Section */}
      <div className="device-section">
        <div className="device-section-header">
          <div className="device-section-title-row">
            <Link2 size={13} />
            <span>WIRELESS ADB LINK</span>
          </div>
        </div>
        <div className="device-ip-row">
          <input
            type="text"
            className="device-ip-input"
            placeholder="Phone IP:port (e.g. 192.168.1.50:5555)"
            value={phoneIp}
            onChange={(e) => setPhoneIp(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleConnect()}
          />
          <button
            className="device-connect-btn"
            onClick={handleConnect}
            title="Connect Phone via ADB"
          >
            <Link2 size={12} />
            <span>LINK</span>
          </button>
        </div>
      </div>
    </div>
  );
};
