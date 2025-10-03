#!/bin/bash
# install_pi.sh - Setup Chute Monitor on Raspberry Pi (Raspberry Pi OS)
# Usage: bash install_pi.sh

set -euo pipefail

APP_NAME="chute-monitor"
SERVICE_FILE="/etc/systemd/system/${APP_NAME}.service"
PROJECT_DIR="$(pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
PY_BIN="$VENV_DIR/bin/python"
PIP_BIN="$VENV_DIR/bin/pip"

echo "[1/6] Updating system packages..."
sudo apt update
sudo apt install -y python3 python3-venv python3-pip

# Ensure dialout group for USB serial (RPLidar)
echo "[2/6] Ensuring USB serial permissions (dialout group)..."
sudo usermod -a -G dialout "$USER" || true

echo "[3/6] Creating Python virtual environment..."
if [ ! -d "$VENV_DIR" ]; then
	python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

echo "[4/6] Installing Python requirements..."
if [ -f "$PROJECT_DIR/requirements.txt" ]; then
	$PIP_BIN install --upgrade pip
	$PIP_BIN install -r "$PROJECT_DIR/requirements.txt"
else
	echo "requirements.txt not found in $PROJECT_DIR" >&2
	exit 1
fi

# Create systemd service
echo "[5/6] Creating systemd service at $SERVICE_FILE ..."
SERVICE_CONTENT="[Unit]
Description=Chute Monitor Web UI
After=network.target

[Service]
Type=simple
User=%i
WorkingDirectory=$PROJECT_DIR
Environment=PATH=$VENV_DIR/bin
ExecStart=$PY_BIN $PROJECT_DIR/web_ui.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
"

echo "$SERVICE_CONTENT" | sudo tee "$SERVICE_FILE" > /dev/null

# Replace %i User with current user explicitly (some systems need a concrete user)
sudo sed -i "s/User=%i/User=$USER/" "$SERVICE_FILE"

echo "[6/6] Enabling service to start on boot..."
sudo systemctl daemon-reload
sudo systemctl enable "$APP_NAME"

cat <<EOF

Done.

Next steps:
1) Reboot your Pi to ensure group changes take effect:
   sudo reboot

After reboot, the service will auto-start. Useful commands:
- Check status:   sudo systemctl status $APP_NAME
- View logs:      sudo journalctl -u $APP_NAME -f
- Start/Stop:     sudo systemctl start|stop $APP_NAME

Web UI will be at: http://<pi-ip>:5000
EOF

