#!/usr/bin/env python3
"""
AOL Mail (aol.com) 独立注册脚本
用法: python register_aol.py [--headless] [--proxy http://ip:port]
AOL 使用 Yahoo 的注册系统。
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

SIGNUP_URL = "https://login.aol.com/account/create"


def register(account: AccountInfo | None = None,
             proxy: str = "", headless: bool = False,
             keep_browser: bool = False) -> RegistrationResult:
    if account is None:
        account = generate_account("aol", "aol.com")

    result = RegistrationResult(
        provider="aol", domain="aol.com",
        email=account.email, password=account.password, username=account.username,
    )

    browser = None
    try:
        logger.info("=== AOL Mail 注册 ===")
        logger.info("邮箱: %s  密码: %s", account.email, account.password)

        browser = launch_browser(proxy=proxy, headless=headless)
        result.browser = browser

        browser.navigate(SIGNUP_URL, timeout=30)
        time.sleep(4)

        # 姓
        for sel in ["#user-first-name", "input[name='firstName']",
                     "input[id*='first' i]", "input[autocomplete='given-name']"]:
            if wait_and_type(browser, sel, account.first_name, timeout=5):
                logger.info("[STEP] 姓名: %s %s", account.first_name, account.last_name)
                break

        # 名
        for sel in ["#user-last-name", "input[name='lastName']",
                     "input[id*='last' i]", "input[autocomplete='family-name']"]:
            wait_and_type(browser, sel, account.last_name, timeout=3)

        time.sleep(0.5)

        # 邮箱地址
        for sel in ["#user-name", "input[name='userId']", "input[name='username']",
                     "input[id*='email' i]", "input[type='email']"]:
            if wait_and_type(browser, sel, account.username, timeout=5):
                logger.info("[STEP] 用户名: %s", account.username)
                break

        # 密码
        for sel in ["#user-passwd", "input[name='password']", "input[type='password']"]:
            if wait_and_type(browser, sel, account.password, timeout=5):
                logger.info("[STEP] 密码已填写")
                break

        # 出生日期
        for sel in ["#user-dob-month", "select[name='mm']", "select[id*='month' i]"]:
            select_dropdown_by_text(browser, sel, account.birth_month)
        for sel in ["#user-dob-day", "input[name='dd']", "input[id*='day' i]"]:
            set_value_and_dispatch(browser, sel, account.birth_day)
        for sel in ["#user-dob-year", "input[name='yyyy']", "input[id*='year' i]"]:
            set_value_and_dispatch(browser, sel, account.birth_year)

        time.sleep(1)

        # 提交
        for sel in ["button[type='submit']", "#reg-submit-button",
                     "button:has-text('Continue')", "button:has-text('Next')",
                     "button:has-text('创建')"]:
            if wait_and_click(browser, sel, timeout=3):
                logger.info("[STEP] 已提交")
                break

        time.sleep(8)

        # 验证码
        captcha = detect_captcha(browser)
        if captcha:
            logger.info("[CAPTCHA] 检测到: %s", captcha)
            take_screenshot(browser, "aol_captcha")
            if wait_for_captcha_clear(browser, timeout=60):
                logger.info("[CAPTCHA] 已通过")
            else:
                result.error = f"captcha: {captcha}"

        # 手机号验证检测（AOL 可能要求）
        body = browser.get_body_text().lower()
        final_url = browser.get_url()
        result.final_url = final_url

        phone_markers = ["phone number", "mobile number", "手机号", "电话号码",
                         "verify your phone", "短信验证"]
        if any(m in body for m in phone_markers):
            result.error = "phone_verification_required"
            logger.warning("[WARN] AOL 要求手机号验证")
            take_screenshot(browser, "aol_phone_required")
            if keep_browser:
                result.browser = browser
            else:
                browser.close()
            save_result(result)
            return result

        # 成功检测
        success_markers = [
            "welcome", "inbox", "successfully", "account created",
            "mail.aol.com", "start exploring",
        ]
        if any(m in body for m in success_markers) or "mail.aol" in final_url:
            result.success = True
            logger.info("[OK] AOL 注册成功! %s", account.email)
        elif "already" in body or "taken" in body:
            result.error = "username_taken"
        else:
            result.error = f"unknown: {final_url[:80]}"

        take_screenshot(browser, "aol_final")
        if keep_browser:
            result.browser = browser
        else:
            browser.close()

    except Exception as e:
        result.error = str(e)
        logger.exception("[ERROR] AOL 注册异常")
        if browser and not keep_browser:
            try:
                take_screenshot(browser, "aol_error")
                browser.close()
            except Exception:
                pass

    save_result(result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AOL Mail 注册")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--proxy", default="")
    args = parser.parse_args()

    r = register(proxy=args.proxy, headless=args.headless)
    print(f"\n结果: {'成功' if r.success else '失败'}  邮箱: {r.email}  密码: {r.password}")
    if r.error:
        print(f"错误: {r.error}")
