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
REGISTER_INTERVAL_SECONDS = 4 * 60 * 60
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
    log.info("starting Xvfb %s", DISPLAY_ID)
    subprocess.Popen(
        ["Xvfb", DISPLAY_ID, "-screen", "0", "1366x768x24", "-ac", "-nolisten", "tcp"],
        stdout=open(LOG_DIR / "xvfb_daemon.log", "a", encoding="utf-8"),
        stderr=subprocess.STDOUT,
    )
    time.sleep(3)


def sync_credentials(push: bool = True) -> None:
    cmd = [sys.executable, str(ROOT / "sync_credentials.py")]
    if push:
        cmd.append("--push")
    code = run(cmd, timeout=300)
    log.info("sync exit=%s", code)


def register_batch() -> None:
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
    sync_credentials(push=True)


def seconds_until_midnight() -> float:
    now = dt.datetime.now()
    nxt = (now + dt.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(1.0, (nxt - now).total_seconds())


def main() -> int:
    log.info("Outlook daemon start: interval=4h count=5 serial forever")
    ensure_xvfb()
    sync_credentials(push=True)
    next_register = time.time()
    next_push = time.time() + seconds_until_midnight()
    while True:
        now = time.time()
        try:
            if now >= next_push:
                log.info("daily midnight credential push")
                sync_credentials(push=True)
                next_push = time.time() + seconds_until_midnight()
            if now >= next_register:
                register_batch()
                next_register = time.time() + REGISTER_INTERVAL_SECONDS
        except Exception as exc:
            log.exception("daemon loop error: %s", exc)
            time.sleep(60)
        time.sleep(30)


if __name__ == "__main__":
    raise SystemExit(main())
