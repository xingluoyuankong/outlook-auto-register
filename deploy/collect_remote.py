#!/usr/bin/env python3
import json, sys, urllib.request
from pathlib import Path
root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/home/workspace/Email-Register")
nid_path = root / "runtime_outlook/node_identity.json"
nid = json.loads(nid_path.read_text())["node_id"] if nid_path.exists() else "unknown"
out = {"node_id": nid, "collected_via": "ssh"}
try:
    with urllib.request.urlopen("http://127.0.0.1:8765/api/status", timeout=8) as r:
        out.update(json.loads(r.read().decode()))
except Exception as e:
    out["api_error"] = str(e)
rf = root / "runtime_outlook/results.jsonl"
if rf.exists():
    ok = fail = 0
    for line in rf.read_text().splitlines():
        if not line.strip():
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if d.get("success"):
            ok += 1
        else:
            fail += 1
    out["results_success_total"] = ok
    out["results_fail_total"] = fail
print(json.dumps(out, ensure_ascii=False))