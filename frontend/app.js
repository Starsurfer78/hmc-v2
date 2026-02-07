const API_BASE = "";

// State
let currentView = 'libraries'; 
let currentLibrary = null;
let currentArtist = null;
let currentAlbum = null;
let currentTracks = [];
let currentTrack = null;

// Queue UI State
let queueVisible = false;

const content = document.getElementById('content');
const statusDiv = document.getElementById('status');
const pageTitle = document.getElementById('page-title');
const btnHome = document.getElementById('btn-home');
const btnBack = document.getElementById('btn-back');

// Init
async function init() {
    setupPlayerControls();
    setupNavigation();
    setupKioskProtection();
    setupAccentSwitcher();
    setupQueueUI();
    loadLibraries();
    setInterval(updatePlayerState, 2000);
    
    // Load current volume
    try {
        const vol = await fetch(`${API_BASE}/player/volume`).then(r => r.json());
        const slider = document.getElementById('volume-slider');
        const value = document.getElementById('volume-value');
        if (slider && value) {
            slider.value = vol.volume;
            value.innerText = `${vol.volume}%`;
        }
    } catch (e) {
        console.log('Could not load volume');
    }
    
    // Load saved accent
    const savedAccent = localStorage.getItem('hmc_accent');
    if (savedAccent) {
        document.documentElement.style.setProperty('--accent-color', savedAccent);
    }
}

function setupAccentSwitcher() {
    const accents = ['#e5a00d', '#4facfe', '#ff6b6b', '#6bffb3', '#d45d79'];
    let idx = 0;
    
    const current = localStorage.getItem('hmc_accent');
    if (current) {
        const found = accents.indexOf(current);
        if (found !== -1) idx = found;
    }

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
    document.addEventListener('touchstart', e => {
        if (e.touches.length > 1) e.preventDefault();
    }, { passive: false });
}

function setupNavigation() {
    btnHome.onclick = loadLibraries;
    btnBack.onclick = goBack;
}

function goBack() {
    // Close queue if open
    if (queueVisible) {
        closeQueue();
        return;
    }
    
    switch (currentView) {
        case 'track-detail':
            if (currentAlbum) openAlbum(currentAlbum);
            break;
        case 'tracks':
            if (currentArtist) loadAlbums(currentArtist);
            break;
        case 'albums':
            if (currentLibrary) loadArtists(currentLibrary);
            break;
        case 'artists':
            loadLibraries();
            break;
        default:
            loadLibraries();
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
    // Add Queue button to player controls
    const target = document.getElementById('queue-container-target');
    if (target) {
        target.appendChild(createQueueButton());
    }
    
    // Create Queue Overlay
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
                <div class="queue-current">
                    <!-- Current track info -->
                </div>
                <div class="queue-list">
                    <!-- Queue items -->
                </div>
            </div>
        </div>
    `;
    document.body.appendChild(queueOverlay);
    
    // Setup close handler
    document.getElementById('queue-close').onclick = closeQueue;
    queueOverlay.onclick = (e) => {
        if (e.target === queueOverlay) closeQueue();
    };
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
    const overlay = document.getElementById('queue-overlay');
    overlay.classList.add('visible');
    
    // Load queue data
    await updateQueue();
}

function closeQueue() {
    queueVisible = false;
    const overlay = document.getElementById('queue-overlay');
    overlay.classList.remove('visible');
}

async function updateQueue() {
    if (!queueVisible) return;
    
    try {
        const data = await fetch(`${API_BASE}/queue`).then(r => r.json());
        
        const currentDiv = document.querySelector('.queue-current');
        const listDiv = document.querySelector('.queue-list');
        
        // Current Track
        if (data.current_track) {
            const track = data.current_track;
            currentDiv.innerHTML = `
                <div class="queue-current-card">
                    ${track.image ? `<img src="${track.image}" alt="${track.name}">` : '<div class="album-placeholder">🎵</div>'}
                    <div class="queue-current-info">
                        <h3>${track.name}</h3>
                        <p>Spielt gerade</p>
                    </div>
                </div>
            `;
        } else {
            currentDiv.innerHTML = '<p>Keine Wiedergabe</p>';
        }
        
        // Upcoming Tracks
        if (data.upcoming_tracks && data.upcoming_tracks.length > 0) {
            listDiv.innerHTML = '<h3>Als Nächstes</h3>' + data.upcoming_tracks.map((track, idx) => {
                const actualIndex = data.current_index + idx + 1;
                return `
                    <div class="queue-item" data-index="${actualIndex}">
                        <span class="queue-item-num">${idx + 1}</span>
                        <span class="queue-item-name">${track.name}</span>
                        <div class="queue-item-actions">
                            <button onclick="jumpToTrack(${actualIndex})" title="Zu diesem Titel springen">
                                <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
                            </button>
                            <button onclick="removeFromQueue(${actualIndex})" title="Entfernen">
                                <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>
                            </button>
                        </div>
                    </div>
                `;
            }).join('');
        } else {
            listDiv.innerHTML = '<p class="queue-empty">Keine weiteren Titel in der Warteschlange</p>';
        }
        
    } catch (e) {
        console.error('Failed to load queue', e);
    }
}

async function jumpToTrack(index) {
    try {
        await fetch(`${API_BASE}/queue/jump/${index}`, { method: 'POST' });
        await updateQueue();
        await updatePlayerState();
    } catch (e) {
        console.error('Jump failed', e);
    }
}

async function removeFromQueue(index) {
    try {
        await fetch(`${API_BASE}/queue/${index}`, { method: 'DELETE' });
        await updateQueue();
        await updatePlayerState();
    } catch (e) {
        console.error('Remove failed', e);
    }
}

// ==========================================
// 🎵 TRACK CONTEXT MENU
// ==========================================

function showTrackMenu(track, albumId) {
    // Create overlay
    const overlay = document.createElement('div');
    overlay.className = 'track-menu-overlay';
    overlay.innerHTML = `
        <div class="track-menu">
            <div class="track-menu-header">
                <h3>${track.name}</h3>
            </div>
            <div class="track-menu-actions">
                <button class="track-menu-btn" data-action="play-now">
                    <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
                    <span>Jetzt wiedergeben</span>
                </button>
                <button class="track-menu-btn" data-action="play-next">
                    <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor"><path d="M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z"/></svg>
                    <span>Als Nächstes wiedergeben</span>
                </button>
                <button class="track-menu-btn" data-action="add-to-queue">
                    <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor"><path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/></svg>
                    <span>Zur Wiedergabeliste hinzufügen</span>
                </button>
            </div>
            <button class="track-menu-close">Abbrechen</button>
        </div>
    `;
    
    document.body.appendChild(overlay);
    
    // Setup handlers
    overlay.querySelectorAll('.track-menu-btn').forEach(btn => {
        btn.onclick = async () => {
            const action = btn.dataset.action;
            await handleQueueAction(action, track.id, albumId);
            document.body.removeChild(overlay);
        };
    });
    
    const closeMenu = () => document.body.removeChild(overlay);
    overlay.querySelector('.track-menu-close').onclick = closeMenu;
    overlay.onclick = (e) => {
        if (e.target === overlay) closeMenu();
    };
}

async function handleQueueAction(action, trackId, albumId) {
    const endpoint = {
        'play-now': '/queue/play-now',
        'play-next': '/queue/play-next',
        'add-to-queue': '/queue/add'
    }[action];
    
    if (!endpoint) return;
    
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ track_id: trackId, album_id: albumId })
        });
        
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        
        const result = await response.json();
        console.log('Queue action result:', result);
        
        // Show feedback
        showToast({
            'play-now': 'Wiedergabe gestartet',
            'play-next': 'Als Nächstes hinzugefügt',
            'add-to-queue': 'Zur Wiedergabeliste hinzugefügt'
        }[action]);
        
        await updatePlayerState();
        
    } catch (e) {
        console.error('Queue action failed', e);
        showToast('Fehler: Aktion fehlgeschlagen', true);
    }
}

function showToast(message, isError = false) {
    const toast = document.createElement('div');
    toast.className = 'toast' + (isError ? ' toast-error' : '');
    toast.innerText = message;
    document.body.appendChild(toast);
    
    setTimeout(() => toast.classList.add('visible'), 10);
    setTimeout(() => {
        toast.classList.remove('visible');
        setTimeout(() => document.body.removeChild(toast), 300);
    }, 2000);
}

// Navigation
async function loadLibraries() {
    currentView = 'libraries';
    currentLibrary = null;
    currentArtist = null;
    currentAlbum = null;
    
    updateHeader("Bibliotheken", false);
    content.innerHTML = '<div class="loading">Lade Bibliotheken...</div>';
    
    try {
        const res = await fetch(`${API_BASE}/libraries`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const libs = await res.json();
        renderGrid(libs, (lib) => loadArtists(lib));
    } catch (e) {
        showError(e);
    }
}

async function loadArtists(lib) {
    currentView = 'artists';
    currentLibrary = lib;
    
    updateHeader(`${lib.name}`, true);
    content.innerHTML = '<div class="loading">Lade Künstler...</div>';
    
    try {
        const res = await fetch(`${API_BASE}/library/${lib.id}/artists`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const artists = await res.json();
        renderGrid(artists, (artist) => loadAlbums(artist));
    } catch (e) {
        showError(e);
    }
}

async function loadAlbums(artist) {
    currentView = 'albums';
    currentArtist = artist;
    
    updateHeader(`${currentLibrary.name} > ${artist.name}`, true);
    content.innerHTML = '<div class="loading">Lade Alben...</div>';
    
    try {
        const res = await fetch(`${API_BASE}/artist/${artist.id}/albums`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const albums = await res.json();
        renderGrid(albums, (album) => openAlbum(album));
    } catch (e) {
        showError(e);
    }
}

async function openAlbum(album) {
    currentView = 'tracks';
    currentAlbum = album;
    
    updateHeader(`${currentArtist.name} > ${album.name}`, true);
    content.innerHTML = '<div class="loading">Lade Titel...</div>';
    
    try {
        const res = await fetch(`${API_BASE}/album/${album.id}/tracks`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        currentTracks = await res.json();
        
        renderTracklist(album, currentTracks);
    } catch (e) {
        showError(e);
    }
}

function openTrack(index) {
    const track = currentTracks[index];
    currentView = 'track-detail';
    currentTrack = track;
    
    updateHeader(`${currentAlbum.name}`, true);
    
    let imgHtml = '';
    const imageUrl = track.image || currentAlbum.image;
    
    if (imageUrl) {
        imgHtml = `
            <img src="${imageUrl}" alt="${track.name}" 
                 onclick="playAlbumFromTrack('${currentAlbum.id}', '${track.id}')"
                 style="cursor: pointer"
                 onerror="this.style.display='none'; this.nextElementSibling.style.display='flex'">
            <div class="album-placeholder" style="display:none;">🎵</div>
        `;
    } else {
        imgHtml = `<div class="album-placeholder">🎵</div>`;
    }

    content.innerHTML = `
        <div class="album-detail">
            <div class="album-header">
                ${imgHtml}
                <h2>${track.name}</h2>
                <div style="color: rgba(255,255,255,0.9); margin-bottom: 1rem; display: flex; align-items: center; justify-content: center; gap: 8px; font-size: 1.1rem;">
                    <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67z"/></svg>
                    <span>Dauer: ${formatDuration(track.duration)} Min.</span>
                </div>
                ${track.overview ? `<div style="max-width: 600px; margin-bottom: 2rem; line-height: 1.5; color: #ddd;">${track.overview}</div>` : ''}
                
                <div style="display: flex; gap: 1rem; justify-content: center; width: 100%; margin-top: 1rem;">
                    <button class="btn-secondary" onclick="playAlbumFromTrack('${currentAlbum.id}', '${track.id}')">
                        <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor" style="margin-right: 8px; vertical-align: middle;"><path d="M8 5v14l11-7z"/></svg>
                        AB HIER SPIELEN
                    </button>
                    
                    <button class="btn-secondary" onclick="showTrackMenu(currentTracks[${index}], '${currentAlbum.id}')">
                        Mehr Optionen
                    </button>
                </div>
            </div>
        </div>
    `;
}

function renderTracklist(album, tracks) {
    let imgHtml = '';
    if (album.image) {
        imgHtml = `
            <img src="${album.image}" alt="${album.name}" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex'">
            <div class="album-placeholder" style="display:none;">🎵</div>
        `;
    } else {
        imgHtml = `<div class="album-placeholder">🎵</div>`;
    }

    const trackRows = tracks.map((t, i) => `
        <div class="track-row" onclick="openTrack(${i})">
            <span class="track-num">${i+1}</span>
            <span class="track-name">${t.name}</span>
            <span class="track-duration">${formatDuration(t.duration)}</span>
            <button class="track-menu-trigger" onclick="event.stopPropagation(); showTrackMenu(currentTracks[${i}], '${album.id}')">⋮</button>
        </div>
    `).join('');

    content.innerHTML = `
        <div class="album-detail-view">
            <div class="album-sidebar">
                ${imgHtml}
                <button class="btn-play-hero" onclick="playAlbum('${album.id}')">
                    <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor" style="margin-right: 8px; vertical-align: middle;"><path d="M8 5v14l11-7z"/></svg>
                    ALLES ABSPIELEN
                </button>
            </div>
            <div class="album-content">
                <div class="album-header-info">
                    <h2>${album.name}</h2>
                    ${currentArtist ? `<h3 style="color: var(--text-muted); margin: 0; font-weight: normal;">${currentArtist.name}</h3>` : ''}
                </div>
                <div class="track-list">
                    ${trackRows}
                </div>
            </div>
        </div>
    `;
}

function formatDuration(sec) {
    if (!sec) return "0:00";
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
}

// Actions
async function playAlbum(albumId) {
    try {
        const res = await fetch(`${API_BASE}/play/album/${albumId}`, { method: 'POST' });
        if (!res.ok) throw new Error(`Playback failed: ${res.status}`);
        updatePlayerState();
    } catch (e) {
        showError(e);
    }
}

async function playAlbumFromTrack(albumId, trackId) {
    try {
        const res = await fetch(`${API_BASE}/play/album/${albumId}?start_track_id=${trackId}`, { method: 'POST' });
        if (!res.ok) throw new Error(`Playback failed: ${res.status}`);
        updatePlayerState();
    } catch (e) {
        showError(e);
    }
}

function adjustVolume(delta) {
    const slider = document.getElementById('volume-slider');
    let newVal = parseInt(slider.value) + delta;
    if (newVal < 0) newVal = 0;
    if (newVal > 100) newVal = 100; // Assuming max is 100 or 60? HTML says max="60"
    if (newVal > slider.max) newVal = slider.max;
    
    slider.value = newVal;
    setVolume(newVal);
}

// Global scope
window.adjustVolume = adjustVolume;

// Helpers
function renderGrid(items, onClick) {
    content.innerHTML = '';
    items.forEach(item => {
        const el = document.createElement('div');
        el.className = 'card';
        
        let imgHtml = '';
        if (item.image) {
            imgHtml = `
                <img src="${item.image}" loading="lazy" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex'">
                <div class="album-placeholder" style="display:none">🎵</div>
            `;
        } else {
            imgHtml = `<div class="album-placeholder">🎵</div>`;
        }
        
        el.innerHTML = `
            ${imgHtml}
            <div class="title">${item.name}</div>
        `;
        el.onclick = () => onClick(item);
        content.appendChild(el);
    });
}

function showError(e) {
    content.innerHTML = `<div class="error">Fehler: ${e.message}</div>`;
}

// Player Controls
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
    
    document.getElementById('btn-stop').onclick = () => fetch(`${API_BASE}/player/stop`, { method: 'POST' });
    document.getElementById('btn-next').onclick = () => fetch(`${API_BASE}/player/next`, { method: 'POST' });
    document.getElementById('btn-prev').onclick = () => fetch(`${API_BASE}/player/previous`, { method: 'POST' });

    // Seek
    const progressBar = document.querySelector('.progress-bar-bg');
    if (progressBar) {
        progressBar.onclick = async (e) => {
            const rect = progressBar.getBoundingClientRect();
            const percent = (e.clientX - rect.left) / rect.width;
            
            try {
                const state = await fetch(`${API_BASE}/player/state`).then(r => r.json());
                if (state.duration > 0) {
                    const seekTo = state.duration * percent;
                    await fetch(`${API_BASE}/player/seek`, { 
                        method: 'POST', 
                        headers: {'Content-Type': 'application/json'}, 
                        body: JSON.stringify({position: seekTo}) 
                    });
                    updatePlayerState();
                }
            } catch (e) {
                console.error("Seek failed", e);
            }
        };
    }

    // Volume
    const volumeSlider = document.getElementById('volume-slider');
    const volumeValue = document.getElementById('volume-value');
    
    if (volumeSlider && volumeValue) {
        let volumeTimeout;
        volumeSlider.oninput = (e) => {
            const vol = parseInt(e.target.value);
            volumeValue.innerText = `${vol}%`;
            
            clearTimeout(volumeTimeout);
            volumeTimeout = setTimeout(async () => {
                try {
                    await fetch(`${API_BASE}/player/volume`, { 
                        method: 'POST', 
                        headers: {'Content-Type': 'application/json'}, 
                        body: JSON.stringify({volume: vol}) 
                    });
                } catch (e) {
                    console.error('Volume set failed:', e);
                }
            }, 200);
        };
    }
}

async function updatePlayerState() {
    const overlay = document.getElementById('connection-overlay');
    try {
        const state = await fetch(`${API_BASE}/player/state`).then(r => r.json());
        
        if (overlay) overlay.style.display = 'none';

        const stateMap = {
            'idle': 'Bereit',
            'loading': 'Lade...',
            'playing': 'Wiedergabe',
            'paused': 'Pause',
            'stopped': 'Gestoppt',
            'error': 'Fehler'
        };
        statusDiv.innerText = stateMap[state.state] || state.state.toUpperCase();
        
        // Update Play/Pause Icon
        const iconContainer = document.getElementById('btn-play-pause');
        if (state.state === 'playing') {
            iconContainer.innerHTML = '<svg viewBox="0 0 24 24" width="32" height="32" fill="currentColor"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>';
        } else {
            iconContainer.innerHTML = '<svg viewBox="0 0 24 24" width="32" height="32" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>';
        }

        // Update Queue Count
        const queueCount = document.getElementById('queue-count');
        if (queueCount) {
            const total = state.total_tracks || 0;
            queueCount.innerText = total;
            queueCount.style.display = total > 0 ? 'flex' : 'none';
        }

        // Highlight current track
        if (currentView === 'tracks' && state.current_track) {
            const rows = document.querySelectorAll('.track-row');
            rows.forEach((row, index) => {
                const track = currentTracks[index];
                if (track && track.id === state.current_track.id) {
                    row.classList.add('active');
                } else {
                    row.classList.remove('active');
                }
            });
        } else if (currentView === 'tracks') {
             document.querySelectorAll('.track-row').forEach(r => r.classList.remove('active'));
        }

        // Now Playing
        const npContainer = document.querySelector('.now-playing');
        const npTitle = document.getElementById('np-title');
        const npArtist = document.getElementById('np-artist');

        if (state.current_track) {
            npContainer.style.display = 'flex';
            npTitle.innerText = state.current_track.name || "Unbekannter Titel";
            npArtist.innerText = state.current_track.artist || "";
        } else {
            npContainer.style.display = 'none';
        }

        // Progress Bar
        const currentTimeEl = document.getElementById('current-time');
        const totalTimeEl = document.getElementById('total-time');
        const progressFill = document.getElementById('progress-fill');

        if (state.duration > 0) {
            const pos = state.position || 0;
            const dur = state.duration;
            const percent = Math.min(100, (pos / dur) * 100);
            
            progressFill.style.width = `${percent}%`;
            currentTimeEl.innerText = formatDuration(pos);
            totalTimeEl.innerText = formatDuration(dur);
        } else {
            progressFill.style.width = '0%';
            currentTimeEl.innerText = "0:00";
            totalTimeEl.innerText = "0:00";
        }

        // Enable buttons
        document.querySelectorAll('footer button').forEach(b => {
            b.disabled = false;
            b.style.opacity = 1;
            b.style.pointerEvents = 'auto';
        });

        // Update queue view if open
        if (queueVisible) {
            await updateQueue();
        }

    } catch (e) {
        statusDiv.innerText = "OFFLINE";
        if (overlay) overlay.style.display = 'flex';
        
        document.querySelectorAll('footer button').forEach(b => {
            b.disabled = true;
            b.style.opacity = 0.5;
            b.style.pointerEvents = 'none';
        });
    }
}

init();