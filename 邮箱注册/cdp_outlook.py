"""
CDP-based Outlook Registration Module

Uses the hybrid approach:
1. Clean Chrome (no automation flags) via CDP
2. Extension-like DOM detection logic (from browser_extension/content/outlook-signup.js)
3. OS-level input for typing and clicking
4. Touch long-press for CAPTCHA (Input.dispatchMouseEvent + pointerType:"touch")

This replaces Selenium-based outlook.py for anti-detection.
"""

from __future__ import annotations

import logging
import random
import re
import secrets
import string
import time
import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Tuple

try:
    from .cdp_browser import CDPBrowser, CDPLaunchConfig
    from .os_input import (
        os_click, os_long_press, os_type_text,
        os_press_enter, os_press_tab, os_press_escape,
        os_dismiss_webauthn_dialog,
        browser_to_screen_coords, get_browser_window_position,
    )
    from .proxy_utils import parse_proxy, ProxyInfo
except ImportError:
    from cdp_browser import CDPBrowser, CDPLaunchConfig
    from os_input import (
        os_click, os_long_press, os_type_text,
        os_press_enter, os_press_tab, os_press_escape,
        os_dismiss_webauthn_dialog,
        browser_to_screen_coords, get_browser_window_position,
    )
    from proxy_utils import parse_proxy, ProxyInfo

logger = logging.getLogger(__name__)

# ── Constants ──
SIGNUP_URL = "https://signup.live.com/signup"
MANUAL_CAPTCHA_TIMEOUT = 600  # 10 min for manual CAPTCHA (visible mode)
MANUAL_CAPTCHA_TIMEOUT_HEADLESS = 15  # 15s for headless (can't manually solve)
_captcha_force_skip = False
_registration_paused = False
_registration_stop = False
_current_reg_step = ""
_current_reg_steps = {}  # 线程级步骤跟踪 {thread_id: step}，支持并发模式
_active_browsers = {}  # 线程安全的浏览器实例字典 {thread_id: browser}
_active_browsers_lock = threading.Lock()  # 保护 _active_browsers 的锁

# ── 并发安全: 线程级控制状态 ──
# 全局变量在并发时所有线程共享，导致一个线程停止/暂停影响所有线程
# 现在改为线程级存储，每个线程独立控制
_thread_states = {}  # {thread_id: {"paused": bool, "stop": bool, "captcha_skip": bool}}
_thread_states_lock = threading.Lock()


def reset_all_states():
    """重置所有控制状态（全局变量+线程状态字典），用于新注册任务启动前清理残留。
    解决：上次任务点停止后，残留的 stop=True 导致新任务立即退出浏览器的问题。
    """
    global _captcha_force_skip, _registration_paused, _registration_stop, _current_reg_step
    _captcha_force_skip = False
    _registration_paused = False
    _registration_stop = False
    _current_reg_step = ""
    with _thread_states_lock:
        _thread_states.clear()
    with _active_browsers_lock:
        _current_reg_steps.clear()
    logger.info("[CDP] 所有控制状态已重置（全局变量+线程状态已清空）")


def _get_thread_state() -> dict:
    """获取当前线程的控制状态（不存在则初始化）"""
    tid = threading.current_thread().ident
    with _thread_states_lock:
        if tid not in _thread_states:
            _thread_states[tid] = {"paused": False, "stop": False, "captcha_skip": False}
        return _thread_states[tid]


def _clear_thread_state():
    """清理当前线程的控制状态"""
    tid = threading.current_thread().ident
    with _thread_states_lock:
        _thread_states.pop(tid, None)

def set_registration_paused(val=True):
    """设置当前线程的暂停状态（并发安全）"""
    state = _get_thread_state()
    state["paused"] = val
    # 同时保留全局变量兼容性（单线程模式）
    global _registration_paused; _registration_paused = val

def set_registration_stop(val=True):
    """设置当前线程的停止状态（并发安全），并关闭浏览器"""
    state = _get_thread_state()
    state["stop"] = val
    # 同时保留全局变量兼容性（单线程模式）
    global _registration_stop; _registration_stop = val
    # 立即尝试关闭所有活跃的浏览器，加速停止
    if val:
        _kill_all_browsers()

def get_current_reg_step():
    """返回当前注册步骤（并发模式下返回第一个活跃线程的步骤）"""
    # 优先返回线程级步骤
    with _active_browsers_lock:
        if _current_reg_steps:
            # 返回第一个活跃线程的步骤
            for tid, step in _current_reg_steps.items():
                if step:
                    return step
    return _current_reg_step

def _kill_all_browsers():
    """关闭所有注册流程使用的浏览器实例（并发安全），不影响用户自己的浏览器"""
    with _active_browsers_lock:
        browsers = dict(_active_browsers)
        _active_browsers.clear()
    for tid, browser in browsers.items():
        try:
            logger.info("[STOP] 关闭注册浏览器 (thread=%s)...", tid)
            browser.close()
        except Exception as e:
            logger.warning("[STOP] 关闭浏览器异常 (thread=%s): %s", tid, e)

def _register_browser(browser):
    """将浏览器实例注册到当前线程（并发安全）"""
    tid = threading.current_thread().ident
    with _active_browsers_lock:
        _active_browsers[tid] = browser

def _unregister_browser():
    """从当前线程注销浏览器实例（并发安全）"""
    tid = threading.current_thread().ident
    with _active_browsers_lock:
        _active_browsers.pop(tid, None)
        _current_reg_steps.pop(tid, None)

def stop_registration_browser():
    """外部调用：关闭所有注册流程使用的浏览器，不影响其他功能"""
    _kill_all_browsers()

def kill_orphan_chrome_processes():
    """清理孤儿 Chrome 进程（outlook 注册残留），不影响 agent-browser 等其他浏览器"""
    import subprocess as _sp
    try:
        # 找出所有带 --user-data-dir=/tmp 的 chrome 进程（注册用的临时目录）
        r = _sp.run(
            ["pgrep", "-a", "chrome"],
            capture_output=True, text=True, timeout=5
        )
        killed = 0
        for line in r.stdout.splitlines():
            # 只杀注册用的临时 user-data-dir，不碰 agent-browser / zo 内置浏览器
            if "--user-data-dir=" in line and "/tmp" in line and "agent-browser" not in line:
                parts = line.split()
                if parts and parts[0].isdigit():
                    pid = int(parts[0])
                    try:
                        os.kill(pid, 9)
                        killed += 1
                    except (ProcessLookupError, PermissionError):
                        pass
        if killed:
            logger.info("[CLEANUP] Killed %d orphan Chrome processes", killed)
        return killed
    except Exception as e:
        logger.warning("[CLEANUP] Failed to kill orphan chrome: %s", e)
        return 0

def _check_pause_or_stop(step=""):
    """检查暂停/停止。暂停时阻塞直到恢复，返回后调用者应重新检测页面状态。
    并发安全: 优先读取线程级状态，回退到全局状态。
    返回: False=继续, True=应停止"""
    global _registration_paused, _registration_stop, _captcha_force_skip, _current_reg_step
    _current_reg_step = step
    # 同时更新线程级步骤跟踪
    tid = threading.current_thread().ident
    _current_reg_steps[tid] = step
    # ── 并发安全: 优先读取线程级状态 ──
    state = _get_thread_state()
    should_stop = state.get("stop", False) or _registration_stop
    should_pause = state.get("paused", False) or _registration_paused
    should_skip = state.get("captcha_skip", False) or _captcha_force_skip
    if should_stop:
        return True
    if not should_pause:
        return False
    # 已暂停 → 阻塞等待恢复
    logger.info("[PAUSE] ⏸ 已暂停在步骤: %s，等待继续...", step)
    while True:
        state = _get_thread_state()
        should_pause = state.get("paused", False) or _registration_paused
        should_stop = state.get("stop", False) or _registration_stop
        should_skip = state.get("captcha_skip", False) or _captcha_force_skip
        if not should_pause:
            break
        if should_stop:
            return True
        if should_skip:
            break
        time.sleep(0.5)
    # 已恢复 → 返回 False，调用者应重新检测页面状态
    logger.info("[PAUSE] ▶ 已恢复，将重新检测页面状态继续")
    return False


def set_captcha_force_skip(value=True):
    """设置当前线程的验证码跳过状态（并发安全）"""
    state = _get_thread_state()
    state["captcha_skip"] = value
    # 同时保留全局变量兼容性（单线程模式）
    global _captcha_force_skip; _captcha_force_skip = value
AUTO_CAPTCHA_TIMEOUT = 120    # 2 min for auto CAPTCHA attempt

# ── Field Selectors (mirrored from browser_extension/content/outlook-signup.js) ──
FIELD_SELECTORS = {
    "username": [
        "input[name='MemberName']",
        "input[name='Username']",
        "input[name='email']",
        "#usernameInput",
        "input[type='email']",
        "input[autocomplete='username']",
        "input[id*='email' i]",
        "input[id*='user' i]",
        "input[name*='email' i]",
        "input[name*='user' i]",
        "input[placeholder*='@']",
        "input[placeholder*='email' i]",
        "input[placeholder*='邮箱']",
        "input[aria-label*='email' i]",
        "input[aria-label*='user' i]",
        "input[type='text'][maxlength='112']",
    ],
    "password": [
        "input[name='Password']",
        "input[type='password']",
        "input[autocomplete='new-password']",
    ],
    "first_name": [
        "input[name='FirstName']",
        "#firstName",
        "#firstNameInput",
        "input[autocomplete='given-name']",
    ],
    "last_name": [
        "input[name='LastName']",
        "#lastName",
        "#lastNameInput",
        "input[autocomplete='family-name']",
    ],
    "birth_month": [
        "#BirthMonth",
        "select[name='BirthMonth']",
        "#BirthMonthDropdown",
        "[aria-label*='Birth month' i]",
        "[aria-label*='月份']",
    ],
    "birth_day": [
        "#BirthDay",
        "select[name='BirthDay']",
        "#BirthDayDropdown",
        "[aria-label*='Birth day' i]",
        "[aria-label*='日期']",
    ],
    "birth_year": [
        "#BirthYear",
        "input[name='BirthYear']",
        "input[aria-label*='Birth year' i]",
        "input[aria-label*='年份']",
    ],
    "country": [
        "#countryRegionDropdown",
        "#countryDropdownId",
        "select[name='Country']",
    ],
    "submit": [
        "#nextButton",
        "button[type='submit']",
        "button[data-testid='primaryButton']",
        "#idSIButton9",
    ],
    "live_switch": [
        "#liveSwitch",
        "a#liveSwitch",
    ],
    "domain_dropdown": [
        "#domainDropdownId",
        "#domainSelect",
    ],
}

# Post-challenge state detection (from extension)
POST_CHALLENGE_MARKERS = {
    "privacy_notice": ["privacynotice", "privacy notice", "隐私声明", "个人数据导出许可", "数据导出许可", "data export", "同意并继续", "agree and continue", "拒绝并退出", "帮助改进", "改进产品", "隐私偏好", "是否希望", "account.live.com/consent"],  # 包含 Consent/Update 页面
    "account_notice": ["quick note about your microsoft account", "有关 microsoft 帐户的快速说明"],
    "stay_signed_in": ["stay signed in", "保持登录"],
    "add_recovery": ["add a recovery", "recovery email", "添加恢复"],
    "passkey_prompt": ["passkey", "security key", "windows hello", "通行密钥", "创建通行密钥"],
    "microsoft_problem": ["we ran into a problem", "something went wrong", "我们遇到了问题"],
    "success": ["account has been created", "帐户已创建"],
}


@dataclass
class OutlookAccount:
    """Outlook account registration data."""
    username: str = ""
    email: str = ""
    password: str = ""
    first_name: str = ""
    last_name: str = ""
    country: str = "United States"
    birth_month: str = ""
    birth_day: str = ""
    birth_year: str = ""
    domain: str = "outlook.com"
    provider: str = "outlook"
    client_id: str = "14d82eec-204b-4c2f-b7e8-296a70dab67e"


@dataclass
class RegistrationResult:
    """Result of an Outlook registration attempt."""
    success: bool = False
    email: str = ""
    password: str = ""
    username: str = ""
    provider: str = "outlook"
    domain: str = "outlook.com"
    client_id: str = ""
    error: str = ""
    final_url: str = ""
    final_state: str = ""
    challenge_type: str = ""
    challenge_cleared: bool = False
    screenshot_path: str = ""
    refresh_token: str = ""  # OAuth refresh token (populated when extract_rt=True)
    browser: object = None  # Keep browser reference when keep_browser_open=True
    auto_country: str = ""  # 网站根据代理IP自动选择的国家


def _random_account(domain: str = "outlook.com", provider: str = "outlook") -> OutlookAccount:
    """Generate a random Outlook account."""
    first_names = [
        "Aiden", "Amelia", "Andrew", "Avery", "Blake", "Brooke", "Caleb", "Carter",
        "Chloe", "Claire", "Connor", "Dylan", "Eleanor", "Elliot", "Emma", "Ethan",
        "Grace", "Hannah", "Harper", "Hazel", "Henry", "Ian", "Iris", "Isaac",
        "Jack", "James", "Julian", "Landon", "Leah", "Leo", "Lily", "Logan",
        "Lucas", "Mason", "Maya", "Mia", "Miles", "Naomi", "Nolan", "Nora",
    ]
    last_names = [
        "Adams", "Allen", "Bailey", "Baker", "Bennett", "Brooks", "Carter", "Clark",
        "Coleman", "Collins", "Cooper", "Davis", "Diaz", "Edwards", "Evans", "Fisher",
        "Flores", "Foster", "Garcia", "Gray", "Green", "Hall", "Harris", "Hayes",
        "Henderson", "Hill", "Howard", "Hughes", "Jackson", "James", "Johnson",
        "Kelly", "King", "Lewis", "Long", "Martin", "Mitchell", "Morgan", "Murphy",
    ]

    first = random.choice(first_names)
    last = random.choice(last_names)

    first_lower = first.lower()
    last_lower = last.lower()
    style = random.randint(0, 4)
    suffix = ''.join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=random.randint(12, 16)))

    chunks = [
        f"{first_lower[:random.randint(3, min(7, len(first_lower)))]}{last_lower[:random.randint(2, min(6, len(last_lower)))]}",
        f"{last_lower[:random.randint(4, min(8, len(last_lower)))]}{first_lower[:random.randint(2, min(5, len(first_lower)))]}",
        f"mx{''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=2))}{''.join(random.choices('0123456789', k=2))}",
        f"{first_lower[0]}{last_lower}{''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=2))}",
        f"{first_lower}{''.join(random.choices('0123456789', k=random.randint(2, 4)))}",
    ]
    username = f"{chunks[style]}{suffix}"[:30]

    lower = "abcdefghijkmnopqrstuvwxyz"
    upper = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    digits = "23456789"
    symbols = "!@#$%^&*_-+="
    alphabet = lower + upper + digits + symbols
    chars = [random.choice(upper), random.choice(lower), random.choice(digits), random.choice(symbols)]
    while len(chars) < 18:
        chars.append(random.choice(alphabet))
    for i in range(len(chars) - 1, 0, -1):
        j = random.randint(0, i)
        chars[i], chars[j] = chars[j], chars[i]
    password = "".join(chars)

    now_year = time.localtime().tm_year
    year = random.randint(now_year - 46, now_year - 19)
    month = random.randint(1, 12)
    max_day = [0, 31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month]
    day = random.randint(1, max_day)

    return OutlookAccount(
        username=username, email=f"{username}@{domain}", password=password,
        first_name=first, last_name=last, country="United States",
        birth_month=str(month), birth_day=str(day), birth_year=str(year),
        domain=domain, provider=provider,
    )


def _month_name(month: str) -> str:
    names = {"1": "January", "2": "February", "3": "March", "4": "April",
             "5": "May", "6": "June", "7": "July", "8": "August",
             "9": "September", "10": "October", "11": "November", "12": "December"}
    return names.get(str(month).lstrip("0"), str(month))


def _find_first_visible(browser: CDPBrowser, selectors: list[str]) -> Tuple[dict | None, str]:
    for selector in selectors:
        try:
            nid = browser.query_selector(selector)
            if nid:
                rect = browser.get_element_rect(nid)
                if rect and rect["width"] > 0 and rect["height"] > 0:
                    return {"node_id": nid, "rect": rect, "selector": selector}, selector
        except Exception:
            continue
    return None, ""


def _type_into_element(browser: CDPBrowser, element_info: dict, text: str, clear_first: bool = True):
    selector = element_info["selector"]
    browser.focus_element(selector)
    time.sleep(random.uniform(0.1, 0.3))
    if clear_first:
        escaped_sel = selector.replace("'", "\\'")
        browser.evaluate(f"""
            (() => {{{{
                const el = document.querySelector('{escaped_sel}');
                if (el) {{{{ el.value = ''; el.dispatchEvent(new Event('input', {{{{bubbles: true}}}})); }}}}
            }}}})()
        """)
        time.sleep(random.uniform(0.1, 0.2))
    browser.type_text(text, delay_ms=random.randint(50, 120))
    time.sleep(random.uniform(0.2, 0.5))


def _select_dropdown(browser: CDPBrowser, selector: str, visible_text: str):
    escaped_sel = selector.replace("'", "\\'")
    lower_text = visible_text.lower()
    js = f"""
    (() => {{
        const el = document.querySelector('{escaped_sel}');
        if (!el) return false;
        if (el.tagName === 'SELECT') {{
            for (let i = 0; i < el.options.length; i++) {{
                if (el.options[i].text.trim().toLowerCase() === '{lower_text}') {{
                    el.selectedIndex = i;
                    el.dispatchEvent(new Event('change', {{bubbles: true}}));
                    return true;
                }}
            }}
            return false;
        }}
        el.click();
        return true;
    }})()
    """
    browser.evaluate(js)
    time.sleep(random.uniform(0.3, 0.6))
    option_js = f"""
    (() => {{
        const options = document.querySelectorAll('[role="option"], option, li, [data-value]');
        for (const opt of options) {{
            const text = (opt.textContent || opt.innerText || '').trim().toLowerCase();
            if (text === '{lower_text}' || text.includes('{lower_text}')) {{
                if (opt.offsetParent !== null) {{ opt.click(); return true; }}
            }}
        }}
        return false;
    }})()
    """
    browser.evaluate(option_js)
    time.sleep(random.uniform(0.3, 0.5))



def _check_page_advanced(browser: CDPBrowser) -> str | None:
    """Check if page advanced past CAPTCHA WITHOUT calling _detect_captcha.
    Returns state string or None if still on CAPTCHA/loading."""
    url = browser.get_url().lower()
    body = browser.get_body_text().lower()
    body_len = len(body)
    for state, markers in POST_CHALLENGE_MARKERS.items():
        for marker in markers:
            if marker in body or marker in url:
                if state in ("privacy_notice", "account_notice", "stay_signed_in",
                             "add_recovery", "passkey_prompt", "success", "microsoft_problem"):
                    return state
    # 排除 login.microsoft.com，因为那是登录页面，不是账户主页
    is_login_page = "login.microsoft.com" in url or "login.live.com" in url
    if not is_login_page and ("account.microsoft.com" in url or "outlook.live.com" in url):
        return "account_home"
    if any(kw in body for kw in ["\u88ab\u963b\u6b62", "blocked", "\u5f02\u5e38\u6d3b\u52a8"]):
        return "blocked"
    # ── 修复: body 为空时不返回 fill 状态，避免 SPA 未渲染时误判 ──
    if body_len >= 50:
        for field_type in ("username", "password", "first_name", "birth_month", "birth_year"):
            for selector in FIELD_SELECTORS.get(field_type, []):
                try:
                    nid = browser.query_selector(selector)
                    if nid and browser.is_element_visible(nid):
                        return "fill_" + field_type
                except Exception:
                    continue
    has_form = browser.evaluate("""(() => {
        const inputs = document.querySelectorAll('input[type=text], input[type=email], input[type=password], input[type=number], select');
        for (const el of inputs) { if (el.offsetParent !== null && el.offsetWidth > 50) return true; }
        return false;
    })()""")
    if has_form:
        return "form_visible"
    return None

def _detect_page_state(browser: CDPBrowser) -> str:
    url = browser.get_url().lower()
    body = browser.get_body_text().lower()
    body_len = len(body)

    # \u2500\u2500 Chrome \u9519\u8bef\u9875\u68c0\u6d4b\uff08\u4ee3\u7406\u4e0d\u901a/\u7f51\u7edc\u9519\u8bef\uff09\u2500\u2500
    # 排除微软域名上的错误页面（login.live.com/err=... 不是代理错误）
    is_ms_domain = any(d in url for d in ["login.live.com", "signup.live.com", "account.live.com", "login.microsoft.com", "account.microsoft.com"])
    # 只用最可靠的指标：chrome-error:// URL 判断代理错误
    # 不再用 body 文本关键词匹配（微软页面JS代码中常含这些字符串，导致误判关闭浏览器）
    if "chrome-error" in url:
        return "proxy_error"
    # 非微软域名 + body 为空 → 页面未加载
    if not is_ms_domain and body_len < 10:
        return "proxy_error"

    for state, markers in POST_CHALLENGE_MARKERS.items():
        for marker in markers:
            if marker in body or marker in url:
                if state in ("privacy_notice", "account_notice", "stay_signed_in",
                             "add_recovery", "passkey_prompt", "success"):
                    return state
    # \u6392\u9664 login.microsoft.com\uff0c\u56e0\u4e3a\u90a3\u662f\u767b\u5f55\u9875\u9762\uff0c\u4e0d\u662f\u8d26\u6237\u4e3b\u9875
    is_login_page = "login.microsoft.com" in url or "login.live.com" in url
    if not is_login_page and ("account.microsoft.com" in url or "outlook.live.com" in url):
        return "account_home"
    # Consent/Update \u9875\u9762\uff08body \u53ef\u80fd\u4e3a 0\uff0c\u53ea\u80fd\u901a\u8fc7 URL \u68c0\u6d4b\uff09
    if "account.live.com/consent" in url:
        return "privacy_notice"  # \u5904\u7406\u65b9\u5f0f\u548c privacy_notice \u7c7b\u4f3c\uff0c\u901a\u8fc7\u6309\u94ae\u786e\u8ba4
    # Blocked state
    if any(kw in body for kw in ["\u88ab\u963b\u6b62", "blocked", "\u5f02\u5e38\u6d3b\u52a8", "\u6b64\u5e10\u6237\u5df2\u88ab"]):
        return "blocked"
    # ── 关键修复: 微软域名 + body 为空 → SPA 未渲染，返回 loading 而非 fill_* ──
    # signup.live.com 是 SPA，JS 未执行时 body 为空但 input 元素可能已存在于 DOM
    # 此时不应返回 fill_username，否则会导致无限循环
    if is_ms_domain and body_len < 50:
        # 检查 readyState 是否 complete
        ready = browser.evaluate("document.readyState")
        if ready == "complete":
            # DOM complete 但 body 仍为空 → JS 渲染失败，需要刷新
            return "page_empty"
        return "loading"

    for selector in FIELD_SELECTORS["username"]:
        nid = browser.query_selector(selector)
        if nid and browser.is_element_visible(nid):
            return "fill_username"
    for selector in FIELD_SELECTORS["password"]:
        nid = browser.query_selector(selector)
        if nid and browser.is_element_visible(nid):
            return "fill_password"
    for selector in FIELD_SELECTORS["first_name"]:
        nid = browser.query_selector(selector)
        if nid and browser.is_element_visible(nid):
            return "fill_profile"
    for selector in FIELD_SELECTORS["birth_month"] + FIELD_SELECTORS["birth_year"]:
        nid = browser.query_selector(selector)
        if nid and browser.is_element_visible(nid):
            return "fill_birthdate"
    if _detect_captcha(browser):
        return "captcha"
    return "unknown"


def _detect_captcha(browser: CDPBrowser) -> dict | None:
    body = browser.get_body_text().lower()
    url = browser.get_url().lower()
    
    # ── hsprotect / HUMAN Security detection (expanded) ──
    hsprotect_text = any(kw in body for kw in [
        "press and hold", "prove you're human", "human challenge",
        "\u6309\u4f4f", "\u8bc1\u660e\u4f60\u4e0d\u662f\u673a\u5668\u4eba",
        "\u9a8c\u8bc1\u4f60\u4e0d\u662f\u673a\u5668\u4eba",
        "prove you are human", "security check", "verification required",
    ])
    hsprotect_url = "hsprotect.net" in url or "fpt.live.com" in url
    hsprotect_iframe = browser.evaluate("""
        (() => {
            const frames = document.querySelectorAll('iframe');
            for (const f of frames) {
                const style = window.getComputedStyle(f);
                const rect = f.getBoundingClientRect();
                const visible = style.display !== 'none' && style.visibility !== 'hidden'
                    && Number(style.opacity || 1) !== 0 && rect.width > 80 && rect.height > 50;
                const src = (f.src || '').toLowerCase();
                const title = (f.title || '').toLowerCase();
                const id = (f.id || '').toLowerCase();
                if (visible && (src.includes('hsprotect') || src.includes('fpt.live.com') ||
                    title.includes('human iframe') || id.includes('human') || id.includes('challenge'))) {
                    return { src: f.src, title: f.title, id: f.id, visible: true };
                }
            }
            const hsEls = document.querySelectorAll('[class*=hsprotect], [class*=human-security], [class*=h-captcha], [id*=hsprotect]');
            for (const el of hsEls) {
                const r = el.getBoundingClientRect();
                if (r.width > 50 && r.height > 30) {
                    return { src: 'inline', title: el.className || el.id, visible: true };
                }
            }
            return null;
        })()
    """)
    if hsprotect_url or hsprotect_text or hsprotect_iframe:
        evidence = "text_match"
        if hsprotect_iframe:
            evidence = hsprotect_iframe.get("src", "") or hsprotect_iframe.get("id", "") or "iframe_match"
        return {"type": "hsprotect", "label": "HUMAN Security (hsprotect)",
                "evidence": evidence}
    
    # ── Arkose / FunCaptcha ──
    funcaptcha_markers = ["arkose", "funcaptcha", "game-core-frame", "enforcementframe"]
    for marker in funcaptcha_markers:
        if marker in body or marker in url:
            return {"type": "funcaptcha", "label": "Arkose/FunCaptcha", "evidence": marker}
    
    # ── reCAPTCHA ──
    if "recaptcha" in body or "g-recaptcha" in body:
        return {"type": "recaptcha", "label": "reCAPTCHA", "evidence": "recaptcha_detected"}
    
    # ── FunCaptcha iframe ──
    captcha_iframe = browser.evaluate("""
        (() => {
            const frames = document.querySelectorAll('iframe');
            for (const f of frames) {
                const src = (f.src || '').toLowerCase();
                const id = (f.id || '').toLowerCase();
                if (id === 'enforcementframe' || src.includes('funcaptcha') || src.includes('arkose')) {
                    const rect = f.getBoundingClientRect();
                    if (rect.width > 80 && rect.height > 50) return { src: f.src, id: f.id, visible: true };
                }
            }
            return null;
        })()
    """)
    if captcha_iframe:
        return {"type": "funcaptcha", "label": "FunCaptcha iframe", "evidence": captcha_iframe.get("src", "")}
    
    return None



def _handle_hsprotect_captcha(browser: CDPBrowser, timeout: float = AUTO_CAPTCHA_TIMEOUT) -> bool:
    """
    Handle hsprotect (HUMAN Security) CAPTCHA — press-and-hold, slider, and puzzle variants.
    
    Strategy:
    1. Detect challenge type (press_hold / slider / puzzle / unknown)
    2. For press-and-hold: simulate human-like approach with micro-movements during hold
    3. For slider: screenshot-based gap detection → human-like drag with easing
    4. For unknown/cross-origin: try multiple strategies with increasing aggression
    5. Each attempt uses a different approach to avoid pattern detection
    
    Key anti-detection techniques:
    - Mouse movement before touch (approach curve)
    - Micro-movements during press-and-hold (simulates human tremor)
    - Randomized hold duration (2.5-5.0s, not fixed)
    - Multiple input methods (CDP touch → CDP mouse → OS mouse)
    """
    logger.info("[CAPTCHA] Attempting hsprotect auto-solve (timeout=%.0fs)", timeout)
    deadline = time.monotonic() + timeout
    attempt = 0
    
    try_again_count = 0  # consecutive try-again counter, abort after 3
    while time.monotonic() < deadline:
        attempt += 1
        if _captcha_force_skip or _get_thread_state().get("captcha_skip", False):
            logger.info("[CAPTCHA] Force skip activated, bypassing hsprotect")
            return True
        _pa = _check_page_advanced(browser)
        if _pa:
            logger.info("[CAPTCHA] Page advanced to '%s', treating hsprotect as solved", _pa)
            return True
        captcha = _detect_captcha(browser)
        if not captcha or captcha["type"] != "hsprotect":
            logger.info("[CAPTCHA] hsprotect cleared after %d attempts!", attempt)
            return True
        
        remaining = deadline - time.monotonic()
        logger.info("[CAPTCHA] Attempt %d (%.0fs remaining)", attempt, remaining)
        
        # Locate the challenge element
        challenge_info = _locate_hsprotect_challenge(browser)
        ch_type = challenge_info.get("type", "unknown") if challenge_info else "unknown"
        logger.info("[CAPTCHA] Challenge type: %s", ch_type)
        

        # 无可交互元素检测：验证码页面但找不到可点击/拖拽的按钮 → 系统级阻碍
        if not challenge_info or ch_type == 'unknown':
            body_lower = browser.get_body_text().lower()
            _block_keywords = ['遇到问题', '遇到了问题', 'ran into a problem', 'something went wrong',
                               '帐户创建已被阻止', 'account creation blocked', '创建被阻止',
                               '请再试一次', 'try again', 'unusual activity', '异常活动']
            if any(kw in body_lower for kw in _block_keywords):
                logger.error('[CAPTCHA] No interactable element + blockage keywords detected → system blockage, aborting')
                return False
            # 没有阻碍关键词但也找不到按钮，继续尝试
            logger.info('[CAPTCHA] No interactable element found, but no blockage keywords — will retry')

        if ch_type == "press_hold":
            success = _hsprotect_press_hold(browser, challenge_info, attempt)
        elif ch_type == "slider":
            success = _hsprotect_slider(browser, challenge_info, attempt)
        elif ch_type == "puzzle":
            success = _hsprotect_puzzle(browser, challenge_info, attempt)
        else:
            success = _hsprotect_unknown(browser, attempt)
        
        if success:
            time.sleep(random.uniform(3.0, 5.0))
            captcha2 = _detect_captcha(browser)
            if not captcha2 or captcha2["type"] != "hsprotect":
                logger.info("[CAPTCHA] hsprotect cleared!")
                return True
            # Check for "please try again" — means click worked but site rejected
            body_text = browser.get_body_text().lower()
            if any(kw in body_text for kw in ['try again', '再试一次', 'try again later', '请重试']):
                try_again_count += 1
                logger.info("[CAPTCHA] Got 'try again' (%d/3) — site rejected the attempt", try_again_count)
                if try_again_count >= 3:
                    logger.error("[CAPTCHA] 3 consecutive 'try again' rejections → system blockage detected, aborting")
                    return False
                # Don't sleep long, just retry immediately with same coords
                time.sleep(2.0)
                continue
            logger.info("[CAPTCHA] Still present after strategy, retrying...")
        
        # Increased retry interval: 5-10s instead of 1.5-3s
        time.sleep(random.uniform(5.0, 10.0))
    
    logger.warning("[CAPTCHA] hsprotect auto-solve timed out after %d attempts", attempt)
    return False


def _locate_hsprotect_challenge(browser: CDPBrowser) -> dict | None:
    """
    Locate the hsprotect challenge element and determine its type.
    Tries multiple detection strategies for robustness.
    """
    info = browser.evaluate("""
        (() => {
            const frames = document.querySelectorAll('iframe');
            for (const f of frames) {
                const src = (f.src || '').toLowerCase();
                if (!src.includes('hsprotect') && !src.includes('fpt.live.com')) continue;
                const frameRect = f.getBoundingClientRect();
                if (frameRect.width < 50 || frameRect.height < 30) continue;
                
                try {
                    const doc = f.contentDocument || f.contentWindow.document;
                    if (!doc || !doc.body) throw 'cross_origin';
                    
                    const body = (doc.body.textContent || '').toLowerCase();
                    const html = (doc.body.innerHTML || '').toLowerCase();
                    
                    // Detect press-and-hold
                    const btns = doc.querySelectorAll('button, [role=button], div[role=button], span, div, a');
                    for (const btn of btns) {
                        const text = (btn.textContent || btn.innerText || '').toLowerCase().trim();
                        const ariaLabel = (btn.getAttribute('aria-label') || '').toLowerCase();
                        if (text.includes('press') || text.includes('hold') || text.includes('human') ||
                            text.includes('\u6309\u4f4f') || text.includes('\u8bc1\u660e') || text.includes('\u9a8c\u8bc1') ||
                            ariaLabel.includes('press') || ariaLabel.includes('hold') || ariaLabel.includes('human')) {
                            const r = btn.getBoundingClientRect();
                            if (r.width > 10 && r.height > 10) {
                                return {
                                    type: 'press_hold',
                                    x: frameRect.left + r.left + r.width / 2,
                                    y: frameRect.top + r.top + r.height / 2,
                                    w: r.width, h: r.height,
                                    frameX: frameRect.left, frameY: frameRect.top,
                                    frameW: frameRect.width, frameH: frameRect.height,
                                    src: f.src
                                };
                            }
                        }
                    }
                    
                    // Check by CSS class patterns
                    const pressEls = doc.querySelectorAll('[class*=press], [class*=hold], [class*=human], [class*=verify], [class*=challenge], [class*=captcha]');
                    for (const el of pressEls) {
                        const r = el.getBoundingClientRect();
                        if (r.width > 30 && r.height > 20) {
                            return {
                                type: 'press_hold',
                                x: frameRect.left + r.left + r.width / 2,
                                y: frameRect.top + r.top + r.height / 2,
                                w: r.width, h: r.height,
                                frameX: frameRect.left, frameY: frameRect.top,
                                frameW: frameRect.width, frameH: frameRect.height,
                                src: f.src
                            };
                        }
                    }
                    
                    // Detect slider
                    const sliders = doc.querySelectorAll('[class*=slider], [class*=Slider], [draggable], [role=slider], [class*=drag], [class*=puzzle], [class*=gap]');
                    if (sliders.length > 0 || body.includes('slider') || body.includes('drag') || body.includes('\u6ed1\u5757') || body.includes('\u7f3a\u53e3')) {
                        for (const el of sliders) {
                            const r = el.getBoundingClientRect();
                            if (r.width > 10 && r.height > 10) {
                                return {
                                    type: 'slider',
                                    handleX: frameRect.left + r.left + r.width / 2,
                                    handleY: frameRect.top + r.top + r.height / 2,
                                    handleW: r.width, handleH: r.height,
                                    frameX: frameRect.left, frameY: frameRect.top,
                                    frameW: frameRect.width, frameH: frameRect.height,
                                    src: f.src
                                };
                            }
                        }
                        return {
                            type: 'slider_unknown',
                            frameX: frameRect.left, frameY: frameRect.top,
                            frameW: frameRect.width, frameH: frameRect.height,
                            src: f.src
                        };
                    }
                    
                    // Detect puzzle
                    const canvases = doc.querySelectorAll('canvas');
                    const puzzleImgs = doc.querySelectorAll('img[class*=puzzle], img[class*=piece], img[class*=target], img[class*=match]');
                    if (canvases.length > 0 || puzzleImgs.length > 0 || body.includes('puzzle') || body.includes('match')) {
                        return {
                            type: 'puzzle',
                            frameX: frameRect.left, frameY: frameRect.top,
                            frameW: frameRect.width, frameH: frameRect.height,
                            src: f.src
                        };
                    }
                    
                    return {
                        type: 'unknown_accessible',
                        frameX: frameRect.left, frameY: frameRect.top,
                        frameW: frameRect.width, frameH: frameRect.height,
                        src: f.src
                    };
                } catch(e) {
                    return {
                        type: 'unknown_cross_origin',
                        frameX: frameRect.left, frameY: frameRect.top,
                        frameW: frameRect.width, frameH: frameRect.height,
                        x: frameRect.left + frameRect.width / 2,
                        y: frameRect.top + frameRect.height / 2,
                        src: f.src
                    };
                }
            }
            
            // Check parent page
            const parentBtns = document.querySelectorAll('[class*=press], [class*=hold], [class*=human], [class*=verify], [class*=challenge], [class*=captcha], [id*=human], [id*=challenge]');
            for (const btn of parentBtns) {
                const r = btn.getBoundingClientRect();
                if (r.width > 30 && r.height > 20) {
                    return {
                        type: 'press_hold',
                        x: r.left + r.width / 2, y: r.top + r.height / 2,
                        w: r.width, h: r.height,
                        src: 'parent'
                    };
                }
            }
            
            return null;
        })()
    """)
    
    if info:
        return info
    
    # Fallback: check by URL/text patterns
    body = browser.get_body_text().lower()
    url = browser.get_url().lower()
    if "hsprotect" in url or "press and hold" in body or "prove you're human" in body:
        fallback = browser.evaluate("""
            (() => {
                const candidates = document.querySelectorAll('[class*=challenge], [class*=captcha], [class*=verify], [class*=human], [id*=challenge], [id*=captcha], [id*=verify]');
                for (const el of candidates) {
                    const r = el.getBoundingClientRect();
                    if (r.width > 50 && r.height > 30) {
                        return {x: r.left + r.width/2, y: r.top + r.height/2, w: r.width, h: r.height};
                    }
                }
                return {x: window.innerWidth/2, y: window.innerHeight/2, w: 0, h: 0};
            })()
        """)
        if fallback:
            return {"type": "unknown", "x": fallback["x"], "y": fallback["y"],
                    "w": fallback.get("w", 0), "h": fallback.get("h", 0)}
    
    return None


def _hsprotect_press_hold(browser: CDPBrowser, info: dict, attempt: int) -> bool:
    """
    Handle press-and-hold challenge.
    
    Strategy (from outlook-register's proven approach):
    1. First attempt: CDP touch long-press with pointerType="touch" for 8 seconds
    2. Second attempt: Same but 10 seconds (longer hold)
    3. Third attempt: OS-level long-press as fallback
    
    Key insight: Clean press without tremor/micro-movements works best.
    hspress/PerimeterX expects a clean, steady touch.
    """
    btn_x = info.get("x", 0)
    btn_y = info.get("y", 0)
    logger.info("[CAPTCHA] Press-and-hold at (%.0f, %.0f) attempt=%d", btn_x, btn_y, attempt)
    
    if attempt == 1:
        # First try: 8-second clean touch press (proven approach)
        logger.info("[CAPTCHA] Strategy A: CDP touch long-press 8s (pointerType=touch)")
        try:
            _cdp_touch_long_press(browser, btn_x, btn_y, duration=8.0)
            return True
        except Exception as e:
            logger.warning("[CAPTCHA] Strategy A failed: %s", e)
    elif attempt == 2:
        # Second try: longer hold (10 seconds)
        logger.info("[CAPTCHA] Strategy B: CDP touch long-press 10s")
        try:
            _cdp_touch_long_press(browser, btn_x, btn_y, duration=10.0)
            return True
        except Exception as e:
            logger.warning("[CAPTCHA] Strategy B failed: %s", e)
    else:
        # 3rd+: longer CDP press (no OS-level fallback - clicks wrong window)
        duration = 12.0 + (attempt - 3) * 2.0
        logger.info("[CAPTCHA] Strategy C: CDP touch long-press %.0fs", duration)
        try:
            _cdp_touch_long_press(browser, btn_x, btn_y, duration=duration)
            return True
        except Exception as e:
            logger.warning("[CAPTCHA] Strategy C failed: %s", e)
    
    return False


def _cdp_touch_long_press(browser: CDPBrowser, x: float, y: float, duration: float = 8.0):
    """
    CDP touch long-press using pointerType="touch" on mouse events.
    This is the proven approach from outlook-register that bypasses PerimeterX/HUMAN Security.
    
    Key: Uses Input.dispatchMouseEvent with pointerType="touch" (NOT dispatchTouchEvent).
    No micro-movements — clean press is what hspress expects.
    """
    actual_duration = duration + random.uniform(-0.3, 0.5)
    actual_duration = max(6.0, actual_duration)  # Minimum 6 seconds
    
    # ── Viewport bounds checking ──
    viewport = browser.evaluate("JSON.stringify({w: window.innerWidth, h: window.innerHeight})")
    if viewport:
        import json as _json
        try:
            vp = _json.loads(viewport) if isinstance(viewport, str) else viewport
            vw, vh = vp.get("w", 1280), vp.get("h", 900)
            # Clamp coordinates to viewport with 10px margin
            x = max(10, min(x, vw - 10))
            y = max(10, min(y, vh - 10))
        except Exception:
            pass
    
    logger.info("[CAPTCHA] Touch long-press at (%.0f, %.0f) for %.1fs (pointerType=touch)", x, y, actual_duration)
    
    # Move to position first (natural approach)
    browser._send_cmd("Input.dispatchMouseEvent", {
        "type": "mouseMoved", "x": x, "y": y,
        "button": "none", "clickCount": 0,
    })
    time.sleep(random.uniform(0.2, 0.5))
    
    # Press with pointerType="touch" — this is the key trick
    browser._send_cmd("Input.dispatchMouseEvent", {
        "type": "mousePressed", "x": x, "y": y,
        "button": "left", "clickCount": 1,
        "pointerType": "touch",
    })
    
    # Clean hold — no movement, no tremor
    time.sleep(actual_duration)
    
    # Release
    browser._send_cmd("Input.dispatchMouseEvent", {
        "type": "mouseReleased", "x": x, "y": y,
        "button": "left", "clickCount": 1,
        "pointerType": "touch",
    })
    
    logger.info("[CAPTCHA] Touch long-press done (%.1fs)", actual_duration)


def _cdp_mouse_long_press(browser: CDPBrowser, x: float, y: float, duration: float = 8.0):
    """
    CDP mouse long-press with pointerType="touch".
    Fallback when _cdp_touch_long_press doesn't work.
    Uses the same pointerType trick but with mouse button events.
    """
    actual_duration = duration + random.uniform(-0.3, 0.5)
    actual_duration = max(6.0, actual_duration)
    
    logger.info("[CAPTCHA] Mouse long-press at (%.0f, %.0f) for %.1fs", x, y, actual_duration)
    
    browser._send_cmd("Input.dispatchMouseEvent", {
        "type": "mouseMoved", "x": x, "y": y,
        "button": "none", "clickCount": 0,
    })
    time.sleep(random.uniform(0.1, 0.3))
    
    browser._send_cmd("Input.dispatchMouseEvent", {
        "type": "mousePressed", "x": x, "y": y,
        "button": "left", "clickCount": 1,
        "pointerType": "touch",
    })
    
    # Clean hold — no tremor
    time.sleep(actual_duration)
    
    browser._send_cmd("Input.dispatchMouseEvent", {
        "type": "mouseReleased", "x": x, "y": y,
        "button": "left", "clickCount": 1,
        "pointerType": "touch",
    })
    
    logger.info("[CAPTCHA] Mouse long-press completed (%.1fs)", actual_duration)


def _hsprotect_slider(browser: CDPBrowser, info: dict, attempt: int) -> bool:
    """Handle slider CAPTCHA."""
    handle_x = info.get("handleX", 0)
    handle_y = info.get("handleY", 0)
    frame_x = info.get("frameX", 0)
    frame_y = info.get("frameY", 0)
    frame_w = info.get("frameW", 400)
    frame_h = info.get("frameH", 300)
    
    logger.info("[CAPTCHA] Slider at (%.0f, %.0f) frame=%.0fx%.0f", handle_x, handle_y, frame_w, frame_h)
    
    gap_offset_x = _find_slider_gap(browser, frame_x, frame_y, frame_w, frame_h)
    if gap_offset_x is None:
        gap_offset_x = frame_w * random.uniform(0.40, 0.75)
        logger.info("[CAPTCHA] Using estimated gap: %.0fpx (%.0f%%)", gap_offset_x, gap_offset_x / frame_w * 100)
    else:
        logger.info("[CAPTCHA] Detected gap: %.0fpx", gap_offset_x)
    
    end_x = handle_x + gap_offset_x
    end_y = handle_y + random.uniform(-2, 2)
    
    try:
        browser.touch_drag(handle_x, handle_y, end_x, end_y, duration_ms=random.randint(500, 1000))
    except Exception as e:
        logger.warning("[CAPTCHA] Touch drag failed: %s, trying mouse", e)
        try:
            browser.mouse_drag(handle_x, handle_y, end_x, end_y, duration_ms=random.randint(500, 1000))
        except Exception as e2:
            logger.warning("[CAPTCHA] Mouse drag also failed: %s", e2)
            return False
    
    return True


def _hsprotect_puzzle(browser: CDPBrowser, info: dict, attempt: int) -> bool:
    """Handle puzzle CAPTCHA (image matching)."""
    frame_x = info.get("frameX", 0)
    frame_y = info.get("frameY", 0)
    frame_w = info.get("frameW", 400)
    frame_h = info.get("frameH", 300)
    
    logger.info("[CAPTCHA] Puzzle at (%.0f, %.0f) size=%.0fx%.0f", frame_x, frame_y, frame_w, frame_h)
    
    try:
        ss_path = browser.screenshot("_puzzle_temp.png")
        from PIL import Image
        img = Image.open(ss_path)
        crop_x, crop_y = int(frame_x), int(frame_y)
        crop_w, crop_h = int(frame_w), int(frame_h)
        if crop_x + crop_w <= img.width and crop_y + crop_h <= img.height:
            puzzle_img = img.crop((crop_x, crop_y, crop_x + crop_w, crop_y + crop_h))
            pw, ph = puzzle_img.size
            piece_x = frame_x + pw * 0.15
            piece_y = frame_y + ph * 0.5
            target_x = frame_x + pw * 0.75
            target_y = frame_y + ph * 0.5
            logger.info("[CAPTCHA] Puzzle: piece=(%.0f,%.0f) target=(%.0f,%.0f)", piece_x, piece_y, target_x, target_y)
            try:
                browser.touch_drag(piece_x, piece_y, target_x, target_y, duration_ms=random.randint(600, 1200))
            except Exception:
                browser.mouse_drag(piece_x, piece_y, target_x, target_y, duration_ms=random.randint(600, 1200))
        try:
            os.remove(ss_path)
        except:
            pass
        return True
    except ImportError:
        logger.warning("[CAPTCHA] PIL not available for puzzle analysis")
    except Exception as e:
        logger.warning("[CAPTCHA] Puzzle analysis failed: %s", e)
    
    start_x = frame_x + frame_w * 0.15
    start_y = frame_y + frame_h * 0.5
    end_x = frame_x + frame_w * 0.75
    end_y = start_y
    try:
        browser.touch_drag(start_x, start_y, end_x, end_y, duration_ms=random.randint(600, 1200))
        return True
    except Exception:
        return False


def _hsprotect_unknown(browser: CDPBrowser, attempt: int) -> bool:
    """Handle unknown hsprotect challenge type with escalating strategies."""
    logger.info("[CAPTCHA] Unknown challenge type, attempt=%d", attempt)
    
    iframe_info = browser.evaluate("""
        (() => {
            const frames = document.querySelectorAll('iframe');
            for (const f of frames) {
                const src = (f.src || '').toLowerCase();
                if ((src.includes('hsprotect') || src.includes('fpt.live.com')) && f.offsetWidth > 50 && f.offsetHeight > 30) {
                    const r = f.getBoundingClientRect();
                    return {x: r.left + r.width/2, y: r.top + r.height/2, w: r.width, h: r.height, src: f.src};
                }
            }
            const els = document.querySelectorAll('[class*=challenge], [class*=captcha], [class*=verify], [class*=human], [id*=challenge], [id*=captcha]');
            for (const el of els) {
                const r = el.getBoundingClientRect();
                if (r.width > 30 && r.height > 20) {
                    return {x: r.left + r.width/2, y: r.top + r.height/2, w: r.width, h: r.height, src: 'parent'};
                }
            }
            return null;
        })()
    """)
    
    if not iframe_info:
        logger.warning("[CAPTCHA] Cannot locate challenge element")
        return False
    
    btn_x = iframe_info["x"]
    btn_y = iframe_info["y"]
    
    # CDP-only: no OS-level fallback (pyautogui clicks whatever window is in front)
    if attempt <= 2:
        duration = 8.0 if attempt == 1 else 10.0
        logger.info("[CAPTCHA] Unknown: CDP touch long-press %.0fs (attempt %d)", duration, attempt)
        try:
            _cdp_touch_long_press(browser, btn_x, btn_y, duration=duration)
            return True
        except Exception as e:
            logger.warning("[CAPTCHA] Failed: %s", e)
    else:
        # 3rd+ attempt: longer CDP press with slight coord variation
        duration = 12.0 + (attempt - 3) * 2.0
        logger.info("[CAPTCHA] Unknown: CDP touch long-press %.0fs (attempt %d)", duration, attempt)
        try:
            _cdp_touch_long_press(browser, btn_x, btn_y, duration=duration)
            return True
        except Exception as e:
            logger.warning("[CAPTCHA] Failed: %s", e)
    
    return False


def _wait_for_manual_captcha(browser: CDPBrowser, timeout: float = None) -> bool:
    """
    Wait for user to manually solve the CAPTCHA.
    Polls every 3 seconds to check if the challenge is cleared.
    Supports pause: when paused, blocks until resumed then re-checks.
    """
    if timeout is None:
        try:
            timeout = MANUAL_CAPTCHA_TIMEOUT_HEADLESS if browser.config.headless else MANUAL_CAPTCHA_TIMEOUT
        except Exception:
            timeout = MANUAL_CAPTCHA_TIMEOUT
    logger.info("[CAPTCHA] Waiting for manual solve (timeout=%.0fs)", timeout)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(3)
        # ── 并发安全: 读取线程级状态 ──
        state = _get_thread_state()
        is_paused = state.get("paused", False) or _registration_paused
        should_stop = state.get("stop", False) or _registration_stop
        should_skip = state.get("captcha_skip", False) or _captcha_force_skip
        # 支持暂停：暂停时阻塞，恢复后继续检测
        if is_paused:
            logger.info("[CAPTCHA] ⏸ 暂停中，等待恢复...")
            while True:
                state = _get_thread_state()
                is_paused = state.get("paused", False) or _registration_paused
                should_stop = state.get("stop", False) or _registration_stop
                should_skip = state.get("captcha_skip", False) or _captcha_force_skip
                if not is_paused: break
                if should_stop: return False
                if should_skip: return True
                time.sleep(0.5)
            logger.info("[CAPTCHA] ▶ 已恢复，继续检测...")
        if should_stop:
            return False
        if should_skip:
            logger.info("[CAPTCHA] Force skip activated, bypassing manual wait")
            return True
        _pa = _check_page_advanced(browser)
        if _pa:
            logger.info("[CAPTCHA] Page advanced to '%s', treating as manually solved", _pa)
            return True
        captcha = _detect_captcha(browser)
        if not captcha or captcha["type"] != "hsprotect":
            logger.info("[CAPTCHA] Manually solved!")
            return True
        remaining = int(deadline - time.monotonic())
        logger.info("[CAPTCHA] Still waiting... (%ds remaining)", remaining)
    logger.warning("[CAPTCHA] Manual solve timed out")
    return False



def _find_slider_gap(browser: CDPBrowser, frame_x: float, frame_y: float, frame_w: float, frame_h: float) -> float | None:
    """
    Find the gap position in a slider CAPTCHA using screenshot analysis.
    Returns the horizontal offset from the slider start to the gap.
    """
    try:
        from PIL import Image
        import io as _io
        # Take screenshot and crop to CAPTCHA area
        ss_path = browser.screenshot("_captcha_temp.png")
        img = Image.open(ss_path)
        # Crop to the puzzle area (above the slider track)
        crop_x = int(frame_x)
        crop_y = int(frame_y)
        crop_w = int(frame_w)
        crop_h = int(frame_h - 60)  # exclude slider track at bottom
        if crop_x + crop_w > img.width or crop_y + crop_h > img.height:
            return None
        captcha_img = img.crop((crop_x, crop_y, crop_x + crop_w, crop_y + crop_h))
        
        # Find the gap: look for a vertical strip with high contrast/edges
        # The gap usually appears as a darker or differently-colored vertical strip
        pixels = captcha_img.load()
        w, h = captcha_img.size
        if w < 50 or h < 50:
            return None
        
        # Calculate column brightness variance
        # The gap column will have higher variance than surrounding columns
        col_scores = []
        for x in range(10, w - 10):
            brightnesses = []
            for y in range(h // 4, h * 3 // 4):  # sample middle portion
                r, g, b = pixels[x, y][:3]
                brightnesses.append(r * 0.299 + g * 0.587 + b * 0.114)
            if brightnesses:
                mean_b = sum(brightnesses) / len(brightnesses)
                variance = sum((b - mean_b) ** 2 for b in brightnesses) / len(brightnesses)
                col_scores.append((x, variance))
        
        if not col_scores:
            return None
        
        # Find the column with highest variance (the gap edge)
        col_scores.sort(key=lambda x: x[1], reverse=True)
        gap_x = col_scores[0][0]
        
        # Clean up temp file
        try: os.remove(ss_path)
        except: pass
        
        return float(gap_x)
    except ImportError:
        logger.info("[CAPTCHA] PIL not available for image analysis")
        return None
    except Exception as e:
        logger.warning("[CAPTCHA] Gap detection failed: %s", e)
        return None


def _handle_funcaptcha(browser: CDPBrowser, timeout: float = AUTO_CAPTCHA_TIMEOUT) -> bool:
    logger.info("[CAPTCHA] Attempting FunCaptcha handling")
    deadline = time.monotonic() + timeout
    in_frame = browser.evaluate("""
        (() => {
            const frames = document.querySelectorAll('iframe');
            for (const f of frames) {
                if (f.id === 'enforcementFrame' || f.src.includes('funcaptcha') || f.src.includes('arkose'))
                    return { found: true, src: f.src };
            }
            return { found: false };
        })()
    """)
    if not in_frame or not in_frame.get("found"):
        logger.warning("[CAPTCHA] FunCaptcha iframe not found")
        return False
    browser.evaluate("""
        (() => {
            const btns = document.querySelectorAll('button, [role="button"]');
            for (const btn of btns) {
                const rect = btn.getBoundingClientRect();
                if (rect.width > 20 && rect.height > 20) { btn.click(); return true; }
            }
            return false;
        })()
    """)
    while time.monotonic() < deadline:
        confirm = browser.evaluate("""
            (() => {
                const keywords = ['click again', 'continue', 'verify', 'confirm', 'submit', 'next'];
                const btns = document.querySelectorAll('button, [role="button"]');
                for (const btn of btns) {
                    if (!btn.offsetParent && !btn.offsetWidth) continue;
                    const text = (btn.innerText || btn.textContent || '').toLowerCase().trim();
                    for (const kw of keywords) {
                        if (text.includes(kw)) { btn.click(); return { clicked: true, text }; }
                    }
                }
                return { clicked: false };
            })()
        """)
        if confirm and confirm.get("clicked"):
            logger.info("[CAPTCHA] FunCaptcha confirm clicked: %s", confirm.get("text"))
            time.sleep(2)
            new_state = _detect_page_state(browser)
            if new_state not in ("captcha", "unknown"):
                return True
        time.sleep(1)
    return False


def _handle_post_challenge(browser: CDPBrowser, account: OutlookAccount) -> str:
    logger.info("[POST] Handling post-challenge pages")
    consent_url_count = 0  # Consent/Update 页面连续出现次数
    max_consent_retries = 5
    profile_fill_count = 0  # Guard against repeated profile filling
    max_profile_fills = 2
    # Increased from 10 to 40 steps (40 seconds) for slower post-captcha transitions
    for step in range(40):
        # 支持暂停
        if _registration_stop or _get_thread_state().get("stop", False): return "stopped"
        while _registration_paused or _get_thread_state().get("paused", False):
            time.sleep(0.5)
            if _registration_stop or _get_thread_state().get("stop", False): return "stopped"
        state = _detect_page_state(browser)
        logger.info("[POST] Step %d, state: %s", step + 1, state)
        if state == "account_home":
            return "account_home"

        # 检测 Consent/Update 页面（URL 匹配，body 可能为 0）
        url_now = browser.get_url()
        if "account.live.com/consent" in url_now.lower():
            consent_url_count += 1
            logger.info("[POST] Consent/Update 页面 (第%d次), 尝试点击确认...", consent_url_count)
            clicked = browser.evaluate("""(() => {
                function _vis(el) {
                    if (!el) return false;
                    const s = window.getComputedStyle(el);
                    if (s.display==='none'||s.visibility==='hidden'||Number(s.opacity||1)===0) return false;
                    return el.offsetWidth>0||el.offsetHeight>0||el.getClientRects().length>0;
                }
                const btns = document.querySelectorAll('button, input[type=submit], [role=button]');
                for (const b of btns) {
                    const t = (b.textContent || b.value || '').toLowerCase().trim();
                    if (!_vis(b)) continue;
                    if (t.includes('accept')||t.includes('agree')||t.includes('allow')||t.includes('continue')||t.includes('next')||t.includes('ok')||t.includes('yes')||t.includes('submit')||t.includes('确认')||t.includes('同意')||t.includes('接受')||t.includes('继续'))
                    { b.click(); return 'consent:' + t.substring(0,30); }
                }
                for (const id of ['idSIButton9','acceptButton','nextButton','primaryButton']) {
                    const el = document.getElementById(id);
                    if (el && _vis(el)) { el.click(); return 'consent-id:' + id; }
                }
                return null;
            })()""")
            if clicked:
                logger.info("[POST] Consent 已点击: %s", clicked)
            elif consent_url_count >= max_consent_retries:
                logger.warning("[POST] Consent 页面重试 %d 次仍失败, 尝试重新导航", max_consent_retries)
                browser.navigate("https://signup.live.com/signup", wait_for_load=True, timeout=20)
                consent_url_count = 0
            time.sleep(3); continue

        if state == "privacy_notice":
            url_now = browser.get_url()
            title_now = browser.evaluate("document.title") or ""
            logger.info("[POST] privacy_notice page: URL=%s title=%s", url_now[:100], title_now[:80])
            clicked = browser.evaluate("""(() => {
                function isVisible(el) {
                    if (!el) return false;
                    const s = window.getComputedStyle(el);
                    if (s.display === 'none' || s.visibility === 'hidden' || Number(s.opacity) === 0) return false;
                    return el.offsetWidth > 0 || el.offsetHeight > 0 || el.getClientRects().length > 0;
                }
                // 策略1: 按文本匹配 agree/continue/同意 按钮
                const btns = document.querySelectorAll('button, input[type="submit"], [role="button"]');
                for (const b of btns) {
                    const t = (b.textContent||b.value||'').toLowerCase();
                    if (t.includes('agree')||t.includes('continue')||t.includes('同意')||t.includes('accept')||t.includes('接受')||t==='否'||t==='no') {
                        b.click(); return 'text:' + t.trim().substring(0,30);
                    }
                }
                // 策略2: 按 ID 匹配已知的确认按钮
                const idBtns = ['nextButton', 'idSIButton9', 'idBtn_Back', 'acceptButton', 'primaryButton'];
                for (const id of idBtns) {
                    const el = document.getElementById(id);
                    if (el && isVisible(el)) { el.click(); return 'id:' + id; }
                }
                // 策略3: 点击 type=submit 的按钮
                const submitBtns = document.querySelectorAll('button[type="submit"], input[type="submit"]');
                for (const b of submitBtns) {
                    if (isVisible(b)) { b.click(); return 'submit:' + (b.textContent||b.value||'').trim().substring(0,30); }
                }
                // 策略4: 点击第一个可见的非取消/非拒绝按钮（隐私偏好页优先"否"）
                const pageText = document.body ? document.body.innerText.toLowerCase() : '';
                const isYesNoPage = pageText.includes('是否希望') || pageText.includes('是否将') || pageText.includes('隐私偏好');
                for (const b of btns) {
                    const t = (b.textContent||b.value||'').toLowerCase();
                    if (!isVisible(b)) continue;
                    if (t.includes('cancel') || t.includes('reject') || t.includes('拒绝') || t.includes('close') || t.includes('关闭')) continue;
                    if (isYesNoPage && (t === '是' || t === 'yes')) continue;  // 跳过"是"按钮
                    b.click(); return 'fallback:' + t.trim().substring(0,30);
                }
                // 最后兜底：如果只剩"是"按钮
                for (const b of btns) {
                    const t = (b.textContent||b.value||'').toLowerCase();
                    if (isVisible(b) && (t === '是' || t === 'yes')) {
                        b.click(); return 'fallback-yes:' + t.trim().substring(0,30);
                    }
                }
                // 策略5: 尝试在 iframe 中查找按钮
                const frames = document.querySelectorAll('iframe');
                for (const f of frames) {
                    try {
                        const doc = f.contentDocument || f.contentWindow.document;
                        if (!doc) continue;
                        const fbtns = doc.querySelectorAll('button, input[type="submit"]');
                        for (const b of fbtns) {
                            const t = (b.textContent||b.value||'').toLowerCase();
                            if (t.includes('agree')||t.includes('continue')||t.includes('同意')||t.includes('accept')) {
                                b.click(); return 'iframe:' + t.trim().substring(0,30);
                            }
                        }
                        // Try nextButton in iframe
                        const next = doc.getElementById('nextButton');
                        if (next) { next.click(); return 'iframe:nextButton'; }
                    } catch(e) {}
                }
                return null;
            })()""")
            if clicked:
                logger.info("[POST] privacy_notice clicked: %s", clicked)
            else:
                logger.warning("[POST] privacy_notice: no clickable button found")
            time.sleep(3); continue
        if state == "account_notice":
            browser.evaluate("""(() => { const b = document.getElementById('id__0')||document.getElementById('idSIButton9');
                if(b){b.click();return true;} const btns=document.querySelectorAll('button');
                for(const x of btns){if((x.textContent||'').toLowerCase()==='ok'){x.click();return true;}}
                return false; })()""")
            time.sleep(3); continue
        if state == "stay_signed_in":
            browser.evaluate("""(() => { const b = document.getElementById('idBtn_Back');
                if(b){b.click();return true;} const btns=document.querySelectorAll('button');
                for(const x of btns){const t=(x.textContent||'').toLowerCase();
                if(t==='no'||t==='否'){x.click();return true;}} return false; })()""")
            time.sleep(3); continue
        if state == "add_recovery":
            browser.evaluate("""(() => { const btns = document.querySelectorAll('button,a');
                for(const b of btns){const t=(b.textContent||'').toLowerCase();
                if(t.includes('skip')||t.includes('暂不')||t.includes('跳过')||t.includes('not now')){b.click();return true;}}
                return false; })()""")
            time.sleep(3); continue
        if state == "passkey_prompt":
            logger.info("[POST] passkey_prompt detected, dismissing Windows WebAuthn system dialog...")
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # Windows 通行密钥弹窗是系统级弹窗（WebAuthn/Windows Hello），
            # JS/CDP 完全看不到它。必须用 Win32 API 查找弹窗窗口并发送关闭消息。
            # 绝对不能盲目发 SendInput 按键，否则会发给 Chrome 导致关闭浏览器！
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            dismissed = os_dismiss_webauthn_dialog(timeout=5.0)
            if dismissed:
                logger.info("[POST] WebAuthn dialog dismissed via Win32 API")
            else:
                logger.warning("[POST] WebAuthn dialog dismiss failed or not found, continuing...")
            time.sleep(1)
            # 关闭系统弹窗后，再尝试点击网页上的"下一步"/"跳过"按钮
            clicked = browser.evaluate("""(() => { const btns = document.querySelectorAll('button,a,[role=button],input[type=submit]');
                for(const b of btns){const t=(b.textContent||b.value||'').toLowerCase().trim();
                if(t==='next'||t==='下一步'||t==='继续'||t==='sign in'||t==='登录'){b.click();return 'next:'+t.substring(0,30);}}
                for(const b of btns){const t=(b.textContent||b.value||'').toLowerCase().trim();
                if(t.includes('skip')||t.includes('not now')||t.includes('暂不')||t.includes('跳过')||t.includes('以后再说')||t.includes('稍后')||t.includes('later')){b.click();return 'skip:'+t.substring(0,30);}}
                const idBtn = document.getElementById('idSIButton9');
                if(idBtn){idBtn.click();return 'idSIButton9';}
                for(const b of btns){const t=(b.textContent||b.value||'').toLowerCase().trim();
                if(t==='cancel'||t==='close'||t==='取消'||t==='关闭'){b.click();return 'cancel:'+t.substring(0,30);}}
                return null; })()""")
            if clicked:
                logger.info("[POST] passkey_prompt page button clicked: %s", clicked)
            else:
                logger.info("[POST] 系统弹窗已关闭，等待页面变化...")
            time.sleep(3); continue

        # ── Windows 安全中心通行密钥弹窗（OS级对话框） ──
        # 微软在注册/登录流程中会弹出 OS 级别的"选择保存通行密钥的位置"弹窗
        body_post = browser.get_body_text().lower()
        if any(kw in body_post for kw in ["选择保存通行密钥", "windows 安全中心", "windows security",
                                            "保存通行密钥的位置", "passkey setup"]):
            logger.info("[POST] 检测到 Windows 安全中心通行密钥弹窗，用 Win32 API 关闭...")
            # 同上：用 Win32 API 精准找到弹窗并发送关闭消息，不用 SendInput
            dismissed = os_dismiss_webauthn_dialog(timeout=5.0)
            if dismissed:
                logger.info("[POST] Windows Security dialog dismissed via Win32 API")
            else:
                logger.warning("[POST] Windows Security dialog dismiss failed or not found, continuing...")
            time.sleep(1)
            # 关闭弹窗后，尝试点击网页上的按钮继续
            clicked = browser.evaluate("""(() => {
                const btns = document.querySelectorAll('button, [role=button], input[type=submit]');
                for (const b of btns) {
                    const t = (b.textContent || b.value || '').toLowerCase().trim();
                    if (!t) continue;
                    if (t === 'next' || t === '下一步' || t === 'continue' || t === '继续' || t === 'sign in' || t === '登录') {
                        b.click(); return 'next:' + t;
                    }
                }
                for (const b of btns) {
                    const t = (b.textContent || b.value || '').toLowerCase().trim();
                    if (!t) continue;
                    if (t === '取消' || t === 'cancel' || t === 'close' || t.includes('关闭')) {
                        b.click(); return 'cancel:' + t;
                    }
                    if (t.includes('skip') || t.includes('no thanks') || t.includes('暂不') || t.includes('later')) {
                        b.click(); return 'fallback:' + t;
                    }
                }
                const idBtn = document.getElementById('idSIButton9');
                if (idBtn) { idBtn.click(); return 'idSIButton9'; }
                return null;
            })()""")
            if clicked:
                logger.info("[POST] 通行密钥弹窗已处理: %s", clicked)
            else:
                logger.info("[POST] 系统弹窗已关闭，等待页面变化...")
            time.sleep(3); continue
        if state == "fill_profile":
            # 返回主状态机处理，避免在 post_challenge 中重复填写
            logger.info("[POST] 检测到 fill_profile，返回主状态机处理")
            return "fill_profile"
        # ── 关键修复: fill_username/fill_password 应返回主状态机，不应在此处处理 ──
        if state == "fill_username":
            logger.info("[POST] 检测到 fill_username，返回主状态机处理")
            return "fill_username"
        if state == "fill_password":
            logger.info("[POST] 检测到 fill_password，返回主状态机处理")
            return "fill_password"
        if state == "blocked":
            logger.error("[POST] Account creation blocked by Microsoft")
            return "blocked"
        if state == "proxy_error":
            logger.error("[POST] Proxy error page detected")
            return "proxy_error"
        if state == "captcha":
            captcha = _detect_captcha(browser)
            if captcha:
                logger.info("[POST] CAPTCHA detected: %s", captcha['type'])
                if captcha['type'] == 'hsprotect':
                    if _handle_hsprotect_captcha(browser):
                        time.sleep(3); continue
                elif captcha['type'] == 'funcaptcha':
                    if _handle_funcaptcha(browser):
                        time.sleep(3); continue
                # Manual fallback
                logger.info("[POST] Waiting for manual CAPTCHA solve...")
                _wait_for_manual_captcha(browser)
                time.sleep(3); continue
            else:
                logger.info("[POST] State=captcha but no captcha detected, waiting...")
                time.sleep(3); continue
        if state == "microsoft_problem":
            return "microsoft_problem"
        
        # ── NEW: handle unknown/loading states more gracefully ──
        url = browser.get_url().lower()
        body = browser.get_body_text().lower()
        
        # Detect if page is still loading
        ready = browser.evaluate("document.readyState")
        if ready not in ("complete", "interactive"):
            logger.info("[POST] Page still loading (readyState=%s), waiting...", ready)
            time.sleep(2); continue

        # ── 关键修复: body 为空时不盲目点击按钮 ──
        # signup.live.com 是 SPA，body 为空说明 JS 未渲染，点击按钮无意义
        if len(body) < 50:
            logger.info("[POST] Body 为空(长度=%d)，SPA 未渲染，等待3秒...", len(body))
            time.sleep(3); continue

        # If on a Microsoft domain, keep trying (page may be in transition)
        if any(domain in url for domain in ["login.live.com", "signup.live.com", "account.microsoft.com", "outlook.live.com", "live.com"]):
            # Try clicking any obvious next/continue button
            clicked = browser.evaluate("""(() => {
                function _vis(el) {
                    if (!el) return false;
                    const s = window.getComputedStyle(el);
                    if (s.display==='none'||s.visibility==='hidden'||Number(s.opacity)===0) return false;
                    return el.offsetWidth>0||el.offsetHeight>0||el.getClientRects().length>0;
                }
                const keywords = ['next', 'continue', 'agree', 'accept', 'ok', 'got it', 'done', 'yes', 'submit',
                    '下一步', '继续', '同意', '接受', '确定', '完成', '好的', '拒绝并退出', '否'];
                const btns = document.querySelectorAll('button, input[type=submit], [role=button], a.btn');
                for (const b of btns) {
                    if (!_vis(b)) continue;
                    const text = (b.textContent || b.value || '').toLowerCase().trim();
                    for (const kw of keywords) {
                        if (text === kw || text.includes(kw)) { b.click(); return text; }
                    }
                }
                // ID-based fallback
                const idBtns = ['nextButton', 'idSIButton9', 'acceptButton', 'idBtn_Back'];
                for (const id of idBtns) {
                    const el = document.getElementById(id);
                    if (el && _vis(el)) { el.click(); return 'id:' + id; }
                }
                return null;
            })()""")
            if clicked:
                logger.info("[POST] Auto-clicked button: %s", clicked)
                time.sleep(3); continue
            # If URL changed from signup to something else, might be success
            if "account.microsoft.com" in url or "outlook.live.com" in url:
                logger.info("[POST] Detected account.microsoft.com or outlook URL, treating as success")
                return "account_home"
            time.sleep(2); continue
        
        # Unknown state on unknown domain - check URL for success indicators
        # 排除 login.microsoft.com，因为那是登录页面，不是账户主页
        success_domains = ["account.microsoft.com", "outlook.live.com", "msn.com", "bing.com"]
        is_login_page = "login.microsoft.com" in url or "login.live.com" in url
        if not is_login_page and any(domain in url for domain in success_domains):
            logger.info("[POST] On Microsoft domain (%s), treating as success", url[:80])
            return "account_home"
        
        time.sleep(2)
    return "timeout"


def _fill_username(browser: CDPBrowser, account: OutlookAccount) -> bool:
    """Fill email/username on the new Microsoft signup page.
    
    New flow (2024+): Single email input field, enter full email address.
    Old flow: Username field + domain dropdown.
    """
    logger.info("[FILL] Filling email: %s", account.email)
    
    # Detect if this is old flow (has domain dropdown) or new flow (single email input)
    has_domain_dropdown = False
    for dd_selector in FIELD_SELECTORS["domain_dropdown"]:
        try:
            nid = browser.query_selector(dd_selector)
            if nid and browser.is_element_visible(nid):
                has_domain_dropdown = True
                break
        except Exception:
            continue
    
    if has_domain_dropdown:
        # Old flow: username field + domain dropdown
        element, selector = _find_first_visible(browser, FIELD_SELECTORS["username"])
        if not element:
            logger.error("[FILL] Username field not found")
            return False
        _type_into_element(browser, element, account.username)
        time.sleep(random.uniform(0.3, 0.7))
        for dd_selector in FIELD_SELECTORS["domain_dropdown"]:
            try:
                nid = browser.query_selector(dd_selector)
                if nid and browser.is_element_visible(nid):
                    domain_text = "@hotmail.com" if account.provider == "hotmail" else "@outlook.com"
                    _select_dropdown(browser, dd_selector, domain_text)
                    break
            except Exception:
                continue
    else:
        # New flow: single email input field
        email_input = None
        used_selector = ""
        for sel in FIELD_SELECTORS["username"]:
            try:
                nid = browser.query_selector(sel)
                if nid and browser.is_element_visible(nid):
                    email_input = nid
                    used_selector = sel
                    break
            except Exception:
                continue
        if not email_input:
            # Fallback: try any visible text input that looks like email
            logger.warning("[FILL] Standard selectors failed, trying fallback...")
            fallback_js = """
            (() => {
                const inputs = document.querySelectorAll('input[type="text"], input[type="email"], input:not([type])');
                for (const el of inputs) {
                    if (el.offsetParent !== null && el.offsetWidth > 100) {
                        const name = (el.name || '').toLowerCase();
                        const id = (el.id || '').toLowerCase();
                        const placeholder = (el.placeholder || '').toLowerCase();
                        const aria = (el.getAttribute('aria-label') || '').toLowerCase();
                        if (name.includes('email') || name.includes('user') || id.includes('email') || id.includes('user') ||
                            placeholder.includes('@') || placeholder.includes('email') || aria.includes('email') || aria.includes('user')) {
                            return {found: true, selector: '#' + el.id || 'input[name="' + el.name + '"]',
                                    tag: el.tagName, type: el.type, name: el.name, id: el.id, placeholder: el.placeholder};
                        }
                    }
                }
                return {found: false};
            })()
            """
            fallback_result = browser.evaluate(fallback_js)
            if fallback_result and fallback_result.get('found'):
                fb_sel = fallback_result.get('selector', '')
                logger.info("[FILL] Fallback found: %s (name=%s, id=%s)", fb_sel, fallback_result.get('name'), fallback_result.get('id'))
                try:
                    nid = browser.query_selector(fb_sel)
                    if nid and browser.is_element_visible(nid):
                        email_input = nid
                        used_selector = fb_sel
                except Exception:
                    pass
        if not email_input:
            # Last resort: dump all visible inputs for debugging
            dump_js = """
            (() => {
                const inputs = document.querySelectorAll('input');
                const result = [];
                for (const el of inputs) {
                    if (el.offsetParent !== null) {
                        result.push({tag: el.tagName, type: el.type, name: el.name, id: el.id,
                                    placeholder: el.placeholder, value: el.value ? '(has value)' : '',
                                    width: el.offsetWidth, height: el.offsetHeight});
                    }
                }
                return result;
            })()
            """
            visible_inputs = browser.evaluate(dump_js)
            logger.error("[FILL] No email input found. Visible inputs: %s", json.dumps(visible_inputs, ensure_ascii=False))
            return False
        rect = browser.get_element_rect(email_input)
        if not rect:
            logger.error("[FILL] Email input rect not found")
            return False
        logger.info("[FILL] Found email input via: %s", used_selector)
        # Focus the input
        browser.focus_element(used_selector)
        time.sleep(random.uniform(0.2, 0.5))
        # Type full email address
        browser.type_text(account.email, delay_ms=random.randint(40, 80))
        # Dispatch change event for React
        escaped_sel = used_selector.replace("'", "\\'")
        browser.evaluate(f"""
            (() => {{
                const el = document.querySelector('{escaped_sel}');
                if (el) {{
                    el.dispatchEvent(new Event('change', {{bubbles: true}}));
                    el.dispatchEvent(new Event('blur', {{bubbles: true}}));
                }}
            }})()
        """)
        time.sleep(random.uniform(0.3, 0.7))
    
    _click_next(browser)
    time.sleep(random.uniform(1, 2))
    for _ in range(20):
        pwd_element, _ = _find_first_visible(browser, FIELD_SELECTORS["password"])
        if pwd_element:
            return True
        body = browser.get_body_text().lower()
        if any(m in body for m in ("isn't available", "already a microsoft account", "try another", "\u4e0d\u53ef\u7528", "\u5df2\u88ab\u4f7f\u7528")):
            logger.warning("[FILL] Email unavailable: %s", account.email)
            return False
        time.sleep(0.5)
    return False


def _fill_password(browser: CDPBrowser, password: str) -> bool:
    logger.info("[FILL] Filling password: %s", password)
    element, sel = _find_first_visible(browser, FIELD_SELECTORS["password"])
    if not element:
        return False
    _type_into_element(browser, element, password)
    # 确保 React 框架识别到输入值
    escaped_sel = sel.replace("'", "\\'")
    browser.evaluate(f"""
        (() => {{
            const el = document.querySelector('{escaped_sel}');
            if (el) {{
                el.dispatchEvent(new Event('change', {{bubbles: true}}));
                el.dispatchEvent(new Event('blur', {{bubbles: true}}));
            }}
        }})()
    """)
    time.sleep(random.uniform(0.5, 1.0))
    _click_next(browser)
    time.sleep(random.uniform(1, 2))
    ms_error_retries = 0
    for _ in range(30):  # 15秒等待
        # 检测 Chrome 是否已崩溃
        try:
            browser.get_url()
        except Exception:
            logger.warning("[FILL] Chrome 已崩溃，退出等待")
            return False
        state = _detect_page_state(browser)
        if state in ("fill_profile", "fill_birthdate", "captcha", "privacy_notice",
                     "account_notice", "stay_signed_in", "add_recovery", "passkey_prompt"):
            return True
        if state == "microsoft_problem":
            ms_error_retries += 1
            if ms_error_retries >= 3:
                logger.warning("[FILL] microsoft_problem 重试 %d 次仍失败,放弃", ms_error_retries)
                return False
            logger.info("[FILL] microsoft_problem 页面,等待后重试 (%d/3)", ms_error_retries)
            time.sleep(3)
            _click_next(browser)
            time.sleep(1)
            continue
        time.sleep(0.5)
    return False


def _read_auto_country(browser: CDPBrowser) -> str:
    """读取页面上网站根据代理IP自动选择的国家（在注册流程的profile/birthdate页面调用）"""
    country = browser.evaluate("""
        (() => {
            // 方法1: select 元素
            const sels = document.querySelectorAll('select');
            for (const s of sels) {
                if (s.offsetParent !== null && s.options.length > 1) {
                    const sel = s.options[s.selectedIndex];
                    if (sel && sel.text && sel.text.trim()) return sel.text.trim();
                }
            }
            // 方法2: Fluent UI dropdown button (id 含 country/region)
            const btns = document.querySelectorAll('button, [role="combobox"]');
            for (const b of btns) {
                const id = (b.id || '').toLowerCase();
                const name = (b.getAttribute('name') || '').toLowerCase();
                if ((id.includes('country') || id.includes('region') || name.includes('country'))
                    && b.offsetParent !== null) {
                    const text = (b.textContent || '').trim();
                    if (text && text.length < 50) return text;
                }
            }
            return '';
        })()
    """)
    if country:
        logger.info("[PROXY VERIFY] 网站自动选择的国家: %s", country)
    else:
        logger.warning("[PROXY VERIFY] 未能读取自动选择的国家")
    return country or ""


def _fill_profile_fields(browser: CDPBrowser, account: OutlookAccount) -> bool:
    logger.info("[FILL] Filling profile: %s %s", account.first_name, account.last_name)
    fn, _ = _find_first_visible(browser, FIELD_SELECTORS["first_name"])
    if fn:
        _type_into_element(browser, fn, account.first_name)
        time.sleep(random.uniform(0.2, 0.5))
    ln, _ = _find_first_visible(browser, FIELD_SELECTORS["last_name"])
    if ln:
        _type_into_element(browser, ln, account.last_name)
        time.sleep(random.uniform(0.3, 0.8))
    _click_next(browser)
    time.sleep(random.uniform(1, 2))
    return True


def _fill_birthdate(browser: CDPBrowser, account: OutlookAccount) -> bool:
    logger.info("[FILL] Filling birthdate: %s/%s/%s", account.birth_month, account.birth_day, account.birth_year)
    
    # Birth year - type into number input
    year_filled = False
    for selector in FIELD_SELECTORS["birth_year"]:
        try:
            nid = browser.query_selector(selector)
            if nid and browser.is_element_visible(nid):
                rect = browser.get_element_rect(nid)
                if rect:
                    browser.click_at(rect["center_x"], rect["center_y"])
                    time.sleep(0.2)
                    browser.type_text(account.birth_year, delay_ms=50)
                    year_filled = True
                break
        except Exception:
            continue
    if not year_filled:
        nid = browser.query_selector("input[type='number']")
        if nid and browser.is_element_visible(nid):
            rect = browser.get_element_rect(nid)
            if rect:
                browser.click_at(rect["center_x"], rect["center_y"])
                time.sleep(0.2)
                browser.type_text(account.birth_year, delay_ms=50)
    
    time.sleep(random.uniform(0.3, 0.5))
    
    # Birth month - Fluent UI: click dropdown, then click option with matching month name/number
    month_num = int(account.birth_month)
    month_names = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ]
    _click_fluent_dropdown_option(
        browser,
        "#BirthMonthDropdown",
        "BirthMonth",
        [str(month_num), f"{month_num}月", month_names[month_num - 1]],
    )
    time.sleep(random.uniform(0.3, 0.5))
    
    # Birth day - Fluent UI: click dropdown, then click exact day option
    day_num = int(account.birth_day)
    _click_fluent_dropdown_option(browser, "#BirthDayDropdown", "BirthDay", [str(day_num)])
    time.sleep(random.uniform(0.3, 0.5))
    
    _click_next(browser)
    time.sleep(random.uniform(1, 2))
    return True


def _click_fluent_dropdown_option(browser: CDPBrowser, button_id: str, name_hint: str, target_texts) -> bool:
    """Click a Fluent UI Dropdown button and select an option by keyboard navigation."""
    # Click the dropdown button to open it
    nid = browser.query_selector(button_id)
    if not nid:
        nid = browser.query_selector(f"button[name*='{name_hint}']")
    if not nid or not browser.is_element_visible(nid):
        logger.warning("[FILL] Dropdown button not found: %s", button_id)
        return False
    rect = browser.get_element_rect(nid)
    if not rect:
        return False
    browser.click_at(rect["center_x"], rect["center_y"])
    time.sleep(0.8)
    
    # Get the list of option texts to find the target index
    if isinstance(target_texts, str):
        targets = [target_texts]
    else:
        targets = [str(t) for t in target_texts]
    result = browser.evaluate(f"""
        (() => {{
            const targets = {json.dumps(targets, ensure_ascii=False)};
            const options = document.querySelectorAll('[role=option]');
            const texts = [];
            let targetIdx = -1;
            for (let i = 0; i < options.length; i++) {{
                const t = (options[i].textContent || '').trim();
                texts.push(t);
                if (targets.some(x => t === x || t.toLowerCase() === x.toLowerCase())) {{
                    targetIdx = i;
                    break;
                }}
            }}
            return JSON.stringify({{texts, targetIdx, count: options.length}});
        }})()
    """)
    if result:
        data = json.loads(result)
        logger.info("[FILL] Options: %s, target index: %d", data["texts"][:5], data["targetIdx"])
        if data["targetIdx"] >= 0:
            # Use keyboard: press Home first, then Down arrow to target
            # First press Home to go to first option
            browser.press_key("Home")
            time.sleep(0.1)
            # Then press Down arrow target_idx times
            for _ in range(data["targetIdx"]):
                browser.press_key("ArrowDown")
                time.sleep(0.05)
            # Press Enter to select
            browser.press_key("Enter")
            logger.info("[FILL] Selected option at index %d", data["targetIdx"])
        else:
            logger.warning("[FILL] Target option '%s' not found in list", targets)
            browser.press_key("Escape")
    else:
        logger.warning("[FILL] Could not read dropdown options")
        browser.press_key("Escape")
    time.sleep(0.3)
    return True


def _click_next(browser: CDPBrowser):
    # \u65b9\u6cd51: JavaScript \u76f4\u63a5\u70b9\u51fb\uff08\u5bf9 React \u5e94\u7528\u66f4\u53ef\u9760\uff09
    result = browser.evaluate("""(() => {
        // \u4f18\u5148\u6309 selector \u627e
        const selectors = ['#nextButton', 'button[type="submit"]', '#idSIButton9', 'button[data-testid="primaryButton"]'];
        for (const sel of selectors) {
            const btn = document.querySelector(sel);
            if (btn && btn.offsetParent !== null && !btn.disabled) {
                btn.focus();
                btn.click();
                return 'js:' + sel;
            }
        }
        // \u518d\u6309\u6587\u672c\u627e
        const allBtns = document.querySelectorAll('button');
        for (const btn of allBtns) {
            const text = (btn.textContent || '').trim().toLowerCase();
            if ((text === 'next' || text === 'sign in' || text === '\u4e0b\u4e00\u6b65' || text === '\u540c\u610f\u5e76\u7ee7\u7eed') && btn.offsetParent !== null && !btn.disabled) {
                btn.focus();
                btn.click();
                return 'js:text:' + text;
            }
        }
        return false;
    })()""")
    if result and result != False:
        logger.info("[CLICK] Next button via JS: %s", result)
        return

    # \u65b9\u6cd52: CDP \u9f20\u6807\u4e8b\u4ef6\uff08\u540e\u5907\uff09
    for selector in FIELD_SELECTORS["submit"]:
        try:
            nid = browser.query_selector(selector)
            if nid and browser.is_element_visible(nid):
                rect = browser.get_element_rect(nid)
                if rect:
                    browser.click_at(rect["center_x"], rect["center_y"])
                    logger.info("[CLICK] Next button via CDP: %s", selector)
                    return
        except Exception:
            continue
    logger.warning("[CLICK] Next button NOT FOUND by any method")



def _extract_refresh_token(browser, email, client_id="14d82eec-204b-4c2f-b7e8-296a70dab67e", timeout=60, password="", proxy_url=""):
    """使用 localhost 回调 + PKCE 获取 OAuth refresh_token。
    流程：导航到 OAuth 页（只导航一次）→ 跟随微软自动重定向 → 每页点对按钮 → 捕获 code → 换取 tokens。
    proxy_url: 用于 token 交换的代理（格式: http://user:pass@host:port 或 http://host:port）
    """
    import base64, hashlib, secrets, socket, socketserver, threading as _thr
    import http.server, urllib.parse, urllib.request

    # PKCE
    def _b64url(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")
    code_verifier = _b64url(secrets.token_bytes(64))
    code_challenge = _b64url(hashlib.sha256(code_verifier.encode("ascii")).digest())

    # 找可用端口
    port = 0
    for p in range(18765, 18780):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("127.0.0.1", p))
                port = p
                break
        except OSError:
            continue
    if not port:
        logger.warning("[RT] 无法找到可用端口")
        return ""

    redirect_uri = f"http://localhost:{port}"

    # OAuth 回调 HTTP Handler
    class _CallbackHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path in ("/callback", "/"):
                params = urllib.parse.parse_qs(parsed.query)
                self.server.oauth_code = params.get("code", [None])[0]
                self.server.oauth_state = params.get("state", [None])[0]
                self.server.oauth_error = params.get("error", [None])[0]
                self.server.oauth_error_description = params.get("error_description", [None])[0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                msg = "授权成功，可以关闭此页面" if self.server.oauth_code else "授权失败"
                self.wfile.write(f"<html><body><h1>{msg}</h1></body></html>".encode("utf-8"))
            else:
                self.send_response(200)
                self.end_headers()
        def log_message(self, *a):
            pass

    class _TCPServer(socketserver.TCPServer):
        allow_reuse_address = True
        address_family = socket.AF_INET

    class _DualTCPServer(socketserver.TCPServer):
        allow_reuse_address = True
        def server_bind(self):
            try:
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            except Exception:
                pass
            super().server_bind()

    # 构建 OAuth URL（带 PKCE）
    state = secrets.token_hex(18)
    scopes = "offline_access openid profile https://graph.microsoft.com/User.Read https://graph.microsoft.com/Mail.Read"
    oauth_params = urllib.parse.urlencode({
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "response_mode": "query",
        "scope": scopes,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "prompt": "login",  # 使用 login 而非 select_account，配合 login_hint 自动选择账号并确认
        "login_hint": email,
    })
    oauth_url = f"https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize?{oauth_params}"

    try:
        # 启动本地回调服务器
        # 优先尝试 IPv6 双栈监听（[::] 同时接受 IPv4 和 IPv6 连接）
        # 但 Windows 上 IPv6 双栈不一定可靠，所以用 dual-stack + IPV6_V6ONLY=0
        httpd = None
        try:
            _DualTCPServer.address_family = socket.AF_INET6
            httpd = _DualTCPServer(("::", port), _CallbackHandler)
            # 确保 IPv6 双栈模式：同时接受 IPv4 和 IPv6 连接
            try:
                httpd.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            except (AttributeError, OSError):
                pass
            logger.info("[RT] 回调服务器监听 IPv6+IPv4 双栈: [::]:%d", port)
        except Exception as e6:
            logger.debug("[RT] IPv6 监听失败: %s, 回退到 IPv4", e6)
            try:
                httpd = _TCPServer(("127.0.0.1", port), _CallbackHandler)
                logger.info("[RT] 回调服务器监听 IPv4: 127.0.0.1:%d", port)
            except Exception as e4:
                logger.warning("[RT] IPv4 监听也失败: %s, 尝试 0.0.0.0", e4)
                httpd = _TCPServer(("0.0.0.0", port), _CallbackHandler)
                logger.info("[RT] 回调服务器监听 0.0.0.0:%d", port)
        httpd.oauth_code = None
        httpd.oauth_state = None
        httpd.oauth_error = None
        httpd.oauth_error_description = None
        def _serve_requests(srv):
            """处理回调请求，最多等待 timeout 秒"""
            srv.timeout = 2.0
            deadline_serve = time.time() + timeout
            while time.time() < deadline_serve:
                if srv.oauth_code or srv.oauth_error:
                    break
                try:
                    srv.handle_request()
                except Exception:
                    break
        _thr.Thread(target=_serve_requests, args=(httpd,), daemon=True).start()
        logger.info("[RT] 本地回调服务器已启动: 127.0.0.1:%d", port)

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 唯一一次导航，之后全部跟随微软自动重定向
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        logger.info("[RT] 导航到 OAuth 授权页: %s", email)
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 关键修复：用 CDP Network.setProxyOverride 确保本地回调直连
        # 问题：Chrome 用 --proxy-server 时，即使有 --proxy-bypass-list=<-loopback>，
        #        localhost 回调仍可能被代理拦截导致 502
        # 方案：通过 CDP 动态设置代理规则，显式将 localhost/127.0.0.1 排除在代理之外
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        _cdp_redirect_code = None  # 从 CDP 拦截到的 auth code
        _original_proxy_config = None  # 保存原始代理配置以便恢复
        try:
            browser.evaluate("undefined")  # warm up
            browser._send_cmd("Network.enable", {})
            logger.info("[RT] CDP Network 域已启用")

            # ── 用 Network.setProxyOverride 确保本地回调绕过代理 ──
            # 获取当前浏览器的代理配置（来自 --proxy-server 启动参数）
            try:
                proxy_result = browser._send_cmd("Network.getProxySettings", {})
                _original_proxy_config = proxy_result
                logger.info("[RT] 当前代理配置: %s", proxy_result)
            except Exception:
                logger.debug("[RT] 无法获取当前代理配置（可能无代理）")

            # 设置代理绕过规则：所有外部流量走代理，localhost/127.0.0.1 直连
            try:
                bypass_rules = [
                    "localhost",
                    "127.0.0.1",
                    "::1",
                    f"localhost:{port}",
                    f"127.0.0.1:{port}",
                    "<-loopback>",
                ]
                browser._send_cmd("Network.setProxyOverride", {
                    "bypassRules": bypass_rules,
                })
                logger.info("[RT] 已设置代理绕过规则: %s（确保本地回调直连）", bypass_rules)
            except Exception as proxy_err:
                logger.warning("[RT] Network.setProxyOverride 失败（旧版 Chrome 可能不支持）: %s", proxy_err)
                # 备选方案：尝试用 Page.setBypassCSP 等方式，或继续用 CDP 事件拦截

            # ── 注册 Network.requestWillBeSent 事件处理器，拦截 localhost 回调重定向 ──
            # 双保险：即使代理绕过成功，也保留 CDP 事件拦截作为备用
            def _on_network_request(event):
                nonlocal _cdp_redirect_code
                try:
                    params = event.get("params", {})
                    req_url = params.get("request", {}).get("url", "")
                    if ("localhost" in req_url or "127.0.0.1" in req_url) and "code=" in req_url:
                        logger.info("[RT] CDP 拦截到 localhost 回调: %s", req_url[:200])
                        parsed = urllib.parse.urlparse(req_url)
                        qs = urllib.parse.parse_qs(parsed.query)
                        code = qs.get("code", [None])[0]
                        if code:
                            _cdp_redirect_code = code
                            logger.info("[RT] CDP 拦截到 auth code: %s...", code[:20])
                except Exception:
                    pass
            browser._event_handlers.setdefault("Network.requestWillBeSent", []).append(_on_network_request)
        except Exception as cdp_err:
            logger.warning("[RT] CDP Network 域启用失败（将回退到 URL 检测）: %s", cdp_err)
        
        browser.navigate(oauth_url, wait_for_load=True, timeout=30)
        time.sleep(3)

        # 主循环：跟随微软自动重定向，每页识别并点击
        # 同时通过 CDP Network 事件拦截 localhost 回调重定向
        deadline = time.time() + timeout
        while time.time() < deadline and not httpd.oauth_code and not httpd.oauth_error and not _cdp_redirect_code:
            if _registration_stop or _get_thread_state().get("stop", False):
                logger.info("[RT] 检测到停止标志，退出")
                httpd.server_close()
                return ""

            url = browser.get_url()
            url_lower = url.lower()
            body = browser.get_body_text().lower()
            logger.info("[RT] 页面: URL=%s body_len=%d", url[:120], len(body))

            # ── 1. callback: code 已到 ──
            if "/callback" in url_lower or "code=" in url_lower:
                logger.info("[RT] 检测到 callback 重定向，提取 code...")
                try:
                    parsed = urllib.parse.urlparse(url)
                    params = urllib.parse.parse_qs(parsed.query)
                    code = params.get("code", [None])[0]
                    if code:
                        httpd.oauth_code = code
                        httpd.oauth_state = params.get("state", [None])[0]
                        logger.info("[RT] 获取到 code: %s...", code[:20])
                        break
                except Exception:
                    pass

            # ── 2. 账号选择页（主线第1步）：检测账号磁贴 ──
            # 必须严格检测：URL 包含登录域名 + 页面有明确的账号选择特征
            is_account_picker = False
            if ("login.live.com" in url_lower or "login.microsoftonline.com" in url_lower) and "error" not in body and "invalid_request" not in body:
                # 严格检测：必须有账号选择的关键词或 data-email 属性
                if any(kw in body for kw in ["pick an account", "choose account", "选择帐户", "选择账户", "pick account", "sign in with"]):
                    is_account_picker = True
                elif browser.evaluate('(() => document.querySelectorAll("[data-email], [data-upn]").length > 0)()'):
                    is_account_picker = True
            if is_account_picker:
                logger.info("[RT] 账号选择页，点击已登录账号: %s", email)
                email_prefix = email.split('@')[0].lower()
                pos = browser.evaluate(
                    f'(() => {{ '
                    f' const email = "{email.lower()}";'
                    f' const emailPrefix = "{email_prefix}";'
                    f' // 策略1: 查找包含邮箱前缀的最小面积元素'
                    f' const els = [...document.querySelectorAll("div, button, a, tr, td, span, li, p, [role=listitem], [role=option]")];'
                    f' let best = null; let bestArea = Infinity;'
                    f' for (const el of els) {{'
                    f'  const t = (el.textContent || "").trim().toLowerCase();'
                    f'  if (!t || (!t.includes(email) && !t.includes(emailPrefix))) continue;'
                    f'  const r = el.getBoundingClientRect();'
                    f'  if (r.width < 30 || r.height < 10) continue;'
                    f'  const area = r.width * r.height;'
                    f'  if (area < bestArea) {{ bestArea = area; best = el; }}'
                    f' }}'
                    f' if (best) {{'
                    f'  const r = best.getBoundingClientRect();'
                    f'  return JSON.stringify({{x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2), text: best.textContent.trim().substring(0,40)}});'
                    f' }}'
                    f' // 策略2: data-email / data-upn 属性'
                    f' const emailEls = document.querySelectorAll("[data-email], [data-upn]");'
                    f' for (const el of emailEls) {{'
                    f'  const e = (el.getAttribute("data-email") || el.getAttribute("data-upn") || "").toLowerCase();'
                    f'  if (e.includes(email) || e.includes(emailPrefix)) {{'
                    f'   const r = el.getBoundingClientRect();'
                    f'   return JSON.stringify({{x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2), text: e.substring(0,40)}});'
                    f'  }}'
                    f' }}'
                    f' return null; }})()'
                )
                if pos:
                    try:
                        pos_data = json.loads(pos)
                        logger.info("[RT] 找到账号: '%s' at (%d,%d)", pos_data.get('text',''), pos_data['x'], pos_data['y'])
                        browser.click_at(pos_data['x'], pos_data['y'])
                    except Exception as e:
                        logger.warning("[RT] 账号点击失败: %s", e)
                else:
                    logger.warning("[RT] 未找到账号元素，点击页面中央")
                    # 兜底：点击页面中央偏上（账号磁贴通常在这个区域）
                    browser.evaluate("(() => { document.elementFromPoint(640, 300)?.click(); return true; })()")
                time.sleep(3)
                continue

            # ── 2.5. 密码输入页：微软可能要求重新输入密码确认身份 ──
            if ("login.live.com" in url_lower or "login.microsoftonline.com" in url_lower) and password:
                # 检测是否有密码输入框
                has_password_field = browser.evaluate("""(() => {
                    const inputs = document.querySelectorAll('input[type="password"]');
                    for (const inp of inputs) {
                        if (inp.offsetParent !== null && inp.offsetWidth > 30) return true;
                    }
                    return false;
                })()""")
                if has_password_field:
                    logger.info("[RT] 检测到密码输入页，输入密码并点击下一步...")
                    # 先等待页面完全加载（body_len 太小说明还没加载完）
                    page_ready = browser.evaluate("document.readyState") == "complete"
                    if not page_ready:
                        time.sleep(2)
                    # 策略: JS native setter 填密码 + 触发 React 事件 + 点击 Sign in/Next 按钮
                    fill_result = browser.evaluate(f"""(() => {{
                        const inputs = document.querySelectorAll('input[type="password"]');
                        let filled = false;
                        for (const inp of inputs) {{
                            if (inp.offsetParent !== null && inp.offsetWidth > 30) {{
                                inp.scrollIntoView({{block: 'center'}});
                                inp.focus();
                                // 清空已有值
                                inp.value = '';
                                // 使用 native setter 以触发 React onChange
                                const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                                nativeInputValueSetter.call(inp, '{password.replace("'", "\\'")}');
                                inp.dispatchEvent(new Event('input', {{bubbles: true}}));
                                inp.dispatchEvent(new Event('change', {{bubbles: true}}));
                                filled = true;
                                break;
                            }}
                        }}
                        if (!filled) return 'no_visible_input';
                        // 点击 Sign in / Next / 登录 / 下一步 按钮
                        const btns = document.querySelectorAll('button, input[type=submit], [role=button]');
                        for (const b of btns) {{
                            const t = (b.textContent || b.value || '').toLowerCase().trim();
                            if (!t) continue;
                            if (t.includes('sign in') || t.includes('next') || t.includes('登录') || t.includes('下一步')) {{
                                b.click(); return 'btn:' + t.substring(0,30);
                            }}
                        }}
                        // 兜底：尝试 idSIButton9（微软标准按钮）
                        const idBtn = document.getElementById('idSIButton9');
                        if (idBtn) {{ idBtn.click(); return 'idSIButton9'; }}
                        return 'filled_no_btn';
                    }})()""")
                    logger.info("[RT] 密码输入+按钮点击结果: %s", fill_result)
                    # 验证密码是否真的填入了
                    pwd_check = browser.evaluate("""(() => {
                        const inputs = document.querySelectorAll('input[type="password"]');
                        for (const inp of inputs) {
                            if (inp.offsetParent !== null && inp.offsetWidth > 30) return inp.value.length;
                        }
                        return -1;
                    })()""")
                    if pwd_check == 0:
                        logger.warning("[RT] 密码值为空！native setter 可能未生效，尝试 CDP insertText")
                        # 用 CDP insertText 作为备选
                        try:
                            browser.evaluate("""(() => {
                                const inputs = document.querySelectorAll('input[type="password"]');
                                for (const inp of inputs) {
                                    if (inp.offsetParent !== null && inp.offsetWidth > 30) {
                                        inp.focus(); return true;
                                    }
                                }
                                return false;
                            })()""")
                            time.sleep(0.3)
                            browser._send_cmd("Input.insertText", {"text": password})
                            time.sleep(0.5)
                            # 再次点击按钮
                            browser.evaluate("""(() => {
                                const btns = document.querySelectorAll('button, input[type=submit], [role=button]');
                                for (const b of btns) {
                                    const t = (b.textContent || b.value || '').toLowerCase().trim();
                                    if (t.includes('sign in') || t.includes('next') || t.includes('登录') || t.includes('下一步')) {
                                        b.click(); return t;
                                    }
                                }
                                const idBtn = document.getElementById('idSIButton9');
                                if (idBtn) { idBtn.click(); return 'idSIButton9'; }
                                return null;
                            })()""")
                        except Exception:
                            pass
                    if fill_result == 'filled_no_btn':
                        # 没找到按钮，用 CDP Enter 提交
                        try:
                            browser._send_cmd("Input.dispatchKeyEvent", {
                                "type": "keyDown", "key": "Enter", "code": "Enter",
                                "windowsVirtualKeyCode": 13
                            })
                            browser._send_cmd("Input.dispatchKeyEvent", {
                                "type": "keyUp", "key": "Enter", "code": "Enter",
                                "windowsVirtualKeyCode": 13
                            })
                            logger.info("[RT] 密码已填入，用 CDP Enter 提交")
                        except Exception:
                            pass
                    time.sleep(3)
                    continue

            # ── 2.7 Windows 安全中心通行密钥弹窗 ──
            # 微软 OAuth 流程中会弹出 "Windows 安全中心 - 选择保存通行密钥的位置"
            # 不是必须关闭弹窗，直接点击页面上的"下一步"即可跳过
            if any(kw in body for kw in ["选择保存通行密钥", "windows 安全中心", "windows security", "保存通行密钥",
                                           "passkey setup", "passkey creation"]):
                logger.info("[RT] 检测到 Windows 安全中心/通行密钥弹窗，点击下一步跳过...")
                dismissed = browser.evaluate("""(() => {
                    const btns = document.querySelectorAll('button, [role=button], input[type=submit]');
                    // 优先点击"下一步"继续流程
                    for (const b of btns) {
                        const t = (b.textContent || b.value || '').toLowerCase().trim();
                        if (!t) continue;
                        if (t === 'next' || t === '下一步' || t === 'continue' || t === '继续' || t === 'sign in' || t === '登录') {
                            b.click(); return 'next:' + t;
                        }
                    }
                    // idSIButton9
                    const idBtn = document.getElementById('idSIButton9');
                    if (idBtn) { idBtn.click(); return 'idSIButton9'; }
                    // 其次找取消/关闭按钮
                    for (const b of btns) {
                        const t = (b.textContent || b.value || '').toLowerCase().trim();
                        if (!t) continue;
                        if (t === '取消' || t === 'cancel' || t === 'close' || t.includes('关闭')) {
                            b.click(); return 'cancel:' + t;
                        }
                    }
                    // 兜底：找任何看起来像跳过的按钮
                    for (const b of btns) {
                        const t = (b.textContent || b.value || '').toLowerCase().trim();
                        if (t.includes('skip') || t.includes('no thanks') || t.includes('暂不') || t.includes('later')) {
                            b.click(); return 'fallback:' + t;
                        }
                    }
                    return null;
                })()""")
                if dismissed:
                    logger.info("[RT] 通行密钥弹窗已处理: %s", dismissed)
                else:
                    logger.warning("[RT] 通行密钥弹窗未找到按钮，等待页面变化...")
                time.sleep(3)
                continue

            # ── 3. Consent/Update/OAuth 授权确认页（主线第2步）：URL + body 检测 ──
            # 注意: URL 中的 Consent/Update 首字母大写，必须用 .lower() 比较
            is_consent_url = "account.live.com/consent" in url_lower or ("login.microsoftonline.com" in url_lower and ("/consent" in url_lower or "/authorize" in url_lower))
            is_consent_body = any(kw in body for kw in ["microsoft graph command line tools", "permission", "permissions requested", "请求的权限", "已授予访问权限"])
            if is_consent_url or ("login.microsoftonline.com" in url_lower and is_consent_body):
                logger.info("[RT] Consent/OAuth 权限页面，点击确认... URL=%s", url[:120])
                clicked = browser.evaluate("""(() => {
                    function _vis(el) {
                        if (!el) return false;
                        const s = window.getComputedStyle(el);
                        if (s.display==='none'||s.visibility==='hidden'||Number(s.opacity||1)===0) return false;
                        return el.offsetWidth>0||el.offsetHeight>0||el.getClientRects().length>0;
                    }
                    // 优先尝试 idBtn_Accept（OAuth 权限同意页的标准按钮）
                    for (const id of ['idBtn_Accept','idSIButton9','acceptButton','nextButton','primaryButton']) {
                        const el = document.getElementById(id);
                        if (el && _vis(el)) { el.click(); return 'consent-id:' + id; }
                    }
                    const btns = document.querySelectorAll('button, input[type=submit], [role=button]');
                    for (const b of btns) {
                        const t = (b.textContent || b.value || '').toLowerCase().trim();
                        if (!_vis(b)) continue;
                        if (t.includes('accept')||t.includes('agree')||t.includes('allow')||t.includes('continue')||
                            t.includes('next')||t.includes('ok')||t.includes('yes')||t.includes('submit')||
                            t.includes('确认')||t.includes('同意')||t.includes('接受')||t.includes('继续')||t.includes('下一步'))
                        { b.click(); return 'consent:' + t.substring(0,30); }
                    }
                    return null;
                })()""")
                if clicked:
                    logger.info("[RT] Consent 已点击: %s", clicked)
                else:
                    logger.warning("[RT] Consent 未找到按钮")
                time.sleep(3)
                continue

            # ── 4. "是否保持登录"（主线第3步）：URL / body 检测，点"是" ──
            is_kmsi_url = "/kmsi" in url_lower
            is_kmsi_body = "keepsignin" in body.replace(" ", "") or "stay signed" in body or "保持登录" in body
            if is_kmsi_url or is_kmsi_body:
                logger.info("[RT] 保持登录页面（kmsi），点击'是' URL=%s", url[:120])
                clicked_kmsi = browser.evaluate("""(() => {
                    // 优先 idSIButton9（微软标准 KMSI 按钮）
                    const btn9 = document.getElementById('idSIButton9');
                    if (btn9) { btn9.click(); return 'idSIButton9'; }
                    // 回退：查找包含"是"/"Yes"的按钮
                    const btns = document.querySelectorAll('button, input[type=submit], [role=button]');
                    for (const b of btns) {
                        const t = (b.textContent || b.value || '').toLowerCase().trim();
                        if (t==='yes' || t==='是' || t.includes('stay signed') || t.includes('保持登录'))
                        { b.click(); return 'text:' + t.substring(0,20); }
                    }
                    // 最后兜底：点任何肯定性按钮
                    for (const b of btns) {
                        const t = (b.textContent || b.value || '').toLowerCase().trim();
                        if (t.includes('accept')||t.includes('agree')||t.includes('continue')||t.includes('ok')||
                            t.includes('确认')||t.includes('同意')||t.includes('接受')||t.includes('继续'))
                        { b.click(); return 'fallback:' + t.substring(0,20); }
                    }
                    return null;
                })()""")
                if clicked_kmsi:
                    logger.info("[RT] KMSI 已点击: %s", clicked_kmsi)
                else:
                    logger.warning("[RT] KMSI 未找到可点击按钮")
                time.sleep(3)
                continue

            # ── 5. 隐私声明页：body 含关键词 ──
            if any(kw in body for kw in ["privacynotice", "privacy notice", "隐私声明", "隐私偏好", "数据导出", "帮助改进"]):
                logger.info("[RT] 隐私声明页")
                browser.evaluate("""(() => {
                    const btns = document.querySelectorAll('button, input[type=submit], [role=button]');
                    for (const b of btns) {
                        const t = (b.textContent||b.value||'').toLowerCase();
                        if (t.includes('agree')||t.includes('continue')||t.includes('同意')||t.includes('接受')||
                            t.includes('继续')||t.includes('否')||t==='no') { b.click(); return t.substring(0,30); }
                    }
                    return null;
                })()""")
                time.sleep(3)
                continue

            # ── 6. 帐户说明页 ──
            if any(kw in body for kw in ["quick note about your microsoft account", "有关 microsoft 帐户的快速说明"]):
                logger.info("[RT] 帐户说明页")
                browser.evaluate("""(() => {
                    const btns = document.querySelectorAll('button');
                    for (const b of btns) { const t=(b.textContent||'').toLowerCase();
                        if (t==='ok'||t==='确定'||t==='got it'||t.includes('continue')) { b.click(); return t; } }
                    return null;
                })()""")
                time.sleep(3)
                continue

            # ── 7. 添加恢复邮箱 ──
            if any(kw in body for kw in ["add a recovery", "recovery email", "添加恢复"]):
                logger.info("[RT] 添加恢复邮箱页，跳过")
                browser.evaluate("""(() => {
                    const btns = document.querySelectorAll('button, a, [role=button]');
                    for (const b of btns) { const t=(b.textContent||'').toLowerCase();
                        if (t.includes('skip')||t.includes('暂不')||t.includes('跳过')||t.includes('not now'))
                        { b.click(); return t.substring(0,30); } }
                    return null;
                })()""")
                time.sleep(3)
                continue

            # ── 8. Passkey/FIDO 页 ──
            if "fido" in url or "passkey" in body or "security key" in body or "windows hello" in body:
                logger.info("[RT] Passkey 页，跳过")
                browser.evaluate("""(() => {
                    const btns = document.querySelectorAll('button, a, [role=button]');
                    for (const b of btns) { const t=(b.textContent||'').toLowerCase();
                        if (t.includes('skip')||t.includes('not now')||t.includes('暂不')||t.includes('以后')||
                            t.includes('稍后')||t.includes('no thanks')) { b.click(); return t.substring(0,30); } }
                    return null;
                })()""")
                time.sleep(3)
                continue

            # ── 9a. OAuth 严重错误页：真正的不可恢复错误 ──
            # 注意：interaction_required 只是微软要求交互确认，不是错误，不应在此处退出
            # access_denied 可能是临时问题，先重试
            if any(kw in body for kw in ['could not complete', 'unable to complete', 'cannot complete', 'couldn\'t complete',
                                           '无法完成', '请求出错']):
                # 检查 URL 中是否有真正的错误码
                try:
                    parsed = urllib.parse.urlparse(url)
                    params = urllib.parse.parse_qs(parsed.query)
                    err = params.get('error', [None])[0]
                    if err in ('invalid_request', 'unauthorized_client', 'unsupported_response_type', 'server_error'):
                        logger.error('[RT] OAuth 严重错误: %s - %s', err, params.get('error_description', [None])[0])
                        httpd.server_close()
                        return ''
                except Exception:
                    pass
                logger.warning('[RT] OAuth 可能的错误页面，等待重试... URL=%s', url[:120])
                time.sleep(3)
                continue

            # ── 9. 授权失败 → 等待（微软可能自动重试） ──
            if "授权失败" in body or "authorization failed" in body:
                logger.warning("[RT] 授权失败页面，等待自动重试...")
                time.sleep(3)
                continue

            # ── 9b. chrome-error 页面：网络错误导致页面无法加载 ──
            if "chromewebdata" in url_lower:
                # 如果 CDP 已经拦截到了 code，直接退出循环
                if _cdp_redirect_code:
                    logger.info("[RT] chrome-error 页面但已拦截到 code，退出循环")
                    break
                # 否则等一会再重新导航（Accept 可能已点击，重定向中 502）
                logger.warning("[RT] 检测到 chrome-error 页面（网络错误），3s 后重新导航到 OAuth URL")
                time.sleep(3)
                try:
                    browser.navigate(oauth_url, wait_for_load=True, timeout=20)
                except Exception:
                    pass
                time.sleep(2)
                continue

            # ── 10. 未识别 → 等页面加载，点任何可用按钮 ──
            logger.info("[RT] 未识别页面，等待加载...")
            time.sleep(2)
            browser.evaluate("""(() => {
                function _vis(el) {
                    if (!el) return false;
                    const s = window.getComputedStyle(el);
                    if (s.display==='none'||s.visibility==='hidden'||Number(s.opacity||1)===0) return false;
                    return el.offsetWidth>0||el.offsetHeight>0||el.getClientRects().length>0;
                }
                const btns = document.querySelectorAll('button, input[type=submit], [role=button]');
                for (const b of btns) {
                    if (!_vis(b)) continue;
                    const t = (b.textContent || b.value || '').toLowerCase().trim();
                    if (t.includes('accept')||t.includes('agree')||t.includes('allow')||t.includes('continue')||
                        t.includes('next')||t.includes('ok')||t.includes('yes')||t.includes('submit')||t.includes('confirm')||
                        t.includes('确认')||t.includes('同意')||t.includes('接受')||t.includes('继续')||t.includes('下一步'))
                    { b.click(); return 'auto:' + t.substring(0,30); }
                }
                return null;
            })()""")

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 循环结束，处理结果
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 优先使用 CDP 拦截到的 code（不依赖浏览器页面加载成功）
        code = _cdp_redirect_code or httpd.oauth_code
        error = httpd.oauth_error if not _cdp_redirect_code else None
        error_desc = getattr(httpd, 'oauth_error_description', None) if not _cdp_redirect_code else None
        httpd.server_close()

        if error:
            logger.warning("[RT] OAuth 错误: %s - %s", error, error_desc)
            try:
                logger.warning("[RT] 错误时 URL: %s", browser.get_url())
            except Exception:
                pass
            return ""
        if not code:
            logger.warning("[RT] 等待授权超时 (%ds)", timeout)
            return ""

        if httpd.oauth_state and httpd.oauth_state != state:
            logger.warning("[RT] state 校验失败")
            return ""

        logger.info("[RT] 获取到 auth code: %s...", code[:20])

        # 用 PKCE 换取 tokens
        data = urllib.parse.urlencode({
            "client_id": client_id,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "scope": scopes,
            "code_verifier": code_verifier,
        }).encode()
        token_url = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
        req = urllib.request.Request(
            token_url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        # 如果有代理，通过代理发送 token 交换请求
        opener = None
        if proxy_url:
            try:
                proxy_handler = urllib.request.ProxyHandler({
                    "http": proxy_url,
                    "https": proxy_url,
                })
                opener = urllib.request.build_opener(proxy_handler)
                logger.info("[RT] Token 交换使用代理: %s", proxy_url[:50])
            except Exception as proxy_err:
                logger.warning("[RT] 代理设置失败，直连: %s", proxy_err)

        try:
            if opener:
                resp = opener.open(req, timeout=15)
            else:
                resp = urllib.request.urlopen(req, timeout=15)
            tokens = json.loads(resp.read())
            rt = tokens.get("refresh_token", "")
            if rt:
                logger.info("[RT] refresh_token 获取成功: %s...", rt[:30])
            else:
                logger.warning("[RT] token 响应中无 refresh_token")
            return rt
        except Exception as token_err:
            # 如果直连失败且有代理，尝试用代理重试
            if not opener and proxy_url:
                logger.warning("[RT] 直连 token 交换失败: %s，尝试用代理重试", token_err)
                try:
                    proxy_handler = urllib.request.ProxyHandler({
                        "http": proxy_url,
                        "https": proxy_url,
                    })
                    opener = urllib.request.build_opener(proxy_handler)
                    resp = opener.open(req, timeout=15)
                    tokens = json.loads(resp.read())
                    rt = tokens.get("refresh_token", "")
                    if rt:
                        logger.info("[RT] 代理重试成功: %s...", rt[:30])
                    return rt
                except Exception as retry_err:
                    logger.warning("[RT] 代理重试也失败: %s", retry_err)
                    return ""
            raise
    except Exception as e:
        logger.warning("[RT] refresh_token 获取失败: %s", e)
        return ""

def register_outlook_account(
    account: OutlookAccount | None = None,
    chrome_path: str = "",
    browser_type: str = "chrome",  # chrome, edge, brave, chromium, vivaldi, thorium
    proxy: str = "",
    headless: bool = False,
    extension_path: str = "",
    flow_report=None,
    proxy_manager=None,  # Deprecated (no longer used for retries)
    keep_browser_open: bool = False,  # Keep browser open for post-registration tasks (e.g. OAuth)
    extract_rt: bool = False,  # 注册成功后自动在同一浏览器获取 refresh_token
    pause_checker=None,  # 暂停检查回调: pause_checker(step_name) -> bool(stop)
    slot_index: int = 0,  # 并发槽位索引（0-based），用于计算窗口偏移位置
) -> RegistrationResult:
    """
    Register an Outlook account using the CDP hybrid approach.

    Args:
        account: Account data (generated if None)
        chrome_path: Path to Chrome executable
        proxy: Proxy in any format (IPWEB host:port:user:pass, URL, etc.)
        headless: Run in headless mode
        extension_path: Path to browser extension
        flow_report: Flow diagnostics report
        proxy_manager: Deprecated (no longer used)

    Returns:
        RegistrationResult with account details
    """
    logger.info("[CDP_REG] register_outlook_account called: browser_type='%s'", browser_type)
    # Parse and normalize proxy
    proxy_info = parse_proxy(proxy) if proxy else None
    proxy_url = proxy_info.chrome_proxy if proxy_info else ""
    proxy_auth_url = proxy_info.url if proxy_info and proxy_info.has_auth else ""
    if proxy_info and proxy_info.has_auth:
        logger.info("[CDP_REG] Proxy: %s (auth: %s)", proxy_info.host_port, proxy_info.username)
    elif proxy_info:
        logger.info("[CDP_REG] Proxy: %s (no auth)", proxy_info.host_port)
    if account is None:
        account = _random_account()

    result = RegistrationResult(
        email=account.email, password=account.password, username=account.username,
        provider=account.provider, domain=account.domain, client_id=account.client_id,
    )

    # ── 并发窗口偏移: 每个槽位错开窗口位置，避免重叠 ──
    # 2列布局: slot 0 -> (0, 0), slot 1 -> (640, 0), slot 2 -> (0, 500), slot 3 -> (640, 500)
    win_w, win_h = 640, 450  # 每个窗口的大小（小于 screen_size 以容纳多个）
    col = slot_index % 2
    row = slot_index // 2
    win_x = col * (win_w + 20)
    win_y = row * (win_h + 40) + 40  # 顶部留 40px 给任务栏
    logger.info("[CDP_REG] Slot %d: window at (%d, %d) size %dx%d", slot_index, win_x, win_y, win_w, win_h)

    config = CDPLaunchConfig(
        chrome_path=chrome_path, browser_type=browser_type,
        proxy=proxy_url, proxy_auth_url=proxy_auth_url, headless=headless,
        extensions=[extension_path] if extension_path else [],
        window_size=(win_w, win_h), window_position=(win_x, win_y),
    )

    browser = None
    try:
        browser = CDPBrowser(config).launch()
        _register_browser(browser)  # 注册到线程安全字典，用于强制终止
        logger.info("[CDP_REG] Starting registration for %s", account.email)

        # 代理 IP 验证已由 curl 预检完成，Chrome 直接访问注册页（跳过 ipify 避免 SOCKS5 DNS 超时）
        if proxy_info:
            logger.info("[CDP_REG] Proxy: %s (curl预检已通过，Chrome直接访问注册页)", proxy_info.host_port)

        # Step 1: Navigate to signup
        if _check_pause_or_stop("navigate"): result.error = "stopped"; return result

        if pause_checker:
            if pause_checker("navigate"): result.error = "stopped"; return result
        browser.navigate(SIGNUP_URL, wait_for_load=True, timeout=25)

        # Wait for SPA to render — detect page readiness ASAP instead of fixed sleep
        for _wait_i in range(30):
            # 快速检测 Chrome 错误页，立即退出
            try:
                quick_url = browser.get_url().lower()
                if "chrome-error" in quick_url:
                    logger.error("[CDP_REG] Chrome error page detected early: %s", quick_url)
                    result.error = f"proxy_error: {quick_url}"; break
            except Exception:
                pass

            body_text = browser.get_body_text().lower()

            # 快速检测隐私同意页面（中国区），命中即处理，不用等后面单独处理
            if any(kw in body_text for kw in ["同意并继续", "agree and continue", "拒绝并退出"]):
                logger.info("[CDP_REG] Privacy consent page detected early, clicking agree...")
                browser.evaluate("""(() => {
                    const btns = document.querySelectorAll('button');
                    for (const b of btns) {
                        const t = (b.textContent || '').toLowerCase();
                        if (t.includes('agree') || t.includes('同意')) { b.click(); return true; }
                    }
                    const next = document.getElementById('nextButton');
                    if (next) { next.click(); return true; }
                    return false;
                })()""")
                time.sleep(1)
                continue

            # 检测可见输入框 — 页面已就绪，立即进入状态机
            inputs = browser.evaluate("""(() => {
                const els = document.querySelectorAll('input');
                const vis = [];
                for (const el of els) {
                    if (el.offsetParent !== null && el.offsetWidth > 50) vis.push(el.type || el.name || el.id);
                }
                return vis;
            })()""")
            if inputs and len(inputs) > 0:
                logger.info("[CDP_REG] Page ready, visible inputs: %s", inputs)
                break

            # 检测页面状态（可能已跳转到非 signup 页面）
            page_state = _detect_page_state(browser)
            if page_state not in ("unknown", "fill_username"):
                logger.info("[CDP_REG] Page state detected early: %s", page_state)
                break
            if _wait_i % 5 == 4:
                url_now = browser.get_url()
                title_now = browser.get_title()
                body_snip = browser.get_body_text()[:300]
                all_els = browser.evaluate("""(() => {
                    const els = document.querySelectorAll('input,select,button,textarea');
                    return Array.from(els).map(e => e.tagName + '#' + e.id + '.' + e.name + ' vis:' + (e.offsetParent!==null));
                })()""")
                logger.info("[CDP_REG] Tick %d: URL=%s title=%s", _wait_i, url_now[:80], title_now)
                logger.info("[CDP_REG] Body: %s", body_snip[:200])
                logger.info("[CDP_REG] All els: %s", all_els)
            time.sleep(0.3)
        else:
            url_now = browser.get_url()
            title_now = browser.get_title()
            body_snip = browser.get_body_text()[:500]
            logger.warning("[CDP_REG] No inputs after 9s. URL=%s title=%s", url_now, title_now)
            logger.warning("[CDP_REG] Body: %s", body_snip[:400])

        # Step 1.5: 隐私同意页面已在上方 SPA 渲染等待循环中提前处理
        for _ in range(0):  # disabled
            body = browser.get_body_text().lower()
            if any(kw in body for kw in ["\u540c\u610f\u5e76\u7ee7\u7eed", "agree and continue", "\u62d1\u7edd\u5e76\u9000\u51fa"]):
                logger.info("[CDP_REG] Privacy consent page detected, clicking agree...")
                browser.evaluate("""(() => {
                    const btns = document.querySelectorAll('button');
                    for (const b of btns) {
                        const t = (b.textContent || '').toLowerCase();
                        if (t.includes('agree') || t.includes('\u540c\u610f')) { b.click(); return true; }
                    }
                    const next = document.getElementById('nextButton');
                    if (next) { next.click(); return true; }
                    return false;
                })()""")
                time.sleep(random.uniform(2, 3))
            else:
                break

        # ═══════════════════════════════════════════════════════════
        # 状态机注册流程：每步可暂停，恢复后自动识别页面状态继续
        # ═══════════════════════════════════════════════════════════
        _steps_done = set()  # 已完成的步骤，避免重复执行
        _ms_error_count = 0  # microsoft_problem 页面出现次数
        _empty_page_count = 0  # 页面 body 为空的连续次数
        _crash_count = 0  # Chrome 崩溃检测计数（局部变量，并发安全）

        for _iter in range(50):  # MAX_ITERATIONS (增加到50，给加载慢的页面更多时间)
            # 暂停检查：暂停时阻塞，恢复后自动重新检测页面状态
            if _check_pause_or_stop("running"):
                result.error = "stopped"; return result
            if pause_checker:
                if pause_checker("running"): result.error = "stopped"; return result

            # 检测 Chrome 是否已崩溃（宽松：连续失败3次才判定崩溃）
            # 注意：_crash_count 是局部变量，每个注册任务独立，并发安全
            try:
                browser.get_url()
                _crash_count = 0  # 重置计数
            except Exception:
                _crash_count += 1
                if _crash_count >= 3:
                    logger.error("[CDP_REG] Chrome 进程已崩溃（连续%d次检测失败），退出状态机", _crash_count)
                    result.error = "browser_crashed"; break
                else:
                    logger.warning("[CDP_REG] get_url 异常（第%d次），可能是临时连接问题，重试...", _crash_count)
                    time.sleep(2); continue

            # 自动检测当前页面状态
            page_state = _detect_page_state(browser)
            logger.info("[CDP_REG] 状态机 iter=%d, 页面状态=%s, 已完成=%s", _iter, page_state, _steps_done)

            # ── 注册完成 ──
            if page_state == "account_home":
                result.success = True
                result.final_state = "account_home"
                result.final_url = browser.get_url()
                logger.info("[CDP_REG] Registration successful: %s", account.email)
                if _check_pause_or_stop("extract_rt"): result.error = "stopped"; return result
                if extract_rt and browser:
                    try:
                        # 传入代理 URL，用于 token 交换请求（带认证的完整代理 URL）
                        _rt_proxy = proxy_info.url if proxy_info and proxy_info.has_auth else (proxy_url if proxy_url else "")
                        rt = _extract_refresh_token(browser, account.email, account.client_id or "14d82eec-204b-4c2f-b7e8-296a70dab67e", password=account.password, proxy_url=_rt_proxy)
                        result.refresh_token = rt
                        if rt: logger.info("[CDP_REG] RT 获取成功: %s...", rt[:30])
                        else: logger.warning("[CDP_REG] RT 获取失败（注册已成功）")
                    except Exception as rt_exc:
                        logger.warning("[CDP_REG] RT 获取异常: %s", rt_exc)
                break

            if page_state == "blocked":
                result.error = "account_blocked"; break
            if page_state == "microsoft_problem":
                _ms_error_count += 1
                if _ms_error_count >= 5:
                    logger.error("[CDP_REG] microsoft_problem 页面重试 %d 次仍失败,放弃", _ms_error_count)
                    result.error = "microsoft_problem_page"; break
                logger.warning("[CDP_REG] microsoft_problem 页面 (第%d次), 等待5秒后刷新重试...", _ms_error_count)
                time.sleep(5)
                # 尝试刷新页面重新加载
                try:
                    browser.navigate(SIGNUP_URL, wait_for_load=True, timeout=20)
                except Exception:
                    pass
                _steps_done.clear()  # 重置步骤状态，重新开始
                continue
            if page_state == "proxy_error":
                err_snippet = browser.get_body_text()[:200]
                logger.error("[CDP_REG] 代理错误页面: %s", err_snippet)
                result.error = f"proxy_error: {err_snippet[:100]}"; break

            # ── 填写邮箱 ──
            if page_state == "fill_username" and "fill_username" not in _steps_done:
                # 额外检查: 确保 body 有内容（SPA 已渲染）
                body_check = browser.get_body_text().strip()
                if len(body_check) < 30:
                    logger.warning("[CDP_REG] fill_username 但 body 长度仅 %d，SPA 可能未渲染，等待...", len(body_check))
                    time.sleep(3)
                    continue
                if _check_pause_or_stop("fill_username"): result.error = "stopped"; return result
                if _fill_username(browser, account):
                    _steps_done.add("fill_username")
                else:
                    result.error = "username_fill_failed"; break
                continue

            # ── 填写密码 ──
            if page_state == "fill_password" and "fill_password" not in _steps_done:
                if _check_pause_or_stop("fill_password"): result.error = "stopped"; return result
                if _fill_password(browser, account.password):
                    _steps_done.add("fill_password")
                else:
                    result.error = "password_fill_failed"; break
                continue

            # ── 填写个人信息 ──
            if page_state == "fill_profile":
                if "fill_profile" in _steps_done:
                    # Already filled profile before — try clicking Next directly
                    # instead of re-typing, to avoid repeated input loop
                    logger.warning("[CDP_REG] fill_profile already done, clicking Next instead of re-filling")
                    _click_next(browser)
                    time.sleep(2)
                    continue
                if _check_pause_or_stop("fill_profile"): result.error = "stopped"; return result
                _fill_profile_fields(browser, account)
                _steps_done.add("fill_profile")
                continue

            # ── 填写生日 ──
            if page_state == "fill_birthdate":
                if _check_pause_or_stop("fill_birthdate"): result.error = "stopped"; return result
                result.auto_country = _read_auto_country(browser)
                _fill_birthdate(browser, account)
                _steps_done.add("fill_birthdate")
                continue

            # ── 处理验证码 ──
            if page_state == "captcha":
                if _check_pause_or_stop("captcha"): result.error = "stopped"; return result
                captcha = _detect_captcha(browser)
                if captcha:
                    result.challenge_type = captcha["type"]
                    logger.info("[CAPTCHA] Detected: %s", captcha["type"])
                    cleared = False
                    if captcha["type"] == "hsprotect":
                        cleared = _handle_hsprotect_captcha(browser)
                        if not cleared: cleared = _wait_for_manual_captcha(browser)
                    elif captcha["type"] == "funcaptcha":
                        cleared = _handle_funcaptcha(browser)
                        if not cleared: cleared = _wait_for_manual_captcha(browser)
                    else:
                        cleared = _wait_for_manual_captcha(browser)
                    result.challenge_cleared = cleared
                    if not cleared:
                        # CAPTCHA 未通过 — 系统级阻碍，直接结束（不再关闭浏览器换代理重试）
                        logger.error("[CAPTCHA] CAPTCHA not solved (%s) → system blockage, aborting", captcha['type'])
                        result.error = f"captcha_not_solved: {captcha['type']}"; break
                else:
                    logger.info("[CAPTCHA] State=captcha but no captcha detected, waiting...")
                    time.sleep(3)
                continue

            # ── 注册后页面处理 ──
            if page_state in ("privacy_notice", "account_notice", "stay_signed_in",
                              "add_recovery", "passkey_prompt", "success"):
                if _check_pause_or_stop("post_challenge"): result.error = "stopped"; return result
                final_state = _handle_post_challenge(browser, account)
                result.final_state = final_state
                result.final_url = browser.get_url()
                if final_state == "account_home":
                    result.success = True
                    logger.info("[CDP_REG] Registration successful: %s", account.email)
                    if extract_rt and browser:
                        try:
                            _rt_proxy = proxy_info.url if proxy_info and proxy_info.has_auth else (proxy_url if proxy_url else "")
                            rt = _extract_refresh_token(browser, account.email, account.client_id or "14d82eec-204b-4c2f-b7e8-296a70dab67e", password=account.password, proxy_url=_rt_proxy)
                            result.refresh_token = rt
                            if rt: logger.info("[CDP_REG] RT 获取成功: %s...", rt[:30])
                        except Exception as rt_exc:
                            logger.warning("[CDP_REG] RT 获取异常: %s", rt_exc)
                    break
                elif final_state == "microsoft_problem":
                    result.error = "microsoft_problem_page"; break
                elif final_state == "blocked":
                    result.error = "account_blocked"; break
                elif final_state in ("fill_username", "fill_password", "fill_profile"):
                    # _handle_post_challenge 返回了需要填写的状态，继续主循环处理
                    logger.info("[CDP_REG] post_challenge 返回 %s，继续主循环处理", final_state)
                    continue
                else:
                    result.error = f"unexpected_final_state: {final_state}"; break

            # ── loading/page_empty 状态: SPA 未渲染，等待或刷新 ──
            if page_state == "loading":
                logger.info("[CDP_REG] 页面加载中 (body 为空)，等待3秒...")
                time.sleep(3)
                continue
            if page_state == "page_empty":
                # 追踪空页面次数（局部变量，每个注册任务独立）
                _empty_page_count += 1
                if _empty_page_count >= 3:
                    logger.warning("[CDP_REG] 页面 body 持续为空 (第%d次)，刷新页面重试...", _empty_page_count)
                    try:
                        browser.navigate(SIGNUP_URL, wait_for_load=True, timeout=20)
                    except Exception:
                        pass
                    _empty_page_count = 0
                    time.sleep(3)
                    continue
                logger.info("[CDP_REG] 页面 DOM 完成但 body 为空 (第%d次)，等待3秒...", _empty_page_count)
                time.sleep(3)
                continue

            # ── 未知状态 → 等待页面加载，尝试恢复 ──
            logger.info("[CDP_REG] 未知页面状态 '%s'，等待3秒...", page_state)
            time.sleep(3)
            # 连续多次 unknown 后，尝试点击可能的提交按钮（页面可能卡在中间状态）
            if _iter > 0 and _iter % 5 == 0:
                # 先检查 body 是否有内容，避免在空白页面上盲目点击
                body_now = browser.get_body_text().strip()
                if len(body_now) > 50:
                    logger.info("[CDP_REG] 连续 unknown %d 次，尝试点击 Next/Submit 按钮恢复", _iter)
                    _click_next(browser)
                    time.sleep(2)
                else:
                    logger.info("[CDP_REG] 连续 unknown %d 次，但 body 为空(长度=%d)，跳过点击", _iter, len(body_now))
        else:
            result.error = "max_iterations_reached"
            logger.error("[CDP_REG] 状态机循环超过最大次数")

    except Exception as e:
        err_str = str(e)
        # 检测 Chrome 崩溃：如果 Chrome 进程已退出，明确标记为 browser_crashed 而非注册失败
        # 宽松检测：连续3次 evaluate 失败才判定崩溃
        chrome_alive = False
        if browser:
            for _crash_check in range(3):
                try:
                    chrome_alive = browser.evaluate("true") is not None
                    if chrome_alive:
                        break
                except Exception:
                    if _crash_check < 2:
                        time.sleep(1)
        if not chrome_alive and browser:
            logger.error("[CDP_REG] Chrome process crashed during registration")
            result.error = "browser_crashed"
        else:
            logger.exception("[CDP_REG] Registration failed: %s", e)
            result.error = err_str
    finally:
        _unregister_browser()  # 从线程安全字典中移除
        _clear_thread_state()  # 清理线程级控制状态
        if browser and not keep_browser_open:
            try:
                # Take final screenshot
                result.screenshot_path = browser.screenshot("final_state.png")
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass
        elif browser and keep_browser_open:
            try:
                result.screenshot_path = browser.screenshot("final_state.png")
            except Exception:
                pass
            result.browser = browser

    return result
