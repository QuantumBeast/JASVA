import React from 'react';
import { useJasva } from '../context/JasvaContext';
import { Clock, Sun, Tv, Smartphone, Cpu, Brain, Sparkles } from 'lucide-react';

export const PortalHeader = () => {
  const { telemetry, tvStatus, phoneStatus, togglePanel, setHubActiveTab } = useJasva();

  return (
    <div className="panel-window portal-greeting-panel" id="portalGreetingPanel">
      <div className="panel-header" style={{ marginBottom: '6px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Sparkles size={12} color="var(--accent-color)" />
          <span className="panel-title">SYSTEM STATUS & SHORTCUTS</span>
        </div>
        <button
          className="panel-close-dot"
          onClick={() => togglePanel('activeListeningPanel')}
          title="Close Status"
        ></button>
      </div>

      <div className="portal-telemetry">
        {/* Clock & Date */}
        <div className="telemetry-pill">
          <Clock size={13} color="var(--accent-color)" />
          <span className="clock-time">{telemetry.time}</span>
          <span className="clock-date-badge">{telemetry.date}</span>
        </div>

        {/* Weather */}
        <div className="telemetry-pill">
          <Sun size={13} color="var(--success-color)" />
          <span className="temp-text">{telemetry.temp || '24°C'}</span>
          <span style={{ fontSize: '9px', color: 'var(--text-muted)' }}>
            {telemetry.loc || 'NOMINAL'}
          </span>
        </div>

        {/* Skills Shortcut */}
        <div
          className="telemetry-pill device-pill online"
          onClick={() => setHubActiveTab('skills')}
          style={{ cursor: 'pointer' }}
          title="Open Installed Skills"
        >
          <Cpu size={13} color="var(--accent-color)" />
          <span>SKILLS</span>
        </div>

        {/* Memory Shortcut */}
        <div
          className="telemetry-pill device-pill online"
          onClick={() => setHubActiveTab('memory')}
          style={{ cursor: 'pointer' }}
          title="Open Learned Memory"
        >
          <Brain size={13} color="var(--accent-secondary)" />
          <span>MEMORY</span>
        </div>

        {/* TV Status Pill */}
        <div
          className={`telemetry-pill device-pill ${tvStatus.connected ? 'online' : 'offline'}`}
          onClick={() => setHubActiveTab('tv')}
          style={{ cursor: 'pointer' }}
          title="Open Smart TV Remote"
        >
          <Tv size={13} />
          <span>{tvStatus.connected ? 'TV: ONLINE' : 'TV: REMOTE'}</span>
        </div>

        {/* Phone Status Pill */}
        <div
          className={`telemetry-pill device-pill ${phoneStatus.connected ? 'online' : 'offline'}`}
          onClick={() => setHubActiveTab('phone')}
          style={{ cursor: 'pointer' }}
          title="Open Phone Controller"
        >
          <Smartphone size={13} />
          <span>{phoneStatus.connected ? 'PHONE: ONLINE' : 'PHONE: LINK'}</span>
        </div>
      </div>
    </div>
  );
};
