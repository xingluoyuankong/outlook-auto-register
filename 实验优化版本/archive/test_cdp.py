"""
CDP 混合方案 - 实跑测试
测试 1: 模块导入 + 编译
测试 2: CDPBrowser 启动 Chrome + WebSocket 连接
测试 3: CDP 基础操作（导航、DOM 查询、JS 执行）
测试 4: OS 输入模块（坐标转换）
测试 5: Outlook 注册模块（随机账号生成、状态检测）
测试 6: 本地 HTML mock 页面填写测试
"""
import sys
import os
import time
import json
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ninjemail'))

import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

PASS = 0
FAIL = 0
SKIP = 0

def test(name, fn):
    global PASS, FAIL, SKIP
    try:
        result = fn()
        if result == "SKIP":
            SKIP += 1
            print(f"  ⏭  {name} — SKIP")
        else:
            PASS += 1
            print(f"  ✅ {name}")
        return result
    except Exception as e:
        FAIL += 1
        print(f"  ❌ {name}: {e}")
        traceback.print_exc()
        return None

# ── Test 1: Module Import ──
print("\n═══ 1. 模块导入测试 ═══")

def test_import_cdp_browser():
    from cdp_browser import CDPBrowser, CDPLaunchConfig
    assert CDPBrowser is not None
    assert CDPLaunchConfig is not None
    return True

def test_import_os_input():
    from os_input import os_click, os_long_press, os_type_text, browser_to_screen_coords
    assert callable(os_click)
    assert callable(os_long_press)
    assert callable(os_type_text)
    return True

def test_import_cdp_outlook():
    from cdp_outlook import register_outlook_account, OutlookAccount, RegistrationResult
    assert callable(register_outlook_account)
    return True

def test_import_manager():
    from ninjemail_manager import Ninjemail, CDP_AVAILABLE, USE_CDP_HYBRID
    assert CDP_AVAILABLE == True
    print(f"    CDP_AVAILABLE={CDP_AVAILABLE}, USE_CDP_HYBRID={USE_CDP_HYBRID}")
    return True

test("cdp_browser 模块导入", test_import_cdp_browser)
test("os_input 模块导入", test_import_os_input)
test("cdp_outlook 模块导入", test_import_cdp_outlook)
test("ninjemail_manager CDP 集成", test_import_manager)

# ── Test 2: OS Input Module ──
print("\n═══ 2. OS 输入模块测试 ═══")

def test_screen_coords():
    from os_input import browser_to_screen_coords, ScreenCoords
    # viewport (100,200) + DPR=1.0 + window (50,50) + chrome height 85
    coords = browser_to_screen_coords(100, 200, 0, 0, 50, 50, 1.0)
    # x = 100*1.0 + 50 = 150, y = 200*1.0 + 50 + 85 = 335
    assert coords.x == 150, f"Expected x=150, got {coords.x}"
    assert coords.y == 335, f"Expected y=335, got {coords.y}"
    print(f"    browser(100,200) -> screen({coords.x},{coords.y})")
    return True

def test_os_press_functions():
    from os_input import os_press_enter, os_press_tab
    # Just verify they don't crash (no actual window focused)
    os_press_enter()
    os_press_tab()
    return True

test("坐标转换", test_screen_coords)
test("OS 按键函数可用", test_os_press_functions)

# ── Test 3: Random Account Generation ──
print("\n═══ 3. Outlook 账号生成测试 ═══")

def test_random_account():
    from cdp_outlook import _random_account
    acc = _random_account()
    assert "@" in acc.email, f"Bad email: {acc.email}"
    assert len(acc.password) >= 16, f"Weak password: {acc.password}"
    assert acc.first_name, "Missing first_name"
    assert acc.last_name, "Missing last_name"
    assert acc.birth_year, "Missing birth_year"
    print(f"    email={acc.email}")
    print(f"    name={acc.first_name} {acc.last_name}")
    print(f"    birth={acc.birth_year}-{acc.birth_month}-{acc.birth_day}")
    print(f"    pwd_len={len(acc.password)}")
    return True

def test_random_account_hotmail():
    from cdp_outlook import _random_account
    acc = _random_account(domain="hotmail.com", provider="hotmail")
    assert "@hotmail.com" in acc.email
    assert acc.provider == "hotmail"
    print(f"    hotmail: {acc.email}")
    return True

test("随机账号生成 (outlook)", test_random_account)
test("随机账号生成 (hotmail)", test_random_account_hotmail)

# ── Test 4: CDP Browser Launch + Connect ──
print("\n═══ 4. CDP 浏览器启动测试 ═══")

def test_cdp_launch():
    from cdp_browser import CDPBrowser, CDPLaunchConfig
    config = CDPLaunchConfig(headless=True)
    browser = CDPBrowser(config).launch()
    print(f"    Chrome PID={browser._process.pid}")
    print(f"    WS Endpoint={browser._ws_url}")
    print(f"    connected={browser._connected}")
    assert browser._connected, "WebSocket not connected"
    # Basic CDP command
    result = browser._send_cmd("Runtime.evaluate", {"expression": "1+1", "returnByValue": True})
    value = browser.evaluate("1+1")
    assert value == 2, f"Expected 2, got {value}"
    print(f"    CDP eval 1+1 = {value}")
    browser.close()
    return True

def test_cdp_navigate():
    from cdp_browser import CDPBrowser, CDPLaunchConfig
    config = CDPLaunchConfig(headless=True)
    browser = CDPBrowser(config).launch()
    # Navigate to a data: URI with a simple form
    html = """data:text/html,
    <html><body>
    <h1 id='title'>Test Page</h1>
    <input id='user' type='text' placeholder='username'/>
    <input id='pass' type='password' placeholder='password'/>
    <button id='submit' onclick="document.getElementById('result').innerText='clicked'">Submit</button>
    <div id='result'></div>
    </body></html>"""
    browser.navigate(html, wait_for_load=True, timeout=10)
    time.sleep(0.5)
    url = browser.get_url()
    print(f"    navigated to: {url[:60]}...")
    assert "data:" in url
    # Query element
    nid = browser.query_selector("#title")
    assert nid is not None, "Could not find #title"
    print(f"    found #title node_id={nid}")
    # Get body text
    body = browser.get_body_text()
    assert "Test Page" in body, f"Body text wrong: {body[:100]}"
    print(f"    body_text: '{body[:50]}...'")
    # Type into input
    browser.evaluate("document.getElementById('user').focus()")
    time.sleep(0.1)
    browser.type_text("hello_world", delay_ms=30)
    time.sleep(0.2)
    val = browser.evaluate("document.getElementById('user').value")
    assert val == "hello_world", f"Typed value wrong: {val}"
    print(f"    typed value: {val}")
    # Click button
    browser.evaluate("document.getElementById('submit').click()")
    time.sleep(0.2)
    result_text = browser.evaluate("document.getElementById('result').innerText")
    assert result_text == "clicked", f"Click result wrong: {result_text}"
    print(f"    click result: {result_text}")
    browser.close()
    return True

def test_cdp_touch():
    from cdp_browser import CDPBrowser, CDPLaunchConfig
    config = CDPLaunchConfig(headless=True)
    browser = CDPBrowser(config).launch()
    html = """data:text/html,
    <html><body>
    <div id='box' style='width:200px;height:200px;background:red;position:relative'>
    <div id='log'></div>
    </div>
    <script>
    const box = document.getElementById('box');
    const log = document.getElementById('log');
    let touched = false;
    box.addEventListener('touchstart', function(e) {
        touched = true;
        log.innerText = 'touchstart at ' + e.touches[0].clientX + ',' + e.touches[0].clientY;
    });
    box.addEventListener('touchend', function(e) {
        log.innerText += ' touchend';
    });
    </script>
    </body></html>"""
    browser.navigate(html, wait_for_load=True, timeout=10)
    time.sleep(0.3)
    # Dispatch touch events directly via JS (headless doesn't support real touch)
    result = browser.evaluate("""
        (() => {
            const box = document.getElementById('box');
            const rect = box.getBoundingClientRect();
            const cx = rect.left + rect.width/2;
            const cy = rect.top + rect.height/2;
            const touch = new Touch({identifier: 0, target: box, clientX: cx, clientY: cy, radiusX: 10, radiusY: 10});
            box.dispatchEvent(new TouchEvent('touchstart', {touches: [touch], bubbles: true}));
            box.dispatchEvent(new TouchEvent('touchend', {changedTouches: [touch], bubbles: true}));
            return document.getElementById('log').innerText;
        })()
    """)
    print(f"    touch test result: {result}")
    assert "touchstart" in str(result), f"Touch events didn't fire: {result}"
    browser.close()
    return True

test("CDP 浏览器启动 + WebSocket 连接", test_cdp_launch)
test("CDP 导航 + DOM 查询 + 键盘输入 + 点击", test_cdp_navigate)
test("CDP 触摸事件", test_cdp_touch)

# ── Test 5: Mock Outlook Registration Page ──
print("\n═══ 5. Mock Outlook 注册页面测试 ═══")

MOCK_SIGNUP_HTML = """data:text/html,
<html><body>
<h1>Create account</h1>
<div id='page'>
  <div id='step-username'>
    <input name='MemberName' id='usernameInput' type='email' placeholder='username'/>
    <select id='domainDropdownId'>
      <option value='@outlook.com'>@outlook.com</option>
      <option value='@hotmail.com'>@hotmail.com</option>
    </select>
    <button id='nextButton' onclick='showPassword()'>Next</button>
    <div id='username-error' style='display:none;color:red'>This username isn't available</div>
  </div>
  <div id='step-password' style='display:none'>
    <input name='Password' type='password' id='passwordInput' placeholder='Password'/>
    <button id='nextButton' onclick='showProfile()'>Next</button>
  </div>
  <div id='step-profile' style='display:none'>
    <input name='FirstName' id='firstNameInput' placeholder='First name'/>
    <input name='LastName' id='lastNameInput' placeholder='Last name'/>
    <button id='nextButton' onclick='showBirthdate()'>Next</button>
  </div>
  <div id='step-birthdate' style='display:none'>
    <select id='BirthMonth'><option value='1'>January</option><option value='6'>June</option></select>
    <select id='BirthDay'><option value='15'>15</option></select>
    <input name='BirthYear' id='BirthYear' placeholder='Year'/>
    <select id='countryRegionDropdown'><option value='US'>United States</option></select>
    <button id='nextButton' onclick='showDone()'>Next</button>
  </div>
  <div id='step-done' style='display:none'>
    <p id='success-msg'>Registration complete</p>
    <button id='okButton'>OK</button>
  </div>
</div>
<script>
function hideAll() {
  ['step-username','step-password','step-profile','step-birthdate','step-done'].forEach(
    id => document.getElementById(id).style.display='none'
  );
}
function showPassword() {
  hideAll(); document.getElementById('step-password').style.display='block';
}
function showProfile() {
  hideAll(); document.getElementById('step-profile').style.display='block';
}
function showBirthdate() {
  hideAll(); document.getElementById('step-birthdate').style.display='block';
}
function showDone() {
  hideAll(); document.getElementById('step-done').style.display='block';
}
</script>
</body></html>"""

def test_mock_registration():
    from cdp_browser import CDPBrowser, CDPLaunchConfig
    from cdp_outlook import (
        _fill_username, _fill_password, _fill_profile_fields, _fill_birthdate,
        _detect_page_state, OutlookAccount
    )
    config = CDPLaunchConfig(headless=True)
    browser = CDPBrowser(config).launch()
    browser.navigate(MOCK_SIGNUP_HTML, wait_for_load=True, timeout=10)
    time.sleep(0.3)

    account = OutlookAccount(
        username="testuser123456", email="testuser123456@outlook.com",
        password="T3st!P@ssw0rd_XyZ", first_name="Alice", last_name="Smith",
        country="United States", birth_month="6", birth_day="15", birth_year="1995",
        domain="outlook.com", provider="outlook",
    )

    # Step 1: Fill username
    state = _detect_page_state(browser)
    print(f"    state before username: {state}")
    assert state == "fill_username", f"Expected fill_username, got {state}"
    ok = _fill_username(browser, account)
    assert ok, "Username fill failed"
    time.sleep(0.5)

    # Step 2: Fill password
    state = _detect_page_state(browser)
    print(f"    state after next: {state}")
    ok = _fill_password(browser, account.password)
    assert ok, "Password fill failed"
    time.sleep(0.5)

    # Step 3: Fill profile
    state = _detect_page_state(browser)
    print(f"    state: {state}")
    ok = _fill_profile_fields(browser, account)
    assert ok, "Profile fill failed"
    time.sleep(0.5)

    # Step 4: Fill birthdate
    state = _detect_page_state(browser)
    print(f"    state: {state}")
    ok = _fill_birthdate(browser, account)
    assert ok, "Birthdate fill failed"
    time.sleep(0.5)

    # Step 5: Check final state
    state = _detect_page_state(browser)
    print(f"    final state: {state}")

    # Verify values were typed
    user_val = browser.evaluate("document.getElementById('usernameInput').value")
    pass_val = browser.evaluate("document.getElementById('passwordInput').value")
    fn_val = browser.evaluate("document.getElementById('firstNameInput').value")
    ln_val = browser.evaluate("document.getElementById('lastNameInput').value")
    year_val = browser.evaluate("document.getElementById('BirthYear').value")

    print(f"    username field: {user_val}")
    print(f"    password field: {'*' * len(pass_val)}")
    print(f"    first_name field: {fn_val}")
    print(f"    last_name field: {ln_val}")
    print(f"    birth_year field: {year_val}")

    assert user_val == "testuser123456", f"Username mismatch: {user_val}"
    assert pass_val == "T3st!P@ssw0rd_XyZ", f"Password mismatch: {pass_val}"
    assert fn_val == "Alice", f"First name mismatch: {fn_val}"
    assert ln_val == "Smith", f"Last name mismatch: {ln_val}"
    assert year_val == "1995", f"Year mismatch: {year_val}"

    browser.close()
    return True

test("Mock Outlook 注册流程完整填写", test_mock_registration)

# ── Test 6: Mock CAPTCHA Detection ──
print("\n═══ 6. Mock CAPTCHA 检测测试 ═══")

MOCK_HSprotect = """data:text/html,
<html><body>
<h1>Verify your identity</h1>
<p>Please press and hold the button below to prove you're human</p>
<iframe id='human-iframe' src='about:blank' style='width:300px;height:100px'></iframe>
<button id='verify-btn'>Press and hold</button>
</body></html>"""

MOCK_FUNCAPTCHA = """data:text/html,
<html><body>
<h1>Sign up</h1>
<iframe id='enforcementFrame' src='about:blank' style='width:300px;height:200px'></iframe>
<script>void(0);</script>
</body></html>"""

MOCK_NO_CAPTCHA = """data:text/html,
<html><body>
<h1>Sign up</h1>
<input type='text' placeholder='username'/>
</body></html>"""

def test_detect_hsprotect():
    from cdp_browser import CDPBrowser, CDPLaunchConfig
    from cdp_outlook import _detect_captcha
    config = CDPLaunchConfig(headless=True)
    browser = CDPBrowser(config).launch()
    browser.navigate(MOCK_HSprotect, wait_for_load=True, timeout=10)
    time.sleep(0.3)
    captcha = _detect_captcha(browser)
    print(f"    detected: {captcha}")
    assert captcha is not None, "hsprotect not detected"
    assert captcha["type"] == "hsprotect", f"Wrong type: {captcha['type']}"
    browser.close()
    return True

def test_detect_funcaptcha():
    from cdp_browser import CDPBrowser, CDPLaunchConfig
    from cdp_outlook import _detect_captcha
    config = CDPLaunchConfig(headless=True)
    browser = CDPBrowser(config).launch()
    browser.navigate(MOCK_FUNCAPTCHA, wait_for_load=True, timeout=10)
    time.sleep(0.3)
    captcha = _detect_captcha(browser)
    print(f"    detected: {captcha}")
    assert captcha is not None, "funcaptcha not detected"
    assert captcha["type"] == "funcaptcha", f"Wrong type: {captcha['type']}"
    browser.close()
    return True

def test_detect_no_captcha():
    from cdp_browser import CDPBrowser, CDPLaunchConfig
    from cdp_outlook import _detect_captcha
    config = CDPLaunchConfig(headless=True)
    browser = CDPBrowser(config).launch()
    browser.navigate(MOCK_NO_CAPTCHA, wait_for_load=True, timeout=10)
    time.sleep(0.3)
    captcha = _detect_captcha(browser)
    print(f"    detected: {captcha}")
    assert captcha is None, f"False positive: {captcha}"
    browser.close()
    return True

test("hsprotect CAPTCHA 检测", test_detect_hsprotect)
test("funcaptcha 检测", test_detect_funcaptcha)
test("无 CAPTCHA 时不误检", test_detect_no_captcha)

# ── Test 7: Page State Detection ──
print("\n═══ 7. 页面状态检测测试 ═══")

MOCK_STAY_SIGNED_IN = """data:text/html,
<html><body>
<h2>Stay signed in?</h2>
<p>Stay signed in so you don't have to sign in again next time.</p>
<button>Yes</button>
<button id='nobtn'>No</button>
</body></html>"""

MOCK_PRIVACY = """data:text/html,
<html><body>
<h2>Privacy notice</h2>
<p>Quick note about your Microsoft account</p>
<button>OK</button>
</body></html>"""

def test_state_stay_signed_in():
    from cdp_browser import CDPBrowser, CDPLaunchConfig
    from cdp_outlook import _detect_page_state
    config = CDPLaunchConfig(headless=True)
    browser = CDPBrowser(config).launch()
    browser.navigate(MOCK_STAY_SIGNED_IN, wait_for_load=True, timeout=10)
    time.sleep(0.3)
    state = _detect_page_state(browser)
    print(f"    state: {state}")
    assert state == "stay_signed_in", f"Expected stay_signed_in, got {state}"
    browser.close()
    return True

def test_state_privacy():
    from cdp_browser import CDPBrowser, CDPLaunchConfig
    from cdp_outlook import _detect_page_state
    config = CDPLaunchConfig(headless=True)
    browser = CDPBrowser(config).launch()
    browser.navigate(MOCK_PRIVACY, wait_for_load=True, timeout=10)
    time.sleep(0.3)
    state = _detect_page_state(browser)
    print(f"    state: {state}")
    assert state == "privacy_notice", f"Expected privacy_notice, got {state}"
    browser.close()
    return True

test("stay_signed_in 状态检测", test_state_stay_signed_in)
test("privacy_notice 状态检测", test_state_privacy)

# ── Summary ──
print(f"\n{'═' * 50}")
print(f"  测试结果: ✅ {PASS} 通过  ❌ {FAIL} 失败  ⏭ {SKIP} 跳过")
print(f"{'═' * 50}")
if FAIL > 0:
    sys.exit(1)
