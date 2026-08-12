(() => {
/**
 * chat.js — Chat window controller for JASVA.
 * Handles: speech recognition, text input, voice output (TTS + Neural),
 *          settings modal, image upload, and the communication engine.
 * 
 * Also syncs sphere state to the backend so the sphere window reacts visually.
 */

// ─── DOM Elements ───
const textInput = document.getElementById('textInput');
const sendBtn = document.getElementById('sendBtn');
const voiceToggleBtn = document.getElementById('voiceToggleBtn');
const speakerIcon = document.getElementById('speakerIcon');

// ─── State ───
let recognition;
let numpadDecimalPressed = false;
let syncCounter = 0;
let audioContext;
let analyser;
let micSource;
let micInterval;

// Set initial speaker state
if (voiceToggleBtn) {
    if (isVoiceMuted) {
        voiceToggleBtn.classList.add('muted');
        voiceToggleBtn.classList.remove('active-blue');
        updateSpeakerIcon(true);
    } else {
        voiceToggleBtn.classList.remove('muted');
        voiceToggleBtn.classList.add('active-blue');
        updateSpeakerIcon(false);
    }
}

// ─── Sphere State Sync Helper ───
// Pushes the chat window's listening/speaking/processing state to the backend
// so the sphere window can read it and update its visuals.
let lastSphereSyncSig = '';
function syncSphereState() {
    // Only the chat window or unified window should push state to the backend
    const params = new URLSearchParams(window.location.search);
    const activePanel = params.get('panel');
    if (activePanel && activePanel !== 'chat') {
        return;
    }

    if (window.pywebview && window.pywebview.api) {
        const statusInd = document.getElementById('statusIndicator');
        const isProcessing = statusInd && statusInd.textContent.includes('PROCESSING');
        // Skip identical updates to avoid hammering the JS<->Python bridge
        const sig = `${isListening}|${isSpeaking}|${isProcessing}|${userIsSpeaking}`;
        if (sig === lastSphereSyncSig) return;
        lastSphereSyncSig = sig;
        try {
            window.pywebview.api.set_sphere_state(isListening, isSpeaking, isProcessing, userIsSpeaking);
        } catch (e) {}
    }
}

// Periodically sync sphere state (throttled to reduce CPU/bridge load)
setInterval(syncSphereState, 700);

// Precise speech state tracking is managed dynamically using interim recognition results.
let silenceTimeout = null;
let accumulatedTranscript = "";

// ─── Speech Recognition Setup ───
// Speech recognition should only run in the chat panel (or unified mode)
const speechParams = new URLSearchParams(window.location.search);
const speechPanel = speechParams.get('panel');
const shouldRunSpeech = !speechPanel || speechPanel === 'chat';

if (shouldRunSpeech && ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    recognition.onstart = () => {
        isListening = true;
        userIsSpeaking = false;
        const statusDot = document.querySelector('.status-dot');
        if (statusDot) {
            statusDot.className = 'status-dot';
            statusDot.classList.add('listening');
        }
        document.getElementById('statusIndicator').textContent = 'JASVA LISTENING';
        shouldAutoListen = false;
        syncSphereState();
    };

    // Browser noise/speech callbacks removed in favor of precise Web Audio mic analyser threshold gate

    recognition.onend = () => {
        isListening = false;
        userIsSpeaking = false;
        const statusDot = document.querySelector('.status-dot');
        if (statusDot) statusDot.className = 'status-dot online';
        document.getElementById('statusIndicator').textContent = 'JASVA STANDBY';
        syncSphereState();

        if (isAlwaysListeningMode || isSpeaking || shouldAutoListen) {
            setTimeout(() => {
                try {
                    if (!isListening && (isAlwaysListeningMode || isSpeaking || shouldAutoListen)) {
                        recognition.start();
                    }
                } catch (e) {}
            }, 100);
        }
    };

    recognition.onresult = (event) => {
        // Speech activity detected: light up green visually in real time
        userIsSpeaking = true;
        syncSphereState();

        const resultIndex = event.resultIndex;
        const transcript = event.results[resultIndex][0].transcript;
        
        if (transcript.trim()) {
            accumulatedTranscript = transcript.trim();
        }

        if (silenceTimeout) clearTimeout(silenceTimeout);
        silenceTimeout = setTimeout(() => {
            userIsSpeaking = false;
            syncSphereState();
            
            // Fallback: If we have an accumulated transcript that wasn't processed yet, process it now
            if (accumulatedTranscript) {
                const text = accumulatedTranscript;
                accumulatedTranscript = "";
                processRecognizedSpeech(text);
            }
        }, 1200);

        const isFinal = event.results[resultIndex].isFinal;
        if (isFinal && accumulatedTranscript) {
            const text = accumulatedTranscript;
            accumulatedTranscript = "";
            processRecognizedSpeech(text);
        }
    };

    function processRecognizedSpeech(transcriptText) {
        const cleanTranscript = removeSentenceFullStops(transcriptText).trim().toLowerCase();
        if (!cleanTranscript) return;

        // Wake Word Trigger
        const wakeWords = ["jasva", "jarvis", "hey jasva", "hey jarvis"];
        const hasWakeWord = wakeWords.some(ww => cleanTranscript.includes(ww));
        
        if (hasWakeWord) {
            if (window.pywebview && window.pywebview.api) {
                window.pywebview.api.wake_up();
            }
        }
        
        const timeSinceLastSpeech = Date.now() - lastSpeechEndTime;

        if (isAlwaysListeningSetting && !hasWakeWord && timeSinceLastSpeech > 7000) {
            console.log(`Continuous listening ignored background noise/speech: "${transcriptText}"`);
            return;
        }

        let processedTranscript = transcriptText;
        for (const ww of wakeWords) {
            const regex = new RegExp(`^\\b${ww}\\b\\s*`, 'i');
            if (regex.test(processedTranscript)) {
                processedTranscript = processedTranscript.replace(regex, '');
                break;
            }
        }

        function isEcho(text) {
            if (!lastSpokenText) return false;
            const cleanTranscriptText = text.toLowerCase().replace(/[^a-z0-9\s]/g, "").trim();
            const cleanSpokenText = lastSpokenText.toLowerCase().replace(/[^a-z0-9\s]/g, "").trim();
            if (cleanTranscriptText.length === 0) return true;
            if (cleanSpokenText.includes(cleanTranscriptText)) return true;
            const transcriptWords = cleanTranscriptText.split(/\s+/);
            const spokenWords = cleanSpokenText.split(/\s+/);
            let matchCount = 0;
            for (const word of transcriptWords) {
                if (spokenWords.includes(word)) matchCount++;
            }
            return (matchCount / transcriptWords.length) > 0.6;
        }

        // Stop/interrupt commands
        const stopKeywords = ["stop", "shh", "quiet", "shut up", "cancel", "hold on", "pause", "never mind", "nevermind", "hush"];
        const transcriptWords = cleanTranscript.split(/\s+/);
        const hasStopWord = stopKeywords.some(kw => transcriptWords.includes(kw));
        if (isSpeaking && hasStopWord) {
            stopSpeaking();
            syncSphereState();
            return;
        }

        // Echo filter
        const isRecentSpeech = isSpeaking || (timeSinceLastSpeech < 5000);
        if (isRecentSpeech && isEcho(cleanTranscript)) return;

        // Barge-in
        if (isSpeaking) { stopSpeaking(); syncSphereState(); }

        const cleanTranscriptReal = removeSentenceFullStops(processedTranscript);
        addMessage('USER', cleanTranscriptReal, 'user-msg');
        sendCommand(cleanTranscriptReal, false);
    }

    recognition.onerror = (event) => {
        if (event.error === 'no-speech' || event.error === 'aborted') return;
        if (event.error === 'network') {
            addMessage('SYSTEM', "Speech recognition requires internet connection.", 'error-msg');
            speakText("Speech recognition requires internet connection.");
        } else {
            addMessage('SYSTEM', `Recognition error: ${event.error}`, 'error-msg');
        }
    };
}

// ─── TTS: Speak Text ───
function speakText(text) {
    if (isVoiceMuted) return;

    isSpeaking = true;
    currentSpokenText = text;
    lastSpokenText = text;
    syncSphereState();
    
    if (recognition && !isListening) {
        try { recognition.start(); } catch(e){}
    }
    
    if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
        const cleanText = text.replace(/\[DIR\s*\]|\[FILE\s*\]/gi, "").trim();
        const utterance = new SpeechSynthesisUtterance(cleanText);
        const voices = window.speechSynthesis.getVoices();

        const jarvisVoice = voices.find(v =>
            v.name.includes('George') || v.name.includes('Ryan') || v.name.includes('David') || v.name.includes('Google UK English Male')
        ) || voices.find(v =>
            v.name.includes('Online (Natural)') && (v.lang.includes('en-GB') || v.lang.includes('en-US'))
        ) || voices.find(v =>
            v.name.includes('Google UK English') || v.lang.includes('en-GB')
        ) || voices.find(v =>
            v.name.includes('Hazel') || v.name.includes('Zira') || v.lang.includes('en-US')
        ) || voices[0];

        if (jarvisVoice) utterance.voice = jarvisVoice;
        utterance.rate = globalSpeechSpeed * 1.02;
        utterance.pitch = 0.96;
        utterance.volume = globalSpeechVolume;

        utterance.onend = () => {
            isSpeaking = false;
            currentSpokenText = "";
            lastSpeechEndTime = Date.now();
            syncSphereState();
            if (shouldAutoListen && recognition) {
                shouldAutoListen = false;
                setTimeout(() => { try { if (recognition && !isListening) recognition.start(); } catch(e){} }, 400);
            } else {
                if (!isAlwaysListeningMode && recognition && isListening) {
                    try { recognition.stop(); } catch(e){}
                }
            }
        };
        utterance.onerror = () => {
            isSpeaking = false;
            currentSpokenText = "";
            lastSpeechEndTime = Date.now();
            syncSphereState();
            if (shouldAutoListen && recognition) {
                shouldAutoListen = false;
                setTimeout(() => { try { if (recognition && !isListening) recognition.start(); } catch(e){} }, 400);
            } else {
                if (!isAlwaysListeningMode && recognition && isListening) {
                    try { recognition.stop(); } catch(e){}
                }
            }
        };
        window.speechSynthesis.speak(utterance);
    }
}

// ─── Neural TTS Audio Playback ───
function playNeuralAudio(base64Wav, backupText = "") {
    isSpeaking = true;
    currentSpokenText = backupText;
    lastSpokenText = backupText;
    syncSphereState();
    
    if (recognition && !isListening) { try { recognition.start(); } catch(e){} }
    if (currentNeuralAudio) { currentNeuralAudio.pause(); currentNeuralAudio = null; }
    if ('speechSynthesis' in window) { window.speechSynthesis.cancel(); }

    function onPlaybackEnd() {
        isSpeaking = false;
        currentSpokenText = "";
        lastSpeechEndTime = Date.now();
        currentNeuralAudio = null;
        syncSphereState();
        if (shouldAutoListen && recognition) {
            shouldAutoListen = false;
            setTimeout(() => { try { if (recognition && !isListening) recognition.start(); } catch(e){} }, 400);
        } else {
            if (!isAlwaysListeningMode && recognition && isListening) {
                try { recognition.stop(); } catch(e){}
            }
        }
    }

    try {
        const binaryString = atob(base64Wav);
        const bytes = new Uint8Array(binaryString.length);
        for (let i = 0; i < binaryString.length; i++) bytes[i] = binaryString.charCodeAt(i);

        const isWav = base64Wav.startsWith("UklGR");
        const mimeType = isWav ? 'audio/wav' : 'audio/mpeg';
        const blob = new Blob([bytes], { type: mimeType });
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        audio.volume = globalSpeechVolume;
        if (typeof window.connectAudioToVisualizer === 'function') {
            window.connectAudioToVisualizer(audio);
        }

        audio.onended = () => { URL.revokeObjectURL(url); onPlaybackEnd(); };
        audio.onerror = (e) => {
            URL.revokeObjectURL(url);
            console.error("Neural audio playback error:", e);
            if (backupText) { speakText(backupText); } else { onPlaybackEnd(); }
        };

        currentNeuralAudio = audio;
        audio.play().catch(err => {
            console.error("Failed to play neural audio:", err);
            currentNeuralAudio = null;
            if (backupText) { speakText(backupText); } else { onPlaybackEnd(); }
        });
    } catch (e) {
        console.error("Error decoding neural audio:", e);
        if (backupText) { speakText(backupText); } else { onPlaybackEnd(); }
    }
}

// ─── Async Get & Play Speech Helper (Non-blocking) ───
async function getAndPlaySpeech(text) {
    if (window.pywebview && window.pywebview.api) {
        try {
            const resJson = await window.pywebview.api.get_tts_audio(text);
            const res = JSON.parse(resJson);
            if (res.status === 'success' && res.audio) {
                playNeuralAudio(res.audio, text);
            } else {
                if (res.status === 'error' && res.message) {
                    showToast({
                        type: 'error',
                        title: 'SPEECH ENGINE ERROR',
                        message: res.message
                    });
                }
                speakText(text);
            }
        } catch (e) {
            console.error("Async speech fetch failed, falling back to local TTS:", e);
            speakText(text);
        }
    } else {
        speakText(text);
    }
}

// ─── Communication Engine ───
async function sendCommand(commandText, quiet = false) {
    let prompt = commandText;
    if (!prompt.trim() && currentAttachedImage) prompt = "Describe this image.";
    if (!prompt.trim()) return;

    shouldAutoListen = !quiet;

    const statusDot = document.querySelector('.status-dot');
    if (statusDot) statusDot.className = 'status-dot processing';
    const statusInd = document.getElementById('statusIndicator');
    if (statusInd) statusInd.textContent = 'JASVA PROCESSING';
    syncSphereState();

    const imgToSend = currentAttachedImage;
    clearAttachedImage();

    try {
        let responseData;

        if (window.pywebview && window.pywebview.api) {
            let resultJson;
            if (imgToSend) {
                resultJson = await window.pywebview.api.execute_command(prompt, quiet, imgToSend.base64, imgToSend.mimeType);
            } else {
                resultJson = await window.pywebview.api.execute_command(prompt, quiet);
            }
            responseData = JSON.parse(resultJson);
        } else {
            const host = window.location.protocol === 'file:' ? 'http://127.0.0.1:8000' : '';
            const bodyPayload = { command: prompt, quiet: quiet };
            if (imgToSend) {
                bodyPayload.image_base64 = imgToSend.base64;
                bodyPayload.image_mime = imgToSend.mimeType;
            }
            const response = await fetch(`${host}/api/command`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(bodyPayload)
            });
            if (!response.ok) throw new Error(`HTTP Error: ${response.status}`);
            responseData = await response.json();
        }

        if (responseData.output && commandText !== "initialize") {
            addMessage('JASVA', responseData.output, 'system-msg');
            if (!quiet && !isVoiceMuted) {
                getAndPlaySpeech(responseData.output);
            }
        }
        
        if (responseData.settings_updated) {
            await loadSettingsFromBackend();
        }

    } catch (error) {
        console.error("Communication error", error);
        addMessage('SYSTEM', `Failed to execute: ${error.message}`, 'error-msg');
    } finally {
        if (statusDot) statusDot.className = 'status-dot online';
        if (statusInd) statusInd.textContent = 'JASVA STANDBY';
        syncSphereState();
    }
}

// ─── Toggle Mic ───
function toggleMic() {
    if (!recognition) return;
    if (isListening) {
        isAlwaysListeningMode = false;
        shouldAutoListen = false;
        recognition.stop();
    } else {
        stopSpeaking();
        isAlwaysListeningMode = isAlwaysListeningSetting;
        recognition.start();
    }
}

// ─── Speaker Mute Toggle ───
function updateSpeakerIcon(muted) {
    if (!speakerIcon) return;
    if (muted) {
        speakerIcon.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" width="20" height="20"><path d="M13.5 4.06c0-1.336-1.616-2.005-2.56-1.06l-4.5 4.5H4.5A1.5 1.5 0 003 9v6a1.5 1.5 0 001.5 1.5h1.94l4.5 4.5c.944.945 2.56.276 2.56-1.06V4.06zM17.78 9.22a.75.75 0 10-1.06 1.06L18.44 12l-1.72 1.72a.75.75 0 001.06 1.06l1.72-1.72 1.72 1.72a.75.75 0 101.06-1.06L20.56 12l1.72-1.72a.75.75 0 00-1.06-1.06l-1.72 1.72-1.72-1.72z"/></svg>`;
    } else {
        speakerIcon.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" width="20" height="20"><path d="M13.5 4.06c0-1.336-1.616-2.005-2.56-1.06l-4.5 4.5H4.5A1.5 1.5 0 003 9v6a1.5 1.5 0 001.5 1.5h1.94l4.5 4.5c.944.945 2.56.276 2.56-1.06V4.06zM18.57 12c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM16.07 3.33v2.06c2.89.86 5 3.54 5 6.61s-2.11 5.75-5 6.61v2.06c4.01-.9 7-4.49 7-8.67s-2.99-7.77-7-8.67z"/></svg>`;
    }
}

if (voiceToggleBtn) {
    voiceToggleBtn.addEventListener('click', () => {
        isVoiceMuted = !isVoiceMuted;
        localStorage.setItem('jasva_muted', isVoiceMuted);
        
        if (isVoiceMuted) {
            voiceToggleBtn.classList.add('muted');
            voiceToggleBtn.classList.remove('active-blue');
        } else {
            voiceToggleBtn.classList.remove('muted');
            voiceToggleBtn.classList.add('active-blue');
        }
        
        updateSpeakerIcon(isVoiceMuted);
        if (!isVoiceMuted) speakText("Voice response enabled, sir.");
    });
}

// ─── Text Input Listeners ───
if (sendBtn) {
    sendBtn.addEventListener('click', () => {
        const text = textInput.value;
        if (text.trim() || currentAttachedImage) {
            const cleanText = removeSentenceFullStops(text);
            let displayMsg = cleanText;
            
            if (currentAttachedImage) {
                displayMsg = `
                    <div style="display: flex; flex-direction: column; gap: 8px;">
                        <img src="data:${currentAttachedImage.mimeType};base64,${currentAttachedImage.base64}" style="max-width: 200px; max-height: 150px; border-radius: 6px; border: 1px solid rgba(0, 242, 254, 0.25);" />
                        <div>${cleanText || 'Describe this image.'}</div>
                    </div>
                `;
                addMessage('USER', displayMsg, 'user-msg');
            } else {
                addMessage('USER', cleanText, 'user-msg');
            }
            
            sendCommand(cleanText, false);
            textInput.value = '';
        }
    });
}

if (textInput) {
    textInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') sendBtn.click();
    });
}

// ─── Keyboard Shortcuts (Numpad Decimal) ───
window.addEventListener('keydown', (e) => {
    const active = document.activeElement;
    const typingInField = active &&
        (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA' || active.isContentEditable);
    if (e.code === 'NumpadDecimal' && active !== textInput && !typingInField) {
        e.preventDefault();
        if (!numpadDecimalPressed && recognition && !isListening) {
            numpadDecimalPressed = true;
            stopSpeaking();
            isAlwaysListeningMode = true;
            recognition.start();
        }
    }
});

window.addEventListener('keyup', (e) => {
    if (e.code === 'NumpadDecimal') {
        if (numpadDecimalPressed && recognition) {
            numpadDecimalPressed = false;
            isAlwaysListeningMode = isAlwaysListeningSetting;
            recognition.stop();
        }
    }
});

// ─── Settings Modal ───
const settingsToggleBtn = document.getElementById('settingsToggleBtn');
const settingsOverlay = document.getElementById('settingsOverlay');
const closeSettingsBtn = document.getElementById('closeSettingsBtn');
const volumeSlider = document.getElementById('volumeSlider');
const volumeVal = document.getElementById('volumeVal');
const speedSlider = document.getElementById('speedSlider');
const speedVal = document.getElementById('speedVal');

if (settingsToggleBtn) {
    settingsToggleBtn.addEventListener('click', () => {
        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.show_settings_window();
        } else {
            loadSettingsFromBackend();
            settingsOverlay.classList.add('active');
        }
    });
}

if (closeSettingsBtn) {
    closeSettingsBtn.addEventListener('click', () => {
        const params = new URLSearchParams(window.location.search);
        const panel = params.get('panel');
        if (panel === 'settings' && window.pywebview && window.pywebview.api) {
            window.pywebview.api.hide_settings_window();
        } else {
            settingsOverlay.classList.remove('active');
        }
    });
}

if (settingsOverlay) {
    settingsOverlay.addEventListener('click', (e) => {
        const params = new URLSearchParams(window.location.search);
        const panel = params.get('panel');
        if (panel === 'settings') return;
        if (e.target === settingsOverlay) settingsOverlay.classList.remove('active');
    });
}

if (volumeSlider) {
    volumeSlider.addEventListener('input', () => {
        const val = parseFloat(volumeSlider.value);
        volumeVal.textContent = Math.round(val * 100) + '%';
        globalSpeechVolume = val;
        if (currentNeuralAudio) {
            try { currentNeuralAudio.volume = val; } catch(e){}
        }
    });
}

if (speedSlider) {
    speedSlider.addEventListener('input', () => {
        const val = parseFloat(speedSlider.value);
        speedVal.textContent = val.toFixed(1) + 'x';
        globalSpeechSpeed = val;
    });
}

// ─── Voice Engine Toggle UI Helpers ───
function toggleVoiceEngineFields(engine) {
    const edgeItem = document.getElementById('edgeVoiceItem');
    const elevenlabsItem = document.getElementById('elevenlabsVoiceItem');
    const elevenlabsCustomItem = document.getElementById('elevenlabsCustomVoiceItem');
    const elevenlabsVoiceSelect = document.getElementById('elevenlabsVoiceSelect');
    
    if (engine === 'elevenlabs') {
        if (edgeItem) edgeItem.style.display = 'none';
        if (elevenlabsItem) elevenlabsItem.style.display = 'block';
        if (elevenlabsCustomItem) {
            elevenlabsCustomItem.style.display = (elevenlabsVoiceSelect && elevenlabsVoiceSelect.value === 'custom') ? 'block' : 'none';
        }
    } else {
        if (edgeItem) edgeItem.style.display = 'block';
        if (elevenlabsItem) elevenlabsItem.style.display = 'none';
        if (elevenlabsCustomItem) elevenlabsCustomItem.style.display = 'none';
    }
}

function toggleElevenlabsCustomVoiceField(show) {
    const elCustomItem = document.getElementById('elevenlabsCustomVoiceItem');
    if (elCustomItem) {
        elCustomItem.style.display = show ? 'block' : 'none';
    }
}

// ─── Load Settings ───
async function loadSettingsFromBackend() {
    if (window.pywebview && window.pywebview.api) {
        try {
            const settingsJson = await window.pywebview.api.get_settings();
            const settings = JSON.parse(settingsJson);
            
            const engineEl = document.getElementById('speechEngineSelect');
            if (engineEl) {
                engineEl.value = settings.speech_engine || "edge_tts";
                toggleVoiceEngineFields(engineEl.value);
            }
            
            const voiceEl = document.getElementById('voiceSelect');
            if (voiceEl) voiceEl.value = settings.voice || "en-US-SteffanNeural";
            
            const elVoice = settings.elevenlabs_voice || "21m00Tcm4TlvDq8ikWAM";
            const elVoiceSelect = document.getElementById('elevenlabsVoiceSelect');
            const elVoiceInput = document.getElementById('elevenlabsVoiceInput');
            
            if (elVoiceSelect) {
                if (settings.elevenlabs_voices && settings.elevenlabs_voices.length > 0) {
                    elVoiceSelect.innerHTML = '';
                    settings.elevenlabs_voices.forEach(voice => {
                        const opt = document.createElement('option');
                        opt.value = voice.id;
                        opt.textContent = `${voice.name} (${voice.category})`;
                        elVoiceSelect.appendChild(opt);
                    });
                    const customOpt = document.createElement('option');
                    customOpt.value = 'custom';
                    customOpt.textContent = '-- Custom Voice ID --';
                    elVoiceSelect.appendChild(customOpt);
                }
                
                const presetValues = Array.from(elVoiceSelect.options).map(opt => opt.value);
                if (presetValues.includes(elVoice)) {
                    elVoiceSelect.value = elVoice;
                    if (elVoiceInput) elVoiceInput.value = elVoice;
                    toggleElevenlabsCustomVoiceField(false);
                } else {
                    elVoiceSelect.value = "custom";
                    if (elVoiceInput) elVoiceInput.value = elVoice;
                    toggleElevenlabsCustomVoiceField(true);
                }
            }
            
            const volEl = document.getElementById('volumeSlider');
            if (volEl) volEl.value = settings.volume !== undefined ? settings.volume : 0.75;
            
            const volValEl = document.getElementById('volumeVal');
            if (volValEl) volValEl.textContent = Math.round((settings.volume !== undefined ? settings.volume : 0.75) * 100) + '%';
            
            const spdEl = document.getElementById('speedSlider');
            if (spdEl) spdEl.value = settings.speed !== undefined ? settings.speed : 1.0;
            
            const spdValEl = document.getElementById('speedVal');
            if (spdValEl) spdValEl.textContent = (settings.speed !== undefined ? settings.speed : 1.0).toFixed(1) + 'x';
            
            let isBootAutostart = false;
            try { isBootAutostart = await window.pywebview.api.is_autostart_boot(); } catch(e) {}
            
            const isAlwaysListening = !!settings.always_listening || isBootAutostart;
            const alEl = document.getElementById('alwaysListenToggle');
            if (alEl) alEl.checked = isAlwaysListening;
            const asEl = document.getElementById('autostartToggle');
            if (asEl) asEl.checked = !!settings.autostart;
            
            const headerBtn = document.getElementById('alwaysListenHeaderBtn');
            if (headerBtn) {
                if (isAlwaysListening) headerBtn.classList.add('active');
                else headerBtn.classList.remove('active');
            }
            

            globalSpeechVolume = settings.volume !== undefined ? settings.volume : 0.75;
            globalSpeechSpeed = settings.speed !== undefined ? settings.speed : 1.0;
            isAlwaysListeningSetting = isAlwaysListening;
            isAlwaysListeningMode = isAlwaysListeningSetting;
            
            const keyMap = [
                ['geminiKeyInput', 'gemini_key'],
                ['groqKeyInput', 'groq_key'],
                ['puterKeyInput', 'puter_key'],
                ['elevenlabsKeyInput', 'elevenlabs_key']
            ];
            keyMap.forEach(([id, key]) => {
                const el = document.getElementById(id);
                if (el && settings[key]) el.value = settings[key];
            });
            
            if (isAlwaysListeningMode && recognition && !isListening) {
                try { recognition.start(); } catch(e){}
            }
        } catch (e) {
            console.error("Failed to load settings:", e);
        }
    }
}

// ─── Auto Save Settings ───
async function autoSaveSettings() {
    const voiceSelect = document.getElementById('voiceSelect');
    const speechEngineSelect = document.getElementById('speechEngineSelect');
    const elevenlabsVoiceSelect = document.getElementById('elevenlabsVoiceSelect');
    const elevenlabsVoiceInput = document.getElementById('elevenlabsVoiceInput');
    const alwaysListenToggle = document.getElementById('alwaysListenToggle');
    const autostartToggle = document.getElementById('autostartToggle');
    const autoSaveStatus = document.getElementById('autoSaveStatus');

    let elVoice = "21m00Tcm4TlvDq8ikWAM";
    if (elevenlabsVoiceSelect) {
        if (elevenlabsVoiceSelect.value === 'custom') {
            elVoice = elevenlabsVoiceInput ? elevenlabsVoiceInput.value.trim() : "";
        } else {
            elVoice = elevenlabsVoiceSelect.value;
            if (elevenlabsVoiceInput) elevenlabsVoiceInput.value = elVoice;
        }
    }

    // Build the config from whatever controls exist in THIS window so saving
    // from the top header (which has no settings controls) never overwrites
    // or wipes values the user has set elsewhere.
    const config = {};
    if (voiceSelect) config.voice = voiceSelect.value;
    if (speechEngineSelect) config.speech_engine = speechEngineSelect.value;
    if (elevenlabsVoiceSelect) config.elevenlabs_voice = elVoice;
    if (speedSlider) config.speed = parseFloat(speedSlider.value);
    if (volumeSlider) config.volume = parseFloat(volumeSlider.value);
    if (alwaysListenToggle) config.always_listening = alwaysListenToggle.checked;
    else config.always_listening = isAlwaysListeningMode;
    if (autostartToggle) config.autostart = autostartToggle.checked;

    // Only persist API keys when their inputs exist in this window, so other
    // windows (e.g. the top header) never accidentally wipe stored keys.
    ['gemini', 'groq', 'puter', 'elevenlabs'].forEach(k => {
        const el = document.getElementById(k + 'KeyInput');
        if (el) config[k + '_key'] = el.value.trim();
    });

    if (autoSaveStatus) {
        autoSaveStatus.textContent = 'SAVING...';
        autoSaveStatus.style.color = '#00ffcc';
        autoSaveStatus.style.opacity = '1';
    }

    try {
        if (window.pywebview && window.pywebview.api) {
            const resJson = await window.pywebview.api.save_settings(JSON.stringify(config));
            const res = JSON.parse(resJson);
            if (res.status === 'success') {
                if (config.volume !== undefined) globalSpeechVolume = config.volume;
                if (config.speed !== undefined) globalSpeechSpeed = config.speed;
                isAlwaysListeningSetting = config.always_listening;
                isAlwaysListeningMode = config.always_listening;
                
                const headerBtn = document.getElementById('alwaysListenHeaderBtn');
                if (headerBtn) {
                    if (config.always_listening) headerBtn.classList.add('active');
                    else headerBtn.classList.remove('active');
                }
                
                if (isAlwaysListeningMode) {
                    if (recognition && !isListening) { try { recognition.start(); } catch(e){} }
                } else {
                    if (recognition && isListening) { try { recognition.stop(); } catch(e){} }
                }
                
                if (autoSaveStatus) {
                    autoSaveStatus.textContent = 'SAVED';
                    setTimeout(() => { autoSaveStatus.style.opacity = '0'; }, 1200);
                }
                await loadSettingsFromBackend();
            }
        }
    } catch (err) {
        console.error("Auto save config error:", err);
        if (autoSaveStatus) { autoSaveStatus.textContent = 'ERROR'; autoSaveStatus.style.color = '#ff3366'; }
    }
}

// Bind save listeners
[
    'voiceSelect', 'alwaysListenToggle', 'autostartToggle', 
    'speechEngineSelect', 'elevenlabsVoiceSelect', 'elevenlabsVoiceInput',
    'geminiKeyInput', 'groqKeyInput', 'puterKeyInput', 'elevenlabsKeyInput'
].forEach(id => {
    const el = document.getElementById(id);
    if (el) {
        if (id === 'speechEngineSelect') {
            el.addEventListener('change', () => {
                toggleVoiceEngineFields(el.value);
                autoSaveSettings();
            });
        } else if (id === 'elevenlabsVoiceSelect') {
            el.addEventListener('change', () => {
                toggleElevenlabsCustomVoiceField(el.value === 'custom');
                if (el.value !== 'custom') {
                    const inp = document.getElementById('elevenlabsVoiceInput');
                    if (inp) inp.value = el.value;
                }
                autoSaveSettings();
            });
        } else {
            el.addEventListener('change', autoSaveSettings);
        }
    }
});
if (volumeSlider) volumeSlider.addEventListener('change', autoSaveSettings);
if (speedSlider) speedSlider.addEventListener('change', autoSaveSettings);

const alwaysListenHeaderBtn = document.getElementById('alwaysListenHeaderBtn');
if (alwaysListenHeaderBtn) {
    alwaysListenHeaderBtn.addEventListener('click', () => {
        const alwaysListenToggle = document.getElementById('alwaysListenToggle');
        let newState = !isAlwaysListeningMode;
        if (alwaysListenToggle) {
            newState = !alwaysListenToggle.checked;
            alwaysListenToggle.checked = newState;
        }
        isAlwaysListeningMode = newState;
        if (newState) alwaysListenHeaderBtn.classList.add('active');
        else alwaysListenHeaderBtn.classList.remove('active');
        if (newState) {
            if (recognition && !isListening) { try { recognition.start(); } catch(e){} }
        } else {
            if (recognition && isListening) { try { recognition.stop(); } catch(e){} }
        }
        autoSaveSettings();
    });
}

// ─── Voice loading + initial settings load ───
if ('speechSynthesis' in window) {
    window.speechSynthesis.onvoiceschanged = () => { window.speechSynthesis.getVoices(); };
}

let appInitialized = false;
async function initializeApp() {
    applyPanelFilter();
    if (appInitialized) return;
    appInitialized = true;
    await loadSettingsFromBackend();
    
    // Only send the initialize command from the main chat window
    const params = new URLSearchParams(window.location.search);
    const activePanel = params.get('panel');
    if (!activePanel || activePanel === 'chat') {
        await sendCommand("initialize", true);
    }
    
    startSystemMetricsPolling();
    initPanelResizers();
    startClockLoop();
    loadLayoutState();
}

window.addEventListener('pywebviewready', initializeApp);
setTimeout(() => {
    if (!appInitialized) {
        initializeApp();
    }
}, 1500);

// ─── Polling: notifications only (dashboard does metrics) ───
setInterval(async () => {
    // Only the chat window or unified window should poll and clear notifications
    const params = new URLSearchParams(window.location.search);
    const activePanel = params.get('panel');
    if (activePanel && activePanel !== 'chat') {
        return;
    }

    syncCounter++;
    if (window.pywebview && window.pywebview.api) {
        try {
            // Poll notifications for responsive timers/alarms
            const notifsJson = await window.pywebview.api.get_notifications();
            const notifs = JSON.parse(notifsJson);
            if (notifs && notifs.length > 0) {
                notifs.forEach(n => {
                    showToast(n);
                    if (n.command) sendCommand(n.command, true);
                });
            }
        } catch (err) {
            // silent
        }
    }
}, 2000);

// Helper to write diagnostic echo logs
function renderEchoLog(type, message) {
    const container = document.getElementById('echoLogsContainer');
    if (!container) return;
    const line = document.createElement('div');
    line.className = `echo-log-line ${type}`;
    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
    line.textContent = `[${timeStr}] [${type.toUpperCase()}] ${message}`;
    container.appendChild(line);
    container.scrollTop = container.scrollHeight;
    
    while (container.childNodes.length > 30) {
        container.removeChild(container.firstChild);
    }
}

let __lastEchoSig = '';

// Broadcast a log to all windows so the separate LOG panel stays live
window.__remoteEchoLog = function(type, message) {
    const sig = type + '|' + message;
    if (sig === __lastEchoSig) return;
    __lastEchoSig = sig;
    renderEchoLog(type, message);
};

function appendEchoLog(type, message) {
    __lastEchoSig = type + '|' + message;
    renderEchoLog(type, message);
    if (window.pywebview && window.pywebview.api && window.pywebview.api.broadcast_js) {
        window.pywebview.api.broadcast_js(`window.__remoteEchoLog(${JSON.stringify(type)}, ${JSON.stringify(message)})`);
    }
}

// Helper to update mood colors (Dynamic Mood Ring)
function updateMoodGlow(color, glowOpacity) {
    document.documentElement.style.setProperty('--mood-color', color);
    document.documentElement.style.setProperty('--mood-glow', `rgba(${hexToRgb(color)}, ${glowOpacity})`);
}

function hexToRgb(hex) {
    if (hex === '#00f2fe') return '0, 242, 254';
    if (hex === '#ffaa00') return '255, 170, 0';
    if (hex === '#ff3366') return '255, 51, 102';
    if (hex === '#00ffcc') return '0, 255, 204';
    return '0, 242, 254';
}

// ─── Agent Console Event Listener (Diagnostic & Mood Synced) ───
window.onAgentEvent = function(eventType, data) {
    const statusDot = document.getElementById('statusDot');
    const statusInd = document.getElementById('statusIndicator');
    
    if (eventType === 'start') {
        if (statusDot) statusDot.className = 'status-dot processing';
        if (statusInd) statusInd.textContent = 'JASVA THINKING...';
        window.sphereEmotion = 'calm';
        updateMoodGlow('#ffaa00', 0.1); 
        appendEchoLog('system', 'DIAGNOSTIC CYCLE INITIALIZED');
        return;
    }
    
    if (eventType === 'thought') {
        if (statusDot) statusDot.className = 'status-dot processing';
        if (data.current_step) {
            statusInd.textContent = `JASVA: ${data.current_step.toUpperCase()}`;
            appendEchoLog('thought', `SUB-TASK: ${data.current_step}`);
        } else {
            statusInd.textContent = 'JASVA COGNITION ACTIVE';
        }
        if (data.thought) {
            appendEchoLog('thought', `COGNITION: ${data.thought}`);
        }
        if (data.emotion) {
            window.sphereEmotion = data.emotion;
        }
        updateMoodGlow('#ffaa00', 0.1);
    }
    
    else if (eventType === 'action') {
        if (statusDot) statusDot.className = 'status-dot processing';
        if (data.command) {
            statusInd.textContent = `RUNNING: ${data.command.toUpperCase()}`;
            appendEchoLog('action', `EXECUTE: ${data.command}`);
        }
        updateMoodGlow('#00ffcc', 0.1);
    }
    
    else if (eventType === 'observation') {
        if (data.command) {
            const outSnippet = data.output ? data.output.substring(0, 100) : '';
            appendEchoLog('observation', `OBSERVED (${data.status}): ${outSnippet}...`);
        }
    }
    
    else if (eventType === 'stop') {
        if (statusDot) statusDot.className = 'status-dot online';
        if (statusInd) statusInd.textContent = 'JASVA STANDBY';
        window.sphereEmotion = 'calm';
        
        let hasError = data.reply && (data.reply.includes('failed') || data.reply.includes('API error') || data.reply.includes('error') || data.reply.includes('quota'));
        if (hasError) {
            updateMoodGlow('#ff3366', 0.1); 
            appendEchoLog('error', 'CYCLE ABORTED WITH DIAGNOSTIC ERRORS');
        } else {
            updateMoodGlow('#00f2fe', 0.05); 
            appendEchoLog('system', 'DIAGNOSTIC CYCLE COMPLETED');
        }
    }
};

// ─── Real-Time Audio Visualizer Analysis ───
let audioCtx = null;
let analyserNode = null;
let audioSourceNode = null;
let frequencyData = null;

window.connectAudioToVisualizer = function(audioElement) {
    try {
        if (!audioCtx) {
            audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            analyserNode = audioCtx.createAnalyser();
            analyserNode.fftSize = 64;
            frequencyData = new Uint8Array(analyserNode.frequencyBinCount);
        }
        if (audioCtx && audioCtx.state === 'suspended') {
            audioCtx.resume();
        }
        if (audioSourceNode) {
            try { audioSourceNode.disconnect(); } catch(e){}
        }
        audioSourceNode = audioCtx.createMediaElementSource(audioElement);
        audioSourceNode.connect(analyserNode);
        analyserNode.connect(audioCtx.destination);
        
        window.audioAnalyserNode = analyserNode;
        window.audioFrequencyData = frequencyData;
    } catch (e) {
        console.error("Failed to connect audio to visualizer:", e);
    }
};

// ─── System Metrics & Graphs Polling Loop ───
const graphData = {
    cpu: [],
    ram: [],
    gpu: [],
    disk: []
};
const maxGraphPoints = 30;

function drawMetricGraph(canvasId, dataArray, color) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    
    const dpr = window.devicePixelRatio || 1;
    const width = canvas.width = (canvas.offsetWidth || 150) * dpr;
    const height = canvas.height = (canvas.offsetHeight || 40) * dpr;
    ctx.scale(dpr, dpr);
    
    const displayWidth = canvas.offsetWidth || 150;
    const displayHeight = canvas.offsetHeight || 40;
    
    ctx.clearRect(0, 0, displayWidth, displayHeight);
    
    if (dataArray.length === 0) return;
    
    // Grid lines
    ctx.strokeStyle = 'rgba(0, 242, 254, 0.02)';
    ctx.lineWidth = 1;
    for (let x = 0; x < displayWidth; x += 15) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, displayHeight);
        ctx.stroke();
    }
    for (let y = 0; y < displayHeight; y += 10) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(displayWidth, y);
        ctx.stroke();
    }
    
    // Plot Line
    ctx.beginPath();
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.25;
    
    const step = displayWidth / (maxGraphPoints - 1);
    dataArray.forEach((val, idx) => {
        const x = idx * step;
        const y = displayHeight - (val / 100) * displayHeight * 0.75 - (displayHeight * 0.1);
        if (idx === 0) {
            ctx.moveTo(x, y);
        } else {
            ctx.lineTo(x, y);
        }
    });
    ctx.stroke();
    
    // Fill
    ctx.lineTo((dataArray.length - 1) * step, displayHeight);
    ctx.lineTo(0, displayHeight);
    ctx.fillStyle = color.replace('1)', '0.04)');
    ctx.fill();
}

function startSystemMetricsPolling() {
    updateMetrics();
    setInterval(updateMetrics, 2000);
}

async function updateMetrics() {
    // Only poll metrics if the system monitor panel is visible in this window context
    if (window.isPanelVisibleInWindow && !window.isPanelVisibleInWindow('systemPanel')) {
        return;
    }

    if (window.pywebview && window.pywebview.api) {
        try {
            const metricsJson = await window.pywebview.api.get_system_metrics();
            const metrics = JSON.parse(metricsJson);
            
            const valCPU = document.getElementById('valCPU');
            const valRAM = document.getElementById('valRAM');
            const valGPU = document.getElementById('valGPU');
            const valDisk = document.getElementById('valDisk');
            
            if (valCPU) valCPU.textContent = Math.round(metrics.cpu) + '%';
            if (valRAM) valRAM.textContent = Math.round(metrics.ram) + '%';
            if (valGPU) valGPU.textContent = Math.round(metrics.gpu) + '%';
            if (valDisk) valDisk.textContent = Math.round(metrics.disk) + '%';
            
            const barCPU = document.getElementById('barCPU');
            const barRAM = document.getElementById('barRAM');
            const barGPU = document.getElementById('barGPU');
            const barDisk = document.getElementById('barDisk');
            
            if (barCPU) barCPU.style.width = metrics.cpu + '%';
            if (barRAM) barRAM.style.width = metrics.ram + '%';
            if (barGPU) barGPU.style.width = metrics.gpu + '%';
            if (barDisk) barDisk.style.width = metrics.disk + '%';
            
            const osProfile = document.getElementById('osProfileText');
            if (osProfile && metrics.os) {
                osProfile.textContent = metrics.os.toUpperCase();
            }
            
            ['cpu', 'ram', 'gpu', 'disk'].forEach(key => {
                graphData[key].push(metrics[key] !== undefined ? metrics[key] : 0);
                if (graphData[key].length > maxGraphPoints) {
                    graphData[key].shift();
                }
            });
            
            drawMetricGraph('graphCPU', graphData.cpu, 'rgba(0, 242, 254, 1)');
            drawMetricGraph('graphRAM', graphData.ram, 'rgba(161, 140, 209, 1)');
            drawMetricGraph('graphGPU', graphData.gpu, 'rgba(0, 255, 135, 1)');
            drawMetricGraph('graphDisk', graphData.disk, 'rgba(255, 8, 68, 1)');
            
            // Live notifications ticker query — use recent (non-popping) API to avoid stealing unread notifications
            if (window.pywebview.api.get_recent_notifications) {
                const notifsJson = await window.pywebview.api.get_recent_notifications(5);
                const notifs = JSON.parse(notifsJson);
                if (notifs && notifs.length > 0) {
                    const tickerEl = document.getElementById('notificationTicker');
                    if (tickerEl) {
                        const alertStrings = notifs.map(n => `ALERT: ${(n.message || n.title || '').toUpperCase()}`);
                        tickerEl.textContent = alertStrings.join(' // ') + ' // SYSTEM NOMINAL...';
                    }
                }
            }
            
            // Live context schedules query
            if (window.pywebview.api.get_active_schedules) {
                const schedsJson = await window.pywebview.api.get_active_schedules();
                const scheds = JSON.parse(schedsJson);
                updateActiveContextWidget(scheds);
            }
            
        } catch (e) {
            console.error("System metrics fetch failed:", e);
        }
    }
}

// ─── Active Context Widget Renderer ───
function updateActiveContextWidget(scheds) {
    const listEl = document.getElementById('activeContextList');
    if (!listEl) return;
    
    if (!scheds || scheds.length === 0) {
        listEl.innerHTML = '<div class="context-item empty">NO ACTIVE ALARMS/TIMERS</div>';
        return;
    }
    
    listEl.innerHTML = '';
    scheds.forEach(s => {
        const item = document.createElement('div');
        item.className = 'context-item';
        
        const label = document.createElement('span');
        const timeText = s.trigger_time ? new Date(s.trigger_time * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false }) : 'CRON';
        label.textContent = `${s.prompt.substring(0, 16)} (${timeText})`;
        
        const removeBtn = document.createElement('button');
        removeBtn.className = 'context-remove-btn';
        removeBtn.innerHTML = '&times;';
        removeBtn.title = 'Cancel active alarm';
        removeBtn.addEventListener('click', async (e) => {
            e.stopPropagation();
            if (window.pywebview && window.pywebview.api) {
                await window.pywebview.api.remove_schedule(s.id);
                updateMetrics(); // refresh list
            }
        });
        
        item.appendChild(label);
        item.appendChild(removeBtn);
        listEl.appendChild(item);
    });
}

// ─── HUD Panel Resizers Drag Logic ───
function initPanelResizers() {
    const leftPanel = document.getElementById('chatPanel');
    const rightPanel = document.getElementById('systemPanel');
    const leftResizer = document.getElementById('leftResizer');
    const rightResizer = document.getElementById('rightResizer');
    
    const midTopResizer = document.getElementById('midTopResizer');
    const midBotResizer = document.getElementById('midBotResizer');
    const portalGreeting = document.getElementById('portalGreetingPanel');
    const commandEcho = document.getElementById('commandEchoPanel');
    
    const snapGridSize = 25; // Snap to 25px grid increments
    
    if (leftResizer && leftPanel) {
        setupDrag(leftResizer, (deltaX) => {
            let rawWidth = leftPanel.offsetWidth + deltaX;
            let snappedWidth = Math.round(rawWidth / snapGridSize) * snapGridSize;
            snappedWidth = Math.max(300, Math.min(650, snappedWidth));
            leftPanel.style.width = snappedWidth + 'px';
        });
    }
    
    if (rightResizer && rightPanel) {
        setupDrag(rightResizer, (deltaX) => {
            let rawWidth = rightPanel.offsetWidth - deltaX;
            let snappedWidth = Math.round(rawWidth / snapGridSize) * snapGridSize;
            snappedWidth = Math.max(300, Math.min(650, snappedWidth));
            rightPanel.style.width = snappedWidth + 'px';
        });
    }
    
    if (midTopResizer && portalGreeting) {
        setupDragVertical(midTopResizer, (deltaY) => {
            let rawHeight = portalGreeting.offsetHeight + deltaY;
            let snappedHeight = Math.round(rawHeight / snapGridSize) * snapGridSize;
            snappedHeight = Math.max(80, Math.min(250, snappedHeight));
            portalGreeting.style.height = snappedHeight + 'px';
        });
    }
    
    if (midBotResizer && commandEcho) {
        setupDragVertical(midBotResizer, (deltaY) => {
            let rawHeight = commandEcho.offsetHeight - deltaY;
            let snappedHeight = Math.round(rawHeight / snapGridSize) * snapGridSize;
            snappedHeight = Math.max(100, Math.min(350, snappedHeight));
            commandEcho.style.height = snappedHeight + 'px';
        });
    }
}

function setupDrag(resizer, onResize) {
    resizer.addEventListener('mousedown', (e) => {
        e.preventDefault();
        resizer.classList.add('dragging');
        let startX = e.clientX;
        
        function onMouseMove(moveEvent) {
            const deltaX = moveEvent.clientX - startX;
            startX = moveEvent.clientX;
            onResize(deltaX);
        }
        
        function onMouseUp() {
            resizer.classList.remove('dragging');
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);
            saveLayoutState();
        }
        
        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
    });
}

function setupDragVertical(resizer, onResize) {
    resizer.addEventListener('mousedown', (e) => {
        e.preventDefault();
        resizer.classList.add('dragging');
        let startY = e.clientY;
        
        function onMouseMove(moveEvent) {
            const deltaY = moveEvent.clientY - startY;
            startY = moveEvent.clientY;
            onResize(deltaY);
        }
        
        function onMouseUp() {
            resizer.classList.remove('dragging');
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);
            saveLayoutState();
        }
        
        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
    });
}

// ─── Clock and Weather Portals Loops ───
function startClockLoop() {
    updateClockAndWeather();
    setInterval(updateClockAndWeather, 1000);
    
    // Live weather query
    fetchLiveWeather();
    setInterval(fetchLiveWeather, 600000); // 10 minutes
}

async function fetchLiveWeather() {
    if (window.isPanelVisibleInWindow && !window.isPanelVisibleInWindow('portalGreetingPanel')) {
        return;
    }
    try {
        const res = await fetch('https://wttr.in/?format=j1');
        if (!res.ok) return;
        const data = await res.json();
        
        const current = data.current_condition[0];
        const temp = current.temp_C + '°C';
        const desc = current.weatherDesc[0].value.toUpperCase();
        
        const tempEl = document.getElementById('portalTemp');
        const locationEl = document.getElementById('portalLocation');
        
        if (tempEl) tempEl.textContent = temp;
        
        const area = data.nearest_area[0];
        const city = (area.areaName[0].value || 'BENGALURU').toUpperCase();
        if (locationEl) {
            locationEl.textContent = city;
            locationEl.title = desc; // Hover reveals full weather description
        }
    } catch(e) {
        console.error("Failed to fetch live weather:", e);
    }
}

function updateClockAndWeather() {
    if (window.isPanelVisibleInWindow && !window.isPanelVisibleInWindow('portalGreetingPanel')) {
        return;
    }
    const timeEl = document.getElementById('portalTime');
    const dateEl = document.getElementById('portalDate');
    
    if (timeEl) {
        const now = new Date();
        let hours = now.getHours();
        const mins = String(now.getMinutes()).padStart(2, '0');
        const ampm = hours >= 12 ? 'PM' : 'AM';
        hours = hours % 12;
        hours = hours ? hours : 12; // convert hour '0' to '12'
        const hrsStr = String(hours).padStart(2, '0');
        timeEl.textContent = `${hrsStr}:${mins} ${ampm}`;
    }
    
    if (dateEl) {
        const now = new Date();
        const options = { weekday: 'short', month: 'short', day: 'numeric' };
        dateEl.textContent = now.toLocaleDateString('en-US', options).toUpperCase();
    }
}

// ─── Sidebar Toggle Bindings ───
window.toggleLeftPanel = async function() {
    if (window.pywebview && window.pywebview.api) {
        const btn = document.getElementById('toggleLeftBtn');
        const nextState = btn ? !btn.classList.contains('active') : true;
        await window.pywebview.api.set_panel_window_visibility('chat', nextState);
    } else {
        const layout = document.querySelector('.hud-layout');
        const leftResizer = document.getElementById('leftResizer');
        
        if (layout) {
            layout.classList.toggle('left-open');
            const isOpen = layout.classList.contains('left-open');
            if (leftResizer) leftResizer.style.display = isOpen ? 'block' : 'none';
            
            const btn = document.getElementById('toggleLeftBtn');
            if (btn) {
                if (isOpen) btn.classList.add('active');
                else btn.classList.remove('active');
            }
        }
    }
};

window.toggleRightPanel = async function() {
    if (window.pywebview && window.pywebview.api) {
        const btn = document.getElementById('toggleRightBtn');
        const nextState = btn ? !btn.classList.contains('active') : true;
        await window.pywebview.api.set_panel_window_visibility('dashboard', nextState);
    } else {
        const layout = document.querySelector('.hud-layout');
        const rightResizer = document.getElementById('rightResizer');
        
        if (layout) {
            layout.classList.toggle('right-open');
            const isOpen = layout.classList.contains('right-open');
            if (rightResizer) rightResizer.style.display = isOpen ? 'block' : 'none';
            
            const btn = document.getElementById('toggleRightBtn');
            if (btn) {
                if (isOpen) btn.classList.add('active');
                else btn.classList.remove('active');
            }
        }
    }
};

// ─── Window Actions Bridges ───
window.minimizeWindow = async function() {
    if (window.pywebview && window.pywebview.api) {
        await window.pywebview.api.minimize_current_window();
    }
};

window.closeWindow = async function() {
    if (window.pywebview && window.pywebview.api) {
        const params = new URLSearchParams(window.location.search);
        const panel = params.get('panel');
        let winName = '';
        if (panel === 'chat') winName = 'chat';
        else if (panel === 'top') winName = 'top';
        else if (panel === 'sphere') winName = 'sphere';
        else if (panel === 'bottom') winName = 'bottom';
        else if (panel === 'system' || panel === 'monitor') winName = 'dashboard';
        else if (panel === 'control') winName = 'control';
        else if (panel === 'settings') winName = 'settings';
        
        if (winName) {
            await window.pywebview.api.close_panel_window(winName);
        }
    }
};

window.exitApplication = async function() {
    if (window.pywebview && window.pywebview.api) {
        await window.pywebview.api.close_window();
    }
};

// ─── HUD Widget Toggle Controllers ───
window.toggleHudMenu = function() {
    const menu = document.getElementById('hudDropdownMenu');
    if (menu) menu.classList.toggle('show');
};

document.addEventListener('click', (e) => {
    const container = document.querySelector('.hud-dropdown-container');
    if (container && !container.contains(e.target)) {
        const menu = document.getElementById('hudDropdownMenu');
        if (menu) menu.classList.remove('show');
    }
});

window.closePanel = function(panelId) {
    if (document.body.classList.contains('panel-mode')) {
        window.closeWindow();
        return;
    }
    
    const panel = document.getElementById(panelId);
    if (!panel) return;
    
    panel.style.display = 'none';
    
    // Hide resizer dividers if columns closed
    if (panelId === 'chatPanel') {
        const resizer = document.getElementById('leftResizer');
        if (resizer) resizer.style.display = 'none';
    } else if (panelId === 'systemPanel') {
        const resizer = document.getElementById('rightResizer');
        if (resizer) resizer.style.display = 'none';
    }
    
    // Uncheck in dropdown menu
    const chk = document.getElementById(`chk-${panelId}`);
    if (chk) chk.checked = false;
    
    saveLayoutState();
};

window.togglePanelFromMenu = async function(panelId) {
    const chk = document.getElementById(`chk-${panelId}`);
    if (!chk) return;
    const shouldShow = chk.checked;
    
    if (window.pywebview && window.pywebview.api) {
        let winName = '';
        if (panelId === 'chatPanel') winName = 'chat';
        else if (panelId === 'portalGreetingPanel') winName = 'top';
        else if (panelId === 'activeListeningPanel') winName = 'sphere';
        else if (panelId === 'commandEchoPanel') winName = 'bottom';
        else if (panelId === 'systemPanel') winName = 'dashboard';
        
        if (winName) {
            await window.pywebview.api.set_panel_window_visibility(winName, shouldShow);
        }
    } else {
        const panel = document.getElementById(panelId);
        if (!panel) return;
        
        panel.style.display = shouldShow ? 'flex' : 'none';
        
        // Toggle resizers
        if (panelId === 'chatPanel') {
            const resizer = document.getElementById('leftResizer');
            if (resizer) resizer.style.display = shouldShow ? 'block' : 'none';
        } else if (panelId === 'systemPanel') {
            const resizer = document.getElementById('rightResizer');
            if (resizer) resizer.style.display = shouldShow ? 'block' : 'none';
        }
        
        saveLayoutState();
    }
};

window.syncWindowVisibilityState = function(winName, isVisible) {
    let panelId = '';
    if (winName === 'chat') panelId = 'chatPanel';
    else if (winName === 'top') panelId = 'portalGreetingPanel';
    else if (winName === 'sphere') panelId = 'activeListeningPanel';
    else if (winName === 'bottom') panelId = 'commandEchoPanel';
    else if (winName === 'dashboard') panelId = 'systemPanel';
    
    if (panelId) {
        const chk = document.getElementById(`chk-${panelId}`);
        if (chk) chk.checked = isVisible;
        
        if (winName === 'chat') {
            const btn = document.getElementById('toggleLeftBtn');
            if (btn) {
                if (isVisible) btn.classList.add('active');
                else btn.classList.remove('active');
            }
        } else if (winName === 'dashboard') {
            const btn = document.getElementById('toggleRightBtn');
            if (btn) {
                if (isVisible) btn.classList.add('active');
                else btn.classList.remove('active');
            }
        }
    }
};

// ─── Layout State Persistence Handlers ───
function saveLayoutState() {
    const leftPanel = document.getElementById('chatPanel');
    const rightPanel = document.getElementById('systemPanel');
    const portalGreeting = document.getElementById('portalGreetingPanel');
    const commandEcho = document.getElementById('commandEchoPanel');
    
    const visibility = {
        chatPanel: leftPanel ? leftPanel.style.display !== 'none' : true,
        portalGreetingPanel: getPanelVisibility('portalGreetingPanel'),
        activeListeningPanel: getPanelVisibility('activeListeningPanel'),
        commandEchoPanel: getPanelVisibility('commandEchoPanel'),
        systemPanel: rightPanel ? rightPanel.style.display !== 'none' : true
    };
    
    const widths = {
        chatPanel: leftPanel ? leftPanel.style.width : '420px',
        systemPanel: rightPanel ? rightPanel.style.width : '320px'
    };
    
    const heights = {
        portalGreetingPanel: portalGreeting ? portalGreeting.style.height : '110px',
        commandEchoPanel: commandEcho ? commandEcho.style.height : '180px'
    };
    
    localStorage.setItem('jasvaLayoutState', JSON.stringify({ visibility, widths, heights }));
}

function getPanelVisibility(id) {
    const el = document.getElementById(id);
    return el ? el.style.display !== 'none' : true;
}

function loadLayoutState() {
    try {
        const stateStr = localStorage.getItem('jasvaLayoutState');
        if (!stateStr) return;
        const state = JSON.parse(stateStr);
        
        const layout = document.querySelector('.hud-layout');
        const leftResizer = document.getElementById('leftResizer');
        const rightResizer = document.getElementById('rightResizer');
        
        // Restore widths
        if (state.widths) {
            const leftPanel = document.getElementById('chatPanel');
            const rightPanel = document.getElementById('systemPanel');
            if (leftPanel && state.widths.chatPanel) leftPanel.style.width = state.widths.chatPanel;
            if (rightPanel && state.widths.systemPanel) rightPanel.style.width = state.widths.systemPanel;
        }
        
        // Restore heights
        if (state.heights) {
            const portalGreeting = document.getElementById('portalGreetingPanel');
            const commandEcho = document.getElementById('commandEchoPanel');
            if (portalGreeting && state.heights.portalGreetingPanel) portalGreeting.style.height = state.heights.portalGreetingPanel;
            if (commandEcho && state.heights.commandEchoPanel) commandEcho.style.height = state.heights.commandEchoPanel;
        }
        
        // Restore visibility
        if (state.visibility) {
            Object.keys(state.visibility).forEach(panelId => {
                const show = state.visibility[panelId];
                const panel = document.getElementById(panelId);
                if (panel) {
                    panel.style.display = show ? 'flex' : 'none';
                }
                
                // Update checkboxes
                const chk = document.getElementById(`chk-${panelId}`);
                if (chk) chk.checked = show;
            });
            
            // Adjust layout collapse classes based on left/right panels visibility
            if (layout) {
                if (state.visibility.chatPanel) layout.classList.add('left-open');
                else layout.classList.remove('left-open');
                
                if (state.visibility.systemPanel) layout.classList.add('right-open');
                else layout.classList.remove('right-open');
            }
            
            // Adjust resizers visibility
            if (leftResizer) leftResizer.style.display = state.visibility.chatPanel ? 'block' : 'none';
            if (rightResizer) rightResizer.style.display = state.visibility.systemPanel ? 'block' : 'none';
        }
    } catch (e) {
        console.error("Failed to load layout state:", e);
    }
}

function applyPanelFilter() {
    const params = new URLSearchParams(window.location.search);
    const panel = params.get('panel');
    
    if (panel) {
        document.body.classList.add('panel-mode');
        document.body.classList.add(`mode-${panel}`);
        
        // Hide top command header bar on all windows except the top bar window (panel=top)
        const topBar = document.querySelector('.quantum-top-bar');
        if (topBar) {
            if (panel === 'top') {
                topBar.style.display = 'flex';
            } else {
                topBar.style.display = 'none';
            }
        }
        
        // Hide the other main containers
        const chatPanel = document.getElementById('chatPanel');
        const middleColumn = document.querySelector('.middle-column');
        const systemPanel = document.getElementById('systemPanel');
        
        if (chatPanel) chatPanel.style.display = 'none';
        if (middleColumn) middleColumn.style.display = 'none';
        if (systemPanel) systemPanel.style.display = 'none';
        
        // Hide all resizers in panel mode
        const leftResizer = document.getElementById('leftResizer');
        const rightResizer = document.getElementById('rightResizer');
        const midTopResizer = document.getElementById('midTopResizer');
        const midBotResizer = document.getElementById('midBotResizer');
        if (leftResizer) leftResizer.style.display = 'none';
        if (rightResizer) rightResizer.style.display = 'none';
        if (midTopResizer) midTopResizer.style.display = 'none';
        if (midBotResizer) midBotResizer.style.display = 'none';
        
        // Hide the HUD dropdown trigger except in the top command hub window where the header lives
        const dropdownTrigger = document.querySelector('.hud-dropdown-container');
        if (dropdownTrigger && panel !== 'top') dropdownTrigger.style.display = 'none';
        
        if (panel === 'chat' && chatPanel) {
            chatPanel.style.display = 'flex';
            chatPanel.style.width = '100%';
            chatPanel.style.height = '100%';
        } else if ((panel === 'system' || panel === 'monitor' || panel === 'control') && systemPanel) {
            systemPanel.style.display = 'flex';
            systemPanel.style.width = '100%';
            systemPanel.style.height = '100%';
            const panelTitle = systemPanel.querySelector('.panel-title');
            if (panelTitle) {
                if (panel === 'monitor') panelTitle.textContent = 'MONITOR';
                else if (panel === 'control') panelTitle.textContent = 'DEVICE CONTROL';
                else panelTitle.textContent = 'SYSTEM';
            }
        } else if (panel === 'settings') {
            const settingsOverlay = document.getElementById('settingsOverlay');
            if (settingsOverlay) {
                settingsOverlay.classList.add('active');
                settingsOverlay.style.position = 'relative';
                settingsOverlay.style.width = '100%';
                settingsOverlay.style.height = '100%';
                settingsOverlay.style.background = 'transparent';
            }
        } else if (middleColumn) {
            const portalGreeting = document.getElementById('portalGreetingPanel');
            const activeListening = document.getElementById('activeListeningPanel');
            const commandEcho = document.getElementById('commandEchoPanel');
            
            middleColumn.style.display = 'flex';
            middleColumn.style.width = '100%';
            middleColumn.style.height = '100%';
            middleColumn.style.margin = '0';
            middleColumn.style.gap = '0';
            
            if (panel === 'listening') {
                if (portalGreeting) portalGreeting.style.display = 'flex';
                if (activeListening) activeListening.style.display = 'flex';
                if (commandEcho) commandEcho.style.display = 'flex';
            } else if (panel === 'top') {
                if (portalGreeting) {
                    portalGreeting.style.display = 'flex';
                    portalGreeting.style.width = '100%';
                    portalGreeting.style.height = 'calc(100% - 68px)';
                    portalGreeting.style.flex = 'none';
                }
                if (activeListening) activeListening.style.display = 'none';
                if (commandEcho) commandEcho.style.display = 'none';
            } else if (panel === 'sphere') {
                if (portalGreeting) portalGreeting.style.display = 'none';
                if (activeListening) {
                    activeListening.style.display = 'flex';
                    activeListening.style.width = '100%';
                    activeListening.style.height = '100%';
                    activeListening.style.flex = '1';
                }
                if (commandEcho) commandEcho.style.display = 'none';
            } else if (panel === 'bottom') {
                if (portalGreeting) portalGreeting.style.display = 'none';
                if (activeListening) activeListening.style.display = 'none';
                if (commandEcho) {
                    commandEcho.style.display = 'flex';
                    commandEcho.style.width = '100%';
                    commandEcho.style.height = '100%';
                    commandEcho.style.flex = '1';
                }
            }
        }
    }
}

// Quick Macro helper
window.sendMacroCommand = function(cmdText) {
    const textInput = document.getElementById('textInput');
    if (textInput) {
        textInput.value = cmdText;
        window.sendCommand(cmdText);
    }
};

// ─── Theme Management ───
window.changeHudTheme = function(themeName) {
    if (!themeName) return;
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const shouldAnimate = window.__themeInitialized && currentTheme !== themeName;
    let overlay = null;

    if (shouldAnimate) {
        const oldBg = getComputedStyle(document.documentElement).getPropertyValue('--bg-color').trim() || '#03060d';
        overlay = document.createElement('div');
        overlay.className = 'theme-crossfade';
        overlay.style.background = `radial-gradient(circle at 50% 20%, ${oldBg} 0%, ${oldBg} 70%, #010205 100%)`;
        document.body.appendChild(overlay);
    }

    document.documentElement.setAttribute('data-theme', themeName);
    localStorage.setItem('jasva_theme', themeName);
    
    // Broadcast to all windows via pywebview
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.broadcast_js(`window.applyThemeSync('${themeName}')`);
    }

    // Sync dropdowns
    const themeSelect = document.getElementById('themeSelect');
    if (themeSelect && themeSelect.value !== themeName) {
        themeSelect.value = themeName;
    }
    const headerThemeSelect = document.getElementById('headerThemeSelect');
    if (headerThemeSelect && headerThemeSelect.value !== themeName) {
        headerThemeSelect.value = themeName;
    }

    if (overlay) {
        requestAnimationFrame(() => requestAnimationFrame(() => {
            overlay.classList.add('fade-out');
            setTimeout(() => overlay.remove(), 700);
        }));
    }
    window.__themeInitialized = true;
};

// Apply theme from broadcast (no crossfade, no re-broadcast)
window.applyThemeSync = function(themeName) {
    if (!themeName) return;
    document.documentElement.setAttribute('data-theme', themeName);
    localStorage.setItem('jasva_theme', themeName);
    
    const themeSelect = document.getElementById('themeSelect');
    if (themeSelect && themeSelect.value !== themeName) {
        themeSelect.value = themeName;
    }
    const headerThemeSelect = document.getElementById('headerThemeSelect');
    if (headerThemeSelect && headerThemeSelect.value !== themeName) {
        headerThemeSelect.value = themeName;
    }
};

// Load initial stored theme
const savedTheme = localStorage.getItem('jasva_theme') || 'default';
window.changeHudTheme(savedTheme);

// Expose callbacks to global window scope
window.toggleMic = toggleMic;
window.clearAttachedImage = clearAttachedImage;
window.onImageSelected = onImageSelected;
window.sendCommand = sendCommand;

})();
