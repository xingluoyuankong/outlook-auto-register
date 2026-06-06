#!/usr/bin/env python3
"""
Mail.com 独立注册脚本
用法: python register_mailcom.py [--headless] [--proxy http://ip:port]
Mail.com 注册通常不需要手机号验证。
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

SIGNUP_URL = "https://service.mail.com/registration.html"


def register(account: AccountInfo | None = None,
             proxy: str = "", headless: bool = False,
             keep_browser: bool = False) -> RegistrationResult:
    if account is None:
        account = generate_account("mailcom", "mail.com")

    result = RegistrationResult(
        provider="mailcom", domain="mail.com",
        email=account.email, password=account.password, username=account.username,
    )

    browser = None
    try:
        logger.info("=== Mail.com 注册 ===")
        logger.info("邮箱: %s  密码: %s", account.email, account.password)

        browser = launch_browser(proxy=proxy, headless=headless)
        result.browser = browser

        browser.navigate(SIGNUP_URL, timeout=30)
        time.sleep(4)

        # 邮箱地址（用户名）
        for sel in ["#username", "input[name='username']", "input[id*='mail' i]",
                     "input[type='email']", "input[autocomplete='username']"]:
            if wait_and_type(browser, sel, account.username, timeout=5):
                logger.info("[STEP] 用户名: %s", account.username)
                break

        # 选择域名（如果有下拉框）
        for sel in ["select[name*='domain' i]", "select[id*='domain' i]"]:
            select_dropdown_by_text(browser, sel, "mail.com")

        time.sleep(0.5)

        # 密码
        for sel in ["#password", "input[name='password']", "input[type='password']"]:
            if wait_and_type(browser, sel, account.password, timeout=5):
                logger.info("[STEP] 密码已填写")
                break

        # 确认密码
        for sel in ["#passwordConfirm", "input[name*='confirm' i]",
                     "input[name*='passwordConfirm' i]"]:
            wait_and_type(browser, sel, account.password, timeout=3)

        # 姓名
        for sel in ["#firstName", "input[name='firstName']"]:
            wait_and_type(browser, sel, account.first_name, timeout=3)
        for sel in ["#lastName", "input[name='lastName']"]:
            wait_and_type(browser, sel, account.last_name, timeout=3)

        # 出生日期
        for sel in ["select[name*='birthMonth' i]", "select[id*='birthMonth' i]",
                     "select[name*='month' i]"]:
            select_dropdown_by_text(browser, sel, account.birth_month)
        for sel in ["select[name*='birthDay' i]", "select[id*='birthDay' i]",
                     "select[name*='day' i]"]:
            select_dropdown_by_text(browser, sel, account.birth_day)
        for sel in ["select[name*='birthYear' i]", "select[id*='birthYear' i]",
                     "select[name*='year' i]"]:
            select_dropdown_by_text(browser, sel, account.birth_year)

        # 性别（如果有）
        for sel in ["select[name*='gender' i]", "select[id*='gender' i]"]:
            select_dropdown_by_text(browser, sel, "male")

        # 国家
        for sel in ["select[name*='country' i]", "select[id*='country' i]"]:
            select_dropdown_by_text(browser, sel, "United States")

        time.sleep(1)

        # 勾选条款
        for sel in ["input[type='checkbox'][id*='terms' i]",
                     "input[type='checkbox'][id*='agree' i]",
                     "input[type='checkbox'][name*='terms' i]"]:
            nid = browser.query_selector(sel)
            if nid and browser.is_element_visible(nid):
                rect = browser.get_element_rect(nid)
                if rect:
                    browser.click_at(rect["center_x"], rect["center_y"])
                    break

        time.sleep(0.5)

        # 提交
        for sel in ["button[type='submit']", "input[type='submit']",
                     "button:has-text('Register')", "button:has-text('Sign Up')",
                     "button:has-text('Create')", "#registerButton"]:
            if wait_and_click(browser, sel, timeout=3):
                logger.info("[STEP] 已提交")
                break

        time.sleep(8)

        # 验证码
        captcha = detect_captcha(browser)
        if captcha:
            logger.info("[CAPTCHA] 检测到: %s", captcha)
            take_screenshot(browser, "mailcom_captcha")
            if wait_for_captcha_clear(browser, timeout=60):
                logger.info("[CAPTCHA] 已通过")

        # 结果检测
        final_url = browser.get_url()
        result.final_url = final_url
        body = browser.get_body_text().lower()

        success_markers = [
            "welcome", "successfully", "account created", "inbox",
            "check your email", "verify your email",
        ]
        if any(m in body for m in success_markers):
            result.success = True
            logger.info("[OK] Mail.com 注册成功! %s", account.email)
        elif "already" in body or "taken" in body or "exists" in body:
            result.error = "username_taken"
        else:
            result.error = f"unknown: {final_url[:80]}"

        take_screenshot(browser, "mailcom_final")
        if keep_browser:
            result.browser = browser
        else:
            browser.close()

    except Exception as e:
        result.error = str(e)
        logger.exception("[ERROR] Mail.com 注册异常")
        if browser and not keep_browser:
            try:
                take_screenshot(browser, "mailcom_error")
                browser.close()
            except Exception:
                pass

    save_result(result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mail.com 注册")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--proxy", default="")
    args = parser.parse_args()

    r = register(proxy=args.proxy, headless=args.headless)
    print(f"\n结果: {'成功' if r.success else '失败'}  邮箱: {r.email}  密码: {r.password}")
    if r.error:
        print(f"错误: {r.error}")
