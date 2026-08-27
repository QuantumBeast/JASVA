/**
 * device.js — JASVA Unified Multi-Hub Dock Controller
 * Powers:
 * - Segmented Tab Switching (System, TV Remote, Phone, Media Player, Agenda Timeline)
 * - TV Direct ADB Buttons, Quick Apps, and 60FPS Screen Mirror
 * - Phone Direct ADB Keys, Screen Mirror, and AI Screen Task Runner
 * - Live Media Status, Now Playing Art, Master Volume, and Synced Lyrics
 * - Interactive Agenda Timeline, Event Scheduling, and .ICS Export
 */

(() => {

// ─── Utility: Flash button on click ───
function flashBtn(el) {
    if (!el) return;
    el.classList.add('btn-flash-ok');
    setTimeout(() => el.classList.remove('btn-flash-ok'), 300);
}

// ─── Segmented Dock Tab Switcher ───
window.switchDockTab = function(tabName) {
    const tabs = ['system', 'tv', 'phone', 'media', 'agenda'];
    tabs.forEach(t => {
        const btn = document.getElementById(`tabBtn${t.charAt(0).toUpperCase() + t.slice(1)}`);
        const content = document.getElementById(`dockTab${t.charAt(0).toUpperCase() + t.slice(1)}`);
        if (btn) btn.classList.toggle('active', t === tabName);
        if (content) {
            if (t === tabName) {
                content.style.display = 'flex';
                content.classList.add('active');
            } else {
                content.style.display = 'none';
                content.classList.remove('active');
            }
        }
    });

    // Refresh data when specific tabs open
    if (tabName === 'media') {
        pollMediaStatus();
    } else if (tabName === 'agenda') {
        loadAgendaEvents();
    } else if (tabName === 'tv' || tabName === 'phone') {
        pollDeviceStatuses();
    }
};

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
    if (window.pywebview && window.pywebview.api) {
        try {
            return await window.pywebview.api.execute_command(cmd, true);
        } catch(e) { console.error('Device cmd error:', e); }
    } else if (typeof window.sendCmdDirect === 'function') {
        window.sendCmdDirect(cmd, true);
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

    if (btn) btn.classList.add('connecting');
    setTvStatus(false, 'LINKING...');

    await sendDeviceCmd(`connect tv ${ip}`);
    setTimeout(pollDeviceStatuses, 2500);
    if (btn) btn.classList.remove('connecting');
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

    if (btn) btn.classList.add('connecting');
    setPhoneStatus(false, 'LINKING...');

    await sendDeviceCmd(`phone connect ${ip}`);
    setTimeout(pollDeviceStatuses, 2500);
    if (btn) btn.classList.remove('connecting');
};

// ─── Fast Direct TV Remote Button Handler ───
window.tvBtn = async function(key) {
    const idMap = {
        'up': 'tvBtnUp', 'down': 'tvBtnDown', 'left': 'tvBtnLeft', 'right': 'tvBtnRight',
        'select': 'tvBtnSelect', 'home': 'tvBtnHome', 'back': 'tvBtnBack',
        'power': 'tvBtnPower', 'mute': 'tvBtnMute',
        'volume_up': 'tvBtnVolUp', 'volume_down': 'tvBtnVolDown', 'menu': 'tvBtnMenu'
    };
    if (idMap[key]) flashBtn(document.getElementById(idMap[key]));

    if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.quick_button === 'function') {
        try {
            await window.pywebview.api.quick_button('tv', key);
            return;
        } catch (e) { /* fallback */ }
    }
    sendDeviceCmd(`tv ${key}`);
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

// ─── Fast Direct Phone Key Handler ───
window.phoneKey = async function(keycode) {
    if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.quick_button === 'function') {
        try {
            await window.pywebview.api.quick_button('phone', keycode);
            return;
        } catch(e) { /* fallback */ }
    }
    sendDeviceCmd(`phone keyevent ${keycode}`);
};

// ─── Phone Mirror Handler ───
window.mirrorPhone = function() {
    const btn = document.getElementById('phoneMirrorBtn');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><rect x="5" y="2" width="14" height="20" rx="2"/><line x1="12" y1="18" x2="12.01" y2="18"/></svg><span>LAUNCHING...</span>';
    }

    sendDeviceCmd('phone mirror');
    showFloatingControls('phone');

    setTimeout(() => {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><rect x="5" y="2" width="14" height="20" rx="2"/><line x1="12" y1="18" x2="12.01" y2="18"/></svg><span>MIRROR</span>';
        }
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

    if (btn) btn.classList.add('connecting');
    await sendDeviceCmd(`phone do ${task}`);
    if (btn) btn.classList.remove('connecting');
    if (input) input.value = '';
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

// ─── Floating Control Panel Bridge ───
window._activeMirrorDevice = null;
function showFloatingControls(deviceType) {
    window._activeMirrorDevice = deviceType;
    if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.show_ctrl_window === 'function') {
        window.pywebview.api.show_ctrl_window(deviceType);
    }
}
window.hideFloatingControls = function() {
    if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.hide_ctrl_window === 'function') {
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
window.setTvStatus = setTvStatus;
window.setPhoneStatus = setPhoneStatus;

// ══════════════════════════════════════════════════════════════
// MEDIA PLAYER & SYNCHRONIZED LYRICS MANAGER
// ══════════════════════════════════════════════════════════════
let currentTrackTitle = '';
let currentTrackArtist = '';
let currentLyricsList = [];

window.mediaControl = async function(action) {
    if (!window.pywebview || !window.pywebview.api) return;
    try {
        await window.pywebview.api.control_media(action);
        setTimeout(pollMediaStatus, 300);
    } catch (e) {
        console.error('Media control error:', e);
    }
};

window.setMediaVolume = async function(val) {
    const label = document.getElementById('mediaVolumeVal');
    if (label) label.textContent = val + '%';
    if (!window.pywebview || !window.pywebview.api) return;
    try {
        await window.pywebview.api.set_system_volume(val);
    } catch(e) {
        console.error('Volume set error:', e);
    }
};

window.launchMediaApp = async function(app) {
    if (!window.pywebview || !window.pywebview.api) return;
    try {
        await window.pywebview.api.launch_media_app(app);
    } catch (e) {
        console.error('Launch media app error:', e);
    }
};

async function pollMediaStatus() {
    if (!window.pywebview || !window.pywebview.api || typeof window.pywebview.api.get_media_status !== 'function') return;
    try {
        const statusJson = await window.pywebview.api.get_media_status();
        if (!statusJson) return;
        const data = typeof statusJson === 'string' ? JSON.parse(statusJson) : statusJson;

        const titleEl = document.getElementById('mediaTrackTitle');
        const artistEl = document.getElementById('mediaTrackArtist');
        const sourceEl = document.getElementById('mediaSourceBadge');
        const playIcon = document.getElementById('mediaPlayIcon');
        const artImg = document.getElementById('mediaArtImg');
        const discPlaceholder = document.getElementById('mediaDiscPlaceholder');

        const title = data.title || 'NO MEDIA PLAYING';
        const artist = data.artist || 'STANDBY';
        const isPlaying = !!data.is_playing;
        const source = data.app_name || 'WINDOWS AUDIO';

        if (titleEl) titleEl.textContent = title;
        if (artistEl) artistEl.textContent = artist;
        if (sourceEl) sourceEl.textContent = source.toUpperCase();

        if (playIcon) {
            if (isPlaying) {
                playIcon.innerHTML = '<rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/>';
            } else {
                playIcon.innerHTML = '<polygon points="5 3 19 12 5 21 5 3"/>';
            }
        }

        if (data.album_art) {
            if (artImg) {
                artImg.src = data.album_art;
                artImg.style.display = 'block';
            }
            if (discPlaceholder) discPlaceholder.style.display = 'none';
        } else {
            if (artImg) artImg.style.display = 'none';
            if (discPlaceholder) discPlaceholder.style.display = 'block';
        }

        // Sync Windows volume if slider is not actively being dragged
        try {
            if (typeof window.pywebview.api.get_system_volume === 'function') {
                const volJson = await window.pywebview.api.get_system_volume();
                const volData = typeof volJson === 'string' ? JSON.parse(volJson) : volJson;
                if (volData && volData.volume !== undefined) {
                    const slider = document.getElementById('mediaVolumeSlider');
                    const label = document.getElementById('mediaVolumeVal');
                    if (slider && !slider.matches(':active')) {
                        slider.value = volData.volume;
                        if (label) label.textContent = volData.volume + '%';
                    }
                }
            }
        } catch(e) {}

        // Check if track changed to fetch lyrics
        if (title !== currentTrackTitle || artist !== currentTrackArtist) {
            currentTrackTitle = title;
            currentTrackArtist = artist;
            if (title !== 'NO MEDIA PLAYING' && title.trim() !== '') {
                fetchLyrics(title, artist);
            }
        }
    } catch(e) { /* silent */ }
}

async function fetchLyrics(title, artist) {
    const container = document.getElementById('mediaLyricsContainer');
    if (!container) return;
    container.innerHTML = '<div class="lyric-line placeholder">Loading synchronized lyrics...</div>';

    if (!window.pywebview || !window.pywebview.api || typeof window.pywebview.api.get_media_lyrics !== 'function') {
        container.innerHTML = '<div class="lyric-line placeholder">Lyrics service ready.</div>';
        return;
    }

    try {
        const resJson = await window.pywebview.api.get_media_lyrics(title, artist);
        const res = typeof resJson === 'string' ? JSON.parse(resJson) : resJson;
        if (res && res.lyrics && res.lyrics.length > 0) {
            currentLyricsList = res.lyrics;
            container.innerHTML = '';
            res.lyrics.forEach((line, idx) => {
                const div = document.createElement('div');
                div.className = 'lyric-line' + (idx === 0 ? ' active' : '');
                div.textContent = typeof line === 'string' ? line : (line.text || line.line || '');
                container.appendChild(div);
            });
        } else {
            container.innerHTML = '<div class="lyric-line placeholder">No lyrics found for this track.</div>';
        }
    } catch(e) {
        container.innerHTML = '<div class="lyric-line placeholder">Lyrics unavailable.</div>';
    }
}

// ══════════════════════════════════════════════════════════════
// AGENDA & CALENDAR TIMELINE MANAGER
// ══════════════════════════════════════════════════════════════
async function loadAgendaEvents() {
    const listEl = document.getElementById('agendaEventsList');
    if (!listEl) return;

    if (!window.pywebview || !window.pywebview.api || typeof window.pywebview.api.get_calendar_agenda !== 'function') {
        listEl.innerHTML = '<div class="agenda-empty-state">Calendar ready. No scheduled events.</div>';
        return;
    }

    try {
        const eventsJson = await window.pywebview.api.get_calendar_agenda();
        const events = typeof eventsJson === 'string' ? JSON.parse(eventsJson) : eventsJson;

        if (!events || events.length === 0) {
            listEl.innerHTML = '<div class="agenda-empty-state">No upcoming agenda events. Add one below!</div>';
            return;
        }

        listEl.innerHTML = '';
        events.forEach(ev => {
            const card = document.createElement('div');
            card.className = 'agenda-event-card' + (ev.completed ? ' completed' : '');
            
            const catClass = ev.category === 'PERSONAL' ? 'agenda-cat-personal' : (ev.category === 'URGENT' ? 'agenda-cat-urgent' : 'agenda-cat-work');
            
            card.innerHTML = `
                <div class="agenda-event-left">
                    <input type="checkbox" class="agenda-checkbox" ${ev.completed ? 'checked' : ''} onchange="window.toggleCalendarEvent('${ev.id}')" />
                    <div class="agenda-event-info">
                        <span class="agenda-event-title-text">${ev.title || 'Untitled'}</span>
                        <span class="agenda-event-time-text">${ev.date || ''} • ${ev.time || ''}</span>
                    </div>
                </div>
                <span class="agenda-event-cat-badge ${catClass}">${ev.category || 'WORK'}</span>
                <button class="agenda-delete-btn" onclick="window.deleteCalendarEvent('${ev.id}')" title="Delete">&times;</button>
            `;
            listEl.appendChild(card);
        });
    } catch(e) {
        listEl.innerHTML = '<div class="agenda-empty-state">Unable to load agenda.</div>';
    }
}

window.addCalendarEvent = async function() {
    const titleInput = document.getElementById('agendaEventTitle');
    const dateInput = document.getElementById('agendaEventDate');
    const timeInput = document.getElementById('agendaEventTime');
    const catInput = document.getElementById('agendaEventCategory');

    const title = titleInput ? titleInput.value.trim() : '';
    const date = dateInput ? dateInput.value : '';
    const time = timeInput ? timeInput.value : '09:00';
    const category = catInput ? catInput.value : 'WORK';

    if (!title) {
        if (titleInput) { titleInput.classList.add('input-error'); setTimeout(() => titleInput.classList.remove('input-error'), 1200); }
        return;
    }

    const todayStr = new Date().toISOString().split('T')[0];
    const eventObj = {
        title: title,
        date: date || todayStr,
        time: time || '09:00',
        category: category,
        duration_mins: 60,
        set_reminder: true
    };

    if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.save_calendar_event === 'function') {
        try {
            await window.pywebview.api.save_calendar_event(JSON.stringify(eventObj));
            if (titleInput) titleInput.value = '';
            loadAgendaEvents();
        } catch(e) {
            console.error('Save event error:', e);
        }
    }
};

window.toggleCalendarEvent = async function(id) {
    if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.toggle_calendar_event === 'function') {
        try {
            await window.pywebview.api.toggle_calendar_event(id);
            loadAgendaEvents();
        } catch(e) {}
    }
};

window.deleteCalendarEvent = async function(id) {
    if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.delete_calendar_event === 'function') {
        try {
            await window.pywebview.api.delete_calendar_event(id);
            loadAgendaEvents();
        } catch(e) {}
    }
};

window.exportCalendar = async function() {
    if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.export_calendar_ics === 'function') {
        try {
            const res = await window.pywebview.api.export_calendar_ics();
            const data = typeof res === 'string' ? JSON.parse(res) : res;
            if (typeof window.showToastNotification === 'function') {
                window.showToastNotification('Calendar exported to ICS', 'success');
            }
        } catch(e) {}
    }
};

// ─── Set default date in Agenda Input on Load ───
document.addEventListener('DOMContentLoaded', () => {
    const dateInput = document.getElementById('agendaEventDate');
    if (dateInput) {
        dateInput.value = new Date().toISOString().split('T')[0];
    }
    setInterval(pollDeviceStatuses, 12000);
    setTimeout(pollDeviceStatuses, 2000);
    setInterval(pollMediaStatus, 5000);
    setTimeout(pollMediaStatus, 2500);
    setTimeout(loadAgendaEvents, 3000);
});

})();
