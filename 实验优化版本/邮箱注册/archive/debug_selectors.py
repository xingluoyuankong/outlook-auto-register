import sys, io, time, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(__file__))

from cdp_browser import CDPBrowser, CDPLaunchConfig
from cdp_outlook import _random_account, FIELD_SELECTORS

config = CDPLaunchConfig(headless=True)
browser = CDPBrowser(config).launch()
account = _random_account()

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

print("[1] Checking all selectors...")
for key in ["username", "domain_dropdown", "password", "submit"]:
    selectors = FIELD_SELECTORS.get(key, [])
    for s in selectors:
        nid = browser.query_selector(s)
        vis = False
        rect = None
        if nid:
            vis = browser.is_element_visible(nid)
            rect = browser.get_element_rect(nid)
        print(f"  {key}: {s} -> nid={nid} vis={vis} rect={rect}")

print("\n[2] Checking input[type=email]...")
email_nid = browser.query_selector("input[type='email']")
if email_nid:
    vis = browser.is_element_visible(email_nid)
    rect = browser.get_element_rect(email_nid)
    print(f"  email input: nid={email_nid} vis={vis} rect={rect}")
    
    if vis and rect:
        print(f"  Clicking at ({rect['center_x']}, {rect['center_y']})...")
        browser.click_at(rect['center_x'], rect['center_y'])
        time.sleep(0.3)
        print(f"  Typing: {account.email}")
        browser.type_text(account.email, delay_ms=50)
        time.sleep(0.5)
        val = browser.evaluate("document.querySelector('input[type=email]').value")
        print(f"  Value: '{val}'")
        
        # Click Next
        browser.evaluate("""(() => {
            const btns = document.querySelectorAll('button');
            for (const b of btns) {
                if ((b.textContent||'').trim() === '下一步') { b.click(); return true; }
            }
            return false;
        })()""")
        time.sleep(2)
        
        body = browser.get_body_text()
        print(f"  Body after next: {body[:300]}")
        
        # Check for password
        pwd_nid = browser.query_selector("input[type='password']")
        if pwd_nid:
            vis = browser.is_element_visible(pwd_nid)
            print(f"  Password input: nid={pwd_nid} vis={vis}")
else:
    print("  NOT FOUND")

browser.screenshot("debug_selectors.png")
browser.close()
