"""Test proxy with Chrome - proper auth via Fetch domain"""
import sys, os, json, time, threading
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cdp_browser import CDPBrowser, CDPLaunchConfig

proxy_raw = "gate2.ipweb.cc:7778:B_72756_JP___90_pphKvB9y:2442375"
parts = proxy_raw.split(":")
proxy_host, proxy_port, proxy_user, proxy_pass = parts[0], parts[1], parts[2], parts[3]

# Chrome proxy format: socks5://host:port (no credentials)
proxy_url = f"socks5://{proxy_host}:{proxy_port}"
print(f"Chrome proxy: {proxy_url}")
print(f"Auth: {proxy_user}:{proxy_pass}")

config = CDPLaunchConfig(
    headless=False,
    proxy=proxy_url,
)

browser = CDPBrowser(config).launch()
print("Chrome launched, waiting 3s...")
time.sleep(3)

# Register Fetch.authRequired handler BEFORE enabling Fetch
def handle_auth_required(msg):
    """Handle proxy authentication challenge"""
    params = msg.get("params", {})
    request_id = params.get("requestId", "")
    auth = params.get("authChallenge", {})
    print(f"  [AUTH] Proxy auth challenge: {auth.get('origin', 'unknown')}")
    
    # Respond with credentials
    resp = {
        "id": 99999,
        "method": "Fetch.continueWithAuth",
        "params": {
            "requestId": request_id,
            "authChallengeResponse": {
                "response": "ProvideCredentials",
                "username": proxy_user,
                "password": proxy_pass,
            }
        }
    }
    try:
        browser._ws.send(json.dumps(resp))
        print(f"  [AUTH] Credentials sent")
    except Exception as e:
        print(f"  [AUTH] Error sending credentials: {e}")

def handle_request_paused(msg):
    """Continue paused requests"""
    params = msg.get("params", {})
    request_id = params.get("requestId", "")
    try:
        browser._ws.send(json.dumps({
            "id": 99998,
            "method": "Fetch.continueRequest",
            "params": {"requestId": request_id}
        }))
    except:
        pass

# Register handlers
browser._event_handlers["Fetch.authRequired"] = [handle_auth_required]
browser._event_handlers["Fetch.requestPaused"] = [handle_request_paused]
print("Event handlers registered")

# Enable Fetch for auth interception
print("Enabling Fetch...")
try:
    result = browser._send_cmd("Fetch.enable", {
        "patterns": [
            {"urlPattern": "*", "requestStage": "AuthRequired"}
        ]
    }, timeout=10)
    print(f"Fetch enabled: {result}")
except TimeoutError:
    print("Fetch.enable timed out, trying without it...")
    # Maybe we don't need Fetch at all if Chrome handles SOCKS5 auth natively

# Navigate
print("\nNavigating to http://ipinfo.io ...")
try:
    browser.navigate("http://ipinfo.io", wait_for_load=True, timeout=30)
    time.sleep(3)
    body = browser.get_body_text()
    url = browser.get_url()
    print(f"URL: {url}")
    print(f"Body: {body[:600]}")
    
    if "ip" in body.lower() and "org" in body.lower():
        print("\n=== PROXY WORKS! ===")
    elif "err" in body.lower() or "error" in body.lower() or "chrome-error" in url:
        print("\n=== PROXY FAILED ===")
    else:
        print(f"\n=== UNKNOWN RESULT ===")
except TimeoutError:
    print("Navigation timed out")
    browser.screenshot("proxy_test.png")
    print("Screenshot saved")

input("\nPress Enter to close...")
browser.close()
