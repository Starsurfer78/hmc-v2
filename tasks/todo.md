# HMC v2.1 – Aufgabenliste

## Kontext (abgeschlossen)
- [x] Projektscan durchgefuehrt und dokumentiert (2026-06-12)

---

## EPIC F – Home Assistant Integration (2026-09-05)

Hintergrund: Der bisherige MQTT-Discovery-Ansatz fuer `media_player` konnte nie
funktionieren, da Home Assistants native MQTT-Integration keine
`media_player`-Discovery-Schema besitzt. Ersetzt durch eine eigene HA Custom
Component. Details siehe `tasks/lessons.md`.

- [x] `backend/mqtt_client.py`: totes Discovery-Publish entfernt
- [x] `setup.py`: MQTT-Konfiguration inkl. Verbindungstest im Setup-Wizard ergaenzt
- [x] `custom_components/hmc_media_player/`: eigene HA-Integration (Config Flow + MediaPlayerEntity)
- [ ] Custom Component in echter HA-Instanz installieren und End-to-End testen (Play/Pause/Volume/Seek, Cover, Availability)
- [ ] Automationen `hmc_pause_bei_tts` / `hmc_nachtmodus_stop` (in CLAUDE.md erwaehnt, real nie angelegt) gegen die neue `media_player`-Entitaet bauen
- [ ] Optional: Zeroconf-Advertising in HMC + Zeroconf-Matcher in der Custom Component fuer automatische HA-Discovery ohne manuelle Geraete-ID-Eingabe

---

## EPIC A – Admin Settings: Alles ueber Admin konfigurierbar (und wirksam)

### A1. Single Source of Truth fuer Runtime-Config
- [ ] Admin-Settings als primaere Quelle definieren (Fallback: `.env` nur fuer Erststart)
- [ ] Migration/Bootstrap: Beim ersten Start `admin_settings.json` mit Werten aus `.env` befuellen
- [ ] `admin_settings.json` um fehlende Felder erweitern:
  - [ ] Jellyfin: URL, API-Key
  - [ ] Bibliotheken: allowed_libraries (IDs)
  - [ ] Audio: audio_device, max_volume
  - [ ] MQTT: broker, port, user, password, device_id, device_name
- [ ] Secrets-Handling fuer API-Key/MQTT-Passwort definieren (nicht loggen, keine Rueckgabe an Frontend ausser wo zwingend)

### A2. Admin API erweitern
- [ ] `GET /admin/settings`: Rueckgabe so anpassen, dass sensible Felder maskiert sind (z.B. api_key_present: true)
- [ ] `POST /admin/settings`: Update-Validierung (URL-Format, Port-Range, Device-ID-Charset, max_volume 0-100)
- [ ] Neue Admin-Endpunkte:
  - [ ] `POST /admin/jellyfin/test` (URL+Key testen, Rueckgabe: ok/fehler + gefundene Libraries)
  - [ ] `POST /admin/mqtt/test` (Broker erreichbar, optional Auth)
  - [ ] Optional: `POST /admin/apply` (geaenderte Settings sofort aktivieren)

### A3. Runtime-Reconfigure (ohne Neustart, soweit sinnvoll)
- [ ] Jellyfin: Client bei URL/Key-Aenderung sauber neu initialisieren (Session schliessen, neu verbinden)
- [ ] Policies: allowed_libraries und max_volume aus Admin Settings laden und bei Aenderung live anwenden
- [ ] Player: max_volume/audiodevice-Aenderung definieren:
  - [ ] max_volume: sofort wirksam (clamp + mpv volume set)
  - [ ] audio_device: erfordert Player-Restart (kontrolliert, Queue/State Verhalten definieren)
- [ ] MQTT: Broker/Device-ID/etc. Aenderung erfordert mqtt reconnect (Client stop/start)
- [ ] Health/State: `/health` um Konfig-Quelle und aktive Werte ergaenzen (ohne Secrets)

### A4. Admin Frontend erweitern
- [ ] Tab "Allgemein" um Jellyfin API-Key + Test-Button erweitern
- [ ] Tab "Bibliotheken" robust machen:
  - [ ] Libraries immer aus aktuell konfiguriertem Jellyfin live laden (nicht nur aus `.env`)
  - [ ] IDs speichern, nicht Namen
- [ ] Tab "MQTT" hinzufuegen (oder in Allgemein integrieren): Felder + Test + Save

---

## EPIC B – UI fuer 600x800 (Touch) optimieren

### B1. Scroll/Tap Konflikte beheben
- [ ] Grid-Cards: Scroll darf nicht als Click/Tap ausloesen (Pointer-Threshold / Touch-Handling)
- [ ] Wisch-Scroll in Listen und Overlays verbessern (groessere Scroll-Flaechen, weniger "dead zones")

### B2. Navigation & Landing verbessern
- [ ] Startscreen immer "Bibliotheken" (kein versehentliches "reinrutschen" in eine Bibliothek)
- [ ] Breadcrumb/Title-Zeile klickbar machen (schneller Sprung nach oben / zurueck)
- [ ] Optional: "Zurueck zur Bibliothekenliste" als fixe Aktion im Header

### B3. Layout fuer 600x800
- [ ] CSS Breakpoints fuer 600x800: Kartenanzahl, Abstaende, Schriftgroessen, Footer-Hoehe
- [ ] Player-Leiste: Touch-Targets vergroessern, Progress/Seek besser bedienbar
- [ ] Queue-Overlay und Admin-Modal: scrollbare Container sauber (kein Scroll-Lock)

---

## EPIC C – Jellyfin: Vollstaendigkeit (Kuenstler/Alben fehlen)

### C1. Paging/Limit in Jellyfin API korrekt implementieren
- [ ] `get_artists`: Paging ueber `StartIndex`/`Limit` bis alle Items geladen sind
- [ ] `get_albums`: Paging ueber `StartIndex`/`Limit` bis alle Items geladen sind
- [ ] `get_tracks`: Paging fuer Kinder-Items, Sortierung stabil halten

### C2. Filter & Query-Parameter pruefen
- [ ] Artist/Album Endpunkte: Jellyfin Parameter so setzen, dass keine Items implizit ausgefiltert werden
- [ ] Sonderfaelle: Audiobooks als Folder vs Single-File konsistent abbilden

### C3. Verifikation
- [ ] Debug-Endpunkt oder Admin-Testseite: Anzahl Artists/Albums aus Jellyfin anzeigen zum Gegencheck
- [ ] Minimaler Regression-Test fuer Paging (mit Mock-Responses)

---

## EPIC D – Plex Evaluation (Machbarkeit)

### D0. Produktanforderung
- [ ] Plex Player soll fuer Kinder und Eltern gleich funktionieren wie der bestehende Jellyfin Player
- [ ] Gleiches Bedienmodell beibehalten: Bibliotheken -> Kuenstler -> Alben -> Tracks
- [ ] Gleiche Kernfunktionen abbilden: Album starten, ab Titel starten, Queue, Pause/Resume, Next/Previous, Seek, Volume, State, Cover
- [ ] Gleiches Sicherheitsmodell erzwingen: nur freigegebene Bibliotheken sichtbar und abspielbar
- [ ] UX-Spezifikation fuer PlexAmp-aehnliches Verhalten festschreiben: `docs/plex_player_spec.md`

### D1. API-Mapping (Plex -> HMC Browse/Playback)
- [ ] Plex Basis: `PLEX_URL`, `PLEX_TOKEN` in Admin Settings
- [ ] Bibliotheken: Plex Sections (Music) listen, Auswahl im Admin
- [ ] Kinderfreigabe: nur explizit freigegebene Plex Bibliotheken/Sections im Plex Player anzeigen
- [ ] Browse: Section -> Artists -> Albums -> Tracks per Plex Library API
- [ ] Artwork: Plex image URLs (mit Token)
- [ ] Playback: MPV Stream-URL:
  - [ ] Direct Play ueber Part-URL wenn moeglich
  - [ ] Fallback: Plex Transcode-Endpoint fuer Audio (MP3/AAC) mit Token
- [ ] Queue-Kompatibilitaet sicherstellen: Plex Tracks in dasselbe funktionale Queue-Modell ueberfuehren
- [ ] Status-/Positionsmodell an Jellyfin-Verhalten angleichen, damit UI und MQTT identisch reagieren

### D2. Architektur
- [ ] Plex Player als eigenstaendige Entwicklung planen, nicht als Umbau des bestehenden Jellyfin Players
- [ ] Eigene Konfiguration, eigene Browse-/Playback-Implementierung und eigene Admin-Maske fuer Plex definieren
- [ ] Gemeinsame Wiederverwendung nur bei generischen UI-/Player-Bausteinen pruefen, nicht auf API-Ebene erzwingen
- [ ] Gleiches Frontend-Verhalten trotz separater Implementierung per gemeinsame UX-Spezifikation absichern

### D3. Risiken/Offene Punkte
- [ ] Plex Transcoding vs Direct Play (CPU/Qualitaet/Latency auf Pi)
- [ ] Auth/Token Handling (kein Logging, Admin-Masking)
- [ ] Unterschiede in Metadatenmodell (Artist/Album IDs, Sortierung, Mehrfach-Artists)
- [ ] Pruefen, ob Plex fuer Hoerbuecher/Single-File-Alben dieselbe Nutzbarkeit wie Jellyfin bietet

---

## Verifikation (Definition of Done pro EPIC)
- [ ] Admin: Aenderungen wirken ohne manuelles Editieren von `.env`
- [ ] UI: Bedienbar auf 600x800 ohne Fehlklicks beim Scrollen
- [ ] Jellyfin: Alle erwarteten Artists/Albums sichtbar (keine Limitierung durch API-Paging)
- [ ] Plex: Funktionalitaet fuer Kinder und Eltern entspricht dem Jellyfin Player im Alltag
- [ ] Plex: Browse, Queue, Player-State, Cover, Seek und Lautstaerke verhalten sich gleichwertig
- [ ] Plex: Nur freigegebene Plex Bibliotheken sind sichtbar und abspielbar

---

## EPIC E – Plex HMC Player: neues Projektgeruest

### E1. Repo-Struktur anlegen
- [ ] Neuen Projektordner anlegen (separat vom Jellyfin Player)
- [ ] Basisstruktur: `backend/`, `frontend/`, `docs/`, `scripts/`
- [ ] README mit Scope, Runbook (Dev/Prod) und Admin-Konzept
- [ ] Setup Script fuer Erstkonfiguration (PLEX_URL, PLEX_TOKEN, erlaubte Sections, Audio, MQTT)

### E2. Minimal lauffaehiges Skeleton
- [ ] `backend/main.py` mit `/health` und Static-Serving des Frontends
- [ ] `backend/config.py` via pydantic-settings + `backend/.env`
- [ ] `backend/plex_client.py` als Platzhalter fuer Plex API Calls
- [ ] `backend/requirements.txt` fuer lokale Entwicklung

### E3. Verifikation
- [ ] `python -m compileall` fuer Plex-Projekt erfolgreich
