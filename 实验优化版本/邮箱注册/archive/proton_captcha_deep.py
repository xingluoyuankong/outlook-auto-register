#!/usr/bin/env python3
"""
Proton CAPTCHA 完整分析 - 一次性获取所有信息
"""
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
btn = browser.evaluate("""
    (() => {
        const btn = document.querySelector('button[type="submit"]');
        if (btn && !btn.disabled) {
            const r = btn.getBoundingClientRect();
            return {x: r.x + r.width/2, y: r.y + r.height/2};
        }
        return null;
    })()
""")
if btn:
    browser.click_at(btn['x'], btn['y'])
    time.sleep(8)

# Dismiss all popups
for _ in range(5):
    dismissed = browser.evaluate("""
        (() => {
            const els = document.querySelectorAll('button, a, [role="button"]');
            const dismissKws = ['no thanks', 'skip', '谢谢', '不用', 'later', 'decline', 'continue', '关闭', 'free'];
            for (const el of els) {
                const text = (el.textContent || '').toLowerCase().trim();
                const r = el.getBoundingClientRect();
                if (r.width > 0 && r.height > 0 && r.width < 200 && r.height < 60) {
                    for (const kw of dismissKws) {
                        if (text.includes(kw)) {
                            el.click();
                            return true;
                        }
                    }
                }
            }
            return false;
        })()
    """)
    if not dismissed:
        break
    time.sleep(2)

# Wait for captcha
time.sleep(5)

# ===== 一次性获取所有信息 =====
result = browser.evaluate("""
    (() => {
        // Get all iframes
        const allIframes = Array.from(document.querySelectorAll('iframe'));
        
        // Get the full page HTML
        const bodyText = (document.body ? document.body.innerText : '').substring(0, 2000);
        
        // Find captcha-related text
        const captchaText = bodyText.match(/(?:(?:CAPTCHA|human|verify|challenge|人机|验证)[^。\n]{0,200})/g);
        
        // Get all visible elements
        const allElements = Array.from(document.querySelectorAll('*'))
            .filter(el => {
                const r = el.getBoundingClientRect();
                return r.width > 0 && r.height > 0 && r.x > 0 && r.x < 2000;
            })
            .slice(0, 100)
            .map(el => {
                const r = el.getBoundingClientRect();
                return {
                    tag: el.tagName,
                    cls: (el.className || '').toString().substring(0, 80),
                    id: el.id || '',
                    text: (el.textContent || '').trim().substring(0, 60),
                    x: Math.round(r.x), y: Math.round(r.y),
                    w: Math.round(r.width), h: Math.round(r.height),
                    inputType: el.type || '',
                    inputName: el.name || '',
                    placeholder: el.placeholder || '',
                    ariaLabel: el.getAttribute('aria-label') || '',
                    role: el.getAttribute('role') || '',
                    src: el.getAttribute('src') || '',
                    onClick: el.getAttribute('onclick') || '',
                };
            });
        
        return {
            iframes: allIframes.map(f => ({
                src: f.src,
                x: Math.round(f.getBoundingClientRect().x),
                y: Math.round(f.getBoundingClientRect().y),
                w: Math.round(f.getBoundingClientRect().width),
                h: Math.round(f.getBoundingClientRect().height),
            })),
            bodyText: bodyText,
            elements: allElements,
            captchaText: captchaText ? captchaText.slice(0, 5).join(' | ') : 'none',
        };
    })()
""")

with open("proton_full_page_analysis.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
logger.info("Full page analysis saved")

# Print key info
logger.info("Iframes: %s", json.dumps(result.get('iframes', []), ensure_ascii=False))
logger.info("Captcha text: %s", result.get('captchaText', 'none'))

# Get elements from captcha area (near the iframes)
captcha_area_elements = []
iframes = result.get('iframes', [])
for frame in iframes:
    # Get elements near this iframe
    nearby = browser.evaluate(f"""
        (() => {{
            const x = {frame['x']}, y = {frame['y']}, w = {frame['w']}, h = {frame['h']};
            const els = Array.from(document.querySelectorAll('*'))
                .filter(el => {{
                    const r = el.getBoundingClientRect();
                    return r.width > 0 && r.height > 0 &&
                           r.x >= Math.max(0, x-50) && r.x <= Math.min(x+w+50, 2000) &&
                           r.y >= Math.max(0, y-50) && r.y <= Math.min(y+h+50, 2000);
                }})
                .slice(0, 20)
                .map(el => {{
                    const r = el.getBoundingClientRect();
                    return {{
                        tag: el.tagName,
                        cls: (el.className || '').toString().substring(0, 80),
                        text: (el.textContent || '').trim().substring(0, 40),
                        x: Math.round(r.x), y: Math.round(r.y),
                        w: Math.round(r.width), h: Math.round(r.height),
                    }};
                }});
            return els;
        }})()
    """)
    captcha_area_elements.append({
        "iframe_src": frame['src'][:80],
        "elements": nearby,
    })

with open("proton_captcha_area_elements.json", "w", encoding="utf-8") as f:
    json.dump(captcha_area_elements, f, ensure_ascii=False, indent=2)
logger.info("Captcha area elements: %s", json.dumps(captcha_area_elements, ensure_ascii=False, indent=2)[:1000])

# ===== 截图 =====
# Full page
result_png = browser._send_cmd("Page.captureScreenshot", {"format": "png"})
import base64
img_data = base64.b64decode(result_png['data'])
with open("proton_final_screenshot.png", "wb") as f:
    f.write(img_data)
logger.info("Full screenshot saved")

# CDP drag the captcha iframe content
# Get captcha iframe src URL
captcha_src = next((f['src'] for f in iframes if 'captcha' in f['src']), None)
challenge_unauth = next((f['src'] for f in iframes if 'unauth' in f['src']), None)
challenge_email = next((f['src'] for f in iframes if 'email' in f['src']), None)

logger.info("Captcha src: %s", captcha_src)
logger.info("Unauth challenge: %s", challenge_unauth)
logger.info("Email challenge: %s", challenge_email)

# The Proton captcha uses challenge/v4/html API - it's a Proton custom captcha
# Let's try to directly fetch the captcha challenge HTML using CDP protocol
if challenge_unauth or challenge_email:
    # Navigate to the captcha iframe URL in a new page
    # Actually, let's use CDP to get the iframe's content directly
    captcha_info = browser.evaluate("""
        (() => {
            // Try to access the iframe's document
            const allFrames = document.querySelectorAll('iframe');
            const results = [];
            for (const iframe of allFrames) {
                try {
                    const frameDoc = iframe.contentDocument || iframe.contentWindow.document;
                    results.push({
                        src_prefix: iframe.src.substring(0, 80),
                        hasContent: !!frameDoc,
                        bodyText: frameDoc ? (frameDoc.body ? frameDoc.body.innerText : '').substring(0, 500) : 'N/A',
                        bodyHTML: frameDoc ? frameDoc.documentElement.outerHTML.substring(0, 2000) : 'N/A',
                        crossOrigin: frameDoc ? (frameDoc.location ? frameDoc.location.origin : 'N/A') : 'N/A',
                    });
                } catch(e) {
                    results.push({
                        src_prefix: iframe.src.substring(0, 80),
                        error: e.message,
                    });
                }
            }
            return results;
        })()
    """)
    with open("proton_iframe_access.json", "w", encoding="utf-8") as f:
        json.dump(captcha_info, f, ensure_ascii=False, indent=2)
    logger.info("iframe access: %s", json.dumps(captcha_info, ensure_ascii=False, indent=2)[:2000])

# Keep browser open for inspection
import time as t
logger.info("Browser open for 30s for inspection...")
t.sleep(30)
browser.close()
logger.info("Done!")
