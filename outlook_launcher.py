#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Outlook 邮箱注册启动器

只负责三件事：
1) 自动获取/导入代理
2) 注册前代理轮询
3) 定时启动注册

Outlook 注册流程本身复用私仓已跑通的 `邮箱注册.cdp_outlook.register_outlook_account`。
默认使用可视实体浏览器 + 无痕模式；不使用 headless。
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import random
import re
import sys
import time
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent
PKG = ROOT / "邮箱注册"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(PKG))

from 邮箱注册.cdp_outlook import register_outlook_account, kill_orphan_chrome_processes
from 邮箱注册.proxy_utils import parse_proxies, parse_proxy
from 邮箱注册.subscription_proxy import get_manager

RUN_DIR = ROOT / "runtime_outlook"
LOG_DIR = RUN_DIR / "logs"
PROXY_FILE = RUN_DIR / "proxies.txt"
RESULT_FILE = RUN_DIR / "results.jsonl"
SCHEDULE_STATE = RUN_DIR / "schedule_state.json"

LOG_DIR.mkdir(parents=True, exist_ok=True)
RUN_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOG_DIR / "outlook_launcher.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
    force=True,
)
log = logging.getLogger("outlook_launcher")

URL_RE = re.compile(r"https?://[^\s<>\"']+", re.I)


def load_proxy_lines() -> list[str]:
    if not PROXY_FILE.exists():
        return []
    return [line.strip() for line in PROXY_FILE.read_text(encoding="utf-8-sig").splitlines() if line.strip() and not line.strip().startswith("#")]


def save_proxy_lines(lines: Iterable[str]) -> None:
    seen: set[str] = set()
    out: list[str] = []
    for raw in lines:
        p = parse_proxy(raw)
        if not p:
            continue
        key = p.url.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(p.url)
    PROXY_FILE.write_text("\n".join(out) + ("\n" if out else ""), encoding="utf-8")
    log.info("代理文件已保存: %s (%d 个)", PROXY_FILE, len(out))


def import_proxies_from_text(text: str, append: bool = True) -> int:
    parsed = [p.url for p in parse_proxies(text)]
    existing = load_proxy_lines() if append else []
    save_proxy_lines(existing + parsed)
    return len(parsed)


def import_proxies_from_file(path: str, append: bool = True) -> int:
    text = Path(path).read_text(encoding="utf-8-sig")
    return import_proxies_from_text(text, append=append)


def import_subscription(url: str, name: str = "") -> None:
    mgr = get_manager()
    ok, msg = mgr.add(url, name=name)
    log.info("订阅导入: %s", msg)
    ok, msg = mgr.start()
    log.info("订阅代理启动: %s", msg)
    if not ok:
        raise RuntimeError(msg)


def import_auto(source: str, append: bool = True) -> None:
    src = source.strip()
    if Path(src).exists():
        count = import_proxies_from_file(src, append=append)
        log.info("已从文件导入代理 %d 个: %s", count, src)
        return
    if URL_RE.fullmatch(src):
        import_subscription(src)
        return
    count = import_proxies_from_text(src, append=append)
    log.info("已从文本导入代理 %d 个", count)


def curl_check_proxy(proxy_url: str, timeout: int = 15) -> dict:
    import subprocess
    test_proxy = proxy_url.replace("socks5://", "socks5h://")
    try:
        r = subprocess.run(
            ["curl", "-s", "--max-time", str(timeout), "--proxy", test_proxy, "https://ipinfo.io/json"],
            capture_output=True,
            text=True,
            timeout=timeout + 5,
        )
        if r.returncode != 0:
            return {"ok": False, "error": r.stderr.strip() or r.stdout.strip() or f"curl_exit_{r.returncode}"}
        data = json.loads(r.stdout)
        return {"ok": True, "ip": data.get("ip", ""), "country": data.get("country", ""), "city": data.get("city", ""), "raw": data}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


class ProxyRotator:
    def __init__(self, shuffle: bool = False):
        self.manager = get_manager()
        if self.manager.subscriptions and not self.manager.is_running:
            log.info("检测到 %d 个订阅，尝试启动订阅代理...", len(self.manager.subscriptions))
            os.environ["SUB_PROXY_FAST_START"] = "1"
            ok, msg = self.manager.start()
            log.info("订阅代理自动启动: %s | %s", ok, msg)
        self.static = load_proxy_lines()
        if shuffle:
            random.shuffle(self.static)
        self.index = 0
        self.fail_count: dict[str, int] = {}

    def next(self) -> str:
        if self.manager.subscriptions and not self.manager.is_running:
            log.warning("订阅代理未运行，尝试重新启动...")
            os.environ["SUB_PROXY_FAST_START"] = "1"
            ok, msg = self.manager.start()
            log.info("订阅代理重启: %s | %s", ok, msg)
        if self.manager.is_running:
            ok, msg = self.manager.switch_to_next_node()
            log.info("订阅节点轮询: %s", msg)
            return self.manager.proxy_url or ""
        if not self.static:
            return ""
        for _ in range(len(self.static)):
            proxy = self.static[self.index % len(self.static)]
            self.index += 1
            if self.fail_count.get(proxy, 0) < 3:
                return proxy
        return self.static[self.index % len(self.static)]

    def mark_failed(self, proxy: str) -> None:
        if proxy:
            self.fail_count[proxy] = self.fail_count.get(proxy, 0) + 1


def write_result(record: dict) -> None:
    with RESULT_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def run_once(proxy: str, browser: str = "chrome", extract_rt: bool = True, slot_index: int = 0) -> dict:
    if proxy:
        check = curl_check_proxy(proxy)
        if check.get("ok"):
            log.info("代理预检通过: %s %s %s", check.get("ip"), check.get("country"), proxy)
        else:
            raise RuntimeError(f"代理预检失败: {proxy} -> {check.get('error')}")
    else:
        log.warning("本次注册未使用代理")

    result = register_outlook_account(
        browser_type=browser,
        proxy=proxy or "",
        headless=False,
        extract_rt=extract_rt,
        keep_browser_open=False,
        slot_index=slot_index,
    )
    record = {
        "ts": dt.datetime.now().isoformat(),
        "success": bool(result.success),
        "email": result.email,
        "password": result.password,
        "client_id": result.client_id,
        "refresh_token": result.refresh_token,
        "error": result.error,
        "final_url": result.final_url,
        "final_state": result.final_state,
        "challenge_type": result.challenge_type,
        "challenge_cleared": result.challenge_cleared,
        "proxy": proxy,
        "screenshot_path": result.screenshot_path,
    }
    write_result(record)
    # ── 每次注册后清理孤儿 Chrome 进程 ──
    try:
        kill_orphan_chrome_processes()
    except Exception as e:
        log.warning("孤儿清理失败: %s", e)
    return record


def run_batch(count: int, browser: str, extract_rt: bool, shuffle: bool, max_proxy_attempts: int = 8) -> list[dict]:
    rotator = ProxyRotator(shuffle=shuffle)
    results: list[dict] = []
    for i in range(count):
        last_error = ""
        recorded = False
        for attempt in range(1, max_proxy_attempts + 1):
            proxy = rotator.next()
            try:
                log.info("开始第 %d/%d 个 Outlook 注册，代理尝试 %d/%d，proxy=%s", i + 1, count, attempt, max_proxy_attempts, proxy or "none")
                record = run_once(proxy, browser=browser, extract_rt=extract_rt, slot_index=i)
                results.append(record)
                recorded = True
                if record.get("success"):
                    log.info("成功: %s", record.get("email"))
                    last_error = ""
                    break
                last_error = str(record.get("error") or "unknown_failure")
                log.warning("注册失败: %s | %s", record.get("email"), last_error)
            except Exception as exc:
                last_error = str(exc)
                log.exception("本轮注册异常: %s", exc)
            if _is_proxy_related_error(last_error) and attempt < max_proxy_attempts:
                log.warning("代理相关失败，轮询下一个代理/节点后重试: %s", last_error)
                time.sleep(1)
                continue
            break
        if last_error and not recorded:
            results.append({"success": False, "error": last_error, "ts": dt.datetime.now().isoformat()})
    # ── 批次结束后最终清理 ──
    try:
        kill_orphan_chrome_processes()
    except Exception as e:
        log.warning("批次结束清理失败: %s", e)
    return results


def _is_proxy_related_error(text: str) -> bool:
    t = (text or "").lower()
    return any(k in t for k in [
        "代理预检失败", "proxy_error", "chrome-error", "curl_exit", "connection", "timeout", "err_tunnel", "err_proxy",
    ])


def parse_run_at(value: str) -> dt.datetime:
    if not value:
        return dt.datetime.now()
    text = value.strip()
    if re.fullmatch(r"\d{1,2}:\d{2}", text):
        hour, minute = map(int, text.split(":"))
        now = dt.datetime.now()
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += dt.timedelta(days=1)
        return target
    return dt.datetime.fromisoformat(text)


def schedule_loop(at: str, interval_minutes: int, count: int, browser: str, extract_rt: bool, shuffle: bool, max_proxy_attempts: int) -> None:
    next_run = parse_run_at(at)
    while True:
        state = {"next_run": next_run.isoformat(), "interval_minutes": interval_minutes, "count": count}
        SCHEDULE_STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        sleep_s = max(0, (next_run - dt.datetime.now()).total_seconds())
        log.info("定时器等待到 %s 后启动注册，count=%d", next_run.isoformat(), count)
        time.sleep(sleep_s)
        run_batch(count=count, browser=browser, extract_rt=extract_rt, shuffle=shuffle, max_proxy_attempts=max_proxy_attempts)
        if interval_minutes <= 0:
            break
        next_run = dt.datetime.now() + dt.timedelta(minutes=interval_minutes)


def main() -> int:
    parser = argparse.ArgumentParser(description="Outlook 注册启动器：代理导入/轮询/定时启动")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_import = sub.add_parser("import-proxies", help="导入代理；参数可为 txt 文件、订阅 URL 或多行代理文本")
    p_import.add_argument("source")
    p_import.add_argument("--replace", action="store_true", help="替换现有静态代理文件")

    p_run = sub.add_parser("run", help="立即启动注册")
    p_run.add_argument("--count", type=int, default=1)
    p_run.add_argument("--browser", default="chrome")
    p_run.add_argument("--no-rt", action="store_true", help="不提取 refresh token")
    p_run.add_argument("--shuffle", action="store_true")
    p_run.add_argument("--max-proxy-attempts", type=int, default=8, help="单个账号最多轮询尝试的代理/节点数")

    p_schedule = sub.add_parser("schedule", help="定时启动注册")
    p_schedule.add_argument("--at", default="", help="启动时间：HH:MM 或 ISO 时间；为空=立即")
    p_schedule.add_argument("--interval-minutes", type=int, default=0, help="循环间隔；0=只跑一次")
    p_schedule.add_argument("--count", type=int, default=1)
    p_schedule.add_argument("--browser", default="chrome")
    p_schedule.add_argument("--no-rt", action="store_true")
    p_schedule.add_argument("--shuffle", action="store_true")
    p_schedule.add_argument("--max-proxy-attempts", type=int, default=8, help="单个账号最多轮询尝试的代理/节点数")

    p_status = sub.add_parser("status", help="查看代理/结果状态")

    args = parser.parse_args()
    if args.cmd == "import-proxies":
        import_auto(args.source, append=not args.replace)
        return 0
    if args.cmd == "run":
        run_batch(count=args.count, browser=args.browser, extract_rt=not args.no_rt, shuffle=args.shuffle, max_proxy_attempts=args.max_proxy_attempts)
        return 0
    if args.cmd == "schedule":
        schedule_loop(args.at, args.interval_minutes, args.count, args.browser, not args.no_rt, args.shuffle, args.max_proxy_attempts)
        return 0
    if args.cmd == "status":
        mgr = get_manager()
        status = {
            "static_proxy_count": len(load_proxy_lines()),
            "proxy_file": str(PROXY_FILE),
            "subscription_proxy": mgr.status(),
            "result_file": str(RESULT_FILE),
            "schedule_state": json.loads(SCHEDULE_STATE.read_text(encoding="utf-8")) if SCHEDULE_STATE.exists() else {},
        }
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
