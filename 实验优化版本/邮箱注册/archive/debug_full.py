import sys, io, time, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(__file__))

from cdp_browser import CDPBrowser, CDPLaunchConfig
from cdp_outlook import (
    _random_account, _fill_username, _fill_password, _fill_profile_fields,
    _fill_birthdate, _detect_page_state, _detect_captcha, _click_next
)

config = CDPLaunchConfig(headless=True)
browser = CDPBrowser(config).launch()
account = _random_account()
print(f"[0] email={account.email} pwd={account.password}")

# Navigate
browser.navigate("https://signup.live.com/signup", wait_for_load=True, timeout=30)
time.sleep(3)

# Consent
body = browser.get_body_text()
if "同意并继续" in body:
    browser.evaluate("""(() => {
        const btns = document.querySelectorAll('button');
        for (const b of btns) { if ((b.textContent||'').includes('同意')) { b.click(); return true; } }
        return false;
    })()""")
    time.sleep(3)
    print("[1] Consent done")

# Fill username
print("[2] Filling username...")
ok = _fill_username(browser, account)
print(f"    result={ok}")
if not ok:
    browser.close()
    sys.exit(1)

# Fill password
print("[3] Filling password...")
ok = _fill_password(browser, account.password)
print(f"    result={ok}")

# Check state
state = _detect_page_state(browser)
print(f"    state after password: {state}")

body = browser.get_body_text()
print(f"    body: {body[:400]}")

# Check inputs
result = browser.evaluate("""
    (() => {
        const inputs = document.querySelectorAll('input');
        const out = [];
        for (const el of inputs) {
            const rect = el.getBoundingClientRect();
            const visible = window.getComputedStyle(el).display !== 'none' && rect.width > 0;
            out.push({type: el.type, name: el.name, id: el.id, visible: visible});
        }
        const iframes = document.querySelectorAll('iframe');
        const iframe_info = [];
        for (const f of iframes) {
            const rect = f.getBoundingClientRect();
            iframe_info.push({id: f.id, src: (f.src||'').substring(0,80), w: Math.round(rect.width), h: Math.round(rect.height)});
        }
        return JSON.stringify({inputs: out, iframes: iframe_info}, null, 2);
    })()
""")
print(f"    elements: {result}")

# Check captcha
captcha = _detect_captcha(browser)
print(f"    captcha: {captcha}")

# Step through remaining
for i in range(15):
    state = _detect_page_state(browser)
    print(f"[4.{i}] state={state}")
    
    if state == "fill_profile":
        _fill_profile_fields(browser, account)
        time.sleep(1)
    elif state == "fill_birthdate":
        _fill_birthdate(browser, account)
        time.sleep(1)
    elif state == "captcha":
        print("    CAPTCHA!")
        break
    elif state in ("account_home", "success"):
        print("    SUCCESS!")
        break
    else:
        body = browser.get_body_text()
        print(f"    body: {body[:300]}")
        
        # Check for any clickable buttons
        result = browser.evaluate("""
            (() => {
                const btns = document.querySelectorAll('button');
                const out = [];
                for (const b of btns) {
                    const rect = b.getBoundingClientRect();
                    if (rect.width > 10) out.push({id: b.id, text: (b.textContent||'').substring(0,50)});
                }
                return JSON.stringify(out);
            })()
        """)
        print(f"    buttons: {result}")
        break

browser.screenshot("debug_full_flow.png")
print("[5] Done")
browser.close()
