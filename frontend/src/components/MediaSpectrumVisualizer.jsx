import React, { useRef, useEffect } from 'react';

export const MediaSpectrumVisualizer = ({ isPlaying = false, accentColor = '#00f2fe' }) => {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let animationFrameId;
    let tick = 0;

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      canvas.width = rect.width * (window.devicePixelRatio || 1);
      canvas.height = rect.height * (window.devicePixelRatio || 1);
      ctx.scale(window.devicePixelRatio || 1, window.devicePixelRatio || 1);
    };

    resize();
    window.addEventListener('resize', resize);

    const barCount = 24;
    const heights = Array(barCount).fill(2);

    const render = () => {
      const width = canvas.getBoundingClientRect().width;
      const height = canvas.getBoundingClientRect().height;

      ctx.clearRect(0, 0, width, height);

      tick += isPlaying ? 0.08 : 0.02;

      const barWidth = Math.max(2, (width - (barCount - 1) * 3) / barCount);

      for (let i = 0; i < barCount; i++) {
        let targetHeight = 2;
        if (isPlaying) {
          // Dynamic frequency simulation with octave harmonic rhythm
          const v1 = Math.sin(tick + i * 0.4) * 0.5 + 0.5;
          const v2 = Math.cos(tick * 1.5 + i * 0.2) * 0.5 + 0.5;
          const v3 = Math.sin(tick * 2.2 + i * 0.6) * 0.5 + 0.5;
          targetHeight = Math.max(3, (v1 * 0.4 + v2 * 0.35 + v3 * 0.25) * (height - 4));
        } else {
          targetHeight = 2;
        }

        // Smooth interpolation
        heights[i] += (targetHeight - heights[i]) * 0.25;

        const x = i * (barWidth + 3);
        const y = height - heights[i];

        // Gradient for frequency bars
        const grad = ctx.createLinearGradient(0, height, 0, y);
        grad.addColorStop(0, `${accentColor}44`);
        grad.addColorStop(1, accentColor);

        ctx.fillStyle = grad;
        ctx.shadowBlur = isPlaying ? 8 : 0;
        ctx.shadowColor = accentColor;

        // Rounded bar
        ctx.beginPath();
        if (ctx.roundRect) {
          ctx.roundRect(x, y, barWidth, heights[i], [2, 2, 0, 0]);
        } else {
          ctx.rect(x, y, barWidth, heights[i]);
        }
        ctx.fill();
      }

      ctx.shadowBlur = 0;
      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      window.removeEventListener('resize', resize);
      cancelAnimationFrame(animationFrameId);
    };
  }, [isPlaying, accentColor]);

  return (
    <div className="media-spectrum-wrapper">
      <canvas ref={canvasRef} className="media-spectrum-canvas" />
    </div>
  );
};
