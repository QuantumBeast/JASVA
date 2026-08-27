import React, { useState, useRef, useEffect } from 'react';
import { useJasva } from '../context/JasvaContext';
import {
  Volume2,
  VolumeX,
  Mic,
  Settings,
  Layers,
  Sparkles,
  Activity,
  Radio,
  Palette
} from 'lucide-react';

const THEMES = [
  { id: 'default', name: 'CYAN', color: '#00f2fe' },
  { id: 'purple', name: 'VIOLET', color: '#bd00ff' },
  { id: 'green', name: 'MATRIX', color: '#00ff87' },
  { id: 'orange', name: 'SOLAR', color: '#ff8800' },
  { id: 'red', name: 'CRIMSON', color: '#ff3b30' }
];

export const TopBar = () => {
  const {
    theme,
    changeTheme,
    panels,
    togglePanel,
    isVoiceMuted,
    setIsVoiceMuted,
    isAlwaysListening,
    toggleVoiceListening,
    setIsSettingsOpen
  } = useJasva();

  const [isPanelsMenuOpen, setIsPanelsMenuOpen] = useState(false);
  const [isThemeMenuOpen, setIsThemeMenuOpen] = useState(false);
  const menuRef = useRef(null);
  const themeRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setIsPanelsMenuOpen(false);
      }
      if (themeRef.current && !themeRef.current.contains(e.target)) {
        setIsThemeMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <header className="quantum-top-bar">
      {/* Brand & Quantum Status */}
      <div className="brand-section">
        <div className="brand-logo">
          <div className="logo-core-pulse"></div>
          <Sparkles className="logo-icon" size={16} />
        </div>
        <div className="brand-text">
          <span className="brand-title">JASVA</span>
          <span className="brand-subtitle">MARK-85 QUANTUM HUD</span>
        </div>
        <div className="top-status-indicator">
          <span className="status-live-node"></span>
          <span className="status-live-text">NEURAL LINK STABLE</span>
        </div>
      </div>

      {/* Action Toolbar */}
      <div className="header-action-toolbar">
        {/* Theme Palette Switcher */}
        <div className="hud-dropdown-container" ref={themeRef} style={{ position: 'relative' }}>
          <button
            className="hud-action-pill"
            onClick={() => setIsThemeMenuOpen(!isThemeMenuOpen)}
            title="Theme Palette"
          >
            <Palette size={12} />
            <span>THEME</span>
          </button>

          {isThemeMenuOpen && (
            <div className="hud-dropdown-menu show theme-picker-menu">
              {THEMES.map((t) => (
                <button
                  key={t.id}
                  className={`theme-option-btn ${theme === t.id ? 'active' : ''}`}
                  onClick={() => {
                    changeTheme(t.id);
                    setIsThemeMenuOpen(false);
                  }}
                >
                  <span className="theme-color-dot" style={{ backgroundColor: t.color }}></span>
                  <span>{t.name}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Panels Visibility Dropdown */}
        <div className="hud-dropdown-container" ref={menuRef} style={{ position: 'relative' }}>
          <button
            className="hud-action-pill"
            onClick={() => setIsPanelsMenuOpen(!isPanelsMenuOpen)}
            title="Toggle Panels"
          >
            <Layers size={12} />
            <span>PANELS</span>
          </button>

          {isPanelsMenuOpen && (
            <div className="hud-dropdown-menu show panels-menu">
              {[
                { key: 'chatPanel', label: 'CHAT CONSOLE' },
                { key: 'activeListeningPanel', label: 'REACTOR CORE' },
                { key: 'commandEchoPanel', label: 'COGNITION LOG' },
                { key: 'systemPanel', label: 'CONTROL HUB' }
              ].map(({ key, label }) => (
                <label key={key} className="panel-toggle-item">
                  <input
                    type="checkbox"
                    checked={panels[key]}
                    onChange={() => togglePanel(key)}
                  />
                  <span>{label}</span>
                </label>
              ))}
            </div>
          )}
        </div>

        {/* Always Listen Toggle */}
        <button
          className={`hud-icon-btn ${isAlwaysListening ? 'active' : ''}`}
          onClick={toggleVoiceListening}
          title={isAlwaysListening ? 'Voice Input: ALWAYS ACTIVE' : 'Voice Input: OFF'}
        >
          <Mic size={15} />
        </button>

        {/* Voice Mute Toggle */}
        <button
          className={`hud-icon-btn ${isVoiceMuted ? 'muted' : ''}`}
          onClick={() => setIsVoiceMuted(!isVoiceMuted)}
          title={isVoiceMuted ? 'Speech: MUTED' : 'Speech: ENABLED'}
        >
          {isVoiceMuted ? <VolumeX size={15} /> : <Volume2 size={15} />}
        </button>

        {/* Settings Modal Trigger */}
        <button
          className="hud-icon-btn"
          onClick={() => setIsSettingsOpen(true)}
          title="System Settings"
        >
          <Settings size={15} />
        </button>
      </div>
    </header>
  );
};
