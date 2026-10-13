# CLAUDE.md – HMC v2.1 (Home Media Console)

> Inhaltsgleich mit `AGENTS.md` (nur die Überschrift unterscheidet sich). Bei Änderungen beide Dateien pflegen.

## Projekt-Übersicht

**HMC v2.1 – Jellyfin Edition** ist ein lokales, kinderfreundliches Audio-Abspielsystem auf Raspberry-Pi-Basis.
Zielgruppe: Kinder (4–10 Jahre) als primäre Nutzer, Eltern als Betreiber (PIN-geschützter Admin-Bereich).
Kernprinzip: **Weniger Features, maximale Stabilität. Kein Cloud-Zwang, kein Wartungsaufwand.**

---

## Architektur auf einen Blick

```
Jellyfin Server  ──▶  Backend (FastAPI)  ──▶  MPV (Audio-Engine, IPC-Socket)
                        │        │
     Frontend (Touch-UI)┘        └──▶ MQTT Broker (Mosquitto, optional)
     inkl. Admin-Panel                       │
                                Home Assistant + Custom Component
                                `custom_components/hmc_media_player`
```

| Schicht | Technologie | Rolle |
|---|---|---|
| Frontend | HTML/CSS/JS (SPA, kein Build-Step) | Touch-UI + Admin-Panel, reiner View-Layer |
| Backend | FastAPI, Python 3.11+ (Pi OS Bookworm) | Zentrale Logik, Policy, REST-API |
| Player | MPV (headless, IPC-Socket) | Audio-Engine, eigene Queue im Backend |
| Medienquelle | Jellyfin | Mediathek + Metadaten |
| Laufzeit-Config | `backend/admin_settings.json` | Über Admin-Panel gepflegt (siehe unten) |
| MQTT | aiomqtt + Mosquitto | State-Push + Command-Empfang (optional) |
| Integration | HA Custom Component | Echte `media_player`-Entität in Home Assistant |

---

## Verzeichnisstruktur

```
D:\TRAE\hmc\
├── backend/
│   ├── main.py              # FastAPI-App, Lifespan, Browse/Playback/Queue-Endpoints, MQTT-Hooks, Screen-Steuerung
│   ├── admin.py             # /admin/*: PIN, Settings, Jellyfin-Bibliotheken, OTA-Update (SSE)
│   ├── settings_store.py    # RuntimeSettingsStore → backend/admin_settings.json (Laufzeit-Quelle)
│   ├── config.py            # pydantic-settings aus backend/.env (Bootstrap + MQTT)
│   ├── jellyfin_client.py   # Jellyfin-API-Client (aiohttp), live rekonfigurierbar
│   ├── mpv_controller.py    # MPV-Prozess, IPC-Socket, State Machine, Queue
│   ├── mqtt_client.py       # MQTT State/Command/Availability
│   ├── policies.py          # get_policy(): erlaubte Libs + Max-Volume aus dem Settings-Store
│   ├── requirements.txt
│   ├── .env.example         # Vorlage (enthält noch keine MQTT-Felder → siehe README)
│   ├── .env                 # Lokal, NICHT in Git
│   └── admin_settings.json  # Lokal, NICHT in Git, wird beim ersten Start erzeugt
├── frontend/
│   ├── index.html           # SPA-Shell inkl. Player-Leiste, Queue-Overlay, Admin-Modal
│   ├── app.js               # Gesamte UI-Logik (Browse, Player, Queue, Admin, Bildschirmschoner)
│   └── styles.css           # Glassmorphism-Touch-Design
├── custom_components/hmc_media_player/   # Home-Assistant-Integration (Config Flow + MediaPlayerEntity), HACS-fähig
├── plex_hmc_player/         # Separater Plex-Player (eigenständiges Projekt, nur Grundgerüst)
├── docs/
│   ├── architecture.md      # State Machine, Komponenten-Übersicht (teilweise älter)
│   ├── admin_ota.md         # Admin-Panel & OTA (sudoers-Pfad dort veraltet → README maßgeblich)
│   ├── plex_player_spec.md  # UX-Spezifikation für den Plex-Player
│   └── homeassistant_integration.yaml  # Alte REST-Fallback-Snippets (überholt)
├── scripts/start_kiosk.sh   # Chromium-Kiosk + DPMS-Setup
├── tasks/
│   ├── todo.md              # MASSGEBLICHE Aufgabenliste (EPICs A–F)
│   └── lessons.md           # Lessons Learned – vor größeren Änderungen lesen
├── test_backend_v2.py       # Manueller Smoke-Test gegen laufenden Server (kein pytest)
├── hmc.service              # systemd-Unit (User pi, /home/pi/hmc, Port 8000)
├── install.sh               # Installations-Skript (Pi OS Bookworm)
├── setup.py                 # Interaktiver Setup-Assistent (schreibt backend/.env, inkl. MQTT-Test)
├── hacs.json                # HACS-Metadaten für die Custom Component
├── README.md                # Nutzer-Doku (Installation, Update, sudoers, Bedienung)
└── CLAUDE.md / AGENTS.md    # Diese Datei
```

---

## Konfiguration – zwei Quellen, klare Rangfolge

**`backend/admin_settings.json` ist die Laufzeit-Quelle** für alles, was im Admin-Panel steht:
`jellyfin_url`, `jellyfin_api_key`, `allowed_libraries`, `audio_device`, `max_volume`, `device_name`, `admin_pin_hash`, `ota_branch`.

- `backend/.env` dient für diese Felder **nur als Bootstrap** beim allerersten Start bzw. zum Nachziehen *fehlender* Schlüssel (`settings_store._load_or_initialize`).
- **Fallstrick:** Existiert ein Schlüssel bereits in der JSON, gewinnt immer die JSON — eine spätere Änderung in `.env` hat dann **keine Wirkung**. Das gilt auch für Altdateien aus dem ersten Admin-Panel (vor 2026-09-05), die fest `audio_device: "hw:1,0"` enthielten. Konfigurationsänderungen also über das Admin-Panel bzw. direkt in der JSON vornehmen.
- **MQTT** (`MQTT_BROKER`, `MQTT_PORT`, `MQTT_USER`, `MQTT_PASSWORD`, `MQTT_DEVICE_ID`, `MQTT_DEVICE_NAME`) kommt weiterhin **ausschließlich aus `.env`** (kein MQTT-Tab im Admin-Panel). Änderung erfordert Service-Neustart.
- Live wirksam ohne Neustart: Jellyfin-URL/Key (`JellyfinClient.reconfigure`), Bibliotheken + Max-Volume (werden pro Request gelesen), Audio-Device (`reconfigure_audio_device` → stoppt Wiedergabe, leert Queue, startet MPV neu).
- Standard-PIN beim Erstanlegen: `1234`.

```dotenv
# backend/.env
JELLYFIN_URL=http://192.168.178.X:8096
JELLYFIN_API_KEY=YOUR_API_KEY
ALLOWED_LIBRARIES=abc123,def456    # Jellyfin Library-IDs (nicht Namen!)
AUDIO_DEVICE=hw:1,0                # ALSA-Device (hw:1,0 = Behringer UCA222)

# MQTT (leer lassen = Home-Assistant-Anbindung deaktiviert)
MQTT_BROKER=192.168.178.XX
MQTT_PORT=1883
MQTT_USER=
MQTT_PASSWORD=
MQTT_DEVICE_ID=hmc_kinderzimmer    # EINDEUTIG pro Instanz! (a-z, 0-9, _)
MQTT_DEVICE_NAME=HMC Kinderzimmer
```

---

## Kern-Komponenten

### `backend/main.py` – FastAPI-App
- Modul-Ebene: `JellyfinClient()`, `MqttClient()`, `MpvController(audio_device, max_volume)` aus dem Settings-Store. Auf Windows (`sys.platform == "win32"`) wird `audio_device` auf `"mock"` gesetzt.
- Lifespan: `jellyfin.start()` → `admin.bind_runtime(jellyfin, player)` → `player.start()` (nicht im Mock) → `mqtt.start()` (nur wenn `MQTT_BROKER` gesetzt) → `_state_push_loop()`
- `_state_push_loop()`: State-Push alle 5 s; `_push_state()`: sofort nach jeder REST-/MQTT-Aktion
- `_handle_mqtt_command()`: `pause`, `resume`/`play`, `stop`, `play_pause`, `next`, `previous`, `volume:<n>` (auf Max-Volume geclampt), `seek:<s>`
- Frontend: `<meta name="google" content="notranslate">` + `translate="no"` unterdrücken Chromiums Übersetzungs-Popup; `install.sh` setzt zusätzlich die Policy `TranslateEnabled=false`. Bei CSS/JS-Änderungen den `?v=`-Cache-Buster in `index.html` erhöhen.
- Bildschirm: `/screen/off` und `/screen/on` rufen `xset dpms force off/on` (nur X11 auf dem Pi). Play/Resume schaltet den Screen automatisch an. Das Timeout selbst steuert das Frontend (`SCREEN_TIMEOUT_MS` in `app.js`).
- Policy-Prüfung (`allowed_libraries`) passiert aktuell nur in `/libraries` und `/library/{id}/artists` — Album-/Track-/Play-Endpoints prüfen nicht.

### `backend/admin.py` – Admin-API
- `POST /admin/verify-pin` → Session-Token (in-memory, ein aktives Token)
- `GET/POST /admin/settings` (Token) → `get_public()` liefert nie PIN-Hash oder API-Key, nur `jellyfin_api_key_present`
- `GET /admin/jellyfin/libraries` → alle Jellyfin-Bibliotheken live + `enabled`-Flag
- `GET /admin/ota/status`, `POST /admin/ota/update` (SSE: `git pull --rebase` → `pip install` → `sudo systemctl restart hmc`; sudoers-Regel siehe README)

### `backend/mpv_controller.py` – MPV-Controller
- MPV als externer Prozess: `--audio-device=alsa/<device> --no-video --idle=yes --keep-open=no --input-ipc-server=/tmp/hmc-mpv.sock`; stdout/stderr gehen nach `/dev/null`, MPV-Warnungen/-Fehler kommen per `request_log_messages` über den IPC-Socket und landen (API-Key maskiert) im Journal
- **State Machine:** `IDLE → LOADING → PLAYING ⇄ PAUSED → STOPPED`, `ERROR`
  - `STOPPED` wird nur durch `stop_playback()` (Stopp-Button, `/queue/clear`, MQTT `stop`, **Ende der Queue in `next_track()`**) oder `stop()` gesetzt
  - `_play_current_track()` setzt `LOADING`; erst das MPV-Event `file-loaded` setzt `PLAYING`
  - `end-file` mit `reason=error` → `ERROR`, bleibt sichtbar (wird von `idle-active` nicht überschrieben)
  - Auto-Advance: MPV-Property `eof-reached == true` → `next_track()`
- Eigene Queue: `playback_queue: List[dict]` + `current_track_index`; MPV bekommt immer nur `loadfile <url> replace`
- `stop()` beendet den Prozess; `stop_playback()` stoppt nur Wiedergabe + leert Queue
- `_monitor_process()` startet nach MPV-Absturz den aktuellen Track neu
- Mock-Mode: `if self.audio_device == "mock":` vor jedem IPC-Call

### `backend/jellyfin_client.py` – Jellyfin-Client
- `aiohttp.ClientSession` mit `X-Emby-Token`-Header; `_get()` gibt bei Fehlern still `{}` zurück (nur Log)
- Navigation: Libraries (`/Library/MediaFolders`) → Artists (`/Artists`) → Albums (`/Items`, `MusicAlbum,AudioBook`) → Tracks
- Single-File-Hörbücher (`IsFolder=False`, z. B. `.m4b`) werden als ein Track geliefert
- Stream-URL: `{url}/Audio/{id}/stream?static=true&api_key={key}` (Direct Play, kein Transcoding — `stream.mp3` lief über Jellyfins ffmpeg und brach mit HTTP 500 ab)
- Image-URL: `{url}/Items/{id}/Images/Primary?api_key={key}`
- Kein Paging (`StartIndex`/`Limit`) → bei großen Bibliotheken fehlen ggf. Einträge (EPIC C)

### `backend/mqtt_client.py` – MQTT
- `aiomqtt`, Reconnect alle 5 s, startet nur wenn `MQTT_BROKER` gesetzt ist
- **State** `hmc/{device_id}/state` (retained): `state`, `title`, `duration`, `position`, `volume_level` (0–1), `media_image_url`, `queue_size`
- **Command** `hmc/{device_id}/command`: siehe `_handle_mqtt_command`
- **Availability** `hmc/{device_id}/availability`: `online`/`offline`, als LWT gesetzt und bei jedem State-Push erneut `online`
- **Kein** HA-Discovery: Die native HA-MQTT-Integration hat kein `media_player`-Discovery-Schema (siehe `tasks/lessons.md`). Die Entität liefert die Custom Component.

### `custom_components/hmc_media_player/` – Home-Assistant-Integration
- Config Flow: pro Gerät `device_id` + Name eintragen; abonniert State/Availability, publiziert Commands
- HA-States: playing / paused / buffering (`loading`) / idle (`idle`, `stopped`, `error`)
- Features: Play, Pause, Stop, Next, Previous, Volume-Set, Seek
- Installation/Einrichtung: `custom_components/hmc_media_player/README.md`

### `plex_hmc_player/` – Plex-Variante
- Bewusst **eigenständiges** Projekt (eigene Config, eigener Client, eigenes Frontend), kein gemeinsames Media-Backend mit Jellyfin (Architekturentscheidung, siehe `tasks/lessons.md`). Stand: Grundgerüst, nicht produktiv.

---

## API-Endpoints (Jellyfin-Player)

### Browse
| Methode | Pfad | Beschreibung |
|---|---|---|
| GET | `/` | Liefert `frontend/index.html` (Assets unter `/static`) |
| GET | `/health` | Status inkl. `mqtt` (Device-ID) und `mqtt_connected` |
| GET | `/libraries` | Erlaubte Bibliotheken (Policy-gefiltert) |
| GET | `/library/{id}/artists` | Künstler einer Bibliothek (Policy-geprüft) |
| GET | `/artist/{id}/albums` | Alben eines Künstlers |
| GET | `/album/{id}/tracks` | Tracks eines Albums |

### Playback
| Methode | Pfad | Beschreibung |
|---|---|---|
| POST | `/play/album/{id}?start_track_id=` | Album abspielen (ersetzt Queue), optional ab Titel |
| POST | `/player/pause` · `/player/resume` · `/player/stop` | Pause / Fortsetzen / Stopp + Queue leeren |
| POST | `/player/next` · `/player/previous` | Nächster / vorheriger Track (previous > 3 s = Neustart) |
| POST | `/player/seek` | `{"position": float}` |
| POST/GET | `/player/volume` | `{"volume": int}`, auf Max-Volume geclampt |
| GET | `/player/state` | Kompletter Player-State inkl. Queue |
| POST | `/screen/off` · `/screen/on` | Display via DPMS |

### Queue
| Methode | Pfad | Beschreibung |
|---|---|---|
| GET | `/queue` | Aktuelle Warteschlange |
| POST | `/queue/play-now` · `/queue/play-next` · `/queue/add` | `{"track_id", "album_id"}` (album_id Pflicht) |
| DELETE | `/queue/{index}` | Track entfernen |
| POST | `/queue/jump/{index}` | Zu Index springen |
| POST | `/queue/clear` | Queue leeren + Stopp |

### Admin (Token aus `/admin/verify-pin`)
`POST /admin/verify-pin` · `GET/POST /admin/settings` · `GET /admin/jellyfin/libraries` · `GET /admin/ota/status` · `POST /admin/ota/update`

---

## Entwicklung & Ausführung

### Lokal (Windows – Mock-Mode)
```powershell
python -m venv venv
venv\Scripts\activate
pip install -r backend/requirements.txt
# backend/.env anlegen (Vorlage: backend/.env.example)
uvicorn backend.main:app --reload
# Browser: http://localhost:8000
```
- Kein echtes MPV (Mock), MQTT läuft normal. Die lokale venv nutzt aktuell Python 3.14, der Pi Python 3.11 — keine 3.12+-only-Syntax verwenden.
- Es gibt keine automatisierten Tests. `test_backend_v2.py` ist ein manueller Smoke-Test gegen einen laufenden Server; Mindest-Check: `python -m compileall -q backend custom_components plex_hmc_player`.

### Raspberry Pi (Produktion)
```bash
./install.sh
python3 setup.py           # Jellyfin, Audio, MQTT → backend/.env
sudo systemctl restart hmc
```
Update bestehender Installation: Admin-Panel → Tab „Update“ (OTA) oder manuell `git pull` + Neustart (siehe README).

---

## Hardware

| Komponente | Spezifikation |
|---|---|
| SBC | Raspberry Pi 3B+ oder 4 |
| Display | 7" Touchscreen im Querformat (800×480 bzw. 1024×600) — kompaktes Layout per `@media (max-height: 600px)` am Ende von `styles.css` |
| Audio | USB-DAC Behringer UCA222 → Cinch (`hw:1,0`) |
| OS | Raspberry Pi OS Bookworm (64-bit empfohlen) |

---

## Bewusste Design-Entscheidungen

| Entscheidung | Begründung |
|---|---|
| Admin-Panel als Laufzeit-Quelle | Eltern konfigurieren ohne SSH/`.env`-Editieren |
| Eigene HA Custom Component statt MQTT-Discovery | HA kennt kein `media_player`-Discovery |
| MQTT statt REST-Polling | Mehrere Player, echtes Push |
| aiomqtt (nicht paho) | Nativ async, passt zu FastAPI/asyncio |
| State-Push nach jeder Aktion | HA sieht Änderungen sofort |
| MPV als externer Prozess | Einfacher Restart, kein Einfluss auf Backend-State |
| Eigene Queue im Backend statt MPV-Playlist | Volle Kontrolle für UI/HA |
| Plex als separates Projekt | Keine Kopplung der Media-Backends |
| Kein Video, kein Kodi/Plex-Client | Reines Audio-Gerät, minimale Abhängigkeiten |
| Kinder-UI ohne Login, Admin hinter PIN | Touch-Only für Kinder |

---

## Arbeitsweise

- **Aufgabenliste:** `tasks/todo.md` ist maßgeblich (EPICs A–F) — erledigte Punkte dort mit Datum abhaken.
- **Lessons:** `tasks/lessons.md` vor Änderungen an HA/MQTT oder Architektur lesen; neue Erkenntnisse dort ergänzen.
- **Doku-Behauptungen gegenprüfen:** Aussagen über „funktioniert in HA“ o. ä. nur nach Test an einer echten Instanz als erledigt markieren.
- Nach Änderungen an Struktur, Config-Flüssen oder Endpoints diese Datei **und** `AGENTS.md` aktualisieren.

## Offene Schwerpunkte (Kurzfassung von `tasks/todo.md`)

- **F – HA:** End-to-End-Test der Custom Component; Automationen (Pause bei TTS, Nachtmodus-Stop) existieren noch nicht
- **A – Admin:** MQTT-Tab, Eingabevalidierung, Jellyfin-/MQTT-Test-Endpoints
- **B – UI 7":** Kompaktes Layout umgesetzt (2026-10-13); offen: Navigation/Startscreen, Test auf echtem Gerät
- **C – Jellyfin:** Paging für Artists/Albums/Tracks
- **D/E – Plex:** Evaluation und Ausbau des separaten Players

---

## Debugging

```bash
sudo journalctl -u hmc -f                                   # Service-Logs
cat ~/hmc/backend/admin_settings.json                       # Tatsächlich genutzte Laufzeit-Config
aplay -l                                                    # Verfügbare ALSA-Geräte
curl -s http://localhost:8000/player/state | python3 -m json.tool
mosquitto_sub -h <broker> -t "hmc/<device_id>/#" -v        # MQTT live
mosquitto_pub -h <broker> -t "hmc/<device_id>/command" -m "pause"
echo '{"command":["get_property","current-ao"]}' | socat - /tmp/hmc-mpv.sock   # MPV-IPC direkt
```
