#!/usr/bin/env python3
"""
Zoho Mail (zoho.com) 独立注册脚本
用法: python register_zoho.py [--headless] [--proxy http://ip:port]
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
    select_dropdown_by_text, detect_captcha, wait_for_captcha_clear,
    take_screenshot, save_result,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SIGNUP_URL = "https://accounts.zoho.com/signup"


def register(account: AccountInfo | None = None,
             proxy: str = "", headless: bool = False,
             keep_browser: bool = False) -> RegistrationResult:
    if account is None:
        account = generate_account("zoho", "zohomail.com")

    result = RegistrationResult(
        provider="zoho", domain="zohomail.com",
        email=account.email, password=account.password, username=account.username,
    )

    browser = None
    try:
        logger.info("=== Zoho Mail 注册 ===")
        logger.info("邮箱: %s  密码: %s", account.email, account.password)

        browser = launch_browser(proxy=proxy, headless=headless)
        result.browser = browser

        browser.navigate(SIGNUP_URL, timeout=30)
        time.sleep(4)

        # Zoho 注册表单
        # 邮箱/手机号
        for sel in ["#luid", "input[name='luid']", "input[id*='email' i]",
                     "input[type='email']", "input[name='email']"]:
            if wait_and_type(browser, sel, account.email, timeout=5):
                logger.info("[STEP] 邮箱: %s", account.email)
                break

        time.sleep(0.5)

        # 密码
        for sel in ["#lupasswd", "input[name='lupasswd']", "input[name='password']",
                     "input[type='password']"]:
            if wait_and_type(browser, sel, account.password, timeout=5):
                logger.info("[STEP] 密码已填写")
                break

        time.sleep(0.5)

        # 姓名
        for sel in ["#lufirstname", "input[name='firstname']", "input[id*='first' i]"]:
            wait_and_type(browser, sel, account.first_name, timeout=3)
        for sel in ["#lulastname", "input[name='lastname']", "input[id*='last' i]"]:
            wait_and_type(browser, sel, account.last_name, timeout=3)

        # 手机号（Zoho 可能强制要求）
        phone_sel = ["#phonefield", "input[name='phone']", "input[id*='phone' i]"]
        phone_found = False
        for sel in phone_sel:
            nid = browser.query_selector(sel)
            if nid and browser.is_element_visible(nid):
                phone_found = True
                break

        if phone_found:
            result.error = "phone_verification_required"
            logger.warning("[WARN] Zoho 要求手机号验证")
            take_screenshot(browser, "zoho_phone_required")
            if keep_browser:
                result.browser = browser
            else:
                browser.close()
            save_result(result)
            return result

        # 提交
        for sel in ["#lupregister", "button[type='submit']",
                     "button:has-text('Sign Up')", "button:has-text('Register')",
                     "input[type='submit']"]:
            if wait_and_click(browser, sel, timeout=3):
                logger.info("[STEP] 已提交")
                break

        time.sleep(8)

        # 验证码
        captcha = detect_captcha(browser)
        if captcha:
            logger.info("[CAPTCHA] 检测到: %s", captcha)
            take_screenshot(browser, "zoho_captcha")
            if wait_for_captcha_clear(browser, timeout=60):
                logger.info("[CAPTCHA] 已通过")

        # 结果检测
        final_url = browser.get_url()
        result.final_url = final_url
        body = browser.get_body_text().lower()

        success_markers = ["welcome", "inbox", "successfully", "verify your email"]
        if any(m in body for m in success_markers):
            result.success = True
            logger.info("[OK] Zoho 注册成功! %s", account.email)
        elif "already" in body or "exists" in body:
            result.error = "username_taken"
        else:
            result.error = f"unknown: {final_url[:80]}"

        take_screenshot(browser, "zoho_final")
        if keep_browser:
            result.browser = browser
        else:
            browser.close()

    except Exception as e:
        result.error = str(e)
        logger.exception("[ERROR] Zoho 注册异常")
        if browser and not keep_browser:
            try:
                take_screenshot(browser, "zoho_error")
                browser.close()
            except Exception:
                pass

    save_result(result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Zoho Mail 注册")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--proxy", default="")
    args = parser.parse_args()

    r = register(proxy=args.proxy, headless=args.headless)
    print(f"\n结果: {'成功' if r.success else '失败'}  邮箱: {r.email}  密码: {r.password}")
    if r.error:
        print(f"错误: {r.error}")
