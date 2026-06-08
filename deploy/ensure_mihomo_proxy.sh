#!/bin/bash
# 启动 mihomo + 校验 28888 出口（gcore/zo3 注册前调用）
set -euo pipefail
ROOT="${EMAIL_REGISTER_ROOT:-/home/workspace/Email-Register}"
cd "$ROOT"
export SUB_PROXY_FAST_START=1
python3 - <<'PY'
import os, sys, socket, subprocess, time
sys.path.insert(0, "邮箱注册")
os.environ["SUB_PROXY_FAST_START"] = "1"
from subscription_proxy import get_manager, MIXED_PORT, _kill_all_mihomo

def port_open():
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
    print("ERROR: subscriptions.json empty"); sys.exit(1)
if not port_open():
    print("WARN: 28888 not listening, restarting mihomo")
    _kill_all_mihomo()
    time.sleep(1)
ok, msg = m.start()
print("start:", ok, msg)
if not ok:
    sys.exit(2)
for _ in range(20):
    if port_open():
        break
    time.sleep(0.5)
else:
    print("ERROR: 28888 still down"); sys.exit(4)
ok2, msg2 = m.switch_to_next_node()
print("switch:", ok2, msg2)
t = m.test_proxy()
print("test:", t)
if not t.get("ok"):
    sys.exit(3)
print("PROXY_OK", t.get("ip"), t.get("country"))
PY