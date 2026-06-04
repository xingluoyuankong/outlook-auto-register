"""
End-to-end Outlook registration test using CDP hybrid approach.
- Non-headless: you can watch the browser
- Handles hsprotect slider & press-and-hold CAPTCHA
- Extracts OAuth tokens (refresh_token) after registration
- Keeps browser open until you close it
- Saves credentials to file
"""

import sys, os, io, json, time, random, logging
from pathlib import Path
from datetime import datetime

# Ensure correct encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cdp_browser import CDPBrowser, CDPLaunchConfig
from cdp_outlook import (
    register_outlook_account, _random_account, OutlookAccount,
    _fill_username, _fill_password, _fill_birthdate, _fill_profile_fields,
    _click_next, _detect_page_state, _detect_captcha,
    _handle_hsprotect_captcha, _handle_funcaptcha,
    _handle_post_challenge, SIGNUP_URL,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

CRED_DIR = Path(r"E:\api获取（待跑通）\20-邮箱服务\ninjemail\browser_extension\邮箱凭证")
CRED_DIR.mkdir(parents=True, exist_ok=True)

OAUTH_AUTHORIZE_URL = (
    "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
    "?client_id={client_id}"
    "&response_type=code"
    "&redirect_uri=https://login.live.com/oauth20_desktop.srf"
    "&scope=openid+profile+email+offline_access+https://outlook.office365.com/IMAP.AccessAsUser.All+https://outlook.office365.com/SMTP.Send"
    "&response_mode=query"
)
OAUTH_TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"


def save_credentials(account: OutlookAccount, refresh_token: str = "", client_id: str = ""):
    """Save 4 credentials to file."""
    creds = {
        "email": account.email,
        "password": account.password,
        "client_id": client_id or account.client_id,
        "refresh_token": refresh_token,
        "created_at": datetime.now().isoformat(),
    }
    fname = CRED_DIR / f"{account.email.replace('@','_at_')}.json"
    with open(fname, "w", encoding="utf-8") as f:
        json.dump(creds, f, indent=2, ensure_ascii=False)
    logger.info("[CRED] Saved to %s", fname)
    return creds


def extract_oauth_tokens(browser: CDPBrowser, account: OutlookAccount) -> str:
    """
    After successful registration, navigate to OAuth authorize URL,
    login, and extract refresh_token from the redirect.
    """
    client_id = account.client_id
    auth_url = OAUTH_AUTHORIZE_URL.format(client_id=client_id)
    
    logger.info("[OAUTH] Navigating to OAuth authorize page...")
    browser.navigate(auth_url, wait_for_load=True, timeout=30)
    time.sleep(3)
    
    # Check if we need to login
    url = browser.get_url()
    body = browser.get_body_text().lower()
    
    if "login" in url or "sign in" in body or "登录" in body:
        logger.info("[OAUTH] Login required, filling credentials...")
        # Fill email
        email_field = browser.evaluate("""(() => {
            const inputs = document.querySelectorAll('input[type=email], input[name=loginfmt], #i0116');
            for (const el of inputs) {
                if (el.offsetParent !== null) return {found: true, sel: el.id || el.name};
            }
            return {found: false};
        })()""")
        if email_field and email_field.get("found"):
            sel = email_field["sel"]
            browser.evaluate(f"""(() => {{
                const el = document.getElementById('{sel}') || document.querySelector('input[name={sel}]');
                if (el) {{ el.focus(); el.value = ''; }}
            }})()""")
            time.sleep(0.3)
            browser.type_text(account.email, delay_ms=60)
            time.sleep(0.5)
            # Click Next
            browser.evaluate("""(() => {
                const btn = document.getElementById('idSIButton9') || document.querySelector('button[type=submit]');
                if (btn) btn.click();
            })()""")
            time.sleep(3)
        
        # Fill password
        pwd_field = browser.evaluate("""(() => {
            const inputs = document.querySelectorAll('input[type=password], input[name=passwd], #i0118');
            for (const el of inputs) {
                if (el.offsetParent !== null) return {found: true, sel: el.id || el.name};
            }
            return {found: false};
        })()""")
        if pwd_field and pwd_field.get("found"):
            sel = pwd_field["sel"]
            browser.evaluate(f"""(() => {{
                const el = document.getElementById('{sel}') || document.querySelector('input[name={sel}]');
                if (el) {{ el.focus(); el.value = ''; }}
            }})()""")
            time.sleep(0.3)
            browser.type_text(account.password, delay_ms=60)
            time.sleep(0.5)
            # Click Sign In
            browser.evaluate("""(() => {
                const btn = document.getElementById('idSIButton9') || document.querySelector('button[type=submit]');
                if (btn) btn.click();
            })()""")
            time.sleep(3)
        
        # Handle "Stay signed in?" prompt
        body = browser.get_body_text().lower()
        if "stay signed in" in body or "保持登录" in body:
            browser.evaluate("""(() => {
                const btn = document.getElementById('idBtn_Back') || document.getElementById('idSIButton9');
                if (btn) btn.click();
                else {
                    const btns = document.querySelectorAll('button');
                    for (const b of btns) {
                        const t = (b.textContent||'').toLowerCase();
                        if (t === 'no' || t === '否' || t === 'yes' || t === '是') { b.click(); break; }
                    }
                }
            })()""")
            time.sleep(3)
    
    # Now check for authorization code in URL
    url = browser.get_url()
    logger.info("[OAUTH] Current URL: %s", url[:200])
    
    if "code=" in url:
        # Extract code from URL
        import urllib.parse
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        auth_code = params.get("code", [""])[0]
        if auth_code:
            logger.info("[OAUTH] Got authorization code: %s...", auth_code[:20])
            # Exchange for tokens
            return exchange_code_for_token(auth_code, client_id)
    
    # If we're on a consent page, click Accept
    body = browser.get_body_text().lower()
    if "accept" in body or "consent" in body or "同意" in body or "允许" in body:
        logger.info("[OAUTH] Consent page detected, clicking accept...")
        browser.evaluate("""(() => {
            const btns = document.querySelectorAll('button, input[type=submit]');
            for (const b of btns) {
                const t = (b.textContent || b.value || '').toLowerCase();
                if (t.includes('accept') || t.includes('agree') || t.includes('同意') || t.includes('允许') || t.includes('yes')) {
                    b.click(); return true;
                }
            }
            return false;
        })()""")
        time.sleep(5)
        url = browser.get_url()
        if "code=" in url:
            import urllib.parse
            parsed = urllib.parse.urlparse(url)
            params = urllib.parse.parse_qs(parsed.query)
            auth_code = params.get("code", [""])[0]
            if auth_code:
                logger.info("[OAUTH] Got authorization code after consent: %s...", auth_code[:20])
                return exchange_code_for_token(auth_code, client_id)
    
    logger.warning("[OAUTH] Could not extract authorization code from URL: %s", url[:200])
    return ""


def exchange_code_for_token(auth_code: str, client_id: str) -> str:
    """Exchange authorization code for tokens."""
    import urllib.request, urllib.parse
    
    data = urllib.parse.urlencode({
        "client_id": client_id,
        "code": auth_code,
        "grant_type": "authorization_code",
        "redirect_uri": "https://login.live.com/oauth20_desktop.srf",
    }).encode()
    
    req = urllib.request.Request(OAUTH_TOKEN_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            refresh_token = result.get("refresh_token", "")
            access_token = result.get("access_token", "")
            logger.info("[OAUTH] Got refresh_token: %s...", refresh_token[:30] if refresh_token else "EMPTY")
            return refresh_token
    except Exception as e:
        logger.error("[OAUTH] Token exchange failed: %s", e)
        return ""


def main():
    print("=" * 60)
    print("  Outlook CDP Registration - End to End")
    print("=" * 60)
    
    account = _random_account()
    print(f"\n  Email:    {account.email}")
    print(f"  Password: {account.password}")
    print(f"  Name:     {account.first_name} {account.last_name}")
    print(f"  Birthday: {account.birth_year}-{account.birth_month}-{account.birth_day}")
    print()
    
    # Find extension path
    ext_dir = Path(r"E:\API获取工具\邮箱自动批量注册\ninjemail - 副本\ninjemail\browser_extension")
    ext_path = ""
    if ext_dir.exists():
        ext_path = str(ext_dir)
    
    config = CDPLaunchConfig(
        headless=False,
        extensions=[ext_path] if ext_path else [],
    )
    
    browser = None
    try:
        browser = CDPBrowser(config).launch()
        print("[1/7] Chrome launched, navigating to signup...")
        
        # Step 1: Navigate
        browser.navigate(SIGNUP_URL, wait_for_load=True, timeout=30)
        time.sleep(random.uniform(2, 3))
        
        # Step 1.5: Privacy consent
        for _ in range(3):
            body = browser.get_body_text().lower()
            if any(kw in body for kw in ["同意并继续", "agree and continue", "拒绝并退出"]):
                print("[1.5] Privacy consent page, clicking agree...")
                browser.evaluate("""(() => {
                    const btns = document.querySelectorAll('button');
                    for (const b of btns) {
                        const t = (b.textContent || '').toLowerCase();
                        if (t.includes('agree') || t.includes('同意')) { b.click(); return true; }
                    }
                    return false;
                })()""")
                time.sleep(random.uniform(2, 3))
            else:
                break
        
        # Step 2: Fill username
        print("[2/7] Filling email address...")
        if not _fill_username(browser, account):
            print("  ✗ FAILED to fill username")
            _wait_for_close(browser)
            return
        print("  ✓ Email filled")
        time.sleep(1)
        
        # Step 3: Fill password
        print("[3/7] Filling password...")
        if not _fill_password(browser, account.password):
            print("  ✗ FAILED to fill password")
            _wait_for_close(browser)
            return
        print("  ✓ Password filled")
        time.sleep(1)
        
        # Step 4: Fill birthdate/profile
        state = _detect_page_state(browser)
        print(f"[4/7] Page state: {state}")
        if state == "fill_profile":
            _fill_profile_fields(browser, account)
            print("  ✓ Profile filled")
            state = _detect_page_state(browser)
        if state == "fill_birthdate":
            _fill_birthdate(browser, account)
            print("  ✓ Birthdate filled")
        time.sleep(1)
        
        # Step 4.5: Fill name if needed
        state = _detect_page_state(browser)
        if state == "fill_profile":
            _fill_profile_fields(browser, account)
            print("  ✓ Name filled")
        time.sleep(1)
        
        # Step 5: CAPTCHA
        print("[5/7] Checking for CAPTCHA...")
        captcha = _detect_captcha(browser)
        if captcha:
            print(f"  ⚠ CAPTCHA detected: {captcha['type']} - {captcha['label']}")
            
            if captcha["type"] == "hsprotect":
                print("  → Attempting auto-solve (touch drag/long-press)...")
                cleared = _handle_hsprotect_captcha(browser, timeout=120)
            elif captcha["type"] == "funcaptcha":
                print("  → Attempting FunCaptcha solve...")
                cleared = _handle_funcaptcha(browser, timeout=120)
            else:
                cleared = False
            
            if not cleared:
                print("  ⚠ Auto-solve failed, waiting for manual intervention...")
                print("  (You have 10 minutes to solve it in the browser)")
                # Wait for CAPTCHA to clear
                deadline = time.monotonic() + 600
                while time.monotonic() < deadline:
                    captcha = _detect_captcha(browser)
                    if not captcha:
                        print("  ✓ CAPTCHA cleared!")
                        cleared = True
                        break
                    time.sleep(2)
            
            if not cleared:
                print("  ✗ CAPTCHA not solved")
                _wait_for_close(browser)
                return
        else:
            print("  ✓ No CAPTCHA detected")
        
        # Step 6: Post-challenge
        print("[6/7] Handling post-registration pages...")
        final_state = _handle_post_challenge(browser, account)
        print(f"  Final state: {final_state}")
        
        if final_state == "blocked":
            print("  ✗ Account creation BLOCKED by Microsoft")
            print("  → Try with a different IP/proxy")
            _wait_for_close(browser)
            return
        
        if final_state not in ("account_home",):
            # Check if we're actually logged in
            url = browser.get_url()
            body = browser.get_body_text().lower()
            if "outlook" in url or "office" in url or "account" in url:
                print("  ✓ Appears to be logged in (detected from URL)")
            else:
                print(f"  ⚠ Unexpected state: {final_state}")
                print(f"  URL: {url[:200]}")
        
        # Step 7: OAuth tokens
        print("[7/7] Extracting OAuth tokens...")
        refresh_token = extract_oauth_tokens(browser, account)
        
        if refresh_token:
            creds = save_credentials(account, refresh_token, account.client_id)
            print("\n" + "=" * 60)
            print("  ✓ SUCCESS! Registration complete with 4 credentials:")
            print(f"  Email:         {creds['email']}")
            print(f"  Password:      {creds['password']}")
            print(f"  Client ID:     {creds['client_id']}")
            print(f"  Refresh Token: {creds['refresh_token'][:40]}...")
            print("=" * 60)
        else:
            # Still save what we have (3 credentials)
            creds = save_credentials(account, "", account.client_id)
            print("\n" + "=" * 60)
            print("  ⚠ Registration succeeded but OAuth token extraction failed")
            print(f"  Email:    {creds['email']}")
            print(f"  Password: {creds['password']}")
            print(f"  Client ID: {creds['client_id']}")
            print("  Refresh Token: (not obtained)")
            print("=" * 60)
        
        # Take final screenshot
        try:
            browser.screenshot("final_result.png")
        except:
            pass
        
        # Keep browser open
        print("\n  Browser will stay open. Press Ctrl+C to exit.")
        _wait_for_close(browser)
        
    except KeyboardInterrupt:
        print("\n  Interrupted by user")
    except Exception as e:
        logger.exception("Registration failed: %s", e)
        print(f"\n  ✗ ERROR: {e}")
        if browser:
            _wait_for_close(browser)


def _wait_for_close(browser: CDPBrowser):
    """Keep browser open until user closes it."""
    try:
        print("  (Browser staying open - close it manually or press Ctrl+C)")
        while True:
            try:
                browser.get_url()  # Will throw if browser closed
                time.sleep(1)
            except:
                print("  Browser closed.")
                break
    except KeyboardInterrupt:
        print("  Exiting...")


if __name__ == "__main__":
    main()
