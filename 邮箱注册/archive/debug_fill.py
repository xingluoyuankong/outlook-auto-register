import sys, io, time, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(__file__))

from cdp_browser import CDPBrowser, CDPLaunchConfig
from cdp_outlook import _random_account, _fill_username, FIELD_SELECTORS

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

print("[1] Testing _fill_username with debug...")
print(f"    account.email={account.email}")

# Manually replicate _fill_username logic
has_domain_dropdown = False
for dd_selector in FIELD_SELECTORS["domain_dropdown"]:
    try:
        nid = browser.query_selector(dd_selector)
        if nid and browser.is_element_visible(nid):
            has_domain_dropdown = True
            print(f"    Found domain dropdown: {dd_selector}")
            break
    except Exception:
        continue
print(f"    has_domain_dropdown={has_domain_dropdown}")

if not has_domain_dropdown:
    print("    Using NEW flow (single email input)...")
    email_input = browser.query_selector("input[type='email']")
    print(f"    email_input nid={email_input}")
    if email_input:
        vis = browser.is_element_visible(email_input)
        print(f"    visible={vis}")
        rect = browser.get_element_rect(email_input)
        print(f"    rect={rect}")
        if vis and rect:
            browser.click_at(rect["center_x"], rect["center_y"])
            time.sleep(0.3)
            browser.type_text(account.email, delay_ms=50)
            time.sleep(0.5)
            val = browser.evaluate("document.querySelector('input[type=email]').value")
            print(f"    typed value='{val}'")
            
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
            has_pwd = "创建密码" in body or "password" in body.lower()
            print(f"    has password page: {has_pwd}")
            print(f"    body: {body[:200]}")
        else:
            print("    NOT visible or no rect!")
    else:
        print("    email input NOT FOUND!")

# Now test the actual function
print("\n[2] Testing actual _fill_username function...")
browser2 = CDPBrowser(CDPLaunchConfig(headless=True)).launch()
browser2.navigate("https://signup.live.com/signup", wait_for_load=True, timeout=30)
time.sleep(3)
body = browser2.get_body_text()
if "同意并继续" in body:
    browser2.evaluate("""(() => {
        const btns = document.querySelectorAll('button');
        for (const b of btns) { if ((b.textContent||'').includes('同意')) { b.click(); return true; } }
        return false;
    })()""")
    time.sleep(3)

result = _fill_username(browser2, account)
print(f"    _fill_username result={result}")
if result:
    body = browser2.get_body_text()
    print(f"    body after: {body[:200]}")

browser.close()
browser2.close()
