# Lessons Learned

## 2026-06-12
- Wenn der Benutzer eine Architekturpraeferenz nennt, sofort die Aufgabenliste daran anpassen und keine Alternativen offen lassen, die dieser Entscheidung widersprechen.
- Plex in diesem Projekt nur als eigenstaendige Entwicklung planen, nicht als automatisch geteiltes Media-Backend mit Jellyfin.

## 2026-09-05
- Home Assistants native MQTT-Integration hat noch nie eine `media_player`-Discovery-Plattform besessen (verifiziert gegen `homeassistant/components/mqtt/` im HA-Core-Repo: `sensor.py`/`switch.py`/`climate.py`/... existieren, `media_player.py` nie). Ein Publish auf `homeassistant/media_player/{id}/config` wird von HA stillschweigend ignoriert — kein Fehler, keine Entitaet, kein Log-Hinweis. Bevor irgendein MQTT-Discovery-Schema fuer eine bestimmte HA-Domaene als gegeben angenommen wird: gegen den aktuellen HA-Core-Quellcode gegenpruefen statt CLAUDE.md/aeltere Kommentare zu vertrauen.
- CLAUDE.md hatte "EPIC 6 HA Integration: ERLEDIGT" samt konkreter Automationsnamen dokumentiert, obwohl laut Nutzer nie etwas davon real eingerichtet wurde — Doku-Behauptungen zu bereits erledigten Integrationsarbeiten vor Weiterverwendung an einer echten, laufenden Instanz gegenpruefen (z.B. "taucht die Entitaet wirklich in HA auf?"), nicht als Fakt uebernehmen.
- Geloest durch eigene HA Custom Component (`custom_components/hmc_media_player/`), die das bestehende, weiterhin sinnvolle State/Command/Availability-MQTT-Protokoll konsumiert und eine echte `MediaPlayerEntity` registriert.
