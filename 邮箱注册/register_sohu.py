#!/usr/bin/env python3
"""
搜狐邮箱 (sohu.com) 独立注册脚本
用法: python register_sohu.py [--headless] [--proxy http://ip:port]
"""

import argparse
import logging
import sys
import time
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cdp_base import (
    AccountInfo, RegistrationResult, generate_account, launch_browser,
    wait_and_click, wait_and_type, set_value_and_dispatch, click_submit,
    detect_captcha, wait_for_captcha_clear, take_screenshot, save_result,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SIGNUP_URL = "https://mail.sohu.com/reg/signup"


def register(account: AccountInfo | None = None,
             proxy: str = "", headless: bool = False,
             keep_browser: bool = False) -> RegistrationResult:
    if account is None:
        account = generate_account("sohu", "sohu.com")

    result = RegistrationResult(
        provider="sohu", domain="sohu.com",
        email=account.email, password=account.password, username=account.username,
    )

    browser = None
    try:
        logger.info("=== Sohu 邮箱注册 ===")
        logger.info("邮箱: %s  密码: %s", account.email, account.password)

        browser = launch_browser(proxy=proxy, headless=headless)
        result.browser = browser

        browser.navigate(SIGNUP_URL, timeout=30)
        time.sleep(4)

        # 用户名
        for sel in ["#username", "input[name='username']", "input[id*='user' i]",
                     "input[placeholder*='用户名']", "input[type='text']"]:
            if wait_and_type(browser, sel, account.username, timeout=5):
                logger.info("[STEP] 用户名: %s", account.username)
                break

        # 密码
        for sel in ["#password", "input[name='password']", "input[type='password']"]:
            if wait_and_type(browser, sel, account.password, timeout=5):
                logger.info("[STEP] 密码已填写")
                break

        # 确认密码
        for sel in ["#password2", "input[name*='confirm' i]"]:
            wait_and_type(browser, sel, account.password, timeout=3)

        # 手机号检测
        for sel in ["input[name='phone']", "input[type='tel']",
                     "input[placeholder*='手机']"]:
            nid = browser.query_selector(sel)
            if nid and browser.is_element_visible(nid):
                result.error = "phone_verification_required"
                logger.warning("[WARN] Sohu 要求手机号验证")
                take_screenshot(browser, "sohu_phone_required")
                if keep_browser:
                    result.browser = browser
                else:
                    browser.close()
                save_result(result)
                return result

        # 验证码
        captcha = detect_captcha(browser)
        if captcha:
            logger.info("[CAPTCHA] 检测到: %s", captcha)
            take_screenshot(browser, "sohu_captcha")
            if wait_for_captcha_clear(browser, timeout=60):
                logger.info("[CAPTCHA] 已通过")

        time.sleep(1)

        # 提交
        for sel in ["button[type='submit']", "input[type='submit']",
                     "button:has-text('注册')", "a:has-text('注册')"]:
            if wait_and_click(browser, sel, timeout=3):
                logger.info("[STEP] 已提交")
                break

        time.sleep(8)

        # 结果
        final_url = browser.get_url()
        result.final_url = final_url
        body = browser.get_body_text().lower()

        success_markers = ["成功", "welcome", "登录", "收件箱", "mail.sohu"]
        if any(m in body for m in success_markers):
            result.success = True
            logger.info("[OK] Sohu 注册成功! %s", account.email)
        elif "已存在" in body or "已被" in body:
            result.error = "username_taken"
        else:
            result.error = f"unknown: {final_url[:80]}"

        take_screenshot(browser, "sohu_final")
        if keep_browser:
            result.browser = browser
        else:
            browser.close()

    except Exception as e:
        result.error = str(e)
        logger.exception("[ERROR] Sohu 注册异常")
        if browser and not keep_browser:
            try:
                take_screenshot(browser, "sohu_error")
                browser.close()
            except Exception:
                pass

    save_result(result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sohu 邮箱注册")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--proxy", default="")
    args = parser.parse_args()

    r = register(proxy=args.proxy, headless=args.headless)
    print(f"\n结果: {'成功' if r.success else '失败'}  邮箱: {r.email}  密码: {r.password}")
    if r.error:
        print(f"错误: {r.error}")
