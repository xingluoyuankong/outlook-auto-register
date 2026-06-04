"""
CDP 共享基础模块
所有独立注册脚本共用的浏览器操控、表单填写、验证码检测工具。
不包含任何提供商特定逻辑。
"""

from __future__ import annotations

import json
import logging
import os
import random
import string
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

try:
    from .cdp_browser import CDPBrowser, CDPLaunchConfig
except ImportError:
    from cdp_browser import CDPBrowser, CDPLaunchConfig

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# 账号数据
# ──────────────────────────────────────────────

@dataclass
class AccountInfo:
    """通用账号注册数据"""
    username: str = ""
    email: str = ""
    password: str = ""
    first_name: str = ""
    last_name: str = ""
    birth_year: str = ""
    birth_month: str = ""
    birth_day: str = ""
    country: str = ""
    phone: str = ""
    provider: str = ""
    domain: str = ""
    extra: dict = field(default_factory=dict)


@dataclass
class RegistrationResult:
    """注册结果"""
    success: bool = False
    email: str = ""
    password: str = ""
    username: str = ""
    provider: str = ""
    domain: str = ""
    error: str = ""
    final_url: str = ""
    screenshot_path: str = ""
    browser: Any = None  # 保留浏览器引用


# ──────────────────────────────────────────────
# 随机数据生成
# ──────────────────────────────────────────────

_FIRST_NAMES = [
    "Aiden", "Amelia", "Andrew", "Avery", "Blake", "Brooke", "Caleb", "Carter",
    "Chloe", "Claire", "Connor", "Dylan", "Eleanor", "Elliot", "Emma", "Ethan",
    "Grace", "Hannah", "Harper", "Hazel", "Henry", "Ian", "Iris", "Isaac",
    "Jack", "James", "Julian", "Landon", "Leah", "Leo", "Lily", "Logan",
    "Lucas", "Mason", "Maya", "Mia", "Miles", "Naomi", "Nolan", "Nora",
]

_LAST_NAMES = [
    "Adams", "Allen", "Bailey", "Baker", "Bennett", "Brooks", "Carter", "Clark",
    "Coleman", "Collins", "Cooper", "Davis", "Diaz", "Edwards", "Evans", "Fisher",
    "Flores", "Foster", "Garcia", "Gray", "Green", "Hall", "Harris", "Hayes",
    "Henderson", "Hill", "Howard", "Hughes", "Jackson", "James", "Johnson",
]


def random_string(length: int = 8) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


def random_password(length: int = 14) -> str:
    upper = random.choice(string.ascii_uppercase)
    lower = "".join(random.choices(string.ascii_lowercase, k=length - 4))
    digit = "".join(random.choices(string.digits, k=2))
    special = random.choice("!@#$%&*")
    base = upper + lower + digit + special
    return "".join(random.sample(base, len(base)))


def random_first_name() -> str:
    return random.choice(_FIRST_NAMES)


def random_last_name() -> str:
    return random.choice(_LAST_NAMES)


def random_birthdate() -> tuple[str, str, str]:
    """返回 (year, month, day) 字符串"""
    year = str(random.randint(1985, 2003))
    month = str(random.randint(1, 12))
    day = str(random.randint(1, 28))
    return year, month, day


def generate_account(provider: str, domain: str) -> AccountInfo:
    """生成随机账号数据"""
    fn = random_first_name()
    ln = random_last_name()
    user = f"{fn.lower()}{ln.lower()}{random_string(4)}"
    pwd = random_password()
    y, m, d = random_birthdate()
    return AccountInfo(
        username=user,
        email=f"{user}@{domain}",
        password=pwd,
        first_name=fn,
        last_name=ln,
        birth_year=y,
        birth_month=m,
        birth_day=d,
        provider=provider,
        domain=domain,
    )


# ──────────────────────────────────────────────
# 浏览器操控辅助
# ──────────────────────────────────────────────

def launch_browser(
    proxy: str = "",
    headless: bool = False,
    extensions: list[str] | None = None,
    browser_type: str = "chrome",
    window_size: tuple[int, int] = (1280, 900),
) -> CDPBrowser:
    """启动干净的 Chrome 浏览器"""
    config = CDPLaunchConfig(
        browser_type=browser_type,
        proxy=proxy,
        headless=headless,
        extensions=extensions or [],
        window_size=window_size,
    )
    browser = CDPBrowser(config)
    browser.launch()
    return browser


def wait_and_click(browser: CDPBrowser, selector: str, timeout: float = 10) -> bool:
    """等待元素出现并点击"""
    if not browser.wait_for_element(selector, timeout=timeout):
        return False
    nid = browser.query_selector(selector)
    if not nid:
        return False
    rect = browser.get_element_rect(nid)
    if not rect:
        return False
    browser.click_at(rect["center_x"], rect["center_y"])
    return True


def wait_and_type(browser: CDPBrowser, selector: str, text: str,
                  timeout: float = 10, clear_first: bool = True,
                  human_delay: bool = True) -> bool:
    """等待输入框出现并输入文字"""
    if not browser.wait_for_element(selector, timeout=timeout):
        return False
    if clear_first:
        browser.focus_element(selector)
        time.sleep(0.2)
        # 全选并清除
        safe_sel = selector.replace("'", "\\'")
        browser.evaluate(f"""
            (() => {{
                const el = document.querySelector('{safe_sel}');
                if (el) {{ el.value = ''; el.dispatchEvent(new Event('input', {{bubbles:true}})); }}
            }})()
        """)
        time.sleep(0.1)
    if human_delay:
        browser.click_at(0, 0)  # 先点一下确保焦点
        time.sleep(0.3)
        nid = browser.query_selector(selector)
        if nid:
            rect = browser.get_element_rect(nid)
            if rect:
                browser.click_at(rect["center_x"], rect["center_y"])
                time.sleep(0.2)
    browser.type_text(text, delay_ms=random.randint(60, 120) if human_delay else 30)
    return True


def set_value_and_dispatch(browser: CDPBrowser, selector: str, value: str) -> bool:
    """通过 JS 设置 input 值并触发事件（不触发键盘输入，更隐蔽）"""
    escaped_sel = selector.replace("'", "\\'")
    escaped_val = value.replace("'", "\\'")
    js = f"""
    (() => {{
        const el = document.querySelector('{escaped_sel}');
        if (!el) return false;
        const nativeSet = Object.getOwnPropertyDescriptor(
            window.HTMLInputElement.prototype, 'value'
        ).set;
        nativeSet.call(el, '{escaped_val}');
        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
        el.dispatchEvent(new Event('change', {{ bubbles: true }}));
        return true;
    }})()
    """
    return bool(browser.evaluate(js))


def select_dropdown(browser: CDPBrowser, selector: str, value: str) -> bool:
    """选择下拉框选项"""
    escaped_sel = selector.replace("'", "\\'")
    escaped_val = value.replace("'", "\\'")
    js = f"""
    (() => {{
        const el = document.querySelector('{escaped_sel}');
        if (!el) return false;
        el.value = '{escaped_val}';
        el.dispatchEvent(new Event('change', {{ bubbles: true }}));
        return true;
    }})()
    """
    return bool(browser.evaluate(js))


def select_dropdown_by_text(browser: CDPBrowser, selector: str, text: str) -> bool:
    """通过文本内容选择下拉框"""
    escaped_sel = selector.replace("'", "\\'")
    escaped_text = text.replace("'", "\\'")
    js = f"""
    (() => {{
        const el = document.querySelector('{escaped_sel}');
        if (!el) return false;
        for (const opt of el.options) {{
            if (opt.text.toLowerCase().includes('{escaped_text.lower()}')) {{
                el.value = opt.value;
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                return true;
            }}
        }}
        return false;
    }})()
    """
    return bool(browser.evaluate(js))


def click_submit(browser: CDPBrowser, selectors: list[str] | None = None) -> bool:
    """点击提交按钮"""
    default_selectors = [
        "button[type='submit']",
        "input[type='submit']",
        "button:not([type='button'])",
    ]
    for sel in (selectors or default_selectors):
        if wait_and_click(browser, sel, timeout=3):
            return True
    return False


# ──────────────────────────────────────────────
# 验证码检测与处理
# ──────────────────────────────────────────────

CAPTCHA_INDICATORS = [
    "captcha", "recaptcha", "hcaptcha", "funcaptcha",
    "arkose", "turnstile", "hsprotect", "verify you are human",
    "prove you're human", "press and hold", "我不是机器人",
    "人机验证", "安全验证",
]


def detect_captcha(browser: CDPBrowser) -> str | None:
    """检测页面上是否有验证码，返回类型或 None"""
    body = browser.get_body_text().lower()
    url = browser.get_url().lower()

    # 检查 iframe
    iframes = browser.evaluate("""
        (() => {
            return [...document.querySelectorAll('iframe')].map(f => f.src || '').join(' ');
        })()
    """) or ""

    haystack = f"{body} {url} {iframes}".lower()

    for indicator in CAPTCHA_INDICATORS:
        if indicator in haystack:
            return indicator
    return None


def handle_captcha_touch_press(browser: CDPBrowser, duration: float = 3.5) -> bool:
    """尝试用触摸长按方式通过 hsprotect 等人机验证"""
    # 查找验证按钮/区域
    js = """
    (() => {
        const selectors = [
            'iframe[src*="hsprotect"]',
            '[id*="captcha"]',
            '[class*="captcha"]',
            'iframe[title*="challenge"]',
            'iframe[title*="verification"]',
        ];
        for (const sel of selectors) {
            const el = document.querySelector(sel);
            if (el) {
                const rect = el.getBoundingClientRect();
                if (rect.width > 0 && rect.height > 0) {
                    return {
                        x: rect.x + rect.width / 2,
                        y: rect.y + rect.height / 2,
                        width: rect.width,
                        height: rect.height,
                        selector: sel
                    };
                }
            }
        }
        return null;
    })()
    """
    target = browser.evaluate(js)
    if not target or not isinstance(target, dict):
        return False

    x = target.get("x", 0)
    y = target.get("y", 0)
    if x <= 0 or y <= 0:
        return False

    logger.info("[CAPTCHA] 触摸长按验证 at (%.0f, %.0f)", x, y)
    browser.touch_long_press(x, y, duration=duration)
    time.sleep(2)
    return True


def wait_for_captcha_clear(browser: CDPBrowser, timeout: float = 120) -> bool:
    """等待验证码被清除（自动或手动）"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        captcha = detect_captcha(browser)
        if captcha is None:
            return True
        time.sleep(2)
    return False


# ──────────────────────────────────────────────
# 页面状态检测
# ──────────────────────────────────────────────

def page_contains_text(browser: CDPBrowser, texts: list[str]) -> str | None:
    """检查页面是否包含指定文本，返回匹配的文本"""
    body = browser.get_body_text().lower()
    for text in texts:
        if text.lower() in body:
            return text
    return None


def wait_for_any_text(browser: CDPBrowser, texts: list[str], timeout: float = 15) -> str | None:
    """等待页面出现指定文本中的任何一个"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        found = page_contains_text(browser, texts)
        if found:
            return found
        time.sleep(1)
    return None


def take_screenshot(browser: CDPBrowser, label: str, output_dir: str = "") -> str:
    """截图并保存"""
    if not output_dir:
        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "screenshots")
    os.makedirs(output_dir, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    path = os.path.join(output_dir, f"{label}_{ts}.png")
    try:
        browser.screenshot(path)
        return path
    except Exception as e:
        logger.warning("[SCREENSHOT] 截图失败: %s", e)
        return ""


# ──────────────────────────────────────────────
# 通用注册流程骨架
# ──────────────────────────────────────────────

def save_result(result: RegistrationResult, output_dir: str = ""):
    """保存注册结果到文件"""
    if not output_dir:
        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "registered_accounts")
    os.makedirs(output_dir, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    filename = f"{result.provider}_{ts}.json"
    path = os.path.join(output_dir, filename)
    data = {
        "success": result.success,
        "email": result.email,
        "password": result.password,
        "username": result.username,
        "provider": result.provider,
        "domain": result.domain,
        "error": result.error,
        "final_url": result.final_url,
        "timestamp": ts,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info("[RESULT] 保存到 %s", path)
    return path
