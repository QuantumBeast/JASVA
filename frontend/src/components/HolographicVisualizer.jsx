import React, { useRef, useEffect } from 'react';

export const HolographicVisualizer = ({
  isListening = false,
  isSpeaking = false,
  isProcessing = false,
  isMusicPlaying = false,
  themeColor = '#00f2fe'
}) => {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let animationFrameId;
    let phase = 0;

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      canvas.width = rect.width * (window.devicePixelRatio || 1);
      canvas.height = rect.height * (window.devicePixelRatio || 1);
      ctx.scale(window.devicePixelRatio || 1, window.devicePixelRatio || 1);
    };

    resize();
    window.addEventListener('resize', resize);

    const render = () => {
      const width = canvas.getBoundingClientRect().width;
      const height = canvas.getBoundingClientRect().height;
      const centerY = height / 2;

      ctx.clearRect(0, 0, width, height);

      // Determine state parameters
      let baseAmp = 4;
      let speed = 0.03;
      let primaryColor = themeColor || '#00f2fe';
      let secondaryColor = '#4facfe';

      if (isMusicPlaying) {
        baseAmp = 12 + Math.sin(phase * 3) * 4;
        speed = 0.07;
        primaryColor = '#00f2fe';
        secondaryColor = '#c026d3';
      } else if (isSpeaking) {
        baseAmp = 14 + Math.sin(phase * 4) * 6;
        speed = 0.08;
        primaryColor = '#ffaa00';
        secondaryColor = '#ff5500';
      } else if (isListening) {
        baseAmp = 10 + Math.sin(phase * 2) * 5;
        speed = 0.06;
        primaryColor = '#00ff87';
        secondaryColor = '#00f2fe';
      } else if (isProcessing) {
        baseAmp = 8;
        speed = 0.09;
        primaryColor = '#d946ef';
        secondaryColor = '#a855f7';
      }

      phase += speed;

      // Draw 3 layered harmonic sine waves with holographic glow
      const waves = [
        { freq: 0.02, amp: baseAmp * 1.0, offset: 0, alpha: 0.85, width: 2.2, color: primaryColor },
        { freq: 0.035, amp: baseAmp * 0.7, offset: 2, alpha: 0.5, width: 1.5, color: secondaryColor },
        { freq: 0.015, amp: baseAmp * 0.45, offset: 4, alpha: 0.35, width: 1.2, color: '#ffffff' }
      ];

      waves.forEach(wave => {
        ctx.beginPath();
        ctx.lineWidth = wave.width;
        ctx.strokeStyle = wave.color;
        ctx.globalAlpha = wave.alpha;
        ctx.shadowBlur = 10;
        ctx.shadowColor = wave.color;

        for (let x = 0; x < width; x++) {
          // Window envelope (tapers ends to 0 so wave blends smoothly)
          const envelope = Math.sin((x / width) * Math.PI);
          const y = centerY + Math.sin(x * wave.freq + phase + wave.offset) * wave.amp * envelope;

          if (x === 0) {
            ctx.moveTo(x, y);
          } else {
            ctx.lineTo(x, y);
          }
        }
        ctx.stroke();
      });

      ctx.globalAlpha = 1.0;
      ctx.shadowBlur = 0;

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      window.removeEventListener('resize', resize);
      cancelAnimationFrame(animationFrameId);
    };
  }, [isListening, isSpeaking, isProcessing, isMusicPlaying, themeColor]);

  return (
    <div className="holographic-waveform-wrapper">
      <canvas ref={canvasRef} className="holographic-waveform-canvas" />
    </div>
  );
};
