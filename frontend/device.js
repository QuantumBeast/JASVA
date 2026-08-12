/**
 * device.js — PC Device Control Hub
 * Handles TV remote and Phone ADB controls from the right panel.
 * All actions relay commands through JASVA's command router.
 */

(() => {

// ─── Utility: Flash button on click ───
function flashBtn(el) {
    if (!el) return;
    el.classList.add('btn-flash-ok');
    setTimeout(() => el.classList.remove('btn-flash-ok'), 350);
}

// ─── Device Status Helpers ───
function setTvStatus(connected, label) {
    const dot = document.getElementById('tvStatusDot');
    const text = document.getElementById('tvStatusText');
    const portalText = document.getElementById('portalTvStatus');
    const pill = document.getElementById('portalTvPill');

    if (dot) dot.className = 'device-status-dot ' + (connected ? 'connected' : '');
    if (text) text.textContent = label || (connected ? 'CONNECTED' : 'DISCONNECTED');
    if (portalText) portalText.textContent = 'TV: ' + (connected ? 'ONLINE' : 'OFFLINE');
    if (pill) {
        pill.classList.toggle('device-pill-online', !!connected);
        pill.classList.toggle('device-pill-offline', !connected);
    }
}

function setPhoneStatus(connected, label) {
    const dot = document.getElementById('phoneStatusDot');
    const text = document.getElementById('phoneStatusText');
    const portalText = document.getElementById('portalPhoneStatus');
    const pill = document.getElementById('portalPhonePill');

    if (dot) dot.className = 'device-status-dot ' + (connected ? 'connected' : '');
    if (text) text.textContent = label || (connected ? 'CONNECTED' : 'DISCONNECTED');
    if (portalText) portalText.textContent = 'PHONE: ' + (connected ? 'ONLINE' : 'OFFLINE');
    if (pill) {
        pill.classList.toggle('device-pill-online', !!connected);
        pill.classList.toggle('device-pill-offline', !connected);
    }
}

// ─── Send Device Command ───
async function sendDeviceCmd(cmd) {
    if (typeof window.sendCmdDirect === 'function') {
        window.sendCmdDirect(cmd, true);
    } else if (window.pywebview && window.pywebview.api) {
        try {
            return await window.pywebview.api.execute_command(cmd, true);
        } catch(e) { console.error('Device cmd error:', e); }
    }
}

// ─── Connect TV ───
window.connectTv = async function() {
    const input = document.getElementById('tvIpPcInput');
    const btn = document.getElementById('tvConnectBtn');
    const ip = input ? input.value.trim() : '';

    if (!ip) {
        if (input) { input.classList.add('input-error'); setTimeout(() => input.classList.remove('input-error'), 1200); }
        return;
    }

    if (btn) { btn.classList.add('connecting'); }
    setTvStatus(false, 'LINKING...');

    await sendDeviceCmd(`connect tv ${ip}`);

    setTimeout(pollDeviceStatuses, 2500);
    if (btn) { btn.classList.remove('connecting'); }
};

// ─── Connect Phone ───
window.connectPhone = async function() {
    const input = document.getElementById('phoneIpPcInput');
    const btn = document.getElementById('phoneConnectBtn');
    const ip = input ? input.value.trim() : '';

    if (!ip) {
        if (input) { input.classList.add('input-error'); setTimeout(() => input.classList.remove('input-error'), 1200); }
        return;
    }

    if (btn) { btn.classList.add('connecting'); }
    setPhoneStatus(false, 'LINKING...');

    await sendDeviceCmd(`phone connect ${ip}`);

    setTimeout(pollDeviceStatuses, 2500);
    if (btn) { btn.classList.remove('connecting'); }
};

// ─── TV Remote Button Handler ───
window.tvBtn = function(key) {
    sendDeviceCmd(`tv ${key}`);
    // Flash the correct button
    const idMap = {
        'up': 'tvBtnUp', 'down': 'tvBtnDown', 'left': 'tvBtnLeft', 'right': 'tvBtnRight',
        'select': 'tvBtnSelect', 'home': 'tvBtnHome', 'back': 'tvBtnBack',
        'power': 'tvBtnPower', 'mute': 'tvBtnMute',
        'volume_up': 'tvBtnVolUp', 'volume_down': 'tvBtnVolDown'
    };
    if (idMap[key]) flashBtn(document.getElementById(idMap[key]));
};

// ─── TV App Quick-Launch ───
window.tvApp = function(appName) {
    sendDeviceCmd(`tv open ${appName}`);
    const appBtnMap = {
        'youtube': 'tvAppYt', 'netflix': 'tvAppNetflix',
        'prime video': 'tvAppPrime', 'spotify': 'tvAppSpotify'
    };
    const btnId = appBtnMap[appName];
    if (btnId) flashBtn(document.getElementById(btnId));
};

// ─── TV Mirror Screen ───
window.tvMirror = function() {
    sendDeviceCmd('tv mirror');
    flashBtn(document.getElementById('tvMirrorBtn'));
    showFloatingControls('tv');
};

// ─── Phone Key Handler ───
window.phoneKey = function(keycode) {
    sendDeviceCmd(`phone keyevent ${keycode}`);
};

// ─── Phone Mirror Handler ───
window.mirrorPhone = function() {
    const btn = document.getElementById('phoneMirrorBtn');
    
    if (btn) { btn.disabled = true; btn.innerHTML = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><rect x="5" y="2" width="14" height="20" rx="2"/><line x1="12" y1="18" x2="12.01" y2="18"/></svg><span>LAUNCHING...</span>'; }
    
    // Always auto-detect the linked phone from adb devices.
    sendDeviceCmd('phone mirror');
    showFloatingControls('phone');
    
    setTimeout(() => {
        if (btn) { btn.disabled = false; btn.innerHTML = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><rect x="5" y="2" width="14" height="20" rx="2"/><line x1="12" y1="18" x2="12.01" y2="18"/></svg><span>PHONE</span>'; }
    }, 3000);
};

// ─── Phone Task Handler (JASVA sees & operates the phone) ───
window.phoneDoTask = async function() {
    const input = document.getElementById('phoneTaskInput');
    const btn = document.getElementById('phoneTaskBtn');
    const task = input ? input.value.trim() : '';

    if (!task) {
        if (input) { input.classList.add('input-error'); setTimeout(() => input.classList.remove('input-error'), 1200); }
        return;
    }

    if (btn) { btn.classList.add('connecting'); }
    await sendDeviceCmd(`phone do ${task}`);
    if (btn) { btn.classList.remove('connecting'); }
    if (input) { input.value = ''; }
};

(function bindPhoneTaskEnter() {
    const input = document.getElementById('phoneTaskInput');
    if (!input) return;
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') window.phoneDoTask();
    });
})();

// ─── Poll Device Connection Status ───
let lastAutoFilledAddr = '';
let lastAutoFilledTvAddr = '';
async function pollDeviceStatuses() {
    if (!window.pywebview || !window.pywebview.api) return;
    // Only poll from the window that actually shows the device control panel.
    // Every window otherwise runs this loop and spawns duplicate `adb` commands.
    const params = new URLSearchParams(window.location.search);
    const activePanel = params.get('panel');
    if (activePanel && activePanel !== 'control') return;
    if (!activePanel && window.isPanelVisibleInWindow && !window.isPanelVisibleInWindow('systemPanel')) return;
    try {
        const resultJson = await window.pywebview.api.execute_command('device status', true);
        if (!resultJson) return;
        const res = JSON.parse(resultJson);
        if (!res || !res.output) return;
        const output = res.output.toLowerCase();

        const tvOnline  = /\btv:\s*connected/.test(output) || (output.includes('tv') && /\bonline/.test(output));
        const tvOffline = /\btv:\s*disconnected/.test(output) || (output.includes('tv') && /\boffline/.test(output));
        if (tvOnline)  setTvStatus(true);
        if (tvOffline) setTvStatus(false);

        const phoneOnline  = /\bphone:\s*connected/.test(output) || (output.includes('phone') && /\bonline/.test(output));
        const phoneOffline = /\bphone:\s*disconnected/.test(output) || (output.includes('phone') && /\boffline/.test(output));
        if (phoneOnline)  setPhoneStatus(true);
        if (phoneOffline) setPhoneStatus(false);

        // Auto-fill the TV IP so the address stays visible after linking.
        // Never clobber manual typing: only fill when empty or still holding the
        // previously auto-filled address.
        const tvIpMatch = output.match(/tv:\s*(?:connected|disconnected)\s*\((\d{1,3}(?:\.\d{1,3}){3})\)/);
        if (tvIpMatch) {
            const tvInput = document.getElementById('tvIpPcInput');
            if (tvInput) {
                const curTv = tvInput.value.trim();
                if (curTv === '' || curTv === lastAutoFilledTvAddr) {
                    tvInput.value = tvIpMatch[1];
                    lastAutoFilledTvAddr = tvIpMatch[1];
                }
            }
        }

        // Auto-fill the mirror address with the currently linked phone so it
        // never asks for an IP when a phone is already connected. Never
        // clobber manual typing: only fill when empty or when it still holds
        // the previously auto-filled address (e.g. Wireless Debugging changed the port).
        if (phoneOnline) {
            const addrMatch = output.match(/\b\d{1,3}(?:\.\d{1,3}){3}:\d+\b/);
            if (addrMatch) {
                const input = document.getElementById('phoneIpPcInput');
                if (input) {
                    const cur = input.value.trim();
                    if (cur === '' || cur === lastAutoFilledAddr) {
                        input.value = addrMatch[0];
                        lastAutoFilledAddr = addrMatch[0];
                    }
                }
            }
        }
    } catch (e) { /* silent */ }
}

// ─── Init ───
document.addEventListener('DOMContentLoaded', () => {
    setInterval(pollDeviceStatuses, 12000);
    setTimeout(pollDeviceStatuses, 3000);
});

window.setTvStatus = setTvStatus;
window.setPhoneStatus = setPhoneStatus;

// ─── Floating Control Panel ───
window._activeMirrorDevice = null;

function showFloatingControls(deviceType) {
    window._activeMirrorDevice = deviceType;
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.show_ctrl_window(deviceType);
    }
}
window.hideFloatingControls = function() {
    if (window.pywebview && window.pywebview.api) {
        if (window._activeMirrorDevice) {
            window.pywebview.api.hide_ctrl_window(window._activeMirrorDevice);
        }
    }
};
window.openControls = function() {
    if (window._activeMirrorDevice && window.pywebview && window.pywebview.api) {
        window.pywebview.api.show_ctrl_window(window._activeMirrorDevice);
    }
};
window.showFloatingControls = showFloatingControls;

})();
