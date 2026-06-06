"""Try CDP mouse events with pointerType=touch for CAPTCHA"""
import sys, os, logging, time, random
sys.path.insert(0, os.path.dirname(__file__))
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
from cdp_outlook import _random_account, _fill_username, _fill_password, _fill_birthdate, _click_next, _fill_profile_fields, _detect_captcha
from cdp_browser import CDPBrowser, CDPLaunchConfig

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

# Get iframe position
iframe_pos = browser.evaluate("""(() => {
    const frames = document.querySelectorAll('iframe');
    for (const f of frames) {
        if ((f.src||'').includes('hsprotect') && f.offsetWidth > 50) {
            const r = f.getBoundingClientRect();
            return {left: r.left, top: r.top, width: r.width, height: r.height};
        }
    }
    return null;
})()""")
print(f"[DEBUG] Iframe: {iframe_pos}")

if iframe_pos:
    cx = iframe_pos['left'] + iframe_pos['width'] / 2
    cy = iframe_pos['top'] + iframe_pos['height'] / 2
    print(f"[DEBUG] Target: ({cx:.0f}, {cy:.0f})")
    
    # Method 1: CDP mouse with pointerType=touch
    print("[DEBUG] Method 1: CDP mousePressed + pointerType=touch")
    browser.evaluate(f"window.scrollTo(0, 0)")  # ensure no scroll offset
    time.sleep(0.2)
    
    # mousePressed
    browser._send_cmd("Input.dispatchMouseEvent", {
        "type": "mousePressed",
        "x": cx, "y": cy,
        "button": "left",
        "pointerType": "touch",
    })
    time.sleep(3.5)
    browser._send_cmd("Input.dispatchMouseEvent", {
        "type": "mouseReleased",
        "x": cx, "y": cy,
        "button": "left",
        "pointerType": "touch",
    })
    time.sleep(2)
    
    captcha = _detect_captcha(browser)
    print(f"[DEBUG] After method 1: {captcha}")
    
    if captcha and captcha['type'] == 'hsprotect':
        # Method 2: touchStart/touchEnd
        print("[DEBUG] Method 2: touchStart + touchEnd")
        browser._send_cmd("Input.dispatchTouchEvent", {
            "type": "touchStart",
            "touchPoints": [{"x": cx, "y": cy}],
        })
        time.sleep(3.5)
        browser._send_cmd("Input.dispatchTouchEvent", {
            "type": "touchEnd",
            "touchPoints": [],
        })
        time.sleep(2)
        captcha = _detect_captcha(browser)
        print(f"[DEBUG] After method 2: {captcha}")
    
    if captcha and captcha['type'] == 'hsprotect':
        # Method 3: Multiple clicks then long-press
        print("[DEBUG] Method 3: 3 quick clicks + long-press")
        for i in range(3):
            browser._send_cmd("Input.dispatchMouseEvent", {
                "type": "mousePressed",
                "x": cx + random.uniform(-5, 5), "y": cy + random.uniform(-5, 5),
                "button": "left",
                "pointerType": "touch",
            })
            time.sleep(0.1)
            browser._send_cmd("Input.dispatchMouseEvent", {
                "type": "mouseReleased",
                "x": cx + random.uniform(-5, 5), "y": cy + random.uniform(-5, 5),
                "button": "left",
                "pointerType": "touch",
            })
            time.sleep(0.3)
        time.sleep(0.5)
        browser._send_cmd("Input.dispatchMouseEvent", {
            "type": "mousePressed",
            "x": cx, "y": cy,
            "button": "left",
            "pointerType": "touch",
        })
        time.sleep(4.0)
        browser._send_cmd("Input.dispatchMouseEvent", {
            "type": "mouseReleased",
            "x": cx, "y": cy,
            "button": "left",
            "pointerType": "touch",
        })
        time.sleep(2)
        captcha = _detect_captcha(browser)
        print(f"[DEBUG] After method 3: {captcha}")

browser.close()
