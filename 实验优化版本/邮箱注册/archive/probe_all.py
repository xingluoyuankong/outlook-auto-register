#!/usr/bin/env python3
"""Quick probe: check each provider signup page accessibility"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cdp_base import launch_browser, take_screenshot, detect_captcha

PROVIDERS = [
    ("tutanota", "https://app.tuta.com/signup"),
    ("gmx", "https://signup.gmx.com/"),
    ("mailcom", "https://service.mail.com/registration.html"),
    ("proton", "https://account.proton.me/signup?plan=free"),
    ("zoho", "https://accounts.zoho.com/signup"),
    ("mailru", "https://account.mail.ru/signup"),
    ("yandex", "https://passport.yandex.com/registration/mail"),
    ("aol", "https://login.aol.com/account/create"),
    ("163", "http://reg.email.163.com/unireg/call.do?cmd=register.entrance&from=163mail"),
    ("sina", "https://mail.sina.com.cn/register/regmail.php"),
    ("sohu", "https://mail.sohu.com/reg/signup"),
]

def probe():
    browser = launch_browser(headless=False)
    results = {}
    
    for name, url in PROVIDERS:
        try:
            print(f"\n{'='*60}")
            print(f"[PROBE] {name}: {url}")
            browser.navigate(url, timeout=30)
            time.sleep(5)
            
            page_url = browser.get_url()
            captcha = detect_captcha(browser)
            body = browser.get_body_text()
            
            # Check for elements
            el_count = browser.evaluate("""
                (() => {
                    const inputs = document.querySelectorAll('input:not([type=hidden])');
                    const buttons = document.querySelectorAll('button, [type=submit]');
                    const iframes = document.querySelectorAll('iframe');
                    return {inputs: inputs.length, buttons: buttons.length, iframes: iframes.length};
                })()
            """)
            
            blocked = 'blocked' in body.lower() or '403' in body or 'reject' in page_url.lower()
            has_form = el_count and el_count.get('inputs', 0) > 0 if el_count else False
            
            results[name] = {
                "url": page_url[:100],
                "body_len": len(body),
                "captcha": captcha,
                "blocked": blocked,
                "has_form": has_form,
                "elements": el_count,
            }
            
            print(f"  URL: {page_url[:100]}")
            print(f"  Body: {len(body)} chars")
            print(f"  Captcha: {captcha}")
            print(f"  Blocked: {blocked}")
            print(f"  Has form: {has_form}")
            print(f"  Elements: {el_count}")
            
            take_screenshot(browser, f"probe_{name}")
            
        except Exception as e:
            print(f"  ERROR: {e}")
            results[name] = {"error": str(e)}
    
    browser.close()
    
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for name, r in results.items():
        status = "BLOCKED" if r.get("blocked") else ("OK" if r.get("has_form") else "UNKNOWN")
        if r.get("error"):
            status = "ERROR"
        print(f"  {name:12s} {status:10s} form={r.get('has_form')} captcha={r.get('captcha')} body={r.get('body_len', 0)}")

if __name__ == "__main__":
    probe()
