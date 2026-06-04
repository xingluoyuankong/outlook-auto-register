#!/usr/bin/env python3
"""Quick Sohu registration probe"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp_base import launch_browser, take_screenshot, detect_captcha
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

browser = launch_browser(headless=False)
browser.navigate("https://mail.sohu.com/reg/signup", timeout=30)
time.sleep(8)

url = browser.get_url()
logger.info("URL: %s", url)
body = browser.evaluate("document.body ? document.body.innerText : ''") or ""
logger.info("Body length: %d", len(body))
logger.info("Body: %s", body[:500])

elements = browser.evaluate("""
    (() => {
        const els = document.querySelectorAll('input:not([type=hidden]), button, select, iframe');
        return Array.from(els).map(e => ({
            tag: e.tagName, type: e.type || '',
            text: (e.textContent || e.value || '').trim().substring(0, 60),
            id: e.id || '', name: e.name || '',
            src: e.src || '',
        })).slice(0, 30);
    })()
""")
logger.info("Elements: %s", elements)

take_screenshot(browser, "sohu_probe")
time.sleep(3)
browser.close()
