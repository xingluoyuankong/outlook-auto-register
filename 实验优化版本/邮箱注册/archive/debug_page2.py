"""Debug: check page content"""
import sys, os, logging, time
sys.path.insert(0, os.path.dirname(__file__))
logging.basicConfig(level=logging.WARNING)

from cdp_browser import CDPBrowser, CDPLaunchConfig

config = CDPLaunchConfig(
    proxy="http://B_72756_JP___90_pphKvB9y:2442375@gate2.ipweb.cc:7778",
    extra_args=["--proxy-bypass-list=localhost,127.0.0.1,<-loopback>"],
)
browser = CDPBrowser(config).launch()

print("[1] Navigating...")
browser.navigate("https://signup.live.com/signup", wait_for_load=True, timeout=30)
time.sleep(3)

print(f"[2] URL: {browser.get_url()}")
print(f"[3] Title: {browser.get_title()}")

html = browser.evaluate("document.documentElement.outerHTML")
if html:
    print(f"[4] HTML length: {len(html)}")
    # Look for key markers
    for marker in ["outlook", "signup", "create", "email", "password", "MemberName", "Username", 
                   "blocked", "error", "captcha", "consent", "agree", "privacy", "signIn"]:
        if marker.lower() in html.lower():
            print(f"  Found: '{marker}'")
    # Check all inputs
    all_inputs = browser.evaluate("""(() => {
        const els = document.querySelectorAll('input, select, button, textarea');
        return Array.from(els).map(e => ({
            tag: e.tagName, type: e.type, name: e.name, id: e.id,
            placeholder: e.placeholder, visible: e.offsetParent !== null,
            w: e.offsetWidth, h: e.offsetHeight
        }));
    })()""")
    print(f"[5] All form elements: {len(all_inputs) if all_inputs else 0}")
    if all_inputs:
        for el in all_inputs[:20]:
            print(f"  {el}")
else:
    print("[4] No HTML returned")

browser.close()
