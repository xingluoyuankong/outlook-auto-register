"""Debug CAPTCHA: press on the actual button (IMG element)"""
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

# Find the actual button - look for IMG inside #human or any clickable element
btn_info = browser.evaluate("""(() => {
    // Method 1: IMG inside #human
    const img = document.querySelector('#human img, [id*=human] img');
    if (img) {
        const r = img.getBoundingClientRect();
        return {x: r.left + r.width/2, y: r.top + r.height/2, w: r.width, h: r.height, src: 'img'};
    }
    // Method 2: Any large circle element
    const divs = document.querySelectorAll('div, button, span');
    for (const d of divs) {
        const r = d.getBoundingClientRect();
        if (r.width > 80 && r.width < 250 && r.height > 80 && r.height < 250 && Math.abs(r.width - r.height) < 20) {
            const style = window.getComputedStyle(d);
            if (style.borderRadius === '50%' || style.borderRadius.includes('9999')) {
                return {x: r.left + r.width/2, y: r.top + r.height/2, w: r.width, h: r.height, src: 'circle'};
            }
        }
    }
    // Method 3: The iframe itself
    const frames = document.querySelectorAll('iframe');
    for (const f of frames) {
        if ((f.src||'').includes('hsprotect') && f.offsetWidth > 50) {
            const r = f.getBoundingClientRect();
            return {x: r.left + r.width/2, y: r.top + r.height/2, w: r.width, h: r.height, src: 'iframe'};
        }
    }
    return null;
})()""")
print(f"[DEBUG] Button info: {btn_info}")

# Get all visible interactive elements
all_els = browser.evaluate("""(() => {
    return Array.from(document.querySelectorAll('*'))
        .filter(e => e.offsetWidth > 50 && e.offsetHeight > 50 && e.offsetParent !== null)
        .map(e => {
            const r = e.getBoundingClientRect();
            return {tag: e.tagName, id: e.id, cls: (e.className||'').toString().slice(0,40), x: r.left + r.width/2, y: r.top + r.height/2, w: r.width, h: r.height};
        })
        .filter(e => e.w > 80 && e.w < 250 && e.h > 80 && e.h < 250)
        .slice(0, 20);
})()""")
print(f"[DEBUG] Large elements: {all_els}")

# Screenshot
ss = browser.screenshot("_captcha_btn.png")
print(f"[DEBUG] Screenshot: {ss}")

if btn_info:
    cx, cy = btn_info['x'], btn_info['y']
    win_x, win_y = get_browser_window_position()
    sc = browser_to_screen_coords(cx, cy, 0, 0, win_x, win_y)
    print(f"[DEBUG] Button at ({cx:.0f}, {cy:.0f}) size {btn_info['w']:.0f}x{btn_info['h']:.0f} -> screen ({sc.x}, {sc.y})")
    
    # Click to focus
    os_click(sc.x, sc.y)
    time.sleep(0.3)
    
    # Long-press
    dur = random.uniform(2.5, 4.0)
    print(f"[DEBUG] Long-press for {dur:.1f}s")
    os_long_press(sc.x, sc.y, duration=dur)
    time.sleep(2)
    
    # Check
    captcha2 = _detect_captcha(browser)
    print(f"[DEBUG] CAPTCHA after: {captcha2}")
    ss2 = browser.screenshot("_captcha_after2.png")
    print(f"[DEBUG] Screenshot after: {ss2}")

browser.close()
