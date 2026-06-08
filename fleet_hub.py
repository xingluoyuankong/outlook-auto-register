#!/usr/bin/env python3
"""舰队汇总（仅主节点 ngrok 域名展示）。"""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CFG = ROOT / "deploy" / "nodes.json"
NGROK_PUBLIC = "https://scientist-primary-pregnancy.ngrok-free.dev"

_cache: dict = {"at": 0.0, "data": None}
TTL = 25


def load_fleet_report() -> dict:
    now = time.time()
    if _cache["data"] and now - _cache["at"] < TTL:
        return _cache["data"]
    script = ROOT / "deploy" / "collect_all_nodes.py"
    r = subprocess.run(
        ["python3", str(script)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    out = (r.stdout or "").strip()
    if not out:
        return {"error": r.stderr[:500], "nodes": []}
    # last JSON object in stdout
    start = out.rfind('{\n  "collected_at"')
    if start < 0:
        start = out.rfind("{")
    try:
        data = json.loads(out[start:])
    except json.JSONDecodeError:
        data = {"error": "parse failed", "raw": out[-800:]}
    cfg_nodes = {n["id"]: n for n in json.loads(CFG.read_text(encoding="utf-8")).get("nodes", [])}
    for s in data.get("nodes") or []:
        nid = s.get("node_id")
        if nid and nid in cfg_nodes:
            c = cfg_nodes[nid]
            s.setdefault("node_label", c.get("label", nid))
            s.setdefault("handle", c.get("handle", nid))
    data["ngrok_hub_url"] = NGROK_PUBLIC
    try:
        hub = json.loads(CFG.read_text(encoding="utf-8")).get("ngrok_hub", {})
        data["ngrok_hub"] = hub
    except Exception:
        pass
    _cache["at"] = now
    _cache["data"] = data
    return data


def build_home_fleet_sections(report: dict) -> tuple[str, str]:
    nodes = report.get("nodes") or []
    cards = []
    merged: list[dict] = []
    for n in nodes:
        handle = n.get("handle") or n.get("node_id", "?")
        label = n.get("node_label") or handle
        if n.get("skipped"):
            cards.append(f'<div class="card" style="margin-top:0.75rem"><b>{label}</b> 跳过</div>')
            continue
        if n.get("error"):
            cards.append(f'<div class="card" style="margin-top:0.75rem"><b>{label}</b> <span class="bad">{str(n.get("error"))[:80]}</span></div>')
            continue
        phase = n.get("phase", "?")
        ok = n.get("results_success_total", "—")
        fail = n.get("results_fail_total", "—")
        cards.append(
            f'<div class="card" style="margin-top:0.75rem;padding:0.75rem 1rem">'
            f'<b>{label}</b> <small style="color:#8b9cb3">({handle})</small><br>'
            f'阶段 {phase} · 累计 <span class="ok">{ok}</span> 成功 / <span class="bad">{fail}</span> 失败</div>'
        )
        for r in n.get("recent_results") or []:
            merged.append({**r, "_node": handle})
    summary_html = '<div class="card"><h2>全舰队节点状态</h2>' + "".join(cards) + "</div>" if cards else ""
    merged.sort(key=lambda x: x.get("ts") or "", reverse=True)
    merged = merged[:40]
    if not merged:
        table = "<p style='color:#8b9cb3'>暂无各节点成果</p>"
    else:
        lines = ["<table><tr><th>节点</th><th>时间</th><th>结果</th><th>邮箱</th><th>说明</th></tr>"]
        for r in merged:
            ok = r.get("success")
            cls = "ok" if ok else "bad"
            lines.append(
                f"<tr><td><b>{r.get('_node')}</b></td><td>{(r.get('ts') or '')[:19]}</td>"
                f"<td class='{cls}'>{'成功' if ok else '失败'}</td><td>{(r.get('email') or '—')[:40]}</td>"
                f"<td>{(r.get('error') or '')[:50]}</td></tr>"
            )
        lines.append("</table>")
        table = "\n".join(lines)
    return summary_html, table


def render_fleet_html(report: dict) -> str:
    nodes = report.get("nodes") or []
    rows = []
    for n in nodes:
        nid = n.get("node_id", "?")
        label = n.get("node_label", nid)
        if n.get("skipped"):
            rows.append(f"<tr><td>{label}</td><td colspan='4' class='muted'>跳过: {n.get('note','')}</td></tr>")
            continue
        if n.get("error"):
            rows.append(f"<tr><td>{label}</td><td colspan='4' class='bad'>{n.get('error','')[:120]}</td></tr>")
            continue
        phase = n.get("phase", "?")
        ok = n.get("results_success_total", n.get("recent_success", "—"))
        fail = n.get("results_fail_total", n.get("recent_fail", "—"))
        nxt = n.get("next_register_at")
        nxt_s = time.strftime("%m-%d %H:%M", time.localtime(nxt)) if nxt else "—"
        rows.append(
            f"<tr><td><b>{label}</b><br><small>{nid}</small></td>"
            f"<td>{phase}</td><td class='ok'>{ok}</td><td class='bad'>{fail}</td><td>{nxt_s}</td></tr>"
        )
    body = "\n".join(rows)
    hub = report.get("ngrok_hub_url", NGROK_PUBLIC)
    collected = report.get("collected_at", "—")
    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"/>
<meta http-equiv="refresh" content="15"/>
<title>Outlook 舰队 · 统一 ngrok</title>
<style>
body{{font-family:system-ui;background:#0f1419;color:#e7ecf3;padding:1.2rem}}
a{{color:#6cb6ff}} table{{width:100%;border-collapse:collapse;margin-top:1rem}}
th,td{{border-bottom:1px solid #2a3548;padding:.5rem;text-align:left;font-size:.9rem}}
th{{color:#8b9cb3}} .ok{{color:#3dd68c}} .bad{{color:#f07178}} .muted{{color:#8b9cb3}}
.card{{background:#1a2332;padding:1rem;border-radius:12px;border:1px solid #2a3548}}
</style></head><body>
<h1>🌐 Outlook 舰队总览</h1>
<p>主隧道（固定）: <a href="{hub}">{hub}</a><br>
本页路径: <code>/fleet</code> · 采集: {collected} · 各节点仅内网 8765，经主节点 SSH 汇总</p>
<div class="card">
<p><a href="/">← 本机 xzxyuan 实况</a></p>
<table><tr><th>节点</th><th>阶段</th><th>累计成功</th><th>累计失败</th><th>下一轮</th></tr>
{body}
</table></div>
<p style="color:#8b9cb3;font-size:.85rem">工作节点不单独暴露 ngrok；隧道端点可变，公网入口仅此主域名。</p>
</body></html>"""