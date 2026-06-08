#!/usr/bin/env python3
"""单机版 Outlook 注册仪表盘 — 本机状态 + 5 个手动按钮（无 SSH 依赖）。"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from outlook_daemon_status import build_snapshot, save_status

PORT = int(os.environ.get("OUTLOOK_DASHBOARD_PORT", "8765"))
ROOT = Path(__file__).resolve().parent

# ─── 按钮动作（全部在本机执行） ─────────────────────────────

def _run(cmd: list[str], timeout: int = 120) -> tuple[int, str, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(ROOT))
        return r.returncode, r.stdout[-3000:], r.stderr[-1000:]
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"
    except Exception as e:
        return -1, "", str(e)[:300]


def action_refresh_proxy() -> dict:
    """启动/刷新 mihomo 订阅代理 + 轮询节点"""
    save_status({"phase": "proxy_refresh", "phase_message": "正在刷新订阅代理..."})
    code, out, err = _run(["bash", str(ROOT / "deploy" / "ensure_mihomo_proxy.sh")], timeout=90)
    ok = code == 0 and "PROXY_OK" in out
    # 提取出口 IP
    ip = ""
    for line in out.splitlines():
        if "PROXY_OK" in line:
            parts = line.split()
            if len(parts) >= 2:
                ip = parts[1]
    msg = f"代理刷新{'成功' if ok else '失败'}"
    if ip:
        msg += f" → 出口 {ip}"
    save_status({"phase": "idle", "phase_message": msg})
    return {"ok": ok, "msg": msg, "output": out[-800:]}


def action_register_5() -> dict:
    """注册 5 个 Outlook（含 RT）"""
    save_status({"phase": "registering", "phase_message": "正在注册 5 个 Outlook 账号..."})
    code, out, err = _run(
        [sys.executable, "outlook_launcher.py", "run", "--count", "5", "--shuffle", "--max-proxy-attempts", "12"],
        timeout=600,
    )
    # 解析结果
    ok_count = out.count("成功:")
    fail_count = 5 - ok_count
    save_status({
        "phase": "idle",
        "phase_message": f"注册完成：{ok_count} 成功 / {fail_count} 失败",
        "last_register_ok": ok_count,
        "last_register_fail": fail_count,
    })
    return {"ok": code == 0, "success": ok_count, "fail": fail_count, "output": out[-1200:]}


def action_fetch_rt() -> dict:
    """为最近注册成功的账号获取 RT"""
    save_status({"phase": "rt_fetch", "phase_message": "正在获取 refresh_token..."})
    code, out, err = _run(
        [sys.executable, "-c", """
import json, sys, os
sys.path.insert(0, "邮箱注册")
os.environ["SUB_PROXY_FAST_START"]="1"
from subscription_proxy import get_manager
proxy = get_manager().proxy_url or ""
from pathlib import Path
p = Path("runtime_outlook/results.jsonl")
target = None
for l in reversed(p.read_text().splitlines()):
    if not l.strip(): continue
    d = json.loads(l)
    if d.get("success") and d.get("email") and not d.get("refresh_token"):
        target = d; break
if not target:
    print("ERROR: 没有已注册但缺 RT 的账号"); sys.exit(1)
from cdp_outlook import _extract_refresh_token, CDPBrowser, CDPLaunchConfig
cfg = CDPLaunchConfig(browser_type="chrome", proxy=proxy, headless=False)
b = CDPBrowser(cfg); b.start()
try:
    rt = _extract_refresh_token(b, target["email"], password=target.get("password",""), proxy_url=proxy)
    if rt:
        # 回写 results.jsonl
        lines = p.read_text().splitlines()
        for i in range(len(lines)-1, -1, -1):
            d2 = json.loads(lines[i])
            if d2.get("email") == target["email"] and not d2.get("refresh_token"):
                d2["refresh_token"] = rt
                lines[i] = json.dumps(d2, ensure_ascii=False)
                break
        p.write_text("\\n".join(lines))
        print(f"RT_OK: {rt[:30]}... email={target['email']}")
    else:
        print("RT_EMPTY")
finally:
    b.stop()
"""],
        timeout=180,
    )
    ok = code == 0 and "RT_OK" in out
    save_status({"phase": "idle", "phase_message": f"RT 获取{'成功' if ok else '失败'}"})
    return {"ok": ok, "msg": f"RT {'成功' if ok else '失败'}", "output": out[-500:]}


def action_push_github() -> dict:
    """同步凭证 + 推送到 cloud-register-email"""
    save_status({"phase": "syncing", "phase_message": "正在同步凭证到 GitHub..."})
    code, out, err = _run([sys.executable, "sync_credentials.py", "--push"], timeout=300)
    save_status({"phase": "idle", "phase_message": f"凭证推送{'成功' if code == 0 else '失败'}"})
    return {"ok": code == 0, "msg": f"推送{'成功' if code == 0 else '失败'}", "output": out[-500:]}


def action_full_pipeline() -> dict:
    """完整流程：代理 → 注册 → RT → 推送"""
    save_status({"phase": "full_pipeline", "phase_message": "完整流程开始..."})
    results = []

    # 1. 代理
    save_status({"phase": "full_pipeline", "phase_message": "步骤 1/4：刷新代理..."})
    r1 = action_refresh_proxy()
    results.append(("代理刷新", r1["ok"]))

    # 2. 注册
    save_status({"phase": "full_pipeline", "phase_message": "步骤 2/4：注册 5 个 Outlook..."})
    r2 = action_register_5()
    results.append(("注册5个", r2["success"]))

    # 3. RT
    if r2["success"] > 0:
        save_status({"phase": "full_pipeline", "phase_message": "步骤 3/4：获取 refresh_token..."})
        r3 = action_fetch_rt()
        results.append(("获取RT", r3["ok"]))
    else:
        results.append(("获取RT", "跳过（无成功注册）"))

    # 4. 推送
    save_status({"phase": "full_pipeline", "phase_message": "步骤 4/4：推送 GitHub..."})
    r4 = action_push_github()
    results.append(("推送GitHub", r4["ok"]))

    summary = " → ".join(f"{k}:{'✅' if v else '❌'}" for k, v in results)
    save_status({"phase": "idle", "phase_message": f"完整流程完成: {summary}"})
    return {"ok": all(v for _, v in results if isinstance(v, bool)), "steps": results}


ACTIONS = {
    "refresh_proxy": action_refresh_proxy,
    "register_5": action_register_5,
    "fetch_rt": action_fetch_rt,
    "push_github": action_push_github,
    "full_pipeline": action_full_pipeline,
}

# ─── HTML ────────────────────────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<meta http-equiv="refresh" content="10"/>
<title>Outlook 自动注册 · xzxyuan</title>
<style>
:root{--bg:#0f1419;--card:#1a2332;--text:#e7ecf3;--muted:#8b9cb3;--ok:#3dd68c;--bad:#f07178;--accent:#6cb6ff;--btn:#2563eb;--btn-hover:#1d4ed8}
*{box-sizing:border-box}
body{font-family:system-ui,-apple-system,sans-serif;background:var(--bg);color:var(--text);margin:0;padding:1rem;line-height:1.5}
h1{font-size:1.4rem;margin:.2rem 0 .4rem}
.sub{color:var(--muted);font-size:.88rem;margin-bottom:1rem}
.grid{display:grid;gap:.8rem;grid-template-columns:repeat(auto-fit,minmax(300px,1fr))}
.card{background:var(--card);border-radius:14px;padding:1rem 1.15rem;border:1px solid #2a3548}
.card h2{font-size:.78rem;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:0 0 .6rem}
.pill{display:inline-block;padding:.15rem .5rem;border-radius:999px;font-size:.78rem;font-weight:600}
.pill.run{background:#1e3a2f;color:var(--ok)}
.pill.idle{background:#2a3040;color:var(--muted)}
.pill.work{background:#2a2840;color:#c4b5fd}
.pill.proxy{background:#1a2a40;color:var(--accent)}
dl{margin:0;display:grid;grid-template-columns:auto 1fr;gap:.3rem .8rem;font-size:.9rem}
dt{color:var(--muted)}
dd{margin:0}
a{color:var(--accent);text-decoration:none}
pre{margin:.5rem 0 0;font-size:.7rem;max-height:180px;overflow:auto;background:#0d1117;padding:.6rem;border-radius:8px;white-space:pre-wrap;word-break:break-all}
.btn{display:inline-block;padding:.55rem 1rem;border-radius:10px;font-size:.85rem;font-weight:600;cursor:pointer;border:none;color:#fff;background:var(--btn);transition:background .15s}
.btn:hover{background:var(--btn-hover)}
.btn.ok{background:#059669}
.btn.warn{background:#d97706}
.btn.err{background:#dc2626}
.btn:disabled{opacity:.45;cursor:not-allowed}
.btn-row{display:flex;gap:.5rem;flex-wrap:wrap;margin:.6rem 0}
table{width:100%;border-collapse:collapse;font-size:.8rem}
th,td{text-align:left;padding:.35rem .3rem;border-bottom:1px solid #2a3548}
th{color:var(--muted);font-weight:500}
.ok{color:var(--ok)}.bad{color:var(--bad)}
#toast{position:fixed;top:1rem;right:1rem;background:#1a2332;border:1px solid #2a3548;padding:.6rem 1rem;border-radius:10px;font-size:.85rem;display:none;z-index:99}
</style>
</head>
<body>
<h1>📬 Outlook 自动注册</h1>
<p class="sub">xzxyuan · 每 4 小时 5 个 · 页面 10 秒刷新 · <span id="clock"></span></p>

<div class="grid">
  <div class="card">
    <h2>运行状态</h2>
    <p><span class="pill {{phase_class}}">{{phase_label}}</span></p>
    <dl>
      <dt>当前任务</dt><dd>{{phase_detail}}</dd>
      <dt>下一轮注册</dt><dd>{{next_register}}</dd>
      <dt>上次成功一批</dt><dd>{{last_success}}</dd>
      <dt>距上次成功</dt><dd>{{hours_since}}</dd>
      <dt>守护重启次数</dt><dd>{{restart_count}}</dd>
      <dt>下次 0 点推送</dt><dd>{{next_midnight}}</dd>
      <dt>状态更新</dt><dd>{{updated}}</dd>
    </dl>
  </div>

  <div class="card">
    <h2>代理 &amp; 外网</h2>
    <dl>
      <dt>出口代理</dt><dd>{{proxy_status}}</dd>
      <dt>ngrok 公网</dt><dd>{{ngrok_link}}</dd>
      <dt>本机面板</dt><dd>端口 {{port}}</dd>
    </dl>
    <div class="btn-row">
      <button class="btn" onclick="go('refresh_proxy')" {{disabled_proxy}}>🔄 刷新代理</button>
    </div>
  </div>
</div>

<div class="card" style="margin-top:.8rem">
  <h2>手动操作（完整流程）</h2>
  <p style="font-size:.82rem;color:var(--muted);margin:0 0 .6rem">每个按钮独立执行，不会互相干扰。</p>
  <div class="btn-row">
    <button class="btn ok" onclick="go('full_pipeline')">🚀 完整流程</button>
    <button class="btn" onclick="go('register_5')">📝 注册 5 个</button>
    <button class="btn warn" onclick="go('fetch_rt')">🔑 获取 RT</button>
    <button class="btn" onclick="go('push_github')">📤 推送 GitHub</button>
  </div>
  <pre id="action_log" style="display:none"></pre>
</div>

<div class="card" style="margin-top:.8rem">
  <h2>最近注册结果（{{results_count}} 条）</h2>
  {{results_table}}
</div>

<div class="card" style="margin-top:.8rem">
  <h2>守护日志（尾部）</h2>
  <pre>{{log_tail}}</pre>
</div>

<div id="toast"></div>

<script>
const clock=document.getElementById('clock');
setInterval(()=>{clock.textContent=new Date().toLocaleString('zh-CN')},1000);

async function go(action){
  const btn=document.querySelector(`button[onclick="go('${action}')"]`);
  if(btn){btn.disabled=true;btn.textContent='⏳ 执行中...';}
  const logEl=document.getElementById('action_log');
  logEl.style.display='block';
  logEl.textContent='正在执行 '+action+' ...';
  try{
    const r=await fetch('/api/action/'+action,{method:'POST'});
    const d=await r.json();
    if(d.ok){
      showToast('✅ '+d.msg,'ok');
      logEl.textContent=d.output||d.msg;
    }else{
      showToast('❌ '+d.msg,'err');
      logEl.textContent=d.output||d.msg;
    }
  }catch(e){
    showToast('❌ 请求失败: '+e,'err');
  }finally{
    if(btn){btn.disabled=false;btn.textContent=btn.dataset.orig||btn.textContent;}
    setTimeout(()=>location.reload(),1500);
  }
}
let toastTimer;
function showToast(msg,type){
  const t=document.getElementById('toast');
  t.textContent=msg;t.style.display='block';
  t.style.borderColor=type==='ok'?'#059669':type==='err'?'#dc2626':'#d97706';
  clearTimeout(toastTimer);
  toastTimer=setTimeout(()=>{t.style.display='none'},4000);
}
document.querySelectorAll('.btn').forEach(b=>{
  b.dataset.orig=b.textContent;
});
</script>
</body>
</html>
"""


def _fmt_ts(ts: float | None) -> str:
    if not ts:
        return "—"
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))


def _render_results(rows: list) -> str:
    if not rows:
        return "<p style='color:var(--muted)'>暂无记录</p>"
    lines = ["<table><tr><th>时间</th><th>结果</th><th>邮箱</th><th>RT</th><th>说明</th></tr>"]
    for r in reversed(rows):
        ok = r.get("success")
        cls = "ok" if ok else "bad"
        label = "✅ 成功" if ok else "❌ 失败"
        email = (r.get("email") or "—")[:40]
        has_rt = "🔑" if r.get("refresh_token") else "—"
        err = (r.get("error") or "")[:45]
        ts = (r.get("ts") or "")[:19]
        lines.append(
            f"<tr><td>{ts}</td><td class='{cls}'>{label}</td><td>{email}</td>"
            f"<td>{has_rt}</td><td>{err}</td></tr>"
        )
    lines.append("</table>")
    return "\n".join(lines)


def _render_page(snap: dict) -> str:
    phase = snap.get("phase") or "unknown"
    labels = {
        "registering": ("work", "注册中", "正在执行一批 5 次串行注册"),
        "syncing": ("work", "同步中", "正在同步/推送凭证到 Git"),
        "proxy_refresh": ("proxy", "代理刷新中", "正在刷新订阅代理"),
        "rt_fetch": ("work", "RT 获取中", "正在获取 refresh_token"),
        "full_pipeline": ("work", "完整流程中", "正在执行完整注册流程"),
        "waiting": ("run", "等待中", "守护进程正常循环，等待下一轮"),
        "starting": ("run", "启动中", "刚启动或刚完成一轮"),
        "idle": ("idle", "空闲", "等待指令"),
        "unknown": ("idle", "未知", "等待守护进程写入状态"),
    }
    phase_class, phase_label, phase_detail = labels.get(phase, labels["unknown"])
    if snap.get("phase_message"):
        phase_detail = str(snap["phase_message"])

    ngrok = snap.get("ngrok_public_url") or ""
    ngrok_link = f'<a href="{ngrok}" target="_blank" rel="noopener">{ngrok}</a>' if ngrok else "—"

    # 代理状态
    proxy_status = "未检测"
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect(("127.0.0.1", 28888))
        s.close()
        proxy_status = "✅ :28888 监听中"
    except Exception:
        proxy_status = "❌ :28888 未监听"

    log_tail = "\n".join(snap.get("log_tail") or [])[-6000:]
    recent = snap.get("recent_results") or []
    return (
        HTML
        .replace("{{phase_class}}", phase_class)
        .replace("{{phase_label}}", phase_label)
        .replace("{{phase_detail}}", phase_detail)
        .replace("{{next_register}}", _fmt_ts(snap.get("next_register_at")))
        .replace("{{last_success}}", snap.get("last_successful_batch_iso") or "—")
        .replace("{{hours_since}}", (
            f"{snap.get('hours_since_last_success'):.1f} 小时"
            if snap.get("hours_since_last_success") is not None else "—"
        ))
        .replace("{{restart_count}}", str(snap.get("daemon_restart_count") or 0))
        .replace("{{next_midnight}}", _fmt_ts(snap.get("next_midnight_push_at")))
        .replace("{{updated}}", snap.get("updated_at_iso") or "—")
        .replace("{{proxy_status}}", proxy_status)
        .replace("{{ngrok_link}}", ngrok_link)
        .replace("{{port}}", str(PORT))
        .replace("{{results_count}}", str(len(recent)))
        .replace("{{results_table}}", _render_results(recent))
        .replace("{{log_tail}}", log_tail or "(暂无日志)")
        .replace("{{disabled_proxy}}", "")
    )


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        return

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path in ("/api/status", "/api/status/"):
            snap = build_snapshot({"ngrok_public_url": _fetch_ngrok_url()})
            self._json(snap)
            return
        if path in ("/", "/index.html"):
            snap = build_snapshot({"ngrok_public_url": _fetch_ngrok_url()})
            self._html(_render_page(snap))
            return
        self.send_error(404)

    def do_POST(self) -> None:
        path = self.path.rstrip("/")
        action_name = path.rsplit("/", 1)[-1]
        fn = ACTIONS.get(action_name)
        if not fn:
            self.send_error(404)
            return
        # 异步执行，先返回 accepted
        threading.Thread(target=fn, daemon=True).start()
        self._json({"ok": True, "msg": f"已启动 {action_name}", "accepted": True})

    def _json(self, data: dict) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _html(self, body: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))


def _fetch_ngrok_url() -> str | None:
    try:
        with urllib.request.urlopen("http://127.0.0.1:4040/api/tunnels", timeout=2) as r:
            data = json.loads(r.read().decode())
        for t in (data.get("tunnels") or []):
            if t.get("proto") == "https":
                return t.get("public_url")
    except Exception:
        pass
    return None


def main() -> None:
    save_status({"phase": "starting", "phase_message": "仪表盘已启动"})
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Outlook dashboard http://0.0.0.0:{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
