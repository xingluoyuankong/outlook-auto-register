#!/usr/bin/env python3
"""
Proton Mail v5 - 使用 React-compatible 输入方式
发现:
1. username 字段不接受键盘直接输入 (React 受控组件)
2. 密码要求: ≥12字符, 大小写+数字+符号
3. #password-confirm 一开始就存在（不只是第一次提交后）
4. 用 nativeInputValueSetter 可以正确设置值
"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp_base import (
    launch_browser, take_screenshot, detect_captcha, 
    wait_for_captcha_clear, save_result, RegistrationResult,
    generate_account, random_password,
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


def fill_react_input(browser, selector, value):
    """用 React 兼容的方式设置 input 值"""
    escaped_sel = selector.replace("'", "\\'")
    escaped_val = value.replace("'", "\\'")
    js = f"""
    (() => {{
        const el = document.querySelector('{escaped_sel}');
        if (!el) return false;
        const nativeSetter = Object.getOwnPropertyDescriptor(
            window.HTMLInputElement.prototype, 'value'
        ).set;
        nativeSetter.call(el, '{escaped_val}');
        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
        el.dispatchEvent(new Event('change', {{ bubbles: true }}));
        el.dispatchEvent(new KeyboardEvent('keydown', {{ bubbles: true }}));
        el.dispatchEvent(new KeyboardEvent('keyup', {{ bubbles: true }}));
        return true;
    }})()
    """
    return browser.evaluate(js)


def try_proton_v5(headless=False):
    account = generate_account("proton", "proton.me")
    # Ensure password meets Proton requirements: 12+ chars, upper+lower+number+symbol
    pwd = "Pr0ton!@" + account.password[:8]  # Guaranteed: upper(P), lower(r), number(0), symbol(!@)
    
    result = RegistrationResult(
        provider="proton", domain="proton.me",
        email=account.email, password=pwd, username=account.username,
    )
    browser = None
    try:
        logger.info("=== Proton Mail v5 实跑 ===")
        logger.info("邮箱: %s  密码: %s", account.email, pwd)
        
        browser = launch_browser(headless=headless)
        result.browser = browser
        
        browser.navigate("https://account.proton.me/signup?plan=free", timeout=30)
        time.sleep(15)  # Long wait for SPA
        
        take_screenshot(browser, "proton_v5_initial")
        
        # Step 1: Fill username using React-compatible method
        ok = fill_react_input(browser, "#username", account.username)
        logger.info("[STEP1] Username fill result: %s, value: %s", ok, 
                     browser.evaluate("document.querySelector('#username').value"))
        
        time.sleep(1)
        
        # Step 2: Fill password
        ok = fill_react_input(browser, "#password", pwd)
        logger.info("[STEP2] Password fill result: %s, len: %d", ok,
                     browser.evaluate("document.querySelector('#password').value.length"))
        
        time.sleep(1)
        
        # Step 3: Fill confirm password
        ok = fill_react_input(browser, "#password-confirm", pwd)
        logger.info("[STEP3] Confirm password fill result: %s", ok)
        
        time.sleep(1)
        
        # Check state
        state = browser.evaluate("""
            (() => {
                const btn = document.querySelector('button[type="submit"]');
                const u = document.querySelector('#username');
                const p = document.querySelector('#password');
                const pc = document.querySelector('#password-confirm');
                return {
                    btnDisabled: btn ? btn.disabled : 'not found',
                    username: u ? u.value : '',
                    password: p ? p.value.length + ' chars' : '',
                    confirm: pc ? pc.value.length + ' chars' : '',
                };
            })()
        """)
        logger.info("[STATE] %s", json.dumps(state))
        
        # Check if username is available (might need to wait for API check)
        time.sleep(3)
        state2 = browser.evaluate("""
            (() => {
                const btn = document.querySelector('button[type="submit"]');
                const hints = document.querySelectorAll('[class*="color-hint"], [class*="error"], [class*="valid"]');
                const hintTexts = Array.from(hints).filter(e => e.getBoundingClientRect().width > 0)
                    .map(e => e.textContent.trim()).filter(t => t.length > 0);
                return {
                    btnDisabled: btn ? btn.disabled : 'not found',
                    hints: hintTexts,
                };
            })()
        """)
        logger.info("[STATE2] %s", json.dumps(state2, ensure_ascii=False))
        
        take_screenshot(browser, "proton_v5_filled")
        
        # Step 4: Click submit
        submit_info = browser.evaluate("""
            (() => {
                const btn = document.querySelector('button[type="submit"]');
                if (btn && !btn.disabled) {
                    const r = btn.getBoundingClientRect();
                    return {x: r.x + r.width/2, y: r.y + r.height/2};
                }
                return null;
            })()
        """)
        
        if submit_info:
            browser.click_at(submit_info['x'], submit_info['y'])
            logger.info("[STEP4] 已点击提交")
        else:
            # Force click even if disabled
            browser.evaluate("""
                (() => {
                    const btn = document.querySelector('button[type="submit"]');
                    if (btn) { btn.disabled = false; btn.click(); }
                })()
            """)
            logger.info("[STEP4] 强制点击提交 (disabled)")
        
        time.sleep(10)
        take_screenshot(browser, "proton_v5_after_submit")
        
        result.final_url = browser.get_url()
        body = browser.get_body_text().lower()
        logger.info("[RESULT] URL: %s", result.final_url[:100])
        logger.info("[RESULT] Body: %s", body[:500])
        
        # Check for CAPTCHA
        captcha = detect_captcha(browser)
        if captcha:
            logger.info("[CAPTCHA] 检测到: %s", captcha)
            take_screenshot(browser, "proton_v5_captcha")
            if wait_for_captcha_clear(browser, timeout=90):
                logger.info("[CAPTCHA] 已通过!")
            else:
                result.error = f"captcha: {captcha}"
        
        # Check for recovery step
        body = browser.get_body_text().lower()
        if 'recovery' in body:
            logger.info("[INFO] 检测到恢复选项页面，尝试跳过")
            skip = browser.evaluate("""
                (() => {
                    const btns = document.querySelectorAll('button');
                    for (const b of btns) {
                        const t = (b.textContent || '').toLowerCase();
                        if (t.includes('skip') || t.includes('跳过') || t.includes('maybe later') || t.includes('稍后')) {
                            const r = b.getBoundingClientRect();
                            if (r.width > 0) { b.click(); return t; }
                        }
                    }
                    return null;
                })()
            """)
            if skip:
                logger.info("[STEP] 跳过: %s", skip)
                time.sleep(5)
        
        # Check final
        body = browser.get_body_text().lower()
        if 'welcome' in body or 'inbox' in body or 'mail.proton' in result.final_url:
            result.success = True
            logger.info("[OK] Proton 注册成功!")
        elif not result.error:
            final_els = browser.evaluate("""
                (() => {
                    const els = document.querySelectorAll('input:not([type=hidden]), button[type="submit"]');
                    return Array.from(els).filter(e => e.getBoundingClientRect().width > 0)
                        .map(e => ({tag: e.tagName, id: e.id, val: (e.value || '').substring(0, 40)}));
                })()
            """)
            logger.info("[FINAL] %s", json.dumps(final_els, ensure_ascii=False))
            
            # Check for verification codes, phone, etc
            if 'phone' in body or 'mobile' in body:
                result.error = "phone_verification_required"
                logger.warning("[WARN] 需要手机号")
            elif 'verification' in body or 'verify' in body or 'code' in body:
                result.error = "verification_code_required"
                logger.warning("[WARN] 需要验证码")
        
        take_screenshot(browser, "proton_v5_final")
        browser.close()
        
    except Exception as e:
        result.error = str(e)
        logger.exception("[ERROR] Proton v5 异常")
        if browser:
            try:
                take_screenshot(browser, "proton_v5_error")
                browser.close()
            except:
                pass
    
    save_result(result)
    return result


if __name__ == "__main__":
    r = try_proton_v5()
    print(f"\n结果: {'成功' if r.success else '失败'}  邮箱: {r.email}  密码: {r.password}")
    if r.error:
        print(f"错误: {r.error}")
