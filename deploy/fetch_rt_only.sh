#!/bin/bash
# 单独获取 RT：用已注册账号走 OAuth 回调
set -euo pipefail
ROOT="${EMAIL_REGISTER_ROOT:-/home/workspace/Email-Register}"
cd "$ROOT"
export DISPLAY="${DISPLAY:-:98}"
export SUB_PROXY_FAST_START=1
export PYTHONUNBUFFERED=1

# 启动 mihomo
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
if not port_ok():
    _kill_all_mihomo()
    time.sleep(1)
m.start()
for _ in range(24):
    if port_ok():
        break
    time.sleep(0.5)
m.switch_to_next_node()
print("mihomo ready, proxy:", m.proxy_url)
PY

# 获取最新一个成功注册的账号
LAST_EMAIL=$(python3 -c "
import json
from pathlib import Path
p = Path('runtime_outlook/results.jsonl')
lines = p.read_text().splitlines()
for l in reversed(lines):
    if not l.strip(): continue
    d = json.loads(l)
    if d.get('success') and d.get('email') and not d.get('refresh_token'):
        print(d['email'] + '|' + d.get('password',''))
        break
 2>/dev/null)

if [[ -z "$LAST_EMAIL" ]]; then
  echo "ERROR: 没有已注册但缺 RT 的账号，请先跑注册"
  exit 1
fi

EMAIL=$(echo "$LAST_EMAIL" | cut -d'|' -f1)
PASS=$(echo "$LAST_EMAIL" | cut -d'|' -f2)

echo ">>> 为 $EMAIL 获取 refresh_token..."
python3 - <<'PYEOF'
import json, sys, os, time
sys.path.insert(0, "邮箱注册")
os.environ["SUB_PROXY_FAST_START"] = "1"
from subscription_proxy import get_manager

proxy = get_manager().proxy_url or ""
email = sys.argv[1] if len(sys.argv) > 1 else ""
password = sys.argv[2] if len(sys.argv) > 2 else ""

from cdp_outlook import _extract_refresh_token, CDPBrowser, CDPLaunchConfig

cfg = CDPLaunchConfig(browser_type="chrome", proxy=proxy, headless=False)
browser = CDPBrowser(cfg)
browser.start()
try:
    rt = _extract_refresh_token(browser, email, password=password, proxy_url=proxy)
    print("RT_OK:", rt[:30] if rt else "EMPTY")
finally:
    browser.stop()
PYEOF
echo "=== fetch_rt done ==="
