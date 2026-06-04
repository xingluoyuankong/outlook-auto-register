"""Debug CAPTCHA: screenshot + try different press positions"""
import sys, os, logging, time, random
sys.path.insert(0, os.path.dirname(__file__))
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
from cdp_outlook import _random_account, _fill_username, _fill_password, _fill_birthdate, _click_next, _fill_profile_fields, _detect_captcha, _detect_page_state
from cdp_browser import CDPBrowser, CDPLaunchConfig
from os_input import os_click, os_long_press, get_browser_window_position, browser_to_screen_coords

account = _random_account()
config = CDPLaunchConfig()
browser = CDPBrowser(config).launch()

browser.navigate("https://signup.live.com/signup", wait_for_load=True, timeout=30)
time.sleep(3)

# Consent
for _ in range(3):
    body = browser.get_body_text().lower()
    if "同意" in body or "agree" in body:
        browser.evaluate("(() => { const btns = document.querySelectorAll('button'); for(const b of btns){const t=(b.textContent||'').toLowerCase(); if(t.includes('agree')||t.includes('同意')){b.click();return true;}} return false;})()")
        time.sleep(2)
    else:
        break

_fill_username(browser, account); time.sleep(1); _click_next(browser); time.sleep(2)
_fill_password(browser, account.password); time.sleep(1); _click_next(browser); time.sleep(2)
_fill_birthdate(browser, account); time.sleep(1); _click_next(browser); time.sleep(2)
_fill_profile_fields(browser, account); time.sleep(1); _click_next(browser); time.sleep(3)

print(f"[DEBUG] State: {_detect_page_state(browser)}")
captcha = _detect_captcha(browser)
print(f"[DEBUG] CAPTCHA: {captcha}")

# Get iframe position
iframe_pos = browser.evaluate("""(() => {
    const frames = document.querySelectorAll('iframe');
    for (const f of frames) {
        const src = (f.src || '').toLowerCase();
        if (src.includes('hsprotect') && f.offsetWidth > 50) {
            const r = f.getBoundingClientRect();
            return {left: r.left, top: r.top, width: r.width, height: r.height, right: r.right, bottom: r.bottom};
        }
    }
    return null;
})()""")
print(f"[DEBUG] Iframe pos: {iframe_pos}")

# Get window position
win_x, win_y = get_browser_window_position()
print(f"[DEBUG] Window pos: ({win_x}, {win_y})")

# Screenshot before press
ss1 = browser.screenshot("_captcha_before.png")
print(f"[DEBUG] Screenshot before: {ss1}")

# Try pressing at center of iframe using OS input
if iframe_pos:
    cx = iframe_pos['left'] + iframe_pos['width'] / 2
    cy = iframe_pos['top'] + iframe_pos['height'] / 2
    sc = browser_to_screen_coords(cx, cy, 0, 0, win_x, win_y)
    print(f"[DEBUG] Iframe center: ({cx:.0f}, {cy:.0f}) -> screen ({sc.x}, {sc.y})")
    
    # First click to focus
    os_click(sc.x, sc.y)
    time.sleep(0.5)
    
    # Then long-press
    print(f"[DEBUG] OS long-press at ({sc.x}, {sc.y})")
    os_long_press(sc.x, sc.y, duration=4.0)
    time.sleep(2)

# Screenshot after
ss2 = browser.screenshot("_captcha_after.png")
print(f"[DEBUG] Screenshot after: {ss2}")

# Check if CAPTCHA cleared
captcha2 = _detect_captcha(browser)
print(f"[DEBUG] CAPTCHA after: {captcha2}")

browser.close()
