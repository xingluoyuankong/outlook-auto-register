import sys, io, time, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(__file__))

from cdp_browser import CDPBrowser, CDPLaunchConfig
from cdp_outlook import (
    _random_account, _fill_username, _fill_password, _fill_profile_fields,
    _fill_birthdate, _detect_page_state, _detect_captcha,
    FIELD_SELECTORS, POST_CHALLENGE_MARKERS
)

config = CDPLaunchConfig(headless=True)
browser = CDPBrowser(config).launch()
account = _random_account()
print(f"[0] email={account.email}")

# Navigate
browser.navigate("https://signup.live.com/signup", wait_for_load=True, timeout=30)
time.sleep(3)

# Consent
body = browser.get_body_text()
if "同意并继续" in body:
    print("[1] Consent page found, clicking agree...")
    browser.evaluate("""(() => {
        const btns = document.querySelectorAll('button');
        for (const b of btns) { if ((b.textContent||'').includes('同意')) { b.click(); return true; } }
        return false;
    })()""")
    time.sleep(3)
else:
    print("[1] No consent page")

# Fill username
print("[2] Filling username...")
state = _detect_page_state(browser)
print(f"    state before: {state}")

ok = _fill_username(browser, account)
print(f"    fill_username result: {ok}")
time.sleep(1)

state = _detect_page_state(browser)
print(f"    state after username: {state}")

if not ok:
    print("    FAILED at username!")
    browser.screenshot("debug_fail_username.png")
    browser.close()
    sys.exit(1)

# Fill password
print("[3] Filling password...")
ok = _fill_password(browser, account.password)
print(f"    fill_password result: {ok}")
time.sleep(1)

state = _detect_page_state(browser)
print(f"    state after password: {state}")

# Check what's on the page
body = browser.get_body_text()
print(f"    body: {body[:300]}")

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
        return JSON.stringify(out, null, 2);
    })()
""")
print(f"    inputs: {result}")

# Check for captcha
captcha = _detect_captcha(browser)
print(f"[4] captcha: {captcha}")

# Continue step by step
for step in range(10):
    state = _detect_page_state(browser)
    print(f"[5] Step {step}: state={state}")
    
    if state == "fill_profile":
        _fill_profile_fields(browser, account)
        time.sleep(1)
        continue
    elif state == "fill_birthdate":
        _fill_birthdate(browser, account)
        time.sleep(1)
        continue
    elif state == "captcha":
        print("    CAPTCHA detected! type:", _detect_captcha(browser))
        break
    elif state in ("account_home", "success", "privacy_notice", "stay_signed_in"):
        print(f"    Reached: {state}")
        break
    else:
        body = browser.get_body_text()
        print(f"    body: {body[:200]}")
        break

browser.screenshot("debug_step_by_step.png")
print("[6] Screenshot saved")
browser.close()
