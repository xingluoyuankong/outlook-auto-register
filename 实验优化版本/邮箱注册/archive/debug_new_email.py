import sys, io, time, os, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(__file__))

from cdp_browser import CDPBrowser, CDPLaunchConfig

config = CDPLaunchConfig(headless=True)
browser = CDPBrowser(config).launch()
browser.navigate("https://signup.live.com/signup", wait_for_load=True, timeout=30)
time.sleep(3)

# Handle consent
body = browser.get_body_text()
if "同意并继续" in body:
    browser.evaluate("""(() => {
        const btns = document.querySelectorAll('button');
        for (const b of btns) {
            if ((b.textContent||'').includes('同意')) { b.click(); return true; }
        }
        return false;
    })()""")
    time.sleep(3)

# Now on the "enter email" page - look for "get a new email" link
print("[1] Looking for 'get new email' link...")
result = browser.evaluate("""
    (() => {
        const all = document.querySelectorAll('a, button, span, div');
        const out = [];
        for (const el of all) {
            const t = (el.textContent || '').trim();
            if (t.length > 0 && t.length < 100) {
                const rect = el.getBoundingClientRect();
                if (rect.width > 5) {
                    out.push({tag: el.tagName, id: el.id, text: t.substring(0,80), href: el.href || '', visible: rect.width > 0});
                }
            }
        }
        return JSON.stringify(out.slice(0, 30), null, 2);
    })()
""")
print(result)

# Look specifically for liveSwitch or "new email" or "获取"
print("[2] Looking for specific elements...")
result = browser.evaluate("""
    (() => {
        const links = document.querySelectorAll('a, #liveSwitch, [id*=new], [id*=switch], [id*=live]');
        const out = [];
        for (const el of links) {
            const rect = el.getBoundingClientRect();
            out.push({
                tag: el.tagName, id: el.id, text: (el.textContent||'').substring(0,50),
                href: el.href || '', class: el.className.substring(0,50),
                visible: rect.width > 0, w: Math.round(rect.width),
            });
        }
        return JSON.stringify(out, null, 2);
    })()
""")
print(result)

# Try clicking "Get a new email address" or equivalent
print("[3] Trying to click 'get new email'...")
clicked = browser.evaluate("""
    (() => {
        // Try liveSwitch
        const ls = document.getElementById('liveSwitch');
        if (ls) { ls.click(); return 'clicked liveSwitch'; }
        // Try any link with "new email" text
        const all = document.querySelectorAll('a, button, span');
        for (const el of all) {
            const t = (el.textContent || '').toLowerCase();
            if (t.includes('new email') || t.includes('get a new') || t.includes('获取新') || t.includes('创建新')) {
                el.click();
                return 'clicked: ' + t.substring(0, 50);
            }
        }
        return 'not found';
    })()
""")
print(f"  Result: {clicked}")
time.sleep(2)

# Now check the page again
print("[4] After clicking:")
body2 = browser.get_body_text()
print(f"  Body: {body2[:300]}")

# Check inputs
result = browser.evaluate("""
    (() => {
        const inputs = document.querySelectorAll('input');
        const out = [];
        for (const el of inputs) {
            const rect = el.getBoundingClientRect();
            const visible = window.getComputedStyle(el).display !== 'none' && rect.width > 0;
            out.push({type: el.type, name: el.name, id: el.id, placeholder: el.placeholder, visible: visible});
        }
        return JSON.stringify(out, null, 2);
    })()
""")
print(f"  Inputs: {result}")

# Check for domain dropdown
result = browser.evaluate("""
    (() => {
        const selects = document.querySelectorAll('select, [role=listbox], [id*=domain]');
        const out = [];
        for (const el of selects) {
            const rect = el.getBoundingClientRect();
            out.push({tag: el.tagName, id: el.id, visible: rect.width > 0, options: el.options ? el.options.length : 0});
        }
        return JSON.stringify(out, null, 2);
    })()
""")
print(f"  Selects/dropdowns: {result}")

browser.screenshot("debug_new_email.png")
print("[5] Screenshot saved")
browser.close()
