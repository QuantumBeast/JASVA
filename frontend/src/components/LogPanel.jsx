import React, { useRef, useEffect } from 'react';
import { useJasva } from '../context/JasvaContext';

export const LogPanel = () => {
  const { logs, togglePanel } = useJasva();
  const logContainerRef = useRef(null);

  // Auto-scroll logs
  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [logs]);

  return (
    <div className="panel-window command-echo-panel" id="commandEchoPanel">
      <div className="panel-header">
        <span className="panel-title">LOG</span>
        <button
          className="panel-close-dot"
          onClick={() => togglePanel('commandEchoPanel')}
          title="Close Panel"
        ></button>
      </div>

      <div className="bottom-panel-content">
        {/* Diagnostic Logs Feed */}
        <div className="echo-logs-container" ref={logContainerRef}>
          {logs.map((log) => (
            <div key={log.id} className={`echo-log-line ${log.type}`}>
              {log.text}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
