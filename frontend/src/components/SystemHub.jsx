import React, { useState } from 'react';
import { useJasva } from '../context/JasvaContext';
import { Activity, Smartphone, Tv, Cpu, Brain } from 'lucide-react';
import { SystemTab } from './SystemTab';
import { PhoneTab } from './PhoneTab';
import { TvTab } from './TvTab';
import { SkillsTab } from './SkillsTab';
import { MemoryTab } from './MemoryTab';

export const SystemHub = () => {
  const { metrics, togglePanel } = useJasva();
  const [activeTab, setActiveTab] = useState('system');

  return (
    <div className="panel-window right-panel system-panel" id="systemPanel">
      {/* Header */}
      <div className="panel-header">
        <div className="panel-title-group">
          <span className="panel-title">JARVIS CORE HUB</span>
          <span style={{ fontSize: '9px', fontFamily: 'JetBrains Mono, monospace', color: 'var(--text-muted)' }}>
            {metrics.os}
          </span>
        </div>
        <button
          className="panel-close-dot"
          onClick={() => togglePanel('systemPanel')}
          title="Close Panel"
        ></button>
      </div>

      {/* Segmented Tab Selector */}
      <div className="panel-tab-bar">
        <button
          className={`panel-tab-btn ${activeTab === 'system' ? 'active' : ''}`}
          onClick={() => setActiveTab('system')}
          title="System Resource Telemetry"
        >
          <Activity size={12} />
          <span>SYSTEM</span>
        </button>
        <button
          className={`panel-tab-btn ${activeTab === 'skills' ? 'active' : ''}`}
          onClick={() => setActiveTab('skills')}
          title="Agentic Skills & Tools"
        >
          <Cpu size={12} />
          <span>SKILLS</span>
        </button>
        <button
          className={`panel-tab-btn ${activeTab === 'memory' ? 'active' : ''}`}
          onClick={() => setActiveTab('memory')}
          title="Learned Memory & Profile"
        >
          <Brain size={12} />
          <span>MEMORY</span>
        </button>
        <button
          className={`panel-tab-btn ${activeTab === 'phone' ? 'active' : ''}`}
          onClick={() => setActiveTab('phone')}
          title="Phone Remote & Mirror"
        >
          <Smartphone size={12} />
          <span>PHONE</span>
        </button>
        <button
          className={`panel-tab-btn ${activeTab === 'tv' ? 'active' : ''}`}
          onClick={() => setActiveTab('tv')}
          title="Smart TV Remote"
        >
          <Tv size={12} />
          <span>TV</span>
        </button>
      </div>

      {/* Tab Panes */}
      {activeTab === 'system' && <SystemTab />}
      {activeTab === 'skills' && <SkillsTab />}
      {activeTab === 'memory' && <MemoryTab />}
      {activeTab === 'phone' && <PhoneTab />}
      {activeTab === 'tv' && <TvTab />}
    </div>
  );
};
