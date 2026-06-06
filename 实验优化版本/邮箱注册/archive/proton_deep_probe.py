#!/usr/bin/env python3
"""Proton Mail deep probe - check all elements and CAPTCHA status"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp_base import launch_browser, take_screenshot, detect_captcha
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

browser = launch_browser(headless=False)
browser.navigate("https://account.proton.me/signup?plan=free", timeout=30)
time.sleep(15)  # Long wait for SPA

url = browser.get_url()
logger.info("URL: %s", url)

body = browser.evaluate("document.body ? document.body.innerText : ''") or ""
logger.info("Body length: %d", len(body))
logger.info("Body: %s", body[:1000])

# Get ALL elements including shadow DOM
all_elements = browser.evaluate("""
    (() => {
        function getElements(root) {
            const els = root.querySelectorAll('*');
            let result = [];
            for (const el of els) {
                if (el.shadowRoot) {
                    result = result.concat(getElements(el.shadowRoot));
                }
                if (['INPUT', 'BUTTON', 'SELECT', 'A', 'IFRAME'].includes(el.tagName)) {
                    const r = el.getBoundingClientRect();
                    result.push({
                        tag: el.tagName,
                        type: el.type || '',
                        text: (el.textContent || el.value || '').trim().substring(0, 80),
                        id: el.id || '',
                        name: el.name || '',
                        placeholder: el.placeholder || '',
                        visible: r.width > 0 && r.height > 0,
                        rect: r.width > 0 ? {x: r.x, y: r.y, w: r.width, h: r.height} : null,
                        src: el.src || '',
                        href: el.href || '',
                        'data-testid': el.getAttribute('data-testid') || '',
                    });
                }
            }
            return result;
        }
        return getElements(document);
    })()
""")
logger.info("All elements (%d): %s", len(all_elements), json.dumps(all_elements, ensure_ascii=False, indent=2))

# Check for CAPTCHA iframes
iframes = browser.evaluate("""
    (() => {
        return Array.from(document.querySelectorAll('iframe')).map(f => ({
            src: f.src || '',
            title: f.title || '',
            width: f.getBoundingClientRect().width,
            height: f.getBoundingClientRect().height,
        }));
    })()
""")
logger.info("Iframes: %s", json.dumps(iframes, ensure_ascii=False, indent=2))

captcha = detect_captcha(browser)
logger.info("CAPTCHA: %s", captcha)

# Check for specific Proton elements
proton_check = browser.evaluate("""
    (() => {
        const checks = {
            freePlan: !!document.querySelector('#freePlan'),
            username: !!document.querySelector('#username'),
            emailInput: !!document.querySelector('input[type="email"]'),
            anyInput: document.querySelectorAll('input').length,
            anyButton: document.querySelectorAll('button').length,
            reactRoot: !!document.querySelector('#root, #app, [data-reactroot]'),
        };
        return checks;
    })()
""")
logger.info("Proton checks: %s", proton_check)

take_screenshot(browser, "proton_deep_probe")
time.sleep(5)
browser.close()
