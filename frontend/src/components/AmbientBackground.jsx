import React from 'react';
import { useJasva } from '../context/JasvaContext';

export const AmbientBackground = ({ mediaStatus }) => {
  const { sphereState } = useJasva();

  const isListening = sphereState.isListening;
  const isSpeaking = sphereState.isSpeaking;
  const isProcessing = sphereState.isProcessing;
  const isMusicPlaying = mediaStatus?.playback?.toLowerCase() === 'playing';

  let modeClass = 'mode-standby';
  if (isListening) modeClass = 'mode-listening';
  else if (isSpeaking) modeClass = 'mode-speaking';
  else if (isProcessing) modeClass = 'mode-processing';
  else if (isMusicPlaying) modeClass = 'mode-music';

  return (
    <div className={`ambient-quantum-backdrop ${modeClass}`}>
      {/* Dynamic ambient color orbs */}
      <div className="ambient-glow-orb orb-primary"></div>
      <div className="ambient-glow-orb orb-secondary"></div>
      <div className="ambient-glow-orb orb-accent"></div>

      {/* Cybernetic grid lines with subtle opacity */}
      <div className="ambient-hologram-mesh"></div>

      {/* Rhythmic background audio/neural waves */}
      <div className="ambient-wave-lines">
        <div className="wave-ring ring-1"></div>
        <div className="wave-ring ring-2"></div>
        <div className="wave-ring ring-3"></div>
      </div>
    </div>
  );
};
