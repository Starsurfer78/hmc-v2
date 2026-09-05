# HMC v2.1 – Home Media Console

**Home Media Console (HMC)** ist ein robustes, kindgerechtes Audio-Abspielsystem für den Raspberry Pi. Es nutzt **Jellyfin** als zentrale Medienquelle und **MPV** für die zuverlässige lokale Wiedergabe — vollständig lokal, ohne Cloud, ohne Abonnement.

Das System ist explizit als **Audio-Endgerät** für Kinder (ca. 4–10 Jahre) konzipiert:

- ✅ **Keine Cloud** (läuft komplett lokal im LAN)
- ✅ **Keine Abo-Kosten** (eigene MP3/M4B-Sammlung via Jellyfin)
- ✅ **Kindgerechte Bedienung** (Touch-Only, keine Texteingabe, keine Menüs)
- ✅ **Eltern-freundlich** (wartungsarm, "Reboot tut gut"-Prinzip)
- ✅ **Multi-Player** (mehrere Geräte im Netz, jedes über eine eigene MQTT_DEVICE_ID)

---

## 🏗 Architektur

```
Jellyfin Server  ──▶  Backend (FastAPI)  ──▶  MPV (Audio)
                            │
                     Frontend (Touch-UI)
                            │
                   MQTT Broker (Mosquitto)
                            │
              Home Assistant Custom Component
                    (custom_components/hmc_media_player)
```

| Schicht | Technologie | Aufgabe |
|---|---|---|
| Frontend | HTML / CSS / JS | Touch-UI, Kiosk-Browser |
| Backend | FastAPI + Python 3.11+ | Logik, Policy, Player-Steuerung |
| Player | MPV (Headless, IPC) | Audio-Engine |
| Medien | Jellyfin | Bibliothek + Metadaten |
| MQTT | aiomqtt + Mosquitto | State-Push, Kommando-Empfang |
| Smart Home | Home Assistant + Custom Component | `media_player`-Entität, Automationen |

---

## 🛠 Hardware

| Komponente | Empfehlung |
|---|---|
| SBC | Raspberry Pi 3B+ oder 4 |
| Display | Offizielles 7" Touchscreen oder kompatibel |
| Audio | USB-DAC Behringer UCA222 → Cinch, oder Klinke/HDMI |
| Storage | SD-Karte 16 GB+ |
| Netzwerk | LAN oder WLAN |

**Voraussetzung:** Jellyfin-Server erreichbar im LAN.

---

## 🚀 Installation

Diese Anleitung gilt für ein frisches **Raspberry Pi OS Bookworm (64-bit)**.

### 1. Repository klonen

```bash
cd /home/pi
git clone https://github.com/Starsurfer78/hmc-v2 hmc
cd hmc
```

### 2. Installer ausführen

```bash
chmod +x install.sh
./install.sh
```

Das Skript installiert alle Abhängigkeiten, richtet das Python-Venv ein, installiert den systemd-Service und bereitet den Kiosk-Modus vor.

### 3. Setup-Assistent

Am Ende der Installation startet der interaktive Setup-Assistent:
- Verbindungstest zu Jellyfin
- Auswahl der erlaubten Bibliotheken
- Audio-Device-Auswahl
- MQTT-Konfiguration mit Verbindungstest (Broker, Port, Login, Device-ID) — kann übersprungen werden, dann startet HMC ohne Home-Assistant-Anbindung

Später erneut aufrufen:
```bash
source venv/bin/activate
python3 setup.py
```

### 4. Einmalige sudo-Berechtigung für OTA

Damit das Admin-Panel den Service nach einem Update automatisch neu starten kann (`$(whoami)` trägt automatisch den richtigen Benutzernamen ein — nicht durch `pi` ersetzen, falls dein Nutzer anders heißt):
```bash
echo "$(whoami) ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart hmc" | sudo tee /etc/sudoers.d/hmc-restart
sudo chmod 440 /etc/sudoers.d/hmc-restart
sudo visudo -c
```
> Bookworm nutzt usrmerge — `systemctl` liegt unter `/usr/bin`, `/bin/systemctl` ist nur ein Symlink und wird von sudoers nicht als gleichwertig erkannt. Mit `/bin/systemctl` in der Regel fragt `sudo` trotz korrekter Datei weiter nach dem Passwort.

### 5. Neustart

```bash
sudo reboot
```

Nach dem Reboot startet HMC automatisch im Kiosk-Modus.

---

## 🔄 Update (bestehende Installation)

**Über das Admin-Panel (empfohlen):** Schild-Symbol → PIN → Tab **„Update"**. Zeigt an, ob neue Commits auf GitHub verfügbar sind, und aktualisiert per Knopfdruck (`git pull` → Python-Pakete aktualisieren → Dienst neu starten) mit Live-Log direkt in der UI. Setzt voraus, dass die sudo-Berechtigung aus Schritt 4 der Installation eingerichtet ist — sonst schlägt nur der Neustart-Schritt fehl und muss manuell nachgeholt werden (`sudo systemctl restart hmc`).

**Manuell per SSH** (z.B. wenn das Admin-Panel selbst nicht mehr erreichbar ist):
```bash
cd /home/pi/hmc
git pull --rebase
source venv/bin/activate
pip install -r backend/requirements.txt
sudo systemctl restart hmc
```

`backend/.env` und `backend/admin_settings.json` sind lokale, nicht versionierte Dateien — ein Update überschreibt weder Jellyfin-Zugangsdaten noch Bibliotheken-Freigabe, Lautstärke-Limit oder Admin-PIN.

Falls `git pull --rebase` wegen lokaler Änderungen abbricht: `git status` prüfen und die betroffene Datei sichern/verwerfen (bei einer unveränderten Installation sollte das nicht vorkommen).

---

## ⚙️ Konfiguration

Alle Einstellungen liegen in `backend/.env` (Vorlage: `.env.example`):

```dotenv
# Jellyfin
JELLYFIN_URL=http://192.168.178.X:8096
JELLYFIN_API_KEY=DEIN_API_KEY

# Bibliotheken (Jellyfin Library-IDs, kommasepariert — nicht die Namen!)
ALLOWED_LIBRARIES=abc123,def456

# Audio (ALSA-Device — hw:1,0 = Behringer UCA222)
AUDIO_DEVICE=hw:1,0

# MQTT (leer lassen = Home-Assistant-Anbindung deaktiviert)
MQTT_BROKER=192.168.178.XX
MQTT_PORT=1883
MQTT_USER=
MQTT_PASSWORD=
MQTT_DEVICE_ID=hmc_kinderzimmer      # Eindeutig pro Gerät! (a-z, 0-9, _)
MQTT_DEVICE_NAME=HMC Kinderzimmer    # Anzeigename in HA
```

> Library-IDs: Jellyfin Admin → Bibliotheken → ID aus der URL kopieren.

Weitere Einstellungen (Max-Lautstärke, Gerätename, …) sind nach dem ersten Start auch direkt über das **Admin-Panel** in der UI änderbar.

---

## 🎨 Bedienung (für Kinder)

- **Startseite**: Alle freigegebenen Bibliotheken (Hörbücher, Kinder-Musik, …)
- **Navigation**: Bibliothek → Künstler → Album → Titel
- **Wiedergabe**:
  - „ALLES ABSPIELEN" startet das gesamte Album
  - „AB HIER SPIELEN" startet ab dem gewählten Titel
  - Tap auf das Cover in der Detailansicht startet ebenfalls die Wiedergabe
- **Player-Leiste** (unten): Play/Pause, Vor/Zurück, Stopp, Lautstärke +/−, Fortschrittsbalken (Seek)
- **Warteschlange**: Track-Menü (⋮) → Als Nächstes / Hinzufügen / Jetzt abspielen

---

## 💡 Bildschirmschoner

Der Bildschirm schaltet sich automatisch ab wenn nichts abgespielt wird (Standard: 5 Minuten).

| Situation | Verhalten |
|---|---|
| Nichts läuft, 5 min kein Touch | Bildschirm schaltet ab |
| Irgendwo antippen | Bildschirm schaltet sofort wieder ein |
| Wiedergabe startet (auch aus HA) | Bildschirm schaltet automatisch ein |
| Wiedergabe stoppt/pausiert | Timer startet neu |

Der Timeout ist in `frontend/app.js` über `SCREEN_TIMEOUT_MS` einstellbar (Standard: `5 * 60 * 1000`).

---

## 🔐 Admin-Panel

Der kleine Schild-Button (🛡) rechts im Header öffnet das PIN-geschützte Admin-Panel.

**Standard-PIN beim ersten Start: `1234`** — bitte sofort ändern.

| Tab | Inhalt |
|---|---|
| Allgemein | Gerätename, Max-Lautstärke, Jellyfin-URL, Audio-Device |
| Bibliotheken | Jellyfin-Bibliotheken per Checkbox freigeben (live von Jellyfin geladen) |
| Sicherheit | Admin-PIN ändern |
| Update | Git-Status, OTA-Update mit Live-Log |

Das Admin-Panel schreibt Änderungen in `backend/admin_settings.json`.

---

## 🏠 Home Assistant Integration

HMC veröffentlicht seinen State laufend per MQTT (`hmc/{device_id}/state`,
`hmc/{device_id}/command`, `hmc/{device_id}/availability`) — das allein reicht
aber nicht für eine `media_player`-Entität: Home Assistants native
MQTT-Integration hat kein Discovery-Schema für die `media_player`-Domäne
(anders als z.B. für `sensor` oder `switch`).

Für eine echte `media_player`-Karte in HA die mitgelieferte Custom Component
installieren: **[custom_components/hmc_media_player](custom_components/hmc_media_player/README.md)**.
Kurzfassung:
1. Ordner `custom_components/hmc_media_player/` in die HA-Config kopieren (oder als HACS-Custom-Repository hinzufügen) und HA neu starten
2. **Einstellungen → Geräte & Dienste → Integration hinzufügen → „HMC Media Player"**
3. Die `MQTT_DEVICE_ID` aus `backend/.env` eintragen

**Was HA danach steuern kann:**
- Play / Pause / Stop
- Nächster / Vorheriger Track
- Lautstärke (wird auf Max-Lautstärke geclampt), Seek
- Status, Track-Titel, Cover, Position werden live angezeigt

Automationen (z.B. "bei TTS pausieren" oder "abends stoppen") lassen sich
anschließend ganz normal gegen die entstandene `media_player.<name>`-Entität
bauen.

---

## 🔧 Entwicklung (Windows / Mac)

HMC kann lokal entwickelt werden. Der Player läuft dann im Mock-Modus (kein Audio), MQTT läuft normal.

```powershell
# .env in backend/ anlegen (Vorlage: .env.example)
python -m venv venv
venv\Scripts\activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload
# Browser: http://localhost:8000
```

---

## 🔗 REST API (Übersicht)

| Methode | Pfad | Beschreibung |
|---|---|---|
| GET | `/health` | System-Status (inkl. MQTT-Verbindungsstatus) |
| GET | `/libraries` | Erlaubte Bibliotheken |
| GET | `/library/{id}/artists` | Künstler einer Bibliothek |
| GET | `/artist/{id}/albums` | Alben eines Künstlers |
| GET | `/album/{id}/tracks` | Tracks eines Albums |
| POST | `/play/album/{id}` | Album abspielen |
| POST | `/player/pause` | Pause |
| POST | `/player/resume` | Fortsetzen |
| POST | `/player/stop` | Stopp |
| POST | `/player/next` | Nächster Track |
| POST | `/player/previous` | Vorheriger Track |
| GET | `/player/state` | Aktueller State (JSON) |
| POST | `/screen/off` | Bildschirm abschalten |
| POST | `/screen/on` | Bildschirm einschalten |
| POST | `/admin/verify-pin` | PIN prüfen → Token |
| GET | `/admin/settings` | Einstellungen lesen |
| POST | `/admin/settings` | Einstellungen speichern |
| GET | `/admin/jellyfin/libraries` | Jellyfin-Bibliotheken mit Aktivierungsstatus (für Bibliotheken-Tab) |
| GET | `/admin/ota/status` | Git-Status |
| POST | `/admin/ota/update` | OTA-Update (SSE-Stream) |

---

## 🐛 Debugging

```bash
# Service-Logs live
sudo journalctl -u hmc -f

# Backend direkt starten (ohne Service)
cd /home/pi/hmc && source venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --port 8000

# MQTT State live verfolgen
mosquitto_sub -h 192.168.178.XX -t "hmc/hmc_kinderzimmer/state"

# Kommando manuell senden (pause/resume/stop/next/previous/volume:<0-100>/seek:<sek>)
mosquitto_pub -h 192.168.178.XX -t "hmc/hmc_kinderzimmer/command" -m "pause"

# MQTT-Verbindungsstatus prüfen (unabhängig vom Broker-Log)
curl -s http://localhost:8000/health

# Bildschirm manuell steuern
curl -X POST http://localhost:8000/screen/off
curl -X POST http://localhost:8000/screen/on

# MPV-Socket direkt testen
echo '{"command":["get_property","volume"]}' | socat - /tmp/hmc-mpv.sock
```

---

**Viel Spaß beim Hören! 🎧**
