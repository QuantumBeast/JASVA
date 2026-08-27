import React from 'react';
import { DraggableWidget } from './DraggableWidget';
import { useJasva } from '../context/JasvaContext';
import { Activity, Cpu, HardDrive, Zap, Radio } from 'lucide-react';

export const TelemetryWidget = ({ initialPos = { x: window.innerWidth - 320, y: 80 } }) => {
  const { metrics, metricHistory, telemetry } = useJasva();

  const renderSparkline = (data = [], color = 'var(--accent-color)') => {
    if (!data.length) return null;
    const max = 100;
    const points = data
      .map((val, idx) => {
        const x = (idx / (data.length - 1)) * 90;
        const y = 20 - (val / max) * 18;
        return `${x},${y}`;
      })
      .join(' ');

    return (
      <svg className="widget-sparkline" viewBox="0 0 90 22">
        <polyline fill="none" stroke={color} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" points={points} />
      </svg>
    );
  };

  return (
    <DraggableWidget
      id="telemetry"
      title="TELEMETRY // GAUGES"
      icon={Activity}
      initialPos={initialPos}
      width={310}
    >
      <div className="telemetry-widget-content">
        {/* Metric Grid */}
        <div className="telemetry-compact-grid">
          {/* CPU */}
          <div className="telemetry-metric-tile">
            <div className="tile-header">
              <Cpu size={12} className="tile-icon cpu" />
              <span className="tile-label">CPU</span>
              <span className="tile-value">{metrics.cpu || 0}%</span>
            </div>
            {renderSparkline(metricHistory?.cpu, 'var(--accent-color)')}
          </div>

          {/* RAM */}
          <div className="telemetry-metric-tile">
            <div className="tile-header">
              <Zap size={12} className="tile-icon ram" />
              <span className="tile-label">RAM</span>
              <span className="tile-value">{metrics.ram || 0}%</span>
            </div>
            {renderSparkline(metricHistory?.ram, 'var(--accent-secondary)')}
          </div>

          {/* GPU */}
          <div className="telemetry-metric-tile">
            <div className="tile-header">
              <Activity size={12} className="tile-icon gpu" />
              <span className="tile-label">GPU</span>
              <span className="tile-value">{metrics.gpu || 0}%</span>
            </div>
            {renderSparkline(metricHistory?.gpu, 'var(--success-color)')}
          </div>

          {/* DISK */}
          <div className="telemetry-metric-tile">
            <div className="tile-header">
              <HardDrive size={12} className="tile-icon disk" />
              <span className="tile-label">DISK</span>
              <span className="tile-value">{metrics.disk || 0}%</span>
            </div>
            {renderSparkline(metricHistory?.disk, 'var(--warning-color)')}
          </div>
        </div>

        {/* Live Network & Clock Ping */}
        <div className="telemetry-bottom-strip">
          <span className="telemetry-live-dot"></span>
          <span className="telemetry-ping-text">{telemetry?.ping || '12ms'}</span>
          <span className="telemetry-os-tag">{metrics.os || 'WINDOWS'}</span>
        </div>
      </div>
    </DraggableWidget>
  );
};
