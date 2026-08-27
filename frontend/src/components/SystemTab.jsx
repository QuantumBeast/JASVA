import React, { useRef, useEffect } from 'react';
import { useJasva } from '../context/JasvaContext';

const RingGauge = ({ value, color, label, size = 68 }) => {
  const strokeWidth = 5;
  const radius = (size - strokeWidth * 2) / 2;
  const circumference = 2 * Math.PI * radius;
  const clampedValue = Math.min(100, Math.max(0, value));
  const offset = circumference - (clampedValue / 100) * circumference;

  return (
    <div className="gauge-item">
      <div className="gauge-svg-wrapper" style={{ width: size, height: size }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
          {/* Background Ring Track */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke="rgba(255, 255, 255, 0.08)"
            strokeWidth={strokeWidth}
            fill="none"
          />
          {/* Glowing Value Arc */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke={color}
            strokeWidth={strokeWidth}
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            fill="none"
            transform={`rotate(-90 ${size / 2} ${size / 2})`}
            style={{
              transition: 'stroke-dashoffset 0.6s cubic-bezier(0.4, 0, 0.2, 1)',
              filter: `drop-shadow(0 0 6px ${color})`
            }}
          />
        </svg>
        <div className="gauge-center-text">
          <span className="gauge-val">{clampedValue}%</span>
        </div>
      </div>
      <span className="gauge-title">{label}</span>
    </div>
  );
};

const SparklineGraph = ({ data, color }) => {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (!data || data.length < 2) return;

    const w = canvas.width;
    const h = canvas.height;
    const step = w / (data.length - 1);

    ctx.beginPath();
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;

    data.forEach((val, i) => {
      const x = i * step;
      const y = h - (val / 100) * (h - 4) - 2;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    ctx.lineTo(w, h);
    ctx.lineTo(0, h);
    ctx.closePath();
    ctx.fillStyle = color.replace('1)', '0.12)').replace('rgb', 'rgba');
    ctx.fill();
  }, [data, color]);

  return <canvas ref={canvasRef} className="metric-graph" width={280} height={24} />;
};

export const SystemTab = () => {
  const { metrics, metricHistory } = useJasva();

  const metricsData = [
    { key: 'CPU', label: 'CPU', value: metrics.cpu, history: metricHistory.cpu, color: 'rgba(0, 242, 254, 1)' },
    { key: 'RAM', label: 'RAM', value: metrics.ram, history: metricHistory.ram, color: 'rgba(189, 0, 255, 1)' },
    { key: 'GPU', label: 'GPU', value: metrics.gpu, history: metricHistory.gpu, color: 'rgba(0, 255, 135, 1)' },
    { key: 'DISK', label: 'DISK', value: metrics.disk, history: metricHistory.disk, color: 'rgba(255, 136, 0, 1)' }
  ];

  return (
    <div className="tab-pane">
      {/* 2x2 Circular Holographic Gauges Grid */}
      <div className="gauges-2x2-grid">
        {metricsData.map((m) => (
          <RingGauge
            key={m.key}
            label={m.label}
            value={m.value}
            color={m.color}
          />
        ))}
      </div>

      {/* Real-time Telemetry Sparklines */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '10px' }}>
        {metricsData.map((m) => (
          <div key={m.key} className="sparkline-row-card">
            <div className="sparkline-header">
              <span style={{ fontSize: '10px', fontWeight: 700, fontFamily: 'Outfit, sans-serif', color: m.color }}>
                {m.label} TELEMETRY
              </span>
              <span style={{ fontSize: '11px', fontWeight: 800, fontFamily: 'JetBrains Mono, monospace', color: '#fff' }}>
                {m.value}%
              </span>
            </div>
            <SparklineGraph data={m.history} color={m.color} />
          </div>
        ))}
      </div>
    </div>
  );
};
