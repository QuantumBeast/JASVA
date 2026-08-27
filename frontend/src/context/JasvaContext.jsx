import React, { createContext, useContext, useState, useEffect, useRef } from 'react';
import { callBackend, isPyWebView } from '../utils/pywebviewBridge';

const JasvaContext = createContext(null);

export const useJasva = () => useContext(JasvaContext);

export const JasvaProvider = ({ children }) => {
  // ─── Theme State ───
  const [theme, setTheme] = useState(() => localStorage.getItem('jasva_theme') || 'default');

  const changeTheme = (newTheme) => {
    setTheme(newTheme);
    localStorage.setItem('jasva_theme', newTheme);
    document.documentElement.setAttribute('data-theme', newTheme);
  };

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  // ─── Panels Visibility ───
  const [panels, setPanels] = useState({
    chatPanel: true,
    activeListeningPanel: true,
    commandEchoPanel: true,
    systemPanel: true
  });

  const togglePanel = (panelKey) => {
    setPanels(prev => ({ ...prev, [panelKey]: !prev[panelKey] }));
  };

  // ─── Modals State ───
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isPhoneOverlayOpen, setIsPhoneOverlayOpen] = useState(false);

  // ─── System & Telemetry State ───
  const [telemetry, setTelemetry] = useState({
    time: '00:00:00 AM',
    date: 'MON, JAN 01',
    temp: '--°C',
    loc: 'ONLINE'
  });

  const [metrics, setMetrics] = useState({
    cpu: 0,
    ram: 0,
    gpu: 0,
    disk: 0,
    os: 'WINDOWS'
  });

  const [metricHistory, setMetricHistory] = useState({
    cpu: Array(25).fill(0),
    ram: Array(25).fill(0),
    gpu: Array(25).fill(0),
    disk: Array(25).fill(0)
  });

  // ─── Device Connection States ───
  const [tvStatus, setTvStatus] = useState({ connected: false, ip: '' });
  const [phoneStatus, setPhoneStatus] = useState({ connected: false, ip: '' });

  // ─── Chat & Messaging State ───
  const [messages, setMessages] = useState([
    {
      id: 1,
      sender: 'bot',
      name: 'JASVA',
      text: 'Quantum neural engine online. All systems nominal, sir. How may I assist you today?',
      thought: null,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
  ]);

  const [attachedImage, setAttachedImage] = useState(null);
  const [isVoiceMuted, setIsVoiceMuted] = useState(() => localStorage.getItem('jasva_muted') === 'true');

  // ─── Sphere & Audio States ───
  const [sphereState, setSphereState] = useState({
    isListening: false,
    isSpeaking: false,
    isProcessing: false,
    userIsSpeaking: false,
    statusLabel: 'CLICK SPHERE TO COMMENCE SPEECH'
  });

  // ─── Agent Live Activity & Trace State ───
  const [agentTrace, setAgentTrace] = useState({
    active: false,
    goal: '',
    thought: '',
    currentStep: '',
    plan: [],
    steps: []
  });

  // ─── Logs & Toasts ───
  const [logs, setLogs] = useState([
    { id: 1, type: 'system', text: '[SYSTEM] QUANTUM NEURAL LINK: ACTIVE' }
  ]);
  const [toasts, setToasts] = useState([]);

  const addLog = (text, type = 'system') => {
    setLogs(prev => [...prev.slice(-100), { id: Date.now() + Math.random(), text, type }]);
  };

  const showToast = (toast) => {
    const id = Date.now() + Math.random();
    setToasts(prev => [...prev, { id, ...toast }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 3500);
  };

  // ─── Real-time Telemetry Poller ───
  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setTelemetry(prev => ({
        ...prev,
        time: now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
        date: now.toLocaleDateString([], { weekday: 'short', month: 'short', day: '2-digit' }).toUpperCase()
      }));
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  // ─── Hardware Metrics Poller ───
  useEffect(() => {
    const pollMetrics = async () => {
      const data = await callBackend('get_system_metrics');
      if (data && typeof data === 'object') {
        const cpuVal = Math.round(data.cpu || 0);
        const ramVal = Math.round(data.ram || 0);
        const gpuVal = Math.round(data.gpu || 0);
        const diskVal = Math.round(data.disk || 0);

        setMetrics({
          cpu: cpuVal,
          ram: ramVal,
          gpu: gpuVal,
          disk: diskVal,
          os: data.os || 'WINDOWS'
        });

        setMetricHistory(prev => ({
          cpu: [...prev.cpu.slice(1), cpuVal],
          ram: [...prev.ram.slice(1), ramVal],
          gpu: [...prev.gpu.slice(1), gpuVal],
          disk: [...prev.disk.slice(1), diskVal]
        }));
      }
    };

    pollMetrics();
    const interval = setInterval(pollMetrics, 2500);
    return () => clearInterval(interval);
  }, []);

  // ─── Sync Sphere State to Python Backend ───
  const lastSyncRef = useRef('');
  useEffect(() => {
    const sig = `${sphereState.isListening}|${sphereState.isSpeaking}|${sphereState.isProcessing}|${sphereState.userIsSpeaking}`;
    if (sig !== lastSyncRef.current) {
      lastSyncRef.current = sig;
      if (isPyWebView() && window.pywebview.api.set_sphere_state) {
        window.pywebview.api.set_sphere_state(
          sphereState.isListening,
          sphereState.isSpeaking,
          sphereState.isProcessing,
          sphereState.userIsSpeaking
        );
      }
    }
  }, [sphereState]);

  // ─── Continuous & Push-to-Talk Voice Recognition Setup ───
  const [isAlwaysListening, setIsAlwaysListening] = useState(() => localStorage.getItem('jasva_always_listening') === 'true');
  const [isPushToTalk, setIsPushToTalk] = useState(false);

  const isAlwaysListeningRef = useRef(isAlwaysListening);
  const isPushToTalkRef = useRef(isPushToTalk);
  const recognitionRef = useRef(null);
  const restartTimerRef = useRef(null);
  const isSpeakingRef = useRef(false);
  const isProcessingRef = useRef(false);
  const activeAudioRef = useRef(null);
  const speechIdRef = useRef(0);
  const finalTranscriptLockRef = useRef(false);
  const lastSpokenTextRef = useRef('');
  const lastSpeechEndTimeRef = useRef(0);

  useEffect(() => {
    isAlwaysListeningRef.current = isAlwaysListening;
    localStorage.setItem('jasva_always_listening', String(isAlwaysListening));
  }, [isAlwaysListening]);

  useEffect(() => {
    isPushToTalkRef.current = isPushToTalk;
  }, [isPushToTalk]);

  useEffect(() => {
    isSpeakingRef.current = sphereState.isSpeaking;
  }, [sphereState.isSpeaking]);

  useEffect(() => {
    isProcessingRef.current = sphereState.isProcessing;
  }, [sphereState.isProcessing]);

  // ─── Self-Echo & Speaker Feedback Filter ───
  const isSelfEcho = (transcript, spokenText) => {
    if (!spokenText || !transcript) return false;
    const cleanTrans = transcript.toLowerCase().replace(/[^a-z0-9\s]/g, '').trim();
    const cleanSpoken = spokenText.toLowerCase().replace(/[^a-z0-9\s]/g, '').trim();
    if (!cleanTrans) return true;

    // Direct string containment (exact match or substring)
    if (cleanSpoken.includes(cleanTrans) || cleanTrans.includes(cleanSpoken)) {
      return true;
    }

    // Word overlap filter (checks if speech was heard from speakers)
    const transWords = cleanTrans.split(/\s+/).filter(w => w.length > 2);
    if (transWords.length === 0) return false;
    const spokenWords = new Set(cleanSpoken.split(/\s+/).filter(w => w.length > 2));

    let matchCount = 0;
    for (const word of transWords) {
      if (spokenWords.has(word)) matchCount++;
    }

    return (matchCount / transWords.length) >= 0.38;
  };

  // ─── Single-Stream Exclusive Audio & Concurrency Lock ───
  const stopSpeaking = () => {
    // Invalidate any in-flight or pending TTS requests
    speechIdRef.current += 1;
    isSpeakingRef.current = false;
    lastSpeechEndTimeRef.current = 0;

    // Immediately stop and detach HTML5 Audio stream
    if (activeAudioRef.current) {
      try {
        activeAudioRef.current.pause();
        activeAudioRef.current.currentTime = 0;
        activeAudioRef.current.src = '';
      } catch (_) {}
      activeAudioRef.current = null;
    }

    // Immediately cancel Web Speech API synthesis
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      try {
        window.speechSynthesis.cancel();
      } catch (_) {}
    }

    setSphereState(prev => ({
      ...prev,
      isSpeaking: false,
      statusLabel: isAlwaysListeningRef.current || isPushToTalkRef.current ? 'JASVA LISTENING...' : 'CLICK MIC TO COMMENCE SPEECH'
    }));

    // If in always listening mode, ensure mic is active for user
    if (isAlwaysListeningRef.current || isPushToTalkRef.current) {
      startListeningEngine();
    }
  };

  // ─── Speech Recognition Engine ───
  const getOrCreateRecognition = () => {
    if (recognitionRef.current) return recognitionRef.current;
    if (typeof window === 'undefined' || (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window))) {
      return null;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const rec = new SpeechRecognition();
    rec.lang = 'en-US';
    rec.continuous = true;
    rec.interimResults = true;
    rec.maxAlternatives = 1;

    rec.onstart = () => {
      setSphereState(prev => ({
        ...prev,
        isListening: true,
        statusLabel: isPushToTalkRef.current ? 'PUSH-TO-TALK ACTIVE...' : (isSpeakingRef.current ? 'JASVA SPEAKING...' : 'JASVA LISTENING...')
      }));
    };

    rec.onspeechstart = () => {
      // Ignore speaker self-audio if currently playing
      if (isSpeakingRef.current) return;

      setSphereState(prev => ({
        ...prev,
        userIsSpeaking: true,
        statusLabel: 'JASVA LISTENING...'
      }));
    };

    rec.onsoundstart = () => {
      if (isSpeakingRef.current) return;
    };

    rec.onresult = (e) => {
      // Ignore audio incoming while JASVA is speaking through speakers
      if (isSpeakingRef.current) return;

      // Check for room reverb lingering within grace period
      const timeSinceSpeech = Date.now() - lastSpeechEndTimeRef.current;

      let finalTranscript = '';
      for (let i = e.resultIndex; i < e.results.length; ++i) {
        if (e.results[i].isFinal) {
          finalTranscript += e.results[i][0].transcript;
        }
      }

      const commandText = finalTranscript.trim();
      if (!commandText) return;

      // Echo Loop Prevention Filter: Discard if transcript is JASVA's own words
      if (timeSinceSpeech < 3500 && isSelfEcho(commandText, lastSpokenTextRef.current)) {
        console.log('[ECHO FILTER] Filtered self-speech loop:', commandText);
        return;
      }

      if (!finalTranscriptLockRef.current) {
        finalTranscriptLockRef.current = true;
        setTimeout(() => {
          finalTranscriptLockRef.current = false;
        }, 500);

        setSphereState(prev => ({
          ...prev,
          userIsSpeaking: false,
          statusLabel: 'JASVA PROCESSING...'
        }));
        sendCommand(commandText);
      }
    };

    rec.onerror = (e) => {
      if (e.error === 'not-allowed' || e.error === 'service-not-allowed') {
        console.warn('Speech recognition permission denied:', e.error);
        setIsAlwaysListening(false);
        isAlwaysListeningRef.current = false;
        setSphereState(prev => ({
          ...prev,
          isListening: false,
          userIsSpeaking: false,
          statusLabel: 'MIC PERMISSION DENIED'
        }));
        showToast({ title: 'MIC PERMISSION', message: 'Microphone access was denied.', type: 'error' });
      }
    };

    rec.onend = () => {
      setSphereState(prev => ({
        ...prev,
        userIsSpeaking: false
      }));

      // If currently speaking audio, do not restart recognition until audio completes
      if (isSpeakingRef.current) return;

      // Automatically restart continuous recognition if mode is still active
      if (isAlwaysListeningRef.current || isPushToTalkRef.current) {
        clearTimeout(restartTimerRef.current);
        restartTimerRef.current = setTimeout(() => {
          if ((isAlwaysListeningRef.current || isPushToTalkRef.current) && !isSpeakingRef.current) {
            try {
              rec.start();
            } catch (_) {
              try {
                recognitionRef.current = null;
                const newRec = getOrCreateRecognition();
                newRec?.start();
              } catch (_) {}
            }
          }
        }, 80);
      } else {
        setSphereState(prev => ({
          ...prev,
          isListening: false,
          statusLabel: 'CLICK MIC TO COMMENCE SPEECH'
        }));
      }
    };

    recognitionRef.current = rec;
    return rec;
  };

  const startListeningEngine = () => {
    if (isSpeakingRef.current) return;
    const rec = getOrCreateRecognition();
    if (rec) {
      try {
        rec.start();
      } catch (_) {}
    }
  };

  const stopListeningEngine = () => {
    clearTimeout(restartTimerRef.current);
    if (recognitionRef.current) {
      try {
        recognitionRef.current.abort();
      } catch (_) {}
    }
    setSphereState(prev => ({
      ...prev,
      isListening: false,
      userIsSpeaking: false,
      statusLabel: 'CLICK MIC TO COMMENCE SPEECH'
    }));
  };

  // ─── Toggle Voice Listening (Persistent Always-On Mode) ───
  const toggleVoiceListening = () => {
    stopSpeaking();
    if (isAlwaysListeningRef.current) {
      // Turn Off
      setIsAlwaysListening(false);
      isAlwaysListeningRef.current = false;
      localStorage.setItem('jasva_always_listening', 'false');
      stopListeningEngine();
      showToast({ title: 'MIC DISABLED', message: 'Voice recognition turned off.', type: 'info' });
    } else {
      // Turn On Always-Active
      setIsAlwaysListening(true);
      isAlwaysListeningRef.current = true;
      localStorage.setItem('jasva_always_listening', 'true');
      startListeningEngine();
      showToast({ title: 'MIC ALWAYS ACTIVE', message: 'Listening continuously. Speak anytime.', type: 'info' });
    }
  };

  // ─── Push-to-Talk Handlers (Hold Button) ───
  const startPushToTalk = () => {
    stopSpeaking();
    setIsPushToTalk(true);
    isPushToTalkRef.current = true;
    setSphereState(prev => ({
      ...prev,
      isListening: true,
      statusLabel: 'PUSH-TO-TALK ACTIVE...'
    }));
    startListeningEngine();
  };

  const stopPushToTalk = () => {
    setIsPushToTalk(false);
    isPushToTalkRef.current = false;
    if (!isAlwaysListeningRef.current) {
      stopListeningEngine();
    } else {
      setSphereState(prev => ({
        ...prev,
        statusLabel: 'JASVA LISTENING...'
      }));
    }
  };

  // Automatically start listening on boot if always-listening was previously enabled
  useEffect(() => {
    if (isAlwaysListening) {
      startListeningEngine();
    }
    return () => {
      clearTimeout(restartTimerRef.current);
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch (_) {}
      }
    };
  }, []);

  // ─── Send Command to JASVA ───
  const sendCommand = async (text, quiet = false) => {
    if (!text || !text.trim()) return;

    // Immediately cut off any previous audio when new message begins
    stopSpeaking();

    const userText = text.trim();
    const timeNow = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    // Add user message
    setMessages(prev => [
      ...prev,
      {
        id: Date.now(),
        sender: 'user',
        name: 'USER',
        text: userText,
        image: attachedImage?.src,
        timestamp: timeNow
      }
    ]);

    addLog(`[USER] ${userText}`, 'user');
    setAttachedImage(null);

    // Update Sphere state to processing
    setSphereState(prev => ({
      ...prev,
      isProcessing: true,
      statusLabel: 'JASVA PROCESSING...'
    }));

    try {
      const res = await callBackend('execute_command', userText, quiet);
      const reply = res.output || res.reply || res.message || (typeof res === 'string' ? res : 'Command received.');

      setMessages(prev => [
        ...prev,
        {
          id: Date.now() + 1,
          sender: 'bot',
          name: 'JASVA',
          text: reply,
          thought: res.thought || null,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);

      addLog(`[AI] ${reply.slice(0, 80)}${reply.length > 80 ? '...' : ''}`, 'system');

      // Speech synthesis
      if (!isVoiceMuted && !quiet) {
        speakResponse(reply);
      }
    } catch (e) {
      console.error('Command execution error:', e);
      addLog(`[ERROR] ${String(e)}`, 'error');
    } finally {
      setSphereState(prev => ({
        ...prev,
        isProcessing: false,
        statusLabel: isAlwaysListeningRef.current ? 'JASVA LISTENING...' : 'CLICK MIC TO COMMENCE SPEECH'
      }));
    }
  };

  // ─── Speech Synthesis (Exclusive Single Active Stream) ───
  const speakResponse = async (text) => {
    if (isVoiceMuted || !text) return;

    // Cut off any prior speech
    stopSpeaking();

    const thisSpeechId = ++speechIdRef.current;
    isSpeakingRef.current = true;
    lastSpokenTextRef.current = text;
    setSphereState(prev => ({ ...prev, isSpeaking: true, statusLabel: 'JASVA SPEAKING...' }));

    const handleSpeechComplete = () => {
      if (thisSpeechId === speechIdRef.current) {
        activeAudioRef.current = null;
        isSpeakingRef.current = false;
        lastSpeechEndTimeRef.current = Date.now();

        setSphereState(prev => ({
          ...prev,
          isSpeaking: false,
          statusLabel: isAlwaysListeningRef.current ? 'JASVA LISTENING...' : 'CLICK MIC TO COMMENCE SPEECH'
        }));

        // Allow 450ms for room acoustic reverberation from speakers to fade out completely
        clearTimeout(restartTimerRef.current);
        restartTimerRef.current = setTimeout(() => {
          if (isAlwaysListeningRef.current && !isSpeakingRef.current) {
            startListeningEngine();
          }
        }, 450);
      }
    };

    // Try Neural TTS from backend
    try {
      const res = await callBackend('get_tts_audio', text);
      // Abort if another message arrived or user interrupted while generating
      if (thisSpeechId !== speechIdRef.current) return;

      if (res && res.status === 'success' && res.audio) {
        const audio = new Audio(`data:audio/wav;base64,${res.audio}`);
        activeAudioRef.current = audio;

        audio.onended = handleSpeechComplete;
        audio.onerror = () => {
          if (thisSpeechId === speechIdRef.current) {
            activeAudioRef.current = null;
            fallbackBrowserTTS(text, thisSpeechId, handleSpeechComplete);
          }
        };

        try {
          await audio.play();
        } catch (_) {
          if (thisSpeechId === speechIdRef.current) {
            fallbackBrowserTTS(text, thisSpeechId, handleSpeechComplete);
          }
        }
        return;
      }
    } catch (e) {}

    if (thisSpeechId === speechIdRef.current) {
      fallbackBrowserTTS(text, thisSpeechId, handleSpeechComplete);
    }
  };

  const fallbackBrowserTTS = (text, thisSpeechId = null, onComplete = null) => {
    if (thisSpeechId && thisSpeechId !== speechIdRef.current) return;

    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      const clean = text.replace(/\[.*?\]/g, '').replace(/```[\s\S]*?```/g, 'code snippet').trim();
      const utterance = new SpeechSynthesisUtterance(clean);
      utterance.onend = () => {
        if (onComplete) onComplete();
        else if (!thisSpeechId || thisSpeechId === speechIdRef.current) {
          isSpeakingRef.current = false;
          lastSpeechEndTimeRef.current = Date.now();
          setSphereState(prev => ({
            ...prev,
            isSpeaking: false,
            statusLabel: isAlwaysListeningRef.current ? 'JASVA LISTENING...' : 'CLICK MIC TO COMMENCE SPEECH'
          }));
        }
      };
      utterance.onerror = () => {
        if (onComplete) onComplete();
        else if (!thisSpeechId || thisSpeechId === speechIdRef.current) {
          isSpeakingRef.current = false;
          lastSpeechEndTimeRef.current = Date.now();
          setSphereState(prev => ({
            ...prev,
            isSpeaking: false,
            statusLabel: isAlwaysListeningRef.current ? 'JASVA LISTENING...' : 'CLICK MIC TO COMMENCE SPEECH'
          }));
        }
      };
      window.speechSynthesis.speak(utterance);
    } else {
      isSpeakingRef.current = false;
      setSphereState(prev => ({
        ...prev,
        isSpeaking: false,
        statusLabel: isAlwaysListeningRef.current ? 'JASVA LISTENING...' : 'CLICK MIC TO COMMENCE SPEECH'
      }));
    }
  };

  // ─── Global Window Sync Bridge for PyWebView ───
  useEffect(() => {
    window.syncWindowVisibilityState = (panelName, visible) => {
      setPanels(prev => ({ ...prev, [panelName]: visible }));
    };
    window.changeHudTheme = (themeName) => {
      changeTheme(themeName);
    };
    window.toggleMic = () => {
      toggleVoiceListening();
    };
    window.onStreamToken = (token) => {
      setMessages(prev => {
        const last = prev[prev.length - 1];
        if (last && last.sender === 'bot') {
          return [...prev.slice(0, -1), { ...last, text: last.text + token }];
        }
        return prev;
      });
    };
    window.onAgentEvent = (type, data) => {
      if (type === 'start') {
        setAgentTrace({
          active: true,
          goal: data?.goal || '',
          thought: '',
          currentStep: 'INITIALIZING',
          plan: [],
          steps: [{ type: 'start', data }]
        });
      } else if (type === 'thought') {
        setAgentTrace(prev => ({
          ...prev,
          active: true,
          thought: data?.thought || '',
          currentStep: data?.current_step || data?.thought || 'REASONING',
          plan: data?.plan || prev.plan,
          steps: [...prev.steps, { type: 'thought', data }]
        }));
      } else if (type === 'action') {
        setAgentTrace(prev => ({
          ...prev,
          active: true,
          currentStep: data?.command ? `EXECUTING: ${data.command}` : 'EXECUTING',
          steps: [...prev.steps, { type: 'action', data }]
        }));
      } else if (type === 'observation') {
        setAgentTrace(prev => ({
          ...prev,
          active: true,
          currentStep: 'OBSERVING',
          steps: [...prev.steps, { type: 'observation', data }]
        }));
      } else if (type === 'stop') {
        setAgentTrace(prev => ({
          ...prev,
          active: false,
          currentStep: 'COMPLETE',
          steps: [...prev.steps, { type: 'stop', data }]
        }));
      }
    };
    window.minimizeWindow = () => {
      if (isPyWebView() && window.pywebview.api.minimize_window) {
        window.pywebview.api.minimize_window();
      }
    };
    window.exitApplication = () => {
      if (isPyWebView()) {
        if (window.pywebview.api.close_window) window.pywebview.api.close_window();
        else if (window.pywebview.api.exit_app) window.pywebview.api.exit_app();
      } else {
        window.close();
      }
    };
  }, []);

  return (
    <JasvaContext.Provider
      value={{
        theme,
        changeTheme,
        panels,
        togglePanel,
        isSettingsOpen,
        setIsSettingsOpen,
        isPhoneOverlayOpen,
        setIsPhoneOverlayOpen,
        telemetry,
        metrics,
        metricHistory,
        tvStatus,
        setTvStatus,
        phoneStatus,
        setPhoneStatus,
        messages,
        attachedImage,
        setAttachedImage,
        isVoiceMuted,
        setIsVoiceMuted,
        isAlwaysListening,
        setIsAlwaysListening,
        isPushToTalk,
        startPushToTalk,
        stopPushToTalk,
        sphereState,
        setSphereState,
        agentTrace,
        logs,
        addLog,
        toasts,
        showToast,
        sendCommand,
        toggleVoiceListening,
        stopSpeaking,
        speakResponse
      }}
    >
      {children}
    </JasvaContext.Provider>
  );
};
