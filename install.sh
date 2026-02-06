#!/bin/bash

# HMC v2.1 Install Script
# Run as user (usually 'pi')

set -e

echo "🔧 HMC v2.1 Installer"
echo "======================"

# 1. System Dependencies
echo "📦 Installing system dependencies..."
sudo apt-get update

# Detect OS Version
if [ -f /etc/os-release ]; then
    . /etc/os-release
    echo "   OS Detected: $PRETTY_NAME ($VERSION_CODENAME)"
fi

# Detect correct Chromium package (Bookworm/Trixie/RPi-OS differentiation)
# We check if chromium-browser has an installation candidate.
if apt-cache policy chromium-browser | grep "Candidate:" | grep -v "(none)" > /dev/null 2>&1; then
    CHROMIUM_PKG="chromium-browser"
else
    CHROMIUM_PKG="chromium"
fi
echo "   Detected Browser Package: $CHROMIUM_PKG"

sudo apt-get install -y python3-venv python3-pip mpv $CHROMIUM_PKG unclutter libasound2-dev

# 2. Python Environment
echo "🐍 Setting up Python environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "   Virtualenv created."
fi

source venv/bin/activate
pip install --upgrade pip
if [ -f "backend/requirements.txt" ]; then
    pip install -r backend/requirements.txt
else
    echo "⚠️  backend/requirements.txt not found!"
fi

# 3. Service Installation
echo "⚙️  Installing systemd service..."

# Adjust paths in service file to current directory
CURRENT_DIR=$(pwd)
USER_NAME=$(whoami)

# Create a temporary service file with correct paths
sed -e "s|/home/pi/hmc|$CURRENT_DIR|g" \
    -e "s|User=pi|User=$USER_NAME|g" \
    hmc.service > hmc.service.tmp

sudo mv hmc.service.tmp /etc/systemd/system/hmc.service
sudo systemctl daemon-reload
sudo systemctl enable hmc.service

echo "   Service enabled. Start with: sudo systemctl start hmc"

# 4. Kiosk Setup
echo "🖥️  Setting up Kiosk scripts..."
chmod +x scripts/start_kiosk.sh

# Detect Display Server (simple check)
if [ -d "$HOME/.config/wayfire.ini" ]; then
    echo "   Wayfire (Bookworm) detected."
    echo "   ⚠️  Manual Step: Add the following to ~/.config/wayfire.ini under [autostart]:"
    echo "   hmc = $CURRENT_DIR/scripts/start_kiosk.sh"
elif [ -d "$HOME/.config/lxsession/LXDE-pi" ]; then
    echo "   LXDE (X11) detected."
    echo "   ⚠️  Manual Step: Add '@$CURRENT_DIR/scripts/start_kiosk.sh' to ~/.config/lxsession/LXDE-pi/autostart"
else
    echo "   ⚠️  Could not detect specific autostart method. Please add '$CURRENT_DIR/scripts/start_kiosk.sh' to your window manager's startup."
fi

# 5. Configuration
echo "📝 Configuration..."
if [ ! -f "backend/.env" ]; then
    echo "   No configuration found. Starting Setup Wizard..."
    python3 setup.py
else
    echo "   Existing configuration found in backend/.env"
    read -p "   Run setup wizard anyway? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        python3 setup.py
    fi
fi

echo ""
echo "✅ Installation complete!"
echo "   1. Start service: sudo systemctl start hmc"
echo "   2. Reboot to test kiosk mode"
