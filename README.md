# HMC v2.1 – Jellyfin Edition

**Home Media Console (HMC)** ist ein robustes, kindgerechtes Audio-Abspielsystem für den Raspberry Pi. Es nutzt **Jellyfin** als zentrale Medienquelle und **MPV** für die zuverlässige lokale Wiedergabe.

Das System ist explizit als **Audio-Endgerät** für Kinder (ca. 4–10 Jahre) konzipiert:
- ✅ **Keine Cloud-Zwang** (läuft lokal im LAN)
- ✅ **Keine Abo-Kosten** (nutzt eigene MP3/M4B Sammlung via Jellyfin)
- ✅ **Kindgerechte Bedienung** (Touch-Only, keine Texteingabe, keine Menüs)
- ✅ **Eltern-freundlich** (Wartungsarm, "Reboot tut gut"-Prinzip)

---

## 🏗 Architektur

- **Frontend**: Touch-optimierte Web-Oberfläche (HTML/CSS/JS), läuft im Kiosk-Browser.
- **Backend**: FastAPI (Python), verwaltet Kommunikation zu Jellyfin und steuert den Player.
- **Player**: MPV (Headless), wird über IPC-Socket gesteuert.
- **Integration**: Optional via Home Assistant (Pause/Resume/TTS).

---

## 🛠 Hardware-Anforderungen

- **Raspberry Pi** (3B+ oder 4 empfohlen)
- **Touchscreen** (z.B. offizielles 7" Display)
- **SD-Karte** (16GB+)
- **Audio-Ausgabe**: Empfohlen USB-Audio-Interface (z.B. Behringer UCA222) für bessere Qualität, oder Klinke/HDMI.
- **Jellyfin Server**: Muss im Netzwerk erreichbar sein.

---

## 🚀 Installation (Schritt-für-Schritt)

Diese Anleitung geht von einem frischen **Raspberry Pi OS (Bookworm / Trixie)** aus.

### 1. System vorbereiten
Updates installieren und System-Abhängigkeiten laden:
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git python3-venv mpv chromium unclutter
```

### 2. Projekt klonen
```bash
cd /home/pi
git clone <DEIN_REPO_URL> hmc
cd hmc
```

### 3. Python Environment einrichten
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
```

### 4. Konfiguration
Erstelle eine `.env` Datei basierend auf der Vorlage:
```bash
cp .env.example .env
nano .env
```
Passe folgende Werte an:
- `JELLYFIN_URL`: URL zu deinem Jellyfin Server (z.B. `http://192.168.1.5:8096`)
- `JELLYFIN_API_KEY`: API Key (in Jellyfin Dashboard erstellen)
- `JELLYFIN_USER_ID`: User ID des Kindes (aus URL im Browser kopieren)
- `AUDIO_DEVICE`: ALSA Device Name (z.B. `hw:1,0` für USB Audio, `hw:0,0` für Onboard)

### 5. Autostart einrichten (Backend)
Damit der HMC-Server beim Booten startet:

```bash
# Service-Datei kopieren
sudo cp hmc.service /etc/systemd/system/

# Service aktivieren und starten
sudo systemctl daemon-reload
sudo systemctl enable hmc.service
sudo systemctl start hmc.service

# Status prüfen
sudo systemctl status hmc.service
```

### 6. Kiosk-Modus einrichten (Frontend)
Damit der Browser automatisch im Vollbild startet:

**Option A: Labwc (Standard in neueren Versionen)**
1. Autostart-Datei erstellen/bearbeiten:
   ```bash
   mkdir -p ~/.config/labwc
   nano ~/.config/labwc/autostart
   ```
2. Folgende Zeile einfügen:
   ```bash
   chromium --kiosk --noerrdialogs --disable-infobars --check-for-update-interval=31536000 http://localhost:8000
   ```

**Option B: Wayfire (Ältere Bookworm Versionen)**
1. Konfiguration bearbeiten:
   ```bash
   nano ~/.config/wayfire.ini
   ```
2. Am Ende einfügen:
   ```ini
   [autostart]
   chromium = chromium --kiosk --noerrdialogs --disable-infobars --check-for-update-interval=31536000 http://localhost:8000
   ```

*(Alternativ für X11/Legacy OS: LXDE Autostart anpassen)*

---

## 💻 Entwicklung (Windows/Mac)

Du kannst HMC auch auf deinem PC entwickeln. Der Player läuft dann im **Mock-Modus** (keine Audio-Ausgabe).

1. Repository klonen
2. Python venv erstellen & Requirements installieren
3. `.env` erstellen
4. Server starten:
   ```powershell
   uvicorn backend.main:app --reload
   ```
5. Browser öffnen: `http://localhost:8000`

---

## 🎵 Bedienung

- **Home**: Übersicht aller freigegebenen Bibliotheken (z.B. "Hörbücher", "Musik").
- **Navigation**: Bibliothek -> Künstler -> Album -> Titel.
- **Wiedergabe**:
  - "ALLES ABSPIELEN": Startet das ganze Album.
  - "AB HIER SPIELEN": Startet ab dem gewählten Titel.
- **Player**: Play/Pause, Weiter, Zurück (unten fixiert).

---

## 🔗 API Endpoints (für Home Assistant)

Der HMC kann via REST API gesteuert werden:

- `POST /player/pause`
- `POST /player/resume`
- `POST /player/stop`
- `GET /player/state`

---

**Viel Spaß beim Hören! 🎧**
