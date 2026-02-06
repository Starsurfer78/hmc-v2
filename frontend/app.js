const API_BASE = "";

// State
let currentView = 'libraries'; 
let currentLibrary = null;
let currentArtist = null;
let currentAlbum = null;
let currentTracks = [];
let currentTrack = null;

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
    loadLibraries();
    setInterval(updatePlayerState, 2000);
    
    // Load saved accent
    const savedAccent = localStorage.getItem('hmc_accent');
    if (savedAccent) {
        document.documentElement.style.setProperty('--accent-color', savedAccent);
    }
}

function setupAccentSwitcher() {
    const accents = ['#e5a00d', '#4facfe', '#ff6b6b', '#6bffb3', '#d45d79']; // Orange, Blue, Red, Green, Pink
    let idx = 0;
    
    // Try to find current index
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
    // Block context menu
    document.addEventListener('contextmenu', e => e.preventDefault());
    
    // Block double tap zoom (optional, CSS touch-action is better)
    document.addEventListener('touchstart', e => {
        if (e.touches.length > 1) e.preventDefault();
    }, { passive: false });
}

function setupNavigation() {
    btnHome.onclick = loadLibraries;
    btnBack.onclick = goBack;
}

function goBack() {
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
        // Fetch tracks
        const res = await fetch(`${API_BASE}/album/${album.id}/tracks`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        currentTracks = await res.json();
        
        renderTracklist(album, currentTracks);
        
        // Removed auto-play per user request to allow browsing
    } catch (e) {
        showError(e);
    }
}

function openTrack(index) {
    const track = currentTracks[index];
    currentView = 'track-detail';
    currentTrack = track;
    
    updateHeader(`${currentAlbum.name}`, true); // Simplified header
    
    let imgHtml = '';
    // Use track image if available, otherwise album image
    const imageUrl = track.image || currentAlbum.image;
    
    if (imageUrl) {
        imgHtml = `
            <img src="${imageUrl}" alt="${track.name}" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex'">
            <div class="placeholder" style="display:none; width: 250px; height: 250px; margin: 0 auto 1rem; font-size: 3rem;">🎵</div>
        `;
    } else {
        imgHtml = `<div class="placeholder" style="width: 250px; height: 250px; margin: 0 auto 1rem; font-size: 3rem;">🎵</div>`;
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
                
                <button class="btn-play-hero" onclick="playAlbumFromTrack('${currentAlbum.id}', '${track.id}')">
                    <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor" style="margin-right: 8px; vertical-align: middle;"><path d="M8 5v14l11-7z"/></svg>
                    AB HIER SPIELEN
                </button>
            </div>
        </div>
    `;
}

function renderTracklist(album, tracks) {
    let imgHtml = '';
    if (album.image) {
        imgHtml = `
            <img src="${album.image}" alt="${album.name}" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex'">
            <div class="placeholder" style="display:none; width: 250px; height: 250px; margin: 0 auto 1rem; font-size: 3rem;">🎵</div>
        `;
    } else {
        imgHtml = `<div class="placeholder" style="width: 250px; height: 250px; margin: 0 auto 1rem; font-size: 3rem;">🎵</div>`;
    }

    const trackRows = tracks.map((t, i) => `
        <div class="track-row" onclick="openTrack(${i})">
            <span class="track-num">${i+1}</span>
            <span class="track-name">${t.name}</span>
            <span class="track-dur">${formatDuration(t.duration)}</span>
        </div>
    `).join('');

    content.innerHTML = `
        <div class="album-detail">
            <div class="album-header">
                ${imgHtml}
                <h2>${album.name}</h2>
                <button class="btn-play-hero" onclick="playAlbum('${album.id}')">
                    <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor" style="margin-right: 8px; vertical-align: middle;"><path d="M8 5v14l11-7z"/></svg>
                    ALLES ABSPIELEN
                </button>
            </div>
            <div class="track-list">
                ${trackRows}
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
                <div class="placeholder" style="display:none">🎵</div>
            `;
        } else {
            imgHtml = `<div class="placeholder">🎵</div>`;
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

    // Seek Functionality
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

    // Volume Control (Hidden logic, can be exposed via UI if needed)
    // For now, we add a simple slider to the footer via JS as requested
    const footerControls = document.querySelector('.player-controls');
    if (footerControls && !document.getElementById('volume-slider')) {
        const volContainer = document.createElement('div');
        volContainer.style.display = 'flex';
        volContainer.style.alignItems = 'center';
        volContainer.style.marginLeft = '1rem';
        
        const volSlider = document.createElement('input');
        volSlider.id = 'volume-slider';
        volSlider.type = 'range';
        volSlider.min = 0;
        volSlider.max = 60; // Max from policy
        volSlider.value = 60;
        volSlider.style.width = '80px';
        volSlider.style.accentColor = 'var(--accent-color)';
        
        volSlider.onchange = async (e) => {
             await fetch(`${API_BASE}/player/volume`, { 
                method: 'POST', 
                headers: {'Content-Type': 'application/json'}, 
                body: JSON.stringify({volume: parseInt(e.target.value)}) 
            });
        };

        volContainer.appendChild(volSlider);
        footerControls.appendChild(volContainer);
    }
}

async function updatePlayerState() {
    const overlay = document.getElementById('connection-overlay');
    try {
        const state = await fetch(`${API_BASE}/player/state`).then(r => r.json());
        
        // Hide Overlay
        if (overlay) overlay.style.display = 'none';

        // Translate State
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

        // Highlight current track in list
        if (currentView === 'tracks' && state.current_track) {
            const rows = document.querySelectorAll('.track-row');
            // Check if current album matches playing album (simple check via currentTracks containing the playing track)
            // But state.current_track has 'id'. 
            // We iterate rows and match index from currentTracks
            
            rows.forEach((row, index) => {
                const track = currentTracks[index];
                if (track && track.id === state.current_track.id) {
                    row.classList.add('active');
                    // Optional: Scroll into view if needed, but might be annoying
                } else {
                    row.classList.remove('active');
                }
            });
        } else if (currentView === 'tracks') {
            // clear if no track playing
             document.querySelectorAll('.track-row').forEach(r => r.classList.remove('active'));
        }

        // Update Now Playing Info
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

        // Update Progress Bar
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

        // Highlight current track if in track view
        if (currentView === 'track-detail' && currentTrack && state.current_track) {
            // Optional: Check if playing track matches current displayed track
        }

    } catch (e) {
        statusDiv.innerText = "OFFLINE";
        // Show Overlay
        if (overlay) overlay.style.display = 'flex';
        
        // Disable buttons
        document.querySelectorAll('footer button').forEach(b => {
            b.disabled = true;
            b.style.opacity = 0.5;
            b.style.pointerEvents = 'none';
        });
    }
}

init();
