# Plex HMC Player – Architektur

## Scope
- Eigenstaendiger Plex Player mit gleichem Bedienmodell wie der Jellyfin Player.
- Bibliotheksfreigabe ueber Admin: Nur erlaubte Plex Sections sind sichtbar und abspielbar.

## Komponenten
- Backend: FastAPI, Plex API Zugriff, Policy/Whitelist fuer Sections, MPV Steuerung
- Frontend: Touch UI, keine lokale Playback-Logik, nutzt Backend als Source of Truth

## Naechste Schritte
- Admin API und Settings Store
- Browse: Sections -> Artists -> Albums -> Tracks (Paging)
- Playback: MPV Stream URL (Direct Play oder Transcode Fallback)
