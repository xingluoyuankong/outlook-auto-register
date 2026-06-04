#!/usr/bin/env python3
"""
实际注册测试 - 逐个跑通可用的提供商
"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cdp_base import (
    AccountInfo, RegistrationResult, generate_account, launch_browser,
    wait_and_click, wait_and_type, set_value_and_dispatch, click_submit,
    select_dropdown_by_text, detect_captcha, wait_for_captcha_clear,
    take_screenshot, save_result, random_string,
)

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "live_run.log")
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ]
)
logger = logging.getLogger(__name__)


def try_proton(headless=False):
    """Proton Mail 注册实跑"""
    account = generate_account("proton", "proton.me")
    result = RegistrationResult(
        provider="proton", domain="proton.me",
        email=account.email, password=account.password, username=account.username,
    )
    browser = None
    try:
        logger.info("=== Proton Mail 实跑 ===")
        logger.info("邮箱: %s  密码: %s", account.email, account.password)
        
        browser = launch_browser(headless=headless)
        result.browser = browser
        
        browser.navigate("https://account.proton.me/signup?plan=free", timeout=30)
        time.sleep(5)
        
        url = browser.get_url()
        logger.info("[STEP] 页面: %s", url[:80])
        take_screenshot(browser, "proton_initial")
        
        # 检查是否有免费计划按钮
        body = browser.get_body_text().lower()
        logger.info("[INFO] Body preview: %s", body[:200])
        
        # 获取所有可见元素
        elements = browser.evaluate("""
            (() => {
                const els = document.querySelectorAll('input:not([type=hidden]), button, a[href], [role=button], [role=link]');
                return Array.from(els).filter(e => {
                    const r = e.getBoundingClientRect();
                    return r.width > 0 && r.height > 0;
                }).map(e => ({
                    tag: e.tagName,
                    type: e.type || '',
                    text: (e.textContent || e.value || '').trim().substring(0, 80),
                    id: e.id || '',
                    name: e.name || '',
                    placeholder: e.placeholder || '',
                    href: e.href || '',
                })).slice(0, 50);
            })()
        """)
        logger.info("[ELEMENTS] %s", json.dumps(elements, ensure_ascii=False, indent=2))
        
        captcha = detect_captcha(browser)
        logger.info("[CAPTCHA] %s", captcha)
        
        # 尝试找用户名输入框
        username_selectors = [
            "#username", "input[name='username']",
            "input[id*='email' i]", "input[autocomplete='username']",
            "input[placeholder*='email' i]", "input[placeholder*='user' i]",
        ]
        found = False
        for sel in username_selectors:
            nid = browser.query_selector(sel)
            if nid and browser.is_element_visible(nid):
                logger.info("[FOUND] Username input: %s", sel)
                found = True
                break
        
        if not found:
            logger.info("[INFO] No username input found yet - may need to click 'Free' plan first")
            # Try to find and click free plan button
            free_selectors = [
                "#freePlan", "[data-testid='free-plan']",
                "button:has-text('free')", "a:has-text('free')",
            ]
            for sel in free_selectors:
                if wait_and_click(browser, sel, timeout=3):
                    logger.info("[STEP] Clicked free plan: %s", sel)
                    time.sleep(3)
                    break
        
        take_screenshot(browser, "proton_after_click")
        
        # Now try to fill username
        for sel in username_selectors:
            if wait_and_type(browser, sel, account.username, timeout=5):
                logger.info("[STEP] Username filled: %s", account.username)
                result.success = True
                break
        
        if not result.success:
            # Try JS-based fill
            for sel in username_selectors:
                nid = browser.query_selector(sel)
                if nid:
                    rect = browser.get_element_rect(nid)
                    if rect:
                        browser.click_at(rect["center_x"], rect["center_y"])
                        time.sleep(0.5)
                        browser.type_text(account.username, delay_ms=80)
                        logger.info("[STEP] Username typed via click+type")
                        result.success = True
                        break
        
        time.sleep(3)
        take_screenshot(browser, "proton_final")
        result.final_url = browser.get_url()
        
        if keep_browser:
            result.browser = browser
        else:
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


def try_tutanota(headless=False):
    """Tutanota 注册实跑"""
    account = generate_account("tutanota", "tuta.com")
    result = RegistrationResult(
        provider="tutanota", domain="tuta.com",
        email=account.email, password=account.password, username=account.username,
    )
    browser = None
    try:
        logger.info("=== Tutanota 实跑 ===")
        logger.info("邮箱: %s  密码: %s", account.email, account.password)
        
        browser = launch_browser(headless=headless)
        result.browser = browser
        
        browser.navigate("https://app.tuta.com/signup", timeout=30)
        time.sleep(10)  # SPA needs more time
        
        url = browser.get_url()
        logger.info("[STEP] 页面: %s", url[:80])
        take_screenshot(browser, "tutanota_initial")
        
        # Check what's on the page
        elements = browser.evaluate("""
            (() => {
                const els = document.querySelectorAll('input, button, a, [role=button], [role=link], [role=tab], select');
                return Array.from(els).filter(e => {
                    const r = e.getBoundingClientRect();
                    return r.width > 0 && r.height > 0;
                }).map(e => ({
                    tag: e.tagName,
                    type: e.type || '',
                    text: (e.textContent || e.value || '').trim().substring(0, 80),
                    id: e.id || '',
                    name: e.name || '',
                    placeholder: e.placeholder || '',
                    'data-testid': e.getAttribute('data-testid') || '',
                })).slice(0, 50);
            })()
        """)
        logger.info("[ELEMENTS] %s", json.dumps(elements, ensure_ascii=False, indent=2))
        
        # Try to find signup form elements
        body_text = browser.evaluate("document.body ? document.body.innerText : ''") or ""
        logger.info("[BODY] Length: %d, Preview: %s", len(body_text), body_text[:300])
        
        captcha = detect_captcha(browser)
        logger.info("[CAPTCHA] %s", captcha)
        
        # Look for email/username input
        email_selectors = [
            "input[name='mailAddress']", "input[id*='email' i]",
            "input[placeholder*='email' i]", "input[type='email']",
            "input[autocomplete='email']", "input.mailAddress",
        ]
        for sel in email_selectors:
            if wait_and_type(browser, sel, account.username, timeout=3):
                logger.info("[STEP] Email filled: %s", account.username)
                break
        
        take_screenshot(browser, "tutanota_final")
        result.final_url = browser.get_url()
        
        browser.close()
    except Exception as e:
        result.error = str(e)
        logger.exception("[ERROR] Tutanota 异常")
        if browser:
            try:
                take_screenshot(browser, "tutanota_error")
                browser.close()
            except:
                pass
    
    save_result(result)
    return result


def try_yandex(headless=False):
    """Yandex 注册实跑"""
    account = generate_account("yandex", "yandex.com")
    result = RegistrationResult(
        provider="yandex", domain="yandex.com",
        email=account.email, password=account.password, username=account.username,
    )
    browser = None
    try:
        logger.info("=== Yandex 实跑 ===")
        logger.info("邮箱: %s  密码: %s", account.email, account.password)
        
        browser = launch_browser(headless=headless)
        result.browser = browser
        
        browser.navigate("https://passport.yandex.com/registration/mail", timeout=30)
        time.sleep(5)
        
        url = browser.get_url()
        logger.info("[STEP] 页面: %s", url[:80])
        take_screenshot(browser, "yandex_initial")
        
        # Get page elements
        elements = browser.evaluate("""
            (() => {
                const els = document.querySelectorAll('input:not([type=hidden]), button, select, [role=button]');
                return Array.from(els).filter(e => {
                    const r = e.getBoundingClientRect();
                    return r.width > 0 && r.height > 0;
                }).map(e => ({
                    tag: e.tagName,
                    type: e.type || '',
                    text: (e.textContent || e.value || '').trim().substring(0, 60),
                    id: e.id || '',
                    name: e.name || '',
                    placeholder: e.placeholder || '',
                    'data-t': e.getAttribute('data-t') || '',
                })).slice(0, 40);
            })()
        """)
        logger.info("[ELEMENTS] %s", json.dumps(elements, ensure_ascii=False, indent=2))
        
        body_text = browser.evaluate("document.body ? document.body.innerText : ''") or ""
        logger.info("[BODY] Length: %d, Preview: %s", len(body_text), body_text[:300])
        
        captcha = detect_captcha(browser)
        logger.info("[CAPTCHA] %s", captcha)
        
        # Fill form fields
        # First name
        for sel in ["#field-firstname", "input[name='firstname']", "input[data-t='field:input-firstname']"]:
            if wait_and_type(browser, sel, account.first_name, timeout=3):
                logger.info("[STEP] First name: %s", account.first_name)
                break
        
        # Last name
        for sel in ["#field-lastname", "input[name='lastname']", "input[data-t='field:input-lastname']"]:
            if wait_and_type(browser, sel, account.last_name, timeout=3):
                logger.info("[STEP] Last name: %s", account.last_name)
                break
        
        # Login/username
        for sel in ["#field-login", "input[name='login']", "input[data-t='field:input-login']"]:
            if wait_and_type(browser, sel, account.username, timeout=3):
                logger.info("[STEP] Login: %s", account.username)
                break
        
        # Password
        for sel in ["#field-password", "input[name='password']", "input[data-t='field:input-password']"]:
            if wait_and_type(browser, sel, account.password, timeout=3):
                logger.info("[STEP] Password filled")
                break
        
        # Confirm password
        for sel in ["#field-password_confirm", "input[name='password_confirm']"]:
            wait_and_type(browser, sel, account.password, timeout=2)
        
        take_screenshot(browser, "yandex_filled")
        
        # Check for phone/captcha
        captcha = detect_captcha(browser)
        if captcha:
            logger.info("[CAPTCHA] After fill: %s", captcha)
            take_screenshot(browser, "yandex_captcha")
        
        # Try submit
        click_submit(browser)
        time.sleep(5)
        
        take_screenshot(browser, "yandex_after_submit")
        result.final_url = browser.get_url()
        
        # Check for phone verification
        body = browser.get_body_text().lower()
        if 'phone' in body or 'mobile' in body or 'sms' in body:
            result.error = "phone_verification_required"
            logger.warning("[WARN] Yandex requires phone verification")
        
        browser.close()
    except Exception as e:
        result.error = str(e)
        logger.exception("[ERROR] Yandex 异常")
        if browser:
            try:
                take_screenshot(browser, "yandex_error")
                browser.close()
            except:
                pass
    
    save_result(result)
    return result


def try_aol(headless=False):
    """AOL 注册实跑"""
    account = generate_account("aol", "aol.com")
    result = RegistrationResult(
        provider="aol", domain="aol.com",
        email=account.email, password=account.password, username=account.username,
    )
    browser = None
    try:
        logger.info("=== AOL 实跑 ===")
        logger.info("邮箱: %s  密码: %s", account.email, account.password)
        
        browser = launch_browser(headless=headless)
        result.browser = browser
        
        browser.navigate("https://login.aol.com/account/create", timeout=30)
        time.sleep(5)
        
        url = browser.get_url()
        logger.info("[STEP] 页面: %s", url[:80])
        take_screenshot(browser, "aol_initial")
        
        elements = browser.evaluate("""
            (() => {
                const els = document.querySelectorAll('input:not([type=hidden]), button, select');
                return Array.from(els).filter(e => {
                    const r = e.getBoundingClientRect();
                    return r.width > 0 && r.height > 0;
                }).map(e => ({
                    tag: e.tagName,
                    type: e.type || '',
                    text: (e.textContent || e.value || '').trim().substring(0, 60),
                    id: e.id || '',
                    name: e.name || '',
                    placeholder: e.placeholder || '',
                })).slice(0, 40);
            })()
        """)
        logger.info("[ELEMENTS] %s", json.dumps(elements, ensure_ascii=False, indent=2))
        
        captcha = detect_captcha(browser)
        logger.info("[CAPTCHA] %s", captcha)
        
        # Fill form
        for sel in ["#user-first-name", "input[name='firstName']"]:
            if wait_and_type(browser, sel, account.first_name, timeout=3):
                logger.info("[STEP] First name: %s", account.first_name)
                break
        
        for sel in ["#user-last-name", "input[name='lastName']"]:
            if wait_and_type(browser, sel, account.last_name, timeout=3):
                logger.info("[STEP] Last name: %s", account.last_name)
                break
        
        for sel in ["#user-name", "input[name='userId']", "input[name='username']"]:
            if wait_and_type(browser, sel, account.username, timeout=3):
                logger.info("[STEP] Username: %s", account.username)
                break
        
        for sel in ["#user-passwd", "input[name='password']"]:
            if wait_and_type(browser, sel, account.password, timeout=3):
                logger.info("[STEP] Password filled")
                break
        
        take_screenshot(browser, "aol_filled")
        
        # Submit
        click_submit(browser)
        time.sleep(5)
        
        take_screenshot(browser, "aol_after_submit")
        result.final_url = browser.get_url()
        
        body = browser.get_body_text().lower()
        if 'phone' in body or 'mobile' in body:
            result.error = "phone_verification_required"
            logger.warning("[WARN] AOL requires phone verification")
        elif 'captcha' in body or 'verify' in body:
            result.error = "captcha_required"
            logger.warning("[WARN] AOL requires CAPTCHA")
        
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


def try_sina(headless=False):
    """Sina 注册实跑"""
    account = generate_account("sina", "sina.com")
    result = RegistrationResult(
        provider="sina", domain="sina.com",
        email=account.email, password=account.password, username=account.username,
    )
    browser = None
    try:
        logger.info("=== Sina 实跑 ===")
        logger.info("邮箱: %s  密码: %s", account.email, account.password)
        
        browser = launch_browser(headless=headless)
        result.browser = browser
        
        browser.navigate("https://mail.sina.com.cn/register/regmail.php", timeout=30)
        time.sleep(5)
        
        url = browser.get_url()
        logger.info("[STEP] 页面: %s", url[:80])
        take_screenshot(browser, "sina_initial")
        
        elements = browser.evaluate("""
            (() => {
                const els = document.querySelectorAll('input:not([type=hidden]), button, select');
                return Array.from(els).filter(e => {
                    const r = e.getBoundingClientRect();
                    return r.width > 0 && r.height > 0;
                }).map(e => ({
                    tag: e.tagName,
                    type: e.type || '',
                    text: (e.textContent || e.value || '').trim().substring(0, 60),
                    id: e.id || '',
                    name: e.name || '',
                    placeholder: e.placeholder || '',
                })).slice(0, 40);
            })()
        """)
        logger.info("[ELEMENTS] %s", json.dumps(elements, ensure_ascii=False, indent=2))
        
        captcha = detect_captcha(browser)
        logger.info("[CAPTCHA] %s", captcha)
        
        body_text = browser.evaluate("document.body ? document.body.innerText : ''") or ""
        logger.info("[BODY] %s", body_text[:300])
        
        # Fill email
        for sel in ["#emailName", "input[name='email']", "input[placeholder*='邮箱']"]:
            if wait_and_type(browser, sel, account.username, timeout=3):
                logger.info("[STEP] Email: %s", account.username)
                break
        
        # Password
        for sel in ["#password", "input[name='password']"]:
            if wait_and_type(browser, sel, account.password, timeout=3):
                logger.info("[STEP] Password filled")
                break
        
        # Confirm password
        for sel in ["#password2", "input[name*='confirm']"]:
            wait_and_type(browser, sel, account.password, timeout=2)
        
        take_screenshot(browser, "sina_filled")
        
        # Check for phone requirement
        for sel in ["input[name='phone']", "input[type='tel']", "input[placeholder*='手机']"]:
            nid = browser.query_selector(sel)
            if nid and browser.is_element_visible(nid):
                result.error = "phone_verification_required"
                logger.warning("[WARN] Sina requires phone verification")
                take_screenshot(browser, "sina_phone_required")
                browser.close()
                save_result(result)
                return result
        
        # Submit
        click_submit(browser)
        time.sleep(5)
        
        take_screenshot(browser, "sina_after_submit")
        result.final_url = browser.get_url()
        
        browser.close()
    except Exception as e:
        result.error = str(e)
        logger.exception("[ERROR] Sina 异常")
        if browser:
            try:
                take_screenshot(browser, "sina_error")
                browser.close()
            except:
                pass
    
    save_result(result)
    return result


def try_zoho(headless=False):
    """Zoho 注册实跑"""
    account = generate_account("zoho", "zohomail.com")
    result = RegistrationResult(
        provider="zoho", domain="zohomail.com",
        email=account.email, password=account.password, username=account.username,
    )
    browser = None
    try:
        logger.info("=== Zoho 实跑 ===")
        logger.info("邮箱: %s  密码: %s", account.email, account.password)
        
        browser = launch_browser(headless=headless)
        result.browser = browser
        
        browser.navigate("https://accounts.zoho.com/signup", timeout=30)
        time.sleep(8)  # JS-heavy page
        
        url = browser.get_url()
        logger.info("[STEP] 页面: %s", url[:80])
        take_screenshot(browser, "zoho_initial")
        
        body_text = browser.evaluate("document.body ? document.body.innerText : ''") or ""
        logger.info("[BODY] Length: %d, Preview: %s", len(body_text), body_text[:300])
        
        elements = browser.evaluate("""
            (() => {
                const els = document.querySelectorAll('input:not([type=hidden]), button, select');
                return Array.from(els).filter(e => {
                    const r = e.getBoundingClientRect();
                    return r.width > 0 && r.height > 0;
                }).map(e => ({
                    tag: e.tagName,
                    type: e.type || '',
                    text: (e.textContent || e.value || '').trim().substring(0, 60),
                    id: e.id || '',
                    name: e.name || '',
                    placeholder: e.placeholder || '',
                })).slice(0, 40);
            })()
        """)
        logger.info("[ELEMENTS] %s", json.dumps(elements, ensure_ascii=False, indent=2))
        
        captcha = detect_captcha(browser)
        logger.info("[CAPTCHA] %s", captcha)
        
        # Fill form
        for sel in ["#luid", "input[name='luid']", "input[type='email']"]:
            if wait_and_type(browser, sel, account.email, timeout=3):
                logger.info("[STEP] Email: %s", account.email)
                break
        
        for sel in ["#lupasswd", "input[name='lupasswd']", "input[type='password']"]:
            if wait_and_type(browser, sel, account.password, timeout=3):
                logger.info("[STEP] Password filled")
                break
        
        take_screenshot(browser, "zoho_filled")
        
        # Check for phone
        for sel in ["input[name='phone']", "input[type='tel']", "input[id*='phone']"]:
            nid = browser.query_selector(sel)
            if nid and browser.is_element_visible(nid):
                result.error = "phone_verification_required"
                logger.warning("[WARN] Zoho requires phone")
                break
        
        click_submit(browser)
        time.sleep(5)
        
        take_screenshot(browser, "zoho_after_submit")
        result.final_url = browser.get_url()
        
        browser.close()
    except Exception as e:
        result.error = str(e)
        logger.exception("[ERROR] Zoho 异常")
        if browser:
            try:
                take_screenshot(browser, "zoho_error")
                browser.close()
            except:
                pass
    
    save_result(result)
    return result


def try_mailru(headless=False):
    """Mail.ru 注册实跑"""
    account = generate_account("mailru", "mail.ru")
    result = RegistrationResult(
        provider="mailru", domain="mail.ru",
        email=account.email, password=account.password, username=account.username,
    )
    browser = None
    try:
        logger.info("=== Mail.ru 实跑 ===")
        logger.info("邮箱: %s  密码: %s", account.email, account.password)
        
        browser = launch_browser(headless=headless)
        result.browser = browser
        
        browser.navigate("https://account.mail.ru/signup", timeout=30)
        time.sleep(8)
        
        url = browser.get_url()
        logger.info("[STEP] 页面: %s", url[:80])
        take_screenshot(browser, "mailru_initial")
        
        body_text = browser.evaluate("document.body ? document.body.innerText : ''") or ""
        logger.info("[BODY] Length: %d, Preview: %s", len(body_text), body_text[:300])
        
        elements = browser.evaluate("""
            (() => {
                const els = document.querySelectorAll('input:not([type=hidden]), button, select');
                return Array.from(els).filter(e => {
                    const r = e.getBoundingClientRect();
                    return r.width > 0 && r.height > 0;
                }).map(e => ({
                    tag: e.tagName,
                    type: e.type || '',
                    text: (e.textContent || e.value || '').trim().substring(0, 60),
                    id: e.id || '',
                    name: e.name || '',
                    placeholder: e.placeholder || '',
                    'data-test-id': e.getAttribute('data-test-id') || '',
                })).slice(0, 40);
            })()
        """)
        logger.info("[ELEMENTS] %s", json.dumps(elements, ensure_ascii=False, indent=2))
        
        captcha = detect_captcha(browser)
        logger.info("[CAPTCHA] %s", captcha)
        
        # Fill form
        for sel in ["input[name='firstname']", "input[data-test-id='first-name-input']"]:
            if wait_and_type(browser, sel, account.first_name, timeout=3):
                logger.info("[STEP] First name: %s", account.first_name)
                break
        
        for sel in ["input[name='lastname']", "input[data-test-id='last-name-input']"]:
            if wait_and_type(browser, sel, account.last_name, timeout=3):
                logger.info("[STEP] Last name: %s", account.last_name)
                break
        
        take_screenshot(browser, "mailru_filled")
        
        click_submit(browser)
        time.sleep(5)
        
        take_screenshot(browser, "mailru_after_submit")
        result.final_url = browser.get_url()
        
        browser.close()
    except Exception as e:
        result.error = str(e)
        logger.exception("[ERROR] Mail.ru 异常")
        if browser:
            try:
                take_screenshot(browser, "mailru_error")
                browser.close()
            except:
                pass
    
    save_result(result)
    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", default="proton", help="Provider to test")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--keep-browser", action="store_true")
    args = parser.parse_args()
    
    keep_browser = args.keep_browser
    
    providers = {
        "proton": try_proton,
        "tutanota": try_tutanota,
        "yandex": try_yandex,
        "aol": try_aol,
        "sina": try_sina,
        "zoho": try_zoho,
        "mailru": try_mailru,
    }
    
    fn = providers.get(args.provider)
    if fn:
        r = fn(headless=args.headless)
        print(f"\n结果: {'成功' if r.success else '失败'}  邮箱: {r.email}  密码: {r.password}")
        if r.error:
            print(f"错误: {r.error}")
    else:
        print(f"未知提供商: {args.provider}")
        print(f"可用: {', '.join(providers.keys())}")
