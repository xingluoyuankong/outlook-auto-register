#!/usr/bin/env python3
"""
Proton v7 - 使用 CDP Input.dispatchKeyEvent 直接输入
React 受控组件不接受 DOM 事件, 需要用底层 CDP 输入
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


def focus_and_type(browser, selector, text, delay_ms=100):
    """Focus element and type using CDP keyboard simulation"""
    # Click to focus
    nid = browser.query_selector(selector)
    if not nid:
        logger.warning("[INPUT] Element not found: %s", selector)
        return False
    rect = browser.get_element_rect(nid)
    if not rect:
        logger.warning("[INPUT] No rect: %s", selector)
        return False
    browser.click_at(rect["center_x"], rect["center_y"])
    time.sleep(0.3)
    
    # Clear existing value
    safe_sel = selector.replace("'", "\\'")
    browser.evaluate(f"""
        (() => {{
            const el = document.querySelector('{safe_sel}');
            if (el) {{
                el.focus();
                el.value = '';
                el.dispatchEvent(new Event('input', {{bubbles:true}}));
            }}
        }})()
    """)
    time.sleep(0.2)
    
    # Type each character
    for ch in text:
        browser.type_text(ch, delay_ms=delay_ms)
    
    time.sleep(0.3)
    
    # Verify
    safe_sel = selector.replace("'", "\\'")
    actual = browser.evaluate(f"document.querySelector('{safe_sel}').value")
    logger.info("[INPUT] %s: expected='%s' actual='%s'", selector, text, actual)
    return actual == text


def try_proton_v7(headless=False):
    account = generate_account("proton", "proton.me")
    pwd = "Pr0ton!@" + account.password[:8]
    
    result = RegistrationResult(
        provider="proton", domain="proton.me",
        email=account.email, password=pwd, username=account.username,
    )
    browser = None
    try:
        logger.info("=== Proton Mail v7 实跑 ===")
        logger.info("邮箱: %s  密码: %s", account.email, pwd)
        
        browser = launch_browser(headless=headless)
        result.browser = browser
        
        browser.navigate("https://account.proton.me/signup?plan=free", timeout=30)
        time.sleep(15)
        
        take_screenshot(browser, "proton_v7_initial")
        
        # Method: Focus, clear, then use browser.type_text (which uses CDP Input.dispatchKeyEvent)
        # This should work with React because CDP key events are "real" keyboard events
        
        # Step 1: Focus username and type
        nid = browser.query_selector("#username")
        if nid:
            rect = browser.get_element_rect(nid)
            browser.click_at(rect["center_x"], rect["center_y"])
            time.sleep(0.5)
            # Select all and delete
            browser.evaluate("document.querySelector('#username').select()")
            time.sleep(0.1)
            # Type using CDP
            for ch in account.username:
                browser.type_text(ch, delay_ms=80)
            time.sleep(1)
            actual = browser.evaluate("document.querySelector('#username').value")
            logger.info("[STEP1] Username: expected='%s' actual='%s'", account.username, actual)
        
        # Step 2: Focus password and type
        nid = browser.query_selector("#password")
        if nid:
            rect = browser.get_element_rect(nid)
            browser.click_at(rect["center_x"], rect["center_y"])
            time.sleep(0.5)
            browser.evaluate("document.querySelector('#password').select()")
            time.sleep(0.1)
            for ch in pwd:
                browser.type_text(ch, delay_ms=80)
            time.sleep(1)
            actual = browser.evaluate("document.querySelector('#password').value")
            logger.info("[STEP2] Password: len expected=%d actual=%d", len(pwd), len(actual))
        
        # Step 3: Focus confirm password and type
        nid = browser.query_selector("#password-confirm")
        if nid:
            rect = browser.get_element_rect(nid)
            browser.click_at(rect["center_x"], rect["center_y"])
            time.sleep(0.5)
            browser.evaluate("document.querySelector('#password-confirm').select()")
            time.sleep(0.1)
            for ch in pwd:
                browser.type_text(ch, delay_ms=80)
            time.sleep(1)
            actual = browser.evaluate("document.querySelector('#password-confirm').value")
            logger.info("[STEP3] Confirm password: len expected=%d actual=%d", len(pwd), len(actual))
        
        time.sleep(3)
        
        # Check button state
        btn_state = browser.evaluate("""
            (() => {
                const btn = document.querySelector('button[type="submit"]');
                const u = document.querySelector('#username');
                const p = document.querySelector('#password');
                const pc = document.querySelector('#password-confirm');
                return {
                    disabled: btn ? btn.disabled : 'not found',
                    username: u ? u.value : '',
                    password: p ? p.value.length : 0,
                    confirm: pc ? pc.value.length : 0,
                };
            })()
        """)
        logger.info("[STATE] %s", json.dumps(btn_state))
        
        take_screenshot(browser, "proton_v7_filled")
        
        # Step 4: Submit
        submit_info = browser.evaluate("""
            (() => {
                const btn = document.querySelector('button[type="submit"]');
                if (btn) {
                    const r = btn.getBoundingClientRect();
                    return {x: r.x + r.width/2, y: r.y + r.height/2, disabled: btn.disabled};
                }
                return null;
            })()
        """)
        logger.info("[SUBMIT] %s", submit_info)
        
        if submit_info:
            if submit_info.get('disabled'):
                logger.warning("[SUBMIT] Button is disabled! Trying to enable...")
                browser.evaluate("document.querySelector('button[type=\"submit\"]').disabled = false")
                time.sleep(0.5)
            browser.click_at(submit_info['x'], submit_info['y'])
            logger.info("[STEP4] 已点击提交")
        
        # Wait for response
        time.sleep(10)
        take_screenshot(browser, "proton_v7_after_submit")
        
        result.final_url = browser.get_url()
        body = browser.get_body_text().lower()
        logger.info("[RESULT] URL: %s", result.final_url[:100])
        logger.info("[RESULT] Body: %s", body[:600])
        
        # Check for upsell page (Mail Plus)
        if 'mail plus' in body or 'sgd' in body or '优惠' in body or 'discount' in body:
            logger.info("[UPSELL] 检测到 upsell 页面")
            # Find and click "No thanks" / skip / free option
            skip = browser.evaluate("""
                (() => {
                    const all = document.querySelectorAll('button, a, [role="button"], span, div');
                    for (const el of all) {
                        const text = (el.textContent || '').toLowerCase().trim();
                        const r = el.getBoundingClientRect();
                        if (r.width > 0 && r.height > 0 && r.height < 100) {
                            if (text === 'no thanks' || text === 'no, thanks' || text === '不用了' || 
                                text === 'skip' || text === 'maybe later' || text === '稍后再说' ||
                                text === 'continue with free' || text === '使用免费版' ||
                                text === '谢谢' || text === 'thank you') {
                                el.click();
                                return text;
                            }
                        }
                    }
                    return null;
                })()
            """)
            if skip:
                logger.info("[UPSELL] 点击: '%s'", skip)
                time.sleep(8)
            else:
                # Try looking for a close/X button
                close = browser.evaluate("""
                    (() => {
                        const els = document.querySelectorAll('button[aria-label*="close"], button[aria-label*="Close"], .close, [class*="dismiss"]');
                        for (const el of els) {
                            const r = el.getBoundingClientRect();
                            if (r.width > 0) { el.click(); return true; }
                        }
                        return false;
                    })()
                """)
                if close:
                    logger.info("[UPSELL] 点击关闭按钮")
                    time.sleep(5)
        
        # Check for CAPTCHA
        captcha = detect_captcha(browser)
        if captcha:
            logger.info("[CAPTCHA] %s", captcha)
            if wait_for_captcha_clear(browser, timeout=90):
                logger.info("[CAPTCHA] 已通过!")
            else:
                result.error = f"captcha: {captcha}"
        
        # Check for recovery
        body = browser.get_body_text().lower()
        if 'recovery' in body or 'recover' in body:
            logger.info("[STEP] 恢复选项页面")
            browser.evaluate("""
                (() => {
                    const btns = document.querySelectorAll('button, a');
                    for (const b of btns) {
                        const t = (b.textContent || '').toLowerCase();
                        if (t.includes('skip') || t.includes('跳过') || t.includes('maybe later')) {
                            const r = b.getBoundingClientRect();
                            if (r.width > 0) { b.click(); return; }
                        }
                    }
                })()
            """)
            time.sleep(5)
        
        # Check for phone
        if 'phone' in body or 'mobile' in body:
            phone_el = browser.evaluate("document.querySelector(\"input[type='tel']\")")
            if phone_el:
                result.error = "phone_verification_required"
        
        # Final success check
        body = browser.get_body_text().lower()
        if 'welcome' in body or 'inbox' in body or 'mail.proton' in result.final_url:
            result.success = True
            logger.info("[OK] Proton 注册成功!")
        
        take_screenshot(browser, "proton_v7_final")
        browser.close()
        
    except Exception as e:
        result.error = str(e)
        logger.exception("[ERROR]")
        if browser:
            try:
                take_screenshot(browser, "proton_v7_error")
                browser.close()
            except:
                pass
    
    save_result(result)
    return result


if __name__ == "__main__":
    r = try_proton_v7()
    print(f"\n结果: {'成功' if r.success else '失败'}  邮箱: {r.email}  密码: {r.password}")
    if r.error:
        print(f"错误: {r.error}")
