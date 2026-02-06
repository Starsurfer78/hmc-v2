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

## 🚀 Installation (Schnellstart)

Diese Anleitung gilt für ein frisches **Raspberry Pi OS (Bookworm / Trixie)**.

### 1. Projekt klonen
```bash
cd /home/pi
git clone <DEIN_REPO_URL> hmc
cd hmc
```

### 2. Installer starten
Das Installationsskript installiert alle Abhängigkeiten, richtet das Python-Environment ein, installiert den System-Service und bereitet den Kiosk-Modus vor.

```bash
chmod +x install.sh
./install.sh
```

### 3. Setup-Assistent
Am Ende der Installation startet automatisch der **Setup-Assistent**. Er führt dich interaktiv durch:
- Verbindungstest zu Jellyfin
- Auswahl der erlaubten Bibliotheken (per Checkbox)
- Audio-Device Auswahl

Falls du die Konfiguration später ändern willst:
```bash
source venv/bin/activate
python3 setup.py
```

### 4. Neustart
Nach dem Reboot startet der HMC automatisch im Kiosk-Modus.
```bash
sudo reboot
```

---

## 🔧 Manuelle Anpassungen (Optional)

### Kiosk-Modus (Autostart)
Das Install-Skript versucht, den Autostart für Labwc oder Wayfire einzurichten. Falls der Browser nicht startet, prüfe die Konfiguration deines Window Managers.
Das Start-Skript liegt unter: `scripts/start_kiosk.sh`

### Updates
Um Updates einzuspielen:
```bash
cd /home/pi/hmc
git pull
./install.sh  # Aktualisiert Abhängigkeiten und Service
sudo systemctl restart hmc
```

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
