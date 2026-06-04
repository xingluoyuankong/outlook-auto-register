#!/usr/bin/env python3
"""
Proton Mail v3 - 检查 challenge iframe 内容并尝试通过
"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp_base import launch_browser, take_screenshot, detect_captcha
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

browser = launch_browser(headless=False)
browser.navigate("https://account.proton.me/signup?plan=free", timeout=30)
time.sleep(12)

# Check all iframes
iframes = browser.evaluate("""
    (() => {
        return Array.from(document.querySelectorAll('iframe')).map((f, i) => {
            try {
                const doc = f.contentDocument || f.contentWindow.document;
                const body = doc.body ? doc.body.innerHTML : 'no body';
                return {
                    index: i, src: f.src, title: f.title,
                    bodyLen: body.length, bodyPreview: body.substring(0, 500),
                    inputs: doc.querySelectorAll('input').length,
                    buttons: doc.querySelectorAll('button').length,
                };
            } catch(e) {
                return {index: i, src: f.src, error: e.message};
            }
        });
    })()
""")
logger.info("Iframes: %s", json.dumps(iframes, ensure_ascii=False, indent=2))

# Fill username
nid = browser.query_selector("#username")
if nid:
    rect = browser.get_element_rect(nid)
    browser.click_at(rect["center_x"], rect["center_y"])
    time.sleep(0.5)
    browser.type_text("testuser12345", delay_ms=80)
    logger.info("Username filled")

# Fill password
nid = browser.query_selector("#password")
if nid:
    rect = browser.get_element_rect(nid)
    browser.click_at(rect["center_x"], rect["center_y"])
    time.sleep(0.5)
    browser.type_text("TestPass123!@#", delay_ms=80)
    logger.info("Password filled")

# Check if username was actually set
username_val = browser.evaluate("document.querySelector('#username') ? document.querySelector('#username').value : 'NOT FOUND'")
logger.info("Username value: '%s'", username_val)

password_val = browser.evaluate("document.querySelector('#password') ? document.querySelector('#password').value : 'NOT FOUND'")
logger.info("Password value: '%s'", password_val)

# Try dispatching input events
browser.evaluate("""
    (() => {
        const username = document.querySelector('#username');
        const password = document.querySelector('#password');
        if (username) {
            username.dispatchEvent(new Event('input', {bubbles: true}));
            username.dispatchEvent(new Event('change', {bubbles: true}));
        }
        if (password) {
            password.dispatchEvent(new Event('input', {bubbles: true}));
            password.dispatchEvent(new Event('change', {bubbles: true}));
        }
    })()
""")
time.sleep(1)

# Check for error messages
errors = browser.evaluate("""
    (() => {
        const errs = document.querySelectorAll('[class*="error"], [class*="alert"], [role="alert"], .text-danger, .text-red');
        return Array.from(errs).map(e => ({
            text: (e.textContent || '').trim().substring(0, 200),
            visible: e.getBoundingClientRect().width > 0,
        }));
    })()
""")
logger.info("Errors: %s", json.dumps(errors, ensure_ascii=False))

# Try submit
submit_info = browser.evaluate("""
    (() => {
        const btn = document.querySelector('button[type="submit"]');
        if (btn) {
            const r = btn.getBoundingClientRect();
            return {x: r.x + r.width/2, y: r.y + r.height/2, text: btn.textContent.trim(), disabled: btn.disabled};
        }
        return null;
    })()
""")
logger.info("Submit button: %s", submit_info)

if submit_info and not submit_info.get('disabled'):
    browser.click_at(submit_info['x'], submit_info['y'])
    logger.info("Clicked submit")
    time.sleep(5)
    
    # Check URL after submit
    new_url = browser.get_url()
    logger.info("URL after submit: %s", new_url)
    
    # Check for new elements
    new_elements = browser.evaluate("""
        (() => {
            const els = document.querySelectorAll('input:not([type=hidden]), button[type="submit"]');
            return Array.from(els).filter(e => {
                const r = e.getBoundingClientRect();
                return r.width > 0 && r.height > 0;
            }).map(e => ({
                tag: e.tagName, type: e.type || '',
                id: e.id || '', text: (e.value || '').substring(0, 60),
            }));
        })()
    """)
    logger.info("New elements: %s", json.dumps(new_elements, ensure_ascii=False))
    
    # Check iframes after submit
    iframes_after = browser.evaluate("""
        (() => {
            return Array.from(document.querySelectorAll('iframe')).map(f => ({
                src: f.src, w: f.getBoundingClientRect().width,
                h: f.getBoundingClientRect().height,
            }));
        })()
    """)
    logger.info("Iframes after submit: %s", json.dumps(iframes_after, ensure_ascii=False))

take_screenshot(browser, "proton_v3_final")
time.sleep(5)
browser.close()
