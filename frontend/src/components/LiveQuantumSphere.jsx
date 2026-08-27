import React, { useRef, useEffect } from 'react';
import { useJasva } from '../context/JasvaContext';

export const LiveQuantumSphere = ({
  mediaStatus,
  size = 260
}) => {
  const {
    sphereState,
    isAlwaysListening,
    isPushToTalk,
    toggleVoiceListening,
    startPushToTalk,
    stopPushToTalk,
    stopSpeaking,
    theme
  } = useJasva();

  const canvasRef = useRef(null);
  const shockwaveRef = useRef([]);
  const pressTimerRef = useRef(null);
  const isLongPressRef = useRef(false);
  const isDraggingRef = useRef(false);
  const dragStartRef = useRef({ x: 0, y: 0 });
  const dragDistanceRef = useRef(0);

  // Inertial physics & interaction state
  const interactionRef = useRef({
    mouseX: 0,
    mouseY: 0,
    targetMouseX: 0,
    targetMouseY: 0,
    cursorScreenX: -1000,
    cursorScreenY: -1000,
    isHovered: false,
    isMouseDown: false,
    velAngleX: 0,
    velAngleY: 0,
    lastMouseX: 0,
    lastMouseY: 0,
    zoomLevel: 1.0,
    targetZoom: 1.0
  });

  const isListening = sphereState.isListening || isAlwaysListening;
  const isSpeaking = sphereState.isSpeaking;
  const isProcessing = sphereState.isProcessing;
  const userIsSpeaking = sphereState.userIsSpeaking;
  const isMusicPlaying = mediaStatus?.playback?.toLowerCase() === 'playing';

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animFrameId;
    const numParticles = 320;
    const particles = [];
    const goldenRatio = (1 + Math.sqrt(5)) / 2;

    // Generate 3D Fibonacci Golden-Ratio Sphere Particles
    for (let i = 0; i < numParticles; i++) {
      const lat = Math.asin(1 - (2 * i) / numParticles);
      const lon = (2 * Math.PI * i) / goldenRatio;
      particles.push({
        x: Math.cos(lat) * Math.cos(lon),
        y: Math.cos(lat) * Math.sin(lon),
        z: Math.sin(lat),
        baseSize: Math.random() * 1.5 + 0.8,
        phase: Math.random() * Math.PI * 2,
        speed: Math.random() * 0.4 + 0.8,
        seed: Math.random()
      });
    }

    let angleX = 0.3;
    let angleY = 0.3;
    let angleZ = 0.0;
    let pulseTime = 0;
    let ringRot = 0;

    // Smooth interpolated colors (RGB)
    let curR = 0, curG = 242, curB = 254; // default Cyan

    // ─── Mouse & Pointer Events ───
    const handleMouseMove = (e) => {
      const rect = canvas.getBoundingClientRect();
      const nx = ((e.clientX - rect.left) / rect.width - 0.5) * 2;
      const ny = ((e.clientY - rect.top) / rect.height - 0.5) * 2;
      interactionRef.current.targetMouseX = nx * 0.7;
      interactionRef.current.targetMouseY = ny * 0.7;
      interactionRef.current.cursorScreenX = e.clientX - rect.left;
      interactionRef.current.cursorScreenY = e.clientY - rect.top;

      // Handle 3D drag rotation if mouse is down
      if (interactionRef.current.isMouseDown) {
        const dx = e.clientX - interactionRef.current.lastMouseX;
        const dy = e.clientY - interactionRef.current.lastMouseY;
        dragDistanceRef.current += Math.sqrt(dx * dx + dy * dy);

        if (dragDistanceRef.current > 6) {
          isDraggingRef.current = true;
          // Clear long press if dragging
          if (pressTimerRef.current) {
            clearTimeout(pressTimerRef.current);
            pressTimerRef.current = null;
          }
        }

        // Apply drag rotation directly
        angleY += dx * 0.008;
        angleX += dy * 0.008;

        interactionRef.current.velAngleY = dx * 0.005;
        interactionRef.current.velAngleX = dy * 0.005;

        interactionRef.current.lastMouseX = e.clientX;
        interactionRef.current.lastMouseY = e.clientY;
      }
    };

    const handleMouseEnter = () => {
      interactionRef.current.isHovered = true;
    };

    const handleMouseLeave = () => {
      interactionRef.current.isHovered = false;
      interactionRef.current.isMouseDown = false;
      interactionRef.current.targetMouseX = 0;
      interactionRef.current.targetMouseY = 0;
      interactionRef.current.cursorScreenX = -1000;
      interactionRef.current.cursorScreenY = -1000;
    };

    const handleWheel = (e) => {
      e.preventDefault();
      const delta = e.deltaY * -0.0015;
      interactionRef.current.targetZoom = Math.min(1.45, Math.max(0.75, interactionRef.current.targetZoom + delta));

      // Trigger interactive subtle ripple
      shockwaveRef.current.push({
        r: size * 0.2,
        maxR: size * 1.1,
        alpha: 0.4
      });
    };

    canvas.addEventListener('mousemove', handleMouseMove);
    canvas.addEventListener('mouseenter', handleMouseEnter);
    canvas.addEventListener('mouseleave', handleMouseLeave);
    canvas.addEventListener('wheel', handleWheel, { passive: false });

    const render = () => {
      if (!ctx || !canvas) return;

      const dpr = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();
      const width = rect.width;
      const height = rect.height;

      if (width === 0 || height === 0) {
        animFrameId = requestAnimationFrame(render);
        return;
      }

      // Sync physical canvas buffer dimensions with DPI
      const targetBufferW = Math.round(width * dpr);
      const targetBufferH = Math.round(height * dpr);
      if (canvas.width !== targetBufferW || canvas.height !== targetBufferH) {
        canvas.width = targetBufferW;
        canvas.height = targetBufferH;
      }

      // Reset transform cleanly every frame
      ctx.save();
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, width, height);

      pulseTime += 0.024;
      ringRot += 0.012;

      // Mouse tracking & Zoom interpolation
      interactionRef.current.mouseX += (interactionRef.current.targetMouseX - interactionRef.current.mouseX) * 0.06;
      interactionRef.current.mouseY += (interactionRef.current.targetMouseY - interactionRef.current.mouseY) * 0.06;
      interactionRef.current.zoomLevel += (interactionRef.current.targetZoom - interactionRef.current.zoomLevel) * 0.1;

      // Apply and damp drag inertia velocity
      if (!interactionRef.current.isMouseDown) {
        angleX += interactionRef.current.velAngleX;
        angleY += interactionRef.current.velAngleY;
        interactionRef.current.velAngleX *= 0.94;
        interactionRef.current.velAngleY *= 0.94;
      }

      // Determine Target RGB & Animation Dynamics based on State
      let targetR = 0, targetG = 242, targetB = 254; // Cyan Default
      let rotSpeed = 0.009;
      let waveAmp = 4;

      // Theme fallback colors for idle state
      if (theme === 'purple') { targetR = 192; targetG = 38; targetB = 211; }
      else if (theme === 'green') { targetR = 0; targetG = 255; targetB = 135; }
      else if (theme === 'orange') { targetR = 255; targetG = 136; targetB = 0; }
      else if (theme === 'red') { targetR = 255; targetG = 59; targetB = 48; }

      if (isPushToTalk) {
        // High-Energy Crimson / Amber Pulse
        targetR = 255; targetG = 45; targetB = 60;
        rotSpeed = 0.045;
        waveAmp = 16;
      } else if (isProcessing) {
        // Ultra Cosmic Violet Swirl
        targetR = 217; targetG = 70; targetB = 239;
        rotSpeed = 0.038;
        waveAmp = 12;
      } else if (isSpeaking) {
        // Solar Radiance / Amber Flare
        targetR = 255; targetG = 170; targetB = 0;
        rotSpeed = 0.022;
        waveAmp = 14 + Math.sin(pulseTime * 6) * 8;
      } else if (userIsSpeaking) {
        // Intense Emerald Response
        targetR = 0; targetG = 255; targetB = 150;
        rotSpeed = 0.032;
        waveAmp = 14;
      } else if (isListening) {
        // Electric Neon Green / Cyan Pulse
        targetR = 0; targetG = 255; targetB = 135;
        rotSpeed = 0.024;
        waveAmp = 10 + Math.sin(pulseTime * 3) * 5;
      } else if (isMusicPlaying) {
        // Duotone Neon Rhythm
        targetR = 0; targetG = 242; targetB = 254;
        rotSpeed = 0.026;
        waveAmp = 12 + Math.sin(pulseTime * 5) * 6;
      }

      // Smooth RGB Glide Transition
      curR += (targetR - curR) * 0.08;
      curG += (targetG - curG) * 0.08;
      curB += (targetB - curB) * 0.08;

      const rInt = Math.round(curR);
      const gInt = Math.round(curG);
      const bInt = Math.round(curB);
      const colorStr = `${rInt}, ${gInt}, ${bInt}`;

      // Update 3D Ambient Rotation Angles with Mouse Physics
      if (!interactionRef.current.isMouseDown) {
        angleX += rotSpeed + interactionRef.current.mouseY * 0.02;
        angleY += rotSpeed * 0.85 + interactionRef.current.mouseX * 0.02;
        angleZ += rotSpeed * 0.35;
      }

      // Exact mathematical center in logical CSS pixels
      const cx = width / 2;
      const cy = height / 2;
      const baseRadius = Math.min(width, height) * 0.35 * interactionRef.current.zoomLevel;
      const radius = baseRadius + Math.sin(pulseTime * 2.2) * (waveAmp * 0.5);

      // ─── 1. Volumetric Energy Core Glow ───
      const coreGrad = ctx.createRadialGradient(cx, cy, 2, cx, cy, baseRadius * 1.4);
      coreGrad.addColorStop(0, `rgba(${colorStr}, ${isSpeaking || isPushToTalk ? 0.45 : isListening ? 0.32 : 0.2})`);
      coreGrad.addColorStop(0.4, `rgba(${colorStr}, ${isProcessing ? 0.28 : 0.12})`);
      coreGrad.addColorStop(1, 'rgba(0, 0, 0, 0)');
      ctx.fillStyle = coreGrad;
      ctx.fillRect(0, 0, width, height);

      // ─── 2. Concentric Holographic Gyro / Orbit Rings ───
      const rings = [
        { r: baseRadius * 1.18, speed: 1.0, dash: [6, 12, 18, 6], width: 1.2 },
        { r: baseRadius * 1.34, speed: -0.75, dash: [4, 10, 4, 10], width: 0.9 },
        { r: baseRadius * 1.48, speed: 0.5, dash: [2, 14], width: 0.7 }
      ];

      rings.forEach((ring, idx) => {
        ctx.save();
        ctx.translate(cx, cy);
        ctx.rotate(ringRot * ring.speed + interactionRef.current.mouseX * 0.15);
        ctx.beginPath();
        ctx.ellipse(0, 0, ring.r, ring.r * 0.34, idx * 0.6, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(${colorStr}, ${0.16 + (idx === 0 ? Math.sin(pulseTime * 3) * 0.08 : 0)})`;
        ctx.lineWidth = ring.width;
        ctx.setLineDash(ring.dash);
        ctx.stroke();
        ctx.restore();
      });

      // ─── 3. Trigger / Render Dynamic Shockwaves ───
      if (Math.random() < (isPushToTalk || isSpeaking ? 0.04 : isListening ? 0.02 : 0.005)) {
        shockwaveRef.current.push({
          r: baseRadius * 0.4,
          maxR: baseRadius * 1.6,
          alpha: 0.5
        });
      }

      for (let s = shockwaveRef.current.length - 1; s >= 0; s--) {
        const sw = shockwaveRef.current[s];
        sw.r += 1.8;
        sw.alpha -= 0.015;
        if (sw.alpha <= 0 || sw.r >= sw.maxR) {
          shockwaveRef.current.splice(s, 1);
          continue;
        }
        ctx.save();
        ctx.beginPath();
        ctx.arc(cx, cy, sw.r, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(${colorStr}, ${sw.alpha * 0.5})`;
        ctx.lineWidth = 1.2;
        ctx.stroke();
        ctx.restore();
      }

      // ─── 4. 3D Particle Transformation & Perspective Projection ───
      const cosX = Math.cos(angleX);
      const sinX = Math.sin(angleX);
      const cosY = Math.cos(angleY);
      const sinY = Math.sin(angleY);
      const cosZ = Math.cos(angleZ);
      const sinZ = Math.sin(angleZ);

      const projected = [];
      const cursorX = interactionRef.current.cursorScreenX;
      const cursorY = interactionRef.current.cursorScreenY;

      particles.forEach((p) => {
        let r = radius;
        // Dynamic harmonic surface waves
        if (isSpeaking) {
          r += Math.sin(pulseTime * 7 + p.phase) * (waveAmp * 0.9);
        } else if (isProcessing) {
          r += Math.sin(pulseTime * 9 + p.phase * 2) * (waveAmp * 0.7);
        } else if (isListening) {
          r += Math.sin(pulseTime * 4 + p.phase) * (waveAmp * 0.6);
        } else if (isMusicPlaying) {
          r += Math.cos(pulseTime * 6 + p.phase) * (waveAmp * 0.8);
        } else {
          r += Math.sin(pulseTime * 2.5 + p.phase) * 3;
        }

        const px = p.x * r;
        const py = p.y * r;
        const pz = p.z * r;

        // Yaw (Y axis)
        const x1 = px * cosY + pz * sinY;
        const y1 = py;
        const z1 = -px * sinY + pz * cosY;

        // Pitch (X axis)
        const x2 = x1;
        const y2 = y1 * cosX - z1 * sinX;
        const z2 = y1 * sinX + z1 * cosX;

        // Roll (Z axis)
        const x3 = x2 * cosZ - y2 * sinZ;
        const y3 = x2 * sinZ + y2 * cosZ;
        const z3 = z2;

        // Perspective Projection centered at (cx, cy)
        const fov = 380;
        const scale = fov / (fov + z3);
        let x2d = cx + x3 * scale;
        let y2d = cy + y3 * scale;

        // Interactive Magnetic Cursor Repulsion Force Field
        if (cursorX > 0 && cursorY > 0) {
          const mdx = x2d - cursorX;
          const mdy = y2d - cursorY;
          const mDist = Math.sqrt(mdx * mdx + mdy * mdy);
          const maxInfluence = 60;
          if (mDist < maxInfluence && mDist > 0) {
            const pushFactor = (1 - mDist / maxInfluence) * 14;
            x2d += (mdx / mDist) * pushFactor;
            y2d += (mdy / mDist) * pushFactor;
          }
        }

        const alpha = Math.max(0.12, Math.min(1.0, (z3 + radius) / (2 * radius)));

        projected.push({
          x: x2d,
          y: y2d,
          z: z3,
          alpha,
          size: Math.max(0.7, p.baseSize * scale * (isSpeaking || isPushToTalk ? 1.25 : 1.0))
        });
      });

      // ─── 5. Plexus Synaptic Connecting Lines ───
      const maxDist = 34 * interactionRef.current.zoomLevel;
      for (let i = 0; i < projected.length; i++) {
        if (projected[i].z < -radius * 0.5) continue;
        for (let j = i + 1; j < projected.length; j++) {
          const dx = projected[i].x - projected[j].x;
          const dy = projected[i].y - projected[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);

          if (dist < maxDist) {
            const lineAlpha = (1 - dist / maxDist) * projected[i].alpha * projected[j].alpha * 0.42;
            ctx.beginPath();
            ctx.strokeStyle = `rgba(${colorStr}, ${lineAlpha})`;
            ctx.lineWidth = 0.75;
            ctx.moveTo(projected[i].x, projected[i].y);
            ctx.lineTo(projected[j].x, projected[j].y);
            ctx.stroke();
          }
        }
      }

      // ─── 6. Glowing Particle Nodes ───
      projected.forEach(p => {
        ctx.beginPath();
        ctx.fillStyle = `rgba(${colorStr}, ${p.alpha * 0.95})`;
        ctx.shadowBlur = p.alpha > 0.6 ? 8 : 0;
        ctx.shadowColor = `rgb(${colorStr})`;
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fill();
        ctx.shadowBlur = 0;
      });

      ctx.restore();
      animFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      canvas.removeEventListener('mousemove', handleMouseMove);
      canvas.removeEventListener('mouseenter', handleMouseEnter);
      canvas.removeEventListener('mouseleave', handleMouseLeave);
      canvas.removeEventListener('wheel', handleWheel);
      cancelAnimationFrame(animFrameId);
    };
  }, [isListening, isSpeaking, isProcessing, userIsSpeaking, isPushToTalk, isMusicPlaying, theme]);

  // ─── Sphere Pointer & Touch Handlers (Click Toggle vs Drag Rotation vs Push-to-Talk) ───
  const handlePointerDown = (e) => {
    if (e.button !== 0 && e.pointerType === 'mouse') return;

    isLongPressRef.current = false;
    isDraggingRef.current = false;
    dragDistanceRef.current = 0;
    dragStartRef.current = { x: e.clientX, y: e.clientY };

    interactionRef.current.isMouseDown = true;
    interactionRef.current.lastMouseX = e.clientX;
    interactionRef.current.lastMouseY = e.clientY;
    interactionRef.current.velAngleX = 0;
    interactionRef.current.velAngleY = 0;

    // Barge-in: if JASVA is currently speaking, tapping/clicking the sphere silences it immediately
    if (isSpeaking) {
      stopSpeaking();
    }

    pressTimerRef.current = setTimeout(() => {
      // Only trigger push-to-talk if not actively dragging
      if (!isDraggingRef.current) {
        isLongPressRef.current = true;
        shockwaveRef.current.push({
          r: size * 0.25,
          maxR: size * 1.5,
          alpha: 0.95
        });
        startPushToTalk();
      }
    }, 250);
  };

  const handlePointerUp = (e) => {
    interactionRef.current.isMouseDown = false;

    if (pressTimerRef.current) {
      clearTimeout(pressTimerRef.current);
      pressTimerRef.current = null;
    }

    if (isDraggingRef.current) {
      // Was a 3D drag rotation gesture; do not trigger click toggle or push-to-talk
      isDraggingRef.current = false;
      return;
    }

    if (isLongPressRef.current) {
      isLongPressRef.current = false;
      stopPushToTalk();
    } else {
      // Interactive Shockwave Pulse
      shockwaveRef.current.push({
        r: size * 0.2,
        maxR: size * 1.25,
        alpha: 0.85
      });
      toggleVoiceListening();
    }
  };

  const handlePointerLeave = () => {
    interactionRef.current.isMouseDown = false;
    if (pressTimerRef.current) {
      clearTimeout(pressTimerRef.current);
      pressTimerRef.current = null;
    }
    if (isLongPressRef.current) {
      isLongPressRef.current = false;
      stopPushToTalk();
    }
  };

  return (
    <div
      className={`live-quantum-sphere-wrap ${isListening ? 'listening' : ''} ${isPushToTalk ? 'push-talk' : ''}`}
      onPointerDown={handlePointerDown}
      onPointerUp={handlePointerUp}
      onPointerLeave={handlePointerLeave}
      onPointerCancel={handlePointerLeave}
      title={
        isPushToTalk
          ? 'PUSH-TO-TALK ACTIVE (Release to Send)'
          : isAlwaysListening
          ? 'SPHERE: ALWAYS LISTENING (Click to Turn Off / Drag to Rotate / Scroll to Zoom)'
          : 'SPHERE: STANDBY (Click to Listen / Hold to Push-to-Talk / Drag to Rotate)'
      }
      style={{
        cursor: 'grab',
        width: `${size}px`,
        height: `${size}px`,
        margin: '0 auto',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        userSelect: 'none',
        touchAction: 'none'
      }}
    >
      <canvas
        ref={canvasRef}
        className="live-quantum-sphere-canvas"
        style={{
          width: `${size}px`,
          height: `${size}px`,
          display: 'block',
          borderRadius: '50%'
        }}
      />
    </div>
  );
};
