"""
CDP (Chrome DevTools Protocol) Browser Module

Launches a clean Chrome browser without automation flags and connects via CDP.
Uses the browser extension's detection logic for element finding.
Replaces Selenium WebDriver to avoid anti-bot detection.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
import threading
import time
import socket
import sys
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── Chrome Launch Configuration ──
DEFAULT_CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe"),
]


def _ensure_display_env():
    """确保 DISPLAY 环境变量已设置（用于 Xvfb 虚拟显示器）"""
    if not os.environ.get('DISPLAY'):
        # 检测常见的 Xvfb 显示器
        for disp in [':98', ':99', ':0']:
            try:
                result = subprocess.run(
                    ['xdpyinfo'],
                    env={**os.environ, 'DISPLAY': disp},
                    capture_output=True,
                    timeout=2
                )
                if result.returncode == 0:
                    os.environ['DISPLAY'] = disp
                    logger.info(f"[CDP] Auto-detected DISPLAY={disp}")
                    return
            except:
                pass
        logger.warning("[CDP] No X display detected, Chrome may fail to launch")

# 多浏览器路径配置（均为 Chromium 内核，支持 CDP）
BROWSER_PATHS = {
    "chrome": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe"),
    ],
    "edge": [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ],
    "brave": [
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        os.path.expanduser(r"~\AppData\Local\BraveSoftware\Brave-Browser\Application\brave.exe"),
    ],
    "chromium": [
        r"C:\Program Files\Chromium\Application\chrome.exe",
        os.path.expanduser(r"~\AppData\Local\Chromium\Application\chrome.exe"),
    ],
    "vivaldi": [
        r"C:\Program Files\Vivaldi\Application\vivaldi.exe",
        os.path.expanduser(r"~\AppData\Local\Vivaldi\Application\vivaldi.exe"),
    ],
    "thorium": [
        r"C:\Program Files\Thorium\Application\thorium.exe",
        os.path.expanduser(r"~\AppData\Local\Thorium\Application\thorium.exe"),
    ],
    "opera": [
        r"C:\Program Files\Opera\opera.exe",
        os.path.expanduser(r"~\AppData\Local\Programs\Opera\opera.exe"),
        os.path.expanduser(r"~\AppData\Local\Programs\Opera GX\opera.exe"),
    ],
    "ungoogled": [
        r"C:\Program Files\ungoogled-chromium\chrome.exe",
        os.path.expanduser(r"~\AppData\Local\ungoogled-chromium\Application\chrome.exe"),
    ],
    "cent": [
        r"C:\Program Files\CentBrowser\Application\chrome.exe",
        os.path.expanduser(r"~\AppData\Local\CentBrowser\Application\chrome.exe"),
    ],
    "360": [
        r"C:\Program Files (x86)\360\360se\360se.exe",
        r"C:\Program Files\360\360se\360se.exe",
        r"C:\Program Files (x86)\360\360chrome\360chrome.exe",
        r"C:\Program Files\360\360chrome\360chrome.exe",
    ],
    "qq": [
        r"C:\Program Files (x86)\Tencent\QQBrowser\QQBrowser.exe",
        r"C:\Program Files\Tencent\QQBrowser\QQBrowser.exe",
    ],
    "sogou": [
        r"C:\Program Files (x86)\SogouExplorer\SogouExplorer.exe",
        r"C:\Program Files\SogouExplorer\SogouExplorer.exe",
    ],
    "maxthon": [
        r"C:\Program Files\Maxthon\Bin\Maxthon.exe",
        os.path.expanduser(r"~\AppData\Local\Maxthon\Application\Maxthon.exe"),
    ],
    "yandex": [
        r"C:\Program Files (x86)\Yandex\YandexBrowser\Application\browser.exe",
        os.path.expanduser(r"~\AppData\Local\Yandex\YandexBrowser\Application\browser.exe"),
    ],
    "srware": [
        r"C:\Program Files\SRWare Iron\iron.exe",
        os.path.expanduser(r"~\AppData\Local\SRWare Iron\Application\iron.exe"),
    ],
    "slimjet": [
        r"C:\Program Files\Slimjet\slimjet.exe",
        os.path.expanduser(r"~\AppData\Local\Slimjet\Application\slimjet.exe"),
    ],
    # ── 指纹浏览器（Fingerprint Browsers）──
    "adspower": [
        os.path.expanduser(r"~\AppData\Local\AdsPower\AdsPower.exe"),
        r"C:\Program Files\AdsPower\AdsPower.exe",
        r"D:\AdsPower\AdsPower.exe",
        r"D:\AdsPower Global\AdsPower.exe",
    ],
    "multilogin": [
        os.path.expanduser(r"~\AppData\Local\Multilogin\Multilogin.exe"),
        r"C:\Program Files\Multilogin\Multilogin.exe",
    ],
    "bitbrowser": [
        os.path.expanduser(r"~\AppData\Local\BitBrowser\BitBrowser.exe"),
        r"C:\Program Files\BitBrowser\BitBrowser.exe",
        r"D:\BitBrowser\BitBrowser.exe",
    ],
    "vmlogin": [
        os.path.expanduser(r"~\AppData\Local\VMLogin\VMLogin.exe"),
        r"C:\Program Files\VMLogin\VMLogin.exe",
    ],
    "gologin": [
        os.path.expanduser(r"~\AppData\Local\GoLogin\GoLogin.exe"),
        r"C:\Program Files\GoLogin\GoLogin.exe",
    ],
    "dolphin_anty": [
        os.path.expanduser(r"~\AppData\Local\Dolphin Anty\Dolphin Anty.exe"),
        r"C:\Program Files\Dolphin Anty\Dolphin Anty.exe",
    ],
    "linken_sphere": [
        os.path.expanduser(r"~\AppData\Local\Linken Sphere\Linken Sphere.exe"),
        r"C:\Program Files\Linken Sphere\Linken Sphere.exe",
    ],
    "undetected_browser": [
        os.path.expanduser(r"~\AppData\Local\Undetected Browser\Undetected Browser.exe"),
        r"C:\Program Files\Undetected Browser\Undetected Browser.exe",
    ],
    "kameleo": [
        os.path.expanduser(r"~\AppData\Local\Kameleo\Kameleo.exe"),
        r"C:\Program Files\Kameleo\Kameleo.exe",
    ],
    "morelogin": [
        os.path.expanduser(r"~\AppData\Local\MoreLogin\MoreLogin.exe"),
        r"C:\Program Files\MoreLogin\MoreLogin.exe",
    ],
    "hubstudio": [
        os.path.expanduser(r"~\AppData\Local\HubStudio\HubStudio.exe"),
        r"C:\Program Files\HubStudio\HubStudio.exe",
    ],
    "clonbrowser": [
        os.path.expanduser(r"~\AppData\Local\ClonBrowser\ClonBrowser.exe"),
        r"C:\Program Files\ClonBrowser\ClonBrowser.exe",
    ],
    "maskfog": [
        os.path.expanduser(r"~\AppData\Local\MaskFog\MaskFog.exe"),
        r"C:\Program Files\MaskFog\MaskFog.exe",
    ],
    "lalicat": [
        os.path.expanduser(r"~\AppData\Local\Lalicat\Lalicat.exe"),
        r"C:\Program Files\Lalicat\Lalicat.exe",
    ],
}

# 浏览器下载信息 {browser_key: {"name": 显示名, "url": 下载页, "installer": 直链(可选)}}
BROWSER_DOWNLOAD_INFO = {
    "chrome": {"name": "Chrome", "url": "https://www.google.com/chrome/", "installer": "https://dl.google.com/chrome/install/latest/chrome_installer.exe"},
    "edge": {"name": "Edge", "url": "https://www.microsoft.com/edge"},
    "brave": {"name": "Brave", "url": "https://brave.com/download/", "installer": "https://laptop-updates.brave.com/latest/winx64/BraveBrowserSetup.exe"},
    "chromium": {"name": "Chromium", "url": "https://www.chromium.org/getting-involved/download-chromium/"},
    "vivaldi": {"name": "Vivaldi", "url": "https://vivaldi.com/download/"},
    "thorium": {"name": "Thorium", "url": "https://github.com/nicothin/nicothin.github.io/wiki/Thorium"},
    "opera": {"name": "Opera", "url": "https://www.opera.com/download"},
    # 指纹浏览器
    "adspower": {"name": "AdsPower", "url": "https://www.adspower.com/download"},
    "multilogin": {"name": "Multilogin", "url": "https://multilogin.com/download/"},
    "bitbrowser": {"name": "BitBrowser", "url": "https://www.bitbrowser.cn/download"},
    "vmlogin": {"name": "VMLogin", "url": "https://vmlogin.us/"},
    "gologin": {"name": "GoLogin", "url": "https://gologin.com/download"},
    "dolphin_anty": {"name": "Dolphin Anty", "url": "https://dolphin-anty.com/"},
    "linken_sphere": {"name": "Linken Sphere", "url": "https://linkensphere.com/"},
    "undetected_browser": {"name": "Undetected Browser", "url": "https://undetected.com/"},
    "kameleo": {"name": "Kameleo", "url": "https://kameleo.io/"},
    "morelogin": {"name": "MoreLogin", "url": "https://www.morelogin.com/"},
    "hubstudio": {"name": "HubStudio", "url": "https://www.hubstudio.com/"},
    "clonbrowser": {"name": "ClonBrowser", "url": "https://www.clonbrowser.com/"},
    "maskfog": {"name": "MaskFog", "url": "https://www.maskfog.com/"},
    "lalicat": {"name": "Lalicat", "url": "https://www.lalicat.com/"},
}

CDP_CHECK_TIMEOUT = 45  # seconds to wait for CDP to be ready (increased from 30 for stability)
CDP_CHECK_INTERVAL = 0.3
_LAUNCH_LOCK = threading.Lock()  # 并发启动Chrome时串行化，避免资源竞争导致崩溃


def detect_installed_browsers() -> dict:
    """检测系统上已安装的 Chromium 内核浏览器，返回 {browser_name: exe_path}"""
    import shutil
    installed = {}
    # 别名映射（和 _find_browser 保持一致）
    aliases = {
        "google-chrome": "chrome", "googlechrome": "chrome",
        "undetected-chrome": "chrome", "undetected_chrome": "chrome", "undetectedchrome": "chrome",
        "msedge": "edge", "microsoft-edge": "edge", "microsoftedge": "edge",
        "brave-browser": "brave", "bravebrowser": "brave",
        "opera-gx": "opera", "operagx": "opera",
        "ungoogled-chromium": "ungoogled", "ungoogledchromium": "ungoogled",
        "centbrowser": "cent", "cent-browser": "cent",
        "360se": "360", "360chrome": "360", "360-browser": "360",
        "qqbrowser": "qq", "qq-browser": "qq",
        "sogou-browser": "sogou", "sogoubrowser": "sogou",
        "maxthon-browser": "maxthon",
        "yandex-browser": "yandex", "yandexbrowser": "yandex",
        "srware-iron": "srware", "iron": "srware",
        "slimjet-browser": "slimjet",
    }
    exe_names = {
        "chrome": ["chrome", "google-chrome"],
        "edge": ["msedge", "microsoft-edge"],
        "brave": ["brave", "brave-browser"],
        "chromium": ["chromium"],
        "vivaldi": ["vivaldi"],
        "thorium": ["thorium"],
        "opera": ["opera"],
        "ungoogled": ["chrome"],
        "cent": ["chrome"],
        "360": ["360se", "360chrome"],
        "qq": ["QQBrowser"],
        "sogou": ["SogouExplorer"],
        "maxthon": ["Maxthon"],
        "yandex": ["browser"],
        "srware": ["iron"],
        "slimjet": ["slimjet"],
        "adspower": ["AdsPower"],
        "multilogin": ["Multilogin"],
        "bitbrowser": ["BitBrowser"],
        "vmlogin": ["VMLogin"],
        "gologin": ["GoLogin"],
        "dolphin_anty": ["Dolphin Anty"],
        "linken_sphere": ["Linken Sphere"],
        "undetected_browser": ["Undetected Browser"],
        "kameleo": ["Kameleo"],
        "morelogin": ["MoreLogin"],
        "hubstudio": ["HubStudio"],
        "clonbrowser": ["ClonBrowser"],
        "maskfog": ["MaskFog"],
        "lalicat": ["Lalicat"],
    }
    display_names = {
        "chrome": "Chrome", "edge": "Edge", "brave": "Brave",
        "chromium": "Chromium", "vivaldi": "Vivaldi", "thorium": "Thorium",
        "opera": "Opera / Opera GX", "ungoogled": "Ungoogled Chromium",
        "cent": "Cent Browser", "360": "360 浏览器", "qq": "QQ 浏览器",
        "sogou": "搜狗浏览器", "maxthon": "傲游浏览器", "yandex": "Yandex Browser",
        "srware": "SRWare Iron", "slimjet": "Slimjet",
        "adspower": "AdsPower", "multilogin": "Multilogin", "bitbrowser": "BitBrowser",
        "vmlogin": "VMLogin", "gologin": "GoLogin", "dolphin_anty": "Dolphin Anty",
        "linken_sphere": "Linken Sphere", "undetected_browser": "Undetected Browser",
        "kameleo": "Kameleo", "morelogin": "MoreLogin", "hubstudio": "HubStudio",
        "clonbrowser": "ClonBrowser", "maskfog": "MaskFog", "lalicat": "Lalicat",
    }
    for btype in BROWSER_PATHS:
        # 检查硬编码路径
        for path in BROWSER_PATHS[btype]:
            if os.path.isfile(path):
                installed[btype] = {"path": path, "name": display_names.get(btype, btype)}
                break
        if btype in installed:
            continue
        # 检查 PATH
        for name in exe_names.get(btype, []):
            found = shutil.which(name)
            if found:
                installed[btype] = {"path": found, "name": display_names.get(btype, btype)}
                break
    return installed


def _find_browser(browser_type: str = "chrome") -> str:
    """Find browser executable path by type. All Chromium-based browsers with CDP support."""
    browser_type = (browser_type or "chrome").strip().lower()
    # 别名映射
    aliases = {
        "google-chrome": "chrome", "googlechrome": "chrome",
        "undetected-chrome": "chrome", "undetected_chrome": "chrome", "undetectedchrome": "chrome",
        "msedge": "edge", "microsoft-edge": "edge", "microsoftedge": "edge",
        "brave-browser": "brave", "bravebrowser": "brave",
        "opera-gx": "opera", "operagx": "opera",
        "ungoogled-chromium": "ungoogled", "ungoogledchromium": "ungoogled",
        "centbrowser": "cent", "cent-browser": "cent",
        "360se": "360", "360chrome": "360", "360-browser": "360", "360安全浏览器": "360", "360极速浏览器": "360",
        "qqbrowser": "qq", "qq-browser": "qq", "qq浏览器": "qq",
        "sogou-browser": "sogou", "sogoubrowser": "sogou", "搜狗浏览器": "sogou",
        "maxthon-browser": "maxthon", "傲游": "maxthon",
        "yandex-browser": "yandex", "yandexbrowser": "yandex",
        "srware-iron": "srware", "iron": "srware",
        "slimjet-browser": "slimjet",
        "firefox": "chrome",  # Firefox 不支持 CDP，回退到 Chrome
        # 指纹浏览器别名
        "adspower-global": "adspower", "adspower global": "adspower",
        "dolphin-anty": "dolphin_anty", "dolphinanty": "dolphin_anty",
        "linken-sphere": "linken_sphere", "linkensphere": "linken_sphere",
        "undetected-browser": "undetected_browser", "undetectedbrowser": "undetected_browser",
    }
    browser_type = aliases.get(browser_type, browser_type)

    paths = BROWSER_PATHS.get(browser_type, BROWSER_PATHS["chrome"])
    for path in paths:
        if os.path.isfile(path):
            return path
    # Try PATH
    import shutil
    exe_names = {
        "chrome": ["chrome", "google-chrome"],
        "edge": ["msedge", "microsoft-edge"],
        "brave": ["brave", "brave-browser"],
        "chromium": ["chromium"],
        "vivaldi": ["vivaldi"],
        "thorium": ["thorium"],
        "opera": ["opera"],
        "ungoogled": ["chrome"],
        "cent": ["chrome"],
        "360": ["360se", "360chrome"],
        "qq": ["QQBrowser"],
        "sogou": ["SogouExplorer"],
        "maxthon": ["Maxthon"],
        "yandex": ["browser"],
        "srware": ["iron"],
        "slimjet": ["slimjet"],
        "adspower": ["AdsPower"],
        "multilogin": ["Multilogin"],
        "bitbrowser": ["BitBrowser"],
        "vmlogin": ["VMLogin"],
        "gologin": ["GoLogin"],
        "dolphin_anty": ["Dolphin Anty"],
        "linken_sphere": ["Linken Sphere"],
        "undetected_browser": ["Undetected Browser"],
        "kameleo": ["Kameleo"],
        "morelogin": ["MoreLogin"],
        "hubstudio": ["HubStudio"],
        "clonbrowser": ["ClonBrowser"],
        "maskfog": ["MaskFog"],
        "lalicat": ["Lalicat"],
    }
    for name in exe_names.get(browser_type, ["chrome"]):
        found = shutil.which(name)
        if found:
            return found
    if sys.platform != "win32":
        linux_candidates = [
            "/usr/bin/google-chrome-stable",
            "/usr/bin/google-chrome",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/snap/bin/chromium",
        ]
        if browser_type in ("chrome", "chromium"):
            for p in linux_candidates:
                if os.path.isfile(p) and os.access(p, os.X_OK):
                    return p
            for name in ("google-chrome-stable", "google-chrome", "chromium", "chromium-browser"):
                found = shutil.which(name)
                if found:
                    return found
    raise FileNotFoundError(
        f"浏览器 '{browser_type}' 未找到。请确认已安装该浏览器，或在页面刷新后选择其他已安装的浏览器。"
    )

def _find_chrome() -> str:
    """Find Chrome executable path (legacy compatibility)."""
    return _find_browser("chrome")


def _find_free_port() -> int:
    """Find a free TCP port for CDP."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_cdp(port: int, timeout: float = CDP_CHECK_TIMEOUT) -> dict:
    """Wait for Chrome CDP to be ready and return the WebSocket debug URL."""
    deadline = time.monotonic() + timeout
    url = f"http://127.0.0.1:{port}/json/version"
    while time.monotonic() < deadline:
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=2) as resp:
                data = json.loads(resp.read())
                ws_url = data.get("webSocketDebuggerUrl", "")
                if ws_url:
                    logger.info("[CDP] Chrome ready, ws=%s", ws_url[:80])
                    return data
        except Exception:
            pass
        time.sleep(CDP_CHECK_INTERVAL)
    raise TimeoutError(f"Chrome CDP not ready after {timeout}s on port {port}")


def _get_page_ws_url(port: int) -> str:
    """Get the WebSocket URL for the first page tab (带重试，并发启动时需要更长时间）。"""
    url = f"http://127.0.0.1:{port}/json"
    for attempt in range(6):  # 最多重试6次
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=8) as resp:
                tabs = json.loads(resp.read())
                for tab in tabs:
                    if tab.get("type") == "page":
                        return tab["webSocketDebuggerUrl"]
        except Exception as e:
            if attempt < 5:
                time.sleep(1)
                continue
            logger.warning("[CDP] Failed to get page WS URL: %s", e)
        logger.warning("[CDP] Failed to get page WS URL: %s", e)
    return ""


@dataclass
class CDPLaunchConfig:
    """Configuration for launching Chrome/Chromium browser with CDP."""
    chrome_path: str = ""
    browser_type: str = "chrome"  # chrome, edge, brave, chromium, vivaldi, thorium
    debug_port: int = 0
    user_data_dir: str = ""
    proxy: str = ""           # No-auth proxy URL for --proxy-server
    proxy_auth_url: str = ""  # Full proxy URL with credentials for Fetch auth
    headless: bool = False
    window_size: tuple[int, int] = (1280, 900)
    window_position: tuple[int, int] = (0, 0)  # 窗口左上角位置（并发时错开：0=0,50  1=400,50  2=800,50 ...）
    extra_args: list[str] = field(default_factory=list)
    extensions: list[str] = field(default_factory=list)


class CDPBrowser:
    """
    Clean Chrome browser controlled via CDP.
    
    Key differences from Selenium:
    - No automation flags (no --enable-automation, no navigator.webdriver)
    - Uses CDP directly for DOM queries and input dispatch
    - OS-level input for clicks (bypasses JS-level detection)
    - Touch events for CAPTCHA long-press
    """

    def __init__(self, config: CDPLaunchConfig | None = None):
        self.config = config or CDPLaunchConfig()
        self._process: subprocess.Popen | None = None
        self._ws: Any = None
        self._ws_url: str = ""
        self._port: int = 0
        self._msg_id: int = 0
        self._callbacks: dict[int, Any] = {}
        self._events: list[dict] = []
        self._event_handlers: dict[str, list] = {}
        self._listen_thread: Any = None
        self._connected: bool = False
        self._temp_dir: str = ""

    def launch(self) -> "CDPBrowser":
        """Launch browser and connect via CDP."""
        # 确保 DISPLAY 环境变量已设置（Xvfb 虚拟显示器）
        if 'DISPLAY' not in os.environ or not os.environ['DISPLAY']:
            # 尝试检测 Xvfb 显示器
            for _disp in [':98', ':99', ':0']:
                try:
                    _r = subprocess.run(['xdpyinfo'], env={**os.environ, 'DISPLAY': _disp}, capture_output=True, timeout=2)
                    if _r.returncode == 0:
                        os.environ['DISPLAY'] = _disp
                        logger.info(f"[CDP] Auto-detected DISPLAY={_disp}")
                        break
                except Exception:
                    pass
            else:
                logger.warning("[CDP] No X display detected, Chrome may fail to launch")
        
        chrome_path = self.config.chrome_path or _find_browser(self.config.browser_type)
        logger.info("[CDP] Browser type requested: '%s', resolved path: %s", self.config.browser_type, chrome_path)
        self._port = self.config.debug_port or _find_free_port()

        # Create temp user data dir if not specified
        if not self.config.user_data_dir:
            self._temp_dir = tempfile.mkdtemp(prefix="邮箱注册_chrome_")
            user_data_dir = self._temp_dir
        else:
            user_data_dir = self.config.user_data_dir

        # ── Resolve proxy: start relay if auth needed ──
        effective_proxy = self.config.proxy  # protocol://host:port (no auth)
        proxy_auth_url = self.config.proxy_auth_url
        if proxy_auth_url:
            try:
                from .proxy_utils import parse_proxy
                proxy_info = parse_proxy(proxy_auth_url)
                if proxy_info and proxy_info.has_auth:
                    relay_port = self._start_proxy_relay(
                        proxy_info.host, proxy_info.port,
                        proxy_info.username, proxy_info.password,
                        proxy_info.protocol
                    )
                    if relay_port:
                        effective_proxy = f"http://127.0.0.1:{relay_port}"
                        self._relay_port = relay_port
                        logger.info("[CDP] Using local relay proxy: %s -> %s:%d", effective_proxy, proxy_info.host, proxy_info.port)
            except Exception as exc:
                logger.warning("[CDP] Failed to start relay, using direct proxy: %s", exc)

        # Build Chrome args - NO automation flags, 无痕模式
        args = [
            chrome_path,
            f"--remote-debugging-port={self._port}",
            f"--user-data-dir={user_data_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-default-apps",
            "--disable-popup-blocking",
            "--disable-translate",
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--disable-features=TranslateUI,BuiltInDnsClient",
            "--disable-hang-monitor",
            "--remote-allow-origins=*",
            f"--window-size={self.config.window_size[0]},{self.config.window_size[1]}",
            f"--window-position={self.config.window_position[0]},{self.config.window_position[1]}",
            "--incognito",
            # 稳定性增强标志
            "--disable-gpu",
            "--disable-software-rasterizer",
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-accelerated-2d-canvas",
            "--disable-accelerated-video-decode",
            "--disable-component-update",
            "--disable-background-networking",
            "--metrics-recording-only",
            "--disable-sync",
            # ── 无痕：禁止缓存和密码保存 ──
            "--disk-cache-size=0",
            "--disable-save-password-bubble",
            "--disable-password-generation",
            "--password-store=basic",
            "--disable-sync",
            "--disable-client-side-phishing-detection",
            "--no-pings",
        ]

        if self.config.headless:
            args.append("--headless=new")

        if effective_proxy:
            args.append(f"--proxy-server={effective_proxy}")
            # 排除所有本地回环流量（CDP调试端口、本地回调服务器等）
            # <-loopback> 是 Chrome 特殊标记，匹配 localhost/127.0.0.1/::1
            args.append(f"--proxy-bypass-list=<-loopback>")

        # Load extensions (the browser extension for enhanced detection)
        if self.config.extensions:
            ext_paths = ",".join(self.config.extensions)
            args.append(f"--load-extension={ext_paths}")
            args.append("--disable-extensions-except=" + ext_paths)

        args.extend(self.config.extra_args)

        logger.info("[CDP] Launching %s on port %d", os.path.basename(chrome_path), self._port)
        logger.debug("[CDP] Args: %s", " ".join(args[:10]) + "...")

        # 并发启动锁：串行化Chrome启动，避免多实例同时启动导致资源竞争崩溃
        # 带重试：并发时 Chrome 偶尔崩溃（exit code 1），最多重试 3 次
        MAX_LAUNCH_RETRIES = 3
        chrome_err_file = None
        for _launch_attempt in range(MAX_LAUNCH_RETRIES):
            with _LAUNCH_LOCK:
                err_dir = Path("/home/workspace/Email-Register/runtime_outlook/logs")
                err_dir.mkdir(parents=True, exist_ok=True)
                chrome_err_path = err_dir / f"chrome_{self._port}_{_launch_attempt + 1}.err"
                chrome_err_file = open(chrome_err_path, "w", encoding="utf-8")
                # 确保环境变量包含 DISPLAY（从父进程继承或显式设置）
                launch_env = os.environ.copy()
                if 'DISPLAY' not in launch_env:
                    launch_env['DISPLAY'] = ':98'  # 默认 Xvfb 显示
                
                self._process = subprocess.Popen(
                    args,
                    stdout=subprocess.DEVNULL,
                    stderr=chrome_err_file,
                    env=launch_env,
                    start_new_session=True,  # 独立进程组，方便整棵树清理
                )
                # 等待一小段时间让Chrome进程稳定，再启动下一个
                time.sleep(2)

            # 检查 Chrome 是否立即崩溃
            if self._process.poll() is not None:
                exit_code = self._process.returncode
                try:
                    chrome_err_file.close()
                except Exception:
                    pass
                logger.warning("[CDP] Chrome exited immediately with code %d (attempt %d/%d), stderr=%s",
                               exit_code, _launch_attempt + 1, MAX_LAUNCH_RETRIES, chrome_err_path)
                if _launch_attempt < MAX_LAUNCH_RETRIES - 1:
                    # 清理旧的 temp dir，重新创建
                    if self._temp_dir:
                        import shutil
                        shutil.rmtree(self._temp_dir, ignore_errors=True)
                        self._temp_dir = tempfile.mkdtemp(prefix="邮箱注册_chrome_")
                        # 更新 args 中的 user-data-dir
                        for i, a in enumerate(args):
                            if a.startswith("--user-data-dir="):
                                args[i] = f"--user-data-dir={self._temp_dir}"
                                break
                    # 换一个新端口
                    self._port = _find_free_port()
                    for i, a in enumerate(args):
                        if a.startswith("--remote-debugging-port="):
                            args[i] = f"--remote-debugging-port={self._port}"
                            break
                    # 更新 bypass list
                    for i, a in enumerate(args):
                        if a.startswith("--proxy-bypass-list="):
                            args[i] = "--proxy-bypass-list=<-loopback>"
                            break
                    time.sleep(1)
                    continue
                else:
                    raise RuntimeError(f"Chrome failed to launch after {MAX_LAUNCH_RETRIES} attempts (exit code {exit_code})")
            else:
                break  # Chrome launched successfully

        # Wait for CDP to be ready
        _wait_for_cdp(self._port)

        # Connect WebSocket
        self._connect_ws()

        # 清除缓存和 Cookie（确保全新无痕）
        try:
            self._send_cmd("Network.enable")
            self._send_cmd("Network.clearBrowserCache")
            self._send_cmd("Network.clearBrowserCookies")
        except Exception:
            pass

        # Enable necessary CDP domains
        self._send_cmd("Runtime.enable")
        self._send_cmd("DOM.enable")
        self._send_cmd("Page.enable")
        
        # Monitor console and dialogs for debugging
        try:
            self._send_cmd("Log.enable")
            self._event_handlers.setdefault("Log.entryAdded", []).append(
                lambda e: logger.info("[CONSOLE] %s", str(e.get('params', {}).get('entry', {}).get('text', ''))[:200])
            )
            self._event_handlers.setdefault("Runtime.consoleAPICalled", []).append(
                lambda e: logger.info("[CONSOLE] %s", str([a.get('value','') for a in e.get('params', {}).get('args', [])])[:200])
            )
            self._event_handlers.setdefault("Page.javascriptDialogOpening", []).append(
                lambda e: logger.warning("[DIALOG] %s: %s", e.get('params',{}).get('type',''), e.get('params',{}).get('message','')[:200])
            )
            # Monitor for target crash or close
            self._event_handlers.setdefault("Inspector.detached", []).append(
                lambda e: logger.warning("[CDP] Inspector detached: %s", e.get('params',{}).get('reason',''))
            )
            self._event_handlers.setdefault("Target.targetDestroyed", []).append(
                lambda e: logger.warning("[CDP] Target destroyed")
            )
        except Exception as e:
            logger.debug("Console monitoring setup failed: %s", e)
        
        # Monitor Chrome process
        import threading
        def _monitor_process():
            if self._process:
                ret = self._process.wait()
                logger.warning("[CDP] Chrome process exited with code %s", ret)
        self._monitor_thread = threading.Thread(target=_monitor_process, daemon=True)
        self._monitor_thread.start()

        # ── 并发安全: 用 CDP 精确设置窗口位置和大小 ──
        # 启动参数 --window-position 有时不可靠，这里用 CDP 命令精确控制
        if self.config.window_position != (0, 0):
            try:
                # 获取当前窗口 target ID
                targets = self._send_cmd("Target.getTargets")
                window_target = None
                for t in (targets or {}).get("targetInfos", []):
                    if t.get("type") == "page":
                        window_target = t.get("targetId")
                        break
                if window_target:
                    # 获取 window ID
                    result = self._send_cmd("Browser.getWindowForTarget", {"targetId": window_target})
                    window_id = result.get("windowId")
                    if window_id is not None:
                        self._send_cmd("Browser.setWindowBounds", {
                            "windowId": window_id,
                            "bounds": {
                                "left": self.config.window_position[0],
                                "top": self.config.window_position[1],
                                "width": self.config.window_size[0],
                                "height": self.config.window_size[1],
                                "windowState": "normal",
                            }
                        })
                        logger.info("[CDP] Window positioned at (%d, %d) size=%dx%d",
                                    self.config.window_position[0], self.config.window_position[1],
                                    self.config.window_size[0], self.config.window_size[1])
            except Exception as e:
                logger.debug("[CDP] Window positioning via CDP failed: %s", e)

        # Set up proxy auth if proxy has credentials (Fetch domain fallback)
        # Only needed if relay didn't start
        if not getattr(self, '_relay_port', None):
            self._setup_proxy_auth_fallback()

        # Remove webdriver flag via CDP
        self._hide_automation()

        self._connected = True
        logger.info("[CDP] Browser launched and connected")
        return self

    def _connect_ws(self):
        """Connect to Chrome via WebSocket (带重试，并发启动时Chrome页面加载较慢）。"""
        ws_url = _get_page_ws_url(self._port)
        if not ws_url:
            # If no page tab, create one and retry
            for retry in range(3):
                try:
                    self._send_cmd_via_http("Target.createTarget", {"url": "about:blank"})
                except Exception:
                    pass
                time.sleep(1 + retry)
                ws_url = _get_page_ws_url(self._port)
                if ws_url:
                    break
        if not ws_url:
            raise RuntimeError("Cannot find Chrome page tab for CDP")

        # 关闭旧 WebSocket（如果有的话，重连场景）
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
            self._ws = None

        import websocket
        self._ws = websocket.create_connection(ws_url, timeout=30, ping_interval=15, ping_timeout=10)
        self._ws_url = ws_url
        logger.info("[CDP] WebSocket connected to %s", ws_url[:80])

        # Start/restart listening thread
        if self._listen_thread and self._listen_thread.is_alive():
            # 旧 listen 线程仍在运行，等它退出（因为旧 _ws 已关闭）
            self._listen_thread.join(timeout=3)
        self._listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._listen_thread.start()
        self._connected = True

    def _listen_loop(self):
        """Background thread to receive CDP messages."""
        while self._ws:
            try:
                msg = self._ws.recv()
                if not msg:
                    continue
                data = json.loads(msg)
                if "id" in data:
                    # Response to a command
                    cb = self._callbacks.pop(data["id"], None)
                    if cb:
                        cb(data)
                elif "method" in data:
                    # Event
                    self._events.append(data)
                    handlers = self._event_handlers.get(data["method"], [])
                    for handler in handlers:
                        try:
                            handler(data)
                        except Exception as e:
                            logger.warning("[CDP] Event handler error: %s", e)
            except Exception as e:
                if self._ws:
                    logger.debug("[CDP] Listen error: %s", e)
                break
        logger.info("[CDP] Listen loop exited")
        # 标记连接已断开
        self._connected = False

    def _send_cmd(self, method: str, params: dict | None = None, timeout: float = 30) -> dict:
        """Send a CDP command and wait for response. Auto-reconnects if WebSocket is closed."""
        import websocket as _ws_mod

        for attempt in range(2):
            self._msg_id += 1
            msg_id = self._msg_id
            msg = {"id": msg_id, "method": method}
            if params:
                msg["params"] = params

            result = {}
            event = __import__("threading").Event()

            def callback(data):
                nonlocal result
                result = data
                event.set()

            self._callbacks[msg_id] = callback

            try:
                self._ws.send(json.dumps(msg))
            except (_ws_mod.WebSocketConnectionClosedException, BrokenPipeError, OSError) as e:
                self._callbacks.pop(msg_id, None)
                if attempt == 0:
                    # First attempt: try to reconnect
                    logger.warning("[CDP] WebSocket closed, attempting reconnect...")
                    try:
                        self._connect_ws()
                        logger.info("[CDP] Reconnected successfully")
                        continue
                    except Exception as re:
                        raise RuntimeError(f"CDP send failed (reconnect also failed): {re}") from e
                raise RuntimeError(f"CDP send failed: {e}") from e
            except Exception as e:
                self._callbacks.pop(msg_id, None)
                raise RuntimeError(f"CDP send failed: {e}") from e

            if not event.wait(timeout):
                self._callbacks.pop(msg_id, None)
                raise TimeoutError(f"CDP command timeout: {method}")

            if "error" in result:
                raise RuntimeError(f"CDP error: {result['error']}")

            return result.get("result", {})

    def _send_cmd_via_http(self, method: str, params: dict | None = None):
        """Send a CDP command via HTTP (for pre-WebSocket commands)."""
        url = f"http://127.0.0.1:{self._port}/json/protocol"
        # Use the browser-level WS
        browser_ws_url = ""
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{self._port}/json/version")
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read())
                browser_ws_url = data.get("webSocketDebuggerUrl", "")
        except Exception:
            pass

        if not browser_ws_url:
            return

        import websocket
        ws = websocket.create_connection(browser_ws_url, timeout=10)
        try:
            self._msg_id += 1
            msg = {"id": self._msg_id, "method": method}
            if params:
                msg["params"] = params
            ws.send(json.dumps(msg))
            ws.recv()
        finally:
            ws.close()

    def _setup_proxy_auth_fallback(self):
        """Fallback: Set up proxy auth via CDP Fetch domain (when relay is not available)."""
        proxy_url = self.config.proxy_auth_url or self.config.proxy
        if not proxy_url:
            return
        
        username = ""
        password = ""
        try:
            from .proxy_utils import parse_proxy
            proxy_info = parse_proxy(proxy_url)
            if proxy_info:
                username = proxy_info.username
                password = proxy_info.password
        except Exception:
            pass
        
        if not username:
            return
        
        try:
            self._send_cmd("Fetch.enable", {
                "handleAuthRequests": True
            })
            logger.info("[CDP] Fetch.enable fallback activated for proxy auth (user=%s)", username)
            self._proxy_username = username
            self._proxy_password = password
            self._event_handlers.setdefault("Fetch.authRequired", []).append(
                self._handle_proxy_auth
            )
        except Exception as exc:
            logger.warning("[CDP] Failed to set up Fetch auth fallback: %s", exc)
    
    def _start_proxy_relay(self, upstream_host: str, upstream_port: int,
                           username: str, password: str, protocol: str = "http") -> int | None:
        """Start a local HTTP CONNECT proxy relay.
        
        Returns the local port number, or None if failed.
        The relay handles upstream proxy authentication transparently.
        """
        import socket
        import threading
        import base64
        
        # Find a free port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            local_port = s.getsockname()[1]
        
        auth_b64 = base64.b64encode(f"{username}:{password}".encode()).decode()
        
        def _handle_client(client_sock):
            try:
                request = b""
                while b"\r\n\r\n" not in request:
                    chunk = client_sock.recv(4096)
                    if not chunk:
                        return
                    request += chunk
                
                first_line = request.split(b"\r\n")[0].decode("utf-8", errors="replace")
                
                if not first_line.upper().startswith("CONNECT"):
                    # Plain HTTP request
                    upstream = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    upstream.settimeout(15)
                    try:
                        upstream.connect((upstream_host, upstream_port))
                        modified = request.replace(b"\r\n", f"\r\nProxy-Authorization: Basic {auth_b64}\r\n".encode(), 1)
                        upstream.sendall(modified)
                        while True:
                            data = upstream.recv(8192)
                            if not data:
                                break
                            client_sock.sendall(data)
                    except Exception:
                        pass
                    finally:
                        try: client_sock.close()
                        except: pass
                        try: upstream.close()
                        except: pass
                    return
                
                # CONNECT method
                parts = first_line.split()
                target = parts[1] if len(parts) >= 2 else ""
                host_part, _, port_part = target.rpartition(":")
                target_port = int(port_part) if port_part else 443
                
                upstream = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                upstream.settimeout(15)
                try:
                    upstream.connect((upstream_host, upstream_port))
                    connect_req = (
                        f"CONNECT {target} HTTP/1.1\r\n"
                        f"Host: {target}\r\n"
                        f"Proxy-Authorization: Basic {auth_b64}\r\n"
                        f"\r\n"
                    )
                    upstream.sendall(connect_req.encode())
                    
                    resp = b""
                    while b"\r\n\r\n" not in resp:
                        chunk = upstream.recv(4096)
                        if not chunk:
                            break
                        resp += chunk
                    
                    if b"200" in resp.split(b"\r\n")[0]:
                        client_sock.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                        # Bidirectional relay
                        def _forward(src, dst):
                            try:
                                while True:
                                    data = src.recv(65536)
                                    if not data:
                                        break
                                    dst.sendall(data)
                            except Exception:
                                pass
                            try: src.close()
                            except: pass
                            try: dst.close()
                            except: pass
                        t1 = threading.Thread(target=_forward, args=(client_sock, upstream), daemon=True)
                        t2 = threading.Thread(target=_forward, args=(upstream, client_sock), daemon=True)
                        t1.start()
                        t2.start()
                    else:
                        client_sock.sendall(resp)
                        client_sock.close()
                        upstream.close()
                except Exception as e:
                    logger.warning("[RELAY] Upstream connect failed: %s", e)
                    try: client_sock.sendall(b"HTTP/502 Connection failed\r\n\r\n")
                    except: pass
                    try: client_sock.close()
                    except: pass
                    try: upstream.close()
                    except: pass
            except Exception as e:
                logger.warning("[RELAY] Handler error: %s", e)
                try: client_sock.close()
                except: pass
        
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind(("127.0.0.1", local_port))
            server.listen(20)
        except Exception as exc:
            server.close()
            raise exc
        
        self._relay_server = server
        
        def _accept_loop():
            while True:
                try:
                    client, addr = server.accept()
                    threading.Thread(target=_handle_client, args=(client,), daemon=True).start()
                except OSError:
                    break
                except Exception as e:
                    logger.warning("[RELAY] Accept error: %s", e)
        
        self._relay_thread = threading.Thread(target=_accept_loop, daemon=True)
        self._relay_thread.start()
        
        return local_port

    def _handle_proxy_auth(self, event):
        """Handle proxy 407 auth challenge via CDP Fetch domain.
        
        IMPORTANT: This runs on the WebSocket listen thread. We must NOT call
        _send_cmd() here because it waits for a response that can only be
        received by the listen thread → deadlock.
        Instead, spawn a separate thread to send the auth response.
        """
        import threading as _thr
        request_id = event.get("params", {}).get("requestId", "")
        username = getattr(self, "_proxy_username", "")
        password = getattr(self, "_proxy_password", "")
        
        def _respond():
            try:
                self._send_cmd("Fetch.continueWithAuth", {
                    "requestId": request_id,
                    "authChallengeResponse": {
                        "response": "ProvideCredentials",
                        "username": username,
                        "password": password,
                    }
                })
                logger.info("[CDP] Proxy auth challenge responded (user=%s)", username)
            except Exception as exc:
                logger.warning("[CDP] Proxy auth handler error: %s", exc)
        
        _thr.Thread(target=_respond, daemon=True).start()

    def _hide_automation(self):
        """Remove automation markers via CDP Runtime.evaluate."""
        js = """
        // Remove webdriver flag
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        
        // Remove chrome automation info
        if (window.chrome) {
            delete window.chrome.csi;
            delete window.chrome.loadTimes;
            delete window.chrome.app;
        }
        
        // Override permissions query
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
        
        // Override plugins
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],
        });
        
        // Override languages
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en'],
        });
        """
        try:
            self._send_cmd("Runtime.evaluate", {"expression": js, "returnByValue": True})
            logger.info("[CDP] Automation markers hidden")
        except Exception as e:
            logger.warning("[CDP] Failed to hide automation: %s", e)

    def navigate(self, url: str, wait_for_load: bool = True, timeout: float = 30):
        """Navigate to a URL."""
        logger.info("[CDP] Navigating to %s", url[:100])
        self._send_cmd("Page.navigate", {"url": url}, timeout=timeout)
        if wait_for_load:
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                result = self._send_cmd("Runtime.evaluate", {
                    "expression": "document.readyState",
                    "returnByValue": True
                })
                state = result.get("result", {}).get("value", "")
                if state in ("complete", "interactive"):
                    return
                time.sleep(0.3)
            logger.warning("[CDP] Page load timeout after %ss", timeout)

    def get_url(self) -> str:
        """Get current page URL."""
        result = self._send_cmd("Runtime.evaluate", {
            "expression": "window.location.href",
            "returnByValue": True
        })
        return result.get("result", {}).get("value", "")

    def get_title(self) -> str:
        """Get current page title."""
        result = self._send_cmd("Runtime.evaluate", {
            "expression": "document.title",
            "returnByValue": True
        })
        return result.get("result", {}).get("value", "")

    def evaluate(self, expression: str, return_by_value: bool = True) -> Any:
        """Evaluate JavaScript expression."""
        result = self._send_cmd("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": return_by_value,
            "awaitPromise": True,
        })
        return result.get("result", {}).get("value")

    def query_selector(self, selector: str) -> int | None:
        """Query a single element, return node ID."""
        try:
            doc = self._send_cmd("DOM.getDocument", {"depth": 0})
            node_id = doc["root"]["nodeId"]
            result = self._send_cmd("DOM.querySelector", {
                "nodeId": node_id,
                "selector": selector
            })
            nid = result.get("nodeId", 0)
            return nid if nid > 0 else None
        except Exception:
            return None

    def query_selector_all(self, selector: str) -> list[int]:
        """Query all matching elements, return node IDs."""
        try:
            doc = self._send_cmd("DOM.getDocument", {"depth": 0})
            node_id = doc["root"]["nodeId"]
            result = self._send_cmd("DOM.querySelectorAll", {
                "nodeId": node_id,
                "selector": selector
            })
            return result.get("nodeIds", [])
        except Exception:
            return []

    def get_element_rect(self, node_id: int) -> dict | None:
        """Get element bounding rectangle via CDP."""
        try:
            result = self._send_cmd("DOM.getBoxModel", {"nodeId": node_id})
            model = result.get("model", {})
            content = model.get("content", [])
            if len(content) >= 8:
                # content is [x1,y1, x2,y2, x3,y3, x4,y4]
                xs = [content[i] for i in range(0, 8, 2)]
                ys = [content[i] for i in range(1, 8, 2)]
                return {
                    "x": min(xs),
                    "y": min(ys),
                    "width": max(xs) - min(xs),
                    "height": max(ys) - min(ys),
                    "center_x": (min(xs) + max(xs)) / 2,
                    "center_y": (min(ys) + max(ys)) / 2,
                }
        except Exception:
            pass
        return None

    def get_element_rect_js(self, selector: str) -> dict | None:
        """Get element bounding rect via JS (fallback)."""
        escaped_sel = selector.replace("'", "\\'")
        js = f"""
        (() => {{
            const el = document.querySelector('{escaped_sel}');
            if (!el) return null;
            const rect = el.getBoundingClientRect();
            return {{
                x: rect.x, y: rect.y,
                width: rect.width, height: rect.height,
                center_x: rect.x + rect.width / 2,
                center_y: rect.y + rect.height / 2,
            }};
        }})()
        """
        result = self.evaluate(js)
        return result if isinstance(result, dict) else None

    def is_element_visible(self, node_id: int) -> bool:
        """Check if element is visible."""
        rect = self.get_element_rect(node_id)
        if not rect:
            return False
        return rect["width"] > 0 and rect["height"] > 0

    def click_at(self, x: float, y: float, button: str = "left"):
        """Click at screen coordinates using CDP Input.dispatchMouseEvent."""
        # Mouse pressed
        self._send_cmd("Input.dispatchMouseEvent", {
            "type": "mousePressed",
            "x": x, "y": y,
            "button": button,
            "clickCount": 1,
        })
        time.sleep(0.05 + __import__("random").uniform(0, 0.05))
        # Mouse released
        self._send_cmd("Input.dispatchMouseEvent", {
            "type": "mouseReleased",
            "x": x, "y": y,
            "button": button,
            "clickCount": 1,
        })

    def touch_tap(self, x: float, y: float):
        """Touch tap at coordinates (for CAPTCHA bypass)."""
        self._send_cmd("Input.dispatchTouchEvent", {
            "type": "touchStart",
            "touchPoints": [{"x": x, "y": y}],
        })
        time.sleep(0.08)
        self._send_cmd("Input.dispatchTouchEvent", {
            "type": "touchEnd",
            "touchPoints": [],
        })

    def touch_long_press(self, x: float, y: float, duration: float = 3.5):
        """
        Touch long-press at coordinates.
        This is the key technique for hsprotect CAPTCHA bypass.
        Uses Input.dispatchTouchEvent with touchStart/touchEnd.
        """
        import random
        actual_duration = duration + random.uniform(-0.3, 0.5)
        actual_duration = max(2.0, actual_duration)

        logger.info("[CDP] Touch long-press at (%.0f, %.0f) for %.1fs", x, y, actual_duration)

        # Touch start
        self._send_cmd("Input.dispatchTouchEvent", {
            "type": "touchStart",
            "touchPoints": [{"x": x, "y": y}],
        })

        # Hold for duration
        time.sleep(actual_duration)

        # Touch end
        self._send_cmd("Input.dispatchTouchEvent", {
            "type": "touchEnd",
            "touchPoints": [],
        })

        logger.info("[CDP] Touch long-press completed")

    def touch_drag(self, start_x: float, start_y: float, end_x: float, end_y: float, duration_ms: int = 800):
        """
        Touch drag from (start_x, start_y) to (end_x, end_y).
        Used for slider CAPTCHA. Simulates human-like drag with intermediate steps.
        """
        import random
        steps = random.randint(15, 25)
        logger.info("[CDP] Touch drag (%.0f,%.0f) -> (%.0f,%.0f) in %dms", start_x, start_y, end_x, end_y, duration_ms)

        # Touch start
        self._send_cmd("Input.dispatchTouchEvent", {
            "type": "touchStart",
            "touchPoints": [{"x": start_x, "y": start_y}],
        })
        time.sleep(random.uniform(0.05, 0.15))

        # Move with easing (ease-out: fast start, slow end)
        for i in range(1, steps + 1):
            t = i / steps
            # Ease-out cubic
            eased = 1.0 - (1.0 - t) ** 3
            cx = start_x + (end_x - start_x) * eased
            cy = start_y + (end_y - start_y) * eased
            # Add slight random jitter
            cx += random.uniform(-1.5, 1.5)
            cy += random.uniform(-0.8, 0.8)
            self._send_cmd("Input.dispatchTouchEvent", {
                "type": "touchMove",
                "touchPoints": [{"x": cx, "y": cy}],
            })
            step_delay = duration_ms / steps / 1000.0
            time.sleep(step_delay + random.uniform(-0.005, 0.01))

        # Touch end
        self._send_cmd("Input.dispatchTouchEvent", {
            "type": "touchEnd",
            "touchPoints": [],
        })
        logger.info("[CDP] Touch drag completed")

    def mouse_drag(self, start_x: float, start_y: float, end_x: float, end_y: float, duration_ms: int = 800):
        """
        Mouse drag from (start_x, start_y) to (end_x, end_y).
        Fallback for touch drag.
        """
        import random
        steps = random.randint(15, 25)

        self._send_cmd("Input.dispatchMouseEvent", {
            "type": "mousePressed", "x": start_x, "y": start_y,
            "button": "left", "clickCount": 1,
        })
        time.sleep(random.uniform(0.05, 0.1))

        for i in range(1, steps + 1):
            t = i / steps
            eased = 1.0 - (1.0 - t) ** 3
            cx = start_x + (end_x - start_x) * eased + random.uniform(-1, 1)
            cy = start_y + (end_y - start_y) * eased + random.uniform(-0.5, 0.5)
            self._send_cmd("Input.dispatchMouseEvent", {
                "type": "mouseMoved", "x": cx, "y": cy,
            })
            time.sleep(duration_ms / steps / 1000.0)

        self._send_cmd("Input.dispatchMouseEvent", {
            "type": "mouseReleased", "x": end_x, "y": end_y,
            "button": "left", "clickCount": 1,
        })

    def type_text(self, text: str, delay_ms: int = 80):
        """Type text character by character using CDP Input.dispatchKeyEvent."""
        import random
        for char in text:
            self._send_cmd("Input.dispatchKeyEvent", {
                "type": "keyDown",
                "text": char,
                "key": char,
                "code": f"Key{char.upper()}" if char.isalpha() else "",
                "windowsVirtualKeyCode": ord(char.upper()) if char.isalpha() else 0,
            })
            self._send_cmd("Input.dispatchKeyEvent", {
                "type": "keyUp",
                "key": char,
                "code": f"Key{char.upper()}" if char.isalpha() else "",
            })
            time.sleep(random.uniform(delay_ms * 0.5, delay_ms * 1.5) / 1000)

    def press_key(self, key: str):
        """Press a special key (Enter, Tab, etc.)."""
        key_map = {
            "Enter": {"key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13},
            "Tab": {"key": "Tab", "code": "Tab", "windowsVirtualKeyCode": 9},
            "Escape": {"key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27},
            "Backspace": {"key": "Backspace", "code": "Backspace", "windowsVirtualKeyCode": 8},
        }
        params = key_map.get(key, {"key": key, "code": key})
        self._send_cmd("Input.dispatchKeyEvent", {"type": "keyDown", **params})
        time.sleep(0.05)
        self._send_cmd("Input.dispatchKeyEvent", {"type": "keyUp", **params})

    def focus_element(self, selector: str) -> bool:
        """Focus an element via JS."""
        escaped_sel = selector.replace("'", "\\'")
        js = f"""
        (() => {{
            const el = document.querySelector('{escaped_sel}');
            if (!el) return false;
            el.focus();
            return true;
        }})()
        """
        return bool(self.evaluate(js))

    def set_input_value(self, selector: str, value: str) -> bool:
        """Set input value via JS (without triggering input events that reveal automation)."""
        escaped_sel = selector.replace("'", "\\'")
        escaped_val = value.replace("'", "\\'")
        js = f"""
        (() => {{
            const el = document.querySelector('{escaped_sel}');
            if (!el) return false;
            // Use native setter to bypass React/Vue wrappers
            const nativeSet = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value'
            ).set;
            nativeSet.call(el, '{escaped_val}');
            el.dispatchEvent(new Event('input', {{ bubbles: true }}));
            el.dispatchEvent(new Event('change', {{ bubbles: true }}));
            return true;
        }})()
        """
        return bool(self.evaluate(js))

    def get_body_text(self) -> str:
        """Get visible body text."""
        return str(self.evaluate("document.body ? document.body.innerText : ''") or "")

    def get_page_html(self) -> str:
        """Get page HTML."""
        return str(self.evaluate("document.documentElement.outerHTML") or "")

    def wait_for_element(self, selector: str, timeout: float = 15) -> bool:
        """Wait for element to appear."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            nid = self.query_selector(selector)
            if nid and self.is_element_visible(nid):
                return True
            time.sleep(0.3)
        return False

    def wait_for_text(self, text: str, timeout: float = 15) -> bool:
        """Wait for text to appear in page body."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            body = self.get_body_text().lower()
            if text.lower() in body:
                return True
            time.sleep(0.3)
        return False

    def screenshot(self, path: str = "") -> str:
        """Take a screenshot, return base64 or save to path."""
        result = self._send_cmd("Page.captureScreenshot", {"format": "png"})
        import base64
        data = base64.b64decode(result.get("data", ""))
        if path:
            Path(path).write_bytes(data)
            return path
        return base64.b64encode(data).decode()

    def close(self):
        """Close the browser and kill entire process tree."""
        self._connected = False
        try:
            if self._ws:
                self._ws.close()
        except Exception:
            pass
        # Kill entire process group (Chrome spawns child processes: renderer, GPU, etc.)
        if self._process:
            pgid = None
            try:
                pgid = os.getpgid(self._process.pid)
            except Exception:
                pass
            try:
                self._process.terminate()
                self._process.wait(timeout=3)
            except Exception:
                try:
                    if self._process:
                        self._process.kill()
                except Exception:
                    pass
            # Kill any remaining children in the process group
            if pgid and pgid > 1:
                try:
                    os.killpg(pgid, 9)  # SIGKILL entire group
                    logger.info("[CDP] Killed process group pgid=%d", pgid)
                except (ProcessLookupError, PermissionError):
                    pass
            # Double-check: kill any chrome processes with our user-data-dir
            if self._temp_dir:
                try:
                    subprocess.run(
                        ["pkill", "-9", "-f", str(self._temp_dir)],
                        capture_output=True, timeout=5
                    )
                except Exception:
                    pass
        # Clean up relay server
        if hasattr(self, '_relay_server') and self._relay_server:
            try:
                self._relay_server.close()
            except Exception:
                pass
        if self._temp_dir:
            try:
                import shutil
                time.sleep(0.3)
                shutil.rmtree(self._temp_dir, ignore_errors=True)
            except Exception:
                pass
        logger.info("[CDP] Browser closed")

    def __enter__(self):
        return self.launch()

    def __exit__(self, *args):
        self.close()

    @property
    def current_url(self) -> str:
        return self.get_url()

    @property
    def title(self) -> str:
        return self.get_title()