#!/usr/bin/env python3
"""
深入测试: 163.com 字母注册, Zoho 其他URL, Mail.ru 注册按钮
"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp_base import launch_browser, take_screenshot, detect_captcha
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def test_163_letter_reg():
    """163.com 字母注册 (不需手机号)"""
    logger.info("\n=== 163.com 字母注册 ===")
    browser = launch_browser(headless=False)
    browser.navigate("https://mail.163.com/register/index.htm#/pn", timeout=30)
    time.sleep(5)
    
    # Check for tab links
    tabs = browser.evaluate("""
        (() => {
            const links = document.querySelectorAll('a, [role=tab], .tab, [class*=tab]');
            return Array.from(links).filter(e => e.getBoundingClientRect().width > 0)
                .map(e => ({
                    tag: e.tagName, text: (e.textContent || '').trim().substring(0, 40),
                    href: e.href || '', class: (e.className || '').substring(0, 40),
                }));
        })()
    """)
    logger.info("Tabs/links: %s", json.dumps(tabs, ensure_ascii=False, indent=2))
    
    # Click "普通注册" tab
    clicked = browser.evaluate("""
        (() => {
            const links = document.querySelectorAll('a, [role=tab]');
            for (const l of links) {
                const text = (l.textContent || '').trim();
                if (text.includes('普通注册') || text.includes('字母')) {
                    l.click();
                    return text;
                }
            }
            return null;
        })()
    """)
    if clicked:
        logger.info("Clicked: '%s'", clicked)
        time.sleep(3)
        
        els = browser.evaluate("""
            (() => {
                return Array.from(document.querySelectorAll('input, button')).filter(e => e.getBoundingClientRect().width > 0)
                    .map(e => ({tag: e.tagName, type: e.type || '', name: e.name || '', placeholder: e.placeholder || ''}));
            })()
        """)
        logger.info("Elements after tab click: %s", json.dumps(els, ensure_ascii=False, indent=2))
    
    take_screenshot(browser, "163_tabs")
    browser.close()


def test_zoho_alt():
    """Zoho alternative URLs"""
    logger.info("\n=== Zoho alternatives ===")
    browser = launch_browser(headless=False)
    
    urls = [
        "https://www.zoho.com/mail/zohomail-pricing.html",
        "https://accounts.zoho.com/signin?signup_url=https%3A%2F%2Faccounts.zoho.com%2Fsignup",
        "https://mail.zoho.com",
    ]
    
    for url in urls:
        try:
            browser.navigate(url, timeout=15)
            time.sleep(5)
            final_url = browser.get_url()
            body = browser.evaluate("document.body ? document.body.innerText : ''") or ""
            logger.info("URL: %s → %s (body: %d chars)", url[:50], final_url[:80], len(body))
            if len(body) > 50:
                logger.info("Body: %s", body[:300])
        except Exception as e:
            logger.info("Error: %s", e)
    
    browser.close()


def test_mailru_create():
    """Mail.ru - click create account button"""
    logger.info("\n=== Mail.ru create ===")
    browser = launch_browser(headless=False)
    browser.navigate("https://account.mail.ru/signup", timeout=30)
    time.sleep(8)
    
    # Try clicking the first button (might be "Создать")
    btns = browser.evaluate("""
        (() => {
            return Array.from(document.querySelectorAll('button, a')).filter(e => e.getBoundingClientRect().width > 0)
                .map(e => ({
                    tag: e.tagName, text: (e.textContent || '').trim().substring(0, 40),
                    href: e.href || '',
                }));
        })()
    """)
    logger.info("Buttons: %s", json.dumps(btns, ensure_ascii=False, indent=2))
    
    # Click first submit button
    clicked = browser.evaluate("""
        (() => {
            const btn = document.querySelector('button[type="submit"]');
            if (btn && btn.getBoundingClientRect().width > 0) {
                btn.click();
                return btn.textContent.trim();
            }
            return null;
        })()
    """)
    if clicked:
        logger.info("Clicked: '%s'", clicked)
        time.sleep(8)
        
        url = browser.get_url()
        logger.info("New URL: %s", url)
        
        els = browser.evaluate("""
            (() => {
                return Array.from(document.querySelectorAll('input, button')).filter(e => e.getBoundingClientRect().width > 0)
                    .map(e => ({
                        tag: e.tagName, type: e.type || '', name: e.name || '',
                        placeholder: e.placeholder || '',
                        'data-test-id': e.getAttribute('data-test-id') || '',
                    }));
            })()
        """)
        logger.info("Elements: %s", json.dumps(els, ensure_ascii=False, indent=2))
        
        body = browser.evaluate("document.body ? document.body.innerText : ''") or ""
        logger.info("Body: %s", body[:500])
    
    take_screenshot(browser, "mailru_create")
    browser.close()


if __name__ == "__main__":
    test_163_letter_reg()
    test_zoho_alt()
    test_mailru_create()
