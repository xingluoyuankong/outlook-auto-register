#!/usr/bin/env python3
"""统计某次手动轮次（默认 2026-06-07 18:56 UTC 起）各节点成功数。"""
import json, subprocess, sys
from pathlib import Path
from datetime import datetime

CUTOFF = "2026-06-07T18:55:00"
ROOT = Path("/home/workspace/Email-Register")
CFG = ROOT / "deploy/nodes.json"

def count_since(path: Path, cutoff: str):
    if not path.is_file():
        return 0, 0, []
    ok = fail = 0
    wins = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = d.get("ts") or ""
        if ts < cutoff:
            continue
        if d.get("success"):
            ok += 1
            if d.get("email"):
                wins.append(d["email"])
        else:
            fail += 1
    return ok, fail, wins

def remote_count(node):
    import json as J
    nodes = J.loads(CFG.read_text())["nodes"]
    n = next(x for x in nodes if x["id"] == node)
    if not n.get("ssh_host") or n["ssh_host"] == "127.0.0.1":
        return None
    user = n.get("ssh_user", "root")
    host = n["ssh_host"]
    port = n["ssh_port"]
    key = n["ssh_key"]
    proj = n["project_dir"]
    py = f"import json;from pathlib import Path;p=Path('{proj}/runtime_outlook/results.jsonl');c='{CUTOFF}';o=f=0;w=[]\n"
    py += "exec('''for l in p.read_text().splitlines() if p.exists() else []:\n d=json.loads(l);ts=d.get(\\\"ts\\\",\\\"\\\");\n if ts<c: continue\n (o:=o+1) if d.get(\\\"success\\\") else (f:=f+1);\n w.append(d[\\\"email\\\"]) if d.get(\\\"success\\\") and d.get(\\\"email\\\") else None''')\n"
    py += "print(json.dumps({\\\"ok\\\":o,\\\"fail\\\":f,\\\"emails\\\":w}))" 
    cmd = ["ssh", "-i", key, "-p", str(port), "-o", "ConnectTimeout=12", f"{user}@{host}", f"python3 -c {repr(py)}"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
    if r.returncode != 0:
        return {"error": (r.stderr or r.stdout)[:200]}
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception as e:
        return {"error": str(e)}

def main():
    cutoff = sys.argv[1] if len(sys.argv) > 1 else CUTOFF
    report = {"cutoff": cutoff, "nodes": {}}
    ok, fail, emails = count_since(ROOT / "runtime_outlook/results.jsonl", cutoff)
    report["nodes"]["xzxyuan"] = {"success": ok, "fail": fail, "emails": emails}
    for nid in ("zo2", "zo3", "gcore"):
        report["nodes"][nid] = remote_count(nid)
    total_ok = sum(report["nodes"][k].get("success", 0) if isinstance(report["nodes"][k], dict) else 0 for k in report["nodes"])
    report["total_success"] = total_ok
    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()