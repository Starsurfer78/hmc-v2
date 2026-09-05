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

Groesstenteils umgesetzt am 2026-09-05 (neues `backend/settings_store.py`, nach Vorbild von `plex_hmc_player/backend/runtime_settings.py`). MQTT-Felder bleiben bewusst ausgeklammert (kein MQTT-Tab im Admin-Panel bisher) — separate spaetere Erweiterung.

### A1. Single Source of Truth fuer Runtime-Config
- [x] Admin-Settings als primaere Quelle definiert (Fallback: `.env` nur fuer Erststart) [2026-09-05]
- [x] Migration/Bootstrap: Beim ersten Start `admin_settings.json` mit Werten aus `.env` befuellt [2026-09-05]
- `admin_settings.json` um fehlende Felder erweitert:
  - [x] Jellyfin: URL, API-Key [2026-09-05]
  - [x] Bibliotheken: allowed_libraries (IDs) [2026-09-05]
  - [x] Audio: audio_device, max_volume [2026-09-05]
  - [ ] MQTT: broker, port, user, password, device_id, device_name — bewusst nicht umgesetzt, kein MQTT-Tab vorhanden
- [x] Secrets-Handling fuer Jellyfin-API-Key definiert (nie im Klartext zurueckgegeben, nur `jellyfin_api_key_present: bool`) [2026-09-05] — MQTT-Passwort-Handling entfaellt, da MQTT nicht im Scope

### A2. Admin API erweitern
- [x] `GET /admin/settings`: sensible Felder maskiert (`jellyfin_api_key_present`, PIN-Hash nie zurueckgegeben) [2026-09-05]
- [ ] `POST /admin/settings`: Update-Validierung fuer URL-Format/Port-Range/Device-ID-Charset weiterhin offen (max_volume 0-100 Clamp existiert bereits)
- [ ] Neue Admin-Endpunkte weiterhin offen:
  - [ ] `POST /admin/jellyfin/test` (eigener Test-Button/-Endpunkt; aktuell nur indirekt ueber den Bibliotheken-Tab pruefbar)
  - [ ] `POST /admin/mqtt/test`
  - [ ] Optional: `POST /admin/apply`

### A3. Runtime-Reconfigure (ohne Neustart, soweit sinnvoll)
- [x] Jellyfin: Client bei URL/Key-Aenderung sauber neu initialisiert (Session schliessen, neu verbinden) [2026-09-05]
- [x] Policies: allowed_libraries und max_volume aus Admin Settings, live bei jedem Aufruf gelesen [2026-09-05]
- Player: max_volume/audiodevice-Aenderung:
  - [x] max_volume: sofort wirksam (Clamp in `/player/volume` liest live aus dem Store) [2026-09-05]
  - [x] audio_device: kontrollierter Player-Neustart (`reconfigure_audio_device`, stoppt Wiedergabe + leert Queue) [2026-09-05]
- [ ] MQTT: Broker/Device-ID/etc. Aenderung erfordert mqtt reconnect — entfaellt aktuell (kein MQTT-Tab)
- [ ] Health/State: `/health` um Konfig-Quelle ergaenzen — weiterhin offen (aktuell nur `mqtt_connected`)

### A4. Admin Frontend erweitern
- [x] Tab "Allgemein" um Jellyfin API-Key erweitert (maskiertes Feld, "gesetzt: ja/nein") [2026-09-05] — dedizierter Test-Button weiterhin offen
- Tab "Bibliotheken":
  - [x] Libraries werden live vom aktuell konfigurierten Jellyfin geladen (nicht mehr nur `.env`) [2026-09-05]
  - [x] IDs werden gespeichert, nicht Namen (unveraendert korrekt)
- [ ] Tab "MQTT" hinzufuegen — weiterhin offen, separate Erweiterung

---

## EPIC B – UI fuer 600x800 (Touch) optimieren

### B1. Scroll/Tap Konflikte beheben
- [x] Grid-Cards und Trackliste: Pointer-Bewegungsschwelle ergaenzt (`bindTap` in app.js) — ein Scroll-Wisch loest keinen Tap mehr aus [2026-09-05]
- [ ] Wisch-Scroll in Listen und Overlays weiter verbessern (groessere Scroll-Flaechen, weniger "dead zones") — nicht weiter untersucht

### B2. Navigation & Landing verbessern
- [ ] Startscreen immer "Bibliotheken" (kein versehentliches "reinrutschen" in eine Bibliothek)
- [ ] Breadcrumb/Title-Zeile klickbar machen (schneller Sprung nach oben / zurueck)
- [ ] Optional: "Zurueck zur Bibliothekenliste" als fixe Aktion im Header

### B3. Layout fuer 600x800
- [ ] CSS Breakpoints fuer 600x800: Kartenanzahl, Abstaende, Schriftgroessen, Footer-Hoehe
- [x] Player-Leiste: Vor/Stopp/Weiter- und Lautstaerke-Buttons auf 44px Touch-Ziel vergroessert [2026-09-05] — Progress/Seek-Bedienbarkeit nicht weiter angefasst
- [x] Header-Titel bei langen Namen: einzeilige Kuerzung mit Ellipsis statt Umbruch/Abschneiden am oberen Rand [2026-09-05]
- [ ] Queue-Overlay und Admin-Modal: scrollbare Container sauber (kein Scroll-Lock) — nicht weiter untersucht

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
