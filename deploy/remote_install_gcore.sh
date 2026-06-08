#!/bin/bash
# Gcore: systemd + no ngrok
set -euo pipefail
ROOT="${EMAIL_REGISTER_ROOT:-/home/ubuntu/Email-Register}"
NODE_ID="${1:-gcore}"
cd "$ROOT"
chmod +x deploy/*.sh outlook_daemon_no_ngrok.sh 2>/dev/null || true
mkdir -p runtime_outlook/logs
echo "{\"node_id\":\"$NODE_ID\",\"label\":\"Gcore VPS\"}" > runtime_outlook/node_identity.json
bash deploy/remote_install.sh "$NODE_ID" || true

UNIT=/etc/systemd/system/outlook-auto-register.service
sudo tee "$UNIT" >/dev/null <<EOF
[Unit]
Description=Outlook auto register daemon
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=$ROOT
Environment=DISPLAY=:98
Environment=SUB_PROXY_FAST_START=1
Environment=PYTHONUNBUFFERED=1
Environment=OUTLOOK_DASHBOARD_PORT=8765
Environment=OUTLOOK_REGISTRAR_NODE=$NODE_ID
Environment=EMAIL_REGISTER_ROOT=$ROOT
ExecStart=/bin/bash $ROOT/outlook_daemon_no_ngrok.sh
Restart=always
RestartSec=15

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now outlook-auto-register.service
sudo systemctl status outlook-auto-register.service --no-pager | head -15