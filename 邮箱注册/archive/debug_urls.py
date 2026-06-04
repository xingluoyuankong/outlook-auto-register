import sys, io, time, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(__file__))

from cdp_browser import CDPBrowser, CDPLaunchConfig

config = CDPLaunchConfig(headless=True)
browser = CDPBrowser(config).launch()

# Try different signup URLs to find the one that offers "create new email"
urls = [
    "https://signup.live.com/signup?lic=1",
    "https://signup.live.com/signup?uaid=1&lic=1",
    "https://outlook.live.com/owa/?nlp=1&signup=1",
    "https://signup.live.com/signup",
]

for i, url in enumerate(urls):
    print(f"\n{'='*60}")
    print(f"[URL {i+1}] {url}")
    browser.navigate(url, wait_for_load=True, timeout=20)
    time.sleep(2)
    
    body = browser.get_body_text()
    # Check for consent page
    if "同意并继续" in body:
        browser.evaluate("""(() => {
            const btns = document.querySelectorAll('button');
            for (const b of btns) {
                if ((b.textContent||'').includes('同意')) { b.click(); return true; }
            }
            return false;
        })()""")
        time.sleep(2)
        body = browser.get_body_text()
    
    print(f"Body: {body[:300]}")
    
    # Check for key elements
    result = browser.evaluate("""
        (() => {
            const body = document.body.innerText.toLowerCase();
            const has_new_email = body.includes('new email') || body.includes('get a new') || body.includes('获取新') || body.includes('创建新');
            const has_live_switch = !!document.getElementById('liveSwitch');
            const has_domain = !!document.getElementById('domainDropdownId');
            const inputs = document.querySelectorAll('input');
            const input_info = [];
            for (const el of inputs) {
                const rect = el.getBoundingClientRect();
                if (rect.width > 0) input_info.push({type: el.type, name: el.name, id: el.id});
            }
            return JSON.stringify({has_new_email, has_live_switch, has_domain, inputs: input_info});
        })()
    """)
    print(f"Analysis: {result}")

print("\n" + "="*60)
print("[DONE]")
browser.close()
