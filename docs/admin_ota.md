## Admin Panel & OTA – Neue Komponenten

### `backend/admin.py` – Admin API
- Routen unter `/admin/...`, eingebunden via `app.include_router(admin_router)` in `main.py`
- PIN-Verifizierung: `POST /admin/verify-pin` → gibt Session-Token zurück (PBKDF2-Hash, In-Memory)
- Einstellungen: `GET/POST /admin/settings` (token-geschützt) → liest/schreibt `backend/admin_settings.json`
- OTA-Status: `GET /admin/ota/status` → git fetch + lokaler/remote Commit-Vergleich
- OTA-Update: `POST /admin/ota/update` → Server-Sent-Events-Stream: git pull → pip install → systemctl restart
- `admin_settings.json` wird beim ersten Start automatisch mit Standard-PIN `1234` angelegt

### Frontend Admin-Panel
- Kleiner Schild-Button rechts im Header (für Kinder unauffällig)
- PIN-Screen mit Ziffernblock (4 Dots, auto-submit ab 4 Stellen)
- Tab "Allgemein": Gerätename, Max-Lautstärke, Jellyfin-URL, Audio-Device
- Tab "Sicherheit": PIN ändern
- Tab "Update": Git-Status mit Commit-Info + Update-Button + Live-Log-Stream

### OTA-Voraussetzung (einmalig auf dem Pi einrichten!)
Das Backend läuft als User `pi` und muss `systemctl restart hmc` ohne Passwort aufrufen dürfen:
```bash
# Einmalig ausführen:
echo "pi ALL=(ALL) NOPASSWD: /bin/systemctl restart hmc" | sudo tee /etc/sudoers.d/hmc-restart
sudo chmod 440 /etc/sudoers.d/hmc-restart
```
Ohne diesen Schritt schlägt der letzte OTA-Schritt fehl (git pull + pip install laufen aber trotzdem durch).

