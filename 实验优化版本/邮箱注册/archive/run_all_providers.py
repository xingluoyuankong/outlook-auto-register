#!/usr/bin/env python3
"""
逐个跑通所有邮箱提供商注册脚本
用法: python run_all_providers.py [--proxy http://ip:port] [--providers proton,gmx,...]
"""

import argparse
import importlib
import json
import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 提供商 → 模块名映射
PROVIDER_MODULES = {
    "proton": "register_proton",
    "gmx": "register_gmx",
    "mailcom": "register_mailcom",
    "tutanota": "register_tutanota",
    "aol": "register_aol",
    "zoho": "register_zoho",
    "mailru": "register_mailru",
    "yandex": "register_yandex",
    "163": "register_163",
    "126": "register_163",      # 同一模块，不同参数
    "yeah": "register_163",    # 同一模块，不同参数
    "sina": "register_sina",
    "sohu": "register_sohu",
}

# 需要额外参数的提供商
PROVIDER_EXTRA_ARGS = {
    "126": {"domain_key": "126"},
    "yeah": {"domain_key": "yeah"},
}


def run_provider(name: str, proxy: str = "", headless: bool = False) -> dict:
    """运行单个提供商注册"""
    module_name = PROVIDER_MODULES.get(name)
    if not module_name:
        return {"provider": name, "success": False, "error": "unknown_provider"}

    try:
        mod = importlib.import_module(module_name)
        extra = PROVIDER_EXTRA_ARGS.get(name, {})
        result = mod.register(proxy=proxy, headless=headless, **extra)
        return {
            "provider": name,
            "success": result.success,
            "email": result.email,
            "password": result.password,
            "error": result.error,
            "final_url": result.final_url,
        }
    except Exception as e:
        return {"provider": name, "success": False, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="逐个跑通所有邮箱提供商注册")
    parser.add_argument("--proxy", default="", help="代理地址")
    parser.add_argument("--headless", action="store_true", help="无头模式")
    parser.add_argument("--providers", default="",
                        help="指定要跑的提供商，逗号分隔。留空跑全部")
    parser.add_argument("--delay", type=int, default=5,
                        help="每个提供商之间的等待秒数")
    args = parser.parse_args()

    if args.providers:
        providers = [p.strip() for p in args.providers.split(",")]
    else:
        providers = list(PROVIDER_MODULES.keys())

    logger.info("=" * 60)
    logger.info("开始逐个跑通邮箱注册")
    logger.info("提供商: %s", ", ".join(providers))
    logger.info("代理: %s", args.proxy or "无")
    logger.info("=" * 60)

    results = []
    for i, provider in enumerate(providers, 1):
        logger.info("\n[%d/%d] ========== %s ==========", i, len(providers), provider)
        r = run_provider(provider, proxy=args.proxy, headless=args.headless)
        results.append(r)

        status = "成功" if r["success"] else "失败"
        logger.info("[%d/%d] %s: %s  邮箱: %s  错误: %s",
                     i, len(providers), provider, status, r.get("email", ""), r.get("error", ""))

        if i < len(providers):
            logger.info("等待 %d 秒后继续...", args.delay)
            time.sleep(args.delay)

    # 汇总报告
    logger.info("\n" + "=" * 60)
    logger.info("注册结果汇总")
    logger.info("=" * 60)

    success_count = 0
    for r in results:
        status = "成功" if r["success"] else "失败"
        if r["success"]:
            success_count += 1
        logger.info("  %-12s  %-6s  邮箱: %-30s  错误: %s",
                     r["provider"], status, r.get("email", ""), r.get("error", ""))

    logger.info("-" * 60)
    logger.info("总计: %d/%d 成功", success_count, len(results))

    # 保存汇总到文件
    summary_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..",
        "registered_accounts", "summary.json"
    )
    os.makedirs(os.path.dirname(summary_path), exist_ok=True)
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": time.strftime("%Y%m%d_%H%M%S"),
            "total": len(results),
            "success": success_count,
            "results": results,
        }, f, ensure_ascii=False, indent=2)
    logger.info("汇总已保存到: %s", summary_path)


if __name__ == "__main__":
    main()
