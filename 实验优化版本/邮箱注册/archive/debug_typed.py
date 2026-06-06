import sys, io, time, os
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
        for (const b of btns) { if ((b.textContent||'').includes('同意')) { b.click(); return true; } }
        return false;
    })()""")
    time.sleep(3)

# Focus the email input and type using CDP keyboard events
print("[1] Focusing email input and typing...")
nid = browser.query_selector("input[type='email']")
if nid:
    rect = browser.get_element_rect(nid)
    print(f"  Input rect: {rect}")
    # Click to focus
    browser.click_at(rect["center_x"], rect["center_y"])
    time.sleep(0.3)
    # Type using CDP keyboard
    test_email = "testuser" + str(int(time.time())) + "@outlook.com"
    print(f"  Typing: {test_email}")
    browser.type_text(test_email, delay_ms=50)
    time.sleep(0.5)
    
    # Verify value
    val = browser.evaluate("document.querySelector('input[type=email]').value")
    print(f"  Value after typing: '{val}'")
else:
    print("  ERROR: input not found")

# Click Next
print("[2] Clicking Next...")
browser.evaluate("""(() => {
    const btns = document.querySelectorAll('button');
    for (const b of btns) {
        const t = (b.textContent||'').trim();
        if (t === '下一步' || t.toLowerCase() === 'next') { b.click(); return t; }
    }
    return false;
})()""")
time.sleep(3)

# Check result
url = browser.get_url()
print(f"[3] URL after Next: {url}")

body2 = browser.get_body_text()
print(f"[4] Body after Next (first 500):")
print(body2[:500])

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
print(f"[5] Elements: {result}")

# Check for captcha
result = browser.evaluate("""
    (() => {
        const body = document.body.innerText.toLowerCase();
        const captcha_markers = ['captcha', 'verify', 'prove', 'press and hold', 'human', 'robot'];
        const found = [];
        for (const m of captcha_markers) {
            if (body.includes(m)) found.push(m);
        }
        return JSON.stringify({captcha: found});
    })()
""")
print(f"[6] Captcha check: {result}")

browser.screenshot("debug_typed_email.png")
print("[7] Screenshot saved")
browser.close()
