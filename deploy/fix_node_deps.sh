#!/bin/bash
# zo3 / gcore：toml + 日志目录权限
set -euo pipefail
ROOT="${EMAIL_REGISTER_ROOT:-/home/workspace/Email-Register}"
cd "$ROOT"
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -qq 2>/dev/null || apt-get update -qq 2>/dev/null || true
sudo apt-get install -y -qq python3-toml python3-yaml python3-requests 2>/dev/null || \
  apt-get install -y -qq python3-toml python3-yaml python3-requests 2>/dev/null || true
pip3 install -q toml pyyaml requests 2>/dev/null || \
  pip3 install --break-system-packages -q toml pyyaml requests 2>/dev/null || true
mkdir -p "$ROOT/runtime_outlook/logs"
if [[ -d "$ROOT/runtime_outlook" ]]; then
  if command -v sudo >/dev/null && [[ "$(id -u)" -ne 0 ]]; then
    sudo chown -R "$(whoami):$(whoami)" "$ROOT/runtime_outlook" 2>/dev/null || true
  fi
  chmod -R u+rwX "$ROOT/runtime_outlook" 2>/dev/null || true
fi
python3 -c "import toml; print('toml ok')"
echo "fix_node_deps done $ROOT"