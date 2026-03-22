# CLAUDE.md – HMC v2.1 (Home Media Console)

## Projekt-Übersicht

**HMC v2.1 – Jellyfin Edition** ist ein lokales, kinderfreundliches Audio-Abspielsystem auf Raspberry-Pi-Basis.  
Zielgruppe: Kinder (4–10 Jahre) als primäre Nutzer, Eltern als Betreiber.  
Kernprinzip: **Weniger Features, maximale Stabilität. Kein Cloud-Zwang, kein Wartungsaufwand.**

---

## Architektur auf einen Blick

```
Jellyfin Server  ──▶  Backend (FastAPI)  ──▶  MPV (Audio-Engine)
                            │
                     Frontend (Touch-UI)
                            │
                   MQTT Broker (Mosquitto)
                            │
                    Home Assistant (Auto-Discovery)
```

| Schicht | Technologie | Rolle |
|---|---|---|
| Frontend | HTML/CSS/JS (SPA) | Touch-UI, reiner View-Layer |
| Backend | FastAPI + Python 3.11+ | Zentrale Logik, Policy, API |
| Player | MPV (Headless, IPC-Socket) | Audio-Engine |
| Medienquelle | Jellyfin | Mediathek + Metadaten |
| MQTT | aiomqtt + Mosquitto | State-Push + Command-Empfang |
| Integration | Home Assistant | Auto-Discovery via MQTT |

---

## Verzeichnisstruktur

```
E:\TRAE\hmc\
├── backend/
│   ├── main.py              # FastAPI App, Lifecycle, alle Endpoints + MQTT-Hooks
│   ├── config.py            # Settings via pydantic-settings + .env (inkl. MQTT)
│   ├── jellyfin_client.py   # Jellyfin API Client (aiohttp)
│   ├── mpv_controller.py    # MPV-Prozess + IPC-Socket + Queue
│   ├── mqtt_client.py       # MQTT Discovery + State-Push + Command-Empfang
│   ├── policies.py          # User-Policies (erlaubte Libs, Max-Volume)
│   ├── requirements.txt     # Python-Dependencies (inkl. aiomqtt)
│   └── .env                 # Lokale Konfiguration (NICHT in Git)
├── frontend/
│   ├── index.html           # SPA-Shell
│   ├── app.js               # Gesamte UI-Logik
│   └── styles.css           # Glassmorphism-Touch-Design
├── docs/
│   ├── architecture.md      # State Machine, Komponenten-Übersicht
│   └── homeassistant_integration.yaml  # REST-Fallback-Snippets (nicht mehr nötig)
├── scripts/
│   └── start_kiosk.sh       # Kiosk-Browser-Start (Labwc/Wayfire)
├── hmc.service              # systemd-Service-Definition
├── install.sh               # Installations-Skript (Pi OS Bookworm)
├── setup.py                 # Interaktiver Setup-Assistent
├── .env.example             # Vorlage für Konfiguration (inkl. MQTT-Felder)
├── Projekt.prd              # Product Requirements Document
├── Task.prd                 # Master Task List mit Status
└── CLAUDE.md                # Diese Datei
```

---

## Kern-Komponenten

### `backend/config.py` – Konfiguration
- Pydantic `BaseSettings`, lädt aus `backend/.env`
- Pflichtfelder: `JELLYFIN_URL`, `JELLYFIN_API_KEY`
- HMC-Felder: `HMC_USER`, `AUDIO_DEVICE`, `ALLOWED_LIBRARIES`
- MQTT-Felder: `MQTT_BROKER`, `MQTT_PORT`, `MQTT_USER`, `MQTT_PASSWORD`, `MQTT_DEVICE_ID`, `MQTT_DEVICE_NAME`
- **Windows-Detection in `main.py`:** `AUDIO_DEVICE` wird auf `"mock"` gesetzt

### `backend/mqtt_client.py` – MQTT Discovery Client
- Bibliothek: `aiomqtt` (async, reconnect-fähig)
- **Discovery-Topic:** `homeassistant/media_player/{device_id}/config` (retained) → HA liest dieses Topic beim Start und registriert automatisch einen `media_player`-Eintrag
- **State-Topic:** `hmc/{device_id}/state` (retained) → JSON mit `state`, `title`, `volume_level`, `duration`, `position`, `media_image_url`
- **Command-Topic:** `hmc/{device_id}/command` → HA sendet hier `pause`, `resume`, `stop`, `play_pause`, `next`, `previous`
- **Availability-Topic:** `hmc/{device_id}/availability` → `online`/`offline`, auch als LWT gesetzt
- Mehrere Player im Netz: jede Instanz hat eine andere `MQTT_DEVICE_ID` → separate `media_player`-Entitäten in HA
- Reconnect-Loop: bei Verbindungsverlust automatischer Neuversuch alle 5 s

### `backend/main.py` – FastAPI App
- Lifespan: `load_policies()` → `jellyfin.start()` → `player.start()` → `mqtt.start()` → `_state_push_loop()`
- `_state_push_loop()`: pusht State alle 5 s via MQTT (Heartbeat)
- `_push_state()`: sofortiger State-Push nach jeder REST-Aktion
- `_handle_mqtt_command()`: empfängt HA-Kommandos und delegiert an `player`

### `backend/jellyfin_client.py` – Jellyfin API Client
- Nutzt `aiohttp.ClientSession` mit `X-Emby-Token`-Header
- **Navigationspfad:** Libraries → Artists → Albums → Tracks
- Tracks: Erkennt Single-File-Audiobooks (`.m4b`, `IsFolder=False`) automatisch
- Stream-URLs: `{JELLYFIN_URL}/Audio/{item_id}/stream.mp3?api_key={key}`
- Image-URLs: `{JELLYFIN_URL}/Items/{item_id}/Images/Primary?api_key={key}`

### `backend/mpv_controller.py` – MPV Controller
- MPV läuft als externer Prozess mit `--input-ipc-server=/tmp/hmc-mpv.sock`
- **State Machine:** `IDLE → LOADING → PLAYING → PAUSED → STOPPED → ERROR`
- **Queue-System:** Eigene `playback_queue: List[dict]` + `current_track_index`
- Track-Autoadvance via `eof-reached`-Event aus MPV-IPC
- `stop()` killt den Prozess; `stop_playback()` stoppt nur Wiedergabe + leert Queue
- Mock-Mode: `if self.audio_device == "mock":` vor jedem IPC-Call

### `backend/policies.py` – Policy Engine
- Statisches In-Memory-Store, geladen aus `.env`
- `UserPolicy`: `allowed_libraries: List[str]`, `max_volume: int`

---

## MQTT Discovery – Wie es funktioniert

Beim Start veröffentlicht HMC einmalig ein JSON auf das Discovery-Topic. HA liest dieses Topic und registriert automatisch einen `media_player`-Eintrag ohne jede manuelle Konfiguration.

**Was HA danach kann:**
- Player-State sehen (playing / paused / stopped / idle)
- Track-Titel, Dauer, Position, Cover-Bild anzeigen
- Pause / Resume / Stop / Next / Previous aus Automationen steuern
- Lautstärke setzen (0–1.0, wird intern auf Max-Volume geclampt)
- Availability-Status (online/offline) verfolgen

**Topic-Übersicht pro Instanz:**
```
homeassistant/media_player/{device_id}/config   Discovery (retained, einmalig beim Start)
hmc/{device_id}/state                            State-JSON (retained, alle 5 s + nach Aktionen)
hmc/{device_id}/command                          Kommandos von HA (pause/resume/stop/next/previous)
hmc/{device_id}/availability                     online / offline (LWT)
```

**Mehrere Player einrichten:** Jede `backend/.env` bekommt eine andere `MQTT_DEVICE_ID`:
```
# Pi 1 (Kinderzimmer):  MQTT_DEVICE_ID=hmc_kinderzimmer
# Pi 2 (Wohnzimmer):    MQTT_DEVICE_ID=hmc_wohnzimmer
# Pi 3 (Küche):         MQTT_DEVICE_ID=hmc_kueche
```
HA zeigt dann `media_player.hmc_kinderzimmer`, `media_player.hmc_wohnzimmer`, etc.

---

## API-Endpoints (Übersicht)

### Browse
| Methode | Pfad | Beschreibung |
|---|---|---|
| GET | `/health` | System-Status (inkl. MQTT device_id) |
| GET | `/libraries` | Erlaubte Bibliotheken (Policy-gefiltert) |
| GET | `/library/{id}/artists` | Künstler einer Bibliothek |
| GET | `/artist/{id}/albums` | Alben eines Künstlers |
| GET | `/album/{id}/tracks` | Tracks eines Albums |

### Playback
| Methode | Pfad | Beschreibung |
|---|---|---|
| POST | `/play/album/{id}` | Album abspielen (ersetzt Queue) |
| POST | `/player/pause` | Pause |
| POST | `/player/resume` | Fortsetzen |
| POST | `/player/stop` | Stopp + Queue leeren |
| POST | `/player/next` | Nächster Track |
| POST | `/player/previous` | Vorheriger Track / Neustart |
| POST | `/player/seek` | Seek zu Position (`{"position": float}`) |
| POST | `/player/volume` | Lautstärke setzen (`{"volume": int}`) |
| GET | `/player/volume` | Aktuelle Lautstärke |
| GET | `/player/state` | Kompletter Player-State |

### Queue
| Methode | Pfad | Beschreibung |
|---|---|---|
| GET | `/queue` | Aktuelle Warteschlange |
| POST | `/queue/play-now` | Track sofort abspielen |
| POST | `/queue/play-next` | Track als nächstes einreihen |
| POST | `/queue/add` | Track ans Ende der Queue |
| DELETE | `/queue/{index}` | Track aus Queue entfernen |
| POST | `/queue/jump/{index}` | Zu Track-Index springen |
| POST | `/queue/clear` | Queue leeren + Stopp |

---

## Konfiguration (`.env`)

```dotenv
# Jellyfin
JELLYFIN_URL=http://192.168.178.X:8096
JELLYFIN_API_KEY=YOUR_API_KEY
ALLOWED_LIBRARIES=abc123,def456    # Jellyfin Library-IDs
AUDIO_DEVICE=hw:1,0               # ALSA-Device (hw:1,0 = Behringer UCA222)

# MQTT Discovery
MQTT_BROKER=192.168.178.XX        # IP des Mosquitto-Brokers
MQTT_PORT=1883
MQTT_USER=                        # leer wenn kein Login nötig
MQTT_PASSWORD=
MQTT_DEVICE_ID=hmc_kinderzimmer   # EINDEUTIG pro Instanz! (a-z, 0-9, _)
MQTT_DEVICE_NAME=HMC Kinderzimmer # Anzeigename in HA
```

---

## Entwicklung & Ausführung

### Lokal (Windows – Mock-Mode)
```powershell
python -m venv venv
venv\Scripts\activate
pip install -r backend/requirements.txt
# backend/.env anlegen (Vorlage: .env.example)
uvicorn backend.main:app --reload
# Browser: http://localhost:8000
```
> Auf Windows: kein echtes MPV, aber MQTT läuft normal (gut zum Testen der Discovery)

### Raspberry Pi (Produktion)
```bash
./install.sh
python3 setup.py      # Jellyfin + Audio konfigurieren
# backend/.env um MQTT-Felder ergänzen
sudo systemctl restart hmc
sudo systemctl status hmc
```

---

## Hardware

| Komponente | Spezifikation |
|---|---|
| SBC | Raspberry Pi 3B+ oder 4 |
| Display | 7" Touchscreen (offiziell oder kompatibel) |
| Audio | USB-DAC Behringer UCA222 → Cinch |
| OS | Raspberry Pi OS Bookworm (64-bit empfohlen) |

---

## Bewusste Design-Entscheidungen

| Entscheidung | Begründung |
|---|---|
| MQTT statt REST-Polling | Mehrere Player, kein Polling-Overhead, echtes Push |
| aiomqtt (nicht paho) | Nativ async, passt zum FastAPI/asyncio-Stack |
| State-Push nach jeder Aktion | HA sieht Änderungen sofort, nicht erst nach 5 s |
| `MQTT_DEVICE_ID` in `.env` | Kein Code-Änderung nötig für weitere Instanzen |
| MPV als externer Prozess | Einfacher Restart, kein Einfluss auf Backend-State |
| Kein Video, kein Kodi/Plex | HMC ist reines Audio-Gerät, minimale Abhängigkeiten |
| Keine Authentifizierung | Touch-Only für Kinder, kein Passwort-Flow möglich |
| IPC-Socket `/tmp/hmc-mpv.sock` | Standard-Pfad, wird bei Stop gelöscht |

---

## Offene Tasks

- **EPIC 5 – Frontend:**
  - `T5.3`: Aktuelles Album/Track-Anzeige (TODO – nur State-Text)
  - `T5.4`: "Keine Inhalte"-Fehlermeldung fehlt

- **EPIC 6 – HA Integration:** ✅ ERLEDIGT (MQTT Discovery)
  - Automationen in HA angelegt: `automation.hmc_pause_bei_tts`, `automation.hmc_nachtmodus_stop`

- **EPIC 7 – Stabilität:** Reboot-Tests, Log-Struktur prüfen

---

## Typische Debugging-Hilfen

```bash
# Service-Logs
sudo journalctl -u hmc -f

# MQTT Discovery prüfen (zeigt was HMC veröffentlicht hat)
mosquitto_sub -h 192.168.178.XX -t "homeassistant/media_player/hmc_kinderzimmer/config" -C 1

# MQTT State live verfolgen
mosquitto_sub -h 192.168.178.XX -t "hmc/hmc_kinderzimmer/state"

# MQTT Kommando manuell senden (zum Testen)
mosquitto_pub -h 192.168.178.XX -t "hmc/hmc_kinderzimmer/command" -m "pause"

# Backend direkt (ohne Service)
cd /home/pi/hmc && source venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --port 8000

# REST State prüfen
curl http://localhost:8000/player/state | python3 -m json.tool
```
