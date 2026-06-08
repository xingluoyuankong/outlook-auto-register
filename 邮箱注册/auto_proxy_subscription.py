#!/usr/bin/env python3
"""自动注册代理服务新账号 → 获取新订阅链接 → 更新 mihomo subscriptions.json。

默认使用 hidexx 免费试用流程：注册随机新账号、领取试用、提取订阅链接。
不保存账号密码到仓库；运行态只写入 mihomo_runtime/subscriptions.json。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Callable

from hidexx_client import register_and_get_subscription
from subscription_proxy import SUBS_FILE, get_manager


def log(msg: str) -> None:
    print(msg, flush=True)


def update_subscription(url: str, name: str = "hidexx-auto") -> None:
    SUBS_FILE.parent.mkdir(parents=True, exist_ok=True)
    data: list[dict] = []
    if SUBS_FILE.exists():
        try:
            data = json.loads(SUBS_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = []
    data = [s for s in data if s.get("name") != name and s.get("url") != url]
    data.insert(0, {"name": name, "url": url, "created_at": int(time.time())})
    SUBS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def has_working_proxy() -> bool:
    try:
        m = get_manager()
        if not m.subscriptions:
            return False
        ok, msg = m.start()
        if not ok:
            log(f"已有订阅启动失败: {msg}")
            return False
        t = m.test_proxy()
        log(f"已有订阅测试: {t}")
        return bool(t.get("ok"))
    except Exception as exc:
        log(f"已有订阅测试异常: {exc}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="自动注册代理新账号并更新 mihomo 订阅")
    parser.add_argument("--force", action="store_true", help="不检测现有订阅，强制注册新账号并更新订阅")
    parser.add_argument("--name", default="hidexx-auto", help="写入 subscriptions.json 的订阅名称")
    parser.add_argument("--proxy", default=os.getenv("HIDEXX_REGISTER_PROXY", ""), help="注册代理服务账号时使用的可选代理")
    args = parser.parse_args()

    if not args.force and has_working_proxy():
        log("现有代理订阅可用，无需注册新代理账号")
        return 0

    url = register_and_get_subscription(log=log, proxy_url=args.proxy or None)
    if not url:
        log("未获取到新订阅链接")
        return 1
    update_subscription(url, args.name)
    log(f"已更新订阅: {args.name}")

    m = get_manager()
    ok, msg = m.start()
    log(f"mihomo start: {ok} {msg}")
    if not ok:
        return 2
    test = m.test_proxy()
    log(f"mihomo test: {test}")
    return 0 if test.get("ok") else 3


if __name__ == "__main__":
    raise SystemExit(main())
