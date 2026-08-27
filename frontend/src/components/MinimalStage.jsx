import React, { useState, useRef } from 'react';
import { useJasva } from '../context/JasvaContext';
import { LiveQuantumSphere } from './LiveQuantumSphere';
import { AgentTrace } from './AgentTrace';
import {
  Mic,
  Send,
  Settings
} from 'lucide-react';

export const MinimalStage = ({
  mediaStatus,
  activeOverlay,
  onToggleOverlay
}) => {
  const {
    messages,
    sendCommand,
    sphereState,
    isAlwaysListening,
    isPushToTalk,
    toggleVoiceListening,
    startPushToTalk,
    stopPushToTalk,
    agentTrace,
    isSettingsOpen,
    setIsSettingsOpen,
    theme
  } = useJasva();

  const [inputVal, setInputVal] = useState('');
  const [isThemeOpen, setIsThemeOpen] = useState(false);
  const inputRef = useRef(null);
  const pressTimerRef = useRef(null);
  const isLongPressRef = useRef(false);

  const botMessages = messages.filter(m => m.sender === 'bot');
  const latestMessage = botMessages.length > 0
    ? botMessages[botMessages.length - 1]
    : { text: 'Quantum neural engine online. All systems nominal, sir. How may I assist you today?' };

  const isListening = sphereState.isListening;
  const isSpeaking = sphereState.isSpeaking;
  const isProcessing = sphereState.isProcessing;
  const isMusicPlaying = mediaStatus?.playback?.toLowerCase() === 'playing';

  // Live status ticker
  let statusText = 'QUANTUM CORE // STANDBY';
  if (isPushToTalk) statusText = 'PUSH-TO-TALK // LISTENING';
  else if (isListening) statusText = 'LISTENING // AUDIO STREAM ACTIVE';
  else if (isProcessing) statusText = 'NEURAL ENGINE // REASONING';
  else if (isSpeaking) statusText = 'VOICE SYNTHESIS // ACTIVE';
  else if (agentTrace?.active) statusText = `AGENT // ${agentTrace.currentStep || 'EXECUTING'}`;
  else if (isMusicPlaying && mediaStatus?.title) statusText = `AUDIO // ${mediaStatus.title.toUpperCase()}`;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!inputVal.trim()) return;
    sendCommand(inputVal.trim());
    setInputVal('');
  };

  const handleMicPointerDown = (e) => {
    if (e.button !== 0 && e.pointerType === 'mouse') return;
    isLongPressRef.current = false;

    pressTimerRef.current = setTimeout(() => {
      isLongPressRef.current = true;
      startPushToTalk();
    }, 250);
  };

  const handleMicPointerUp = (e) => {
    if (pressTimerRef.current) {
      clearTimeout(pressTimerRef.current);
      pressTimerRef.current = null;
    }

    if (isLongPressRef.current) {
      isLongPressRef.current = false;
      stopPushToTalk();
    } else {
      toggleVoiceListening();
    }
  };

  const handleMicPointerLeave = () => {
    if (pressTimerRef.current) {
      clearTimeout(pressTimerRef.current);
      pressTimerRef.current = null;
    }
    if (isLongPressRef.current) {
      isLongPressRef.current = false;
      stopPushToTalk();
    }
  };

  const THEMES = [
    { id: 'default', name: 'CYAN', color: '#00f2fe' },
    { id: 'purple', name: 'VIOLET', color: '#c026d3' },
    { id: 'green', name: 'MATRIX', color: '#00ff87' },
    { id: 'orange', name: 'SOLAR', color: '#ff8800' },
    { id: 'red', name: 'CRIMSON', color: '#ff3b30' }
  ];

  return (
    <main className="pure-text-stage">
      {/* ─── TOP STATUS LINE (PURE TEXT) ─── */}
      <header className="pure-top-bar">
        <div className="pure-status-group">
          <span className="pure-brand">JASVA</span>
          <span className="pure-separator">/</span>
          <span className="pure-status">{statusText}</span>
        </div>

        <div className="pure-top-actions">
          <button
            className="pure-text-link"
            onClick={() => setIsSettingsOpen(true)}
            title="Open System Configuration"
          >
            <Settings size={12} />
            <span>SETTINGS</span>
          </button>
        </div>
      </header>

      {/* ─── CENTRAL FOCAL STAGE (LIVE ACTIVE SPHERE + AGENT TRACE + MAIN TEXT) ─── */}
      <section className="pure-center-core">
        {/* Live Active 3D Quantum Reactor Sphere */}
        <LiveQuantumSphere mediaStatus={mediaStatus} size={230} />

        {/* Live Agent Activity, Web Browsing & Execution Trace */}
        <AgentTrace />

        {/* Main Response Text (Large, crisp kinetic text floating in space) */}
        <div className="pure-main-text-stage">
          <p className="pure-main-text">
            {latestMessage.text}
          </p>
        </div>
      </section>

      {/* ─── BOTTOM COMMAND LINE & ACTION LINKS (PURE TEXT) ─── */}
      <footer className="pure-bottom-footer">
        <form className="pure-command-form" onSubmit={handleSubmit}>
          <button
            type="button"
            className={`pure-mic-btn ${isListening ? 'active' : ''} ${isPushToTalk ? 'push-active' : ''}`}
            onPointerDown={handleMicPointerDown}
            onPointerUp={handleMicPointerUp}
            onPointerLeave={handleMicPointerLeave}
            onPointerCancel={handleMicPointerLeave}
            title={
              isPushToTalk
                ? 'PUSH-TO-TALK ACTIVE (Release to Send)'
                : isAlwaysListening
                ? 'VOICE INPUT: ALWAYS ACTIVE (Click to Turn Off / Hold for Push-to-Talk)'
                : 'VOICE INPUT: OFF (Click to Toggle Always-Active / Hold for Push-to-Talk)'
            }
          >
            <Mic size={18} />
          </button>

          <input
            ref={inputRef}
            type="text"
            className="pure-command-input"
            placeholder="Type your command or question..."
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
          />

          <button
            type="submit"
            className="pure-send-btn"
            disabled={!inputVal.trim()}
          >
            <Send size={16} />
          </button>
        </form>

        {/* Pure Text Action Links */}
        <div className="pure-nav-links">
          <button
            className={`pure-nav-btn ${activeOverlay?.media ? 'active' : ''}`}
            onClick={() => onToggleOverlay('media')}
          >
            [ MEDIA ]
          </button>
          <button
            className={`pure-nav-btn ${activeOverlay?.telemetry ? 'active' : ''}`}
            onClick={() => onToggleOverlay('telemetry')}
          >
            [ TELEMETRY ]
          </button>
          <button
            className={`pure-nav-btn ${activeOverlay?.calendar ? 'active' : ''}`}
            onClick={() => onToggleOverlay('calendar')}
          >
            [ CALENDAR ]
          </button>
          <button
            className={`pure-nav-btn ${activeOverlay?.devices ? 'active' : ''}`}
            onClick={() => onToggleOverlay('devices')}
          >
            [ DEVICES ]
          </button>
          <button
            className={`pure-nav-btn ${activeOverlay?.cognition ? 'active' : ''}`}
            onClick={() => onToggleOverlay('cognition')}
          >
            [ LOGS ]
          </button>
          <button
            className={`pure-nav-btn ${isSettingsOpen ? 'active' : ''}`}
            onClick={() => onToggleOverlay('settings')}
          >
            [ SETTINGS ]
          </button>
        </div>
      </footer>
    </main>
  );
};
