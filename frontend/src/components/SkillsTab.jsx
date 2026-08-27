import React, { useState, useEffect } from 'react';
import { useJasva } from '../context/JasvaContext';
import { callBackend } from '../utils/pywebviewBridge';
import { Cpu, Terminal, Globe, Calendar, CheckCircle2, RefreshCw } from 'lucide-react';

export const SkillsTab = () => {
  const [skills, setSkills] = useState([]);
  const [loading, setLoading] = useState(false);

  const fetchSkills = () => {
    setLoading(true);
    callBackend('get_plugins_list')
      .then(res => {
        if (Array.isArray(res)) setSkills(res);
        else setSkills([]);
      })
      .catch(() => setSkills([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchSkills();
  }, []);

  const getSkillIcon = (name) => {
    if (name.includes('code') || name.includes('coding')) return <Terminal size={14} color="var(--accent-color)" />;
    if (name.includes('web') || name.includes('research')) return <Globe size={14} color="var(--success-color)" />;
    if (name.includes('calendar') || name.includes('notes')) return <Calendar size={14} color="var(--warning-color)" />;
    return <Cpu size={14} color="var(--accent-secondary)" />;
  };

  return (
    <div className="tab-pane">
      <div className="device-section">
        <div className="device-section-header">
          <div className="device-section-title-row">
            <Cpu size={13} />
            <span>AGENTIC SKILLS & TOOLS</span>
          </div>
          <button
            onClick={fetchSkills}
            style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
            title="Refresh skills"
          >
            <RefreshCw size={12} className={loading ? 'spinning' : ''} />
          </button>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '6px' }}>
          {skills.length === 0 ? (
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', padding: '10px', textAlign: 'center' }}>
              No custom skills loaded.
            </div>
          ) : (
            skills.map((skill, index) => (
              <div
                key={index}
                style={{
                  background: 'var(--card-bg)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '10px',
                  padding: '10px 12px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '4px'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    {getSkillIcon(skill.name)}
                    <span style={{ fontSize: '12px', fontWeight: 700, fontFamily: 'Outfit, sans-serif', color: 'var(--text-color)' }}>
                      {skill.name.toUpperCase()}
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <CheckCircle2 size={11} color="var(--success-color)" />
                    <span style={{ fontSize: '9px', fontFamily: 'JetBrains Mono, monospace', color: 'var(--success-color)' }}>
                      ACTIVE
                    </span>
                  </div>
                </div>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)', lineHeight: '1.3' }}>
                  {skill.description}
                </span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
