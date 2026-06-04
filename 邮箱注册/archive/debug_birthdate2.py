import sys, io, time, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(__file__))

from cdp_browser import CDPBrowser, CDPLaunchConfig
from cdp_outlook import _random_account, _fill_username, _fill_password, _fill_birthdate

SS_DIR = r"E:\api获取（待跑通）\20-邮箱服务\ninjemail\browser_extension\截图"
os.makedirs(SS_DIR, exist_ok=True)

def ss(browser, name):
    path = os.path.join(SS_DIR, name)
    browser.screenshot(path)
    return path

config = CDPLaunchConfig(headless=False)
browser = CDPBrowser(config).launch()
acc = _random_account()

# Navigate + consent
browser.navigate("https://signup.live.com/signup", wait_for_load=True, timeout=30)
time.sleep(3)
body = browser.get_body_text()
if "同意并继续" in body:
    browser.evaluate("(()=>{const b=document.querySelectorAll('button');for(const x of b){if((x.textContent||'').includes('同意')){x.click();return}}})()")
    time.sleep(3)

# Fill email
_fill_username(browser, acc)
time.sleep(1)

# Fill password
_fill_password(browser, acc.password)
time.sleep(1)

browser.screenshot(os.path.join(SS_DIR, "step_before_birthdate.png"))
print(f"[1] Before birthdate, month={acc.birth_month} day={acc.birth_day} year={acc.birth_year}")

# Fill birthdate
ok = _fill_birthdate(browser, acc)
print(f"[2] fill_birthdate={ok}")

browser.screenshot(os.path.join(SS_DIR, "step_after_birthdate.png"))

# Check state
body = browser.get_body_text()
print(f"[3] body after birthdate: {body[:400]}")

# Check if we're still on birthdate page or moved on
result = browser.evaluate("""
    (() => {
        const inputs = document.querySelectorAll('input, select, [role=combobox], button[role=combobox]');
        const out = [];
        for (const el of inputs) {
            const rect = el.getBoundingClientRect();
            if (rect.width > 10) {
                out.push({tag: el.tagName, id: el.id, name: el.name, role: el.getAttribute('role'), 
                         text: (el.textContent||'').substring(0,30), visible: rect.width > 0});
            }
        }
        return JSON.stringify(out, null, 2);
    })()
""")
print(f"[4] visible elements: {result}")

# Check what month/day values are selected
result = browser.evaluate("""
    (() => {
        const monthBtn = document.getElementById('BirthMonthDropdown');
        const dayBtn = document.getElementById('BirthDayDropdown');
        const yearInput = document.querySelector('input[name=BirthYear]');
        return JSON.stringify({
            month: monthBtn ? monthBtn.textContent : null,
            day: dayBtn ? dayBtn.textContent : null,
            year: yearInput ? yearInput.value : null
        });
    })()
""")
print(f"[5] selected values: {result}")

# Try clicking Next manually
print("[6] Clicking Next...")
browser.evaluate("(()=>{const b=document.querySelectorAll('button');for(const x of b){if((x.textContent||'').trim()==='下一步'){x.click();return}}})()")
time.sleep(3)

body = browser.get_body_text()
print(f"[7] body after Next: {body[:400]}")

browser.screenshot(os.path.join(SS_DIR, "step_after_next.png"))

# Keep browser open for inspection
print("[8] Browser staying open for 30s inspection...")
time.sleep(30)
browser.close()
