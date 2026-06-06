import sys, os, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ninjemail'))

from cdp_browser import CDPBrowser, CDPLaunchConfig

print("[1] import OK")
config = CDPLaunchConfig(headless=True)
browser = CDPBrowser(config)
print("[2] instance OK")
browser.launch()
print(f"[3] LAUNCHED port={browser._port} connected={browser._connected}")

r = browser._send_cmd("Runtime.evaluate", {"expression": "1+1"})
val = r.get("result", {}).get("result", {}).get("value")
print(f"[4] eval 1+1 = {val}")

body = browser.evaluate("document.body.innerText")
print(f"[5] body text: '{body[:50]}'")

# Navigate to test page
browser.navigate("data:text/html,<h1>Hello CDP</h1><input id='t'/>", wait_for_load=True, timeout=10)
import time; time.sleep(0.5)
title = browser.evaluate("document.querySelector('h1').innerText")
print(f"[6] page title: {title}")

# Query selector
nid = browser.query_selector("#t")
print(f"[7] input node_id: {nid}")

# Type text
browser.evaluate("document.getElementById('t').focus()")
time.sleep(0.1)
browser.type_text("test123", delay_ms=30)
time.sleep(0.2)
val = browser.evaluate("document.getElementById('t').value")
print(f"[8] typed value: {val}")

# Screenshot
path = browser.screenshot("test_screenshot.png")
print(f"[9] screenshot: {path}")

browser.close()
print("[10] DONE - all passed")
