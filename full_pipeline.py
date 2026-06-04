#!/usr/bin/env python3
"""
Full Pipeline: Register Outlook Account → Get Refresh Token → Save 4 Credentials
1. Register via 邮箱注册 (Selenium + proxy)
2. Verify account exists (ROPC)
3. Get RT via Auth Code Flow + PKCE + CDP automation
4. Save: email----password----client_id----refresh_token
"""

import sys, json, time, subprocess, os, urllib.request, urllib.parse, urllib.error
import base64, hashlib, secrets, socket, threading, http.server, logging

sys.path.insert(0, "/home/boxd/邮箱注册")

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger("full_pipeline")

# ── Config ──
CLIENT_ID = "14d82eec-204b-4c2f-b7e8-296a70dab67e"
TENANT = "consumers"
CREDENTIAL_DIR = "/home/boxd/邮箱注册/browser_extension/邮箱凭证"
PROXY_FILE = "/home/boxd/proxyhub/data/邮箱注册_proxies.txt"
DEFAULT_SCOPES = [
    "offline_access", "openid", "profile",
    "https://graph.microsoft.com/User.Read",
    "https://graph.microsoft.com/Mail.Read",
]


class OAuthError(RuntimeError):
    pass


# ── OAuth2 (from oauth_core.py) ──
def b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

def make_pkce_pair():
    verifier = b64url(secrets.token_bytes(64))
    challenge = b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge

def post_form(url, form_data, timeout=30):
    try:
        import requests
        resp = requests.post(url, data=form_data, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except ImportError:
        data = urllib.parse.urlencode(form_data).encode("utf-8")
        req = urllib.request.Request(url, data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(body)
            except:
                payload = {"error": "http_error", "error_description": body}
            raise OAuthError(json.dumps(payload, ensure_ascii=False)) from e

def exchange_authorization_code(code, code_verifier, redirect_uri, client_id=CLIENT_ID):
    return post_form(
        f"https://login.microsoftonline.com/{TENANT}/oauth2/v2.0/token",
        {
            "client_id": client_id, "grant_type": "authorization_code",
            "code": code, "redirect_uri": redirect_uri,
            "scope": " ".join(DEFAULT_SCOPES), "code_verifier": code_verifier,
        },
    )


# ── HTTP Callback Server ──
class CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        self.server.oauth_code = params.get("code", [None])[0]
        self.server.oauth_error = params.get("error", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        msg = "Authorization successful!" if self.server.oauth_code else "Authorization failed."
        self.wfile.write(f"<html><body><h1>{msg}</h1></body></html>".encode())
    def log_message(self, format, *args):
        pass

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

def start_callback_server(port):
    server = http.server.HTTPServer(("127.0.0.1", port), CallbackHandler)
    server.oauth_code = None
    server.oauth_error = None
    def serve_forever():
        while server.oauth_code is None and server.oauth_error is None:
            server.handle_request()
    thread = threading.Thread(target=serve_forever, daemon=True)
    thread.start()
    return server


# ── CDP Browser Automation ──
def kill_chrome():
    subprocess.run(["pkill", "-9", "-f", "undetected"], capture_output=True)
    subprocess.run(["pkill", "-9", "-f", "chromedriver"], capture_output=True)
    subprocess.run(["pkill", "-9", "-f", "google-chrome"], capture_output=True)
    subprocess.run(["pkill", "-9", "-f", "Xvfb"], capture_output=True)
    time.sleep(2)
    subprocess.run(["bash", "-c", "kill -9 $(pgrep -f chrome) 2>/dev/null; kill -9 $(pgrep -f Xvfb) 2>/dev/null; true"], capture_output=True)
    time.sleep(1)

def start_chrome():
    kill_chrome()
    cdp_port = find_free_port()
    xvfb = subprocess.Popen(["Xvfb", ":99", "-screen", "0", "1280x720x24"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    env = os.environ.copy()
    env["DISPLAY"] = ":99"
    chrome = subprocess.Popen([
        "/usr/bin/google-chrome",
        "--remote-debugging-port=%d" % cdp_port,
        "--user-data-dir=/home/boxd/.chrome-rt-pipeline",
        "--no-sandbox", "--disable-dev-shm-usage",
        "--no-first-run", "--no-default-browser-check",
        "--disable-default-apps", "--disable-popup-blocking",
        "--window-size=1280,900",
        "--disable-blink-features=AutomationControlled",
        "--remote-allow-origins=*",
        "about:blank"
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
    time.sleep(5)
    if chrome.poll() is not None:
        xvfb.terminate()
        raise RuntimeError(f"Chrome exited {chrome.returncode}")
    return chrome, xvfb, cdp_port

def get_page_ws(cdp_port):
    resp = urllib.request.urlopen(f"http://127.0.0.1:{cdp_port}/json", timeout=5)
    tabs = json.loads(resp.read())
    page = next((t for t in tabs if t.get("type") == "page"), None)
    if not page:
        ver = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{cdp_port}/json/version", timeout=5).read())
        import websocket
        bws = websocket.create_connection(ver["webSocketDebuggerUrl"], timeout=10)
        bws.send(json.dumps({"id": 1, "method": "Target.createTarget", "params": {"url": "about:blank"}}))
        bws.recv()
        bws.close()
        time.sleep(2)
        resp = urllib.request.urlopen(f"http://127.0.0.1:{cdp_port}/json", timeout=5)
        tabs = json.loads(resp.read())
        page = next((t for t in tabs if t.get("type") == "page"), None)
    return page["webSocketDebuggerUrl"] if page else None

def cdp_eval(ws_url, expr):
    import websocket
    ws = websocket.create_connection(ws_url, timeout=10)
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                         "params": {"expression": expr, "returnByValue": True}}))
    ws.settimeout(10)
    result = json.loads(ws.recv())
    ws.close()
    return result.get("result", {}).get("result", {}).get("value", "")

def type_text(ws_url, text):
    import websocket
    for ch in text:
        ws = websocket.create_connection(ws_url, timeout=5)
        ws.send(json.dumps({"id": 1, "method": "Input.dispatchKeyEvent",
                             "params": {"type": "keyDown", "text": ch, "key": ch}}))
        ws.settimeout(2); ws.recv(); ws.close()
        ws = websocket.create_connection(ws_url, timeout=5)
        ws.send(json.dumps({"id": 1, "method": "Input.dispatchKeyEvent",
                             "params": {"type": "keyUp", "key": ch}}))
        ws.settimeout(2); ws.recv(); ws.close()
        time.sleep(0.03)

def click_element(ws_url, selector):
    coords = cdp_eval(ws_url, """(function(){
        var el = document.querySelector('%s');
        if(!el || el.offsetHeight===0) return "NO";
        var r = el.getBoundingClientRect();
        return JSON.stringify({x:Math.round(r.x+r.width/2), y:Math.round(r.y+r.height/2)});
    })()""" % selector.replace("'", "\\'"))
    if coords == "NO":
        return False
    pos = json.loads(coords)
    import websocket
    ws = websocket.create_connection(ws_url, timeout=10)
    ws.send(json.dumps({"id": 1, "method": "Input.dispatchMouseEvent",
                         "params": {"type": "mousePressed", "x": pos["x"], "y": pos["y"],
                                    "button": "left", "clickCount": 1}}))
    ws.settimeout(5); ws.recv(); ws.close()
    time.sleep(0.05)
    ws = websocket.create_connection(ws_url, timeout=10)
    ws.send(json.dumps({"id": 1, "method": "Input.dispatchMouseEvent",
                         "params": {"type": "mouseReleased", "x": pos["x"], "y": pos["y"],
                                    "button": "left", "clickCount": 1}}))
    ws.settimeout(5); ws.recv(); ws.close()
    return True

def click_submit(ws_url):
    for sel in ['#idSIButton9', 'input[type="submit"]', 'button[type="submit"]',
                '#idBtn_Back', 'input[value="Next"]', 'input[value="Sign in"]']:
        if click_element(ws_url, sel):
            return True
    return False

def find_input(ws_url, selectors):
    for sel in selectors:
        test = cdp_eval(ws_url, "(function(){var e=document.querySelector('%s');return e&&e.offsetHeight>0?'found':'no';})()" % sel.replace("'", "\\'"))
        if test == "found":
            return sel
    return None


# ── Step 1: Register Account ──
def register_account(proxy):
    """Register a new Outlook account using CDP (cdp_outlook.register_outlook_account).

    Returns:
        (email, password, error, auto_country) — auto_country is the country
        the signup page auto-selected based on the proxy IP.
    """
    log.info(f"Registering with proxy: {proxy}")
    try:
        from 邮箱注册.cdp_outlook import register_outlook_account, OutlookAccount

        result = register_outlook_account(proxy=proxy, headless=False)

        if not result or not result.email:
            return None, None, (result.error if result else "no result"), ""

        if result.error and not result.success:
            return None, None, result.error, ""

        log.info(f"Registered: {result.email}")
        browser_country = getattr(result, "auto_country", "") or ""
        return result.email, result.password, None, browser_country

    except Exception as e:
        log.exception("Registration error")
        return None, None, str(e), ""


# ── Step 2: Verify Account ──
def verify_account(email, password):
    """Verify account exists using ROPC."""
    try:
        data = urllib.parse.urlencode({
            "client_id": CLIENT_ID,
            "scope": "offline_access https://graph.microsoft.com/User.Read",
            "grant_type": "password",
            "username": email,
            "password": password,
        }).encode()
        req = urllib.request.Request(
            "https://login.microsoftonline.com/consumers/oauth2/v2.0/token",
            data=data, headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            tokens = json.loads(resp.read())
            if tokens.get("access_token"):
                return True, "ropc_ok"
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        if "invalid_grant" in err or "AADSTS70000" in err:
            return True, "exists_no_ropc"
        if "invalid_user" in err or "AADSTS50034" in err:
            return False, "not_found"
        return True, "unknown_error"
    except:
        return True, "network_error"
    return False, "no_response"


# ── Step 3: Get RT via Auth Code Flow + PKCE + CDP ──
def get_rt_auth_code(email, password):
    """Get RT using Auth Code Flow + PKCE + CDP automation."""
    code_verifier, code_challenge = make_pkce_pair()
    callback_port = find_free_port()
    redirect_uri = f"http://localhost:{callback_port}"
    server = start_callback_server(callback_port)
    log.info(f"Callback server on port {callback_port}")

    state = os.urandom(18).hex()
    authorize_url = (
        f"https://login.microsoftonline.com/{TENANT}/oauth2/v2.0/authorize?"
        + urllib.parse.urlencode({
            "client_id": CLIENT_ID, "response_type": "code",
            "redirect_uri": redirect_uri, "scope": " ".join(DEFAULT_SCOPES),
            "code_challenge": code_challenge, "code_challenge_method": "S256",
            "response_mode": "query", "state": state,
            "prompt": "login", "login_hint": email,
        })
    )

    chrome, xvfb, cdp_port = start_chrome()
    try:
        ws_url = get_page_ws(cdp_port)
        if not ws_url:
            log.error("No page target")
            return None

        # Navigate to authorize URL
        import websocket
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({"id": 1, "method": "Page.navigate", "params": {"url": authorize_url}}))
        ws.settimeout(10); ws.recv(); ws.close()
        time.sleep(8)

        body = cdp_eval(ws_url, "document.body ? document.body.innerText.substring(0,500) : ''")
        log.info(f"Page: {body[:80]}")

        # Check if already on password page (login_hint pre-filled email)
        pwd_sel = find_input(ws_url, ["#i0118", "input[name='passwd']", "input[type='password']"])
        email_sel = find_input(ws_url, ["#i0116", "input[name='loginfmt']", "input[autocomplete='username']"])

        # If on email page, enter email
        if email_sel and not pwd_sel:
            cdp_eval(ws_url, f"document.querySelector('{email_sel}').focus()")
            time.sleep(0.3)
            type_text(ws_url, email)
            time.sleep(0.5)
            click_submit(ws_url)
            time.sleep(8)
            body = cdp_eval(ws_url, "document.body ? document.body.innerText.substring(0,500) : ''")
            log.info(f"After email: {body[:60]}")
            pwd_sel = find_input(ws_url, ["#i0118", "input[name='passwd']", "input[type='password']"])

        if not pwd_sel:
            log.error("No password field found")
            return None

        # Enter password
        cdp_eval(ws_url, f"document.querySelector('{pwd_sel}').focus()")
        time.sleep(0.3)
        type_text(ws_url, password)
        time.sleep(0.5)
        pwd_val = cdp_eval(ws_url, "document.querySelector('" + pwd_sel + "').value")
        log.info(f"Password: {len(pwd_val)} chars")

        click_submit(ws_url)
        time.sleep(10)

        body = cdp_eval(ws_url, "document.body ? document.body.innerText.substring(0,500) : ''")
        log.info(f"After pwd: {body[:60]}")

        # Handle "Stay signed in?"
        if "stay signed" in body.lower() or "保持登录" in body:
            click_submit(ws_url)
            time.sleep(5)

        # Handle "Protect your account"
        body = cdp_eval(ws_url, "document.body ? document.body.innerText.substring(0,500) : ''")
        if "protect" in body.lower() or "保护" in body:
            cdp_eval(ws_url, """(function(){
                var links = document.querySelectorAll('a, button');
                for(var i=0;i<links.length;i++){
                    var t = links[i].textContent.toLowerCase();
                    if(t.indexOf('skip')>=0 || t.indexOf('跳过')>=0){links[i].click();return 'skipped';}
                }
                return 'none';
            })()""")
            time.sleep(6)

        # Handle consent
        body = cdp_eval(ws_url, "document.body ? document.body.innerText.substring(0,500) : ''")
        if "accept" in body.lower() or "consent" in body.lower():
            click_submit(ws_url)
            time.sleep(5)

        # Wait for callback
        log.info("Waiting for auth code...")
        start = time.time()
        while time.time() - start < 60:
            if server.oauth_code:
                break
            if server.oauth_error:
                log.error(f"OAuth error: {server.oauth_error}")
                return None
            time.sleep(1)

        code = server.oauth_code
        if not code:
            final_url = cdp_eval(ws_url, "window.location.href")
            if "code=" in final_url:
                parsed = urllib.parse.urlparse(final_url)
                params = urllib.parse.parse_qs(parsed.query)
                code = params.get("code", [None])[0]

        if not code:
            log.error("No auth code received")
            return None

        log.info(f"Auth code: {code[:20]}...")

    finally:
        try:
            chrome.terminate()
            xvfb.terminate()
        except:
            pass

    # Exchange code for tokens
    log.info("Exchanging code for tokens...")
    try:
        tokens = exchange_authorization_code(code, code_verifier, redirect_uri)
    except Exception as e:
        log.error(f"Token exchange error: {e}")
        # Try with requests for better error info
        try:
            import requests
            resp = requests.post(
                f"https://login.microsoftonline.com/{TENANT}/oauth2/v2.0/token",
                data={
                    "client_id": CLIENT_ID, "grant_type": "authorization_code",
                    "code": code, "redirect_uri": redirect_uri,
                    "scope": " ".join(DEFAULT_SCOPES), "code_verifier": code_verifier,
                }, timeout=30)
            log.info(f"Token response: {resp.status_code} {resp.text[:200]}")
            if resp.status_code == 200:
                tokens = resp.json()
            else:
                return None
        except Exception as e2:
            log.error(f"Direct request failed: {e2}")
            return None

    rt = tokens.get("refresh_token", "")
    if not rt:
        log.error("No refresh_token in response")
        return None

    log.info(f"RT obtained: {len(rt)} chars")
    return rt


# ── Step 4: Save Credentials ──
def save_credentials(email, password, client_id, refresh_token):
    os.makedirs(CREDENTIAL_DIR, exist_ok=True)
    path = os.path.join(CREDENTIAL_DIR, f"{email}__RT_ACQUIRED.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"{email}----{password}----{client_id}----{refresh_token}")
    log.info(f"Saved: {path}")
    return path


# ── Proxy Dual Verification ──
def _curl_check_proxy(proxy_url):
    """第一层验证：curl 通过代理请求 ipinfo.io 获取出口 IP 和国家"""
    socks = proxy_url.replace("socks5://", "socks5h://")
    try:
        r = subprocess.run(
            ["curl", "-s", "--max-time", "15", "--proxy", socks, "https://ipinfo.io/json"],
            capture_output=True, text=True, timeout=20
        )
        if r.returncode == 0:
            info = json.loads(r.stdout)
            return {
                "ip": info.get("ip", "?"),
                "country": info.get("country", "?"),
                "city": info.get("city", "?"),
                "org": info.get("org", "?"),
            }
    except Exception as e:
        log.warning("curl proxy check failed: %s", e)
    return None



def verify_proxy_dual(proxy_url, browser_country=""):
    """
    代理双重验证：
    第一层: curl 通过代理请求 ipinfo.io → 出口 IP/国家
    第二层: 注册流程中网站根据代理IP自动选择的国家（由注册流程顺便读取）
    两层一致 = 代理真正生效
    """
    log.info("[PROXY VERIFY] " + "="*40)
    log.info("[PROXY VERIFY] 开始双重验证: %s", proxy_url)

    # 第一层
    curl_info = _curl_check_proxy(proxy_url)
    if not curl_info:
        log.error("[PROXY VERIFY] ❌ 第一层失败: curl 无法通过代理连接")
        return False, None
    log.info("[PROXY VERIFY] 第一层 OK — IP: %s, 国家: %s, 城市: %s",
             curl_info["ip"], curl_info["country"], curl_info["city"])

    # 第二层：由注册流程中顺便读取，通过参数传入
    if not browser_country:
        log.warning("[PROXY VERIFY] ⚠️ 第二层未获得国家信息（注册流程未走到 profile/birthdate 步骤）")
        log.info("[PROXY VERIFY] 仅 curl 验证通过 (IP: %s)", curl_info["ip"])
        return True, curl_info

    curl_country = curl_info.get("country", "")
    log.info("[PROXY VERIFY] curl 国家: %s | 浏览器国家: %s", curl_country, browser_country)

    # 对比：ipinfo 返回 ISO 代码（如 US, EE），浏览器返回全名（如 United States）
    match = (curl_country.lower() in browser_country.lower() or
             browser_country.lower() in curl_country.lower())
    if match:
        log.info("[PROXY VERIFY] ✅ 双重验证通过 — 代理生效")
    else:
        log.warning("[PROXY VERIFY] ⚠️ 国家不匹配 — curl=%s, browser=%s", curl_country, browser_country)
        log.warning("[PROXY VERIFY] 代理可能未在浏览器层生效")
    return match, curl_info


# ── Main Pipeline ──
def full_pipeline(proxy=None):
    """Complete pipeline: proxy verify → register → verify → get RT → save."""
    
    # Get proxy
    if not proxy:
        try:
            with open(PROXY_FILE) as f:
                proxies = [l.strip() for l in f if l.strip().startswith("socks5://")]
            import random
            random.shuffle(proxies)
            proxy = proxies[0] if proxies else None
        except:
            pass
    
    if not proxy:
        log.error("No proxy available")
        return None

    # Step 0: Proxy curl pre-check (第一层验证)
    log.info("="*50)
    log.info("STEP 0: Proxy pre-check...")
    curl_info = _curl_check_proxy(proxy)
    if not curl_info:
        log.error("Proxy curl check FAILED — aborting")
        return None
    log.info("Proxy curl OK: IP=%s, Country=%s", curl_info.get("ip", "?"), curl_info.get("country", "?"))

    # Step 1: Register
    log.info("="*50)
    log.info("STEP 1: Registering account...")
    email, password, error, browser_country = register_account(proxy)
    if error:
        log.error(f"Registration failed: {error}")
        return None
    
    log.info(f"Registered: {email}")

    # Step 1.5: Proxy dual verification (第二层 — 从注册流程中读取的国家)
    if browser_country:
        verified, curl_info = verify_proxy_dual(proxy, browser_country)
        if not verified:
            log.warning("⚠️ 代理双重验证不匹配，但继续流程")
    else:
        log.warning("⚠️ 注册流程未读取到国家，仅凭 curl 验证")

    # Step 2: Verify
    log.info("STEP 2: Verifying account...")
    valid, method = verify_account(email, password)
    if not valid:
        log.error(f"Account not valid: {method}")
        return None
    log.info(f"Verified: {method}")

    # Step 3: Get RT
    log.info("STEP 3: Getting refresh token...")
    rt = get_rt_auth_code(email, password)
    if not rt:
        log.error("RT acquisition failed")
        # Save without RT
        save_credentials(email, password, CLIENT_ID, "")
        return {"email": email, "password": password, "has_rt": False}

    # Step 4: Save
    log.info("STEP 4: Saving credentials...")
    path = save_credentials(email, password, CLIENT_ID, rt)

    log.info("="*50)
    log.info(f"✅ COMPLETE: {email}")
    log.info(f"  Password: {password}")
    log.info(f"  Client ID: {CLIENT_ID}")
    log.info(f"  RT: {rt[:20]}...{rt[-10:]} ({len(rt)} chars)")
    log.info(f"  Saved: {path}")
    log.info("="*50)

    return {
        "email": email, "password": password,
        "client_id": CLIENT_ID, "refresh_token": rt,
        "has_rt": True, "path": path
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("proxy", nargs="?", help="socks5://host:port")
    parser.add_argument("--verify-only", action="store_true", help="仅验证代理，不执行注册")
    args = parser.parse_args()

    if args.verify_only:
        proxy = args.proxy
        if not proxy:
            try:
                with open(PROXY_FILE) as f:
                    proxies = [l.strip() for l in f if l.strip().startswith("socks5://")]
                import random
                proxy = random.choice(proxies) if proxies else None
            except: pass
        if not proxy:
            print("No proxy available"); sys.exit(1)
        ok, curl_info, browser_info = verify_proxy_dual(proxy)
        print(json.dumps({"verified": ok, "curl": curl_info, "browser": browser_info}, indent=2, ensure_ascii=False))
        sys.exit(0 if ok else 1)

    result = full_pipeline(args.proxy)
    if result:
        print(json.dumps(result, indent=2))
    else:
        print("Pipeline failed")
        sys.exit(1)

