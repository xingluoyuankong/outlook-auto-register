"""Shared status file for outlook daemon + dashboard (stdlib only)."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
STATUS_PATH = ROOT / "runtime_outlook" / "daemon_status.json"
SCHEDULE_PATH = ROOT / "runtime_outlook" / "daemon_schedule.json"
LOG_FILE = ROOT / "runtime_outlook" / "logs" / "outlook_daemon.log"
RESULTS_FILE = ROOT / "runtime_outlook" / "results.jsonl"
DEPLOY_TS = 1780774138  # 2026-06-06T19:28:58 UTC, when the daemon service was first deployed

REGISTER_INTERVAL_SECONDS = 4 * 60 * 60
REGISTER_COUNT = 5


def _tail_lines(path: Path, n: int = 80) -> list[str]:
    if not path.is_file():
        return []
    try:
        data = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return data[-n:]
    except OSError:
        return []


def _recent_results(n: int = 15) -> list[dict[str, Any]]:
    if not RESULTS_FILE.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in _tail_lines(RESULTS_FILE, 200):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows[-n:]


def _parse_last_batch_ends() -> dict[str, Any]:
    import re
    from datetime import datetime

    if not LOG_FILE.is_file():
        return {}
    text = LOG_FILE.read_text(encoding="utf-8", errors="replace")
    batches = re.findall(
        r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*register batch exit=(\d+)", text
    )
    restarts = len(re.findall(r"Outlook daemon start", text))
    last_any: float | None = None
    last_ok: float | None = None
    for ts_s, code in batches:
        try:
            dt = datetime.strptime(ts_s, "%Y-%m-%d %H:%M:%S")
            epoch = dt.timestamp()
        except ValueError:
            continue
        last_any = epoch
        if code == "0":
            last_ok = epoch
    out: dict[str, Any] = {"daemon_restart_count": restarts}
    if last_any is not None:
        out["last_batch_finished_at"] = last_any
        out["last_batch_finished_iso"] = time.strftime(
            "%Y-%m-%d %H:%M:%S", time.localtime(last_any)
        )
    if last_ok is not None:
        out["last_successful_batch_at"] = last_ok
        out["last_successful_batch_iso"] = time.strftime(
            "%Y-%m-%d %H:%M:%S", time.localtime(last_ok)
        )
        out["hours_since_last_success"] = round((time.time() - last_ok) / 3600, 2)
    return out


def load_status() -> dict[str, Any]:
    if STATUS_PATH.is_file():
        try:
            return json.loads(STATUS_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return {}


def save_status(patch: dict[str, Any]) -> dict[str, Any]:
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    cur = load_status()
    cur.update(patch)
    cur["updated_at"] = time.time()
    cur["updated_at_iso"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    STATUS_PATH.write_text(json.dumps(cur, ensure_ascii=False, indent=2), encoding="utf-8")
    return cur


def load_schedule() -> dict[str, Any]:
    if SCHEDULE_PATH.is_file():
        try:
            return json.loads(SCHEDULE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return {}


def save_schedule(patch: dict[str, Any]) -> dict[str, Any]:
    SCHEDULE_PATH.parent.mkdir(parents=True, exist_ok=True)
    cur = load_schedule()
    cur.update(patch)
    SCHEDULE_PATH.write_text(json.dumps(cur, ensure_ascii=False, indent=2), encoding="utf-8")
    return cur


def compute_next_register_after_batch(batch_end: float) -> float:
    return batch_end + REGISTER_INTERVAL_SECONDS


def resolve_next_register_on_startup(now: float | None = None) -> tuple[float, bool, str]:
    """Returns (next_register_at, should_run_immediately, reason)."""
    now = now or time.time()
    sched = load_schedule()
    parsed = _parse_last_batch_ends()
    last_end = sched.get("last_batch_finished_at") or parsed.get("last_batch_finished_at")
    if last_end:
        nxt = float(last_end) + REGISTER_INTERVAL_SECONDS
        if now < nxt:
            return nxt, False, "距上次完成一批未满 4 小时，按持久化计划等待"
        return now, True, "已超过 4 小时，立即开始新一轮"
    return now, True, "尚无完成记录，启动后执行首批注册"


def _registration_stats() -> dict[str, Any]:
    total_registrations = 0
    today_registrations = 0
    today_str = time.strftime("%Y-%m-%d")
    if RESULTS_FILE.is_file():
        for line in RESULTS_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not record.get("success"):
                continue
            total_registrations += 1
            ts_str = (record.get("ts") or "")[:10]
            if ts_str == today_str:
                today_registrations += 1
    elapsed = time.time() - DEPLOY_TS
    days = int(elapsed // 86400)
    hours = int((elapsed % 86400) // 3600)
    mins = int((elapsed % 3600) // 60)
    if days > 0:
        runtime_str = f"{days}天{hours}小时{mins}分"
    elif hours > 0:
        runtime_str = f"{hours}小时{mins}分"
    else:
        runtime_str = f"{mins}分钟"
    return {
        "total_registrations": total_registrations,
        "today_registrations": today_registrations,
        "total_runtime": runtime_str,
    }


def build_snapshot(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    st = load_status()
    sched = load_schedule()
    parsed = _parse_last_batch_ends()
    node_meta = {}
    nid_path = ROOT / "runtime_outlook" / "node_identity.json"
    if nid_path.is_file():
        try:
            node_meta = json.loads(nid_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    snap: dict[str, Any] = {
        "node_id": node_meta.get("node_id", "xzxyuan"),
        "node_label": node_meta.get("label", node_meta.get("node_id", "xzxyuan")),
        "service": "outlook-auto-register-daemon",
        "interval_hours": 4,
        "batch_size": REGISTER_COUNT,
        "schedule": sched,
        "log_tail": _tail_lines(LOG_FILE, 60),
        "recent_results": _recent_results(12),
        "results_total_lines": len(_tail_lines(RESULTS_FILE, 100000)),
        **parsed,
        **st,
    }
    if extra:
        snap.update(extra)
    snap.update(_registration_stats())
    return snap