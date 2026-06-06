#!/usr/bin/env python3
"""Proton CAPTCHA 截图 - 用 CDP 直接截全页"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp_base import launch_browser, save_result, RegistrationResult, generate_account
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

browser = launch_browser(headless=False)
browser.navigate("https://account.proton.me/signup?plan=free", timeout=30)
time.sleep(15)

account = generate_account("proton", "proton.me")
pwd = "Pr0ton!@" + account.password[:8]

browser.set_input_value("#username", account.username)
time.sleep(1)
browser.set_input_value("#password", pwd)
time.sleep(1)
browser.set_input_value("#password-confirm", pwd)
time.sleep(3)

submit_info = browser.evaluate("""
    (() => {
        const btn = document.querySelector('button[type="submit"]');
        if (btn && !btn.disabled) {
            const r = btn.getBoundingClientRect();
            return {x: r.x + r.width/2, y: r.y + r.height/2};
        }
        return null;
    })()
""")
if submit_info:
    browser.click_at(submit_info['x'], submit_info['y'])
    time.sleep(8)

# Dismiss upsell
dismiss = browser.evaluate("""
    (() => {
        const btns = document.querySelectorAll('button, a, [role="button"]');
        for (const b of btns) {
            const text = (b.textContent || '').toLowerCase().trim();
            const r = b.getBoundingClientRect();
            if (r.width > 0 && r.height > 0 && r.height < 80) {
                if (text.includes('no thanks') || text.includes('skip') || text.includes('谢谢') || 
                    text.includes('不用') || text.includes('later') || text.includes('decline') ||
                    text.includes('free') || text.includes('continue')) {
                    b.click();
                    return text;
                }
            }
        }
        return null;
    })()
""")
if dismiss:
    logger.info("Dismissed upsell: '%s'", dismiss)
    time.sleep(5)

# Screenshot the whole page via CDP protocol directly
time.sleep(3)

# CDP full page screenshot using Chrome DevTools
def cdp_full_screenshot(b, fname):
    """Full page screenshot via CDP protocol"""
    # Get scroll dimensions
    scroll_h = b.evaluate("document.documentElement.scrollHeight") or 1000
    window_h = b.evaluate("window.innerHeight") or 1000
    
    logger.info(f"Scroll height: {scroll_h}, Window height: {window_h}")
    
    screenshots = []
    scroll_y = 0
    while scroll_y < scroll_h:
        b.evaluate(f"window.scrollTo(0, {scroll_y})")
        time.sleep(0.5)
        
        try:
            result = b._send_cmd("Page.captureScreenshot", {"format": "png"})
            import base64
            img_data = base64.b64decode(result['data'])
            screenshots.append((scroll_y, img_data))
        except Exception as e:
            logger.warning(f"Screenshot at {scroll_y}: {e}")
        scroll_y += int(window_h)
    
    # Stitch screenshots
    import base64 as b64
    from PIL import Image
    import io
    
    if screenshots:
        # Get first image dimensions
        first_img = Image.open(io.BytesIO(screenshots[0][1]))
        total_height = sum(screenshots[i][1] and Image.open(io.BytesIO(screenshots[i][1])).height for i in range(len(screenshots)))
        
        # Actually sum heights
        imgs = []
        for _, data in screenshots:
            imgs.append(Image.open(io.BytesIO(data)))
        
        total_w = imgs[0].width
        total_h = sum(img.height for img in imgs)
        stitched = Image.new('RGB', (total_w, total_h))
        
        y_offset = 0
        for img in imgs:
            stitched.paste(img, (0, y_offset))
            y_offset += img.height
        
        out_path = f"{fname}_captcha_full.png"
        stitched.save(out_path, "PNG")
        logger.info(f"Saved full page screenshot: {out_path} ({total_w}x{total_h})")
        return out_path
    return None

out_path = cdp_full_screenshot(browser, "proton_captcha_analysis")
logger.info(f"Full screenshot: {out_path}")

# Get CAPTCHA element details
captcha_info = browser.evaluate("""
    (() => {
        const allInputs = document.querySelectorAll('input, iframe, img, canvas, video');
        const results = Array.from(allInputs).filter(e => e.getBoundingClientRect().width > 0).map(e => ({
            tag: e.tagName, id: e.id || '', src: e.src || '',
            width: e.getBoundingClientRect().width, height: e.getBoundingClientRect().height,
            class: (e.className || '').substring(0, 60),
        }));
        
        const iframes = Array.from(document.querySelectorAll('iframe')).map(f => ({
            src: f.src, width: f.getBoundingClientRect().width, height: f.getBoundingClientRect().height,
        }));
        
        const bodyText = (document.body ? document.body.innerText : '').substring(0, 500);
        
        return {
            elements: results,
            iframes: iframes,
            bodyText: bodyText,
            html: document.documentElement.innerHTML.substring(0, 3000),
        };
    })()
""")

with open("proton_captcha_detail.json", "w", encoding="utf-8") as f:
    json.dump(captcha_info, f, ensure_ascii=False, indent=2)
logger.info("Saved captcha detail to proton_captcha_detail.json")

# Also save screenshot with smaller crop of just the captcha area
# Get the captcha container
captcha_area = browser.evaluate("""
    (() => {
        // Try to find the challenge box
        const allDivs = document.querySelectorAll('div, form, section');
        for (const d of allDivs) {
            const r = d.getBoundingClientRect();
            if (r.width > 200 && r.width < 600 && r.height > 100 && r.height < 400) {
                // Check if text content contains captcha-related words
                const text = (d.textContent || '').toLowerCase();
                if (text.includes('human') || text.includes('captcha') || text.includes('robot') || 
                    text.includes('verify') || text.includes('check')) {
                    return {
                        tag: d.tagName, x: Math.round(r.x), y: Math.round(r.y),
                        width: Math.round(r.width), height: Math.round(r.height),
                        text: text.substring(0, 200),
                    };
                }
            }
        }
        return null;
    })()
""")
logger.info(f"Captcha area: {json.dumps(captcha_area)}")

# Keep browser open for user to see
import time as t
t.sleep(15)
browser.close()
logger.info("Done!")
