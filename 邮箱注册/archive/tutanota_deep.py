#!/usr/bin/env python3
"""Tutanota deep - the page has content, need to find the form"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp_base import launch_browser, take_screenshot
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

browser = launch_browser(headless=False)
browser.navigate("https://app.tuta.com/signup", timeout=30)
time.sleep(20)

# Get the full HTML of signup-view
html = browser.evaluate("""
    (() => {
        const sv = document.querySelector('#signup-view');
        return sv ? sv.innerHTML.substring(0, 5000) : 'NOT FOUND';
    })()
""")
logger.info("signup-view HTML: %s", html)

# Try to get all elements inside signup-view (not via querySelectorAll which might not work)
els = browser.evaluate("""
    (() => {
        const sv = document.querySelector('#signup-view');
        if (!sv) return [];
        const all = sv.querySelectorAll('*');
        return Array.from(all).filter(e => {
            const r = e.getBoundingClientRect();
            return r.width > 0 && r.height > 0 && r.height < 200;
        }).map(e => ({
            tag: e.tagName, id: e.id || '', class: (e.className || '').toString().substring(0, 50),
            type: e.type || '', text: (e.textContent || '').trim().substring(0, 60),
            placeholder: e.placeholder || '',
        })).slice(0, 50);
    })()
""")
logger.info("Elements in signup-view: %s", json.dumps(els, ensure_ascii=False, indent=2))

# Get innerText of signup-view specifically
innerText = browser.evaluate("document.querySelector('#signup-view') ? document.querySelector('#signup-view').innerText : 'NOT FOUND'")
logger.info("signup-view innerText: '%s'", (innerText or '')[:1000])

take_screenshot(browser, "tutanota_signup_view")
browser.close()
