#!/usr/bin/env python3
"""
全面测试剩余提供商: Zoho, Mail.ru, Tutanota (更长等待)
"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp_base import launch_browser, take_screenshot, detect_captcha, set_value_and_dispatch
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "live_run.log"), encoding="utf-8"),
    ]
)
logger = logging.getLogger(__name__)


def test_tutanota():
    """Tutanota with much longer wait and Shadow DOM check"""
    logger.info("\n=== Tutanota (长等待) ===")
    browser = launch_browser(headless=False)
    browser.navigate("https://app.tuta.com/signup", timeout=30)
    time.sleep(20)  # Much longer wait for SPA
    
    url = browser.get_url()
    logger.info("URL: %s", url)
    
    # Check Shadow DOM
    shadow_info = browser.evaluate("""
        (() => {
            function findShadowRoots(root) {
                let results = [];
                const els = root.querySelectorAll('*');
                for (const el of els) {
                    if (el.shadowRoot) {
                        results.push({
                            tag: el.tagName, id: el.id, class: el.className,
                            shadowChildren: el.shadowRoot.children.length,
                            shadowHTML: el.shadowRoot.innerHTML.substring(0, 300),
                        });
                        results = results.concat(findShadowRoots(el.shadowRoot));
                    }
                }
                return results;
            }
            return findShadowRoots(document);
        })()
    """)
    logger.info("Shadow DOM: %s", json.dumps(shadow_info, ensure_ascii=False, indent=2))
    
    # Check all elements including in shadow DOM
    all_els = browser.evaluate("""
        (() => {
            function getElements(root) {
                let result = [];
                const els = root.querySelectorAll('input, button, a, [role=button], select');
                for (const el of els) {
                    const r = el.getBoundingClientRect();
                    result.push({
                        tag: el.tagName, type: el.type || '', id: el.id || '',
                        text: (el.textContent || el.value || '').trim().substring(0, 60),
                        visible: r.width > 0 && r.height > 0,
                    });
                }
                // Check shadow roots
                const all = root.querySelectorAll('*');
                for (const el of all) {
                    if (el.shadowRoot) {
                        result = result.concat(getElements(el.shadowRoot));
                    }
                }
                return result;
            }
            return getElements(document);
        })()
    """)
    logger.info("All elements (incl shadow): %s", json.dumps(all_els, ensure_ascii=False, indent=2))
    
    body = browser.evaluate("document.body ? document.body.innerText : ''") or ""
    logger.info("Body: '%s'", body[:500])
    
    html = browser.evaluate("document.documentElement ? document.documentElement.outerHTML.substring(0, 2000) : ''") or ""
    logger.info("HTML preview: %s", html[:1000])
    
    take_screenshot(browser, "tutanota_deep")
    browser.close()


def test_zoho():
    """Zoho with longer wait"""
    logger.info("\n=== Zoho ===")
    browser = launch_browser(headless=False)
    browser.navigate("https://accounts.zoho.com/signup", timeout=30)
    time.sleep(12)
    
    url = browser.get_url()
    logger.info("URL: %s", url)
    
    body = browser.evaluate("document.body ? document.body.innerText : ''") or ""
    logger.info("Body length: %d", len(body))
    logger.info("Body: %s", body[:500])
    
    els = browser.evaluate("""
        (() => {
            return Array.from(document.querySelectorAll('input, button, select')).map(e => ({
                tag: e.tagName, type: e.type || '', id: e.id || '', name: e.name || '',
                text: (e.textContent || e.value || '').trim().substring(0, 60),
                visible: e.getBoundingClientRect().width > 0,
            }));
        })()
    """)
    logger.info("Elements: %s", json.dumps(els, ensure_ascii=False, indent=2))
    
    take_screenshot(browser, "zoho_test")
    browser.close()


def test_mailru():
    """Mail.ru with click on create button"""
    logger.info("\n=== Mail.ru ===")
    browser = launch_browser(headless=False)
    browser.navigate("https://account.mail.ru/signup", timeout=30)
    time.sleep(10)
    
    url = browser.get_url()
    logger.info("URL: %s", url)
    
    body = browser.evaluate("document.body ? document.body.innerText : ''") or ""
    logger.info("Body: %s", body[:500])
    
    els = browser.evaluate("""
        (() => {
            return Array.from(document.querySelectorAll('input, button, a')).filter(e => e.getBoundingClientRect().width > 0)
                .map(e => ({
                    tag: e.tagName, type: e.type || '', id: e.id || '',
                    text: (e.textContent || e.value || '').trim().substring(0, 60),
                    'data-test-id': e.getAttribute('data-test-id') || '',
                }));
        })()
    """)
    logger.info("Elements: %s", json.dumps(els, ensure_ascii=False, indent=2))
    
    # Try clicking "Создать" (Create) button if present
    clicked = browser.evaluate("""
        (() => {
            const btns = document.querySelectorAll('button');
            for (const b of btns) {
                const text = (b.textContent || '').trim();
                if (text.includes('Создать') || text.includes('Create') || text.includes('注册')) {
                    b.click();
                    return text;
                }
            }
            return null;
        })()
    """)
    if clicked:
        logger.info("Clicked: '%s'", clicked)
        time.sleep(5)
        
        els2 = browser.evaluate("""
            (() => {
                return Array.from(document.querySelectorAll('input, button')).filter(e => e.getBoundingClientRect().width > 0)
                    .map(e => ({
                        tag: e.tagName, type: e.type || '', id: e.id || '',
                        text: (e.textContent || e.value || '').trim().substring(0, 60),
                        'data-test-id': e.getAttribute('data-test-id') || '',
                        placeholder: e.placeholder || '',
                    }));
            })()
        """)
        logger.info("After click elements: %s", json.dumps(els2, ensure_ascii=False, indent=2))
    
    take_screenshot(browser, "mailru_test")
    browser.close()


def test_163():
    """163.com alternative URL"""
    logger.info("\n=== 163.com ===")
    browser = launch_browser(headless=False)
    # Try alternative URL
    browser.navigate("https://mail.163.com/register/index.htm", timeout=30)
    time.sleep(8)
    
    url = browser.get_url()
    logger.info("URL: %s", url)
    
    body = browser.evaluate("document.body ? document.body.innerText : ''") or ""
    logger.info("Body: %s", body[:500])
    
    els = browser.evaluate("""
        (() => {
            return Array.from(document.querySelectorAll('input, button')).filter(e => e.getBoundingClientRect().width > 0)
                .map(e => ({
                    tag: e.tagName, type: e.type || '', id: e.id || '', name: e.name || '',
                    placeholder: e.placeholder || '',
                }));
        })()
    """)
    logger.info("Elements: %s", json.dumps(els, ensure_ascii=False, indent=2))
    
    take_screenshot(browser, "163_test")
    browser.close()


if __name__ == "__main__":
    test_tutanota()
    test_zoho()
    test_mailru()
    test_163()
