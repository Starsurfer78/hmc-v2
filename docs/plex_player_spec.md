# Plex Player – UX/Vergleichsspezifikation (PlexAmp-aehnlich)

## Ziel
Der Plex Player soll sich fuer Kinder und Eltern so bedienen lassen wie der bestehende Jellyfin Player, aber Plex als Medienquelle nutzen. Die Oberflaeche und die Kernfunktionen orientieren sich an PlexAmp, bleiben aber bewusst reduziert und kinderfreundlich.

## Harte Anforderung: Bibliotheksfreigabe
- Der Plex Player zeigt nur die Bibliotheken (Plex Sections), die im Admin Bereich explizit freigegeben sind.
- Diese Einschränkung gilt fuer:
  - Bibliotheksliste (Home/Start)
  - Suche
  - Browse (Artists/Albums/Tracks)
  - Playback/Queue (keine Playback-URLs aus nicht freigegebenen Sections akzeptieren)

## Definition: "PlexAmp-aehnlich" (MVP)
Das MVP bildet die wesentlichen PlexAmp-Konzepte ab, die fuer HMC sinnvoll sind:
- Home/Start mit 2-3 grossen Einstiegen:
  - Bibliotheken (freigegeben)
  - Zuletzt gespielt / Zuletzt hinzugefuegt (aus freigegebenen Bibliotheken)
  - Suche
- Browse bleibt wie im Jellyfin Player: Bibliothek -> Kuenstler -> Alben -> Tracks
- Now Playing + Queue Overlay wie im Jellyfin Player
- Gleiche Player-Aktionen: Play/Pause, Stop, Next/Previous, Seek, Lautstaerke

Ausdruecklich nicht im MVP (kann spaeter kommen):
- Radios/Stations (Mix Builder, Artist Radio)
- Smart Playlists, Mood/Style, Sonic Analysis
- Downloads/Offline
- User-Profile Switching innerhalb von HMC

## Screens und Verhalten

### S1: Home
Ziel: schneller Einstieg ohne versehentliches "in eine Bibliothek rutschen".
- Elemente:
  - Kachel "Bibliotheken"
  - Kachel "Zuletzt gespielt"
  - Kachel "Zuletzt hinzugefuegt"
  - Suchfeld/Kachel "Suche"
- Verhalten:
  - Scroll soll nie als Tap interpretiert werden (Touch-Threshold)
  - Wenn keine Bibliotheken freigegeben sind: klare Fehlermeldung + Admin-Hinweis

### S2: Bibliotheken
Ziel: nur freigegebene Sections anzeigen.
- Liste/Grid: Name + optional Icon/Artwork
- Tap: oeffnet S3 (Artists)

### S3: Kuenstler
Ziel: alle Artists innerhalb der gewaehlten Section; Paging muss vollstaendig sein.
- Sortierung: stabil (Name/SortTitle)
- Tap: oeffnet S4 (Alben)

### S4: Alben
Ziel: alle Alben des Kuenstlers (oder alternative View "Alle Alben" in Section, optional spaeter).
- Tap: oeffnet S5 (Trackliste)

### S5: Trackliste / Album-Detail
Ziel: Album komplett oder ab Track starten, wie Jellyfin Player.
- Actions:
  - "ALLES ABSPIELEN" (Queue ersetzen)
  - Track-Tap: Track Detail oder Kontextmenu
  - Track Kontextmenu:
    - Jetzt wiedergeben (Queue ersetzen, sofort)
    - Als Naechstes (Insert)
    - Zur Queue hinzufuegen (Append)

### S6: Now Playing + Queue
Ziel: identisches Bedienmodell wie Jellyfin Player.
- Now Playing:
  - Titel, optional Artist
  - Cover/Artwork
  - Fortschritt + Seek
- Queue Overlay:
  - aktueller Track
  - upcoming tracks, jump/remove

## Funktionsparitaet (Jellyfin -> Plex)
Diese Tabelle definiert "genauso funktioniert" als beobachtbares Verhalten.

| Bereich | Jellyfin Player | Plex Player (Soll) |
|---|---|---|
| Start | zeigt Bibliotheken | zeigt Home (Bibliotheken + zuletzt + Suche), Bibliotheken-View erreichbar |
| Bibliotheken | gefiltert ueber allowed_libraries | gefiltert ueber freigegebene Plex Sections |
| Browse | Artists/Albums/Tracks vollstaendig | Artists/Albums/Tracks vollstaendig (Paging) |
| Play Album | ersetzt Queue, startet Track 1 | ersetzt Queue, startet Track 1 |
| Play ab Track | startet ab ausgewaehltem Track | startet ab ausgewaehltem Track |
| Queue | play-now/play-next/add/remove/jump | gleiches Verhalten |
| Seek | per Progressbar, relativ zur Duration | gleiches Verhalten |
| Volume | Slider/Buttons, clamp auf max | gleiches Verhalten |
| State | playing/paused/stopped/idle/loading | gleiches State-Mapping |
| Artwork | Cover sichtbar wenn vorhanden | Cover sichtbar wenn vorhanden |

## Admin-Konfiguration (Plex Player)
Der Plex Player benoetigt eigene Admin-Felder (nicht Jellyfin wiederverwenden):
- PLEX_URL
- PLEX_TOKEN
- Freigegebene Bibliotheken: PLEX_ALLOWED_SECTIONS (Liste von Section-IDs)
- Optional: PLEX_DEVICE_NAME (Anzeige in UI/HA, falls separat)

Sicherheitsregeln:
- Token niemals im Klartext zurueckgeben (nur token_present: true/false)
- Token nicht loggen

## Datenzugriff (Technik-Notizen fuer Implementierung)
Minimal benoetigte Plex-Faehigkeiten:
- Sections listen (nur Music relevante)
- Artists/Albums/Tracks fuer eine Section browsen
- Metadata fuer Artwork-URL
- Stream-URL fuer MPV:
  - Direct Play wenn moeglich
  - Sonst Transcode Audio Endpoint als Fallback

## Akzeptanzkriterien (MVP)
- Der Nutzer kann ausschliesslich freigegebene Bibliotheken sehen und daraus abspielen.
- Das Scrollen in 600x800 fuehlt sich stabil an (kein unbeabsichtigtes Oeffnen).
- Browse zeigt alle Artists/Albums (keine stillen Limits).
- Playback/Queue verhalten sich im Alltag gleichwertig zum Jellyfin Player.
