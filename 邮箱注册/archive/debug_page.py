"""Debug: check what's on the signup page"""
import sys, os, logging, time
sys.path.insert(0, os.path.dirname(__file__))
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

from cdp_browser import CDPBrowser, CDPLaunchConfig

config = CDPLaunchConfig(
    proxy="http://B_72756_JP___90_pphKvB9y:2442375@gate2.ipweb.cc:7778",
    extra_args=["--proxy-bypass-list=localhost,127.0.0.1,<-loopback>"],
)
browser = CDPBrowser(config).launch()

print("[DEBUG] Navigating to signup...")
browser.navigate("https://signup.live.com/signup", wait_for_load=True, timeout=30)

for i in range(15):
    time.sleep(2)
    url = browser.get_url()
    title = browser.get_title()
    body = browser.get_body_text()[:500]
    inputs = browser.evaluate("""(() => {
        const els = document.querySelectorAll('input');
        const vis = [];
        for (const el of els) {
            vis.push({type: el.type, name: el.name, id: el.id, visible: el.offsetParent !== null, w: el.offsetWidth, h: el.offsetHeight});
        }
        return vis;
    })()""")
    print(f"\n--- Tick {i} ({i*2}s) ---")
    print(f"URL: {url}")
    print(f"Title: {title}")
    print(f"Inputs: {inputs}")
    print(f"Body[:300]: {body[:300]}")
    if inputs and len(inputs) > 0:
        print("[OK] Inputs found!")
        break

browser.close()
