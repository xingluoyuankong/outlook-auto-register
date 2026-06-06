#!/usr/bin/env python3
"""
GMX Mail (gmx.com) 独立注册脚本
用法: python register_gmx.py [--headless] [--proxy http://ip:port]
GMX 注册通常不需要手机号验证，是最容易跑通的提供商之一。
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
    select_dropdown_by_text, detect_captcha, wait_for_any_text,
    take_screenshot, save_result,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SIGNUP_URL = "https://signup.gmx.com/"


def register(account: AccountInfo | None = None,
             proxy: str = "", headless: bool = False,
             keep_browser: bool = False) -> RegistrationResult:
    if account is None:
        account = generate_account("gmx", "gmx.com")

    result = RegistrationResult(
        provider="gmx", domain="gmx.com",
        email=account.email, password=account.password, username=account.username,
    )

    browser = None
    try:
        logger.info("=== GMX Mail 注册 ===")
        logger.info("邮箱: %s  密码: %s", account.email, account.password)

        browser = launch_browser(proxy=proxy, headless=headless)
        result.browser = browser

        browser.navigate(SIGNUP_URL, timeout=30)
        time.sleep(4)

        # GMX 注册表单字段
        # 用户名
        for sel in ["#username", "input[name='username']", "input[id*='user' i]",
                     "input[autocomplete='username']"]:
            if wait_and_type(browser, sel, account.username, timeout=5):
                logger.info("[STEP] 用户名: %s", account.username)
                break

        time.sleep(0.5)

        # 密码
        for sel in ["#password", "input[name='password']", "input[type='password']"]:
            if wait_and_type(browser, sel, account.password, timeout=5):
                logger.info("[STEP] 密码已填写")
                break

        time.sleep(0.3)

        # 确认密码
        for sel in ["#confirmPassword", "input[name='confirmPassword']",
                     "input[name='passwordConfirmation']"]:
            if wait_and_type(browser, sel, account.password, timeout=3):
                break

        # 姓名
        for sel in ["#firstName", "input[name='firstName']", "input[autocomplete='given-name']"]:
            if wait_and_type(browser, sel, account.first_name, timeout=3):
                logger.info("[STEP] 姓名: %s %s", account.first_name, account.last_name)
                break

        for sel in ["#lastName", "input[name='lastName']", "input[autocomplete='family-name']"]:
            wait_and_type(browser, sel, account.last_name, timeout=3)

        # 出生日期 - GMX 通常有下拉框
        for sel in ["select[name*='month' i]", "select[id*='month' i]",
                     "[aria-label*='month' i]"]:
            if select_dropdown_by_text(browser, sel, account.birth_month):
                break
        for sel in ["select[name*='day' i]", "select[id*='day' i]",
                     "[aria-label*='day' i]"]:
            if select_dropdown_by_text(browser, sel, account.birth_day):
                break
        for sel in ["select[name*='year' i]", "select[id*='year' i]",
                     "[aria-label*='year' i]"]:
            if select_dropdown_by_text(browser, sel, account.birth_year):
                break

        # 国家/地区
        for sel in ["select[name*='country' i]", "select[id*='country' i]"]:
            select_dropdown_by_text(browser, sel, "United States")

        time.sleep(1)

        # 勾选条款（如果有）
        for sel in ["input[type='checkbox'][name*='terms' i]",
                     "input[type='checkbox'][id*='terms' i]",
                     "input[type='checkbox'][id*='agree' i]"]:
            nid = browser.query_selector(sel)
            if nid and browser.is_element_visible(nid):
                rect = browser.get_element_rect(nid)
                if rect:
                    browser.click_at(rect["center_x"], rect["center_y"])
                    break

        time.sleep(0.5)

        # 提交
        for sel in ["button[type='submit']", "input[type='submit']",
                     "button:has-text('Sign Up')", "button:has-text('Register')",
                     "button:has-text('Create')", "#registerButton"]:
            if wait_and_click(browser, sel, timeout=3):
                logger.info("[STEP] 已提交注册")
                break

        time.sleep(8)

        # 检查结果
        final_url = browser.get_url()
        result.final_url = final_url
        body = browser.get_body_text().lower()

        # 验证码处理
        captcha = detect_captcha(browser)
        if captcha:
            logger.info("[CAPTCHA] 检测到: %s", captcha)
            take_screenshot(browser, "gmx_captcha")
            # 等待自动通过或手动处理
            from cdp_base import wait_for_captcha_clear
            if wait_for_captcha_clear(browser, timeout=60):
                logger.info("[CAPTCHA] 已通过")
            else:
                result.error = f"captcha: {captcha}"

        # 成功检测
        success_markers = [
            "welcome", "inbox", "successfully", "account created",
            "mail.gmx.com", "account created successfully",
        ]
        if any(m in body for m in success_markers) or "mail.gmx" in final_url:
            result.success = True
            logger.info("[OK] GMX 注册成功! %s", account.email)
        elif "already" in body or "taken" in body:
            result.error = "username_taken"
        else:
            result.error = f"unknown: {final_url[:80]}"

        take_screenshot(browser, "gmx_final")
        if keep_browser:
            result.browser = browser
        else:
            browser.close()

    except Exception as e:
        result.error = str(e)
        logger.exception("[ERROR] GMX 注册异常")
        if browser and not keep_browser:
            try:
                take_screenshot(browser, "gmx_error")
                browser.close()
            except Exception:
                pass

    save_result(result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GMX Mail 注册")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--proxy", default="")
    args = parser.parse_args()

    r = register(proxy=args.proxy, headless=args.headless)
    print(f"\n结果: {'成功' if r.success else '失败'}  邮箱: {r.email}  密码: {r.password}")
    if r.error:
        print(f"错误: {r.error}")
