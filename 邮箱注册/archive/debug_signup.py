import sys, io, time, json, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(__file__))

from cdp_browser import CDPBrowser, CDPLaunchConfig

config = CDPLaunchConfig(headless=True)
browser = CDPBrowser(config).launch()
print("[1] Chrome launched")

browser.navigate("https://signup.live.com/signup", wait_for_load=True, timeout=30)
time.sleep(3)

url = browser.get_url()
print(f"[2] URL: {url}")

body = browser.get_body_text()
print(f"[3] Body text (first 500):")
print(body[:500])

selectors = [
    "input[name='MemberName']",
    "input[name='Username']",
    "input[name='email']",
    "#usernameInput",
    "input[type='email']",
    "input[autocomplete='username']",
    "input[type='text']",
    "input[name='login']",
    "input[name='Email']",
    "input[id='MemberName']",
    "input[id='i0116']",
]
print("[4] Trying selectors:")
for s in selectors:
    nid = browser.query_selector(s)
    vis = False
    if nid:
        vis = browser.is_element_visible(nid)
    print(f"  {s}: node_id={nid} visible={vis}")

print("[5] All inputs:")
result = browser.evaluate("""
    (() => {
        const inputs = document.querySelectorAll('input');
        const out = [];
        for (const el of inputs) {
            const rect = el.getBoundingClientRect();
            const style = window.getComputedStyle(el);
            const visible = style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0;
            out.push({
                type: el.type, name: el.name, id: el.id,
                placeholder: el.placeholder, autocomplete: el.autocomplete,
                visible: visible, w: Math.round(rect.width), h: Math.round(rect.height),
            });
        }
        return JSON.stringify(out, null, 2);
    })()
""")
print(result)

print("[6] All buttons:")
result = browser.evaluate("""
    (() => {
        const btns = document.querySelectorAll('button, input[type=submit], a[role=button]');
        const out = [];
        for (const el of btns) {
            const rect = el.getBoundingClientRect();
            if (rect.width > 10) {
                out.push({tag: el.tagName, id: el.id, text: (el.innerText || el.value || '').substring(0, 50)});
            }
        }
        return JSON.stringify(out, null, 2);
    })()
""")
print(result)

# Dump all iframes
print("[7] All iframes:")
result = browser.evaluate("""
    (() => {
        const frames = document.querySelectorAll('iframe');
        const out = [];
        for (const f of frames) {
            const rect = f.getBoundingClientRect();
            out.push({id: f.id, src: (f.src || '').substring(0, 100), w: Math.round(rect.width), h: Math.round(rect.height)});
        }
        return JSON.stringify(out, null, 2);
    })()
""")
print(result)

browser.screenshot("debug_signup.png")
print("[8] Screenshot saved")

browser.close()
print("[9] Done")
