import sys, io, time, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(__file__))

from cdp_browser import CDPBrowser, CDPLaunchConfig
from cdp_outlook import _random_account, _fill_username, _fill_password

config = CDPLaunchConfig(headless=True)
browser = CDPBrowser(config).launch()
account = _random_account()

# Navigate + consent
browser.navigate("https://signup.live.com/signup", wait_for_load=True, timeout=30)
time.sleep(3)
body = browser.get_body_text()
if "同意并继续" in body:
    browser.evaluate("(()=>{const b=document.querySelectorAll('button');for(const x of b){if((x.textContent||'').includes('同意')){x.click();return}}})()")
    time.sleep(3)

# Fill email + password
_fill_username(browser, account)
_fill_password(browser, account.password)

# Now on birthdate page - dump ALL interactive elements
print("[1] All interactive elements on birthdate page:")
result = browser.evaluate("""
    (() => {
        const all = document.querySelectorAll('*');
        const out = [];
        for (const el of all) {
            const rect = el.getBoundingClientRect();
            if (rect.width < 5 || rect.height < 5) continue;
            const role = el.getAttribute('role');
            const aria = el.getAttribute('aria-haspopup') || '';
            const tag = el.tagName;
            const id = el.id;
            const name = el.name || '';
            const cls = (el.className || '').toString().substring(0, 60);
            const text = (el.textContent || '').substring(0, 30).trim();
            
            if (tag === 'SELECT' || tag === 'INPUT' || role === 'combobox' || role === 'listbox' || 
                aria === 'listbox' || id.includes('Month') || id.includes('Day') || id.includes('Year') ||
                id.includes('country') || name.includes('Month') || name.includes('Day') || 
                name.includes('Birth') || name.includes('Country')) {
                out.push({tag, id, name, role, aria, cls, text, w: Math.round(rect.width), h: Math.round(rect.height), 
                          x: Math.round(rect.x), y: Math.round(rect.y)});
            }
        }
        return JSON.stringify(out, null, 2);
    })()
""")
print(result)

# Look specifically for Fluent UI dropdowns
print("\n[2] Fluent UI dropdowns (button with aria-haspopup):")
result = browser.evaluate("""
    (() => {
        const btns = document.querySelectorAll('button[aria-haspopup], [role=combobox], [role=listbox]');
        const out = [];
        for (const el of btns) {
            const rect = el.getBoundingClientRect();
            if (rect.width > 0) {
                out.push({
                    tag: el.tagName, id: el.id, 
                    role: el.getAttribute('role'),
                    aria: el.getAttribute('aria-haspopup'),
                    ariaLabel: el.getAttribute('aria-label'),
                    text: (el.textContent || '').substring(0, 50),
                    cls: (el.className || '').substring(0, 80),
                    w: Math.round(rect.width), h: Math.round(rect.height),
                });
            }
        }
        return JSON.stringify(out, null, 2);
    })()
""")
print(result)

# Try clicking the month dropdown and see options
print("\n[3] Trying to interact with month dropdown...")
result = browser.evaluate("""
    (() => {
        // Find month-related element
        const monthHints = ['month', '月', 'BirthMonth'];
        for (const hint of monthHints) {
            const els = document.querySelectorAll('[aria-label*="' + hint + '"], [id*="' + hint + '"], [name*="' + hint + '"]');
            for (const el of els) {
                const rect = el.getBoundingClientRect();
                if (rect.width > 10) {
                    el.click();
                    return JSON.stringify({found: hint, tag: el.tagName, id: el.id, x: rect.x + rect.width/2, y: rect.y + rect.height/2});
                }
            }
        }
        // Try any button/dropdown in the birthdate area
        const btns = document.querySelectorAll('button');
        for (const b of btns) {
            const rect = b.getBoundingClientRect();
            if (rect.width > 50 && rect.width < 400 && rect.y > 400) {
                const t = (b.textContent || '').trim();
                if (t.length < 30 && !t.includes('下一步') && !t.includes('帮助')) {
                    return JSON.stringify({found: 'button', text: t, id: b.id, x: rect.x + rect.width/2, y: rect.y + rect.height/2});
                }
            }
        }
        return JSON.stringify({found: 'none'});
    })()
""")
print(f"  Clicked: {result}")
time.sleep(1)

# Check for dropdown options
print("\n[4] Dropdown options after click:")
result = browser.evaluate("""
    (() => {
        const opts = document.querySelectorAll('[role=option], [role=listbox] > *, option, li[role]');
        const out = [];
        for (const el of opts) {
            const rect = el.getBoundingClientRect();
            if (rect.width > 0) {
                out.push({text: (el.textContent || '').substring(0, 30), role: el.getAttribute('role'), id: el.id});
            }
        }
        return JSON.stringify(out.slice(0, 20), null, 2);
    })()
""")
print(result)

browser.screenshot("debug_birthdate.png")
print("\n[5] Screenshot saved")
browser.close()
