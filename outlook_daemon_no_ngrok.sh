#!/bin/bash
# 工作节点：仅本机实况面板 + 守护（不跑 ngrok，状态汇总到主节点域名）
set -u
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="${EMAIL_REGISTER_ROOT:-$SCRIPT_DIR}"
cd "$ROOT"
export OUTLOOK_DASHBOARD_PORT="${OUTLOOK_DASHBOARD_PORT:-8765}"
export PYTHONUNBUFFERED=1
python3 - <<'PY' || true
import os, sys
sys.path.insert(0, "邮箱注册")
os.environ["SUB_PROXY_FAST_START"] = "1"
from subscription_proxy import get_manager
m = get_manager()
if m.subscriptions:
    ok, msg = m.start()
    print("[daemon] mihomo:", ok, msg, flush=True)
PY
if ! ss -tlnp 2>/dev/null | grep -q ":${OUTLOOK_DASHBOARD_PORT} "; then
  python3 "$ROOT/outlook_dashboard_server.py" &
  sleep 1
fi
exec python3 "$ROOT/outlook_daemon.py"