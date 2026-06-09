#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Outlook 注册常驻守护程序

- 每 4 小时串行注册 5 次
- 每天 00:00 自动同步并推送三凭证/四凭证到私有仓库 cloud-register-email
- 永久保活：由 Zo user service supervisor 管理，本脚本自身也持续循环
- 使用可视实体浏览器 + 无痕模式（通过 Xvfb 提供显示，不使用 headless）
"""

from __future__ import annotations
import datetime as dt
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

from outlook_daemon_status import (
    REGISTER_INTERVAL_SECONDS,
    compute_next_register_after_batch,
    resolve_next_register_on_startup,
    save_schedule,
    save_status,
)

ROOT = Path(__file__).resolve().parent
LOG_DIR = ROOT / "runtime_outlook" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "outlook_daemon.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
    force=True,
)
log = logging.getLogger("outlook_daemon")

DISPLAY_ID = ":98"
REGISTER_COUNT = 5


def run(cmd: list[str], timeout: int | None = None, env: dict | None = None) -> int:
    log.info("RUN: %s", " ".join(cmd))
    p = subprocess.Popen(cmd, cwd=str(ROOT), env=env or os.environ.copy())
    try:
        return p.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        log.warning("timeout, terminate: %s", p.pid)
        p.terminate()
        try:
            return p.wait(timeout=20)
        except subprocess.TimeoutExpired:
            p.kill()
            return p.wait()


def ensure_xvfb() -> None:
    env = os.environ.copy()
    env["DISPLAY"] = DISPLAY_ID
    ok = subprocess.run(["xdpyinfo"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    if ok:
        return
    # 僵尸锁：进程已死但 /tmp/.X98-lock 仍在会导致新 Xvfb 起不来
    lock = Path("/tmp/.X98-lock")
    pgrep = subprocess.run(["pgrep", "-f", f"Xvfb {DISPLAY_ID}"], capture_output=True, text=True)
    if pgrep.returncode != 0 and lock.exists():
        log.warning("stale X lock without Xvfb, removing %s", lock)
        lock.unlink(missing_ok=True)
        sock = Path(f"/tmp/.X11-unix/X{DISPLAY_ID.lstrip(':')}")
        sock.unlink(missing_ok=True)
    log.info("starting Xvfb %s", DISPLAY_ID)
    subprocess.Popen(
        ["Xvfb", DISPLAY_ID, "-screen", "0", "1366x768x24", "-ac", "-nolisten", "tcp"],
        stdout=open(LOG_DIR / "xvfb_daemon.log", "a", encoding="utf-8"),
        stderr=subprocess.STDOUT,
    )
    for _ in range(10):
        time.sleep(1)
        if subprocess.run(["xdpyinfo"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
            return
    log.error("Xvfb %s failed to become ready", DISPLAY_ID)


def sync_credentials(push: bool = True) -> None:
    save_status({"phase": "syncing", "phase_message": "同步凭证到云端仓库"})
    cmd = [sys.executable, str(ROOT / "sync_credentials.py")]
    if push:
        cmd.append("--push")
    code = run(cmd, timeout=300)
    log.info("sync exit=%s", code)


def post_register_fetch_rt() -> None:
    """注册后自动获取 refresh_token。"""
    save_status({"phase": "fetching_rt", "phase_message": "注册完成，自动获取 refresh_token"})
    env = os.environ.copy()
    env["DISPLAY"] = DISPLAY_ID
    cmd = [
        sys.executable, "-u", str(ROOT / "post_register_fetch_rt.py"),
        "--limit", "10", "--timeout", "90", "--display", DISPLAY_ID,
    ]
    code = run(cmd, timeout=1800, env=env)
    log.info("post_register_fetch_rt exit=%s", code)


def register_batch() -> None:
    save_status({"phase": "registering", "phase_message": f"串行注册 {REGISTER_COUNT} 个 Outlook 账号"})
    ensure_xvfb()
    env = os.environ.copy()
    env["DISPLAY"] = DISPLAY_ID
    env["SUB_PROXY_FAST_START"] = "1"
    cmd = [
        sys.executable, str(ROOT / "outlook_launcher.py"),
        "run", "--count", str(REGISTER_COUNT), "--shuffle", "--max-proxy-attempts", "12",
    ]
    code = run(cmd, timeout=REGISTER_INTERVAL_SECONDS - 300, env=env)
    log.info("register batch exit=%s", code)
    # ── 注册批次后强制清理孤儿浏览器 ──
    try:
        sys.path.insert(0, str(ROOT / "邮箱注册"))
        from cdp_outlook import kill_orphan_chrome_processes
        kill_orphan_chrome_processes()
    except Exception as e:
        log.warning("批次后浏览器清理失败: %s", e)
    ended = time.time()
    save_schedule({
        "last_batch_finished_at": ended,
        "last_batch_exit_code": code,
        "last_batch_finished_iso": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ended)),
    })
    # 注册后自动获取 RT
    try:
        post_register_fetch_rt()
    except Exception as exc:
        log.warning("post_register_fetch_rt failed: %s", exc)
    # ── RT 提取后再次清理孤儿浏览器 ──
    try:
        from cdp_outlook import kill_orphan_chrome_processes
        kill_orphan_chrome_processes()
    except Exception as e:
        log.warning("RT 提取后浏览器清理失败: %s", e)
    sync_credentials(push=True)


def seconds_until_midnight() -> float:
    now = dt.datetime.now()
    nxt = (now + dt.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(1.0, (nxt - now).total_seconds())


def main() -> int:
    log.info("Outlook daemon start: interval=4h count=5 serial forever")
    ensure_xvfb()
    sync_credentials(push=True)
    next_register, run_now, reason = resolve_next_register_on_startup()
    log.info("schedule: %s next_register=%s run_immediately=%s", reason, next_register, run_now)
    next_push = time.time() + seconds_until_midnight()
    save_status({
        "phase": "waiting" if not run_now else "registering",
        "phase_message": reason if not run_now else "已到计划时间，开始注册",
        "next_register_at": next_register,
        "next_midnight_push_at": next_push,
        "schedule_reason": reason,
    })
    if run_now:
        register_batch()
        next_register = compute_next_register_after_batch(time.time())
        save_status({
            "phase": "waiting",
            "phase_message": "本轮完成，等待下一轮 4 小时",
            "next_register_at": next_register,
        })
    while True:
        now = time.time()
        try:
            if now >= next_push:
                log.info("daily midnight credential push")
                sync_credentials(push=True)
                next_push = time.time() + seconds_until_midnight()
                save_status({"next_midnight_push_at": next_push})
            if now >= next_register:
                register_batch()
                next_register = compute_next_register_after_batch(time.time())
                save_status({
                    "phase": "waiting",
                    "phase_message": "本轮完成，等待下一轮 4 小时",
                    "next_register_at": next_register,
                })
        except Exception as exc:
            log.exception("daemon loop error: %s", exc)
            save_status({"phase": "error", "phase_message": str(exc)[:200]})
            time.sleep(60)
        time.sleep(30)


if __name__ == "__main__":
    raise SystemExit(main())
