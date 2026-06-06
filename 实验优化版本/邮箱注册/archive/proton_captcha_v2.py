#!/usr/bin/env python3
"""Proton CAPTCHA 分析 - 获取 iframe 完整内容"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp_base import launch_browser
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

browser = launch_browser(headless=False)
browser.navigate("https://account.proton.me/signup?plan=free", timeout=30)
time.sleep(15)

# Fill form
browser.set_input_value("#username", "user_" + str(os.getpid()))
time.sleep(1)
browser.set_input_value("#password", "Pr0ton!@Test123")
time.sleep(1)
browser.set_input_value("#password-confirm", "Pr0ton!@Test123")
time.sleep(3)

# Submit
submit_info = browser._send_cmd("Runtime.evaluate", {
    "expression": """
        (() => {
            const btn = document.querySelector('button[type="submit"]');
            if (btn && !btn.disabled) {
                const r = btn.getBoundingClientRect();
                return JSON.stringify({x: r.x + r.width/2, y: r.y + r.height/2});
            }
            return 'null';
        })()
    """,
    "returnByValue": True,
})
btn_val = submit_info.get('result', {}).get('value', 'null')
if btn_val != 'null':
    btn_data = json.loads(btn_val)
    time.sleep(0.5)
    browser.click_at(btn_data['x'], btn_data['y'])
    time.sleep(8)

# Dismiss popups
for _ in range(5):
    d = browser._send_cmd("Runtime.evaluate", {
        "expression": """
            (() => {
                for (const el of document.querySelectorAll('button, a, [role="button"]')) {
                    const t = (el.textContent || '').toLowerCase().trim();
                    const r = el.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0 && r.width < 200 && r.height < 60) {
                        if (['no thanks','skip','谢谢','不用','later','decline','continue','关闭','free'].some(k => t.includes(k))) {
                            el.click(); return 'true';
                        }
                    }
                }
                return 'false';
            })()
        """,
        "returnByValue": True,
    })
    if 'true' not in str(d.get('result', {}).get('value', '')):
        break
    time.sleep(2)

time.sleep(5)

# Screenshot
snap = browser._send_cmd("Page.captureScreenshot", {"format": "png"})
import base64
with open("proton_captcha_final2.png", "wb") as f:
    f.write(base64.b64decode(snap['data']))
logger.info("Screenshot saved")

# Get iframe info
info = browser._send_cmd("Runtime.evaluate", {
    "expression": """
        (() => {
            const data = {iframes: []};
            document.querySelectorAll('iframe').forEach((f, i) => {
                const r = f.getBoundingClientRect();
                if (r.width > 0 && r.x > 0) {
                    data.iframes.push({index: i, src: f.src.substring(0, 200), x: r.x, y: r.y, w: r.width, h: r.height});
                }
            });
            data.bodyText = (document.body ? document.body.innerText : '').substring(0, 2000);
            return JSON.stringify(data);
        })()
    """,
    "returnByValue": True,
})
data = json.loads(info.get('result', {}).get('value', '{}'))
with open("proton_page_info2.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
logger.info("Ifames: %s", json.dumps(data.get('iframes', []), ensure_ascii=False))

# ===== Get iframe content via CDP DOM =====
# Get DOM root
root = browser._send_cmd("DOM.getDocument", {})
root_id = root['root']['nodeId']

# Query iframes
iframe_result = browser._send_cmd("DOM.querySelectorAll", {
    "nodeId": root_id,
    "selector": "iframe",
})
iframe_ids = iframe_result.get('nodeIds', [])
logger.info("iframe node count: %d", len(iframe_ids))

for i, nid in enumerate(iframe_ids):
    desc = browser._send_cmd("DOM.describeNode", {"nodeId": nid})
    node_attrs = desc.get('node', {}).get('attributes', [])
    src = 'unknown'
    for j in range(0, len(node_attrs)-1, 2):
        if node_attrs[j] == 'src':
            src = node_attrs[j+1]
            break
    logger.info("Iframe %d: src=%s, nodeId=%d", i, src[:80], nid)
    
    # Try to get iframe subtree via DOM.resolveNode
    try:
        resolved = browser._send_cmd("DOM.resolveNode", {"nodeId": nid})
        js_ref = resolved.get('objectId')
        logger.info("Resolved iframe %d to JS ref: %s", i, str(js_ref)[:50] if js_ref else 'None')
        
        # Get iframe contentDocument
        if js_ref:
            content_result = browser._send_cmd("Runtime.evaluate", {
                "expression": f"document.elements.fromID('iframe_{i}')?.contentDocument?.body?.innerHTML || ''",
                "objectGroup": "console",
            })
            logger.info("Content result: %s", str(content_result.get('result', {}))[:500])
    except Exception as e:
        logger.warning("Iframe %d resolve error: %s", i, e)

# Try DOMSnapshot.captureSnapshot properly
try:
    snap_dom = browser._send_cmd("DOMSnapshot.captureSnapshot", {
        "computedStyles": [],
    })
    dom_data = snap_dom.get('documents', [{}])[0]
    strings = dom_data.get('strings', [])
    nodes = dom_data.get('nodes', {})
    button_names = nodes.get('buttonNames', [])
    input_values = nodes.get('inputValues', [])
    iframe_names = nodes.get('iframeNames', [])
    
    # Convert strings from binary if needed
    str_map = {}
    for idx, s in enumerate(strings):
        if isinstance(s, bytes):
            try:
                str_map[idx] = s.decode('utf-8', errors='replace')
            except:
                str_map[idx] = s.hex()
        else:
            str_map[idx] = s
    
    with open("proton_dom_snapshot2.json", "w", encoding="utf-8") as f:
        json.dump({
            "strings": {str_map.get(i, i): s for i, s in enumerate(strings[:100])},
            "total_strings": len(strings),
            "buttonNames_raw": button_names[:50],
            "inputValues_raw": input_values[:20],
            "iframeNames_raw": iframe_names[:20],
            "buttonNames_decoded": [str_map.get(i, str(i)) for i in button_names[:20]],
            "inputValues_decoded": [str_map.get(i, str(i)) for i in input_values[:10]],
        }, f, ensure_ascii=False, indent=2)
    logger.info("DOMSnapshot succeeded! strings=%d, buttons=%d, iframes=%d", len(strings), len(button_names), len(iframe_names))
except Exception as e:
    logger.warning("DOMSnapshot failed: %s", e)

# Keep browser open
time.sleep(10)
browser.close()
logger.info("Done!")
