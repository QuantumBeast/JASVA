import React, { useState, useEffect } from 'react';
import { useJasva } from '../context/JasvaContext';
import { callBackend } from '../utils/pywebviewBridge';
import { Brain, User, Trash2, Plus, Sparkles, RefreshCw } from 'lucide-react';

export const MemoryTab = () => {
  const { showToast, sendCommand } = useJasva();
  const [profile, setProfile] = useState({ identity: {}, facts: [], preferences: {} });
  const [newFact, setNewFact] = useState('');
  const [loading, setLoading] = useState(false);

  const fetchProfile = () => {
    setLoading(true);
    callBackend('get_memory_profile')
      .then(res => {
        if (res && typeof res === 'object') setProfile(res);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchProfile();
  }, []);

  const handleAddFact = () => {
    if (!newFact.trim()) return;
    const factText = newFact.trim();
    sendCommand(`remember that ${factText}`, true);
    setNewFact('');
    setTimeout(fetchProfile, 1000);
    showToast({ title: 'MEMORY UPDATED', message: `Fact stored: "${factText}"` });
  };

  const handleClearMemory = () => {
    if (window.confirm('Are you sure you want to clear all learned facts and memory?')) {
      callBackend('clear_memory').then(() => {
        fetchProfile();
        showToast({ title: 'MEMORY CLEARED', message: 'All conversational memory reset.' });
      });
    }
  };

  const factsList = Array.isArray(profile.facts) ? profile.facts : [];
  const identityName = profile.identity?.name || 'Operator';
  const identityRole = profile.identity?.role || 'Creator';

  return (
    <div className="tab-pane">
      {/* Identity Card */}
      <div className="device-section">
        <div className="device-section-header">
          <div className="device-section-title-row">
            <User size={13} />
            <span>USER CONTEXT & IDENTITY</span>
          </div>
          <button
            onClick={fetchProfile}
            style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
            title="Refresh memory"
          >
            <RefreshCw size={12} className={loading ? 'spinning' : ''} />
          </button>
        </div>

        <div style={{ display: 'flex', gap: '10px', marginTop: '6px' }}>
          <div
            style={{
              flex: 1,
              background: 'var(--card-bg)',
              border: '1px solid var(--border-color)',
              borderRadius: '8px',
              padding: '8px 10px',
              display: 'flex',
              flexDirection: 'column',
              gap: '2px'
            }}
          >
            <span style={{ fontSize: '9px', color: 'var(--text-muted)', fontFamily: 'JetBrains Mono, monospace' }}>NAME</span>
            <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--accent-color)' }}>{identityName}</span>
          </div>
          <div
            style={{
              flex: 1,
              background: 'var(--card-bg)',
              border: '1px solid var(--border-color)',
              borderRadius: '8px',
              padding: '8px 10px',
              display: 'flex',
              flexDirection: 'column',
              gap: '2px'
            }}
          >
            <span style={{ fontSize: '9px', color: 'var(--text-muted)', fontFamily: 'JetBrains Mono, monospace' }}>ROLE</span>
            <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--success-color)' }}>{identityRole}</span>
          </div>
        </div>
      </div>

      {/* Learned Facts & Memory */}
      <div className="device-section">
        <div className="device-section-header">
          <div className="device-section-title-row">
            <Brain size={13} />
            <span>LEARNED FACTS ({factsList.length})</span>
          </div>
          <button
            onClick={handleClearMemory}
            style={{ background: 'none', border: 'none', color: 'var(--error-color)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px', fontSize: '10px' }}
            title="Wipe Memory"
          >
            <Trash2 size={11} />
            <span>CLEAR</span>
          </button>
        </div>

        {/* Add Fact Input */}
        <div className="device-ip-row" style={{ marginTop: '6px' }}>
          <input
            type="text"
            className="device-ip-input"
            placeholder="Teach JASVA a fact (e.g. My company is Acme Corp)..."
            value={newFact}
            onChange={(e) => setNewFact(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAddFact()}
          />
          <button
            className="device-connect-btn"
            onClick={handleAddFact}
            title="Store Fact in Long-term Memory"
          >
            <Plus size={12} />
            <span>SAVE</span>
          </button>
        </div>

        {/* Facts Feed */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '8px', maxHeight: '180px', overflowY: 'auto' }}>
          {factsList.length === 0 ? (
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', padding: '8px', textAlign: 'center' }}>
              No facts recorded yet. Type above to teach JASVA.
            </div>
          ) : (
            factsList.map((fact, index) => {
              const text = typeof fact === 'string' ? fact : fact.fact || JSON.stringify(fact);
              return (
                <div
                  key={index}
                  style={{
                    background: 'var(--card-bg)',
                    border: '1px solid rgba(0, 242, 254, 0.15)',
                    borderRadius: '6px',
                    padding: '6px 10px',
                    fontSize: '11px',
                    color: 'var(--text-color)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px'
                  }}
                >
                  <Sparkles size={11} color="var(--accent-color)" style={{ flexShrink: 0 }} />
                  <span style={{ flex: 1, wordBreak: 'break-word' }}>{text}</span>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};
