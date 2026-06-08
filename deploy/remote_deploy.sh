#!/bin/bash
set -euo pipefail
SRC="/home/workspace/Email-Register"
CFG="$SRC/deploy/nodes.json"
NODE="${1:?usage: remote_deploy.sh zo2|zo3|gcore}"

eval "$(python3 - <<PY
import json
n=[x for x in json.load(open("$CFG"))["nodes"] if x["id"]=="$NODE"][0]
print(f'KEY={n.get("ssh_key","")!r}')
print(f'HOST={n["ssh_host"]!r}')
print(f'PORT={n.get("ssh_port",22)!r}')
print(f'DEST={n["project_dir"]!r}')
print(f'USER={n.get("ssh_user","root")!r}')
PY
)"

if [[ -z "$HOST" || "$HOST" == "127.0.0.1" ]]; then
  echo "skip: $NODE"
  exit 0
fi

RSYNC_SSH="ssh -p $PORT -o StrictHostKeyChecking=no"
[[ -n "$KEY" && -f "$KEY" ]] && RSYNC_SSH="ssh -i $KEY -p $PORT -o StrictHostKeyChecking=no"

echo "==> $NODE $USER@$HOST:$PORT -> $DEST"
if [[ "$USER" == "ubuntu" ]]; then
  ssh -i "$KEY" -p "$PORT" -o StrictHostKeyChecking=no "${USER}@${HOST}" "sudo mkdir -p '$DEST' && sudo chown ubuntu:ubuntu '$DEST'"
else
  ssh -i "$KEY" -p "$PORT" -o StrictHostKeyChecking=no "${USER}@${HOST}" "mkdir -p '$DEST'"
fi

rsync -az --delete \
  --exclude '.git' --exclude '__pycache__' \
  --exclude 'runtime_outlook/logs' --exclude 'runtime_outlook/results.jsonl' \
  --exclude 'runtime_outlook/fleet' --exclude '云端注册邮箱/.git' \
  -e "$RSYNC_SSH" "$SRC/" "${USER}@${HOST}:${DEST}/"

rsync -az -e "$RSYNC_SSH" \
  "$SRC/邮箱注册/mihomo_runtime/subscriptions.json" \
  "${USER}@${HOST}:${DEST}/邮箱注册/mihomo_runtime/subscriptions.json" 2>/dev/null || true

ssh -i "$KEY" -p "$PORT" -o StrictHostKeyChecking=no "${USER}@${HOST}" \
  "EMAIL_REGISTER_ROOT='$DEST' bash '$DEST/deploy/remote_install.sh' '$NODE'"

echo "==> enable supervisor (no ngrok on workers)"
ssh -i "$KEY" -p "$PORT" -o StrictHostKeyChecking=no "${USER}@${HOST}" \
  "OUTLOOK_REGISTRAR_NODE='$NODE' USE_NGROK_HUB=0 bash '$DEST/deploy/remote_enable_supervisor.sh'" 2>/dev/null || \
  ssh -i "$KEY" -p "$PORT" -o StrictHostKeyChecking=no "${USER}@${HOST}" \
  "sudo OUTLOOK_REGISTRAR_NODE='$NODE' EMAIL_REGISTER_ROOT='$DEST' bash '$DEST/deploy/remote_install_gcore.sh'" 2>/dev/null || true

echo "OK $NODE"