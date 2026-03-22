#!/bin/bash
# HMC v2.1 – Kiosk Starter
# Startet Chromium im Kiosk-Modus und konfiguriert Bildschirmschoner via DPMS.

exec > >(tee -a /tmp/hmc_kiosk.log) 2>&1
echo "🚀 Kiosk Script started at $(date)"

URL="http://localhost:8000"

# DISPLAY setzen falls nicht gesetzt (passiert bei manchen Autostart-Methoden)
if [ -z "$DISPLAY" ]; then
    export DISPLAY=:0
    echo "⚠️  DISPLAY war nicht gesetzt, setze auf :0"
fi

# Mauszeiger verstecken
unclutter -idle 0.5 -root &

# --- Bildschirmschoner via DPMS ---
# DPMS aktivieren damit xset dpms force off/on funktioniert.
# Der HMC-Backend steuert das Abschalten/Einschalten über POST /screen/off und /screen/on.
# xset s off        = X11-eigenen Screensaver deaktivieren (kein Blanking durch X)
# xset +dpms        = DPMS-Signale aktivieren (nötig für force off/on)
# xset dpms 0 0 0   = Automatisches Abschalten durch X deaktivieren (HMC macht das selbst)
xset s off 2>/dev/null || true
xset +dpms 2>/dev/null || true
xset dpms 0 0 0 2>/dev/null || true

# Warten bis HMC-Backend läuft
echo "Warte auf HMC Backend..."
until curl -s "$URL/health" > /dev/null 2>&1; do
    sleep 1
done
echo "✅ Backend bereit"

# Chromium-Binary bestimmen
if command -v chromium-browser &> /dev/null; then
    BROWSER="chromium-browser"
elif command -v chromium &> /dev/null; then
    BROWSER="chromium"
else
    echo "❌ Fehler: Chromium nicht gefunden!"
    exit 1
fi

echo "Starte $BROWSER..."

$BROWSER \
    --app="$URL" \
    --kiosk \
    --start-fullscreen \
    --no-sandbox \
    --no-first-run \
    --noerrdialogs \
    --disable-infobars \
    --disable-pinch \
    --disable-translate \
    --disable-features=Translate,TranslateUI,LanguageDetection,LanguageSettings \
    --disable-notifications \
    --check-for-update-interval=31536000 \
    --lang=de \
    --accept-lang=de-DE,de \
    --password-store=basic \
    --disable-restore-session-state \
    --enable-features=OverlayScrollbar \
    --overscroll-history-navigation=0 \
    --fast \
    --fast-start
