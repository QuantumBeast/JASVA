import React, { useRef, useEffect } from 'react';
import { useJasva } from '../context/JasvaContext';

export const InteractiveNeuralCanvas = ({ mediaStatus }) => {
  const canvasRef = useRef(null);
  const { sphereState } = useJasva();

  const sphereRef = useRef(sphereState);
  const mediaRef = useRef(mediaStatus);

  useEffect(() => {
    sphereRef.current = sphereState;
  }, [sphereState]);

  useEffect(() => {
    mediaRef.current = mediaStatus;
  }, [mediaStatus]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let animationFrameId;

    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    const handleResize = () => {
      if (!canvas) return;
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
      initParticles();
    };

    window.addEventListener('resize', handleResize);

    // Mouse tracking
    const mouse = {
      x: width / 2,
      y: height / 2,
      targetX: width / 2,
      targetY: height / 2,
      radius: 180,
      isMoving: false,
      lastMoveTime: 0
    };

    const handleMouseMove = (e) => {
      mouse.targetX = e.clientX;
      mouse.targetY = e.clientY;
      mouse.isMoving = true;
      mouse.lastMoveTime = Date.now();
    };

    const handleClick = (e) => {
      createShockwave(e.clientX, e.clientY);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('click', handleClick);

    // Particle system configuration
    const PARTICLE_COUNT = Math.min(100, Math.floor((width * height) / 14000));
    let particles = [];
    let shockwaves = [];

    const createShockwave = (x, y) => {
      shockwaves.push({
        x,
        y,
        radius: 10,
        maxRadius: 220,
        opacity: 0.8,
        speed: 8
      });
    };

    class Particle {
      constructor() {
        this.reset();
      }

      reset() {
        this.x = Math.random() * width;
        this.y = Math.random() * height;
        this.vx = (Math.random() - 0.5) * 1.2;
        this.vy = (Math.random() - 0.5) * 1.2;
        this.baseRadius = Math.random() * 2 + 1;
        this.radius = this.baseRadius;
        this.angle = Math.random() * Math.PI * 2;
        this.orbitRadius = Math.random() * 180 + 40;
        this.orbitSpeed = (Math.random() * 0.02 + 0.005) * (Math.random() > 0.5 ? 1 : -1);
      }

      update(state, isMusic) {
        // Smooth mouse position interpolation
        mouse.x += (mouse.targetX - mouse.x) * 0.1;
        mouse.y += (mouse.targetY - mouse.y) * 0.1;

        // Dynamic State Multipliers
        let speedMult = 1.0;
        if (state.isListening) speedMult = 2.4;
        else if (state.isSpeaking) speedMult = 2.0;
        else if (state.isProcessing) speedMult = 3.2;
        else if (isMusic) speedMult = 1.8;

        // Vortex / Orbit behavior during thinking / processing
        if (state.isProcessing) {
          this.angle += this.orbitSpeed * 2.5;
          const cx = width / 2;
          const cy = height / 2;
          this.x += (cx + Math.cos(this.angle) * this.orbitRadius - this.x) * 0.04;
          this.y += (cy + Math.sin(this.angle) * this.orbitRadius - this.y) * 0.04;
        } else {
          // Standard fluid drift
          this.x += this.vx * speedMult;
          this.y += this.vy * speedMult;

          // Wrap edges smoothly
          if (this.x < 0) this.x = width;
          if (this.x > width) this.x = 0;
          if (this.y < 0) this.y = height;
          if (this.y > height) this.y = 0;
        }

        // Mouse Gravitational & Repulsion Physics
        const dx = mouse.x - this.x;
        const dy = mouse.y - this.y;
        const dist = Math.sqrt(dx * dx + dy * dy);

        if (dist < mouse.radius && dist > 0) {
          const force = (1 - dist / mouse.radius);
          if (state.isListening) {
            // Attraction when listening
            this.x += (dx / dist) * force * 3.5;
            this.y += (dy / dist) * force * 3.5;
          } else {
            // Gentle electromagnetic repulsion & orbit
            const angle = Math.atan2(dy, dx);
            this.x -= Math.cos(angle) * force * 4.5;
            this.y -= Math.sin(angle) * force * 4.5;
          }
        }

        // Reactivity to Shockwaves
        for (let sw of shockwaves) {
          const sDx = this.x - sw.x;
          const sDy = this.y - sw.y;
          const sDist = Math.sqrt(sDx * sDx + sDy * sDy);
          if (Math.abs(sDist - sw.radius) < 25) {
            const push = (1 - Math.abs(sDist - sw.radius) / 25) * 6;
            this.x += (sDx / (sDist || 1)) * push;
            this.y += (sDy / (sDist || 1)) * push;
          }
        }

        // Dynamic pulsing radius based on state
        if (state.isSpeaking) {
          this.radius = this.baseRadius * (1 + Math.sin(Date.now() * 0.008 + this.x) * 0.8);
        } else if (state.isListening) {
          this.radius = this.baseRadius * (1 + Math.cos(Date.now() * 0.012 + this.y) * 0.6);
        } else if (isMusic) {
          this.radius = this.baseRadius * (1 + Math.sin(Date.now() * 0.006 + this.x * 0.1) * 0.7);
        } else {
          this.radius = this.baseRadius;
        }
      }

      draw(ctx, state, isMusic) {
        let color = 'rgba(0, 242, 254, ';
        let glowColor = '#00f2fe';

        if (state.isListening) {
          color = 'rgba(0, 242, 254, ';
          glowColor = '#00f2fe';
        } else if (state.isSpeaking) {
          color = 'rgba(255, 170, 0, ';
          glowColor = '#ffaa00';
        } else if (state.isProcessing) {
          color = 'rgba(192, 38, 211, ';
          glowColor = '#c026d3';
        } else if (isMusic) {
          color = 'rgba(168, 85, 247, ';
          glowColor = '#a855f7';
        }

        ctx.beginPath();
        ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
        ctx.fillStyle = `${color}0.85)`;
        ctx.shadowColor = glowColor;
        ctx.shadowBlur = state.isSpeaking || state.isListening ? 12 : 6;
        ctx.fill();
        ctx.shadowBlur = 0;
      }
    }

    const initParticles = () => {
      particles = [];
      for (let i = 0; i < PARTICLE_COUNT; i++) {
        particles.push(new Particle());
      }
    };

    initParticles();

    // Render loop
    const render = () => {
      ctx.clearRect(0, 0, width, height);

      const state = sphereRef.current || {};
      const isMusic = mediaRef.current?.playback?.toLowerCase() === 'playing';

      // Determine Synaptic Line Color
      let lineBaseColor = '0, 242, 254';
      if (state.isListening) lineBaseColor = '0, 242, 254';
      else if (state.isSpeaking) lineBaseColor = '255, 170, 0';
      else if (state.isProcessing) lineBaseColor = '192, 38, 211';
      else if (isMusic) lineBaseColor = '168, 85, 247';

      // Update and draw shockwaves
      for (let i = shockwaves.length - 1; i >= 0; i--) {
        const sw = shockwaves[i];
        sw.radius += sw.speed;
        sw.opacity *= 0.94;

        ctx.beginPath();
        ctx.arc(sw.x, sw.y, sw.radius, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(${lineBaseColor}, ${sw.opacity})`;
        ctx.lineWidth = 1.8;
        ctx.shadowColor = `rgb(${lineBaseColor})`;
        ctx.shadowBlur = 10;
        ctx.stroke();
        ctx.shadowBlur = 0;

        if (sw.radius >= sw.maxRadius || sw.opacity <= 0.01) {
          shockwaves.splice(i, 1);
        }
      }

      // Update particles
      for (let p of particles) {
        p.update(state, isMusic);
        p.draw(ctx, state, isMusic);
      }

      // Draw Synaptic Neural Lines between close particles
      const maxDistance = state.isProcessing ? 140 : 115;
      const particleLen = particles.length;

      for (let i = 0; i < particleLen; i++) {
        const p1 = particles[i];

        // Connect to mouse if near
        const mDist = Math.hypot(p1.x - mouse.x, p1.y - mouse.y);
        if (mDist < 140) {
          const mAlpha = (1 - mDist / 140) * 0.5;
          ctx.beginPath();
          ctx.moveTo(p1.x, p1.y);
          ctx.lineTo(mouse.x, mouse.y);
          ctx.strokeStyle = `rgba(${lineBaseColor}, ${mAlpha})`;
          ctx.lineWidth = 1.2;
          ctx.stroke();
        }

        // Connect to neighboring particles
        for (let j = i + 1; j < particleLen; j++) {
          const p2 = particles[j];
          const dist = Math.hypot(p1.x - p2.x, p1.y - p2.y);

          if (dist < maxDistance) {
            const alpha = (1 - dist / maxDistance) * (state.isProcessing ? 0.45 : 0.25);
            ctx.beginPath();
            ctx.moveTo(p1.x, p1.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.strokeStyle = `rgba(${lineBaseColor}, ${alpha})`;
            ctx.lineWidth = 0.8;
            ctx.stroke();
          }
        }
      }

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('click', handleClick);
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="interactive-neural-canvas"
    />
  );
};
