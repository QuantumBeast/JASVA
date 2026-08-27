import React, { useRef, useEffect } from 'react';
import { useJasva } from '../context/JasvaContext';

export const SpherePanel = () => {
  const { sphereState, toggleVoiceListening, togglePanel } = useJasva();
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animFrameId;
    const numParticles = 380;
    const particles = [];
    const goldenRatio = (1 + Math.sqrt(5)) / 2;

    // Generate golden ratio 3D particles
    for (let i = 0; i < numParticles; i++) {
      const lat = Math.asin(1 - (2 * i) / numParticles);
      const lon = (2 * Math.PI * i) / goldenRatio;
      particles.push({
        x: Math.cos(lat) * Math.cos(lon),
        y: Math.cos(lat) * Math.sin(lon),
        z: Math.sin(lat),
        baseSize: Math.random() * 1.6 + 0.7,
        phase: Math.random() * Math.PI * 2,
        speedMultiplier: Math.random() * 0.4 + 0.8
      });
    }

    let angleX = 0.5;
    let angleY = 0.5;
    let angleZ = 0.0;
    let pulseTime = 0;
    let ringRot = 0;

    const resize = () => {
      if (canvas && canvas.parentElement) {
        canvas.width = canvas.parentElement.clientWidth;
        canvas.height = canvas.parentElement.clientHeight;
      }
    };
    resize();
    window.addEventListener('resize', resize);

    const render = () => {
      if (!ctx || !canvas) return;
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      pulseTime += 0.025;
      ringRot += 0.01;

      // State-driven rotation speed & colors
      const isListening = sphereState.isListening;
      const isSpeaking = sphereState.isSpeaking;
      const isProcessing = sphereState.isProcessing;

      let rotSpeed = 0.007;
      let primaryColor = '0, 242, 254'; // Cyan default
      let accentColor = '79, 172, 254';

      if (isListening) {
        rotSpeed = 0.022;
        primaryColor = '0, 255, 135'; // Emerald green
        accentColor = '96, 239, 255';
      } else if (isProcessing) {
        rotSpeed = 0.038;
        primaryColor = '255, 170, 0'; // Solar amber
        accentColor = '255, 85, 0';
      } else if (isSpeaking) {
        rotSpeed = 0.016;
        primaryColor = '79, 172, 254'; // Bright blue
        accentColor = '189, 0, 255';
      }

      angleX += rotSpeed;
      angleY += rotSpeed * 0.75;
      angleZ += rotSpeed * 0.3;

      const cx = canvas.width / 2;
      const cy = canvas.height / 2;
      const baseRadius = Math.min(canvas.width, canvas.height) * 0.36;
      const radius = baseRadius + Math.sin(pulseTime * 2.5) * 6;

      // Draw Center Ambient Glow Halo
      const haloGrad = ctx.createRadialGradient(cx, cy, 5, cx, cy, baseRadius * 1.5);
      haloGrad.addColorStop(0, `rgba(${primaryColor}, ${isListening || isSpeaking ? 0.35 : 0.18})`);
      haloGrad.addColorStop(0.5, `rgba(${accentColor}, ${isProcessing ? 0.25 : 0.08})`);
      haloGrad.addColorStop(1, 'rgba(0, 0, 0, 0)');
      ctx.fillStyle = haloGrad;
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      // Draw Concentric Holographic Reactor Rings
      const ringRadii = [baseRadius * 1.15, baseRadius * 1.35];
      ringRadii.forEach((r, idx) => {
        ctx.save();
        ctx.translate(cx, cy);
        ctx.rotate(idx % 2 === 0 ? ringRot : -ringRot * 0.8);
        ctx.beginPath();
        ctx.ellipse(0, 0, r, r * 0.38, idx * 0.5, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(${primaryColor}, ${0.15 + (idx === 0 ? Math.sin(pulseTime * 3) * 0.08 : 0)})`;
        ctx.lineWidth = 1;
        ctx.setLineDash([6, 12, 18, 6]);
        ctx.stroke();
        ctx.restore();
      });

      const projected = [];

      // 3D Rotation and Projection of Particle Nodes
      particles.forEach((p) => {
        let r = radius;
        if (isSpeaking) {
          r += Math.sin(pulseTime * 6 + p.phase) * 14;
        } else if (isListening) {
          r += Math.sin(pulseTime * 4 + p.phase) * 9;
        } else if (isProcessing) {
          r += Math.cos(pulseTime * 8 + p.phase) * 11;
        }

        let px = p.x * r;
        let py = p.y * r;
        let pz = p.z * r;

        // Rotate Y
        const cosY = Math.cos(angleY);
        const sinY = Math.sin(angleY);
        let x1 = px * cosY + pz * sinY;
        let z1 = -px * sinY + pz * cosY;

        // Rotate X
        const cosX = Math.cos(angleX);
        const sinX = Math.sin(angleX);
        let y2 = py * cosX - z1 * sinX;
        let z2 = py * sinX + z1 * cosX;

        // Perspective projection
        const fov = 420;
        const scale = fov / (fov + z2);
        const x2d = cx + x1 * scale;
        const y2d = cy + y2 * scale;
        const alpha = Math.max(0.12, (z2 + radius) / (2 * radius));

        projected.push({ x: x2d, y: y2d, z: z2, alpha, size: p.baseSize * scale });
      });

      // Draw Connecting Plexus Lines
      const maxDist = 38;
      for (let i = 0; i < projected.length; i++) {
        for (let j = i + 1; j < projected.length; j++) {
          const dx = projected[i].x - projected[j].x;
          const dy = projected[i].y - projected[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);

          if (dist < maxDist) {
            const lineAlpha = (1 - dist / maxDist) * projected[i].alpha * 0.32;
            ctx.beginPath();
            ctx.strokeStyle = `rgba(${primaryColor}, ${lineAlpha})`;
            ctx.lineWidth = 0.75;
            ctx.moveTo(projected[i].x, projected[i].y);
            ctx.lineTo(projected[j].x, projected[j].y);
            ctx.stroke();
          }
        }
      }

      // Draw Particle Nodes with Glow Core
      projected.forEach(p => {
        ctx.beginPath();
        ctx.fillStyle = `rgba(${primaryColor}, ${p.alpha * 0.95})`;
        ctx.arc(p.x, p.y, Math.max(0.6, p.size), 0, Math.PI * 2);
        ctx.fill();
      });

      animFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      window.removeEventListener('resize', resize);
      cancelAnimationFrame(animFrameId);
    };
  }, [sphereState]);

  return (
    <div className="panel-window active-listening-panel" id="activeListeningPanel">
      <div className="panel-header">
        <span className="panel-title">REACTOR CORE</span>
        <button
          className="panel-close-dot"
          onClick={() => togglePanel('activeListeningPanel')}
          title="Close Panel"
        ></button>
      </div>

      <div
        className="visualizer-container"
        onClick={toggleVoiceListening}
        style={{ cursor: 'pointer' }}
        title="Click sphere to start/stop listening"
      >
        <canvas ref={canvasRef} className="waves-canvas" />
        <div className="sphere-status-badge">
          <span className={`sphere-pulse-dot ${sphereState.isListening ? 'listening' : sphereState.isProcessing ? 'processing' : ''}`}></span>
          <span className="instruction">{sphereState.statusLabel}</span>
        </div>
      </div>
    </div>
  );
};
