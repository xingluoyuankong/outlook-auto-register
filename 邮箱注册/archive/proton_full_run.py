#!/usr/bin/env python3
"""
Proton Mail 完整注册实跑
表单: #username, #password, submit button
挑战: iframe (account-api.proton.me/challenge/v4)
"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cdp_base import (
    AccountInfo, RegistrationResult, generate_account, launch_browser,
    wait_and_click, wait_and_type, set_value_and_dispatch, click_submit,
    detect_captcha, wait_for_captcha_clear, take_screenshot, save_result,
    random_password,
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


def try_proton_full(headless=False):
    """Proton Mail 完整注册流程"""
    account = generate_account("proton", "proton.me")
    result = RegistrationResult(
        provider="proton", domain="proton.me",
        email=account.email, password=account.password, username=account.username,
    )
    browser = None
    try:
        logger.info("=== Proton Mail 完整实跑 ===")
        logger.info("邮箱: %s  密码: %s", account.email, account.password)
        
        browser = launch_browser(headless=headless)
        result.browser = browser
        
        browser.navigate("https://account.proton.me/signup?plan=free", timeout=30)
        time.sleep(10)  # Wait for SPA to fully load
        
        url = browser.get_url()
        logger.info("[STEP] 页面: %s", url[:80])
        take_screenshot(browser, "proton_initial")
        
        # Fill username
        username_filled = False
        for sel in ["#username", "input[id='username']", "input[data-testid='input-input-element']"]:
            nid = browser.query_selector(sel)
            if nid and browser.is_element_visible(nid):
                rect = browser.get_element_rect(nid)
                if rect:
                    browser.click_at(rect["center_x"], rect["center_y"])
                    time.sleep(0.5)
                    browser.type_text(account.username, delay_ms=80)
                    logger.info("[STEP] 用户名已填写: %s (via click+type)", account.username)
                    username_filled = True
                    break
        
        if not username_filled:
            # Try JS-based approach
            js = """
            (() => {
                const el = document.querySelector('#username');
                if (el) {
                    el.focus();
                    el.click();
                    return true;
                }
                return false;
            })()
            """
            if browser.evaluate(js):
                time.sleep(0.3)
                browser.type_text(account.username, delay_ms=80)
                logger.info("[STEP] 用户名已填写 (via JS focus+type)")
                username_filled = True
        
        time.sleep(1)
        
        # Fill password
        password_filled = False
        for sel in ["#password", "input[type='password']"]:
            nid = browser.query_selector(sel)
            if nid and browser.is_element_visible(nid):
                rect = browser.get_element_rect(nid)
                if rect:
                    browser.click_at(rect["center_x"], rect["center_y"])
                    time.sleep(0.5)
                    browser.type_text(account.password, delay_ms=80)
                    logger.info("[STEP] 密码已填写")
                    password_filled = True
                    break
        
        time.sleep(1)
        take_screenshot(browser, "proton_filled")
        
        # Check for CAPTCHA before submit
        captcha = detect_captcha(browser)
        logger.info("[CAPTCHA] 提交前: %s", captcha)
        
        # Check iframe content (challenge)
        iframe_info = browser.evaluate("""
            (() => {
                const iframes = document.querySelectorAll('iframe');
                return Array.from(iframes).map(f => ({
                    src: f.src,
                    title: f.title,
                    w: f.getBoundingClientRect().width,
                    h: f.getBoundingClientRect().height,
                }));
            })()
        """)
        logger.info("[IFRAMES] %s", json.dumps(iframe_info, ensure_ascii=False))
        
        # Click submit
        submitted = False
        submit_btn = browser.evaluate("""
            (() => {
                const btns = document.querySelectorAll('button[type="submit"]');
                for (const b of btns) {
                    const r = b.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0) {
                        return {x: r.x + r.width/2, y: r.y + r.height/2, text: b.textContent.trim()};
                    }
                }
                return null;
            })()
        """)
        if submit_btn:
            browser.click_at(submit_btn['x'], submit_btn['y'])
            logger.info("[STEP] 已点击提交按钮: '%s'", submit_btn.get('text', ''))
            submitted = True
        
        if not submitted:
            logger.warning("[WARN] 未找到提交按钮")
        
        # Wait for response
        time.sleep(10)
        take_screenshot(browser, "proton_after_submit")
        
        result.final_url = browser.get_url()
        body = browser.evaluate("document.body ? document.body.innerText : ''") or ""
        logger.info("[RESULT] URL: %s", result.final_url[:100])
        logger.info("[RESULT] Body: %s", body[:500])
        
        # Check for CAPTCHA/challenge after submit
        captcha = detect_captcha(browser)
        if captcha:
            logger.info("[CAPTCHA] 提交后检测到: %s", captcha)
            take_screenshot(browser, "proton_captcha")
            
            # Wait for auto-solve
            logger.info("[CAPTCHA] 等待自动解决 (60s)...")
            if wait_for_captcha_clear(browser, timeout=60):
                logger.info("[CAPTCHA] 已通过!")
                time.sleep(5)
                take_screenshot(browser, "proton_captcha_passed")
            else:
                logger.warning("[CAPTCHA] 未能自动通过")
                result.error = f"captcha: {captcha}"
        
        # Check for verification/recovery step
        body = browser.get_body_text().lower()
        if 'recovery' in body or 'recover' in body:
            logger.info("[STEP] 检测到恢复选项页面")
            # Try to skip recovery
            skip_btn = browser.evaluate("""
                (() => {
                    const btns = document.querySelectorAll('button, a');
                    for (const b of btns) {
                        const text = (b.textContent || '').toLowerCase();
                        if (text.includes('skip') || text.includes('跳过') || text.includes('maybe later')) {
                            const r = b.getBoundingClientRect();
                            if (r.width > 0) return {x: r.x + r.width/2, y: r.y + r.height/2, text: b.textContent.trim()};
                        }
                    }
                    return null;
                })()
            """)
            if skip_btn:
                browser.click_at(skip_btn['x'], skip_btn['y'])
                logger.info("[STEP] 跳过恢复选项")
                time.sleep(5)
        
        # Check for phone verification
        if 'phone' in body or 'mobile' in body:
            phone_el = browser.evaluate("""
                (() => {
                    const el = document.querySelector("input[type='tel'], input[name*='phone']");
                    if (el) {
                        const r = el.getBoundingClientRect();
                        return {visible: r.width > 0 && r.height > 0};
                    }
                    return null;
                })()
            """)
            if phone_el and phone_el.get('visible'):
                result.error = "phone_verification_required"
                logger.warning("[WARN] Proton 需要手机号验证")
        
        # Check for success
        body = browser.get_body_text().lower()
        if 'welcome' in body or 'inbox' in body or 'mail.proton.me' in result.final_url:
            result.success = True
            logger.info("[OK] Proton 注册成功! %s", account.email)
        elif 'congratulations' in body or 'created' in body:
            result.success = True
            logger.info("[OK] Proton 注册成功! %s", account.email)
        elif not result.error:
            # Check what page we're on
            elements = browser.evaluate("""
                (() => {
                    const els = document.querySelectorAll('input:not([type=hidden]), button');
                    return Array.from(els).filter(e => {
                        const r = e.getBoundingClientRect();
                        return r.width > 0 && r.height > 0;
                    }).map(e => ({
                        tag: e.tagName, type: e.type || '',
                        text: (e.textContent || e.value || '').trim().substring(0, 60),
                        id: e.id || '',
                    })).slice(0, 20);
                })()
            """)
            logger.info("[ELEMENTS] 当前页面: %s", json.dumps(elements, ensure_ascii=False, indent=2))
        
        take_screenshot(browser, "proton_final")
        browser.close()
        
    except Exception as e:
        result.error = str(e)
        logger.exception("[ERROR] Proton 异常")
        if browser:
            try:
                take_screenshot(browser, "proton_error")
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
    
    r = try_proton_full(headless=args.headless)
    print(f"\n结果: {'成功' if r.success else '失败'}  邮箱: {r.email}  密码: {r.password}")
    if r.error:
        print(f"错误: {r.error}")
