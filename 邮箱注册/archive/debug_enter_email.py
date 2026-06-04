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

# Try entering a random @outlook.com email
test_email = "testuser" + str(int(time.time())) + "@outlook.com"
print(f"[1] Entering email: {test_email}")

browser.evaluate("""
    (() => {
        const input = document.querySelector('input[type=email]');
        if (input) {
            input.focus();
            input.value = '%s';
            input.dispatchEvent(new Event('input', {bubbles: true}));
            input.dispatchEvent(new Event('change', {bubbles: true}));
        }
    })()
""" % test_email)
time.sleep(0.5)

# Click Next
browser.evaluate("""(() => {
    const btns = document.querySelectorAll('button');
    for (const b of btns) {
        if ((b.textContent||'').includes('下一步') || (b.textContent||'').toLowerCase().includes('next')) {
            b.click(); return true;
        }
    }
    return false;
})()""")
print("[2] Clicked Next")
time.sleep(3)

# Check what happened
url = browser.get_url()
print(f"[3] URL: {url}")

body2 = browser.get_body_text()
print(f"[4] Body: {body2[:500]}")

# Check for password field or error
result = browser.evaluate("""
    (() => {
        const inputs = document.querySelectorAll('input');
        const out = [];
        for (const el of inputs) {
            const rect = el.getBoundingClientRect();
            const visible = window.getComputedStyle(el).display !== 'none' && rect.width > 0;
            out.push({type: el.type, name: el.name, id: el.id, visible: visible, value: el.value.substring(0, 30)});
        }
        return JSON.stringify(out, null, 2);
    })()
""")
print(f"[5] Inputs: {result}")

# Check for error messages
result = browser.evaluate("""
    (() => {
        const body = document.body.innerText;
        const error_markers = ['not available', 'already', 'taken', 'unavailable', 'error', 'invalid', '不存在', '不可用', '已被使用', '错误'];
        const found = [];
        for (const m of error_markers) {
            if (body.toLowerCase().includes(m)) found.push(m);
        }
        return JSON.stringify({errors: found, body_snippet: body.substring(0, 300)});
    })()
""")
print(f"[6] Error check: {result}")

browser.screenshot("debug_after_email.png")
print("[7] Screenshot saved")
browser.close()
