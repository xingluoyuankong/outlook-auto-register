#!/usr/bin/env python3
"""
实跑测试所有邮箱提供商（排除 Outlook/Yahoo/Gmail）
使用 CDP 浏览器自动化，加载 CAPTCHA 求解扩展
"""

import argparse
import importlib
import json
import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(os.path.dirname(__file__), "..", "live_test.log"), encoding="utf-8"),
    ]
)
logger = logging.getLogger(__name__)

# 排除 Outlook/Hotmail, Yahoo, Gmail
# AOL 使用 Yahoo 系统但也排除（用户要求排除 Yahoo）
PROVIDERS_TO_TEST = {
    "gmx": {
        "module": "register_gmx",
        "desc": "GMX Mail (gmx.com) - 通常不需要手机号",
        "difficulty": "easy",
        "has_phone": False,
    },
    "mailcom": {
        "module": "register_mailcom",
        "desc": "Mail.com - 通常不需要手机号",
        "difficulty": "easy",
        "has_phone": False,
    },
    "tutanota": {
        "module": "register_tutanota",
        "desc": "Tutanota/Tuta (tuta.com) - 通常不需要手机号",
        "difficulty": "easy",
        "has_phone": False,
    },
    "proton": {
        "module": "register_proton",
        "desc": "Proton Mail (proton.me) - 可能有 CAPTCHA",
        "difficulty": "medium",
        "has_phone": False,
    },
    "zoho": {
        "module": "register_zoho",
        "desc": "Zoho Mail (zoho.com) - 可能要求手机号",
        "difficulty": "hard",
        "has_phone": True,
    },
    "mailru": {
        "module": "register_mailru",
        "desc": "Mail.ru - 可能有 CAPTCHA",
        "difficulty": "medium",
        "has_phone": False,
    },
    "yandex": {
        "module": "register_yandex",
        "desc": "Yandex Mail (yandex.com) - 通常要求手机号",
        "difficulty": "hard",
        "has_phone": True,
    },
    "163": {
        "module": "register_163",
        "desc": "网易 163 邮箱 - 可能要求手机号",
        "difficulty": "hard",
        "has_phone": True,
    },
    "126": {
        "module": "register_163",
        "desc": "网易 126 邮箱",
        "difficulty": "hard",
        "has_phone": True,
        "extra": {"domain_key": "126"},
    },
    "yeah": {
        "module": "register_163",
        "desc": "网易 Yeah 邮箱",
        "difficulty": "hard",
        "has_phone": True,
        "extra": {"domain_key": "yeah"},
    },
    "sina": {
        "module": "register_sina",
        "desc": "新浪邮箱 (sina.com) - 通常要求手机号",
        "difficulty": "hard",
        "has_phone": True,
    },
    "sohu": {
        "module": "register_sohu",
        "desc": "搜狐邮箱 (sohu.com) - 通常要求手机号",
        "difficulty": "hard",
        "has_phone": True,
    },
    "aol": {
        "module": "register_aol",
        "desc": "AOL Mail (aol.com) - 使用 Yahoo 系统",
        "difficulty": "medium",
        "has_phone": False,
    },
}

# CAPTCHA 扩展路径
CAPTCHA_EXT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "captcha_solvers")
CAPSOLVER_EXT = os.path.join(CAPTCHA_EXT_DIR, "capsolver-chrome-extension")
NOPECHA_EXT = os.path.join(CAPTCHA_EXT_DIR, "NopeCHA-CAPTCHA-Solver")


def get_extensions(use_captcha_ext=True):
    """获取要加载的浏览器扩展路径列表"""
    exts = []
    if use_captcha_ext:
        if os.path.isdir(CAPSOLVER_EXT):
            exts.append(CAPSOLVER_EXT)
            logger.info("[EXT] 加载 Capsolver 扩展: %s", CAPSOLVER_EXT)
        if os.path.isdir(NOPECHA_EXT):
            exts.append(NOPECHA_EXT)
            logger.info("[EXT] 加载 NopeCHA 扩展: %s", NOPECHA_EXT)
    return exts


def run_single_provider(name: str, info: dict, proxy: str = "",
                        headless: bool = False, use_captcha_ext: bool = True,
                        keep_browser: bool = False) -> dict:
    """运行单个提供商注册"""
    module_name = info["module"]
    extra = info.get("extra", {})

    try:
        mod = importlib.import_module(module_name)
    except ImportError as e:
        return {"provider": name, "success": False, "error": f"import_error: {e}"}

    # 获取扩展列表
    extensions = get_extensions(use_captcha_ext)

    # 注入扩展到 launch_browser 调用
    # 修改模块的 launch_browser 默认参数
    import cdp_base
    original_launch = cdp_base.launch_browser

    def patched_launch(proxy="", headless=False, extensions=None, browser_type="chrome", window_size=(1280, 900)):
        return original_launch(
            proxy=proxy, headless=headless,
            extensions=extensions or get_extensions(use_captcha_ext),
            browser_type=browser_type, window_size=window_size,
        )

    cdp_base.launch_browser = patched_launch

    try:
        result = mod.register(proxy=proxy, headless=headless, keep_browser=keep_browser, **extra)
        return {
            "provider": name,
            "success": result.success,
            "email": result.email,
            "password": result.password,
            "error": result.error,
            "final_url": result.final_url,
        }
    except Exception as e:
        logger.exception("[ERROR] %s 注册异常", name)
        return {"provider": name, "success": False, "error": str(e)}
    finally:
        cdp_base.launch_browser = original_launch


def main():
    parser = argparse.ArgumentParser(description="实跑所有邮箱提供商注册")
    parser.add_argument("--proxy", default="", help="代理地址")
    parser.add_argument("--headless", action="store_true", help="无头模式")
    parser.add_argument("--providers", default="",
                        help="指定提供商，逗号分隔。留空跑全部")
    parser.add_argument("--no-captcha-ext", action="store_true",
                        help="不加载 CAPTCHA 求解扩展")
    parser.add_argument("--skip-phone", action="store_true",
                        help="跳过需要手机号的提供商")
    parser.add_argument("--delay", type=int, default=5,
                        help="每个提供商之间的等待秒数")
    parser.add_argument("--keep-browser", action="store_true",
                        help="注册完成后保持浏览器打开")
    parser.add_argument("--easy-only", action="store_true",
                        help="只跑简单的提供商（不需要手机号/CAPTCHA）")
    args = parser.parse_args()

    if args.providers:
        provider_names = [p.strip() for p in args.providers.split(",")]
    elif args.easy_only:
        provider_names = [n for n, i in PROVIDERS_TO_TEST.items()
                         if i["difficulty"] == "easy"]
    elif args.skip_phone:
        provider_names = [n for n, i in PROVIDERS_TO_TEST.items()
                         if not i["has_phone"]]
    else:
        provider_names = list(PROVIDERS_TO_TEST.keys())

    logger.info("=" * 70)
    logger.info("开始实跑邮箱注册测试")
    logger.info("提供商: %s", ", ".join(provider_names))
    logger.info("代理: %s", args.proxy or "无")
    logger.info("无头模式: %s", args.headless)
    logger.info("CAPTCHA 扩展: %s", not args.no_captcha_ext)
    logger.info("=" * 70)

    results = []
    for i, name in enumerate(provider_names, 1):
        info = PROVIDERS_TO_TEST.get(name)
        if not info:
            logger.warning("[SKIP] 未知提供商: %s", name)
            continue

        logger.info("\n[%d/%d] ========== %s ==========", i, len(provider_names), info["desc"])
        logger.info("[%d/%d] 难度: %s  需要手机号: %s", i, len(provider_names),
                     info["difficulty"], info["has_phone"])

        r = run_single_provider(
            name, info,
            proxy=args.proxy,
            headless=args.headless,
            use_captcha_ext=not args.no_captcha_ext,
            keep_browser=args.keep_browser,
        )
        results.append(r)

        status = "✓ 成功" if r["success"] else "✗ 失败"
        logger.info("[%d/%d] %s: %s  邮箱: %s  错误: %s",
                     i, len(provider_names), name, status,
                     r.get("email", ""), r.get("error", ""))

        if i < len(provider_names):
            logger.info("等待 %d 秒后继续...", args.delay)
            time.sleep(args.delay)

    # 汇总报告
    logger.info("\n" + "=" * 70)
    logger.info("实跑结果汇总")
    logger.info("=" * 70)

    success_count = 0
    for r in results:
        status = "✓" if r["success"] else "✗"
        if r["success"]:
            success_count += 1
        logger.info("  %s %-12s  邮箱: %-30s  错误: %s",
                     status, r["provider"], r.get("email", ""), r.get("error", ""))

    logger.info("-" * 70)
    logger.info("总计: %d/%d 成功", success_count, len(results))

    # 保存汇总
    summary_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..",
        "registered_accounts", "live_test_summary.json"
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
