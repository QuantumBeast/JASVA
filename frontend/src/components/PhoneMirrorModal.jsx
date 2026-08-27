import React from 'react';
import { useJasva } from '../context/JasvaContext';
import {
  X,
  Smartphone,
  Power,
  Home,
  ArrowLeft,
  Square,
  Volume2,
  VolumeX,
  RotateCw,
  ExternalLink
} from 'lucide-react';

export const PhoneMirrorModal = () => {
  const { isPhoneOverlayOpen, setIsPhoneOverlayOpen, sendCommand, showToast } = useJasva();

  if (!isPhoneOverlayOpen) return null;

  const sendPhoneCmd = (cmd) => {
    sendCommand(`phone ${cmd}`, true);
  };

  const handleLaunchScrcpy = () => {
    sendCommand('phone mirror', true);
    showToast({ title: 'PHONE MIRROR', message: 'Launching native Scrcpy mirror...' });
  };

  return (
    <div className="modal-overlay" onClick={() => setIsPhoneOverlayOpen(false)}>
      <div
        className="settings-modal-card"
        style={{ width: '380px', maxWidth: '90vw' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="settings-modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Smartphone size={15} color="var(--accent-color)" />
            <span style={{ fontFamily: 'Outfit, sans-serif', fontSize: '12px', fontWeight: 800, letterSpacing: '1px', color: 'var(--accent-color)' }}>
              DEVICE MIRROR
            </span>
          </div>
          <button
            onClick={() => setIsPhoneOverlayOpen(false)}
            style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="settings-modal-body" style={{ alignItems: 'center', gap: '12px' }}>
          {/* Stream placeholder / Viewer */}
          <div
            style={{
              width: '200px',
              height: '340px',
              background: 'rgba(4, 10, 22, 0.9)',
              border: '1px solid var(--border-color)',
              borderRadius: '16px',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '12px',
              boxShadow: 'inset 0 0 20px rgba(0, 0, 0, 0.8)'
            }}
          >
            <Smartphone size={36} color="var(--accent-color)" style={{ opacity: 0.6 }} />
            <span style={{ fontSize: '10px', fontFamily: 'JetBrains Mono, monospace', color: 'var(--text-muted)', textAlign: 'center', padding: '0 12px' }}>
              CONNECT PHONE TO STREAM
            </span>
            <button
              className="device-connect-btn"
              onClick={handleLaunchScrcpy}
              style={{ fontSize: '9px', padding: '6px 12px' }}
            >
              <ExternalLink size={12} />
              <span>POP OUT MIRROR</span>
            </button>
          </div>

          {/* Remote Toolbar */}
          <div className="phone-remote-grid" style={{ width: '100%', marginTop: '4px' }}>
            <button className="phone-remote-btn power-btn" onClick={() => sendPhoneCmd('keyevent 26')}>
              <Power size={13} />
              <span>POWER</span>
            </button>
            <button className="phone-remote-btn" onClick={() => sendPhoneCmd('keyevent 3')}>
              <Home size={13} />
              <span>HOME</span>
            </button>
            <button className="phone-remote-btn" onClick={() => sendPhoneCmd('keyevent 4')}>
              <ArrowLeft size={13} />
              <span>BACK</span>
            </button>
            <button className="phone-remote-btn" onClick={() => sendPhoneCmd('keyevent 187')}>
              <Square size={13} />
              <span>RECENTS</span>
            </button>
            <button className="phone-remote-btn" onClick={() => sendPhoneCmd('keyevent 24')}>
              <Volume2 size={13} />
              <span>VOL +</span>
            </button>
            <button className="phone-remote-btn" onClick={() => sendPhoneCmd('keyevent 25')}>
              <VolumeX size={13} />
              <span>VOL -</span>
            </button>
            <button className="phone-remote-btn" onClick={() => sendPhoneCmd('rotate')}>
              <RotateCw size={13} />
              <span>ROTATE</span>
            </button>
            <button className="phone-remote-btn" onClick={handleLaunchScrcpy}>
              <ExternalLink size={13} />
              <span>POP OUT</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
