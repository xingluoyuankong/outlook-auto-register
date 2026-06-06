#!/usr/bin/env python3
"""
AOL Mail 完整注册实跑 - 修复版
AOL 使用 Yahoo 注册系统，表单字段 ID: reg-firstName, reg-lastName, reg-userId, reg-password
出生日期: undefined-mm, undefined-dd, undefined-yyyy
提交按钮: button[name='signup']
"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cdp_base import (
    AccountInfo, RegistrationResult, generate_account, launch_browser,
    wait_and_click, wait_and_type, set_value_and_dispatch, click_submit,
    select_dropdown_by_text, detect_captcha, wait_for_captcha_clear,
    take_screenshot, save_result, random_string, random_password,
)
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "live_run.log"), encoding="utf-8"),
    ]
)
logger = logging.getLogger(__name__)


def try_aol_full(headless=False):
    """AOL 完整注册流程"""
    account = generate_account("aol", "aol.com")
    result = RegistrationResult(
        provider="aol", domain="aol.com",
        email=account.email, password=account.password, username=account.username,
    )
    browser = None
    try:
        logger.info("=== AOL 完整实跑 ===")
        logger.info("邮箱: %s  密码: %s", account.email, account.password)
        
        browser = launch_browser(headless=headless)
        result.browser = browser
        
        browser.navigate("https://login.aol.com/account/create", timeout=30)
        time.sleep(5)
        
        url = browser.get_url()
        logger.info("[STEP] 页面: %s", url[:80])
        take_screenshot(browser, "aol_initial")
        
        # 填写所有表单字段
        # First name
        filled = False
        for sel in ["#reg-firstName", "input[name='firstName']"]:
            if wait_and_type(browser, sel, account.first_name, timeout=5):
                logger.info("[STEP] 姓: %s", account.first_name)
                filled = True
                break
        if not filled:
            # Try by clicking and typing
            el = browser.evaluate("""
                (() => {
                    const el = document.getElementById('reg-firstName');
                    if (el) { const r = el.getBoundingClientRect(); return {x: r.x + r.width/2, y: r.y + r.height/2}; }
                    return null;
                })()
            """)
            if el:
                browser.click_at(el['x'], el['y'])
                time.sleep(0.3)
                browser.type_text(account.first_name, delay_ms=80)
                logger.info("[STEP] 姓 (click+type): %s", account.first_name)
        
        time.sleep(0.5)
        
        # Last name
        for sel in ["#reg-lastName", "input[name='lastName']"]:
            if wait_and_type(browser, sel, account.last_name, timeout=3):
                logger.info("[STEP] 名: %s", account.last_name)
                break
        
        time.sleep(0.5)
        
        # Username
        for sel in ["#reg-userId", "input[name='userId']"]:
            if wait_and_type(browser, sel, account.username, timeout=3):
                logger.info("[STEP] 用户名: %s", account.username)
                break
        
        time.sleep(0.5)
        
        # Password
        for sel in ["#reg-password", "input[name='password']"]:
            if wait_and_type(browser, sel, account.password, timeout=3):
                logger.info("[STEP] 密码已填写")
                break
        
        time.sleep(0.5)
        
        # Birthdate - month
        for sel in ["#undefined-mm", "input[name='mm']"]:
            if wait_and_type(browser, sel, account.birth_month, timeout=3):
                logger.info("[STEP] 出生月: %s", account.birth_month)
                break
        
        time.sleep(0.3)
        
        # Birthdate - day
        for sel in ["#undefined-dd", "input[name='dd']"]:
            if wait_and_type(browser, sel, account.birth_day, timeout=3):
                logger.info("[STEP] 出生日: %s", account.birth_day)
                break
        
        time.sleep(0.3)
        
        # Birthdate - year
        for sel in ["#undefined-yyyy", "input[name='yyyy']"]:
            if wait_and_type(browser, sel, account.birth_year, timeout=3):
                logger.info("[STEP] 出生年: %s", account.birth_year)
                break
        
        time.sleep(1)
        take_screenshot(browser, "aol_filled")
        
        # Check for captcha before submit
        captcha = detect_captcha(browser)
        if captcha:
            logger.info("[CAPTCHA] 提交前检测到: %s", captcha)
        
        # Submit - click "下一页" button
        submitted = False
        for sel in ["button[name='signup']", "button[type='submit']",
                     "button:has-text('Next')", "button:has-text('下一页')"]:
            nid = browser.query_selector(sel)
            if nid and browser.is_element_visible(nid):
                rect = browser.get_element_rect(nid)
                if rect:
                    browser.click_at(rect["center_x"], rect["center_y"])
                    logger.info("[STEP] 已点击提交: %s", sel)
                    submitted = True
                    break
        
        if not submitted:
            # Try clicking the submit button by its name
            js_click = """
            (() => {
                const btn = document.querySelector("button[name='signup']");
                if (btn) { btn.click(); return true; }
                const btns = document.querySelectorAll('button[type="submit"]');
                for (const b of btns) { if (b.offsetParent) { b.click(); return true; } }
                return false;
            })()
            """
            if browser.evaluate(js_click):
                logger.info("[STEP] 已通过JS点击提交")
                submitted = True
        
        time.sleep(8)  # Wait for page transition
        
        take_screenshot(browser, "aol_after_submit")
        result.final_url = browser.get_url()
        
        # Check result
        body = browser.get_body_text().lower()
        logger.info("[RESULT] URL: %s", result.final_url[:100])
        logger.info("[RESULT] Body preview: %s", body[:300])
        
        # Check for CAPTCHA after submit
        captcha = detect_captcha(browser)
        if captcha:
            logger.info("[CAPTCHA] 提交后检测到: %s", captcha)
            take_screenshot(browser, "aol_captcha")
            result.error = f"captcha: {captcha}"
            
            # Try to wait for captcha to clear (if auto-solved by extension)
            logger.info("[CAPTCHA] 等待自动解决...")
            if wait_for_captcha_clear(browser, timeout=60):
                logger.info("[CAPTCHA] 已通过!")
                # May need to re-submit or continue
            else:
                logger.warning("[CAPTCHA] 未能自动通过")
        
        # Check for phone verification
        if 'phone' in body or 'mobile' in body or 'sms' in body:
            # Check if it's a required field
            phone_el = browser.evaluate("""
                (() => {
                    const el = document.querySelector("input[type='tel'], input[name*='phone'], #phone");
                    if (el) {
                        const r = el.getBoundingClientRect();
                        return {visible: r.width > 0 && r.height > 0, required: el.required};
                    }
                    return null;
                })()
            """)
            if phone_el and phone_el.get('visible'):
                result.error = "phone_verification_required"
                logger.warning("[WARN] AOL 需要手机号验证")
                take_screenshot(browser, "aol_phone_required")
        
        # Check for success
        if 'welcome' in body or 'inbox' in body or 'mail.aol.com' in result.final_url:
            result.success = True
            logger.info("[OK] AOL 注册成功! %s", account.email)
        elif not result.error:
            # Check for next step (maybe another page)
            elements = browser.evaluate("""
                (() => {
                    const els = document.querySelectorAll('input:not([type=hidden]), button');
                    return Array.from(els).filter(e => {
                        const r = e.getBoundingClientRect();
                        return r.width > 0 && r.height > 0;
                    }).map(e => ({
                        tag: e.tagName, type: e.type || '',
                        text: (e.textContent || e.value || '').trim().substring(0, 60),
                        id: e.id || '', name: e.name || '',
                    })).slice(0, 30);
                })()
            """)
            logger.info("[ELEMENTS] 下一页元素: %s", json.dumps(elements, ensure_ascii=False, indent=2))
            
            # Check for verification code / phone on next page
            body = browser.get_body_text().lower()
            if 'verification' in body or 'verify' in body or 'code' in body:
                result.error = "verification_required"
                logger.warning("[WARN] AOL 需要验证")
            
            # Try to detect if we're on a success page
            if 'congratulations' in body or 'created' in body or 'welcome' in body:
                result.success = True
                logger.info("[OK] AOL 注册成功! %s", account.email)
        
        browser.close()
        
    except Exception as e:
        result.error = str(e)
        logger.exception("[ERROR] AOL 异常")
        if browser:
            try:
                take_screenshot(browser, "aol_error")
                browser.close()
            except:
                pass
    
    save_result(result)
    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()
    
    r = try_aol_full(headless=args.headless)
    print(f"\n结果: {'成功' if r.success else '失败'}  邮箱: {r.email}  密码: {r.password}")
    if r.error:
        print(f"错误: {r.error}")
