#!/usr/bin/env python3
"""Unified startup entry for Ninjemail."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from desktop_ui import (  # noqa: E402
    check_dependencies,
    format_missing_dependencies,
    install_dependencies,
    launch_web_ui,
    main as launch_desktop,
    run_tests,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ninjemail 启动器")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--desktop", action="store_true", help="启动桌面控制台")
    mode.add_argument("--web", action="store_true", help="启动浏览器版 Web 界面")
    parser.add_argument("--port", type=int, default=7860, help="Web 界面端口")
    parser.add_argument("--share", action="store_true", help="生成公开分享链接")
    parser.add_argument("--no-browser", action="store_true", help="启动 Web 界面时不自动打开浏览器")
    parser.add_argument("--check", action="store_true", help="检查依赖")
    parser.add_argument("--install", action="store_true", help="安装依赖")
    parser.add_argument("--test", action="store_true", help="运行测试")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.check:
        missing = check_dependencies(include_web=args.web)
        message = format_missing_dependencies(missing)
        print(message)
        return 0 if not missing else 1

    if args.install:
        return install_dependencies(include_web=True, log=print)

    if args.test:
        return run_tests(log=print)

    if args.web:
        process, port, url = launch_web_ui(
            port=args.port,
            share=args.share,
            auto_open=not args.no_browser,
            log=print,
        )
        print(f"Web UI running at {url}")
        try:
            return process.wait()
        except KeyboardInterrupt:
            process.terminate()
            try:
                process.wait(timeout=5)
            except Exception:
                process.kill()
            return 130

    launch_desktop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
