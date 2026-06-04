#!/usr/bin/env python3
"""
Proton v8 - 使用 Input.insertText 直接插入文本
这是最底层的文本输入方式，绕过所有事件系统
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


def insert_text_cdp(browser, text):
    """使用 CDP Input.insertText 插入文本"""
    browser._send_cmd("Input.insertText", {"text": text})
    time.sleep(0.3)


def focus_and_insert(browser, selector, text):
    """Focus element, clear, and insert text"""
    safe_sel = selector.replace("'", "\\'")
    
    # Focus and clear
    browser.evaluate(f"""
        (() => {{
            const el = document.querySelector('{safe_sel}');
            if (!el) return false;
            el.focus();
            el.value = '';
            el.dispatchEvent(new Event('input', {{bubbles:true}}));
            return true;
        }})()
    """)
    time.sleep(0.3)
    
    # Also click to ensure focus
    nid = browser.query_selector(selector)
    if nid:
        rect = browser.get_element_rect(nid)
        if rect:
            browser.click_at(rect["center_x"], rect["center_y"])
            time.sleep(0.3)
    
    # Select all text and delete
    browser.evaluate(f"""
        (() => {{
            const el = document.querySelector('{safe_sel}');
            if (el) {{ el.select(); }}
        }})()
    """)
    time.sleep(0.1)
    
    # Insert text using CDP
    insert_text_cdp(browser, text)
    time.sleep(0.5)
    
    # Dispatch events to trigger React state update
    browser.evaluate(f"""
        (() => {{
            const el = document.querySelector('{safe_sel}');
            if (el) {{
                el.dispatchEvent(new Event('input', {{bubbles:true}}));
                el.dispatchEvent(new Event('change', {{bubbles:true}}));
                // Also trigger React's synthetic event
                const ev = new InputEvent('input', {{bubbles:true, data: '{text.replace("'", "\\'")}', inputType: 'insertText'}});
                el.dispatchEvent(ev);
            }}
        }})()
    """)
    time.sleep(0.3)
    
    # Verify
    actual = browser.evaluate(f"document.querySelector('{safe_sel}').value")
    logger.info("[INSERT] %s: expected='%s' actual='%s' match=%s", selector, text, actual, actual == text)
    return actual == text


def try_proton_v8(headless=False):
    account = generate_account("proton", "proton.me")
    pwd = "Pr0ton!@" + account.password[:8]
    
    result = RegistrationResult(
        provider="proton", domain="proton.me",
        email=account.email, password=pwd, username=account.username,
    )
    browser = None
    try:
        logger.info("=== Proton Mail v8 实跑 ===")
        logger.info("邮箱: %s  密码: %s", account.email, pwd)
        
        browser = launch_browser(headless=headless)
        result.browser = browser
        
        browser.navigate("https://account.proton.me/signup?plan=free", timeout=30)
        time.sleep(15)
        
        take_screenshot(browser, "proton_v8_initial")
        
        # Check if _send_cmd method exists
        if hasattr(browser, '_send_cmd'):
            logger.info("[CDP] _send_cmd method available")
        else:
            logger.warning("[CDP] _send_cmd NOT available, trying alternative")
        
        # Fill username
        focus_and_insert(browser, "#username", account.username)
        
        # Fill password
        focus_and_insert(browser, "#password", pwd)
        
        # Fill confirm password
        focus_and_insert(browser, "#password-confirm", pwd)
        
        time.sleep(3)
        
        # Check state
        state = browser.evaluate("""
            (() => {
                const btn = document.querySelector('button[type="submit"]');
                const u = document.querySelector('#username');
                const p = document.querySelector('#password');
                const pc = document.querySelector('#password-confirm');
                
                // Check for validation hints
                const hints = document.querySelectorAll('[class*="color-hint"], [class*="error"]');
                const hintTexts = Array.from(hints)
                    .filter(e => e.getBoundingClientRect().width > 0)
                    .map(e => e.textContent.trim())
                    .filter(t => t.length > 0);
                
                return {
                    btnDisabled: btn ? btn.disabled : 'not found',
                    username: u ? u.value : '',
                    password: p ? p.value.length : 0,
                    confirm: pc ? pc.value.length : 0,
                    hints: hintTexts,
                };
            })()
        """)
        logger.info("[STATE] %s", json.dumps(state, ensure_ascii=False))
        
        take_screenshot(browser, "proton_v8_filled")
        
        # If button is disabled, check what's wrong
        if state.get('btnDisabled'):
            logger.warning("[STATE] Button disabled - checking validation...")
            # Maybe we need to tab out of the field to trigger validation
            browser.evaluate("document.querySelector('#username').blur()")
            time.sleep(2)
            browser.evaluate("document.querySelector('#password').blur()")
            time.sleep(2)
            
            state2 = browser.evaluate("""
                (() => {
                    const btn = document.querySelector('button[type="submit"]');
                    const hints = document.querySelectorAll('[class*="color-hint"], [class*="error"], [class*="valid"]');
                    const hintTexts = Array.from(hints)
                        .filter(e => e.getBoundingClientRect().width > 0)
                        .map(e => ({text: e.textContent.trim(), class: (e.className || '').substring(0, 60)}));
                    return {disabled: btn ? btn.disabled : 'not found', hints: hintTexts};
                })()
            """)
            logger.info("[STATE2] %s", json.dumps(state2, ensure_ascii=False))
        
        # Submit
        submit_info = browser.evaluate("""
            (() => {
                const btn = document.querySelector('button[type="submit"]');
                if (btn) {
                    const r = btn.getBoundingClientRect();
                    return {x: r.x + r.width/2, y: r.y + r.height/2, disabled: btn.disabled, text: btn.textContent.trim()};
                }
                return null;
            })()
        """)
        logger.info("[SUBMIT] %s", submit_info)
        
        if submit_info:
            if submit_info.get('disabled'):
                logger.warning("[SUBMIT] Disabled, enabling...")
                browser.evaluate("document.querySelector('button[type=\"submit\"]').disabled = false")
                time.sleep(0.5)
            browser.click_at(submit_info['x'], submit_info['y'])
            logger.info("[SUBMIT] Clicked!")
        
        time.sleep(15)
        take_screenshot(browser, "proton_v8_after_submit")
        
        result.final_url = browser.get_url()
        body = browser.get_body_text()
        body_lower = body.lower()
        logger.info("[RESULT] URL: %s", result.final_url[:100])
        logger.info("[RESULT] Body: %s", body_lower[:600])
        
        # Check for upsell
        all_buttons = browser.evaluate("""
            (() => {
                return Array.from(document.querySelectorAll('button, a')).filter(e => e.getBoundingClientRect().width > 0)
                    .map(e => (e.textContent || '').trim().substring(0, 80))
                    .filter(t => t.length > 0 && t.length < 50);
            })()
        """)
        logger.info("[BUTTONS] %s", json.dumps(all_buttons, ensure_ascii=False))
        
        # Try to dismiss upsell
        dismiss = browser.evaluate("""
            (() => {
                const targets = ['no thanks', 'no, thanks', 'skip', 'continue with free', 'free', '谢谢', '不用', 'later', 'decline'];
                const btns = document.querySelectorAll('button, a, [role="button"]');
                for (const b of btns) {
                    const text = (b.textContent || '').toLowerCase().trim();
                    for (const t of targets) {
                        if (text.includes(t)) {
                            const r = b.getBoundingClientRect();
                            if (r.width > 0 && r.height > 0 && r.height < 100) {
                                b.click();
                                return text;
                            }
                        }
                    }
                }
                return null;
            })()
        """)
        if dismiss:
            logger.info("[DISMISS] '%s'", dismiss)
            time.sleep(8)
        
        # CAPTCHA check
        captcha = detect_captcha(browser)
        if captcha:
            logger.info("[CAPTCHA] %s", captcha)
            if wait_for_captcha_clear(browser, timeout=90):
                logger.info("[CAPTCHA] Passed!")
            else:
                result.error = f"captcha: {captcha}"
        
        # Recovery check
        body_lower = browser.get_body_text().lower()
        if 'recovery' in body_lower:
            logger.info("[RECOVERY] Skipping...")
            browser.evaluate("""
                (() => {
                    const btns = document.querySelectorAll('button, a');
                    for (const b of btns) {
                        const t = (b.textContent || '').toLowerCase();
                        if (t.includes('skip') || t.includes('跳过') || t.includes('later')) {
                            const r = b.getBoundingClientRect();
                            if (r.width > 0) { b.click(); return; }
                        }
                    }
                })()
            """)
            time.sleep(5)
        
        # Final check
        body_lower = browser.get_body_text().lower()
        result.final_url = browser.get_url()
        if 'welcome' in body_lower or 'inbox' in body_lower or 'mail.proton' in result.final_url:
            result.success = True
            logger.info("[OK] SUCCESS! %s", account.email)
        elif 'phone' in body_lower or 'mobile' in body_lower:
            result.error = "phone_verification_required"
        elif not result.error:
            els = browser.evaluate("""
                (() => {
                    return Array.from(document.querySelectorAll('input:not([type=hidden]), button')).filter(e => e.getBoundingClientRect().width > 0)
                        .map(e => ({tag: e.tagName, id: e.id, val: (e.value || '').substring(0, 40)}));
                })()
            """)
            logger.info("[FINAL] %s", json.dumps(els, ensure_ascii=False))
        
        take_screenshot(browser, "proton_v8_final")
        browser.close()
        
    except Exception as e:
        result.error = str(e)
        logger.exception("[ERROR]")
        if browser:
            try:
                take_screenshot(browser, "proton_v8_error")
                browser.close()
            except:
                pass
    
    save_result(result)
    return result


if __name__ == "__main__":
    r = try_proton_v8()
    print(f"\n结果: {'成功' if r.success else '失败'}  邮箱: {r.email}  密码: {r.password}")
    if r.error:
        print(f"错误: {r.error}")
