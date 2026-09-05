# Plex HMC Player

Eigenstaendiger HMC Player mit Plex als Medienquelle. Das Projekt ist bewusst getrennt vom bestehenden Jellyfin Player und soll fuer Kinder und Eltern das gleiche Bedienmodell und die gleiche Funktionsparitaet liefern.

Die UX-Anforderungen und Akzeptanzkriterien sind in [plex_player_spec.md](file:///e:/TRAE/hmc/docs/plex_player_spec.md) festgehalten.

## Architektur (High Level)

```
Plex Media Server  ──▶  Backend (FastAPI)  ──▶  MPV (Audio)
                            │
                     Frontend (Touch-UI)
                            │
                   MQTT Broker (Mosquitto) (optional)
                            │
                    Home Assistant (optional)
```

## Projektstruktur

```
plex_hmc_player/
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── plex_client.py
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── index.html
│   ├── app.js
│   └── styles.css
├── docs/
│   └── architecture.md
├── scripts/
│   └── start_kiosk.sh
├── install.sh
└── setup.py
```

## Konfiguration

Die Konfiguration liegt in `plex_hmc_player/backend/.env` (Vorlage: `plex_hmc_player/backend/.env.example`).

Pflichtfelder:
- `PLEX_URL` (z.B. `http://192.168.178.X:32400`)
- `PLEX_TOKEN`
- `PLEX_ALLOWED_SECTIONS` (komma-separierte Section-IDs)

## Entwicklung (Windows / Linux)

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r plex_hmc_player/backend/requirements.txt
python plex_hmc_player/setup.py
uvicorn plex_hmc_player.backend.main:app --reload
```

## Raspberry Pi (Produktion)

```bash
cd /home/pi/hmc
cd plex_hmc_player
./install.sh
python3 setup.py
sudo systemctl restart plex-hmc
```

## Security

- `PLEX_TOKEN` wird nicht geloggt und soll im Admin-Bereich spaeter nur als "vorhanden/nicht vorhanden" angezeigt werden.
- Der Plex Player darf nur Inhalte aus `PLEX_ALLOWED_SECTIONS` anzeigen und abspielen.
