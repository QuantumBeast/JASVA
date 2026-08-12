(() => {
/**
 * sphere.js — Interactive Plexus Bio-Core Visualizer for JASVA.
 * Renders a 3D particle plexus sphere that is aware, curious, and reacts to states.
 * Features 8 seamless animation modes + 3D spatial wandering + state-driven colors.
 */

const canvas = document.getElementById('wavesCanvas');
const ctx = canvas ? canvas.getContext('2d') : null;
const statusLabel = document.getElementById('statusLabel');

// ─── Visualizer Configuration ───
const numParticles = 240;
const particles = [];
const goldenRatio = (1 + Math.sqrt(5)) / 2;

// ─── Interaction & Physics State ───
let angleX = 0.5;
let angleY = 0.5;
let targetAngleX = 0.5;
let targetAngleY = 0.5;
let isMouseDown = false;
let isDragging = false;
let dragStartX = 0;
let dragStartY = 0;
let startAngleX = 0.5;
let startAngleY = 0.5;
let zoomLevel = 1.0;
let targetZoom = 1.0;

// Mouse track coordinates (relative to center)
let mouseX = 0;
let mouseY = 0;
let isMouseOver = false;

// Create 3D particles on a golden-ratio sphere
for (let i = 0; i < numParticles; i++) {
    const lat = Math.asin(1 - (2 * i) / numParticles);
    const lon = (2 * Math.PI * i) / goldenRatio;

    const x = Math.cos(lat) * Math.cos(lon);
    const y = Math.cos(lat) * Math.sin(lon);
    const z = Math.sin(lat);

    particles.push({
        x: x, y: y, z: z,
        baseSize: Math.random() * 1.5 + 0.8,
        phase: Math.random() * Math.PI * 2,
        seed: Math.random()
    });
}

let pulseTime = 0;
let currentR = 0, currentG = 130, currentB = 255;

// ─── Animation Mode Engine ───
const ANIM_MODES = ['orbit', 'breathe', 'swirl', 'morph', 'pulsewave', 'ripple', 'tunnel', 'chaos'];
let currentAnimIdx = 0;
let animTimer = 0;
let animHeld = 0;              // ms spent in current mode before next switch
let blend = 1.0;              // 0 -> current, 1 -> next; crossfade weight
let switching = false;
let nextAnimIdx = 0;

function pickNextAnim() {
    let next;
    do {
        next = Math.floor(Math.random() * ANIM_MODES.length);
    } while (next === currentAnimIdx && ANIM_MODES.length > 1);
    return next;
}

// Schedule an animation switch (holds longer when speaking/processing for calm)
function scheduleAnimSwitch() {
    if (switching) return;
    switching = true;
    nextAnimIdx = pickNextAnim();
    blend = 0.0;
}

// ─── 3D Spatial Wander (moves the whole sphere around in space) ───
let wanderX = 0, wanderY = 0, wanderZ = 0;
let wanderTargetX = 0, wanderTargetY = 0, wanderTargetZ = 0;
let wanderTime = 0;

function updateWander(dt) {
    wanderTime += dt * 0.001;
    // Pick a new spatial destination periodically (curious roaming)
    if (Math.random() < 0.004) {
        wanderTargetX = (Math.random() * 2 - 1) * 0.18;
        wanderTargetY = (Math.random() * 2 - 1) * 0.14;
        wanderTargetZ = (Math.random() * 2 - 1) * 0.18;
    }
    const ease = 0.008;
    wanderX += (wanderTargetX - wanderX) * ease;
    wanderY += (wanderTargetY - wanderY) * ease;
    wanderZ += (wanderTargetZ - wanderZ) * ease;
    // Add gentle idle breathing on the wander path
    wanderX += Math.sin(wanderTime * 0.3) * 0.0002;
    wanderY += Math.cos(wanderTime * 0.21) * 0.0002;
}

// State polling flags
let sphereIsListening = false;
let sphereIsSpeaking = false;
let sphereIsProcessing = false;
let sphereIsRecognizing = false;

function resizeCanvas() {
    if (canvas && canvas.parentElement) {
        const parentW = canvas.parentElement.clientWidth;
        const parentH = canvas.parentElement.clientHeight;
        const scale = Math.min(1.5, 800 / Math.max(parentW, parentH));
        canvas.width = Math.round(parentW * scale);
        canvas.height = Math.round(parentH * scale);
        canvas.style.width = '100%';
        canvas.style.height = '100%';
    }
}

// Track mouse position over visualizer
if (canvas) {
    canvas.addEventListener('mousemove', (e) => {
        const rect = canvas.getBoundingClientRect();
        const cx = rect.left + rect.width / 2;
        const cy = rect.top + rect.height / 2;
        mouseX = (e.clientX - cx) / (rect.width / 2);
        mouseY = (e.clientY - cy) / (rect.height / 2);
        isMouseOver = true;
    });

    canvas.addEventListener('mouseleave', () => {
        isMouseOver = false;
        mouseX = 0;
        mouseY = 0;
    });

    // Scroll to zoom (curious: lean in / back away)
    canvas.addEventListener('wheel', (e) => {
        e.preventDefault();
        targetZoom = Math.max(0.55, Math.min(1.6, targetZoom - e.deltaY * 0.001));
    }, { passive: false });
}

// ─── Animation Positioners: return {x, y, z} offsets per particle index ───
function animPositions(mode, i, t, amp, seed) {
    const f = t * 0.001;
    switch (mode) {
        case 'orbit':
            // Classic idle rotation handled by base angles; add subtle axial wobble
            return { x: 0, y: Math.sin(f * 0.8 + seed * 6.28) * 0.05, z: 0 };
        case 'breathe':
            // Slow radial breathing swell
            return { x: 0, y: 0, z: 0, swell: Math.sin(f * 1.2 + seed * 6.28) * 0.14 };
        case 'swirl':
            // Spiral vortex twist around Y
            return { x: 0, y: 0, z: 0, twist: Math.sin(f * 1.6 + i * 0.12) * 0.35 };
        case 'morph':
            // Gentle surface deformation (metaball-ish wobble)
            return { x: 0, y: 0, z: 0, morph: Math.sin(f * 2.0 + seed * 6.28) * 0.3 };
        case 'pulsewave':
            // Concentric expanding shockwave
            return { x: 0, y: 0, z: 0, wave: Math.sin((i * 0.05 - f * 2.2)) * 0.22 };
        case 'ripple':
            // Liquid ripple rings moving across surface
            return { x: 0, y: 0, z: 0, ripple: Math.sin(i * 0.4 + f * 3.0) * 0.18 };
        case 'tunnel':
            // Particles pull toward viewer / recede (depth tunnel)
            return { x: 0, y: 0, z: Math.sin(f * 1.4 + i * 0.2) * 0.5 };
        case 'chaos':
            // Organic turbulence, all axes jitter
            return {
                x: Math.sin(f * 3.1 + seed * 9) * 0.1,
                y: Math.cos(f * 2.7 + seed * 7) * 0.1,
                z: Math.sin(f * 3.7 + seed * 5) * 0.12
            };
        default:
            return { x: 0, y: 0, z: 0 };
    }
}

let lastParentW = 0;
let lastParentH = 0;
let lastFrameTime = 0;
let lastDrawTime = performance.now();

function drawVisualizer(timestamp) {
    if (!canvas || !ctx) return;

    const panelVisible = !window.isPanelVisibleInWindow || window.isPanelVisibleInWindow('activeListeningPanel');

    // When the panel is not visible in this window, avoid burning rAF cycles:
    // re-check on a slow timer instead of every display frame.
    if (!panelVisible) {
        setTimeout(() => requestAnimationFrame(drawVisualizer), 250);
        return;
    }

    requestAnimationFrame(drawVisualizer);

    // Adaptive frame rate: full speed only while active, slower when idle
    const visualActive = sphereIsListening || sphereIsSpeaking || sphereIsRecognizing || sphereIsProcessing;
    const fpsInterval = 1000 / (visualActive ? 45 : 30);

    const parentW = canvas.parentElement ? canvas.parentElement.clientWidth : 0;
    const parentH = canvas.parentElement ? canvas.parentElement.clientHeight : 0;
    if (parentW !== lastParentW || parentH !== lastParentH || canvas.width === 0) {
        lastParentW = parentW;
        lastParentH = parentH;
        resizeCanvas();
    }

    if (typeof isWindowVisible !== 'undefined' && !isWindowVisible) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        return;
    }

    if (!timestamp) return;
    const elapsed = timestamp - lastFrameTime;
    if (elapsed < fpsInterval) return;
    lastFrameTime = timestamp - (elapsed % fpsInterval);
    const dt = timestamp - lastDrawTime;
    lastDrawTime = timestamp;

    // ─── Animation switching (seamless crossfade) ───
    animHeld += dt;
    // Decide when to switch: faster when idle, slower when busy
    const baseHold = sphereIsProcessing ? 6500 : sphereIsSpeaking ? 5500 : 3500;
    if (animHeld > baseHold + Math.random() * 2500) {
        scheduleAnimSwitch();
        animHeld = 0;
    }
    if (switching) {
        blend += dt * 0.0012;   // ~0.8s crossfade
        if (blend >= 1) {
            blend = 1;
            switching = false;
            currentAnimIdx = nextAnimIdx;
        }
    } else {
        // Hold current mode at full weight
        blend = 1.0;
    }

    updateWander(dt);

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const centerX = canvas.width / 2;
    const centerY = canvas.height / 2;
    const minDimension = Math.min(canvas.width, canvas.height);

    const emotion = window.sphereEmotion || 'calm';

    // ─── State → Color mapping (what JASVA is doing) ───
    let targetR = 0, targetG = 130, targetB = 255;
    let rotationSpeed = 1.0;
    let waveAmplitude = 1.0;
    let baseDepthScale = 1.0;
    let floatSpeed = 1.0;
    let floatAmp = 1.0;
    let animBias = 0;    // biases which animation modes are favored

    if (emotion === 'happy') {
        targetR = 240; targetG = 180; targetB = 0;
        rotationSpeed = 1.6; waveAmplitude = 1.3; baseDepthScale = 1.1; floatSpeed = 1.8; floatAmp = 1.2;
        animBias = 1;
    } else if (emotion === 'excited') {
        targetR = 255; targetG = 0; targetB = 128;
        rotationSpeed = 2.4; waveAmplitude = 1.8; baseDepthScale = 1.25; floatSpeed = 2.5; floatAmp = 1.6;
        animBias = 2;
    } else if (emotion === 'sad') {
        targetR = 75; targetG = 0; targetB = 150;
        rotationSpeed = 0.4; waveAmplitude = 0.5; baseDepthScale = 0.75; floatSpeed = 0.4; floatAmp = 0.5;
        animBias = -1;
    } else if (emotion === 'angry') {
        targetR = 255; targetG = 30; targetB = 30;
        rotationSpeed = 3.0; waveAmplitude = 2.2; baseDepthScale = 1.0; floatSpeed = 3.0; floatAmp = 0.8;
        animBias = 3;
    } else if (emotion === 'curious') {
        targetR = 140; targetG = 0; targetB = 255;
        rotationSpeed = 0.8; waveAmplitude = 0.9; baseDepthScale = 1.2; floatSpeed = 1.2; floatAmp = 1.4;
        animBias = 1;
    }

    // Work-state color overrides
    let modeHint = '';
    if (sphereIsListening && sphereIsRecognizing) {
        targetR = 0; targetG = 255; targetB = 100;
        modeHint = 'listening';
    } else if (sphereIsProcessing) {
        targetR = 255; targetG = 100; targetB = 0;
        modeHint = 'processing';
    } else if (sphereIsSpeaking) {
        targetR = 0; targetG = 242; targetB = 254;
        modeHint = 'speaking';
    }

    currentR += (targetR - currentR) * 0.08;
    currentG += (targetG - currentG) * 0.08;
    currentB += (targetB - currentB) * 0.08;

    pulseTime += 1;

    // Apply zoom (from scroll / emotional depth)
    zoomLevel += (targetZoom - zoomLevel) * 0.06;
    const dynamicZoom = baseDepthScale * zoomLevel * (1.0 + Math.sin(pulseTime * 0.02 * floatSpeed) * 0.12 * floatAmp);

    // ─── Curiosity: Look Towards Mouse & organic drift ───
    if (isMouseDown) {
        // Drag control overrides
    } else if (isMouseOver) {
        targetAngleY = mouseX * 0.8;
        targetAngleX = -mouseY * 0.8;
        angleY += (targetAngleY - angleY) * 0.08 * rotationSpeed;
        angleX += (targetAngleX - angleX) * 0.08 * rotationSpeed;
    } else {
        angleY += 0.004 * rotationSpeed;
        angleX += 0.002 * rotationSpeed;
    }

    // Spatial wander applied to focal center
    const driftX = Math.sin(pulseTime * 0.02 * floatSpeed) * 12 * floatAmp + wanderX * minDimension * 0.3;
    const driftY = Math.cos(pulseTime * 0.015 * floatSpeed) * 8 * floatAmp + wanderY * minDimension * 0.3;
    const renderCX = centerX + driftX;
    const renderCY = centerY + driftY;
    const depthShift = wanderZ; // pushes whole sphere into/out of the screen

    const cosY = Math.cos(angleY);
    const sinY = Math.sin(angleY);
    const cosX = Math.cos(angleX);
    const sinX = Math.sin(angleX);

    const outerRadius = minDimension * 0.32 * dynamicZoom;
    const innerRadius = minDimension * 0.15 * dynamicZoom;

    // Volumetric background glow
    const glowGrad = ctx.createRadialGradient(renderCX, renderCY, innerRadius * 0.2, renderCX, renderCY, outerRadius * 1.6);
    if (modeHint === 'processing') {
        glowGrad.addColorStop(0, 'rgba(255, 100, 0, 0.18)');
        glowGrad.addColorStop(0.5, 'rgba(255, 100, 0, 0.04)');
    } else if (modeHint === 'listening') {
        glowGrad.addColorStop(0, 'rgba(0, 255, 100, 0.18)');
        glowGrad.addColorStop(0.5, 'rgba(0, 255, 100, 0.04)');
    } else {
        glowGrad.addColorStop(0, `rgba(${Math.round(currentR)}, ${Math.round(currentG)}, ${Math.round(currentB)}, 0.14)`);
        glowGrad.addColorStop(0.5, `rgba(${Math.round(currentR)}, ${Math.round(currentG)}, ${Math.round(currentB)}, 0.03)`);
    }
    glowGrad.addColorStop(1, 'transparent');
    ctx.fillStyle = glowGrad;
    ctx.beginPath();
    ctx.arc(renderCX, renderCY, outerRadius * 1.6, 0, 2 * Math.PI);
    ctx.fill();

    // Get positioners for current + next animation (crossfade)
    const posA = (i) => animPositions(ANIM_MODES[currentAnimIdx], i, pulseTime, 1, particles[i].seed);
    const posB = (i) => animPositions(ANIM_MODES[nextAnimIdx], i, pulseTime, 1, particles[i].seed);

    // Project particles
    const projected = [];
    for (let i = 0; i < numParticles; i++) {
        const p = particles[i];

        const pa = posA(i);
        const pb = posB(i);
        // Crossfade the two animation offsets
        const off = {
            x: pa.x + (pb.x - pa.x) * blend,
            y: pa.y + (pb.y - pa.y) * blend,
            z: pa.z + (pb.z - pa.z) * blend,
            swell: (pa.swell || 0) + ((pb.swell || 0) - (pa.swell || 0)) * blend,
            twist: (pa.twist || 0) + ((pb.twist || 0) - (pa.twist || 0)) * blend,
            morph: (pa.morph || 0) + ((pb.morph || 0) - (pa.morph || 0)) * blend,
            wave: (pa.wave || 0) + ((pb.wave || 0) - (pa.wave || 0)) * blend,
            ripple: (pa.ripple || 0) + ((pb.ripple || 0) - (pa.ripple || 0)) * blend
        };

        // Base 3D rotation
        const x1 = p.x * cosY - p.z * sinY;
        const z1 = p.x * sinY + p.z * cosY;
        const y2 = p.y * cosX - z1 * sinX;
        const z2 = p.y * sinX + z1 * cosX;

        // Apply animation offsets in rotated space
        let ox = x1 + off.x;
        let oy = y2 + off.y;
        let oz = z2 + off.z + depthShift;

        // Twist effect (swirl): rotate around Y by offset angle
        if (off.twist) {
            const tw = off.twist;
            const cTw = Math.cos(tw), sTw = Math.sin(tw);
            const nx = ox * cTw - oz * sTw;
            const nz = ox * sTw + oz * cTw;
            ox = nx; oz = nz;
        }
        // Morph: radial displacement
        let rad = Math.sqrt(ox*ox + oy*oy + oz*oz) || 1;
        if (off.morph) {
            const grow = 1 + off.morph;
            ox *= grow; oy *= grow; oz *= grow;
            rad *= grow;
        }
        // Wave / ripple: push radially outward based on phase
        if (off.wave) {
            const push = off.wave;
            ox *= (1 + push); oy *= (1 + push); oz *= (1 + push);
            rad *= (1 + push);
        }
        if (off.ripple) {
            const push = off.ripple;
            ox *= (1 + push); oy *= (1 + push); oz *= (1 + push);
            rad *= (1 + push);
        }

        // Spatial coordinate wave offsets (liquid ripples) + activity swell
        const spatialFactor = ox * 2.0 + oy * 2.0 + oz * 1.5;
        let wave = 0;
        if (sphereIsListening && sphereIsRecognizing) {
            wave = Math.sin(spatialFactor * 1.5 + pulseTime * 0.25) * 0.15;
        } else if (sphereIsSpeaking) {
            wave = Math.sin(spatialFactor * 1.2 + pulseTime * 0.18) * 0.10 * waveAmplitude;
        } else if (sphereIsProcessing) {
            wave = Math.sin(spatialFactor * 3.0 + pulseTime * 0.3) * 0.04 * waveAmplitude;
        } else {
            wave = (Math.sin(spatialFactor + pulseTime * 0.03 * floatSpeed) * 0.05
                  + Math.cos(spatialFactor * 2.2 - pulseTime * 0.015 * floatSpeed) * 0.02) * waveAmplitude;
        }

        // Breathe swell modifier
        let baseRadius = outerRadius * (1.0 + wave);
        if (off.swell) {
            baseRadius *= (1 + off.swell);
        }

        const px = renderCX + ox * baseRadius;
        const py = renderCY + oy * baseRadius;

        // Normalize depth for shading (account for z offset + tunnel)
        const depthFraction = Math.max(0, Math.min(1, (oz + 1.2) / 2.4));
        const sizeVal = Math.max(1.1, p.baseSize * (0.6 + depthFraction * 0.8) * (minDimension / 320));

        projected.push({ x: px, y: py, z: oz, size: sizeVal, depth: depthFraction, colorType: p.phase });
    }

    // Sort back-to-front
    projected.sort((a, b) => a.z - b.z);

    // ─── Render Plexus Synapses ───
    ctx.lineWidth = 0.8;
    const maxDist = minDimension * 0.12;
    for (let i = 0; i < projected.length; i++) {
        const p1 = projected[i];
        let connectionCount = 0;
        const maxConnections = sphereIsProcessing ? 4 : 2;
        for (let j = i + 1; j < projected.length; j++) {
            const p2 = projected[j];
            const dx = p1.x - p2.x;
            const dy = p1.y - p2.y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            if (dist < maxDist) {
                const alpha = (1.0 - dist / maxDist) * 0.15 * Math.min(p1.depth, p2.depth)
                    * (0.8 + Math.sin(pulseTime * 0.05 + p1.colorType) * 0.2);
                ctx.strokeStyle = `rgba(${Math.round(currentR)}, ${Math.round(currentG)}, ${Math.round(currentB)}, ${alpha})`;
                ctx.beginPath();
                ctx.moveTo(p1.x, p1.y);
                ctx.lineTo(p2.x, p2.y);
                ctx.stroke();
                connectionCount++;
                if (connectionCount >= maxConnections) break;
            }
        }
    }

    // ─── Render Plexus Dots ───
    for (let i = 0; i < projected.length; i++) {
        const p = projected[i];
        const twinkle = 0.8 + Math.sin(pulseTime * 0.08 + p.colorType) * 0.2;
        const alpha = p.depth * 0.85 * twinkle;
        ctx.fillStyle = `rgba(${Math.round(currentR * 0.8 + 50)}, ${Math.round(currentG * 0.8 + 50)}, ${Math.round(currentB * 0.8 + 50)}, ${alpha})`;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, 2 * Math.PI);
        ctx.fill();
    }

    // ─── Render Holographic Plasma Core ───
    ctx.globalCompositeOperation = 'lighter';
    const coreSwell = 1.0 + Math.sin(pulseTime * 0.05) * 0.08;
    const coreSize = innerRadius * coreSwell;
    const coreGrad = ctx.createRadialGradient(renderCX, renderCY, 0, renderCX, renderCY, coreSize);
    if (modeHint === 'processing') {
        coreGrad.addColorStop(0, 'rgba(255, 100, 0, 0.8)');
        coreGrad.addColorStop(0.4, 'rgba(255, 100, 0, 0.3)');
    } else if (modeHint === 'listening') {
        coreGrad.addColorStop(0, 'rgba(0, 255, 100, 0.8)');
        coreGrad.addColorStop(0.4, 'rgba(0, 255, 100, 0.3)');
    } else if (modeHint === 'speaking') {
        coreGrad.addColorStop(0, 'rgba(0, 242, 254, 0.8)');
        coreGrad.addColorStop(0.4, 'rgba(0, 242, 254, 0.3)');
    } else {
        coreGrad.addColorStop(0, `rgba(${Math.round(currentR)}, ${Math.round(currentG)}, ${Math.round(currentB)}, 0.7)`);
        coreGrad.addColorStop(0.4, `rgba(${Math.round(currentR)}, ${Math.round(currentG)}, ${Math.round(currentB)}, 0.2)`);
    }
    coreGrad.addColorStop(1, 'transparent');
    ctx.fillStyle = coreGrad;
    ctx.beginPath();
    ctx.arc(renderCX, renderCY, coreSize, 0, 2 * Math.PI);
    ctx.fill();
    ctx.globalCompositeOperation = 'source-over';
}

// ─── Mouse/Touch Drag Handlers ───
if (canvas) {
    canvas.addEventListener('mousedown', (e) => {
        isMouseDown = true;
        isDragging = false;
        dragStartX = e.clientX;
        dragStartY = e.clientY;
        startAngleX = angleX;
        startAngleY = angleY;
    });

    window.addEventListener('mousemove', (e) => {
        if (!isMouseDown) return;
        const dx = e.clientX - dragStartX;
        const dy = e.clientY - dragStartY;
        if (Math.sqrt(dx*dx + dy*dy) > 5) isDragging = true;
        if (isDragging) {
            angleY = startAngleY - dx * 0.007;
            angleX = startAngleX - dy * 0.007;
        }
    });

    window.addEventListener('mouseup', () => {
        if (isMouseDown) {
            isMouseDown = false;
            if (!isDragging) {
                if (window.pywebview && window.pywebview.api) {
                    window.pywebview.api.toggle_mic();
                }
            }
        }
    });

    canvas.addEventListener('contextmenu', (e) => {
        e.preventDefault();
    });

    // Touch support
    canvas.addEventListener('touchstart', (e) => {
        if (e.touches.length !== 1) return;
        isMouseDown = true;
        isDragging = false;
        dragStartX = e.touches[0].clientX;
        dragStartY = e.touches[0].clientY;
        startAngleX = angleX;
        startAngleY = angleY;
    });

    window.addEventListener('touchmove', (e) => {
        if (!isMouseDown || e.touches.length !== 1) return;
        const dx = e.touches[0].clientX - dragStartX;
        const dy = e.touches[0].clientY - dragStartY;
        if (Math.sqrt(dx*dx + dy*dy) > 5) isDragging = true;
        if (isDragging) {
            angleY = startAngleY - dx * 0.007;
            angleX = startAngleX - dy * 0.007;
        }
    });

    window.addEventListener('touchend', () => {
        if (isMouseDown) {
            isMouseDown = false;
            if (!isDragging) {
                if (window.pywebview && window.pywebview.api) {
                    window.pywebview.api.toggle_mic();
                }
            }
        }
    });
}

// ─── Real-Time Web Audio Analyzer Setup ───
let sphereMicStream = null;
let sphereAudioCtx = null;
let sphereAnalyser = null;
let sphereMicSource = null;
let sphereFreqData = null;

async function setupSphereMicVisualizer() {
    try {
        if (!sphereAudioCtx) {
            sphereAudioCtx = new (window.AudioContext || window.webkitAudioContext)();
            sphereAnalyser = sphereAudioCtx.createAnalyser();
            sphereAnalyser.fftSize = 64;
            sphereAnalyser.smoothingTimeConstant = 0.75;
            sphereFreqData = new Uint8Array(sphereAnalyser.frequencyBinCount);
        }
        if (sphereAudioCtx.state === 'suspended') {
            await sphereAudioCtx.resume();
        }
        if (!sphereMicStream && navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
            sphereMicStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        }
        if (sphereMicStream && !sphereMicSource) {
            sphereMicSource = sphereAudioCtx.createMediaStreamSource(sphereMicStream);
            sphereMicSource.connect(sphereAnalyser);
        }
    } catch (e) {
        console.log("Sphere mic visualizer setup error/info:", e);
    }
}

// ─── Audio Spectrum Visualizer ───
function initAudioSpectrum() {
    const specCanvas = document.getElementById('spectrumCanvas');
    if (!specCanvas) return;

    const specCtx = specCanvas.getContext('2d');
    let specWidth = specCanvas.width = specCanvas.offsetWidth || 300;
    let specHeight = specCanvas.height = specCanvas.offsetHeight || 40;

    const resizeObserver = new ResizeObserver(entries => {
        for (let entry of entries) {
            specWidth = specCanvas.width = entry.contentRect.width || specCanvas.offsetWidth || 300;
            specHeight = specCanvas.height = entry.contentRect.height || specCanvas.offsetHeight || 40;
        }
    });
    resizeObserver.observe(specCanvas);

    window.addEventListener('click', setupSphereMicVisualizer, { once: true });
    setupSphereMicVisualizer();

    let lastSpecFrameTime = 0;
    const specActiveFps = 1000 / 30;
    const specIdleFps = 1000 / 12;
    // Cached gradients: recreated only when the canvas height changes.
    let specGradients = {};
    let gradCacheHeight = 0;

    function getSpecGradient(key, colorTop, colorBottom) {
        if (gradCacheHeight !== specHeight || !specGradients[key]) {
            gradCacheHeight = specHeight;
            specGradients = {};
            const g = specCtx.createLinearGradient(0, 0, 0, specHeight);
            g.addColorStop(0, colorTop);
            g.addColorStop(1, colorBottom);
            specGradients[key] = g;
        }
        return specGradients[key];
    }

    function drawSpectrum(timestamp) {
        const panelVisible = window.isPanelVisibleInWindow
            && (window.isPanelVisibleInWindow('commandEchoPanel') || window.isPanelVisibleInWindow('activeListeningPanel'));

        // Avoid burning rAF cycles when the panel is not visible in this window
        if (!panelVisible || (typeof isWindowVisible !== 'undefined' && !isWindowVisible)) {
            if (specCtx) specCtx.clearRect(0, 0, specWidth, specHeight);
            setTimeout(() => requestAnimationFrame(drawSpectrum), 250);
            return;
        }

        requestAnimationFrame(drawSpectrum);

        const spectrumActive = sphereIsListening || sphereIsSpeaking || sphereIsRecognizing;
        const specFpsInterval = spectrumActive ? specActiveFps : specIdleFps;

        if (!timestamp) return;
        const elapsed = timestamp - lastSpecFrameTime;
        if (elapsed < specFpsInterval) return;
        lastSpecFrameTime = timestamp - (elapsed % specFpsInterval);

        if (!specCtx) return;

        specCtx.fillStyle = 'rgba(2, 2, 8, 0.22)';
        specCtx.fillRect(0, 0, specWidth, specHeight);

        const barWidth = 4;
        const gap = 2;
        const totalBars = Math.floor(specWidth / (barWidth + gap));
        const time = Date.now() * 0.005;
        const valAudioStatus = document.getElementById('valAudioStatus');

        let amplitude = 2;
        let speedMultiplier = 1;

        if (sphereIsListening && sphereIsRecognizing) {
            amplitude = 18;
            speedMultiplier = 2.5;
            if (valAudioStatus) valAudioStatus.textContent = "REALTIME MIC ACTIVE";
        } else if (sphereIsSpeaking) {
            amplitude = 14;
            speedMultiplier = 1.8;
            if (valAudioStatus) valAudioStatus.textContent = "AI VOICE OUTPUT";
        } else {
            amplitude = 1.5;
            speedMultiplier = 0.4;
            if (valAudioStatus) {
                if (sphereIsListening) valAudioStatus.textContent = "REALTIME MIC STANDBY";
                else valAudioStatus.textContent = "STANDBY";
            }
        }

        let activeAnalyser = sphereAnalyser || window.audioAnalyserNode;
        let activeFreqData = sphereFreqData || window.audioFrequencyData;

        if (sphereIsSpeaking && window.audioAnalyserNode && window.audioFrequencyData) {
            activeAnalyser = window.audioAnalyserNode;
            activeFreqData = window.audioFrequencyData;
        }

        let hasLiveAudioSignal = false;
        if (activeAnalyser && activeFreqData) {
            activeAnalyser.getByteFrequencyData(activeFreqData);
            for (let k = 0; k < activeFreqData.length; k++) {
                if (activeFreqData[k] > 6) {
                    hasLiveAudioSignal = true;
                    break;
                }
            }
        }

        // One shared gradient per color state (created once), not per bar
        if (sphereIsListening && sphereIsRecognizing) {
            specCtx.fillStyle = getSpecGradient('green', '#00ff87', 'rgba(0, 255, 135, 0.05)');
        } else if (sphereIsSpeaking) {
            specCtx.fillStyle = getSpecGradient('cyan', '#00f2fe', 'rgba(0, 242, 254, 0.05)');
        } else {
            specCtx.fillStyle = getSpecGradient('blue', '#0066cc', 'rgba(0, 102, 204, 0.05)');
        }

        for (let i = 0; i < totalBars; i++) {
            let h = 0;
            if (hasLiveAudioSignal && activeFreqData) {
                const bin = Math.floor((i / totalBars) * activeFreqData.length);
                const rawVal = activeFreqData[bin] || 0;
                h = Math.max(2, (rawVal / 255) * specHeight * 1.25);
            } else if (sphereIsListening && sphereIsRecognizing) {
                const noise = Math.sin(i * 0.15 + time * speedMultiplier) * Math.cos(i * 0.08 - time * 0.5);
                const randomFuzz = Math.random() * 0.4 + 0.6;
                h = Math.max(2, Math.abs(noise) * amplitude * randomFuzz);
            } else {
                h = Math.max(1, (Math.sin(i * 0.1 + time * speedMultiplier) + 1) * amplitude);
            }

            const x = i * (barWidth + gap);
            const y = specHeight - h;
            specCtx.fillRect(x, y, barWidth, h);
        }
    }
    requestAnimationFrame(drawSpectrum);
}

// ─── State Sync Loop ───
setInterval(async () => {
    const panelsVisible = window.isPanelVisibleInWindow
        && (window.isPanelVisibleInWindow('activeListeningPanel') || window.isPanelVisibleInWindow('commandEchoPanel'));
    if (!panelsVisible) {
        return;
    }

    const params = new URLSearchParams(window.location.search);
    const activePanel = params.get('panel');

    if (activePanel === 'sphere' && window.pywebview && window.pywebview.api && window.pywebview.api.get_sphere_state) {
        try {
            const stateJson = await window.pywebview.api.get_sphere_state();
            const state = JSON.parse(stateJson);
            sphereIsListening = state.listening;
            sphereIsSpeaking = state.speaking;
            sphereIsRecognizing = state.recognizing;
            sphereIsProcessing = state.processing;
        } catch (e) {
            // silent
        }
    } else if (activePanel === 'bottom' && window.pywebview && window.pywebview.api && window.pywebview.api.get_sphere_state) {
        try {
            const stateJson = await window.pywebview.api.get_sphere_state();
            const state = JSON.parse(stateJson);
            sphereIsListening = state.listening;
            sphereIsSpeaking = state.speaking;
            sphereIsRecognizing = state.recognizing;
            sphereIsProcessing = state.processing;
        } catch (e) {
            // silent
        }
    } else if (typeof isListening !== 'undefined') {
        sphereIsListening = isListening;
        sphereIsSpeaking = isSpeaking;
        sphereIsRecognizing = userIsSpeaking;

        const statusInd = document.getElementById('statusIndicator');
        sphereIsProcessing = statusInd && (statusInd.textContent.includes('PROCESSING') || statusInd.textContent.includes('THINKING') || statusInd.textContent.includes('COGNITION') || statusInd.textContent.includes('RUNNING'));
    }

    if (statusLabel) {
        if (sphereIsListening) {
            if (sphereIsRecognizing) statusLabel.textContent = "Listening... Speak now";
            else statusLabel.textContent = "Listening... (Silent)";
        }
        else if (sphereIsProcessing) statusLabel.textContent = "Processing...";
        else if (sphereIsSpeaking) statusLabel.textContent = "Speaking...";
        else statusLabel.textContent = "Click Blob to Speak";
    }

    if (canvas) {
        if (sphereIsSpeaking) canvas.className = 'waves-canvas speaking';
        else if (sphereIsListening && sphereIsRecognizing) canvas.className = 'waves-canvas recognizing';
        else if (sphereIsProcessing) canvas.className = 'waves-canvas processing';
        else canvas.className = 'waves-canvas';
    }

    // Suspend the WebAudio graph when idle to save CPU (resume when active)
    if (sphereAudioCtx) {
        const audioActive = sphereIsListening || sphereIsSpeaking || sphereIsRecognizing || sphereIsProcessing;
        if (audioActive && sphereAudioCtx.state === 'suspended') {
            try { sphereAudioCtx.resume(); } catch (e) {}
        } else if (!audioActive && sphereAudioCtx.state === 'running') {
            try { sphereAudioCtx.suspend(); } catch (e) {}
        }
    }
}, 400);

// ─── Init ───
resizeCanvas();
requestAnimationFrame(drawVisualizer);

window.addEventListener('resize', resizeCanvas);
window.addEventListener('DOMContentLoaded', initAudioSpectrum);

})();
