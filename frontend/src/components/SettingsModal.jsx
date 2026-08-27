import React, { useState, useEffect } from 'react';
import { useJasva } from '../context/JasvaContext';
import { DraggableWidget } from './DraggableWidget';
import {
  Settings,
  Volume2,
  Cpu,
  User,
  Monitor,
  VolumeX,
  Play,
  Check
} from 'lucide-react';
import { callBackend } from '../utils/pywebviewBridge';

const EDGE_VOICES = [
  { group: 'British (UK / Jarvis & Butler Style)', voices: [
    { id: 'en-GB-RyanNeural', name: 'Ryan (British Male — Official Jarvis Style, Crisp & Authoritative)' },
    { id: 'en-GB-ThomasNeural', name: 'Thomas (British Male — Formal, Sophisticated Butler)' },
    { id: 'en-GB-SoniaNeural', name: 'Sonia (British Female — Analytical, High-Tech AI)' },
    { id: 'en-GB-LibbyNeural', name: 'Libby (British Female — Soft, Elegant & Refined)' },
    { id: 'en-GB-MaisieNeural', name: 'Maisie (British Female — Warm, Natural & Engaging)' }
  ]},
  { group: 'Irish (British Isles)', voices: [
    { id: 'en-IE-ConnorNeural', name: 'Connor (Irish Male — Deep, Resonant & Charming)' },
    { id: 'en-IE-EmilyNeural', name: 'Emily (Irish Female — Crisp, Melodic & Clear)' }
  ]},
  { group: 'Commonwealth Accents', voices: [
    { id: 'en-AU-WilliamMultilingualNeural', name: 'William (Australian Male — Smooth & Confident)' },
    { id: 'en-AU-NatashaNeural', name: 'Natasha (Australian Female — Crisp & Modern)' },
    { id: 'en-NZ-MitchellNeural', name: 'Mitchell (NZ Male — Articulate & Clear)' },
    { id: 'en-NZ-MollyNeural', name: 'Molly (NZ Female — Natural & Warm)' },
    { id: 'en-ZA-LukeNeural', name: 'Luke (South African Male — Sophisticated)' },
    { id: 'en-ZA-LeahNeural', name: 'Leah (South African Female — Polished)' }
  ]},
  { group: 'Indian English', voices: [
    { id: 'en-IN-PrabhatNeural', name: 'Prabhat (Indian Male — Clear & Focused)' },
    { id: 'en-IN-NeerjaNeural', name: 'Neerja (Indian Female — Natural)' },
    { id: 'en-IN-NeerjaExpressiveNeural', name: 'Neerja Expressive (Indian Female — Dynamic)' }
  ]},
  { group: 'US English', voices: [
    { id: 'en-US-ChristopherNeural', name: 'Christopher (US Male — Deep Cinematic Ultron Style)' },
    { id: 'en-US-SteffanNeural', name: 'Steffan (US Male — Deep Tech)' },
    { id: 'en-US-EricNeural', name: 'Eric (US Male — High Precision)' },
    { id: 'en-US-BrianMultilingualNeural', name: 'Brian (US Male — Conversational)' },
    { id: 'en-US-AndrewMultilingualNeural', name: 'Andrew (US Male — Warm)' },
    { id: 'en-US-JennyNeural', name: 'Jenny (US Female — Natural AI)' },
    { id: 'en-US-AriaNeural', name: 'Aria (US Female — Expressive)' },
    { id: 'en-US-AvaMultilingualNeural', name: 'Ava (US Female — Modern)' }
  ]}
];

export const SettingsModal = () => {
  const { isSettingsOpen, setIsSettingsOpen, speakResponse } = useJasva();
  const [activeTab, setActiveTab] = useState('voice');
  const [isTestingVoice, setIsTestingVoice] = useState(false);

  const [settings, setSettings] = useState({
    speech_engine: 'edge_tts',
    voice: 'en-GB-RyanNeural',
    elevenlabs_voice: '21m00Tcm4TlvDq8ikWAM',
    volume: 0.75,
    speed: 1.0,
    gemini_key: '',
    groq_key: '',
    puter_key: '',
    elevenlabs_key: '',
    autostart: false,
    always_listening: false
  });

  const [profile, setProfile] = useState({
    identity: { name: '', role: '', goals: '', rules: '' }
  });

  const [saveStatus, setSaveStatus] = useState('SYNCED');

  useEffect(() => {
    if (isSettingsOpen) {
      callBackend('get_settings').then(res => {
        if (res && typeof res === 'object') {
          setSettings(prev => ({ ...prev, ...res }));
        }
      });
      callBackend('get_memory_profile').then(res => {
        if (res && typeof res === 'object') {
          setProfile(prev => ({ ...prev, ...res }));
        }
      });
    }
  }, [isSettingsOpen]);

  const updateSetting = (key, value) => {
    const next = { ...settings, [key]: value };
    setSettings(next);
    setSaveStatus('SAVING...');

    callBackend('save_settings', JSON.stringify(next)).then(() => {
      setSaveStatus('SYNCED');
    });
  };

  const updateProfileField = (field, value) => {
    const next = {
      ...profile,
      identity: {
        ...profile.identity,
        [field]: value
      }
    };
    setProfile(next);
    setSaveStatus('SAVING...');
    callBackend('save_memory_profile', JSON.stringify(next)).then(() => {
      setSaveStatus('SYNCED');
    });
  };

  const handleTestVoice = async () => {
    setIsTestingVoice(true);
    try {
      await speakResponse("Testing quantum neural voice synthesis. All systems online and operational, sir.");
    } catch (_) {}
    setTimeout(() => setIsTestingVoice(false), 2500);
  };

  if (!isSettingsOpen) return null;

  return (
    <DraggableWidget
      id="settings_panel"
      title="SYSTEM SETTINGS"
      icon={Settings}
      initialPos={{ x: Math.max(20, window.innerWidth / 2 - 190), y: 80 }}
      width={380}
      onClose={() => setIsSettingsOpen(false)}
    >
      <div className="settings-widget-content">
        {/* ─── TAB NAVIGATION ─── */}
        <div className="device-tab-switcher" style={{ marginBottom: '6px' }}>
          <button
            className={`device-mode-btn ${activeTab === 'voice' ? 'active' : ''}`}
            onClick={() => setActiveTab('voice')}
          >
            <Volume2 size={12} />
            <span>VOICE</span>
          </button>
          <button
            className={`device-mode-btn ${activeTab === 'brain' ? 'active' : ''}`}
            onClick={() => setActiveTab('brain')}
          >
            <Cpu size={12} />
            <span>AI BRAIN</span>
          </button>
          <button
            className={`device-mode-btn ${activeTab === 'profile' ? 'active' : ''}`}
            onClick={() => setActiveTab('profile')}
          >
            <User size={12} />
            <span>PROFILE</span>
          </button>
          <button
            className={`device-mode-btn ${activeTab === 'system' ? 'active' : ''}`}
            onClick={() => setActiveTab('system')}
          >
            <Monitor size={12} />
            <span>SYSTEM</span>
          </button>
        </div>

        {/* ─── TAB 1: VOICE ─── */}
        {activeTab === 'voice' && (
          <div className="settings-tab-pane">
            <div className="setting-row">
              <label className="setting-label">SYNTHESIS ENGINE</label>
              <select
                className="hud-select"
                value={settings.speech_engine}
                onChange={(e) => updateSetting('speech_engine', e.target.value)}
              >
                <option value="edge_tts">Edge Neural (High Definition — Free)</option>
                <option value="elevenlabs">ElevenLabs Cloud (Jarvis Clone)</option>
              </select>
            </div>

            {settings.speech_engine === 'edge_tts' ? (
              <div className="setting-row">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                  <label className="setting-label">VOICE ACCENT</label>
                  <button
                    type="button"
                    onClick={handleTestVoice}
                    disabled={isTestingVoice}
                    className="device-link-btn"
                    style={{ padding: '2px 8px', fontSize: '10px' }}
                  >
                    {isTestingVoice ? 'SPEAKING...' : 'TEST'}
                  </button>
                </div>
                <select
                  className="hud-select"
                  value={settings.voice || 'en-GB-RyanNeural'}
                  onChange={(e) => updateSetting('voice', e.target.value)}
                >
                  {EDGE_VOICES.map(group => (
                    <optgroup key={group.group} label={group.group}>
                      {group.voices.map(v => (
                        <option key={v.id} value={v.id}>
                          {v.name}
                        </option>
                      ))}
                    </optgroup>
                  ))}
                </select>
              </div>
            ) : (
              <>
                <div className="setting-row">
                  <label className="setting-label">ELEVENLABS API KEY</label>
                  <input
                    type="password"
                    className="hud-input"
                    placeholder="sk_..."
                    value={settings.elevenlabs_key || ''}
                    onChange={(e) => updateSetting('elevenlabs_key', e.target.value)}
                  />
                </div>
                <div className="setting-row">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                    <label className="setting-label">VOICE ID</label>
                    <button
                      type="button"
                      onClick={handleTestVoice}
                      disabled={isTestingVoice}
                      className="device-link-btn"
                      style={{ padding: '2px 8px', fontSize: '10px' }}
                    >
                      {isTestingVoice ? 'SPEAKING...' : 'TEST'}
                    </button>
                  </div>
                  <input
                    type="text"
                    className="hud-input"
                    placeholder="21m00Tcm4TlvDq8ikWAM"
                    value={settings.elevenlabs_voice || ''}
                    onChange={(e) => updateSetting('elevenlabs_voice', e.target.value)}
                  />
                </div>
              </>
            )}

            <div className="setting-row">
              <label className="setting-label">
                SPEED ({settings.speed || 1.0}x)
              </label>
              <input
                type="range"
                min="0.75"
                max="1.5"
                step="0.05"
                value={settings.speed || 1.0}
                onChange={(e) => updateSetting('speed', parseFloat(e.target.value))}
                className="settings-range-slider"
              />
            </div>

            <div className="setting-row">
              <label className="setting-label">
                VOLUME ({Math.round((settings.volume || 0.75) * 100)}%)
              </label>
              <input
                type="range"
                min="0.1"
                max="1.0"
                step="0.05"
                value={settings.volume || 0.75}
                onChange={(e) => updateSetting('volume', parseFloat(e.target.value))}
                className="settings-range-slider"
              />
            </div>
          </div>
        )}

        {/* ─── TAB 2: AI BRAIN ─── */}
        {activeTab === 'brain' && (
          <div className="settings-tab-pane">
            <div className="setting-row">
              <label className="setting-label">GEMINI API KEY (Multimodal Engine)</label>
              <input
                type="password"
                className="hud-input"
                placeholder="AIzaSy..."
                value={settings.gemini_key || ''}
                onChange={(e) => updateSetting('gemini_key', e.target.value)}
              />
            </div>

            <div className="setting-row">
              <label className="setting-label">GROQ API KEY (Llama 3.3 70B)</label>
              <input
                type="password"
                className="hud-input"
                placeholder="gsk_..."
                value={settings.groq_key || ''}
                onChange={(e) => updateSetting('groq_key', e.target.value)}
              />
            </div>

            <div className="setting-row">
              <label className="setting-label">PUTER API KEY (GPT-4o Mini / Codex)</label>
              <input
                type="password"
                className="hud-input"
                placeholder="puter_..."
                value={settings.puter_key || ''}
                onChange={(e) => updateSetting('puter_key', e.target.value)}
              />
            </div>
          </div>
        )}

        {/* ─── TAB 3: PROFILE ─── */}
        {activeTab === 'profile' && (
          <div className="settings-tab-pane">
            <div className="setting-row">
              <label className="setting-label">YOUR NAME</label>
              <input
                type="text"
                className="hud-input"
                placeholder="e.g. Sir, Likhith, Tony"
                value={profile.identity?.name || ''}
                onChange={(e) => updateProfileField('name', e.target.value)}
              />
            </div>

            <div className="setting-row">
              <label className="setting-label">YOUR ROLE / TITLE</label>
              <input
                type="text"
                className="hud-input"
                placeholder="e.g. Founder, Engineer, Creator"
                value={profile.identity?.role || ''}
                onChange={(e) => updateProfileField('role', e.target.value)}
              />
            </div>

            <div className="setting-row">
              <label className="setting-label">BUSINESS & PROJECT GOALS</label>
              <textarea
                className="hud-textarea"
                rows={2}
                placeholder="e.g. Building next-gen AI agent systems..."
                value={profile.identity?.goals || ''}
                onChange={(e) => updateProfileField('goals', e.target.value)}
              />
            </div>

            <div className="setting-row">
              <label className="setting-label">OPERATING RULES & INSTRUCTIONS</label>
              <textarea
                className="hud-textarea"
                rows={2}
                placeholder="e.g. Keep responses concise and crisp, call me Sir..."
                value={profile.identity?.rules || ''}
                onChange={(e) => updateProfileField('rules', e.target.value)}
              />
            </div>
          </div>
        )}

        {/* ─── TAB 4: SYSTEM INTEGRATION ─── */}
        {activeTab === 'system' && (
          <div className="settings-tab-pane">
            <div className="setting-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <label className="setting-label" style={{ marginBottom: 0 }}>AUTOSTART ON BOOT</label>
                <div style={{ fontSize: '10px', color: 'var(--text-dim)', fontFamily: 'JetBrains Mono, monospace' }}>Run silently on Windows startup</div>
              </div>
              <button
                className={`device-link-btn ${settings.autostart ? 'active' : ''}`}
                style={{ minWidth: '76px', padding: '4px 10px', fontWeight: 700 }}
                onClick={() => updateSetting('autostart', !settings.autostart)}
              >
                {settings.autostart ? 'ENABLED' : 'DISABLED'}
              </button>
            </div>

            <div className="setting-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <label className="setting-label" style={{ marginBottom: 0 }}>WAKE WORD LISTENING</label>
                <div style={{ fontSize: '10px', color: 'var(--text-dim)', fontFamily: 'JetBrains Mono, monospace' }}>Voice activation (Jarvis / JASVA)</div>
              </div>
              <button
                className={`device-link-btn ${settings.always_listening ? 'active' : ''}`}
                style={{ minWidth: '76px', padding: '4px 10px', fontWeight: 700 }}
                onClick={() => updateSetting('always_listening', !settings.always_listening)}
              >
                {settings.always_listening ? 'ENABLED' : 'DISABLED'}
              </button>
            </div>

            <div className="setting-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <label className="setting-label" style={{ marginBottom: 0 }}>GLOBAL HOTKEYS</label>
                <div style={{ fontSize: '10px', color: 'var(--text-dim)', fontFamily: 'JetBrains Mono, monospace' }}>Win + J · Ctrl + Shift + J</div>
              </div>
              <span style={{ fontSize: '11px', fontFamily: 'JetBrains Mono, monospace', color: 'var(--accent-color)', fontWeight: 700 }}>
                ACTIVE
              </span>
            </div>
          </div>
        )}

        {/* ─── STATUS FOOTER ─── */}
        <div className="settings-widget-footer">
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <span className="device-status-pip online"></span>
            <span style={{ fontSize: '10.5px', fontFamily: 'JetBrains Mono, monospace', color: 'var(--text-dim)' }}>
              STATE:
            </span>
            <span style={{ fontSize: '10.5px', fontFamily: 'JetBrains Mono, monospace', color: 'var(--accent-color)', fontWeight: 700 }}>
              {saveStatus}
            </span>
          </div>
        </div>
      </div>
    </DraggableWidget>
  );
};
