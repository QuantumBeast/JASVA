// ─── WebSocket Connection ───
let ws;
const host = window.location.host;
const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const wsUrl = `${wsProtocol}//${host}/ws`;

function connectWebSocket() {
    ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
        updateConnectionStatus(true);
        // Request current status
        fetchStatus();
    };
    
    ws.onclose = () => {
        updateConnectionStatus(false);
        // Try to reconnect in 3 seconds
        setTimeout(connectWebSocket, 3000);
    };
    
    ws.onerror = (err) => {
        console.error("WS connection error:", err);
    };
}

function updateConnectionStatus(isConnected) {
    const badge = document.getElementById("connStatus");
    const label = badge.querySelector("span");
    const dot = badge.querySelector(".status-dot");
    
    if (isConnected) {
        label.innerText = "CONNECTED";
        badge.style.background = "rgba(0, 242, 254, 0.1)";
        badge.style.borderColor = "rgba(0, 242, 254, 0.2)";
        badge.style.color = "var(--accent-cyan)";
        dot.style.backgroundColor = "var(--accent-cyan)";
    } else {
        label.innerText = "OFFLINE";
        badge.style.background = "rgba(243, 85, 136, 0.1)";
        badge.style.borderColor = "rgba(243, 85, 136, 0.2)";
        badge.style.color = "var(--accent-magenta)";
        dot.style.backgroundColor = "var(--accent-magenta)";
    }
}

// ─── Tabs Switching ───
window.switchTab = function(panelId) {
    // Update active tab buttons
    document.querySelectorAll(".tab-btn").forEach(btn => {
        btn.classList.remove("active");
    });
    
    // Find active tab button corresponding to the panel
    const btnIndex = panelId === 'chat-panel' ? 0 : (panelId === 'trackpad-panel' ? 1 : 2);
    document.querySelectorAll(".tab-btn")[btnIndex].classList.add("active");
    
    // Update active panels
    document.querySelectorAll(".panel").forEach(p => {
        p.classList.remove("active");
    });
    document.getElementById(panelId).classList.add("active");
};

// ─── Trackpad Gesture Logic ───
const trackpadArea = document.getElementById("trackpadArea");
let lastTouchX = 0;
let lastTouchY = 0;
let isMoving = false;
let touchStartTime = 0;
let moveThreshold = 4;
let touchStartPos = { x: 0, y: 0 };

trackpadArea.addEventListener("touchstart", (e) => {
    if (e.touches.length === 1) {
        const touch = e.touches[0];
        lastTouchX = touch.clientX;
        lastTouchY = touch.clientY;
        touchStartPos.x = touch.clientX;
        touchStartPos.y = touch.clientY;
        isMoving = true;
        touchStartTime = Date.now();
    }
});

trackpadArea.addEventListener("touchmove", (e) => {
    if (isMoving && e.touches.length === 1) {
        const touch = e.touches[0];
        const dx = touch.clientX - lastTouchX;
        const dy = touch.clientY - lastTouchY;
        
        // Apply acceleration multiplier
        const speedMultiplier = 1.6;
        
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
                type: "mouse_move",
                dx: dx * speedMultiplier,
                dy: dy * speedMultiplier
            }));
        }
        
        lastTouchX = touch.clientX;
        lastTouchY = touch.clientY;
    }
});

trackpadArea.addEventListener("touchend", (e) => {
    if (isMoving) {
        isMoving = false;
        const duration = Date.now() - touchStartTime;
        // Check end coordinates
        const endTouch = e.changedTouches[0];
        const dist = Math.hypot(endTouch.clientX - touchStartPos.x, endTouch.clientY - touchStartPos.y);
        
        // If touch was quick and did not move much, trigger click
        if (duration < 200 && dist < moveThreshold) {
            sendMouseClick('left');
        }
    }
});

window.sendMouseClick = function(button) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
            type: "mouse_click",
            button: button
        }));
    }
};

// ─── Keyboard Input Handling ───
window.handleKeyboardInput = function(e) {
    const val = e.target.value;
    if (val.length > 0) {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
                type: "keyboard_input",
                text: val
            }));
        }
        // Reset field
        e.target.value = "";
    }
};

window.sendKeyboardEvent = function(keyName) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
            type: "key_event",
            key: keyName
        }));
    }
};

// ─── TV Remote Controls ───
window.sendTvButton = function(btnName) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
            type: "tv_button",
            button: btnName
        }));
    }
};

window.launchTvApp = function(appName) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
            type: "tv_app",
            app: appName
        }));
    }
};

window.updateTvIp = function() {
    const ipInput = document.getElementById("tvIpInput");
    const ip = ipInput.value.trim();
    if (!ip) return;
    
    fetch(`/api/set_tv_ip?ip=${encodeURIComponent(ip)}`)
        .then(res => res.json())
        .then(data => {
            alert(data.message);
        })
        .catch(err => {
            console.error("Error setting TV IP:", err);
        });
};

function fetchStatus() {
    fetch('/api/status')
        .then(res => res.json())
        .then(data => {
            if (data.tv_ip) {
                document.getElementById("tvIpInput").value = data.tv_ip;
            }
        })
        .catch(err => console.error("Error fetching status:", err));
}

// ─── Chat Core Control & Speech Recognition ───
const chatOutput = document.getElementById("chatOutput");
const chatInput = document.getElementById("chatInput");
const micBtn = document.getElementById("micBtn");

window.handleInputKey = function(e) {
    if (e.key === "Enter") {
        transmitCommand();
    }
};

window.transmitCommand = function(text = null) {
    const cmdText = text || chatInput.value.trim();
    if (!cmdText) return;
    
    // Clear input
    if (!text) {
        chatInput.value = "";
    }
    
    // Add user message bubble
    appendMessage(cmdText, "user");
    
    // Show temporary typing status
    const typingBubble = appendMessage("Thinking...", "ai");
    
    // Send request to server
    fetch('/api/command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: cmdText })
    })
    .then(res => res.json())
    .then(data => {
        typingBubble.remove();
        if (data.output) {
            appendMessage(data.output, "ai");
        } else if (data.reply) {
            appendMessage(data.reply, "ai");
        } else {
            appendMessage("Command executed successfully, sir.", "ai");
        }
    })
    .catch(err => {
        typingBubble.remove();
        appendMessage("Transmission failed: Unable to reach JASVA core on PC.", "ai");
        console.error("Command error:", err);
    });
};

function appendMessage(text, sender) {
    const bubble = document.createElement("div");
    bubble.className = `message ${sender}`;
    bubble.innerText = text;
    chatOutput.appendChild(bubble);
    chatOutput.scrollTop = chatOutput.scrollHeight;
    return bubble;
}

// ─── Web Speech Recognition ───
let recognition;
let isListening = false;

if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'en-US';
    
    recognition.onstart = () => {
        isListening = true;
        micBtn.classList.add("listening");
        chatInput.placeholder = "Listening...";
    };
    
    recognition.onresult = (event) => {
        const textResult = event.results[0][0].transcript;
        transmitCommand(textResult);
    };
    
    recognition.onerror = (event) => {
        console.error("Speech recognition error:", event.error);
        stopListening();
    };
    
    recognition.onend = () => {
        stopListening();
    };
}

window.toggleVoiceDictation = function() {
    if (!recognition) {
        alert("Speech recognition is not supported on this browser/device.");
        return;
    }
    
    if (isListening) {
        recognition.stop();
    } else {
        recognition.start();
    }
};

function stopListening() {
    isListening = false;
    micBtn.classList.remove("listening");
    chatInput.placeholder = "Transmit command...";
}

// Initial websocket call
connectWebSocket();
