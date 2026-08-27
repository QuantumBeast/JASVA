import React, { useRef, useEffect } from 'react';
import { DraggableWidget } from './DraggableWidget';
import { useJasva } from '../context/JasvaContext';
import { Terminal, Sparkles, Brain } from 'lucide-react';

export const CognitionWidget = ({ initialPos = { x: window.innerWidth - 320, y: 340 } }) => {
  const { logs, agentTrace } = useJasva();
  const listRef = useRef(null);

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [logs, agentTrace]);

  return (
    <DraggableWidget
      id="cognition"
      title="COGNITION // LOGS"
      icon={Terminal}
      initialPos={initialPos}
      width={310}
    >
      <div className="cognition-widget-content">
        {/* Agent Thought Banner (if active) */}
        {agentTrace?.active && (
          <div className="cognition-thought-pill">
            <Brain size={10} className="cognition-brain-pulse" />
            <span className="cognition-thought-text">{agentTrace.currentStep || 'Executing cognitive loop...'}</span>
          </div>
        )}

        {/* Streaming Logs */}
        <div className="cognition-logs-stream" ref={listRef}>
          {logs.slice(-15).map((log) => (
            <div key={log.id} className={`cognition-log-row ${log.type || 'system'}`}>
              <span className="log-prefix">›</span>
              <span className="log-body-text">{log.text}</span>
            </div>
          ))}
        </div>
      </div>
    </DraggableWidget>
  );
};
