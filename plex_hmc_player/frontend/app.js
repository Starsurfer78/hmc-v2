const API_BASE = "";

let currentView = "libraries";
let currentLibrary = null;
let currentArtist = null;
let currentAlbum = null;
let currentTracks = [];
let queueVisible = false;
let _adminPin = "";
let _adminToken = null;

const content = document.getElementById("content");
const statusDiv = document.getElementById("status");
const pageTitle = document.getElementById("page-title");
const btnHome = document.getElementById("btn-home");
const btnBack = document.getElementById("btn-back");

function updateHeader(title, showNav) {
    pageTitle.innerText = title;
    btnHome.style.display = showNav ? "inline-flex" : "none";
    btnBack.style.display = showNav ? "inline-flex" : "none";
}

function showError(e) {
    content.innerHTML = `<div class="error">Fehler: ${e.message}</div>`;
}

function showToast(message, isError = false) {
    const toast = document.createElement("div");
    toast.innerText = message;
    toast.style.position = "fixed";
    toast.style.left = "50%";
    toast.style.bottom = "20px";
    toast.style.transform = "translateX(-50%)";
    toast.style.padding = "10px 14px";
    toast.style.borderRadius = "12px";
    toast.style.background = isError ? "rgba(255,107,107,0.95)" : "rgba(79,172,254,0.95)";
    toast.style.color = "#08101f";
    toast.style.fontWeight = "700";
    toast.style.zIndex = "12000";
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 1800);
}

function formatDuration(sec) {
    const s = Math.max(0, Math.floor(sec || 0));
    return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

function renderGrid(items, onClick) {
    content.innerHTML = `<div class="grid">${items
        .map(
            (item) => `
        <div class="card" data-id="${item.id}">
            <div class="thumb">${item.image ? `<img src="${item.image}" alt="">` : "🎵"}</div>
            <div class="card-name">${item.name}</div>
        </div>`
        )
        .join("")}</div>`;
    content.querySelectorAll(".card").forEach((el) => {
        el.onclick = () => {
            const id = el.getAttribute("data-id");
            const item = items.find((i) => i.id === id);
            if (item) onClick(item);
        };
    });
}

async function loadLibraries() {
    currentView = "libraries";
    currentLibrary = currentArtist = currentAlbum = null;
    updateHeader("Bibliotheken", false);
    content.innerHTML = `<div class="loading">Lade Bibliotheken...</div>`;
    try {
        const res = await fetch(`${API_BASE}/libraries`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const libs = await res.json();
        if (!libs.length) {
            content.innerHTML = `<div class="error">Keine Bibliotheken freigegeben. Bitte im Admin freigeben.</div>`;
            return;
        }
        renderGrid(libs, (lib) => loadArtists(lib));
    } catch (e) {
        showError(e);
    }
}

async function loadArtists(lib) {
    currentView = "artists";
    currentLibrary = lib;
    updateHeader(lib.name, true);
    content.innerHTML = `<div class="loading">Lade Kuenstler...</div>`;
    try {
        const res = await fetch(`${API_BASE}/library/${lib.id}/artists`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        renderGrid(await res.json(), (a) => loadAlbums(a));
    } catch (e) {
        showError(e);
    }
}

async function loadAlbums(artist) {
    currentView = "albums";
    currentArtist = artist;
    updateHeader(`${currentLibrary.name} > ${artist.name}`, true);
    content.innerHTML = `<div class="loading">Lade Alben...</div>`;
    try {
        const res = await fetch(`${API_BASE}/artist/${artist.id}/albums`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        renderGrid(await res.json(), (album) => openAlbum(album));
    } catch (e) {
        showError(e);
    }
}

async function openAlbum(album) {
    currentView = "tracks";
    currentAlbum = album;
    updateHeader(`${currentArtist.name} > ${album.name}`, true);
    content.innerHTML = `<div class="loading">Lade Titel...</div>`;
    try {
        const res = await fetch(`${API_BASE}/album/${album.id}/tracks`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        currentTracks = await res.json();
        renderTracklist(album, currentTracks);
    } catch (e) {
        showError(e);
    }
}

function renderTracklist(album, tracks) {
    const rows = tracks
        .map(
            (t, i) => `
        <div class="card" style="padding:12px;display:flex;gap:12px;align-items:center" onclick="playAlbumFromTrack('${album.id}','${t.id}')">
            <div style="width:34px;color:var(--muted);text-align:right">${i + 1}</div>
            <div style="flex:1">
                <div style="font-weight:700">${t.name}</div>
                <div style="color:var(--muted);font-size:12px">${formatDuration(t.duration)}</div>
            </div>
        </div>`
        )
        .join("");
    content.innerHTML = `
        <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:14px">
            <div style="font-weight:800">${album.name}</div>
            <button onclick="playAlbum('${album.id}')">ALLES ABSPIELEN</button>
        </div>
        <div style="display:flex;flex-direction:column;gap:10px">${rows}</div>
    `;
}

async function playAlbum(albumId) {
    const res = await fetch(`${API_BASE}/play/album/${albumId}`, { method: "POST" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    await updatePlayerState();
}

async function playAlbumFromTrack(albumId, trackId) {
    const res = await fetch(`${API_BASE}/play/album/${albumId}?start_track_id=${trackId}`, { method: "POST" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    await updatePlayerState();
}

function goBack() {
    switch (currentView) {
        case "tracks":
            if (currentArtist) loadAlbums(currentArtist);
            break;
        case "albums":
            if (currentLibrary) loadArtists(currentLibrary);
            break;
        default:
            loadLibraries();
    }
}

function setupNavigation() {
    btnHome.onclick = loadLibraries;
    btnBack.onclick = goBack;
}

function setupPlayerControls() {
    document.getElementById("btn-play-pause").onclick = async () => {
        const state = await fetch(`${API_BASE}/player/state`).then((r) => r.json());
        if (state.state === "playing") {
            await fetch(`${API_BASE}/player/pause`, { method: "POST" });
        } else {
            await fetch(`${API_BASE}/player/resume`, { method: "POST" });
        }
        await updatePlayerState();
    };
    document.getElementById("btn-stop").onclick = () => fetch(`${API_BASE}/player/stop`, { method: "POST" });
    document.getElementById("btn-next").onclick = () => fetch(`${API_BASE}/player/next`, { method: "POST" });
    document.getElementById("btn-prev").onclick = () => fetch(`${API_BASE}/player/previous`, { method: "POST" });

    const progressBar = document.querySelector(".progress-bar-bg");
    if (progressBar) {
        progressBar.onclick = async (e) => {
            const rect = progressBar.getBoundingClientRect();
            const pct = (e.clientX - rect.left) / rect.width;
            const state = await fetch(`${API_BASE}/player/state`).then((r) => r.json());
            if (state.duration > 0) {
                await fetch(`${API_BASE}/player/seek`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ position: state.duration * pct }),
                });
                await updatePlayerState();
            }
        };
    }

    document.getElementById("btn-vol-down").onclick = () => adjustVolume(-5);
    document.getElementById("btn-vol-up").onclick = () => adjustVolume(5);

    const volumeSlider = document.getElementById("volume-slider");
    if (volumeSlider) {
        let vt;
        volumeSlider.oninput = (e) => {
            const vol = parseInt(e.target.value);
            document.getElementById("volume-value").innerText = `${vol}%`;
            clearTimeout(vt);
            vt = setTimeout(() => setVolume(vol), 200);
        };
    }
}

async function setVolume(vol) {
    try {
        await fetch(`${API_BASE}/player/volume`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ volume: vol }),
        });
    } catch {}
}

function adjustVolume(delta) {
    const slider = document.getElementById("volume-slider");
    const newVal = Math.max(0, Math.min(parseInt(slider.max), parseInt(slider.value) + delta));
    slider.value = newVal;
    document.getElementById("volume-value").innerText = `${newVal}%`;
    setVolume(newVal);
}
window.adjustVolume = adjustVolume;
window.playAlbum = playAlbum;
window.playAlbumFromTrack = playAlbumFromTrack;

function openAdminPanel() {
    _adminPin = "";
    _adminToken = null;
    document.getElementById("admin-overlay").style.display = "flex";
    document.getElementById("admin-pin-screen").style.display = "block";
    document.getElementById("admin-settings-screen").style.display = "none";
    document.getElementById("pin-error").style.display = "none";
    renderPinDots();
}

function closeAdminPanel() {
    document.getElementById("admin-overlay").style.display = "none";
    _adminPin = "";
    _adminToken = null;
}

function adminLogout() {
    closeAdminPanel();
}

function pinInput(digit) {
    if (_adminPin.length >= 8) return;
    _adminPin += digit;
    renderPinDots();
    if (_adminPin.length >= 4) tryPin();
}

function pinBackspace() {
    _adminPin = _adminPin.slice(0, -1);
    renderPinDots();
}

function pinClear() {
    _adminPin = "";
    renderPinDots();
}

function renderPinDots() {
    document.querySelectorAll("#pin-dots span").forEach((dot, i) => {
        dot.classList.toggle("filled", i < _adminPin.length);
    });
}

async function tryPin() {
    try {
        const res = await fetch(`${API_BASE}/admin/verify-pin`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ pin: _adminPin }),
        });
        if (!res.ok) throw new Error("wrong");
        _adminToken = (await res.json()).token;
        await openSettings();
    } catch {
        document.getElementById("pin-error").style.display = "block";
        _adminPin = "";
        setTimeout(() => {
            document.getElementById("pin-error").style.display = "none";
            renderPinDots();
        }, 1200);
        renderPinDots();
    }
}

async function openSettings() {
    document.getElementById("admin-pin-screen").style.display = "none";
    document.getElementById("admin-settings-screen").style.display = "block";
    switchTab("general");
    await loadSettings();
}

async function loadSettings() {
    try {
        const data = await fetch(`${API_BASE}/admin/settings?token=${_adminToken}`).then((r) => {
            if (!r.ok) throw new Error(`HTTP ${r.status}`);
            return r.json();
        });
        document.getElementById("set-device-name").value = data.device_name || "";
        document.getElementById("set-plex-url").value = data.plex_url || "";
        document.getElementById("set-plex-token").value = "";
        document.getElementById("set-audio-device").value = data.audio_device || "";
        document.getElementById("set-max-volume").value = data.max_volume ?? 60;
        document.getElementById("set-max-volume-val").innerText = data.max_volume ?? 60;
        document.getElementById("plex-token-info").innerText = data.plex_token_present
            ? "Plex Token ist gespeichert."
            : "Noch kein Plex Token gespeichert.";
        document.getElementById("set-max-volume").oninput = (e) => {
            document.getElementById("set-max-volume-val").innerText = e.target.value;
        };
    } catch (e) {
        showToast(`Fehler beim Laden: ${e.message}`, true);
    }
}

async function saveSettings() {
    try {
        const payload = {
            token: _adminToken,
            device_name: document.getElementById("set-device-name").value,
            plex_url: document.getElementById("set-plex-url").value,
            plex_token: document.getElementById("set-plex-token").value,
            audio_device: document.getElementById("set-audio-device").value,
            max_volume: parseInt(document.getElementById("set-max-volume").value),
        };
        const res = await fetch(`${API_BASE}/admin/settings`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        await loadSettings();
        await loadLibraries();
        await updatePlayerState();
        showToast("Einstellungen gespeichert");
    } catch (e) {
        showToast(`Speichern fehlgeschlagen: ${e.message}`, true);
    }
}

async function saveNewPin() {
    const newPin = document.getElementById("set-new-pin").value.trim();
    const confirmPin = document.getElementById("set-confirm-pin").value.trim();
    const msg = document.getElementById("pin-change-msg");
    msg.style.display = "block";
    if (newPin.length < 4) {
        msg.style.color = "var(--danger)";
        msg.innerText = "PIN muss mind. 4 Ziffern haben";
        return;
    }
    if (newPin !== confirmPin) {
        msg.style.color = "var(--danger)";
        msg.innerText = "PINs stimmen nicht ueberein";
        return;
    }
    try {
        const res = await fetch(`${API_BASE}/admin/settings`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ token: _adminToken, new_pin: newPin }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        msg.style.color = "#6bffb3";
        msg.innerText = "PIN geaendert";
        document.getElementById("set-new-pin").value = "";
        document.getElementById("set-confirm-pin").value = "";
    } catch (e) {
        msg.style.color = "var(--danger)";
        msg.innerText = `Fehler: ${e.message}`;
    }
}

const _TAB_NAMES = ["general", "libraries", "security"];

function switchTab(name) {
    document.querySelectorAll(".admin-tab").forEach((tab, i) => {
        tab.classList.toggle("active", _TAB_NAMES[i] === name);
    });
    _TAB_NAMES.forEach((tabName) => {
        document.getElementById(`tab-${tabName}`).style.display = tabName === name ? "block" : "none";
    });
    if (name === "libraries") loadPlexSections();
}

async function loadPlexSections() {
    const list = document.getElementById("lib-list");
    const btn = document.getElementById("btn-save-libraries");
    const msg = document.getElementById("lib-save-msg");
    list.innerHTML = `<div class="lib-loading">Lade Plex Bibliotheken...</div>`;
    btn.style.display = "none";
    msg.style.display = "none";
    try {
        const libs = await fetch(`${API_BASE}/admin/plex/sections?token=${_adminToken}`).then((r) => {
            if (!r.ok) throw new Error(`HTTP ${r.status}`);
            return r.json();
        });
        if (!libs.length) {
            list.innerHTML = `<p class="admin-hint">Keine Plex Bibliotheken gefunden.</p>`;
            return;
        }
        list.innerHTML = libs
            .map(
                (lib) => `
            <label class="lib-item ${lib.enabled ? "lib-item-active" : ""}" id="lib-label-${lib.id}">
                <div class="lib-item-info">
                    <span class="lib-item-name">${lib.name}</span>
                    <span class="lib-item-type">${lib.type || "unknown"}</span>
                </div>
                <div class="lib-toggle-wrap">
                    <input type="checkbox" class="lib-checkbox" id="lib-${lib.id}" data-id="${lib.id}" ${lib.enabled ? "checked" : ""} onchange="onLibToggle(this)">
                    <span class="lib-toggle-track"><span class="lib-toggle-thumb"></span></span>
                </div>
            </label>`
            )
            .join("");
        btn.style.display = "block";
    } catch (e) {
        list.innerHTML = `<p class="error">Fehler: ${e.message}<br><small>Ist Plex URL/Token korrekt?</small></p>`;
    }
}

function onLibToggle(checkbox) {
    const label = document.getElementById(`lib-label-${checkbox.dataset.id}`);
    if (label) label.classList.toggle("lib-item-active", checkbox.checked);
}

async function saveLibraries() {
    const selected = Array.from(document.querySelectorAll(".lib-checkbox"))
        .filter((cb) => cb.checked)
        .map((cb) => cb.dataset.id);
    const msg = document.getElementById("lib-save-msg");
    msg.style.display = "none";
    try {
        const res = await fetch(`${API_BASE}/admin/settings`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ token: _adminToken, allowed_sections: selected }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        msg.style.display = "block";
        msg.style.color = "#6bffb3";
        msg.innerText = `${selected.length} Bibliothek(en) gespeichert`;
        await loadLibraries();
        showToast("Bibliotheken gespeichert");
    } catch (e) {
        msg.style.display = "block";
        msg.style.color = "var(--danger)";
        msg.innerText = `Fehler: ${e.message}`;
    }
}

window.openAdminPanel = openAdminPanel;
window.closeAdminPanel = closeAdminPanel;
window.adminLogout = adminLogout;
window.pinInput = pinInput;
window.pinBackspace = pinBackspace;
window.pinClear = pinClear;
window.switchTab = switchTab;
window.saveSettings = saveSettings;
window.saveLibraries = saveLibraries;
window.saveNewPin = saveNewPin;
window.onLibToggle = onLibToggle;

async function updatePlayerState() {
    const overlay = document.getElementById("connection-overlay");
    try {
        const state = await fetch(`${API_BASE}/player/state`).then((r) => r.json());
        if (overlay) overlay.style.display = "none";

        const stateMap = { idle: "Bereit", loading: "Lade...", playing: "Wiedergabe", paused: "Pause", stopped: "Gestoppt", error: "Fehler" };
        statusDiv.innerText = stateMap[state.state] || String(state.state || "").toUpperCase();

        const btnPP = document.getElementById("btn-play-pause");
        btnPP.innerHTML =
            state.state === "playing"
                ? '<svg viewBox="0 0 24 24" width="32" height="32" fill="currentColor"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>'
                : '<svg viewBox="0 0 24 24" width="32" height="32" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>';

        const np = document.querySelector(".now-playing");
        if (state.current_track) {
            np.style.display = "flex";
            document.getElementById("np-title").innerText = state.current_track.name || "";
            document.getElementById("np-artist").innerText = state.current_track.artist || "";
        } else {
            np.style.display = "none";
        }

        const progressFill = document.getElementById("progress-fill");
        if (state.duration > 0) {
            const pct = Math.min(100, ((state.position || 0) / state.duration) * 100);
            progressFill.style.width = `${pct}%`;
            document.getElementById("current-time").innerText = formatDuration(state.position || 0);
            document.getElementById("total-time").innerText = formatDuration(state.duration || 0);
        } else {
            progressFill.style.width = "0%";
            document.getElementById("current-time").innerText = "0:00";
            document.getElementById("total-time").innerText = "0:00";
        }
    } catch {
        statusDiv.innerText = "OFFLINE";
        if (overlay) overlay.style.display = "flex";
    }
}

async function init() {
    setupNavigation();
    setupPlayerControls();
    loadLibraries();
    setInterval(updatePlayerState, 2000);
    try {
        const vol = await fetch(`${API_BASE}/player/volume`).then((r) => r.json());
        const slider = document.getElementById("volume-slider");
        const value = document.getElementById("volume-value");
        if (slider && value && typeof vol.volume === "number") {
            slider.value = vol.volume;
            value.innerText = `${vol.volume}%`;
        }
    } catch {}
}

init();
