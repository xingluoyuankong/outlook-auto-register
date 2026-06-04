import sys, io, time, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(__file__))

from cdp_browser import CDPBrowser, CDPLaunchConfig

config = CDPLaunchConfig(headless=True)
browser = CDPBrowser(config).launch()
print("[1] Chrome launched")

browser.navigate("https://signup.live.com/signup", wait_for_load=True, timeout=30)
time.sleep(3)

# Check for privacy consent
body = browser.get_body_text()
print(f"[2] Page 1 body (first 200): {body[:200]}")

has_consent = any(kw in body.lower() for kw in ["同意并继续", "agree and continue"])
print(f"[3] Has consent page: {has_consent}")

if has_consent:
    # Click agree
    browser.evaluate("""
        (() => {
            const btns = document.querySelectorAll('button');
            for (const b of btns) {
                const t = (b.textContent || '').toLowerCase();
                if (t.includes('同意') || t.includes('agree')) { b.click(); return true; }
            }
            const next = document.getElementById('nextButton');
            if (next) { next.click(); return true; }
            return false;
        })()
    """)
    print("[4] Clicked agree")
    time.sleep(3)

# Now check what's on the page
url = browser.get_url()
print(f"[5] URL after consent: {url}")

body2 = browser.get_body_text()
print(f"[6] Page 2 body (first 500): {body2[:500]}")

# Check for username field
selectors = [
    "input[name='MemberName']",
    "input[name='Username']", 
    "input[name='email']",
    "#usernameInput",
    "input[type='email']",
    "input[autocomplete='username']",
    "input[type='text']",
]
print("[7] Trying selectors:")
for s in selectors:
    nid = browser.query_selector(s)
    vis = False
    if nid:
        vis = browser.is_element_visible(nid)
    print(f"  {s}: node_id={nid} visible={vis}")

# Dump all inputs
print("[8] All inputs:")
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
                placeholder: el.placeholder, visible: visible,
                w: Math.round(rect.width), h: Math.round(rect.height),
            });
        }
        return JSON.stringify(out, null, 2);
    })()
""")
print(result)

browser.screenshot("debug_after_consent.png")
print("[9] Screenshot saved")

browser.close()
print("[10] Done")
