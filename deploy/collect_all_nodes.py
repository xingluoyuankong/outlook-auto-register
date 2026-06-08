#!/usr/bin/env python3
"""汇总各节点 Outlook 注册线程状态与成果（按 node_id 区分）。"""
from __future__ import annotations

import json
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CFG = Path(__file__).resolve().parent / "nodes.json"
OUT_DIR = ROOT / "runtime_outlook" / "fleet"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def load_nodes():
    data = json.loads(CFG.read_text(encoding="utf-8"))
    return [n for n in data["nodes"] if n.get("enabled", True) and n.get("ssh_host")]


def local_snapshot(node: dict) -> dict:
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from outlook_daemon_status import build_snapshot
    snap = build_snapshot()
    snap["node_id"] = node["id"]
    snap["node_label"] = node.get("label", node["id"])
    snap["collected_via"] = "local"
    return snap


def ssh_cmd(node: dict, remote_cmd: str) -> str:
    key = node.get("ssh_key") or ""
    port = node.get("ssh_port", 22)
    host = node["ssh_host"]
    user = node.get("ssh_user", "root")
    cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=20", "-p", str(port)]
    if key and Path(key).is_file():
        cmd += ["-i", key]
    cmd += [f"{user}@{host}", remote_cmd]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    return r.stdout if r.returncode == 0 else (r.stderr or r.stdout)


def ssh_collect(node: dict) -> dict:
    key = node["ssh_key"]
    host = node["ssh_host"]
    port = node["ssh_port"]
    root = node["project_dir"]
    remote = f"python3 {root}/deploy/collect_remote.py {root}"
    user = node.get("ssh_user", "root")
    cmd = [
        "ssh", "-i", key, "-p", str(port),
        "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=12",
        f"{user}@{host}", remote,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    out = (r.stdout or "").strip()
    if not out:
        return {"node_id": node["id"], "error": r.stderr[:500] or "empty", "collected_via": "ssh"}
    try:
        return json.loads(out.splitlines()[-1])
    except json.JSONDecodeError:
        return {"node_id": node["id"], "error": out[:500], "collected_via": "ssh"}


def count_success(results: list) -> tuple[int, int]:
    ok = sum(1 for r in results if r.get("success"))
    return ok, len(results) - ok


def main():
    nodes = json.loads(CFG.read_text(encoding="utf-8"))["nodes"]
    report = {"collected_at": datetime.now(timezone.utc).isoformat(), "nodes": []}

    for node in nodes:
        nid = node["id"]
        if nid == "xzxyuan":
            snap = local_snapshot(node)
        elif node.get("enabled") is False or not node.get("ssh_host"):
            snap = {"node_id": nid, "skipped": True, "note": node.get("note", "")}
        else:
            snap = ssh_collect(node)
        recent = snap.get("recent_results") or []
        ok, fail = count_success(recent)
        snap["recent_success"] = ok
        snap["recent_fail"] = fail
        snap["phase"] = snap.get("phase", "unknown")
        report["nodes"].append(snap)

    out_json = OUT_DIR / "fleet_latest.json"
    out_md = OUT_DIR / "fleet_latest.md"
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [f"# Outlook 多节点汇总\n\n采集时间: {report['collected_at']}\n"]
    for s in report["nodes"]:
        lines.append(f"## {s.get('node_label', s.get('node_id'))} (`{s.get('node_id')}`)")
        if s.get("skipped"):
            lines.append(f"- 跳过: {s.get('note')}\n")
            continue
        if s.get("error"):
            lines.append(f"- **错误**: {s['error']}\n")
            continue
        lines.append(f"- 阶段: **{s.get('phase')}** — {s.get('phase_message', '')}")
        lines.append(f"- 最近 12 条: 成功 {s.get('recent_success',0)} / 失败 {s.get('recent_fail',0)}")
        if s.get("results_success_total") is not None:
            lines.append(f"- 累计 results.jsonl: 成功 {s['results_success_total']} / 失败 {s['results_fail_total']}")
        lines.append(f"- 上次成功一批: {s.get('last_batch_finished_iso', '—')}")
        lines.append(f"- 下一轮: {s.get('next_register_at')}")
        lines.append("")
    out_md.write_text("\n".join(lines), encoding="utf-8")
    print(out_json)
    print(out_md)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()