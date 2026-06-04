import sys, io, time, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(__file__))

from cdp_browser import CDPBrowser, CDPLaunchConfig
from cdp_outlook import _random_account

config = CDPLaunchConfig(headless=True)
browser = CDPBrowser(config).launch()
acc = _random_account()

# Navigate + consent
browser.navigate("https://signup.live.com/signup", wait_for_load=True, timeout=30)
time.sleep(3)
body = browser.get_body_text()
if "同意并继续" in body:
    browser.evaluate("(()=>{const b=document.querySelectorAll('button');for(const x of b){if((x.textContent||'').includes('同意')){x.click();return}}})()")
    time.sleep(3)
print("[1] consent done")

# Fill email
nid = browser.query_selector("input[type='email']")
rect = browser.get_element_rect(nid)
browser.click_at(rect["center_x"], rect["center_y"])
time.sleep(0.3)
browser.type_text(acc.email, delay_ms=50)
time.sleep(0.5)
print(f"[2] typed email: {acc.email}")

# Click Next
browser.evaluate("(()=>{const b=document.querySelectorAll('button');for(const x of b){if((x.textContent||'').trim()==='下一步'){x.click();return}}})()")
time.sleep(3)

# Check page
body = browser.get_body_text()
print(f"[3] body: {body[:200]}")

# Find password field
pwd_nid = browser.query_selector("input[type='password']")
if pwd_nid:
    vis = browser.is_element_visible(pwd_nid)
    rect = browser.get_element_rect(pwd_nid)
    print(f"[4] pwd: nid={pwd_nid} vis={vis} rect={rect}")
    if vis and rect:
        browser.click_at(rect["center_x"], rect["center_y"])
        time.sleep(0.3)
        browser.type_text(acc.password, delay_ms=50)
        time.sleep(0.5)
        val = browser.evaluate("document.querySelector('input[type=password]').value")
        print(f"[5] pwd value len={len(val)}")
        
        # Click Next
        browser.evaluate("(()=>{const b=document.querySelectorAll('button');for(const x of b){if((x.textContent||'').trim()==='下一步'){x.click();return}}})()")
        time.sleep(3)
        
        body = browser.get_body_text()
        print(f"[6] body: {body[:400]}")
        
        # Check for profile/birthdate fields
        result = browser.evaluate("""
            (() => {
                const inputs = document.querySelectorAll('input, select');
                const out = [];
                for (const el of inputs) {
                    const rect = el.getBoundingClientRect();
                    if (rect.width > 0) out.push({tag: el.tagName, type: el.type, name: el.name, id: el.id});
                }
                return JSON.stringify(out);
            })()
        """)
        print(f"[7] elements: {result}")
else:
    print("[4] NO password field found!")

browser.screenshot("debug_manual_flow.png")
browser.close()
