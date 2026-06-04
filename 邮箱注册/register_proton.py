#!/usr/bin/env python3
"""
Proton Mail (proton.me) 独立注册脚本
用法: python register_proton.py [--headless] [--proxy http://ip:port]
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
    detect_captcha, handle_captcha_touch_press, wait_for_captcha_clear,
    wait_for_any_text, take_screenshot, save_result, random_password,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SIGNUP_URL = "https://account.proton.me/signup?plan=free&ref=prctbl20"


def register(account: AccountInfo | None = None,
             proxy: str = "", headless: bool = False,
             keep_browser: bool = False) -> RegistrationResult:
    """Proton Mail 注册主流程"""
    if account is None:
        account = generate_account("proton", "proton.me")

    result = RegistrationResult(
        provider="proton", domain="proton.me",
        email=account.email, password=account.password, username=account.username,
    )

    browser = None
    try:
        logger.info("=== Proton Mail 注册 ===")
        logger.info("邮箱: %s  密码: %s", account.email, account.password)

        # 1. 启动浏览器
        browser = launch_browser(proxy=proxy, headless=headless)
        result.browser = browser

        # 2. 打开注册页
        browser.navigate(SIGNUP_URL, timeout=30)
        time.sleep(3)

        # 3. 检查是否到了注册页
        url = browser.get_url()
        logger.info("[STEP] 页面: %s", url[:80])

        # 4. 选择免费计划（如果需要）
        free_plan_btn = browser.query_selector("#freePlan") or \
                        browser.query_selector("[data-testid='free-plan']") or \
                        browser.query_selector("button:has-text('Get for free')")
        if free_plan_btn:
            rect = browser.get_element_rect(free_plan_btn)
            if rect:
                browser.click_at(rect["center_x"], rect["center_y"])
                time.sleep(2)

        # 5. 填写用户名
        username_selectors = [
            "#username", "input[name='username']",
            "input[id*='email' i]", "input[autocomplete='username']",
        ]
        filled = False
        for sel in username_selectors:
            if wait_and_type(browser, sel, account.username, timeout=5):
                logger.info("[STEP] 用户名已填写: %s", account.username)
                filled = True
                break
        if not filled:
            # 尝试 JS 直接设置
            for sel in username_selectors:
                if set_value_and_dispatch(browser, sel, account.username):
                    filled = True
                    break

        # 6. 填写密码
        pwd_selectors = [
            "#password", "input[name='password']",
            "input[type='password']",
        ]
        for sel in pwd_selectors:
            if wait_and_type(browser, sel, account.password, timeout=5):
                logger.info("[STEP] 密码已填写")
                break

        time.sleep(0.5)

        # 7. 填写确认密码（如果有）
        confirm_selectors = [
            "#repeat-password", "#passwordc",
            "input[name='passwordConfirmation']",
        ]
        # Proton 可能只有一个密码框
        for sel in confirm_selectors:
            nid = browser.query_selector(sel)
            if nid and browser.is_element_visible(nid):
                wait_and_type(browser, sel, account.password, timeout=3)
                break

        time.sleep(1)

        # 8. 点击创建账号
        create_selectors = [
            "button[data-testid='create-account']",
            "button:has-text('Create account')",
            "button:has-text('创建账号')",
            "button.signUpProcess-btn-create",
            "button[type='submit']",
        ]
        clicked = False
        for sel in create_selectors:
            if wait_and_click(browser, sel, timeout=3):
                clicked = True
                logger.info("[STEP] 已点击创建账号")
                break

        if not clicked:
            # 尝试通用提交
            click_submit(browser)

        time.sleep(5)

        # 9. 处理验证码
        captcha = detect_captcha(browser)
        if captcha:
            logger.info("[CAPTCHA] 检测到验证码: %s", captcha)
            screenshot = take_screenshot(browser, "proton_captcha")
            result.screenshot_path = screenshot

            # 尝试触摸长按
            if "hsprotect" in captcha or "press and hold" in captcha:
                handle_captcha_touch_press(browser, duration=4.0)
                time.sleep(3)

            # 等待验证码清除
            if not wait_for_captcha_clear(browser, timeout=90):
                logger.warning("[CAPTCHA] 验证码未在超时内清除")
                result.error = f"captcha_timeout: {captcha}"
                take_screenshot(browser, "proton_captcha_timeout")
                if not keep_browser:
                    browser.close()
                return result

            logger.info("[CAPTCHA] 验证码已通过")

        # 10. 跳过恢复邮箱/手机步骤
        time.sleep(3)
        skip_selectors = [
            "button:has-text('Skip')", "button:has-text('跳过')",
            "button:has-text('Maybe later')", "button:has-text('稍后')",
            "a:has-text('Skip')", "[data-testid='skip']",
        ]
        for _ in range(3):  # 可能有多步需要跳过
            for sel in skip_selectors:
                if wait_and_click(browser, sel, timeout=3):
                    logger.info("[STEP] 跳过恢复选项")
                    time.sleep(2)
                    break

        # 11. 检测最终状态
        time.sleep(5)
        final_url = browser.get_url()
        result.final_url = final_url
        body = browser.get_body_text().lower()

        success_markers = [
            "welcome to proton", "inbox", "收件箱",
            "mail.proton.me", "account.proton.me/mail",
        ]
        if any(m in body or m in final_url.lower() for m in success_markers):
            result.success = True
            logger.info("[OK] Proton Mail 注册成功! %s", account.email)
        elif "verification" in body or "verify" in body:
            result.error = "needs_verification"
            logger.warning("[WARN] 需要额外验证步骤")
        else:
            result.error = f"unknown_state: url={final_url[:80]}"
            logger.warning("[WARN] 未知状态: %s", final_url[:80])

        take_screenshot(browser, "proton_final")

        if keep_browser:
            result.browser = browser
        else:
            browser.close()

    except Exception as e:
        result.error = str(e)
        logger.exception("[ERROR] Proton 注册异常")
        if browser and not keep_browser:
            try:
                take_screenshot(browser, "proton_error")
                browser.close()
            except Exception:
                pass

    save_result(result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Proton Mail 注册")
    parser.add_argument("--headless", action="store_true", help="无头模式")
    parser.add_argument("--proxy", default="", help="代理地址 http://ip:port")
    args = parser.parse_args()

    r = register(proxy=args.proxy, headless=args.headless)
    print(f"\n结果: {'成功' if r.success else '失败'}")
    print(f"邮箱: {r.email}")
    print(f"密码: {r.password}")
    if r.error:
        print(f"错误: {r.error}")
