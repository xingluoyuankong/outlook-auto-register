#!/usr/bin/env python3
"""
Tutanota (tuta.com) 独立注册脚本
用法: python register_tutanota.py [--headless] [--proxy http://ip:port]
Tutanota 注册通常不需要手机号验证。
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

SIGNUP_URL = "https://app.tuta.com/signup"


def register(account: AccountInfo | None = None,
             proxy: str = "", headless: bool = False,
             keep_browser: bool = False) -> RegistrationResult:
    if account is None:
        account = generate_account("tutanota", "tuta.com")

    result = RegistrationResult(
        provider="tutanota", domain="tuta.com",
        email=account.email, password=account.password, username=account.username,
    )

    browser = None
    try:
        logger.info("=== Tutanota 注册 ===")
        logger.info("邮箱: %s  密码: %s", account.email, account.password)

        browser = launch_browser(proxy=proxy, headless=headless)
        result.browser = browser

        browser.navigate(SIGNUP_URL, timeout=30)
        time.sleep(5)

        # Tutanota 新注册流程：
        # 1. 选择免费计划
        for sel in ["button:has-text('Free')", "button:has-text('免费')",
                     "[data-testid='free-plan']", ".plan-free"]:
            if wait_and_click(browser, sel, timeout=5):
                logger.info("[STEP] 选择免费计划")
                time.sleep(2)
                break

        # 2. 选择域名
        for sel in ["button:has-text('tuta.com')", "button:has-text('tutanota.com')",
                     "select[id*='domain' i]"]:
            if wait_and_click(browser, sel, timeout=3):
                logger.info("[STEP] 选择域名")
                break

        time.sleep(1)

        # 3. 填写邮箱地址
        for sel in ["input[name='mailAddress']", "input[id*='email' i]",
                     "input[placeholder*='email' i]", "input[type='email']",
                     "input[autocomplete='email']"]:
            if wait_and_type(browser, sel, account.username, timeout=5):
                logger.info("[STEP] 用户名: %s", account.username)
                break

        time.sleep(0.5)

        # 4. 填写密码
        pwd_sel = ["#new-password", "input[name='newPassword']",
                    "input[type='password'][id*='new' i]",
                    "input[type='password']"]
        for sel in pwd_sel:
            if wait_and_type(browser, sel, account.password, timeout=5):
                logger.info("[STEP] 密码已填写")
                break

        # 5. 确认密码
        for sel in ["#repeat-password", "input[name='repeatPassword']",
                     "input[type='password'][id*='repeat' i]",
                     "input[type='password'][id*='confirm' i]"]:
            if wait_and_type(browser, sel, account.password, timeout=3):
                break

        time.sleep(1)

        # 6. 勾选条款
        for sel in ["input[type='checkbox']", "label:has-text('agree')"]:
            nid = browser.query_selector(sel)
            if nid and browser.is_element_visible(nid):
                rect = browser.get_element_rect(nid)
                if rect:
                    browser.click_at(rect["center_x"], rect["center_y"])
                    break

        time.sleep(0.5)

        # 7. 点击注册/下一步
        for sel in ["button[type='submit']", "button:has-text('Next')",
                     "button:has-text('Sign up')", "button:has-text('Register')",
                     "button:has-text('下一步')", "button:has-text('注册')"]:
            if wait_and_click(browser, sel, timeout=3):
                logger.info("[STEP] 已提交")
                break

        time.sleep(8)

        # 8. 处理验证码
        captcha = detect_captcha(browser)
        if captcha:
            logger.info("[CAPTCHA] 检测到: %s", captcha)
            take_screenshot(browser, "tuta_captcha")
            if wait_for_captcha_clear(browser, timeout=60):
                logger.info("[CAPTCHA] 已通过")

        # 9. 结果检测
        final_url = browser.get_url()
        result.final_url = final_url
        body = browser.get_body_text().lower()

        success_markers = [
            "welcome", "inbox", "mail", "successfully",
            "account created", "your account",
        ]
        if any(m in body for m in success_markers) or "mail" in final_url:
            result.success = True
            logger.info("[OK] Tutanota 注册成功! %s", account.email)
        elif "already" in body or "taken" in body:
            result.error = "username_taken"
        elif "captcha" in body:
            result.error = "captcha_blocked"
        else:
            result.error = f"unknown: {final_url[:80]}"

        take_screenshot(browser, "tuta_final")
        if keep_browser:
            result.browser = browser
        else:
            browser.close()

    except Exception as e:
        result.error = str(e)
        logger.exception("[ERROR] Tutanota 注册异常")
        if browser and not keep_browser:
            try:
                take_screenshot(browser, "tuta_error")
                browser.close()
            except Exception:
                pass

    save_result(result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tutanota 注册")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--proxy", default="")
    args = parser.parse_args()

    r = register(proxy=args.proxy, headless=args.headless)
    print(f"\n结果: {'成功' if r.success else '失败'}  邮箱: {r.email}  密码: {r.password}")
    if r.error:
        print(f"错误: {r.error}")
