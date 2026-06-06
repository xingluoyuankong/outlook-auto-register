#!/usr/bin/env python3
"""
Proton v9 - Focus via JS eval, then immediately type via CDP
The key insight: focus must be on the input WHEN type_text is called
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


def try_proton_v9(headless=False):
    account = generate_account("proton", "proton.me")
    pwd = "Pr0ton!@" + account.password[:8]
    
    result = RegistrationResult(
        provider="proton", domain="proton.me",
        email=account.email, password=pwd, username=account.username,
    )
    browser = None
    try:
        logger.info("=== Proton Mail v9 ===")
        logger.info("邮箱: %s  密码: %s", account.email, pwd)
        
        browser = launch_browser(headless=headless)
        result.browser = browser
        
        browser.navigate("https://account.proton.me/signup?plan=free", timeout=30)
        time.sleep(15)
        
        # Method: Use set_input_value (native setter + events) then verify
        # The key is that set_input_value does work (proven in v5)
        # The issue was the button being disabled initially but becoming enabled later
        
        # Fill all fields using set_input_value
        browser.set_input_value("#username", account.username)
        time.sleep(1)
        logger.info("[1] Username: %s", browser.evaluate("document.querySelector('#username').value"))
        
        browser.set_input_value("#password", pwd)
        time.sleep(1)
        logger.info("[2] Password: %d chars", browser.evaluate("document.querySelector('#password').value.length"))
        
        browser.set_input_value("#password-confirm", pwd)
        time.sleep(1)
        logger.info("[3] Confirm: %d chars", browser.evaluate("document.querySelector('#password-confirm').value.length"))
        
        # Now wait for validation to complete (async API call to check username availability)
        logger.info("[WAIT] Waiting for async validation...")
        for i in range(20):
            time.sleep(1)
            state = browser.evaluate("""
                (() => {
                    const btn = document.querySelector('button[type="submit"]');
                    const hints = document.querySelectorAll('[class*="color-hint"], [class*="error"], [class*="valid"]');
                    const hintTexts = Array.from(hints)
                        .filter(e => e.getBoundingClientRect().width > 0)
                        .map(e => e.textContent.trim())
                        .filter(t => t.length > 0);
                    return {
                        disabled: btn ? btn.disabled : 'not found',
                        hints: hintTexts,
                    };
                })()
            """)
            if not state.get('disabled'):
                logger.info("[WAIT] Button enabled after %ds! Hints: %s", i+1, state.get('hints'))
                break
            if i % 5 == 0:
                logger.info("[WAIT] Still disabled after %ds, hints: %s", i+1, state.get('hints'))
        
        take_screenshot(browser, "proton_v9_ready")
        
        # Submit
        btn_info = browser.evaluate("""
            (() => {
                const btn = document.querySelector('button[type="submit"]');
                if (btn) {
                    const r = btn.getBoundingClientRect();
                    return {x: r.x + r.width/2, y: r.y + r.height/2, disabled: btn.disabled};
                }
                return null;
            })()
        """)
        
        if btn_info:
            if btn_info.get('disabled'):
                logger.warning("[SUBMIT] Still disabled, force-enabling")
                browser.evaluate("document.querySelector('button[type=\"submit\"]').disabled = false")
                time.sleep(0.5)
            browser.click_at(btn_info['x'], btn_info['y'])
            logger.info("[SUBMIT] Clicked!")
        
        # Wait for response
        time.sleep(15)
        take_screenshot(browser, "proton_v9_after_submit")
        
        result.final_url = browser.get_url()
        body = browser.get_body_text().lower()
        logger.info("[RESULT] URL: %s", result.final_url[:100])
        
        # Log all visible buttons for upsell detection
        buttons = browser.evaluate("""
            (() => {
                return Array.from(document.querySelectorAll('button, a')).filter(e => e.getBoundingClientRect().width > 0)
                    .map(e => (e.textContent || '').trim().substring(0, 80))
                    .filter(t => t.length > 0 && t.length < 60);
            })()
        """)
        logger.info("[BUTTONS] %s", json.dumps(buttons, ensure_ascii=False))
        
        # Handle upsell page
        if 'mail plus' in body or 'sgd' in body or '优惠' in body:
            logger.info("[UPSELL] Detected pricing page")
            dismiss = browser.evaluate("""
                (() => {
                    const btns = document.querySelectorAll('button, a, [role="button"]');
                    for (const b of btns) {
                        const text = (b.textContent || '').toLowerCase().trim();
                        const r = b.getBoundingClientRect();
                        if (r.width > 0 && r.height > 0 && r.height < 80) {
                            if (text.includes('no thanks') || text.includes('skip') || text.includes('free') ||
                                text.includes('谢谢') || text.includes('不用') || text.includes('later') ||
                                text.includes('decline') || text.includes('continue')) {
                                b.click();
                                return text;
                            }
                        }
                    }
                    return null;
                })()
            """)
            if dismiss:
                logger.info("[UPSELL] Dismissed: '%s'", dismiss)
                time.sleep(10)
            else:
                logger.warning("[UPSELL] No dismiss button found")
                # Log all visible text for debugging
                all_text = browser.evaluate("document.body ? document.body.innerText : ''")
                logger.info("[UPSELL] Full text: %s", all_text[:1000])
        
        # Handle recovery
        body = browser.get_body_text().lower()
        if 'recovery' in body:
            logger.info("[RECOVERY] Skipping...")
            browser.evaluate("""
                (() => {
                    const btns = document.querySelectorAll('button');
                    for (const b of btns) {
                        const t = (b.textContent || '').toLowerCase();
                        if (t.includes('skip') || t.includes('跳过') || t.includes('later')) {
                            b.click(); return;
                        }
                    }
                })()
            """)
            time.sleep(5)
        
        # CAPTCHA
        captcha = detect_captcha(browser)
        if captcha:
            logger.info("[CAPTCHA] %s", captcha)
            if wait_for_captcha_clear(browser, timeout=90):
                logger.info("[CAPTCHA] Passed!")
            else:
                result.error = f"captcha: {captcha}"
        
        # Phone check
        body = browser.get_body_text().lower()
        if 'phone' in body or 'mobile' in body:
            tel = browser.evaluate("document.querySelector(\"input[type='tel']\")")
            if tel:
                result.error = "phone_verification_required"
        
        # Success check
        body = browser.get_body_text().lower()
        result.final_url = browser.get_url()
        if 'welcome' in body or 'inbox' in body or 'mail.proton' in result.final_url:
            result.success = True
            logger.info("[OK] SUCCESS! %s", account.email)
        elif 'congratulations' in body or 'created' in body:
            result.success = True
            logger.info("[OK] SUCCESS! %s", account.email)
        elif not result.error:
            els = browser.evaluate("""
                (() => {
                    return Array.from(document.querySelectorAll('input:not([type=hidden]), button')).filter(e => e.getBoundingClientRect().width > 0)
                        .map(e => ({tag: e.tagName, id: e.id, val: (e.value || '').substring(0, 40)}));
                })()
            """)
            logger.info("[FINAL] %s", json.dumps(els, ensure_ascii=False))
        
        take_screenshot(browser, "proton_v9_final")
        browser.close()
        
    except Exception as e:
        result.error = str(e)
        logger.exception("[ERROR]")
        if browser:
            try:
                take_screenshot(browser, "proton_v9_error")
                browser.close()
            except:
                pass
    
    save_result(result)
    return result


if __name__ == "__main__":
    r = try_proton_v9()
    print(f"\n结果: {'成功' if r.success else '失败'}  邮箱: {r.email}  密码: {r.password}")
    if r.error:
        print(f"错误: {r.error}")
