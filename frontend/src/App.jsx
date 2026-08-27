import React, { useState, useEffect } from 'react';
import { useJasva } from './context/JasvaContext';
import { InteractiveNeuralCanvas } from './components/InteractiveNeuralCanvas';
import { MinimalStage } from './components/MinimalStage';
import { MediaWidget } from './components/MediaWidget';
import { TelemetryWidget } from './components/TelemetryWidget';
import { CalendarWidget } from './components/CalendarWidget';
import { CognitionWidget } from './components/CognitionWidget';
import { DeviceWidget } from './components/DeviceWidget';
import { SettingsModal } from './components/SettingsModal';
import { ToastContainer } from './components/ToastContainer';
import { callBackend } from './utils/pywebviewBridge';

export const App = () => {
  const { isSettingsOpen, setIsSettingsOpen } = useJasva();
  const [mediaStatus, setMediaStatus] = useState(null);

  // Widget visibility toggles (all visible by default across fullscreen)
  const [widgets, setWidgets] = useState({
    media: true,
    telemetry: true,
    calendar: true,
    devices: true,
    cognition: true
  });

  // Poll media status for moving background & widgets
  useEffect(() => {
    let mounted = true;
    const pollMedia = async () => {
      try {
        const res = await callBackend('get_media_status');
        if (res && res.status !== 'error' && mounted) {
          setMediaStatus(res);
        }
      } catch (_) {}
    };
    pollMedia();
    const interval = setInterval(pollMedia, 2500);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  // F11 hotkey to toggle fullscreen mode
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'F11') {
        e.preventDefault();
        callBackend('toggle_fullscreen');
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const handleToggleOverlay = (key) => {
    if (key === 'settings') {
      setIsSettingsOpen(prev => !prev);
      return;
    }
    setWidgets(prev => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <div className="pure-fullscreen-app">
      {/* ─── 1. MOVING INTERACTIVE NEURAL BACKGROUND ─── */}
      <InteractiveNeuralCanvas mediaStatus={mediaStatus} />

      {/* ─── 2. CENTRAL FOCAL STAGE (HEADING + MAIN TEXT + COMMAND INPUT) ─── */}
      <MinimalStage
        mediaStatus={mediaStatus}
        activeOverlay={widgets}
        onToggleOverlay={handleToggleOverlay}
      />

      {/* ─── 3. DRAGGABLE HOLOGRAPHIC WIDGETS (DRAGGABLE BY HEADING ONLY) ─── */}
      {widgets.media && (
        <MediaWidget initialPos={{ x: 40, y: 70 }} />
      )}

      {widgets.calendar && (
        <CalendarWidget initialPos={{ x: 40, y: 310 }} />
      )}

      {widgets.telemetry && (
        <TelemetryWidget initialPos={{ x: window.innerWidth - 320, y: 70 }} />
      )}

      {widgets.cognition && (
        <CognitionWidget initialPos={{ x: window.innerWidth - 320, y: 310 }} />
      )}

      {widgets.devices && (
        <DeviceWidget initialPos={{ x: window.innerWidth - 320, y: 550 }} />
      )}

      {/* Overlays & Modals */}
      <SettingsModal />
      <ToastContainer />
    </div>
  );
};

export default App;
