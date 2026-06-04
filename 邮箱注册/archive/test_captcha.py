"""Run full registration and screenshot CAPTCHA page"""
import sys, os, logging, time
sys.path.insert(0, os.path.dirname(__file__))
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
from cdp_outlook import register_outlook_account, _random_account, _detect_page_state, _detect_captcha
from cdp_outlook import _fill_username, _fill_password, _fill_birthdate, _click_next, _fill_profile_fields
from cdp_outlook import _handle_post_challenge
from cdp_browser import CDPBrowser, CDPLaunchConfig

account = _random_account()
print(f"[TEST] Account: {account.email}")

config = CDPLaunchConfig()
browser = CDPBrowser(config).launch()

# Navigate
browser.navigate("https://signup.live.com/signup", wait_for_load=True, timeout=30)
time.sleep(3)

# Consent page
for _ in range(3):
    body = browser.get_body_text().lower()
    if "同意" in body or "agree" in body:
        browser.evaluate("(() => { const btns = document.querySelectorAll('button'); for(const b of btns){const t=(b.textContent||'').toLowerCase(); if(t.includes('agree')||t.includes('同意')){b.click();return true;}} return false;})()")
        time.sleep(2)
    else:
        break

# Fill form
_fill_username(browser, account)
time.sleep(1)
_click_next(browser)
time.sleep(2)
_fill_password(browser, account.password)
time.sleep(1)
_click_next(browser)
time.sleep(2)
_fill_birthdate(browser, account)
time.sleep(1)
_click_next(browser)
time.sleep(2)
_fill_profile_fields(browser, account)
time.sleep(1)
_click_next(browser)
time.sleep(3)

# Now on CAPTCHA page - screenshot
print(f"[TEST] State: {_detect_page_state(browser)}")
captcha = _detect_captcha(browser)
print(f"[TEST] CAPTCHA: {captcha}")

ss = browser.screenshot("_captcha_page.png")
print(f"[TEST] Screenshot saved: {ss}")

# Also dump all iframes
iframes = browser.evaluate("(() => { const frames = document.querySelectorAll('iframe'); return Array.from(frames).map(f => ({src: f.src, w: f.offsetWidth, h: f.offsetHeight, vis: f.offsetParent!==null, id: f.id, name: f.name})); })()")
print(f"[TEST] Iframes: {iframes}")

# Get all elements on page
all_els = browser.evaluate("(() => { return Array.from(document.querySelectorAll('*')).filter(e => e.offsetWidth > 10 && e.offsetParent !== null).map(e => e.tagName + '#' + e.id + '.' + (e.className||'').toString().slice(0,30) + ' ' + e.offsetWidth + 'x' + e.offsetHeight).slice(0, 50); })()")
print(f"[TEST] Visible elements: {all_els}")

browser.close()
