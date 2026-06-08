#!/bin/bash
# 在目标机器上执行：安装依赖、节点身份、订阅代理、mihomo、注册 Zo 服务
set -euo pipefail
NODE_ID="${1:?node_id}"
ROOT="${EMAIL_REGISTER_ROOT:-/home/workspace/Email-Register}"
cd "$ROOT"

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq >/dev/null 2>&1 || true
apt-get install -y -qq xvfb curl git python3 python3-pip python3-yaml python3-requests python3-toml 2>/dev/null || true
if ! command -v google-chrome-stable >/dev/null 2>&1 && ! command -v google-chrome >/dev/null 2>&1; then
  apt-get install -y -qq chromium 2>/dev/null || true
  (wget -q -O /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb 2>/dev/null && dpkg -i /tmp/chrome.deb 2>/dev/null && apt-get install -f -y -qq 2>/dev/null) || true
fi

pip3 install -q requests pyyaml toml 2>/dev/null || pip3 install --break-system-packages -q requests pyyaml toml 2>/dev/null || true

mkdir -p runtime_outlook/logs
chmod -R u+rwX,g+rwX runtime_outlook 2>/dev/null || true
echo "{\"node_id\":\"$NODE_ID\",\"label\":\"$NODE_ID\"}" > runtime_outlook/node_identity.json

# mihomo linux
MIHOMO_DIR="$ROOT/邮箱注册/mihomo_runtime"
mkdir -p "$MIHOMO_DIR"
if [[ ! -x "$MIHOMO_DIR/mihomo-linux" ]]; then
  ARCH=$(uname -m)
  case "$ARCH" in
    x86_64) URL="https://github.com/MetaCubeX/mihomo/releases/download/v1.19.12/mihomo-linux-amd64-v1.19.12.gz" ;;
    aarch64) URL="https://github.com/MetaCubeX/mihomo/releases/download/v1.19.12/mihomo-linux-arm64-v1.19.12.gz" ;;
    *) echo "unsupported arch $ARCH"; exit 1 ;;
  esac
  curl -fsSL "$URL" -o /tmp/mihomo.gz
  gunzip -f /tmp/mihomo.gz
  mv /tmp/mihomo "$MIHOMO_DIR/mihomo-linux"
  chmod +x "$MIHOMO_DIR/mihomo-linux"
fi

# 订阅：若本地无 subscriptions.json，保留已有；由 xzxyuan 同步时会覆盖
if [[ ! -f "$MIHOMO_DIR/subscriptions.json" ]]; then
  echo '[]' > "$MIHOMO_DIR/subscriptions.json"
fi

chmod +x "$ROOT/outlook_daemon_with_tunnel.sh" 2>/dev/null || true
chmod +x "$ROOT/deploy/remote_install.sh" 2>/dev/null || true

# 预检订阅代理
python3 - <<'PY'
import os, sys
sys.path.insert(0, "邮箱注册")
os.environ["SUB_PROXY_FAST_START"] = "1"
from subscription_proxy import get_manager
m = get_manager()
if m.subscriptions:
    ok, msg = m.start()
    print("mihomo start:", ok, msg)
else:
    print("WARN: no subscriptions.json entries — add subs on xzxyuan and re-sync")
PY

echo "remote_install done for node $NODE_ID"