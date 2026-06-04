#!/usr/bin/env python3
"""
Mail.ru 独立注册脚本
用法: python register_mailru.py [--headless] [--proxy http://ip:port]
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

SIGNUP_URL = "https://account.mail.ru/signup?rf=auth.mail.ru&from=main"


def register(account: AccountInfo | None = None,
             proxy: str = "", headless: bool = False,
             keep_browser: bool = False) -> RegistrationResult:
    if account is None:
        account = generate_account("mailru", "mail.ru")

    result = RegistrationResult(
        provider="mailru", domain="mail.ru",
        email=account.email, password=account.password, username=account.username,
    )

    browser = None
    try:
        logger.info("=== Mail.ru 注册 ===")
        logger.info("邮箱: %s  密码: %s", account.email, account.password)

        browser = launch_browser(proxy=proxy, headless=headless)
        result.browser = browser

        browser.navigate(SIGNUP_URL, timeout=30)
        time.sleep(4)

        # 姓名
        for sel in ["input[name='firstname']", "input[data-test-id='first-name-input']",
                     "input[autocomplete='given-name']"]:
            if wait_and_type(browser, sel, account.first_name, timeout=5):
                logger.info("[STEP] 姓名: %s %s", account.first_name, account.last_name)
                break

        for sel in ["input[name='lastname']", "input[data-test-id='last-name-input']",
                     "input[autocomplete='family-name']"]:
            wait_and_type(browser, sel, account.last_name, timeout=3)

        # 出生日期
        for sel in ["select[name*='day' i]", "input[name*='day' i]"]:
            if set_value_and_dispatch(browser, sel, account.birth_day):
                break
        for sel in ["select[name*='month' i]"]:
            select_dropdown_by_text(browser, sel, account.birth_month)
        for sel in ["select[name*='year' i]", "input[name*='year' i]"]:
            if set_value_and_dispatch(browser, sel, account.birth_year):
                break

        # 性别
        for sel in ["input[name='gender'][value='male']", "input[type='radio'][value='male']"]:
            nid = browser.query_selector(sel)
            if nid and browser.is_element_visible(nid):
                rect = browser.get_element_rect(nid)
                if rect:
                    browser.click_at(rect["center_x"], rect["center_y"])
                    break

        # 邮箱地址
        for sel in ["input[name='login']", "input[data-test-id='login-input']",
                     "input[id*='email' i]"]:
            if wait_and_type(browser, sel, account.username, timeout=5):
                logger.info("[STEP] 用户名: %s", account.username)
                break

        # 选择域名
        for sel in ["select[name='domain']", "div[data-test-id='domain-select']"]:
            select_dropdown_by_text(browser, sel, "mail.ru")

        # 密码
        for sel in ["input[name='password']", "input[data-test-id='password-input']",
                     "input[type='password']"]:
            if wait_and_type(browser, sel, account.password, timeout=5):
                logger.info("[STEP] 密码已填写")
                break

        # 确认密码
        for sel in ["input[name='password_confirm']", "input[data-test-id='password-confirm']"]:
            wait_and_type(browser, sel, account.password, timeout=3)

        # 手机号检测
        body_text = browser.get_body_text().lower()
        phone_markers = ["phone", "mobile", "电话", "手机", "телефон"]
        if any(m in body_text for m in phone_markers):
            # 检查是否有手机号输入框
            for sel in ["input[name='phone']", "input[type='tel']",
                         "input[id*='phone' i]", "input[data-test-id*='phone']"]:
                nid = browser.query_selector(sel)
                if nid and browser.is_element_visible(nid):
                    result.error = "phone_verification_required"
                    logger.warning("[WARN] Mail.ru 要求手机号验证")
                    take_screenshot(browser, "mailru_phone_required")
                    if keep_browser:
                        result.browser = browser
                    else:
                        browser.close()
                    save_result(result)
                    return result

        time.sleep(1)

        # 提交
        for sel in ["button[type='submit']", "button[data-test-id='signup-submit']",
                     "button:has-text('Sign Up')", "button:has-text('Register')",
                     "button:has-text('Зарегистрироваться')"]:
            if wait_and_click(browser, sel, timeout=3):
                logger.info("[STEP] 已提交")
                break

        time.sleep(8)

        # 验证码
        captcha = detect_captcha(browser)
        if captcha:
            logger.info("[CAPTCHA] 检测到: %s", captcha)
            take_screenshot(browser, "mailru_captcha")
            if wait_for_captcha_clear(browser, timeout=60):
                logger.info("[CAPTCHA] 已通过")

        # 结果检测
        final_url = browser.get_url()
        result.final_url = final_url
        body = browser.get_body_text().lower()

        success_markers = ["welcome", "inbox", "成功", "успешно", "e.mail.ru"]
        if any(m in body for m in success_markers) or "e.mail.ru" in final_url:
            result.success = True
            logger.info("[OK] Mail.ru 注册成功! %s", account.email)
        elif "already" in body or "exists" in body or "занят" in body:
            result.error = "username_taken"
        else:
            result.error = f"unknown: {final_url[:80]}"

        take_screenshot(browser, "mailru_final")
        if keep_browser:
            result.browser = browser
        else:
            browser.close()

    except Exception as e:
        result.error = str(e)
        logger.exception("[ERROR] Mail.ru 注册异常")
        if browser and not keep_browser:
            try:
                take_screenshot(browser, "mailru_error")
                browser.close()
            except Exception:
                pass

    save_result(result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mail.ru 注册")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--proxy", default="")
    args = parser.parse_args()

    r = register(proxy=args.proxy, headless=args.headless)
    print(f"\n结果: {'成功' if r.success else '失败'}  邮箱: {r.email}  密码: {r.password}")
    if r.error:
        print(f"错误: {r.error}")
