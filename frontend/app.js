const API_BASE = "";

// ==========================================
// State
// ==========================================
let currentView = 'libraries';
let currentLibrary = null;
let currentArtist = null;
let currentAlbum = null;
let currentTracks = [];
let currentTrack = null;
let queueVisible = false;

const content    = document.getElementById('content');
const statusDiv  = document.getElementById('status');
const pageTitle  = document.getElementById('page-title');
const btnHome    = document.getElementById('btn-home');
const btnBack    = document.getElementById('btn-back');


// ==========================================
// 💡 BILDSCHIRMSCHONER
// ==========================================
// Wie es funktioniert:
//   – Nach SCREEN_TIMEOUT ms ohne Touch UND ohne laufende Wiedergabe:
//     Frontend ruft POST /screen/off → Backend führt xset dpms force off aus
//   – Bei erstem Touch auf den schwarzen Bildschirm:
//     Frontend ruft POST /screen/on → Bildschirm leuchtet sofort wieder
//   – Wenn Wiedergabe startet (updatePlayerState erkennt state=playing):
//     Bildschirm wird automatisch eingeschaltet und Timer resettet
// ==========================================

const SCREEN_TIMEOUT_MS = 5 * 60 * 1000;  // 5 Minuten – im Admin-Panel einstellbar (TODO)
let _screenTimer   = null;
let _screenIsOff   = false;
let _isPlaying     = false;

function _resetScreenTimer() {
    clearTimeout(_screenTimer);
    if (_screenIsOff) {
        // Beim ersten Touch Bildschirm einschalten
        _screenWakeUp();
        return;
    }
    // Nur Timer starten wenn nichts abgespielt wird
    if (!_isPlaying) {
        _screenTimer = setTimeout(_screenSleep, SCREEN_TIMEOUT_MS);
    }
}

async function _screenSleep() {
    if (_isPlaying || _screenIsOff) return;
    _screenIsOff = true;
    try {
        await fetch(`${API_BASE}/screen/off`, { method: 'POST' });
    } catch (e) {
        // Kein Fehler – auf Windows läuft das einfach ins Leere
    }
}

async function _screenWakeUp() {
    if (!_screenIsOff) return;
    _screenIsOff = false;
    try {
        await fetch(`${API_BASE}/screen/on`, { method: 'POST' });
    } catch (e) {}
    // Timer für nächstes Abschalten neu starten
    if (!_isPlaying) {
        _screenTimer = setTimeout(_screenSleep, SCREEN_TIMEOUT_MS);
    }
}

function _setupScreenWatcher() {
    // Jede Touch-/Maus-Interaktion setzt den Timer zurück
    ['touchstart', 'touchend', 'mousedown', 'mousemove', 'keydown'].forEach(evt => {
        document.addEventListener(evt, _resetScreenTimer, { passive: true });
    });
    // Initial-Timer starten
    _resetScreenTimer();
}


// ==========================================
// Init
// ==========================================
async function init() {
    setupPlayerControls();
    setupNavigation();
    setupKioskProtection();
    setupAccentSwitcher();
    setupQueueUI();
    _setupScreenWatcher();
    loadLibraries();
    setInterval(updatePlayerState, 2000);

    try {
        const vol = await fetch(`${API_BASE}/player/volume`).then(r => r.json());
        const slider = document.getElementById('volume-slider');
        const value  = document.getElementById('volume-value');
        if (slider && value) { slider.value = vol.volume; value.innerText = `${vol.volume}%`; }
    } catch (e) {}

    const savedAccent = localStorage.getItem('hmc_accent');
    if (savedAccent) document.documentElement.style.setProperty('--accent-color', savedAccent);
}

function setupAccentSwitcher() {
    const accents = ['#e5a00d', '#4facfe', '#ff6b6b', '#6bffb3', '#d45d79'];
    let idx = 0;
    const current = localStorage.getItem('hmc_accent');
    if (current) { const f = accents.indexOf(current); if (f !== -1) idx = f; }
    pageTitle.style.cursor = 'pointer';
    pageTitle.title = "Farbe wechseln";
    pageTitle.onclick = () => {
        idx = (idx + 1) % accents.length;
        const color = accents[idx];
        document.documentElement.style.setProperty('--accent-color', color);
        localStorage.setItem('hmc_accent', color);
    };
}

function setupKioskProtection() {
    document.addEventListener('contextmenu', e => e.preventDefault());
    document.addEventListener('touchstart', e => { if (e.touches.length > 1) e.preventDefault(); }, { passive: false });
}

function setupNavigation() {
    btnHome.onclick = loadLibraries;
    btnBack.onclick = goBack;
}

function goBack() {
    if (queueVisible) { closeQueue(); return; }
    switch (currentView) {
        case 'track-detail': if (currentAlbum) openAlbum(currentAlbum); break;
        case 'tracks':       if (currentArtist) loadAlbums(currentArtist); break;
        case 'albums':       if (currentLibrary) loadArtists(currentLibrary); break;
        default:             loadLibraries();
    }
}

function updateHeader(title, showNav) {
    pageTitle.innerText = title;
    btnHome.style.display = showNav ? 'flex' : 'none';
    btnBack.style.display = showNav ? 'flex' : 'none';
}


// ==========================================
// 🎵 QUEUE UI
// ==========================================

function setupQueueUI() {
    const target = document.getElementById('queue-container-target');
    if (target) target.appendChild(createQueueButton());

    const queueOverlay = document.createElement('div');
    queueOverlay.id = 'queue-overlay';
    queueOverlay.className = 'queue-overlay';
    queueOverlay.innerHTML = `
        <div class="queue-container">
            <div class="queue-header">
                <h2>Wiedergabeliste</h2>
                <button id="queue-close" class="queue-close">✕</button>
            </div>
            <div class="queue-content">
                <div class="queue-current"></div>
                <div class="queue-list"></div>
            </div>
        </div>
    `;
    document.body.appendChild(queueOverlay);
    document.getElementById('queue-close').onclick = closeQueue;
    queueOverlay.onclick = (e) => { if (e.target === queueOverlay) closeQueue(); };
}

function createQueueButton() {
    const btn = document.createElement('button');
    btn.id = 'btn-queue';
    btn.title = 'Wiedergabeliste';
    btn.innerHTML = `
        <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor">
            <path d="M15 6H3v2h12V6zm0 4H3v2h12v-2zM3 16h8v-2H3v2zM17 6v8.18c-.31-.11-.65-.18-1-.18-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3V8h3V6h-5z"/>
        </svg>
        <span class="queue-count" id="queue-count" style="display:none">0</span>
    `;
    btn.onclick = openQueue;
    return btn;
}

async function openQueue() {
    queueVisible = true;
    document.getElementById('queue-overlay').classList.add('visible');
    await updateQueue();
}

function closeQueue() {
    queueVisible = false;
    document.getElementById('queue-overlay').classList.remove('visible');
}

async function updateQueue() {
    if (!queueVisible) return;
    try {
        const data = await fetch(`${API_BASE}/queue`).then(r => r.json());
        const currentDiv = document.querySelector('.queue-current');
        const listDiv    = document.querySelector('.queue-list');

        if (data.current_track) {
            const t = data.current_track;
            currentDiv.innerHTML = `
                <div class="queue-current-card">
                    ${t.image ? `<img src="${t.image}" alt="${t.name}">` : '<div class="album-placeholder">🎵</div>'}
                    <div class="queue-current-info"><h3>${t.name}</h3><p>Spielt gerade</p></div>
                </div>`;
        } else {
            currentDiv.innerHTML = '<p>Keine Wiedergabe</p>';
        }

        if (data.upcoming_tracks && data.upcoming_tracks.length > 0) {
            listDiv.innerHTML = '<h3>Als Nächstes</h3>' + data.upcoming_tracks.map((t, idx) => {
                const ai = data.current_index + idx + 1;
                return `<div class="queue-item">
                    <span class="queue-item-num">${idx + 1}</span>
                    <span class="queue-item-name">${t.name}</span>
                    <div class="queue-item-actions">
                        <button onclick="jumpToTrack(${ai})"><svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M8 5v14l11-7z"/></svg></button>
                        <button onclick="removeFromQueue(${ai})"><svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg></button>
                    </div>
                </div>`;
            }).join('');
        } else {
            listDiv.innerHTML = '<p class="queue-empty">Keine weiteren Titel in der Warteschlange</p>';
        }
    } catch (e) { console.error('Queue load failed', e); }
}

async function jumpToTrack(index) {
    try { await fetch(`${API_BASE}/queue/jump/${index}`, { method: 'POST' }); await updateQueue(); await updatePlayerState(); } catch (e) {}
}
async function removeFromQueue(index) {
    try { await fetch(`${API_BASE}/queue/${index}`, { method: 'DELETE' }); await updateQueue(); await updatePlayerState(); } catch (e) {}
}


// ==========================================
// 🎵 TRACK CONTEXT MENU
// ==========================================

function showTrackMenu(track, albumId) {
    const overlay = document.createElement('div');
    overlay.className = 'track-menu-overlay';
    overlay.innerHTML = `
        <div class="track-menu">
            <div class="track-menu-header"><h3>${track.name}</h3></div>
            <div class="track-menu-actions">
                <button class="track-menu-btn" data-action="play-now">
                    <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
                    <span>Jetzt wiedergeben</span></button>
                <button class="track-menu-btn" data-action="play-next">
                    <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor"><path d="M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z"/></svg>
                    <span>Als Nächstes wiedergeben</span></button>
                <button class="track-menu-btn" data-action="add-to-queue">
                    <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor"><path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/></svg>
                    <span>Zur Wiedergabeliste hinzufügen</span></button>
            </div>
            <button class="track-menu-close">Abbrechen</button>
        </div>`;
    document.body.appendChild(overlay);
    overlay.querySelectorAll('.track-menu-btn').forEach(btn => {
        btn.onclick = async () => { await handleQueueAction(btn.dataset.action, track.id, albumId); document.body.removeChild(overlay); };
    });
    const close = () => document.body.removeChild(overlay);
    overlay.querySelector('.track-menu-close').onclick = close;
    overlay.onclick = (e) => { if (e.target === overlay) close(); };
}

async function handleQueueAction(action, trackId, albumId) {
    const ep = { 'play-now': '/queue/play-now', 'play-next': '/queue/play-next', 'add-to-queue': '/queue/add' }[action];
    if (!ep) return;
    try {
        const res = await fetch(`${API_BASE}${ep}`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ track_id: trackId, album_id: albumId })
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        showToast({ 'play-now': 'Wiedergabe gestartet', 'play-next': 'Als Nächstes hinzugefügt', 'add-to-queue': 'Zur Wiedergabeliste hinzugefügt' }[action]);
        await updatePlayerState();
    } catch (e) { showToast('Fehler: Aktion fehlgeschlagen', true); }
}

function showToast(message, isError = false) {
    const toast = document.createElement('div');
    toast.className = 'toast' + (isError ? ' toast-error' : '');
    toast.innerText = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.classList.add('visible'), 10);
    setTimeout(() => { toast.classList.remove('visible'); setTimeout(() => document.body.removeChild(toast), 300); }, 2000);
}


// ==========================================
// 🗂 NAVIGATION
// ==========================================

async function loadLibraries() {
    currentView = 'libraries'; currentLibrary = currentArtist = currentAlbum = null;
    updateHeader("Bibliotheken", false);
    content.innerHTML = '<div class="loading">Lade Bibliotheken...</div>';
    try {
        const res = await fetch(`${API_BASE}/libraries`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        renderGrid(await res.json(), (lib) => loadArtists(lib));
    } catch (e) { showError(e); }
}

async function loadArtists(lib) {
    currentView = 'artists'; currentLibrary = lib;
    updateHeader(lib.name, true);
    content.innerHTML = '<div class="loading">Lade Künstler...</div>';
    try {
        const res = await fetch(`${API_BASE}/library/${lib.id}/artists`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        renderGrid(await res.json(), (a) => loadAlbums(a));
    } catch (e) { showError(e); }
}

async function loadAlbums(artist) {
    currentView = 'albums'; currentArtist = artist;
    updateHeader(`${currentLibrary.name} > ${artist.name}`, true);
    content.innerHTML = '<div class="loading">Lade Alben...</div>';
    try {
        const res = await fetch(`${API_BASE}/artist/${artist.id}/albums`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        renderGrid(await res.json(), (album) => openAlbum(album));
    } catch (e) { showError(e); }
}

async function openAlbum(album) {
    currentView = 'tracks'; currentAlbum = album;
    updateHeader(`${currentArtist.name} > ${album.name}`, true);
    content.innerHTML = '<div class="loading">Lade Titel...</div>';
    try {
        const res = await fetch(`${API_BASE}/album/${album.id}/tracks`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        currentTracks = await res.json();
        renderTracklist(album, currentTracks);
    } catch (e) { showError(e); }
}

function openTrack(index) {
    const track = currentTracks[index];
    currentView = 'track-detail'; currentTrack = track;
    updateHeader(currentAlbum.name, true);
    const imageUrl = track.image || currentAlbum.image;
    const imgHtml = imageUrl
        ? `<img src="${imageUrl}" alt="${track.name}" onclick="playAlbumFromTrack('${currentAlbum.id}','${track.id}')" style="cursor:pointer" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'"><div class="album-placeholder" style="display:none">🎵</div>`
        : `<div class="album-placeholder">🎵</div>`;
    content.innerHTML = `
        <div class="album-detail"><div class="album-header">
            ${imgHtml}
            <h2>${track.name}</h2>
            <div style="color:rgba(255,255,255,0.9);margin-bottom:1rem;display:flex;align-items:center;justify-content:center;gap:8px;font-size:1.1rem;">
                <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67z"/></svg>
                <span>Dauer: ${formatDuration(track.duration)} Min.</span>
            </div>
            ${track.overview ? `<div style="max-width:600px;margin-bottom:2rem;line-height:1.5;color:#ddd;">${track.overview}</div>` : ''}
            <div style="display:flex;gap:1rem;justify-content:center;width:100%;margin-top:1rem;">
                <button class="btn-secondary" onclick="playAlbumFromTrack('${currentAlbum.id}','${track.id}')">
                    <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor" style="margin-right:8px;vertical-align:middle"><path d="M8 5v14l11-7z"/></svg>AB HIER SPIELEN</button>
                <button class="btn-secondary" onclick="showTrackMenu(currentTracks[${index}],'${currentAlbum.id}')">Mehr Optionen</button>
            </div>
        </div></div>`;
}

function renderTracklist(album, tracks) {
    const imgHtml = album.image
        ? `<img src="${album.image}" alt="${album.name}" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'"><div class="album-placeholder" style="display:none">🎵</div>`
        : `<div class="album-placeholder">🎵</div>`;
    const trackRows = tracks.map((t, i) => `
        <div class="track-row" onclick="openTrack(${i})">
            <span class="track-num">${i+1}</span>
            <span class="track-name">${t.name}</span>
            <span class="track-duration">${formatDuration(t.duration)}</span>
            <button class="track-menu-trigger" onclick="event.stopPropagation();showTrackMenu(currentTracks[${i}],'${album.id}')">⋮</button>
        </div>`).join('');
    content.innerHTML = `
        <div class="album-detail-view">
            <div class="album-sidebar">
                ${imgHtml}
                <button class="btn-play-hero" onclick="playAlbum('${album.id}')">
                    <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor" style="margin-right:8px;vertical-align:middle"><path d="M8 5v14l11-7z"/></svg>ALLES ABSPIELEN</button>
            </div>
            <div class="album-content">
                <div class="album-header-info">
                    <h2>${album.name}</h2>
                    ${currentArtist ? `<h3 style="color:var(--text-muted);margin:0;font-weight:normal">${currentArtist.name}</h3>` : ''}
                </div>
                <div class="track-list">${trackRows}</div>
            </div>
        </div>`;
}

function formatDuration(sec) {
    if (!sec) return "0:00";
    return `${Math.floor(sec/60)}:${String(Math.floor(sec%60)).padStart(2,'0')}`;
}


// ==========================================
// 🎵 PLAYBACK ACTIONS
// ==========================================

async function playAlbum(albumId) {
    try {
        const res = await fetch(`${API_BASE}/play/album/${albumId}`, { method: 'POST' });
        if (!res.ok) throw new Error(`Playback failed: ${res.status}`);
        updatePlayerState();
    } catch (e) { showError(e); }
}

async function playAlbumFromTrack(albumId, trackId) {
    try {
        const res = await fetch(`${API_BASE}/play/album/${albumId}?start_track_id=${trackId}`, { method: 'POST' });
        if (!res.ok) throw new Error(`Playback failed: ${res.status}`);
        updatePlayerState();
    } catch (e) { showError(e); }
}

function adjustVolume(delta) {
    const slider = document.getElementById('volume-slider');
    const newVal = Math.max(0, Math.min(parseInt(slider.max), parseInt(slider.value) + delta));
    slider.value = newVal;
    setVolume(newVal);
}
window.adjustVolume = adjustVolume;

async function setVolume(vol) {
    try {
        await fetch(`${API_BASE}/player/volume`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ volume: vol })
        });
    } catch (e) {}
}


// ==========================================
// 🔧 HELPERS
// ==========================================

function renderGrid(items, onClick) {
    content.innerHTML = '';
    items.forEach(item => {
        const el = document.createElement('div');
        el.className = 'card';
        el.innerHTML = item.image
            ? `<img src="${item.image}" loading="lazy" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'"><div class="album-placeholder" style="display:none">🎵</div><div class="title">${item.name}</div>`
            : `<div class="album-placeholder">🎵</div><div class="title">${item.name}</div>`;
        el.onclick = () => onClick(item);
        content.appendChild(el);
    });
}

function showError(e) {
    content.innerHTML = `<div class="error">Fehler: ${e.message}</div>`;
}


// ==========================================
// 🎮 PLAYER CONTROLS
// ==========================================

function setupPlayerControls() {
    document.getElementById('btn-play-pause').onclick = async () => {
        const state = await fetch(`${API_BASE}/player/state`).then(r => r.json());
        if (state.state === 'playing') {
            await fetch(`${API_BASE}/player/pause`, { method: 'POST' });
        } else {
            await fetch(`${API_BASE}/player/resume`, { method: 'POST' });
        }
        updatePlayerState();
    };
    document.getElementById('btn-stop').onclick    = () => fetch(`${API_BASE}/player/stop`,     { method: 'POST' });
    document.getElementById('btn-next').onclick    = () => fetch(`${API_BASE}/player/next`,     { method: 'POST' });
    document.getElementById('btn-prev').onclick    = () => fetch(`${API_BASE}/player/previous`, { method: 'POST' });

    const progressBar = document.querySelector('.progress-bar-bg');
    if (progressBar) {
        progressBar.onclick = async (e) => {
            const rect = progressBar.getBoundingClientRect();
            const pct  = (e.clientX - rect.left) / rect.width;
            try {
                const state = await fetch(`${API_BASE}/player/state`).then(r => r.json());
                if (state.duration > 0) {
                    await fetch(`${API_BASE}/player/seek`, {
                        method: 'POST', headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ position: state.duration * pct })
                    });
                    updatePlayerState();
                }
            } catch (e) {}
        };
    }

    const volumeSlider = document.getElementById('volume-slider');
    if (volumeSlider) {
        let vt;
        volumeSlider.oninput = (e) => {
            const vol = parseInt(e.target.value);
            document.getElementById('volume-value').innerText = `${vol}%`;
            clearTimeout(vt);
            vt = setTimeout(() => setVolume(vol), 200);
        };
    }
}

async function updatePlayerState() {
    const overlay = document.getElementById('connection-overlay');
    try {
        const state = await fetch(`${API_BASE}/player/state`).then(r => r.json());
        if (overlay) overlay.style.display = 'none';

        // Bildschirm-Logik: Bei Wiedergabe immer einschalten + Timer stoppen
        const nowPlaying = state.state === 'playing';
        if (nowPlaying && !_isPlaying) {
            // Wiedergabe gerade gestartet → Bildschirm ein, Timer stoppen
            clearTimeout(_screenTimer);
            if (_screenIsOff) _screenWakeUp();
        } else if (!nowPlaying && _isPlaying) {
            // Wiedergabe gerade gestoppt/pausiert → Timer starten
            _resetScreenTimer();
        }
        _isPlaying = nowPlaying;

        const stateMap = { idle:'Bereit', loading:'Lade...', playing:'Wiedergabe', paused:'Pause', stopped:'Gestoppt', error:'Fehler' };
        statusDiv.innerText = stateMap[state.state] || state.state.toUpperCase();

        const btnPP = document.getElementById('btn-play-pause');
        btnPP.innerHTML = state.state === 'playing'
            ? '<svg viewBox="0 0 24 24" width="32" height="32" fill="currentColor"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>'
            : '<svg viewBox="0 0 24 24" width="32" height="32" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>';

        const queueCount = document.getElementById('queue-count');
        if (queueCount) {
            const total = state.total_tracks || 0;
            queueCount.innerText = total;
            queueCount.style.display = total > 0 ? 'flex' : 'none';
        }

        if (currentView === 'tracks' && state.current_track) {
            document.querySelectorAll('.track-row').forEach((row, i) => {
                const t = currentTracks[i];
                row.classList.toggle('active', !!(t && t.id === state.current_track.id));
            });
        } else if (currentView === 'tracks') {
            document.querySelectorAll('.track-row').forEach(r => r.classList.remove('active'));
        }

        const npContainer = document.querySelector('.now-playing');
        if (state.current_track) {
            npContainer.style.display = 'flex';
            document.getElementById('np-title').innerText  = state.current_track.name  || '';
            document.getElementById('np-artist').innerText = state.current_track.artist || '';
        } else {
            npContainer.style.display = 'none';
        }

        const progressFill = document.getElementById('progress-fill');
        if (state.duration > 0) {
            const pct = Math.min(100, ((state.position || 0) / state.duration) * 100);
            progressFill.style.width = `${pct}%`;
            document.getElementById('current-time').innerText = formatDuration(state.position || 0);
            document.getElementById('total-time').innerText   = formatDuration(state.duration);
        } else {
            progressFill.style.width = '0%';
            document.getElementById('current-time').innerText = '0:00';
            document.getElementById('total-time').innerText   = '0:00';
        }

        document.querySelectorAll('footer button').forEach(b => {
            b.disabled = false; b.style.opacity = 1; b.style.pointerEvents = 'auto';
        });

        if (queueVisible) await updateQueue();

    } catch (e) {
        statusDiv.innerText = 'OFFLINE';
        if (overlay) overlay.style.display = 'flex';
        document.querySelectorAll('footer button').forEach(b => {
            b.disabled = true; b.style.opacity = 0.5; b.style.pointerEvents = 'none';
        });
    }
}


// ==========================================
// 🔐 ADMIN PANEL
// ==========================================

let _adminPin   = '';
let _adminToken = null;

function openAdminPanel() {
    _adminPin = ''; _adminToken = null;
    document.getElementById('admin-overlay').style.display = 'flex';
    document.getElementById('admin-pin-screen').style.display      = 'block';
    document.getElementById('admin-settings-screen').style.display = 'none';
    document.getElementById('pin-error').style.display = 'none';
    _renderPinDots();
}

function closeAdminPanel() {
    document.getElementById('admin-overlay').style.display = 'none';
    _adminPin = ''; _adminToken = null;
}

function adminLogout() { closeAdminPanel(); }

function pinInput(digit) {
    if (_adminPin.length >= 8) return;
    _adminPin += digit;
    _renderPinDots();
    if (_adminPin.length >= 4) _tryPin();
}
function pinBackspace() { _adminPin = _adminPin.slice(0, -1); _renderPinDots(); }
function pinClear()     { _adminPin = ''; _renderPinDots(); }

function _renderPinDots() {
    document.querySelectorAll('#pin-dots span').forEach((dot, i) => {
        dot.classList.toggle('filled', i < _adminPin.length);
    });
}

async function _tryPin() {
    try {
        const res = await fetch(`${API_BASE}/admin/verify-pin`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pin: _adminPin })
        });
        if (!res.ok) throw new Error('wrong');
        _adminToken = (await res.json()).token;
        _openSettings();
    } catch {
        document.getElementById('pin-error').style.display = 'block';
        _adminPin = '';
        setTimeout(() => { document.getElementById('pin-error').style.display = 'none'; _renderPinDots(); }, 1200);
        _renderPinDots();
    }
}

async function _openSettings() {
    document.getElementById('admin-pin-screen').style.display      = 'none';
    document.getElementById('admin-settings-screen').style.display = 'block';
    switchTab('general');
    await _loadSettings();
}

async function _loadSettings() {
    try {
        const data = await fetch(`${API_BASE}/admin/settings?token=${_adminToken}`).then(r => r.json());
        document.getElementById('set-device-name').value      = data.device_name   || '';
        document.getElementById('set-jellyfin-url').value     = data.jellyfin_url  || '';
        document.getElementById('set-audio-device').value     = data.audio_device  || '';
        document.getElementById('set-max-volume').value       = data.max_volume    ?? 60;
        document.getElementById('set-max-volume-val').innerText = data.max_volume  ?? 60;
        document.getElementById('set-max-volume').oninput = (e) => {
            document.getElementById('set-max-volume-val').innerText = e.target.value;
        };
    } catch (e) { console.error('Settings load failed', e); }
}

async function saveSettings() {
    try {
        const res = await fetch(`${API_BASE}/admin/settings`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                token:        _adminToken,
                device_name:  document.getElementById('set-device-name').value,
                jellyfin_url: document.getElementById('set-jellyfin-url').value,
                audio_device: document.getElementById('set-audio-device').value,
                max_volume:   parseInt(document.getElementById('set-max-volume').value),
            })
        });
        if (!res.ok) throw new Error();
        showToast('✅ Einstellungen gespeichert');
    } catch { showToast('❌ Fehler beim Speichern', true); }
}

async function saveNewPin() {
    const newPin     = document.getElementById('set-new-pin').value.trim();
    const confirmPin = document.getElementById('set-confirm-pin').value.trim();
    const msg        = document.getElementById('pin-change-msg');
    msg.style.display = 'block';
    if (newPin.length < 4)       { msg.style.color = '#ff6b6b'; msg.innerText = 'PIN muss mind. 4 Ziffern haben'; return; }
    if (newPin !== confirmPin)   { msg.style.color = '#ff6b6b'; msg.innerText = 'PINs stimmen nicht überein';     return; }
    try {
        const res = await fetch(`${API_BASE}/admin/settings`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token: _adminToken, new_pin: newPin })
        });
        if (!res.ok) throw new Error();
        msg.style.color = '#6bffb3'; msg.innerText = '✅ PIN geändert';
        document.getElementById('set-new-pin').value     = '';
        document.getElementById('set-confirm-pin').value = '';
    } catch { msg.style.color = '#ff6b6b'; msg.innerText = '❌ Fehler beim Ändern'; }
}

function switchTab(name) {
    const names = ['general', 'security', 'ota'];
    document.querySelectorAll('.admin-tab').forEach((t, i) => t.classList.toggle('active', names[i] === name));
    names.forEach(t => { document.getElementById(`tab-${t}`).style.display = t === name ? 'block' : 'none'; });
    if (name === 'ota') _loadOtaStatus();
}

async function _loadOtaStatus() {
    const box = document.getElementById('ota-status-box');
    const btn = document.getElementById('btn-ota-update');
    box.innerHTML = '<div class="ota-loading">Prüfe auf Updates...</div>';
    btn.style.display = 'none';
    try {
        const data = await fetch(`${API_BASE}/admin/ota/status?token=${_adminToken}`).then(r => r.json());
        if (data.error) { box.innerHTML = `<p class="ota-error">⚠️ Git nicht verfügbar: ${data.error}</p>`; return; }
        const badge = data.updates_available
            ? `<span class="ota-badge-update">🔄 ${data.commits_behind} Update(s) verfügbar</span>`
            : `<span class="ota-badge-ok">✅ Aktuell</span>`;
        box.innerHTML = `
            <div class="ota-info-row"><span>Branch</span><strong>${data.branch}</strong></div>
            <div class="ota-info-row"><span>Lokaler Commit</span><strong>${data.local_commit}</strong></div>
            <div class="ota-info-row"><span>Remote Commit</span><strong>${data.remote_commit}</strong></div>
            <div class="ota-info-row"><span>Letzter Commit</span><strong>${data.commit_message}</strong></div>
            <div class="ota-info-row"><span>Datum</span><strong>${new Date(data.commit_date).toLocaleString('de-DE')}</strong></div>
            <div class="ota-status-badge">${badge}</div>`;
        btn.style.display = data.updates_available ? 'block' : 'none';
    } catch { box.innerHTML = `<p class="ota-error">Verbindungsfehler</p>`; }
}

async function startOtaUpdate() {
    const btn = document.getElementById('btn-ota-update');
    const log = document.getElementById('ota-log');
    btn.disabled = true; btn.innerText = '⏳ Update läuft...';
    log.style.display = 'block'; log.innerHTML = '';
    try {
        const res = await fetch(`${API_BASE}/admin/ota/update`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token: _adminToken })
        });
        const reader = res.body.getReader();
        const dec = new TextDecoder();
        let buf = '';
        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            buf += dec.decode(value, { stream: true });
            const lines = buf.split('\n'); buf = lines.pop();
            for (const line of lines) {
                if (!line.startsWith('data:')) continue;
                try {
                    const msg = JSON.parse(line.slice(5).trim());
                    if (msg.text === 'done') { btn.innerText = '✅ Fertig'; return; }
                    const el = document.createElement('div');
                    el.className = `ota-log-line ${msg.level === 'error' ? 'ota-error' : msg.level === 'success' ? 'ota-success' : ''}`;
                    el.innerText = msg.text;
                    log.appendChild(el);
                    log.scrollTop = log.scrollHeight;
                } catch {}
            }
        }
    } catch (e) {
        const el = document.createElement('div');
        el.className = 'ota-log-line ota-error';
        el.innerText = `Verbindungsfehler: ${e.message}`;
        log.appendChild(el);
    }
}

init();
