#!/usr/bin/env python3
"""
Proton v6 - 处理 upsell 页面，找到跳过/免费选项
"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp_base import launch_browser, take_screenshot, detect_captcha, wait_for_captcha_clear, save_result, RegistrationResult, generate_account
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
        return true;
    }})()
    """
    return browser.evaluate(js)


def try_proton_v6(headless=False):
    account = generate_account("proton", "proton.me")
    pwd = "Pr0ton!@" + account.password[:8]
    
    result = RegistrationResult(
        provider="proton", domain="proton.me",
        email=account.email, password=pwd, username=account.username,
    )
    browser = None
    try:
        logger.info("=== Proton Mail v6 实跑 ===")
        logger.info("邮箱: %s  密码: %s", account.email, pwd)
        
        browser = launch_browser(headless=headless)
        result.browser = browser
        
        browser.navigate("https://account.proton.me/signup?plan=free", timeout=30)
        time.sleep(15)
        
        take_screenshot(browser, "proton_v6_initial")
        
        # Fill form
        fill_react_input(browser, "#username", account.username)
        time.sleep(0.5)
        fill_react_input(browser, "#password", pwd)
        time.sleep(0.5)
        fill_react_input(browser, "#password-confirm", pwd)
        time.sleep(3)
        
        logger.info("[STEP] 表单已填写, username=%s", 
                     browser.evaluate("document.querySelector('#username').value"))
        
        # Submit
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
            logger.info("[STEP] 已提交")
        
        time.sleep(10)
        take_screenshot(browser, "proton_v6_after_submit")
        
        # Now check for upsell/pricing page and try to dismiss it
        body = browser.get_body_text().lower()
        logger.info("[PAGE] Body: %s", body[:500])
        
        # Look for dismiss/skip/close buttons on upsell
        all_buttons = browser.evaluate("""
            (() => {
                const els = document.querySelectorAll('button, a, [role="button"]');
                return Array.from(els).filter(e => {
                    const r = e.getBoundingClientRect();
                    return r.width > 0 && r.height > 0;
                }).map(e => ({
                    tag: e.tagName,
                    text: (e.textContent || '').trim().substring(0, 80),
                    href: e.href || '',
                    class: (e.className || '').substring(0, 60),
                })).slice(0, 40);
            })()
        """)
        logger.info("[BUTTONS] %s", json.dumps(all_buttons, ensure_ascii=False, indent=2))
        
        # Try various dismiss patterns
        dismiss_selectors = [
            "button:has-text('No thanks')", "button:has-text('no thanks')",
            "button:has-text('Skip')", "button:has-text('skip')",
            "button:has-text('Continue')", "button:has-text('Free')",
            "button:has-text('谢谢')", "button:has-text('不用了')",
            "button:has-text('No, thanks')", "button:has-text('Decline')",
            "a:has-text('No thanks')", "a:has-text('Skip')",
            "[data-testid*='skip']", "[data-testid*='decline']",
            "[data-testid*='dismiss']", "[data-testid*='close']",
        ]
        
        dismissed = False
        for sel in dismiss_selectors:
            nid = browser.query_selector(sel)
            if nid and browser.is_element_visible(nid):
                rect = browser.get_element_rect(nid)
                if rect:
                    browser.click_at(rect["center_x"], rect["center_y"])
                    logger.info("[STEP] 点击: %s", sel)
                    dismissed = True
                    break
        
        if not dismissed:
            # Try JS-based search for dismiss buttons
            dismiss = browser.evaluate("""
                (() => {
                    const btns = document.querySelectorAll('button, a, [role="button"]');
                    for (const b of btns) {
                        const text = (b.textContent || '').toLowerCase().trim();
                        if (text.includes('no thanks') || text.includes('no, thanks') || 
                            text.includes('skip') || text.includes('decline') ||
                            text.includes('free') || text.includes('不用') ||
                            text.includes('谢谢') || text.includes('later') ||
                            text.includes('continue with free') || text.includes('maybe later')) {
                            const r = b.getBoundingClientRect();
                            if (r.width > 0) {
                                b.click();
                                return text;
                            }
                        }
                    }
                    return null;
                })()
            """)
            if dismiss:
                logger.info("[STEP] JS dismiss: '%s'", dismiss)
                dismissed = True
        
        if not dismissed:
            logger.warning("[WARN] 未找到跳过按钮，检查页面...")
        
        time.sleep(8)
        take_screenshot(browser, "proton_v6_after_dismiss")
        
        # Check for recovery step
        body = browser.get_body_text().lower()
        logger.info("[PAGE] Body after dismiss: %s", body[:500])
        
        if 'recovery' in body or 'recover' in body:
            logger.info("[STEP] 检测到恢复选项")
            skip = browser.evaluate("""
                (() => {
                    const btns = document.querySelectorAll('button, a');
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
                logger.info("[STEP] 跳过恢复: '%s'", skip)
                time.sleep(5)
        
        # Check for phone verification
        if 'phone' in body or 'mobile' in body:
            phone_el = browser.evaluate("""
                (() => {
                    const el = document.querySelector("input[type='tel'], input[name*='phone']");
                    if (el) { const r = el.getBoundingClientRect(); return {visible: r.width > 0}; }
                    return null;
                })()
            """)
            if phone_el and phone_el.get('visible'):
                result.error = "phone_verification_required"
                logger.warning("[WARN] 需要手机号")
        
        # Check for CAPTCHA
        captcha = detect_captcha(browser)
        if captcha:
            logger.info("[CAPTCHA] 检测到: %s", captcha)
            if wait_for_captcha_clear(browser, timeout=90):
                logger.info("[CAPTCHA] 已通过!")
            else:
                result.error = f"captcha: {captcha}"
        
        # Final check
        result.final_url = browser.get_url()
        body = browser.get_body_text().lower()
        if 'welcome' in body or 'inbox' in body or 'mail.proton' in result.final_url:
            result.success = True
            logger.info("[OK] Proton 注册成功! %s", account.email)
        elif 'congratulations' in body or 'created' in body:
            result.success = True
            logger.info("[OK] Proton 注册成功! %s", account.email)
        elif not result.error:
            # Get all visible elements for debugging
            final = browser.evaluate("""
                (() => {
                    const els = document.querySelectorAll('input:not([type=hidden]), button, a[href]');
                    return Array.from(els).filter(e => e.getBoundingClientRect().width > 0)
                        .map(e => ({
                            tag: e.tagName, id: e.id, 
                            text: (e.textContent || e.value || '').trim().substring(0, 60),
                            href: e.href || '',
                        })).slice(0, 25);
                })()
            """)
            logger.info("[FINAL] %s", json.dumps(final, ensure_ascii=False, indent=2))
        
        take_screenshot(browser, "proton_v6_final")
        browser.close()
        
    except Exception as e:
        result.error = str(e)
        logger.exception("[ERROR] Proton v6 异常")
        if browser:
            try:
                take_screenshot(browser, "proton_v6_error")
                browser.close()
            except:
                pass
    
    save_result(result)
    return result


if __name__ == "__main__":
    r = try_proton_v6()
    print(f"\n结果: {'成功' if r.success else '失败'}  邮箱: {r.email}  密码: {r.password}")
    if r.error:
        print(f"错误: {r.error}")
