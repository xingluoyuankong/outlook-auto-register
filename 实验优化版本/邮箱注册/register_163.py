#!/usr/bin/env python3
"""
网易 163/126/Yeah 邮箱独立注册脚本
用法: python register_163.py [--headless] [--proxy http://ip:port] [--domain 163]
支持 163.com / 126.com / yeah.net
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
    take_screenshot, save_result, random_string,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DOMAIN_URLS = {
    "163": ("163.com", "http://reg.email.163.com/unireg/call.do?cmd=register.entrance&from=163mail"),
    "126": ("126.com", "http://reg.email.163.com/unireg/call.do?cmd=register.entrance&from=126mail"),
    "yeah": ("yeah.net", "http://reg.email.163.com/unireg/call.do?cmd=register.entrance&from=yeah"),
}


def register(account: AccountInfo | None = None,
             proxy: str = "", headless: bool = False,
             keep_browser: bool = False, domain_key: str = "163") -> RegistrationResult:
    domain, signup_url = DOMAIN_URLS.get(domain_key, DOMAIN_URLS["163"])

    if account is None:
        account = generate_account(f"netease{domain_key}", domain)

    result = RegistrationResult(
        provider=f"netease{domain_key}", domain=domain,
        email=account.email, password=account.password, username=account.username,
    )

    browser = None
    try:
        logger.info("=== %s 邮箱注册 ===", domain)
        logger.info("邮箱: %s  密码: %s", account.email, account.password)

        browser = launch_browser(proxy=proxy, headless=headless)
        result.browser = browser

        browser.navigate(signup_url, timeout=30)
        time.sleep(5)

        # 网易注册表单
        # 邮箱地址
        for sel in ["#nameCtrl input", "input[name='name']", "input[id*='name' i]",
                     "input[placeholder*='邮箱']", "input[placeholder*='email' i]",
                     "input[type='text']"]:
            if wait_and_type(browser, sel, account.username, timeout=5):
                logger.info("[STEP] 用户名: %s", account.username)
                break

        # 密码
        for sel in ["input[name='password']", "input[type='password']",
                     "#passwordCtrl input"]:
            if wait_and_type(browser, sel, account.password, timeout=5):
                logger.info("[STEP] 密码已填写")
                break

        # 确认密码
        for sel in ["input[name*='confirm' i]", "input[name*='repeat' i]",
                     "#confirmPasswordCtrl input"]:
            wait_and_type(browser, sel, account.password, timeout=3)

        # 手机号检测
        body_text = browser.get_body_text().lower()
        for sel in ["input[name='phone']", "input[type='tel']",
                     "input[placeholder*='手机']", "input[placeholder*='phone']"]:
            nid = browser.query_selector(sel)
            if nid and browser.is_element_visible(nid):
                result.error = "phone_verification_required"
                logger.warning("[WARN] %s 要求手机号验证", domain)
                take_screenshot(browser, f"{domain_key}_phone_required")
                if keep_browser:
                    result.browser = browser
                else:
                    browser.close()
                save_result(result)
                return result

        # 验证码（网易通常有图形验证码）
        captcha = detect_captcha(browser)
        if captcha:
            logger.info("[CAPTCHA] 检测到: %s", captcha)
            take_screenshot(browser, f"{domain_key}_captcha")
            if wait_for_captcha_clear(browser, timeout=60):
                logger.info("[CAPTCHA] 已通过")

        time.sleep(1)

        # 提交
        for sel in ["button[type='submit']", "input[type='submit']",
                     "button:has-text('注册')", "a:has-text('注册')",
                     "#registerButton"]:
            if wait_and_click(browser, sel, timeout=3):
                logger.info("[STEP] 已提交")
                break

        time.sleep(8)

        # 结果检测
        final_url = browser.get_url()
        result.final_url = final_url
        body = browser.get_body_text().lower()

        success_markers = ["成功", "welcome", "登录", "收件箱", "mail.163.com",
                           "mail.126.com", "mail.yeah.net"]
        if any(m in body for m in success_markers):
            result.success = True
            logger.info("[OK] %s 注册成功! %s", domain, account.email)
        elif "已存在" in body or "已被" in body or "taken" in body:
            result.error = "username_taken"
        elif "验证码" in body or "captcha" in body:
            result.error = "captcha_blocked"
        else:
            result.error = f"unknown: {final_url[:80]}"

        take_screenshot(browser, f"{domain_key}_final")
        if keep_browser:
            result.browser = browser
        else:
            browser.close()

    except Exception as e:
        result.error = str(e)
        logger.exception("[ERROR] %s 注册异常", domain)
        if browser and not keep_browser:
            try:
                take_screenshot(browser, f"{domain_key}_error")
                browser.close()
            except Exception:
                pass

    save_result(result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="网易邮箱注册 (163/126/yeah)")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--proxy", default="")
    parser.add_argument("--domain", default="163", choices=["163", "126", "yeah"],
                        help="邮箱域名: 163, 126, yeah")
    args = parser.parse_args()

    r = register(proxy=args.proxy, headless=args.headless, domain_key=args.domain)
    print(f"\n结果: {'成功' if r.success else '失败'}  邮箱: {r.email}  密码: {r.password}")
    if r.error:
        print(f"错误: {r.error}")
