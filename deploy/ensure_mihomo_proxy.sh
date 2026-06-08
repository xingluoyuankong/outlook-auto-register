#!/bin/bash
# 启动 mihomo + 校验 28888 出口；订阅失效时自动注册代理服务新账号并刷新订阅
set -euo pipefail
ROOT="${EMAIL_REGISTER_ROOT:-/home/workspace/Email-Register}"
cd "$ROOT"
export SUB_PROXY_FAST_START="${SUB_PROXY_FAST_START:-1}"
set +e
python3 - <<'PY'
import os, sys, socket, subprocess, time
sys.path.insert(0, "邮箱注册")
os.environ["SUB_PROXY_FAST_START"] = os.environ.get("SUB_PROXY_FAST_START", "1")
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

def start_and_test():
    m = get_manager()
    if not m.subscriptions:
        print("WARN: subscriptions.json empty")
        return False
    if not port_open():
        print("WARN: 28888 not listening, restarting mihomo")
        _kill_all_mihomo()
        time.sleep(1)
    ok, msg = m.start()
    print("start:", ok, msg)
    if not ok:
        return False
    for _ in range(20):
        if port_open():
            break
        time.sleep(0.5)
    else:
        print("ERROR: 28888 still down")
        return False
    ok2, msg2 = m.switch_to_next_node()
    print("switch:", ok2, msg2)
    t = m.test_proxy()
    print("test:", t)
    return bool(t.get("ok"))

if start_and_test():
    print("PROXY_OK")
    raise SystemExit(0)
print("WARN: existing subscription unavailable; auto-registering a fresh proxy subscription")
raise SystemExit(7)
PY
code=$?
set -e
if [[ "$code" == "7" ]]; then
  SUB_PROXY_FAST_START=0 python3 邮箱注册/auto_proxy_subscription.py --force
  SUB_PROXY_FAST_START=0 python3 - <<'PY'
import os, sys
sys.path.insert(0, "邮箱注册")
from subscription_proxy import get_manager
m = get_manager()
ok, msg = m.start()
print("start_after_refresh:", ok, msg)
t = m.test_proxy()
print("test_after_refresh:", t)
raise SystemExit(0 if ok and t.get("ok") else 3)
PY
else
  exit "$code"
fi