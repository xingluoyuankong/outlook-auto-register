#!/usr/bin/env python3
"""Proton v4 - check what disables the submit button"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp_base import launch_browser, wait_and_type
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

browser = launch_browser(headless=False)
browser.navigate("https://account.proton.me/signup?plan=free", timeout=30)
time.sleep(15)

# Wait for username to appear
for _ in range(30):
    nid = browser.query_selector("#username")
    if nid and browser.is_element_visible(nid):
        break
    time.sleep(1)
time.sleep(1)

def test_fill_and_check(uname, pwd="Abc12345!@#"):
    """Fill username + password, check button state"""
    # Clear and fill username
    js = """
    (() => {
        const u = document.querySelector('#username');
        const p = document.querySelector('#password');
        if (u) {
            u.focus();
            u.value = '';
            u.dispatchEvent(new Event('input', {bubbles:true}));
        }
        if (p) {
            p.focus();
            p.value = '';
            p.dispatchEvent(new Event('input', {bubbles:true}));
        }
    })()
    """
    browser.evaluate(js)
    time.sleep(0.5)
    
    nid = browser.query_selector("#username")
    if nid:
        rect = browser.get_element_rect(nid)
        if rect:
            browser.click_at(rect["center_x"], rect["center_y"])
            time.sleep(0.3)
            browser.type_text(uname, delay_ms=50)
    time.sleep(0.5)
    
    nid = browser.query_selector("#password")
    if nid:
        rect = browser.get_element_rect(nid)
        if rect:
            browser.click_at(rect["center_x"], rect["center_y"])
            time.sleep(0.3)
            browser.type_text(pwd, delay_ms=50)
    time.sleep(1)
    
    state = browser.evaluate("""
        (() => {
            const btn = document.querySelector('button[type="submit"]');
            const u = document.querySelector('#username');
            const p = document.querySelector('#password');
            const pc = document.querySelector('#password-confirm');
            return {
                btnDisabled: btn ? btn.disabled : 'not found',
                btnText: btn ? btn.textContent.trim() : '',
                username: u ? u.value : 'NOT FOUND',
                password: p ? p.value.length + ' chars' : 'NOT FOUND',
                passwordConfirm: pc ? {exists: true, visible: pc.getBoundingClientRect().width > 0, val: pc.value} : {exists: false},
            };
        })()
    """)
    logger.info("  uname='%s' pwd='%s' → %s", uname, pwd, json.dumps(state))
    return state

# Test various combos
test_fill_and_check("testuser")
test_fill_and_check("testuser123")
test_fill_and_check("abcd")
test_fill_and_check("u1234567")

# Also test: what if we use JS to set value and trigger React-style events
logger.info("\n--- Testing React-style value setting ---")
browser.evaluate("""
    (() => {
        function triggerReact(el, val) {
            const nativeSetter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value'
            ).set;
            nativeSetter.call(el, val);
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        }
        const u = document.querySelector('#username');
        const p = document.querySelector('#password');
        if (u) triggerReact(u, 'mason2026test');
        if (p) triggerReact(p, 'SecurePass99!@#');
    })()
""")
time.sleep(2)
state = browser.evaluate("""
    (() => {
        const btn = document.querySelector('button[type="submit"]');
        const u = document.querySelector('#username');
        const p = document.querySelector('#password');
        return {
            btnDisabled: btn ? btn.disabled : 'not found',
            username: u ? u.value : '',
            password: p ? p.value.length + ' chars' : '',
        };
    })()
""")
logger.info("  React-style: %s", json.dumps(state))

# Check for any error/hint elements
hints = browser.evaluate("""
    (() => {
        const all = document.querySelectorAll('*');
        const results = [];
        for (const el of all) {
            const text = (el.textContent || '').trim();
            const r = el.getBoundingClientRect();
            if (r.width > 0 && r.height > 0 && text.length > 0 && text.length < 100) {
                const cls = el.className || '';
                if (cls.includes && (cls.includes('error') || cls.includes('hint') || cls.includes('warn') || cls.includes('valid'))) {
                    results.push({text, class: cls.substring(0, 80)});
                }
            }
        }
        return results.slice(0, 20);
    })()
""")
logger.info("Hints/errors: %s", json.dumps(hints, ensure_ascii=False))

browser.close()
