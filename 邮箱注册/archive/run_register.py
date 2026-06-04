"""
完整 Outlook 注册脚本 — 终端直接运行
用法: python run_register.py [--headless] [--proxy "host:port:user:pass"]
"""
import sys, os, json, time, random, logging, subprocess, secrets, string, base64

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cdp_browser import CDPBrowser, CDPLaunchConfig
from proxy_utils import parse_proxy, ProxyInfo

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("register")

# ── Proxy Config (IPWEB format: host:port:user:pass) ──
DEFAULT_PROXY = "gate2.ipweb.cc:7778:B_72756_JP___90_pphKvB9y:2442375"

def verify_proxy(proxy_str: str) -> bool:
    """Verify proxy works using curl.exe (subprocess)"""
    p = parse_proxy(proxy_str)
    if not p:
        logger.error("Invalid proxy format: %s", proxy_str)
        return False
    logger.info("Verifying proxy: %s@%s:%s", p.username, p.host, p.port)
    try:
        r = subprocess.run(
            ["curl.exe", "-s", "-x", p.curl_arg, "http://ipinfo.io", "--connect-timeout", "15", "-m", "20"],
            capture_output=True, text=True, timeout=30
        )
        if r.returncode == 0 and "ip" in r.stdout.lower():
            data = json.loads(r.stdout)
            logger.info("Proxy OK: IP=%s Country=%s Org=%s", data.get("ip"), data.get("country"), data.get("org"))
            return True
        else:
            logger.error("Proxy failed: %s", r.stderr or r.stdout)
            return False
    except Exception as e:
        logger.error("Proxy check error: %s", e)
        return False

def random_email():
    """Generate random Outlook email"""
    chars = string.ascii_lowercase + string.digits
    user = ''.join(secrets.choice(chars) for _ in range(random.randint(10, 15)))
    return f"{user}@outlook.com"

def random_password():
    """Generate strong password"""
    chars = string.ascii_letters + string.digits + "!@#$%"
    pwd = (
        secrets.choice(string.ascii_uppercase) +
        secrets.choice(string.ascii_lowercase) +
        secrets.choice(string.digits) +
        secrets.choice("!@#$%") +
        ''.join(secrets.choice(chars) for _ in range(10))
    )
    return pwd

def random_name():
    first_names = ["James","Mary","John","Patricia","Robert","Jennifer","Michael","Linda","David","Elizabeth",
                   "William","Barbara","Richard","Susan","Joseph","Jessica","Thomas","Sarah","Christopher","Karen",
                   "Daniel","Lisa","Matthew","Betty","Anthony","Margaret","Mark","Sandra","Donald","Ashley"]
    last_names = ["Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis","Rodriguez","Martinez",
                  "Hernandez","Lopez","Gonzalez","Wilson","Anderson","Thomas","Taylor","Moore","Jackson","Martin"]
    return random.choice(first_names), random.choice(last_names)

def random_birthdate():
    year = random.randint(1980, 2002)
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    return year, month, day


class OutlookRegistrar:
    """Full Outlook registration with proxy auth via CDP Fetch"""

    def __init__(self, proxy_str: str, headless: bool = False):
        self.proxy_info = parse_proxy(proxy_str)
        if not self.proxy_info:
            raise ValueError(f"Invalid proxy format: {proxy_str}")
        self.headless = headless
        self.browser = None
        self.auth_sent = False
        self.email = None
        self.password = None

    def _handle_auth_required(self, msg):
        """Handle proxy auth challenge from Fetch"""
        params = msg.get("params", {})
        request_id = params.get("requestId", "")
        auth = params.get("authChallenge", {})
        origin = auth.get("origin", "")
        logger.info("[AUTH] Proxy auth challenge from: %s", origin)
        resp = {
            "id": 99999,
            "method": "Fetch.continueWithAuth",
            "params": {
                "requestId": request_id,
                "authChallengeResponse": {
                    "response": "ProvideCredentials",
                    "username": self.proxy_info.username,
                    "password": self.proxy_info.password,
                }
            }
        }
        try:
            self.browser._ws.send(json.dumps(resp))
            self.auth_sent = True
            logger.info("[AUTH] Credentials sent")
        except Exception as e:
            logger.error("[AUTH] Failed to send credentials: %s", e)

    def _handle_fetch_paused(self, msg):
        """Continue paused requests"""
        params = msg.get("params", {})
        request_id = params.get("requestId", "")
        try:
            self.browser._ws.send(json.dumps({
                "id": 99998,
                "method": "Fetch.continueRequest",
                "params": {"requestId": request_id}
            }))
        except:
            pass

    def launch(self):
        """Launch Chrome with proxy and set up auth handling"""
        proxy_url = self.proxy_info.chrome_proxy
        logger.info("Launching Chrome with proxy: %s", proxy_url)

        config = CDPLaunchConfig(
            headless=self.headless,
            proxy=proxy_url,
            extra_args=["--proxy-bypass-list=localhost,127.0.0.1,<-loopback>"],
        )
        self.browser = CDPBrowser(config).launch()
        time.sleep(2)

        # Register Fetch event handlers for proxy auth
        self.browser._event_handlers["Fetch.authRequired"] = [self._handle_auth_required]
        self.browser._event_handlers["Fetch.requestPaused"] = [self._handle_fetch_paused]

        # Enable Fetch for auth interception
        try:
            self.browser._send_cmd("Fetch.enable", {
                "patterns": [
                    {"urlPattern": "*", "requestStage": "AuthRequired"}
                ]
            }, timeout=10)
            logger.info("[CDP] Fetch enabled for proxy auth")
        except TimeoutError:
            logger.warning("[CDP] Fetch.enable timed out, trying without explicit Fetch...")
            # Some Chrome versions handle SOCKS5/HTTP proxy auth natively
            # and show a dialog - we'll handle it via Page.javascriptDialogOpening

        return self

    def _click_next(self):
        """Click the Next/Submit button"""
        return self.browser.evaluate("""(() => {
            // Try specific IDs first
            for (const id of ['nextButton', 'idSIButton9', 'iSignupAction', 'idBtn_Back']) {
                const el = document.getElementById(id);
                if (el && el.offsetParent) { el.click(); return id; }
            }
            // Try button text
            const keywords = ['next', '下一步', 'sign in', 'create', 'submit', 'agree', 'continue', '同意'];
            const btns = document.querySelectorAll('button, input[type=submit], [role=button]');
            for (const b of btns) {
                if (!b.offsetParent && !b.offsetWidth) continue;
                const text = (b.textContent || b.value || '').toLowerCase().trim();
                for (const kw of keywords) {
                    if (text.includes(kw)) { b.click(); return text; }
                }
            }
            return null;
        })()""")

    def _detect_state(self) -> str:
        """Detect current page state"""
        url = self.browser.get_url().lower()
        body = self.browser.get_body_text().lower()
        
        if "login.live.com" in url and ("signin" in url or "login" in url):
            return "login"
        if "signup.live.com" in url:
            if any(kw in body for kw in ["create a password", "创建密码", "enter the password"]):
                return "password"
            if any(kw in body for kw in ["add details", "详细信息", "birth", "出生", "birthmonth", "country"]):
                return "birthdate"
            if any(kw in body for kw in ["first name", "last name", "姓", "名"]):
                return "name"
            if any(kw in body for kw in ["captcha", "verify", "验证"]):
                return "captcha"
            if any(kw in body for kw in ["agreement", "privacy", "同意", "agree"]):
                return "consent"
            if "blocked" in body or "已阻止" in body:
                return "blocked"
            return "signup_unknown"
        if "account.microsoft.com" in url or "outlook.live.com" in url:
            return "account_home"
        if any(kw in body for kw in ["stay signed in", "保持登录"]):
            return "stay_signed"
        if any(kw in body for kw in ["add recovery", "添加恢复", "skip"]):
            return "recovery"
        return "unknown"

    def _fill_email(self, email: str):
        """Fill email input"""
        result = self.browser.evaluate(f"""(() => {{
            const inputs = document.querySelectorAll("input[type='email'], input[name='MemberName'], input[name='email'], input[autocomplete='username']");
            for (const inp of inputs) {{
                if (inp.offsetParent || inp.offsetWidth) {{
                    inp.focus();
                    inp.value = '';
                    return inp.tagName + '|' + inp.name + '|' + inp.type;
                }}
            }}
            return null;
        }})()""")
        if result:
            logger.info("[FILL] Email input found: %s", result)
            # Type character by character to trigger React state
            for ch in email:
                self.browser._send_cmd("Input.dispatchKeyEvent", {
                    "type": "keyDown", "text": ch, "key": ch, "code": "",
                    "windowsVirtualKeyCode": 0, "nativeVirtualKeyCode": 0,
                })
                self.browser._send_cmd("Input.dispatchKeyEvent", {
                    "type": "keyUp", "key": ch, "code": "",
                    "windowsVirtualKeyCode": 0, "nativeVirtualKeyCode": 0,
                })
                time.sleep(random.uniform(0.03, 0.08))
            time.sleep(0.5)
            return True
        logger.warning("[FILL] Email input not found")
        return False

    def _fill_password_field(self, password: str):
        """Fill password input"""
        result = self.browser.evaluate("""(() => {
            const inputs = document.querySelectorAll("input[type='password']");
            for (const inp of inputs) {
                if (inp.offsetParent || inp.offsetWidth) {
                    inp.focus();
                    inp.value = '';
                    return 'found';
                }
            }
            return null;
        })()""")
        if result:
            for ch in password:
                self.browser._send_cmd("Input.dispatchKeyEvent", {
                    "type": "keyDown", "text": ch, "key": ch, "code": "",
                    "windowsVirtualKeyCode": 0, "nativeVirtualKeyCode": 0,
                })
                self.browser._send_cmd("Input.dispatchKeyEvent", {
                    "type": "keyUp", "key": ch, "code": "",
                    "windowsVirtualKeyCode": 0, "nativeVirtualKeyCode": 0,
                })
                time.sleep(random.uniform(0.03, 0.08))
            time.sleep(0.5)
            return True
        return False

    def _click_fluent_dropdown(self, button_id: str, target_text: str):
        """Click a Fluent UI dropdown and select option by keyboard navigation"""
        nid = self.browser.query_selector(f"#{button_id}")
        if not nid:
            return False
        rect = self.browser.get_element_rect(nid)
        if not rect:
            return False
        self.browser.click_at(rect["center_x"], rect["center_y"])
        time.sleep(0.8)
        # Get options and find target index
        result = self.browser.evaluate(f"""(() => {{
            const options = document.querySelectorAll('[role=option]');
            let targetIdx = -1;
            for (let i = 0; i < options.length; i++) {{
                const t = (options[i].textContent || '').trim();
                if (t === '{target_text}' || t.startsWith('{target_text}')) {{ targetIdx = i; }}
            }}
            return JSON.stringify({{targetIdx, count: options.length}});
        }})()""")
        if result:
            data = json.loads(result)
            if data["targetIdx"] >= 0:
                self.browser.press_key("Home")
                time.sleep(0.1)
                for _ in range(data["targetIdx"]):
                    self.browser.press_key("ArrowDown")
                    time.sleep(0.05)
                self.browser.press_key("Enter")
                time.sleep(0.5)
                return True
        return False

    def _fill_birthdate(self, year: int, month: int, day: int):
        """Fill birthdate (Fluent UI dropdowns)"""
        # Country dropdown
        self._click_fluent_dropdown("countryDropdownId", "CN")
        time.sleep(0.5)
        # Month dropdown (Fluent UI uses "7月" format for Chinese locale)
        self._click_fluent_dropdown("BirthMonthDropdown", str(month))
        time.sleep(0.5)
        # Day dropdown
        self._click_fluent_dropdown("BirthDayDropdown", str(day))
        time.sleep(0.5)
        # Year input
        year_input = self.browser.evaluate("""(() => {
            const inp = document.querySelector("input[name='BirthYear']");
            if (inp) { inp.focus(); inp.value = ''; return 'found'; }
            return null;
        })()""")
        if year_input:
            for ch in str(year):
                self.browser._send_cmd("Input.dispatchKeyEvent", {
                    "type": "keyDown", "text": ch, "key": ch, "code": "",
                    "windowsVirtualKeyCode": 0, "nativeVirtualKeyCode": 0,
                })
                self.browser._send_cmd("Input.dispatchKeyEvent", {
                    "type": "keyUp", "key": ch, "code": "",
                    "windowsVirtualKeyCode": 0, "nativeVirtualKeyCode": 0,
                })
                time.sleep(0.05)
        time.sleep(0.5)
        return True

    def _fill_name(self, first: str, last: str):
        """Fill first/last name"""
        self.browser.evaluate(f"""(() => {{
            const fn = document.querySelector("input[name='FirstName'], #firstNameInput");
            const ln = document.querySelector("input[name='LastName'], #lastNameInput");
            if (fn) {{ fn.focus(); fn.value = ''; }}
            if (ln) {{ ln.focus(); ln.value = ''; }}
        }})()""")
        # Type first name
        fn_found = self.browser.evaluate("""(() => {
            const fn = document.querySelector("input[name='FirstName'], #firstNameInput");
            if (fn) { fn.focus(); return 'found'; }
            return null;
        })()""")
        if fn_found:
            for ch in first:
                self.browser._send_cmd("Input.dispatchKeyEvent", {
                    "type": "keyDown", "text": ch, "key": ch, "code": "",
                    "windowsVirtualKeyCode": 0, "nativeVirtualKeyCode": 0,
                })
                self.browser._send_cmd("Input.dispatchKeyEvent", {
                    "type": "keyUp", "key": ch, "code": "",
                    "windowsVirtualKeyCode": 0, "nativeVirtualKeyCode": 0,
                })
                time.sleep(0.03)
        # Tab to last name
        self.browser.press_key("Tab")
        time.sleep(0.2)
        for ch in last:
            self.browser._send_cmd("Input.dispatchKeyEvent", {
                "type": "keyDown", "text": ch, "key": ch, "code": "",
                "windowsVirtualKeyCode": 0, "nativeVirtualKeyCode": 0,
            })
            self.browser._send_cmd("Input.dispatchKeyEvent", {
                "type": "keyUp", "key": ch, "code": "",
                "windowsVirtualKeyCode": 0, "nativeVirtualKeyCode": 0,
            })
            time.sleep(0.03)
        time.sleep(0.5)

    def _wait_for_manual_captcha(self, timeout: int = 300):
        """Wait for user to manually solve CAPTCHA"""
        logger.info("[CAPTCHA] Waiting for manual solve (timeout: %ds)...", timeout)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            state = self._detect_state()
            if state not in ("captcha", "unknown", "signup_unknown"):
                logger.info("[CAPTCHA] Page changed to: %s", state)
                return True
            time.sleep(2)
        return False

    def _handle_post_signup(self):
        """Handle pages after signup form (stay signed in, recovery, etc.)"""
        for _ in range(15):
            state = self._detect_state()
            logger.info("[POST] State: %s", state)

            if state == "account_home":
                return True
            if state == "blocked":
                logger.error("[POST] Account creation blocked by Microsoft")
                return False
            if state == "stay_signed":
                # Click "No" to not stay signed in
                self.browser.evaluate("""(() => {
                    const no = document.getElementById('idBtn_Back');
                    if (no) { no.click(); return; }
                    const btns = document.querySelectorAll('button');
                    for (const b of btns) {
                        const t = (b.textContent||'').toLowerCase();
                        if (t === 'no' || t === '否') { b.click(); return; }
                    }
                })()""")
                time.sleep(2)
                continue
            if state == "recovery":
                # Skip recovery
                self.browser.evaluate("""(() => {
                    const btns = document.querySelectorAll('button, a');
                    for (const b of btns) {
                        const t = (b.textContent||'').toLowerCase();
                        if (t.includes('skip') || t.includes('暂不') || t.includes('跳过')) { b.click(); return; }
                    }
                })()""")
                time.sleep(2)
                continue
            time.sleep(2)
        return False

    def run(self):
        """Run the full registration flow"""
        self.email = random_email()
        self.password = random_password()
        first, last = random_name()
        year, month, day = random_birthdate()

        logger.info("=" * 60)
        logger.info("Starting registration: %s", self.email)
        logger.info("Password: %s", self.password)
        logger.info("Name: %s %s", first, last)
        logger.info("Birth: %d-%02d-%02d", year, month, day)
        logger.info("=" * 60)

        # Launch Chrome with proxy
        self.launch()

        try:
            # Step 1: Navigate to signup
            logger.info("[STEP 1] Navigating to signup...")
            self.browser.navigate("https://signup.live.com/signup", wait_for_load=True, timeout=30)
            time.sleep(random.uniform(2, 4))

            # Step 1.5: Consent page
            for _ in range(3):
                body = self.browser.get_body_text().lower()
                if any(kw in body for kw in ["同意并继续", "agree and continue"]):
                    logger.info("[STEP 1.5] Consent page, clicking agree...")
                    self._click_next()
                    time.sleep(random.uniform(2, 3))
                else:
                    break

            # Step 2: Fill email
            state = self._detect_state()
            logger.info("[STEP 2] Page state: %s", state)
            if not self._fill_email(self.email):
                logger.error("Failed to fill email")
                return None
            time.sleep(0.5)
            self._click_next()
            time.sleep(random.uniform(2, 3))

            # Step 3: Fill password
            state = self._detect_state()
            logger.info("[STEP 3] Page state: %s", state)
            if not self._fill_password_field(self.password):
                logger.error("Failed to fill password")
                return None
            time.sleep(0.5)
            self._click_next()
            time.sleep(random.uniform(2, 3))

            # Step 4: Fill birthdate
            state = self._detect_state()
            logger.info("[STEP 4] Page state: %s", state)
            if state in ("birthdate", "signup_unknown", "unknown"):
                self._fill_birthdate(year, month, day)
                self._click_next()
                time.sleep(random.uniform(2, 3))

            # Step 5: Fill name
            state = self._detect_state()
            logger.info("[STEP 5] Page state: %s", state)
            if state in ("name", "signup_unknown", "unknown"):
                self._fill_name(first, last)
                self._click_next()
                time.sleep(random.uniform(2, 3))

            # Step 6: CAPTCHA
            state = self._detect_state()
            logger.info("[STEP 6] Page state: %s", state)
            if state == "captcha":
                logger.info("[STEP 6] CAPTCHA detected, waiting for manual solve...")
                if not self._wait_for_manual_captcha(300):
                    logger.error("CAPTCHA solve timed out")
                    self.browser.screenshot("captcha_timeout.png")
                    return None

            # Step 7: Post-signup handling
            state = self._detect_state()
            logger.info("[STEP 7] Page state: %s", state)
            if self._handle_post_signup():
                logger.info("[SUCCESS] Registration complete!")
                logger.info("Email: %s", self.email)
                logger.info("Password: %s", self.password)
                self.browser.screenshot("success.png")

                # Try to get OAuth tokens
                self._extract_oauth_tokens()
                return {
                    "email": self.email,
                    "password": self.password,
                    "refresh_token": getattr(self, '_oauth_rt', ''),
                    "success": True,
                }
            else:
                logger.error("Post-signup handling failed")
                self.browser.screenshot("post_signup_failed.png")
                return None

        except Exception as e:
            logger.exception("Registration failed: %s", e)
            try:
                self.browser.screenshot("error.png")
            except:
                pass
            return None
        finally:
            input("\nPress Enter to close browser...")
            try:
                self.browser.close()
            except:
                pass

    def _extract_oauth_tokens(self):
        """Try to get OAuth refresh token"""
        logger.info("[OAUTH] Attempting to get refresh token...")
        # Navigate to OAuth endpoint
        client_id = "14d82eec-204b-4c2f-b7e8-296a70dab67e"
        redirect = "https://login.microsoftonline.com/common/oauth2/nativeclient"
        oauth_url = f"https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize?client_id={client_id}&response_type=code&redirect_uri={redirect}&scope=offline_access+https://outlook.office365.com/.default"
        
        try:
            self.browser.navigate(oauth_url, wait_for_load=True, timeout=30)
            time.sleep(5)
            # Check for consent
            body = self.browser.get_body_text().lower()
            if "accept" in body or "\u540c\u610f" in body:
                self._click_next()
                time.sleep(5)
            # The redirect URL should contain the auth code
            final_url = self.browser.get_url()
            logger.info("[OAUTH] Final URL: %s", final_url)
            if "code=" in final_url:
                code = final_url.split("code=")[1].split("&")[0]
                logger.info("[OAUTH] Auth code: %s", code[:30]+"...")
                # Exchange for tokens
                self._exchange_code(code, client_id, redirect)
        except Exception as e:
            logger.warning("[OAUTH] Failed: %s", e)

    def _exchange_code(self, code: str, client_id: str, redirect: str):
        """Exchange auth code for refresh token"""
        import urllib.request, urllib.parse
        data = urllib.parse.urlencode({
            "client_id": client_id,
            "code": code,
            "redirect_uri": redirect,
            "grant_type": "authorization_code",
        }).encode()
        try:
            req = urllib.request.Request(
                "https://login.microsoftonline.com/consumers/oauth2/v2.0/token",
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                tokens = json.loads(resp.read())
                logger.info("[OAUTH] Access token: %s...", tokens.get("access_token", "")[:30])
                logger.info("[OAUTH] Refresh token: %s...", tokens.get("refresh_token", "")[:30])
                self._oauth_rt = tokens.get("refresh_token", "")
                # Save tokens
                out = {
                    "email": self.email,
                    "password": self.password,
                    "client_id": client_id,
                    "refresh_token": tokens.get("refresh_token"),
                }
                out_path = os.path.join(os.path.dirname(__file__), "..", "browser_extension", "邮箱凭证", f"{self.email}.json")
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                with open(out_path, "w") as f:
                    json.dump(out, f, indent=2)
                logger.info("[OAUTH] Credentials saved to: %s", out_path)
        except Exception as e:
            logger.warning("[OAUTH] Token exchange failed: %s", e)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Register Outlook account via CDP")
    parser.add_argument("--proxy", default=DEFAULT_PROXY, help="Proxy: host:port:user:pass")
    parser.add_argument("--headless", action="store_true", help="Run headless")
    parser.add_argument("--skip-proxy-check", action="store_true", help="Skip proxy verification")
    args = parser.parse_args()

    if not args.skip_proxy_check:
        if not verify_proxy(args.proxy):
            logger.error("Proxy verification failed. Check your proxy config.")
            sys.exit(1)

    registrar = OutlookRegistrar(args.proxy, headless=args.headless)
    result = registrar.run()
    if result:
        print("\n" + "=" * 60)
        print("REGISTRATION SUCCESS!")
        print(f"Email: {result['email']}")
        print(f"Password: {result['password']}")
        print("=" * 60)
    else:
        print("\nREGISTRATION FAILED")
        sys.exit(1)
