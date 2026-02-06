#!/bin/bash

# HMC v2.1 Kiosk Starter
# Waits for backend and starts Chromium in Kiosk mode

# Log output for debugging
exec > >(tee -a /tmp/hmc_kiosk.log) 2>&1
echo "🚀 Kiosk Script started at $(date)"

URL="http://localhost:8000"

# Set DISPLAY explicitly if missing (common in some autostart methods)
if [ -z "$DISPLAY" ]; then
    export DISPLAY=:0
    echo "⚠️  DISPLAY was not set, setting to :0"
fi

# Hide mouse cursor
unclutter -idle 0.1 -root &

# Disable screen blanking (basic X11/Wayland attempt)
xset s off -dpms 2>/dev/null || true

# Wait for Backend
echo "Waiting for HMC Backend..."
until curl -s $URL/player/state > /dev/null; do
    sleep 1
done

# Start Chromium
# --kiosk: Fullscreen, no borders
# --noerrdialogs: No crash popups
# --disable-infobars: No "Chrome is being controlled..."
# --check-for-update-interval=31536000: No update checks
# --overscroll-history-navigation=0: Disable swipe back
# --disable-pinch: Disable pinch zoom

# Detect Chromium Executable (Bookworm/Trixie/RPi-OS differentiation)
if command -v chromium-browser &> /dev/null; then
    BROWSER="chromium-browser"
elif command -v chromium &> /dev/null; then
    BROWSER="chromium"
else
    echo "❌ Error: Chromium not found!"
    exit 1
fi

$BROWSER \
    --kiosk \
    --noerrdialogs \
    --disable-infobars \
    --check-for-update-interval=31536000 \
    --overscroll-history-navigation=0 \
    --disable-pinch \
    --disable-features=Translate \
    --password-store=basic \
    --no-first-run \
    --fast \
    --fast-start \
    --disable-restore-session-state \
    --app=$URL
