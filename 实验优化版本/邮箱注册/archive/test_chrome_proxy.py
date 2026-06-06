"""
快速测试 Chrome + 代理 是否能用
直接在终端运行: python test_chrome_proxy.py
"""
import sys, os, json, time, subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp_browser import CDPBrowser, CDPLaunchConfig
from proxy_utils import parse_proxy

PROXY = "gate2.ipweb.cc:7778:B_72756_JP___90_pphKvB9y:2442375"

def main():
    p = parse_proxy(PROXY)
    if not p:
        print(f"Invalid proxy: {PROXY}")
        sys.exit(1)

    # Step 1: curl verify
    print("=" * 50)
    print("Step 1: Verifying proxy with curl.exe...")
    print(f"  Format: {p.url}")
    r = subprocess.run(
        ["curl.exe", "-s", "-x", p.curl_arg, "http://ipinfo.io", "--connect-timeout", "15", "-m", "20"],
        capture_output=True, text=True, timeout=30
    )
    if r.returncode == 0 and "ip" in r.stdout.lower():
        data = json.loads(r.stdout)
        print(f"  OK! IP={data['ip']} Country={data['country']}")
    else:
        print(f"  FAILED: {r.stderr or r.stdout}")
        sys.exit(1)

    # Step 2: Chrome with proxy
    print("\nStep 2: Launching Chrome with proxy...")
    proxy_url = p.chrome_proxy
    print(f"  Chrome proxy: {proxy_url}")

    config = CDPLaunchConfig(
        headless=False,
        proxy=proxy_url,
        extra_args=["--proxy-bypass-list=localhost,127.0.0.1,<-loopback>"],
    )

    browser = CDPBrowser(config).launch()
    print("  Chrome launched!")

    # Step 3: Proxy auth is handled automatically by CDPBrowser._setup_proxy_auth
    print("\nStep 3: Proxy auth handled by CDPBrowser automatically")

    # Step 4: Navigate to test page
    print("\nStep 4: Navigating to http://ipinfo.io ...")
    browser.navigate("http://ipinfo.io", wait_for_load=True, timeout=30)
    time.sleep(3)

    body = browser.get_body_text()
    url = browser.get_url()
    print(f"  URL: {url}")
    print(f"  Body: {body[:300]}")

    if "ip" in body.lower() and ("org" in body.lower() or "country" in body.lower()):
        print("\n" + "=" * 50)
        print("SUCCESS! Chrome + Proxy works!")
        print("=" * 50)
    else:
        print("\n" + "=" * 50)
        print("FAILED - check screenshot")
        print("=" * 50)
        browser.screenshot("proxy_chrome_test.png")
        print("Screenshot saved to proxy_chrome_test.png")

    input("\nPress Enter to close browser...")
    browser.close()

if __name__ == "__main__":
    main()
