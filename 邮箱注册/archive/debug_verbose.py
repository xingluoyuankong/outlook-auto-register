import sys, io, time, os, logging
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(__file__))

logging.basicConfig(level=logging.DEBUG, format='%(name)s %(levelname)s %(message)s')

from cdp_browser import CDPBrowser, CDPLaunchConfig
from cdp_outlook import (
    _random_account, _fill_username, _fill_password, _fill_profile_fields,
    _fill_birthdate, _detect_page_state, _detect_captcha, _click_next
)

config = CDPLaunchConfig(headless=True)
browser = CDPBrowser(config).launch()
account = _random_account()

# Step 1: Navigate + consent
browser.navigate("https://signup.live.com/signup", wait_for_load=True, timeout=30)
time.sleep(3)
body = browser.get_body_text()
if "同意并继续" in body:
    browser.evaluate("(()=>{const b=document.querySelectorAll('button');for(const x of b){if((x.textContent||'').includes('同意')){x.click();return}}})()")
    time.sleep(3)
print("[STEP 1] Consent done")

# Step 2: Fill username/email
ok = _fill_username(browser, account)
print(f"[STEP 2] username={ok}")
if not ok:
    browser.screenshot("fail_step2.png")
    browser.close()
    sys.exit(1)

# Step 3: Fill password
print("[STEP 3] Filling password...")
state = _detect_page_state(browser)
print(f"    state before pwd: {state}")

# Check password field
pwd_nid = browser.query_selector("input[type='password']")
print(f"    pwd nid={pwd_nid}")
if pwd_nid:
    vis = browser.is_element_visible(pwd_nid)
    rect = browser.get_element_rect(pwd_nid)
    print(f"    pwd vis={vis} rect={rect}")

ok = _fill_password(browser, account.password)
print(f"    fill_password={ok}")

state = _detect_page_state(browser)
print(f"    state after pwd: {state}")

body = browser.get_body_text()
print(f"    body: {body[:300]}")

browser.screenshot("fail_after_pwd.png")

# Step 4: Handle whatever comes next
for i in range(10):
    state = _detect_page_state(browser)
    print(f"[STEP 4.{i}] state={state}")
    
    captcha = _detect_captcha(browser)
    if captcha:
        print(f"    CAPTCHA: {captcha}")
        browser.screenshot(f"captcha_{i}.png")
        break
    
    if state == "fill_profile":
        ok = _fill_profile_fields(browser, account)
        print(f"    fill_profile={ok}")
        time.sleep(1)
    elif state == "fill_birthdate":
        ok = _fill_birthdate(browser, account)
        print(f"    fill_birthdate={ok}")
        time.sleep(1)
    elif state in ("account_home", "success"):
        print("    SUCCESS!")
        break
    elif state == "privacy_notice":
        browser.evaluate("(()=>{const b=document.querySelectorAll('button');for(const x of b){if((x.textContent||'').includes('OK')){x.click();return}}})()")
        time.sleep(1)
    elif state == "stay_signed_in":
        browser.evaluate("(()=>{const b=document.querySelectorAll('button');for(const x of b){if((x.textContent||'').trim()==='No'){x.click();return}}})()")
        time.sleep(1)
    else:
        body = browser.get_body_text()
        print(f"    body: {body[:300]}")
        
        # Check all inputs
        result = browser.evaluate("""
            (() => {
                const inputs = document.querySelectorAll('input, select, [role=combobox]');
                const out = [];
                for (const el of inputs) {
                    const rect = el.getBoundingClientRect();
                    if (rect.width > 0) out.push({tag: el.tagName, type: el.type, name: el.name, id: el.id, role: el.getAttribute('role')});
                }
                return JSON.stringify(out);
            })()
        """)
        print(f"    inputs: {result}")
        
        # Try clicking Next anyway
        _click_next(browser)
        time.sleep(2)
        
        body2 = browser.get_body_text()
        if body2 != body:
            print(f"    body changed: {body2[:200]}")
        else:
            print("    body unchanged, stuck")
            browser.screenshot(f"stuck_{i}.png")
            break

browser.close()
print("[DONE]")
