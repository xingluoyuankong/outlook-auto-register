#!/usr/bin/env python3
"""Quick probe to find Proton signup form selectors"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp_browser import CDPBrowser, CDPLaunchConfig

config = CDPLaunchConfig(
    browser_type="chrome",
    headless=False,
    window_size=(1366, 768),
    user_data_dir=os.path.join(os.path.dirname(os.path.abspath(__file__)), "chrome_profile_proton"),
)
browser = CDPBrowser(config)
browser.launch()
browser.navigate("https://account.proton.me/signup?plan=free", timeout=60)

# Wait for page to load
time.sleep(15)

# Dump all input elements
inputs = browser.evaluate("""
(() => {
    const inputs = document.querySelectorAll('input, textarea, select');
    return JSON.stringify([...inputs].map(el => ({
        tag: el.tagName,
        id: el.id,
        name: el.name,
        type: el.type,
        placeholder: el.placeholder || '',
        className: el.className.substring(0, 100),
        ariaLabel: el.getAttribute('aria-label') || '',
        autocomplete: el.autocomplete || '',
        rect: {x: el.getBoundingClientRect().x, y: el.getBoundingClientRect().y, w: el.getBoundingClientRect().width, h: el.getBoundingClientRect().height}
    })));
})()
""")
print("=== INPUT ELEMENTS ===")
print(json.dumps(json.loads(inputs) if isinstance(inputs, str) else inputs, indent=2, ensure_ascii=False))

# Also dump all buttons
buttons = browser.evaluate("""
(() => {
    const btns = document.querySelectorAll('button, [role="button"], a.btn');
    return JSON.stringify([...btns].map(el => ({
        tag: el.tagName,
        id: el.id,
        text: (el.textContent || '').trim().substring(0, 50),
        type: el.type || '',
        disabled: el.disabled || false,
        className: el.className.substring(0, 100),
        rect: {x: el.getBoundingClientRect().x, y: el.getBoundingClientRect().y, w: el.getBoundingClientRect().width, h: el.getBoundingClientRect().height}
    })));
})()
""")
print("\n=== BUTTONS ===")
print(json.dumps(json.loads(buttons) if isinstance(buttons, str) else buttons, indent=2, ensure_ascii=False))

# Take screenshot
r = browser._send_cmd("Page.captureScreenshot", {"format": "png"})
import base64
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "proton_steps", "probe_page.png"), "wb") as f:
    f.write(base64.b64decode(r['data']))
print("\nScreenshot saved to proton_steps/probe_page.png")

time.sleep(5)
browser.close()
