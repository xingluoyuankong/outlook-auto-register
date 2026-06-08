#!/bin/bash
# 从 xzxyuan 在四节点各触发一轮（后台）
set -euo pipefail
SRC="/home/workspace/Email-Register"
CFG="$SRC/deploy/nodes.json"

trigger_local() {
  export OUTLOOK_REGISTRAR_NODE=xzxyuan
  export EMAIL_REGISTER_ROOT="$SRC"
  nohup bash "$SRC/deploy/trigger_manual_round.sh" </dev/null &
  echo "xzxyuan: pid $!"
}

trigger_ssh() {
  local id="$1"
  python3 - <<PY
import json, subprocess
from pathlib import Path
cfg = json.loads(Path("$CFG").read_text())
n = next(x for x in cfg["nodes"] if x["id"] == "$id")
key, host, port = n["ssh_key"], n["ssh_host"], n.get("ssh_port", 22)
user = n.get("ssh_user", "root")
root = n["project_dir"]
remote = f"cd {root} && OUTLOOK_REGISTRAR_NODE={n['id']} EMAIL_REGISTER_ROOT={root} nohup bash {root}/deploy/trigger_manual_round.sh </dev/null &"
cmd = ["ssh", "-i", key, "-p", str(port), "-o", "StrictHostKeyChecking=no", f"{user}@{host}", remote]
print(" ".join(cmd))
subprocess.run(cmd, check=False)
PY
}

chmod +x "$SRC/deploy/trigger_manual_round.sh"
trigger_local
for id in zo2 zo3 gcore; do
  echo "==> trigger $id"
  trigger_ssh "$id" || true
done
echo "All triggers sent. Watch logs: runtime_outlook/logs/manual_round_*.log on each node."