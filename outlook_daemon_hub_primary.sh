#!/bin/bash
# 主节点：单机版仪表盘 + 守护 + 固定 ngrok 域名
set -u
ROOT="/home/workspace/Email-Register"
cd "$ROOT"

export OUTLOOK_DASHBOARD_PORT="${OUTLOOK_DASHBOARD_PORT:-8765}"
export PYTHONUNBUFFERED=1

# 面板
if ! ss -tlnp 2>/dev/null | grep -q ":${OUTLOOK_DASHBOARD_PORT} "; then
  python3 "$ROOT/outlook_dashboard_server.py" &
  sleep 1
fi

# ngrok
if [[ -n "${NGROK_AUTHTOKEN:-}" ]] && ! pgrep -f "ngrok http ${OUTLOOK_DASHBOARD_PORT}" >/dev/null 2>&1; then
  ngrok http "$OUTLOOK_DASHBOARD_PORT" --log=stdout --log-format=logfmt &
  sleep 3
fi

exec python3 "$ROOT/outlook_daemon.py"
