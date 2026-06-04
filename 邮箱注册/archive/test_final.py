#!/usr/bin/env python3
"""Final batch: 163 普通注册, Zoho signup link, Tutanota via different entry"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp_base import launch_browser, take_screenshot, detect_captcha
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def test_163_normal():
    """163 普通注册 tab"""
    logger.info("\n=== 163.com 普通注册 ===")
    browser = launch_browser(headless=False)
    browser.navigate("https://mail.163.com/register/index.htm#/pn", timeout=30)
    time.sleep(5)
    
    # Click the "普通注册" tab (second tab row)
    browser.evaluate("""
        (() => {
            const tabs = document.querySelectorAll('[class*=tab]');
            for (const tab of tabs) {
                if (tab.textContent && tab.textContent.includes('普通注册')) {
                    tab.click();
                    return true;
                }
            }
            // Try clicking the second tab
            const allTabs = document.querySelectorAll('tr[class*=tab]');
            if (allTabs.length >= 2) {
                allTabs[1].click();
                return 'clicked second tab';
            }
            return false;
        })()
    """)
    time.sleep(3)
    
    url = browser.get_url()
    logger.info("URL: %s", url)
    
    els = browser.evaluate("""
        (() => {
            return Array.from(document.querySelectorAll('input, button')).filter(e => e.getBoundingClientRect().width > 0)
                .map(e => ({
                    tag: e.tagName, type: e.type || '', name: e.name || '',
                    placeholder: e.placeholder || '',
                    text: (e.textContent || e.value || '').trim().substring(0, 40),
                }));
        })()
    """)
    logger.info("Elements: %s", json.dumps(els, ensure_ascii=False, indent=2))
    
    body = browser.evaluate("document.body ? document.body.innerText : ''") or ""
    logger.info("Body: %s", body[:500])
    
    take_screenshot(browser, "163_normal")
    browser.close()


def test_zoho_signup():
    """Zoho - click signup link"""
    logger.info("\n=== Zoho signup ===")
    browser = launch_browser(headless=False)
    browser.navigate("https://accounts.zoho.com/signin", timeout=30)
    time.sleep(8)
    
    # Find and click "注册" link
    browser.evaluate("""
        (() => {
            const links = document.querySelectorAll('a');
            for (const l of links) {
                if (l.textContent && (l.textContent.includes('注册') || l.textContent.includes('Sign Up') || l.textContent.includes('signup'))) {
                    l.click();
                    return l.textContent.trim();
                }
            }
            return null;
        })()
    """)
    time.sleep(5)
    
    url = browser.get_url()
    logger.info("URL: %s", url)
    
    body = browser.evaluate("document.body ? document.body.innerText : ''") or ""
    logger.info("Body: %s", body[:500])
    
    els = browser.evaluate("""
        (() => {
            return Array.from(document.querySelectorAll('input, button')).filter(e => e.getBoundingClientRect().width > 0)
                .map(e => ({
                    tag: e.tagName, type: e.type || '', name: e.name || '',
                    id: e.id || '', placeholder: e.placeholder || '',
                }));
        })()
    """)
    logger.info("Elements: %s", json.dumps(els, ensure_ascii=False, indent=2))
    
    take_screenshot(browser, "zoho_signup")
    browser.close()


def test_tutanota_direct():
    """Tutanota - try waiting for JS to load, check console errors"""
    logger.info("\n=== Tutanota with console ===")
    browser = launch_browser(headless=False)
    
    # Enable console logging
    browser._send_cmd("Runtime.enable", {})
    
    browser.navigate("https://app.tuta.com/signup", timeout=30)
    time.sleep(25)  # Very long wait
    
    # Check console errors
    url = browser.get_url()
    logger.info("URL: %s", url)
    
    # Check if there's an error in the page
    page_info = browser.evaluate("""
        (() => {
            return {
                scripts: Array.from(document.querySelectorAll('script')).map(s => s.src || 'inline'),
                bodyHTML: document.body ? document.body.innerHTML.substring(0, 500) : 'no body',
                errors: window.__errors || [],
            };
        })()
    """)
    logger.info("Page info: %s", json.dumps(page_info, ensure_ascii=False, indent=2))
    
    body = browser.evaluate("document.body ? document.body.innerHTML : ''") or ""
    logger.info("Body HTML: %s", body[:500])
    
    take_screenshot(browser, "tutanota_console")
    browser.close()


if __name__ == "__main__":
    test_163_normal()
    test_zoho_signup()
    test_tutanota_direct()
