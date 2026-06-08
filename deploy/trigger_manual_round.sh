#!/bin/bash
# 手动一轮：刷新订阅代理 → 注册 5 个 Outlook（含 RT）→ 推送 Git
set -euo pipefail
ROOT="${EMAIL_REGISTER_ROOT:-/home/workspace/Email-Register}"
cd "$ROOT"
LOG_DIR="$ROOT/runtime_outlook/logs"
mkdir -p "$LOG_DIR" "$ROOT/runtime_outlook"
chmod -R u+rwX "$ROOT/runtime_outlook" 2>/dev/null || true
TAG="${OUTLOOK_REGISTRAR_NODE:-local}_$(date +%Y%m%d_%H%M%S)"
LOG="$LOG_DIR/manual_round_${TAG}.log"
exec > >(tee -a "$LOG") 2>&1

echo "=== manual round start $(date -Iseconds) node=${OUTLOOK_REGISTRAR_NODE:-local} ==="

DISPLAY_ID="${DISPLAY:-:98}"
export DISPLAY="$DISPLAY_ID"
export SUB_PROXY_FAST_START=1
export PYTHONUNBUFFERED=1

ensure_xvfb() {
  if xdpyinfo >/dev/null 2>&1; then return 0; fi
  lock="/tmp/.X${DISPLAY_ID#:}-lock"
  if ! pgrep -f "Xvfb $DISPLAY_ID" >/dev/null && [[ -f "$lock" ]]; then rm -f "$lock" "/tmp/.X11-unix/X${DISPLAY_ID#:}"; fi
  Xvfb "$DISPLAY_ID" -screen 0 1366x768x24 -ac -nolisten tcp &
  for _ in $(seq 1 12); do sleep 1; xdpyinfo >/dev/null 2>&1 && return 0; done
  echo "Xvfb failed"; exit 1
}
ensure_xvfb

echo ">>> subscription proxy (mihomo start + switch + test)"
python3 - <<'PY'
import os, sys, socket, time
sys.path.insert(0, "邮箱注册")
os.environ["SUB_PROXY_FAST_START"] = "1"
from subscription_proxy import get_manager, MIXED_PORT, _kill_all_mihomo

def port_ok():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect(("127.0.0.1", MIXED_PORT))
        s.close()
        return True
    except Exception:
        return False

m = get_manager()
if not m.subscriptions:
    print("ERROR: no subscriptions"); sys.exit(1)
if not port_ok():
    _kill_all_mihomo()
    time.sleep(1)
ok, msg = m.start()
print("start:", ok, msg)
if not ok:
    sys.exit(2)
for _ in range(24):
    if port_ok():
        break
    time.sleep(0.5)
m.switch_to_next_node()
time.sleep(2)
t = m.test_proxy()
print("test:", t)
if not t.get("ok"):
    sys.exit(3)
print("PROXY_OK", t.get("ip"), t.get("country"))
PY

echo ">>> register 5 outlook (RT on)"
python3 "$ROOT/outlook_launcher.py" run --count 5 --shuffle --max-proxy-attempts 12

echo ">>> sync + push github"
python3 "$ROOT/sync_credentials.py" --push

echo "=== manual round done $(date -Iseconds) log=$LOG ==="