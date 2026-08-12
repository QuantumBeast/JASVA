/**
 * shared.js — Shared utilities for all JASVA windows.
 * Provides: markdown parsing, message rendering helpers, notification sound,
 * toast display, and the cross-window state bridge.
 */

// ─── State Variables (shared across modules that include this file) ───
let isVoiceMuted = localStorage.getItem('jasva_muted') === 'true';
let isSpeaking = false;
let isListening = false;
let userIsSpeaking = false;
let isWindowVisible = true;
window.onWindowVisibilityChanged = (visible) => {
    isWindowVisible = visible;
};
let currentAttachedImage = null;
let shouldAutoListen = false;
let isAlwaysListeningMode = false;
let isAlwaysListeningSetting = false;
let currentSpokenText = "";
let lastSpokenText = "";
let lastSpeechEndTime = 0;
let globalSpeechVolume = 0.75;
let globalSpeechSpeed = 1.0;
let currentNeuralAudio = null;

// ─── Utility: Remove trailing sentence full stops ───
function removeSentenceFullStops(str) {
    if (!str) return "";
    return str.replace(/(?<!\.)\.(\\s|$)/g, '$1');
}

// ─── Clipboard Copy Helper for Code Blocks ───
window.copyCodeToClipboard = function(buttonEl) {
    const wrapper = buttonEl.closest('.code-block-wrapper');
    if (!wrapper) return;
    const codeEl = wrapper.querySelector('code');
    if (!codeEl) return;
    
    const textToCopy = codeEl.textContent;
    navigator.clipboard.writeText(textToCopy).then(() => {
        const origText = buttonEl.textContent;
        buttonEl.textContent = 'COPIED!';
        buttonEl.style.color = '#00ff87';
        setTimeout(() => {
            buttonEl.textContent = origText;
            buttonEl.style.color = '';
        }, 2000);
    }).catch(err => {
        console.error('Failed to copy text: ', err);
    });
};

// ─── Markdown-to-HTML Parser ───
function parseMarkdownToHTML(text) {
    if (!text) return "";
    
    let html = text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");

    // Code blocks with optional language
    html = html.replace(/```(\w*)\n?([\s\S]+?)```/g, (match, lang, code) => {
        const langTag = lang ? lang.toUpperCase() : 'CODE';
        return `<div class="code-block-wrapper">
            <div class="code-block-header">
                <span>${langTag}</span>
                <button class="copy-code-btn" onclick="window.copyCodeToClipboard(this)">COPY</button>
            </div>
            <pre><code>${code.trim()}</code></pre>
        </div>`;
    });
    
    // Inline code
    html = html.replace(/`([^`]+?)`/g, '<code>$1</code>');

    // Bold-Italic
    html = html.replace(/\*\*\*([^*]+?)\*\*\*/g, '<strong><em>$1</em></strong>');
    html = html.replace(/___([^_]+?)___/g, '<strong><em>$1</em></strong>');

    // Bold
    html = html.replace(/\*\*([^*]+?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/__([^_]+?)__/g, '<strong>$1</strong>');

    // Italic
    html = html.replace(/\*([^*]+?)\*/g, '<em>$1</em>');
    html = html.replace(/_([^_]+?)_/g, '<em>$1</em>');

    // Underline tags
    html = html.replace(/&lt;u&gt;([\s\S]+?)&lt;\/u&gt;/gi, '<u>$1</u>');

    // Unordered Lists
    const lines = html.split('\n');
    let inList = false;
    let newLines = [];
    
    for (let i = 0; i < lines.length; i++) {
        let line = lines[i];
        const listMatch = line.match(/^(\s*)([-*+])\s+(.+)$/);
        
        if (listMatch) {
            if (!inList) { newLines.push('<ul>'); inList = true; }
            newLines.push(`<li>${listMatch[3]}</li>`);
        } else {
            if (inList) { newLines.push('</ul>'); inList = false; }
            newLines.push(line);
        }
    }
    if (inList) newLines.push('</ul>');
    html = newLines.join('\n');

    // Ordered Lists
    const lines2 = html.split('\n');
    let inOList = false;
    let newLines2 = [];
    
    for (let i = 0; i < lines2.length; i++) {
        let line = lines2[i];
        const olistMatch = line.match(/^(\s*)(\d+)[.)]\s+(.+)$/) || line.match(/^(\s*)(\d+)\s+(\*\*[\s\S]+)$/);
        
        if (olistMatch) {
            if (!inOList) { newLines2.push('<ol>'); inOList = true; }
            const content = olistMatch[3] || olistMatch[0].replace(/^(\s*)\d+\s+/, '');
            newLines2.push(`<li>${content}</li>`);
        } else {
            if (inOList) { newLines2.push('</ol>'); inOList = false; }
            newLines2.push(line);
        }
    }
    if (inOList) newLines2.push('</ol>');
    html = newLines2.join('\n');

    // Line breaks (ignore line breaks inside pre/code blocks)
    html = html.replace(/\n/g, '<br>');
    html = html.replace(/<\/?(ul|ol|li|pre|code|div)><br>/gi, (match) => match.replace('<br>', ''));
    html = html.replace(/<br><\/?(ul|ol|li|pre|code|div)>/gi, (match) => match.replace('<br>', ''));
    html = html.replace(/<li><br>/gi, '<li>');
    html = html.replace(/<\/li><br>/gi, '</li>');

    return html;
}

// ─── Add Message to Chat Container ───
function addMessage(sender, content, className) {
    const chatContainer = document.getElementById('chatContainer');
    if (!chatContainer) return;
    
    const cleanContent = (sender === 'USER' || sender === 'JASVA') ? removeSentenceFullStops(content) : content;
    
    const msgDiv = document.createElement('div');
    msgDiv.className = `chat-message ${sender === 'USER' ? 'user-message' : 'bot-message'} ${className || ''}`;
    
    const senderName = sender === 'USER' ? 'You' : sender;
    
    if (sender === 'JASVA' && !className?.includes('error-msg') && !className?.includes('system-msg')) {
        msgDiv.innerHTML = `
            <div class="message-sender">${senderName}</div>
            <div class="message-text typewriter-cursor"></div>
        `;
        chatContainer.appendChild(msgDiv);
        
        const textEl = msgDiv.querySelector('.message-text');
        let index = 0;
        const typingSpeed = 15;
        
        function typeChar() {
            if (index < cleanContent.length) {
                textEl.textContent += cleanContent.charAt(index);
                index++;
                chatContainer.scrollTop = chatContainer.scrollHeight;
                setTimeout(typeChar, typingSpeed);
            } else {
                textEl.classList.remove('typewriter-cursor');
                textEl.innerHTML = parseMarkdownToHTML(cleanContent);
                chatContainer.scrollTop = chatContainer.scrollHeight;
            }
        }
        typeChar();
    } else {
        msgDiv.innerHTML = `
            <div class="message-sender">${senderName}</div>
            <div class="message-text"></div>
        `;
        msgDiv.querySelector('.message-text').innerHTML = parseMarkdownToHTML(cleanContent);
        chatContainer.appendChild(msgDiv);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }
    
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

// ─── Notification Sound Generator ───
function playNotificationSound(type) {
    if (isVoiceMuted) return;
    try {
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = audioCtx.createOscillator();
        const gainNode = audioCtx.createGain();
        
        oscillator.connect(gainNode);
        gainNode.connect(audioCtx.destination);
        
        if (type === 'alert' || type === 'warning') {
            oscillator.type = 'sawtooth';
            oscillator.frequency.setValueAtTime(880, audioCtx.currentTime);
            oscillator.frequency.exponentialRampToValueAtTime(440, audioCtx.currentTime + 0.35);
            gainNode.gain.setValueAtTime(0.12, audioCtx.currentTime);
            gainNode.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.35);
            oscillator.start();
            oscillator.stop(audioCtx.currentTime + 0.35);
        } else {
            oscillator.type = 'sine';
            oscillator.frequency.setValueAtTime(587.33, audioCtx.currentTime);
            oscillator.frequency.setValueAtTime(880, audioCtx.currentTime + 0.08);
            gainNode.gain.setValueAtTime(0.08, audioCtx.currentTime);
            gainNode.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.3);
            oscillator.start();
            oscillator.stop(audioCtx.currentTime + 0.3);
        }
    } catch (e) {
        console.error("Failed to play notification beep:", e);
    }
}

// ─── Toast Notifications ───
function showToast(notif) {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    
    const toast = document.createElement('div');
    toast.className = `toast-notification ${notif.type || 'info'}`;
    
    toast.innerHTML = `
        <div class="toast-header">
            <span>${notif.title || 'ALERT SYSTEM'}</span>
            <span style="cursor:pointer; font-size: 1.1rem; line-height: 1; color: var(--text-muted);" onclick="this.parentElement.parentElement.remove()">&times;</span>
        </div>
        <div class="toast-message">${notif.message}</div>
    `;
    
    container.appendChild(toast);
    setTimeout(() => { toast.classList.add('active'); }, 10);
    playNotificationSound(notif.type);
    
    if (notif.message && (notif.type === 'timer' || notif.type === 'alert' || notif.type === 'reminder')) {
        if (typeof speakText === 'function') speakText(notif.message);
    }
    
    setTimeout(() => {
        toast.classList.add('exit');
        toast.addEventListener('transitionend', () => { toast.remove(); });
    }, 8000);
}

// ─── Stop Speaking Helper ───
function stopSpeaking() {
    isSpeaking = false;
    currentSpokenText = "";
    lastSpeechEndTime = Date.now();
    if (currentNeuralAudio) {
        try { currentNeuralAudio.pause(); } catch(e){}
        currentNeuralAudio = null;
    }
    if ('speechSynthesis' in window) {
        try { window.speechSynthesis.cancel(); } catch(e){}
    }
}

// ─── Global command hook ───
window.sendCmdDirect = (text, quiet = true) => {
    const cleanText = removeSentenceFullStops(text);
    addMessage('USER', cleanText, 'user-msg');
    if (typeof sendCommand === 'function') sendCommand(cleanText, quiet);
};

// ─── Image Upload Handlers ───
window.onImageSelected = (event) => {
    const file = event.target.files[0];
    if (!file) return;
    
    const reader = new FileReader();
    reader.onload = function(e) {
        const base64Data = e.target.result.split(',')[1];
        currentAttachedImage = {
            base64: base64Data,
            mimeType: file.type,
            name: file.name
        };
        
        const previewContainer = document.getElementById('imagePreviewContainer');
        const previewImg = document.getElementById('imagePreview');
        const nameText = document.getElementById('imageNameText');
        
        if (previewImg) previewImg.src = e.target.result;
        if (nameText) nameText.textContent = file.name;
        if (previewContainer) previewContainer.style.display = 'flex';
    };
    reader.readAsDataURL(file);
};

window.clearAttachedImage = () => {
    currentAttachedImage = null;
    const previewContainer = document.getElementById('imagePreviewContainer');
    const imageInput = document.getElementById('imageInput');
    if (previewContainer) previewContainer.style.display = 'none';
    if (imageInput) imageInput.value = '';
};

// ─── Window Controls Bridge Functions ───
window.minimizeWindow = function() {
    if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.minimize_window === 'function') {
        window.pywebview.api.minimize_window();
    } else if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.minimize_current_window === 'function') {
        window.pywebview.api.minimize_current_window();
    } else {
        console.log("Minimize window requested");
    }
};

window.exitApplication = function() {
    if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.close_window === 'function') {
        window.pywebview.api.close_window();
    } else {
        console.log("Exit application requested");
    }
};

// ─── Drag & Drop sub-window repositioning helper ───
function makePanelsDraggable() {
    const panels = document.querySelectorAll('.panel-window');
    
    panels.forEach(panel => {
        const header = panel.querySelector('.panel-header') || panel.querySelector('.settings-header');
        if (!header) return; // Strict: drag allowed ONLY on header bars
        header.style.cursor = 'move';
        
        let offsetX = 0;
        let offsetY = 0;
        let isDraggingPanel = false;
        let startMouseX = 0;
        let startMouseY = 0;
        let startPanelX = 0;
        let startPanelY = 0;
        
        header.addEventListener('mousedown', (e) => {
            if (e.button !== 0) return;
            if (e.target.closest('button') || e.target.closest('input') || e.target.closest('select') || e.target.closest('textarea') || e.target.closest('.hud-dropdown-container') || e.target.closest('.header-select-pill') || e.target.closest('.hud-icon-btn')) {
                return;
            }
            
            isDraggingPanel = true;
            startMouseX = e.clientX;
            startMouseY = e.clientY;
            
            const style = window.getComputedStyle(panel);
            const matrix = new DOMMatrix(style.transform);
            startPanelX = matrix.m41;
            startPanelY = matrix.m42;
            
            // Bring active dragged panel to front
            panels.forEach(p => p.style.zIndex = '10');
            panel.style.zIndex = '20';
            
            e.preventDefault();
        });
        
        window.addEventListener('mousemove', (e) => {
            if (!isDraggingPanel) return;
            const dx = e.clientX - startMouseX;
            const dy = e.clientY - startMouseY;
            offsetX = startPanelX + dx;
            offsetY = startPanelY + dy;
            panel.style.transform = `translate(${offsetX}px, ${offsetY}px)`;
        });
        
        window.addEventListener('mouseup', () => {
            isDraggingPanel = false;
        });
    });
}

window.addEventListener('DOMContentLoaded', makePanelsDraggable);

// ─── Manual Keybind Reload (F5 / Ctrl+R) ───
window.addEventListener('keydown', (e) => {
    if (e.key === 'F5' || (e.ctrlKey && (e.key === 'r' || e.key === 'R'))) {
        e.preventDefault();
        window.location.reload();
    }
});

// ─── Universal Interactive Feedback (Ripple) ───
// Any clickable control gets an instant, seamless light pulse so every action
// has a visible response regardless of which module owns the handler.
window.addEventListener('pointerdown', (e) => {
    const el = e.target.closest('button, .stage-pill, .menu-item, .hud-dropdown-trigger, .panel-close-dot, .tv-app-btn, .phone-action-btn, .dpad-mini-btn, .dpad-mini-center, .tv-ctrl-btn');
    if (!el || el.disabled) return;
    const ripple = document.createElement('span');
    ripple.className = 'btn-ripple-effect';
    const rect = el.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height);
    ripple.style.width = ripple.style.height = size + 'px';
    ripple.style.left = (e.clientX - rect.left - size / 2) + 'px';
    ripple.style.top = (e.clientY - rect.top - size / 2) + 'px';
    const pos = getComputedStyle(el).position;
    if (pos === 'static') el.style.position = 'relative';
    el.appendChild(ripple);
    setTimeout(() => ripple.remove(), 600);
});

// ─── Song-driven Dynamic Accent Sync ───
// Applied to every JASVA window via broadcast; retheme accent CSS vars from the
// album-art dominant colors while keeping the user's chosen base theme intact.
window.handleSongAccent = function(colors) {
    const root = document.documentElement;
    if (!colors || !Array.isArray(colors) || colors.length < 3) {
        // No song colors: fall back to the stored theme's accent values.
        const theme = root.getAttribute('data-theme') || 'default';
        const accents = {
            default:   ['#00f2fe', '#4facfe', 'rgba(0, 242, 254, 0.35)'],
            purple:    ['#bd00ff', '#7000ff', 'rgba(189, 0, 255, 0.35)'],
            green:     ['#00ff87', '#60efff', 'rgba(0, 255, 135, 0.35)'],
            orange:    ['#ff8800', '#ff5500', 'rgba(255, 136, 0, 0.35)'],
            red:       ['#ff3b30', '#ff2d55', 'rgba(255, 59, 48, 0.35)'],
            light:     ['#007aff', '#5856d6', 'rgba(0, 122, 255, 0.2)']
        }[theme] || ['#00f2fe', '#4facfe', 'rgba(0, 242, 254, 0.35)'];
        root.style.setProperty('--accent-color', accents[0]);
        root.style.setProperty('--accent-secondary', accents[1]);
        root.style.setProperty('--accent-glow', accents[2]);
        root.style.setProperty('--accent-gradient', `linear-gradient(135deg, ${accents[0]} 0%, ${accents[1]} 100%)`);
        return;
    }

    const c1 = Array.isArray(colors[0]) ? colors[0] : null;
    const c2 = Array.isArray(colors[1]) ? colors[1] : colors[0];
    const c3 = Array.isArray(colors[2]) ? colors[2] : colors[colors.length - 1];
    if (!c1 || c1.length < 3) return;

    const a = `rgb(${c1[0]}, ${c1[1]}, ${c1[2]})`;
    const b = Array.isArray(c2) && c2.length >= 3 ? `rgb(${c2[0]}, ${c2[1]}, ${c2[2]})` : a;
    const glow = `rgba(${c1[0]}, ${c1[1]}, ${c1[2]}, 0.35)`;

    root.style.setProperty('--accent-color', a);
    root.style.setProperty('--accent-secondary', b);
    root.style.setProperty('--accent-glow', glow);
    root.style.setProperty('--accent-gradient', `linear-gradient(135deg, ${a} 0%, ${b} 100%)`);
};

// ─── Panel Visibility Helper ───
window.isPanelVisibleInWindow = function(panelName) {
    const params = new URLSearchParams(window.location.search);
    const activePanel = params.get('panel');
    if (!activePanel) {
        // Unified mode: check if it's display: none or not
        const el = document.getElementById(panelName);
        return el && el.style.display !== 'none';
    }
    // Individual panel window mode: a panel is visible in this window when this
    // window IS that panel, or (for the system column inside the chat window)
    // when its element is actually shown there.
    if (panelName === 'chatPanel') return activePanel === 'chat';
    if (panelName === 'portalGreetingPanel') return activePanel === 'top';
    if (panelName === 'activeListeningPanel') return activePanel === 'sphere';
    if (panelName === 'commandEchoPanel') return activePanel === 'bottom';
    if (panelName === 'systemPanel') {
        if (activePanel === 'system' || activePanel === 'monitor' || activePanel === 'control') return true;
        if (activePanel === 'chat') {
            const el = document.getElementById(panelName);
            return el && el.style.display !== 'none';
        }
        return false;
    }
    if (panelName === 'settingsOverlay') return activePanel === 'settings';
    return false;
};


