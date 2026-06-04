#!/usr/bin/env python3
"""Proton CAPTCHA 分析 - 获取 challenge iframe 的完整内容"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp_base import launch_browser
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

browser = launch_browser(headless=False)

# Navigate to the challenge iframe URL directly
# Proton uses challenge/v4/html API
# Let's try the unauth challenge first
browser.navigate("https://account-api.proton.me/challenge/v4/html?Type=0&Name=unauth&Lang=zh-CN&Dir=ltr", timeout=30)
time.sleep(5)

# Screenshot the challenge page
snap = browser._send_cmd("Page.captureScreenshot", {"format": "png"})
import base64
with open("proton_challenge_unauth.png", "wb") as f:
    f.write(base64.b64decode(snap['data']))
logger.info("Unauth challenge screenshot saved")

# Get the page content
content = browser._send_cmd("Runtime.evaluate", {
    "expression": """
        (() => {
            return JSON.stringify({
                html: document.documentElement.innerHTML.substring(0, 10000),
                body: document.body ? document.body.innerHTML.substring(0, 5000) : 'N/A',
                title: document.title,
                bodyText: document.body ? document.body.innerText.substring(0, 2000) : '',
                allElements: Array.from(document.querySelectorAll('*')).slice(0, 50).map(el => ({
                    tag: el.tagName,
                    cls: (el.className || '').toString().substring(0, 60),
                    text: (el.textContent || '').trim().substring(0, 40),
                    id: el.id || '',
                    type: el.type || '',
                    src: el.src ? el.src.substring(0, 100) : '',
                    href: el.href ? el.href.substring(0, 100) : '',
                    value: el.value || '',
                    onclick: el.onclick ? 'yes' : '',
                    width: el.offsetWidth,
                    height: el.offsetHeight,
                })),
                scripts: Array.from(document.querySelectorAll('script')).map(s => s.src ? s.src.substring(0, 200) : '[inline]'),
                styles: Array.from(document.querySelectorAll('style')).map(s => s.textContent.substring(0, 200)),
            });
        })()
    """,
    "returnByValue": True,
})
content_data = json.loads(content.get('result', {}).get('value', '{}'))

with open("proton_unauth_challenge.json", "w", encoding="utf-8") as f:
    json.dump(content_data, f, ensure_ascii=False, indent=2)
logger.info("Unauth challenge content saved")
logger.info("Title: %s", content_data.get('title', ''))
logger.info("Body text: %s", content_data.get('bodyText', '')[:500])
logger.info("Elements: %s", json.dumps(content_data.get('allElements', [])[:10], ensure_ascii=False, indent=2))

# ===== Now try the email challenge =====
browser.navigate("https://account-api.proton.me/challenge/v4/html?Type=0&Name=email&Lang=zh-CN&Dir=ltr", timeout=30)
time.sleep(5)

snap2 = browser._send_cmd("Page.captureScreenshot", {"format": "png"})
with open("proton_challenge_email.png", "wb") as f:
    f.write(base64.b64decode(snap2['data']))
logger.info("Email challenge screenshot saved")

content2 = browser._send_cmd("Runtime.evaluate", {
    "expression": """
        (() => {
            return JSON.stringify({
                html: document.documentElement.innerHTML.substring(0, 10000),
                body: document.body ? document.body.innerHTML.substring(0, 5000) : 'N/A',
                title: document.title,
                bodyText: document.body ? document.body.innerText.substring(0, 2000) : '',
                allElements: Array.from(document.querySelectorAll('*')).slice(0, 50).map(el => ({
                    tag: el.tagName,
                    cls: (el.className || '').toString().substring(0, 60),
                    text: (el.textContent || '').trim().substring(0, 40),
                    id: el.id || '',
                    type: el.type || '',
                    src: el.src ? el.src.substring(0, 100) : '',
                    href: el.href ? el.href.substring(0, 100) : '',
                    value: el.value || '',
                    width: el.offsetWidth,
                    height: el.offsetHeight,
                })),
            });
        })()
    """,
    "returnByValue": True,
})
content2_data = json.loads(content2.get('result', {}).get('value', '{}'))

with open("proton_email_challenge.json", "w", encoding="utf-8") as f:
    json.dump(content2_data, f, ensure_ascii=False, indent=2)
logger.info("Email challenge content saved")
logger.info("Title: %s", content2_data.get('title', ''))
logger.info("Body text: %s", content2_data.get('bodyText', '')[:500])

# Keep browser open
time.sleep(15)
browser.close()
logger.info("Done! Check screenshots and JSON files")
