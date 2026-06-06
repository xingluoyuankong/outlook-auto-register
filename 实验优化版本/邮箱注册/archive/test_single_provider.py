#!/usr/bin/env python3
"""
快速测试单个提供商注册
用法:
  python test_single_provider.py proton
  python test_single_provider.py gmx --proxy http://ip:port
  python test_single_provider.py mailcom --headless
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run_all_providers import run_provider, PROVIDER_MODULES


def main():
    if len(sys.argv) < 2:
        print("用法: python test_single_provider.py <提供商名> [--proxy URL] [--headless]")
        print(f"支持的提供商: {', '.join(PROVIDER_MODULES.keys())}")
        sys.exit(1)

    provider = sys.argv[1]
    if provider not in PROVIDER_MODULES:
        print(f"未知提供商: {provider}")
        print(f"支持的提供商: {', '.join(PROVIDER_MODULES.keys())}")
        sys.exit(1)

    proxy = ""
    headless = False
    for i, arg in enumerate(sys.argv[2:], 2):
        if arg == "--proxy" and i + 1 < len(sys.argv):
            proxy = sys.argv[i + 1]
        elif arg == "--headless":
            headless = True

    print(f"正在测试: {provider}")
    print(f"代理: {proxy or '无'}")
    print(f"无头: {headless}")
    print("-" * 40)

    r = run_provider(provider, proxy=proxy, headless=headless)

    print(f"\n结果: {'成功' if r['success'] else '失败'}")
    print(f"邮箱: {r.get('email', '')}")
    print(f"密码: {r.get('password', '')}")
    if r.get("error"):
        print(f"错误: {r['error']}")


if __name__ == "__main__":
    main()
