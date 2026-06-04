import logging
import os
import sys
import json
import secrets
import time
import socket
import threading
sys.path.append(os.path.dirname(__file__))

from config import (
    CAPTCHA_SERVICES_SUPPORTED,
    DEFAULT_CAPTCHA_SERVICE,
    SMS_SERVICES_SUPPORTED,
    DEFAULT_SMS_SERVICE,
    SUPPORTED_SOLVERS_BY_EMAIL,
    SUPPORTED_BROWSERS
)
from email_providers import outlook, gmail, yahoo
from utils.webdriver_utils import create_driver
from utils import get_birthdate, generate_missing_info
from fp.fp import FreeProxy

# CDP hybrid approach (clean Chrome + CDP + touch CAPTCHA)
try:
    from cdp_outlook import register_outlook_account as cdp_register_outlook
    from cdp_outlook import OutlookAccount as CDPOutlookAccount
    from cdp_outlook import RegistrationResult as CDPRegistrationResult
    CDP_AVAILABLE = True
except ImportError:
    CDP_AVAILABLE = False

try:
    from .flow_diagnostics import FlowRunReport, classify_blocker
    from .service_adapters import normalize_proxy, validate_proxy
    from email_providers.outlook import AccountCreationError
except ImportError:
    try:
        from flow_diagnostics import FlowRunReport, classify_blocker
        from service_adapters import normalize_proxy, validate_proxy
        from email_providers.outlook import AccountCreationError
    except ImportError:
        from flow_diagnostics import FlowRunReport, classify_blocker
        from service_adapters import normalize_proxy, validate_proxy
        class AccountCreationError(Exception):
            pass

# Define FreeProxyException for compatibility with free-proxy 1.0.2
class FreeProxyException(Exception):
    pass


PROVIDER_TARGET_URLS = {
    "outlook": "https://signup.live.com/signup",
    "gmail": "https://accounts.google.com/signup/v2/createaccount?flowName=GlifWebSignIn&flowEntry=SignUp",
    "yahoo": "https://login.yahoo.com/account/create",
}

# ── CDP Hybrid Mode Configuration ──
# When USE_CDP_HYBRID=True, Outlook registration uses the CDP hybrid approach:
# - Clean Chrome (no automation flags) connected via CDP
# - Extension-like DOM detection logic
# - OS-level input (Win32 API / xdotool) for clicks
# - Touch long-press via Input.dispatchTouchEvent for CAPTCHA bypass
USE_CDP_HYBRID = True  # CDP hybrid mode enabled by default for Outlook/Hotmail


class 邮箱注册():
    """
    Main class to create email accounts.

    Attributes:
        browser (str): The browser to be used for automation. Default is "firefox".
        captcha_keys (dict): The API keys for captcha solving services. Default is an empty dictionary.
        sms_keys (dict): The API keys for SMS services. Default is an empty dictionary.
        captcha_services_supported (list): The list of supported captcha solving services.
        default_captcha_service (str): The default captcha solving service.
        sms_services_supported (list): The list of supported SMS services.
        default_sms_service (str): The default SMS service.
        supported_solvers_by_email (dict): The dictionary containing supported captcha solvers by email providers.

    Methods:
        __init__(self, browser="firefox", captcha_keys={}, sms_keys={}, proxy=None, auto_proxy=False): Initializes a 邮箱注册 instance.
        setup_logging(self): Sets up the logging configuration for 邮箱注册.
        get_proxy(self): Returns a proxy if user provided one or tries to get a free proxy if auto_proxy is enabled.
        get_captcha_key(self, email_provider): Retrieves the captcha key for the specified email provider if available.
        get_sms_key(self): Retrieves the SMS key for the default SMS service or a randomly chosen one if multiple provided.
        create_outlook_account(self, username="", password="", first_name="", last_name="", country="", birthdate="", hotmail=False, use_proxy=True): Creates an Outlook/Hotmail account using the provided information.
        create_gmail_account(self, username="", password="", first_name="", last_name="", birthdate="", use_proxy=True): Creates a Gmail account using the provided information.
        create_yahoo_account(self, username="", password="", first_name="", last_name="", birthdate="", myyahoo=False, use_proxy=True): Creates a Yahoo/Myyahoo account using the provided information.

    Logging:
        Logs are saved in the 'logs/邮箱注册.log' file with a format of '[timestamp] [log_level]: log_message'.

    """
    def __init__(self,
                 browser="firefox",
                 captcha_keys={},
                 sms_keys={},
                 proxies=None,
                 auto_proxy=False,
                 proxy_recheck=False,
                 flow_report=None,
                 webdriver_visible=False,
                 persistent_browser_profile=False,
                 browser_plugin_paths=None,
                 ):     
        """
        Initializes a 邮箱注册 instance.

        Args:
            browser (str, optional): The browser to be used for automation. Default is "firefox".
            captcha_keys (dict, optional): The API keys for captcha solving services. Default is an empty dictionary.
            sms_keys (dict, optional): The API keys for SMS services. Default is an empty dictionary.
            proxies (list, optional): List of proxies to use for the webdriver. Default is None.
            auto_proxy (bool, optional): Flag to indicate whether to use free proxies. Default is False.
        """
        if browser not in SUPPORTED_BROWSERS:
            raise ValueError(f"Unsupported browser '{browser}'. Supported browsers are: {', '.join(SUPPORTED_BROWSERS)}")
        self.browser = browser
        self.captcha_keys = captcha_keys or {}
        self.sms_keys = sms_keys or {}

        self.captcha_services_supported = CAPTCHA_SERVICES_SUPPORTED
        self.default_captcha_service = DEFAULT_CAPTCHA_SERVICE
        self.sms_services_supported = SMS_SERVICES_SUPPORTED
        self.default_sms_service = DEFAULT_SMS_SERVICE
        self.supported_solvers_by_email = SUPPORTED_SOLVERS_BY_EMAIL 
        
        self.proxies = proxies
        self.auto_proxy = auto_proxy
        self.proxy_recheck = proxy_recheck
        self.flow_report = flow_report
        self.webdriver_visible = bool(webdriver_visible)
        self.persistent_browser_profile = bool(persistent_browser_profile)
        self.browser_plugin_paths = [str(path) for path in (browser_plugin_paths or []) if str(path).strip()]
        self.active_driver = None
        self._proxy_index = 0
        # ── Pause/Resume support ──
        self._pause_event = threading.Event()
        self._pause_event.set()  # Start in 'running' state (not paused)
        self._stop_requested = False
        # 代理健康跟踪：{ proxy_url: {"healthy": bool, "last_check": timestamp, "fail_count": int, "cooldown_until": timestamp} }
        self._proxy_health: dict[str, dict] = {}
        # 代理预检配置
        self._proxy_check_timeout = 3.0       # 快速预检超时（秒）
        self._proxy_cooldown_seconds = 180    # 失败冷却时间（秒）
        self._proxy_max_fails = 3             # 连续失败N次进入冷却

        #Set up logging
        self.setup_logging()

    def import_proxies(self, text: str, append: bool = False) -> int:
        """
        Import proxies from text (supports IPWEB and standard formats).
        
        Supported formats:
          host:port:user:pass     (IPWEB/代理商格式)
          user:pass@host:port     (标准认证格式)
          http://host:port        (HTTP 代理)
          socks5://host:port      (SOCKS5 代理)
          host:port               (无认证)
        
        Args:
            text: Multi-line proxy text
            append: If True, append to existing; if False, replace
        
        Returns:
            Number of proxies imported
        """
        try:
            from proxy_utils import parse_proxies
        except ImportError:
            from .proxy_utils import parse_proxies
        
        parsed = parse_proxies(text)
        urls = [p.url for p in parsed]
        
        if append and self.proxies:
            existing = set(u.lower() for u in self.proxies)
            new_urls = [u for u in urls if u.lower() not in existing]
            self.proxies.extend(new_urls)
        else:
            self.proxies = urls
        
        logging.info("[PROXY] Imported %d proxies (total: %d)", len(urls), len(self.proxies or []))
        return len(urls)

    def import_proxy_file(self, file_path: str, append: bool = False) -> int:
        """Import proxies from a file (txt, one per line)."""
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            text = f.read()
        return self.import_proxies(text, append=append)

    def set_flow_report(self, flow_report):
        self.flow_report = flow_report

    def set_webdriver_visible(self, visible):
        self.webdriver_visible = bool(visible)

    def pause(self):
        """Pause the current registration flow."""
        self._pause_event.clear()
        logging.info("[CONTROL] Registration paused")

    def resume(self):
        """Resume the current registration flow."""
        self._pause_event.set()
        logging.info("[CONTROL] Registration resumed")

    def stop(self):
        """Request stop of the current registration flow."""
        self._stop_requested = True
        self._pause_event.set()  # Unpause so the flow can check stop flag
        logging.info("[CONTROL] Stop requested")

    def reset_stop(self):
        """Reset the stop flag for a new registration."""
        self._stop_requested = False
        self._pause_event.set()

    def wait_if_paused(self):
        """Block if paused. Returns True if stop was requested."""
        if self._stop_requested:
            return True
        self._pause_event.wait()  # Block while paused
        return self._stop_requested

    @property
    def is_paused(self) -> bool:
        return not self._pause_event.is_set()

    @property
    def is_stopped(self) -> bool:
        return self._stop_requested

    def _flow_start(self, name, **details):
        logging.info("[STEP] step=%s details=%s", name, details)
        if self.flow_report:
            self.flow_report.start_step(name, **details)

    def _flow_ok(self, name, **details):
        logging.info("[OK] step=%s details=%s", name, details)
        if self.flow_report:
            self.flow_report.ok(name, **details)

    def _flow_block(self, name, reason, **details):
        blocker = details.pop("blocker", None) or classify_blocker(reason)
        logging.warning("[BLOCK] step=%s blocker=%s reason=%s details=%s", name, blocker, reason, details)
        if self.flow_report:
            self.flow_report.block(name, reason, blocker=blocker, **details)

    def _flow_fail(self, name, exc, **details):
        blocker = classify_blocker(exc)
        logging.exception("[BLOCK] step=%s blocker=%s reason=%s", name, blocker, exc)
        if self.flow_report:
            self.flow_report.fail(name, exc, blocker=blocker, **details)

    def _capture_driver_context(self, report, driver, label):
        if not report or driver is None:
            return
        try:
            current_url = getattr(driver, "current_url", "")
            title = getattr(driver, "title", "")
            report.start_step(f"{label}.driver_context", current_url=current_url, title=title)
            screenshot = report.capture_screenshot(driver, label)
            report.ok(f"{label}.driver_context", screenshot=screenshot)
            logging.info("[FLOW] driver_context label=%s url=%s title=%s screenshot=%s", label, current_url, title, screenshot)
        except Exception as exc:
            logging.warning("[FLOW] driver_context_failed label=%s reason=%s", label, exc)

    def setup_logging(self):
        """
        Sets up the logging configuration for 邮箱注册.

        Logs are saved in the 'logs/邮箱注册.log' file with a format of '[timestamp] [log_level]: log_message'.
        """
        # Create logs directory if it doesn't exist
        logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        os.makedirs(logs_dir, exist_ok=True)

        # Set up logging configuration
        logging.basicConfig(
            filename=os.path.join(logs_dir, '邮箱注册.log'),
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s]: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    def _verify_proxy_exit_ip(self, driver, proxy_url: str = "") -> dict:
        """
        验证代理是否真正生效：通过浏览器访问 ipify.org 检查出口IP。
        返回 {"ok": bool, "exit_ip": str, "is_proxy": bool, "error": str}
        """
        result = {"ok": False, "exit_ip": "", "is_proxy": False, "error": ""}
        if not driver:
            result["error"] = "no_driver"
            return result
        try:
            driver.get("https://api.ipify.org?format=json")
            time.sleep(3)
            body = driver.find_element("tag name", "body").text
            data = json.loads(body) if body else {}
            exit_ip = data.get("ip", "").strip()
            result["exit_ip"] = exit_ip
            result["ok"] = bool(exit_ip)
            if exit_ip:
                # 简单判断：如果出口IP不是常见的中国IP段，则认为代理生效
                # 更准确的判断需要查询IP地理位置数据库
                is_cn = exit_ip.startswith(("116.", "117.", "118.", "119.", "120.",
                                              "121.", "122.", "123.", "124.", "125.",
                                              "1.", "36.", "39.", "42.", "43.",
                                              "49.", "58.", "59.", "60.", "61."))
                result["is_proxy"] = not is_cn
                if is_cn:
                    result["error"] = f"exit_ip_appears_cn: {exit_ip}"
                    logging.warning("[PROXY][VERIFY] ⚠️ 出口IP疑似中国: %s (proxy=%s)", exit_ip, proxy_url)
                else:
                    logging.info("[PROXY][VERIFY] ✅ 出口IP: %s (proxy=%s)", exit_ip, proxy_url)
            else:
                result["error"] = "empty_exit_ip"
        except Exception as exc:
            result["error"] = f"verify_failed: {exc}"
            logging.warning("[PROXY][VERIFY] 验证失败: %s", exc)
        return result

    def _quick_proxy_check(self, proxy_url: str, target_url: str = "") -> dict:
        """
        快速预检代理可用性。
        仅做一次 TCP 连接测试 + 一个 HTTP GET，总超时 3 秒。
        返回 {"ok": bool, "latency_ms": float, "error": str}
        """
        result = {"ok": False, "latency_ms": 0, "error": ""}
        start = time.monotonic()

        # 解析代理地址
        candidate = normalize_proxy(proxy_url, source="health_check")
        if not candidate:
            result["error"] = "invalid_proxy_url"
            return result

        host = candidate.host
        port = candidate.port

        # 步骤1: TCP 连接测试（1.5秒超时）
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1.5)
            sock.connect((host, int(port)))
            sock.close()
        except (socket.timeout, OSError, ValueError) as exc:
            result["error"] = f"tcp_connect_failed: {exc}"
            result["latency_ms"] = round((time.monotonic() - start) * 1000)
            return result

        tcp_ms = round((time.monotonic() - start) * 1000)

        # 步骤2: HTTP GET 验证（剩余超时）
        test_url = target_url or "https://api.ipify.org?format=json"
        remaining = max(1.0, self._proxy_check_timeout - (time.monotonic() - start))
        try:
            import requests
            resp = requests.get(
                test_url,
                proxies={"http": proxy_url, "https": proxy_url},
                timeout=min(remaining, 2.5),
                stream=True,
            )
            # 只读少量字节确认连通
            _ = next(resp.iter_content(64), b"")
            resp.close()
            if resp.status_code < 400:
                result["ok"] = True
            else:
                result["error"] = f"http_{resp.status_code}"
        except Exception as exc:
            result["error"] = f"http_check_failed: {type(exc).__name__}"

        result["latency_ms"] = round((time.monotonic() - start) * 1000)
        logging.info(
            "[PROXY][QUICK_CHECK] proxy=%s ok=%s tcp_ms=%s total_ms=%s error=%s",
            proxy_url, result["ok"], tcp_ms, result["latency_ms"], result["error"] or "none"
        )
        return result

    def _mark_proxy_fail(self, proxy_url: str, reason: str = ""):
        """标记代理失败，累计失败次数，达到阈值进入冷却。"""
        now = time.time()
        health = self._proxy_health.setdefault(proxy_url, {
            "healthy": True, "last_check": 0, "fail_count": 0, "cooldown_until": 0
        })
        health["fail_count"] += 1
        health["last_check"] = now
        if health["fail_count"] >= self._proxy_max_fails:
            health["healthy"] = False
            health["cooldown_until"] = now + self._proxy_cooldown_seconds
            logging.warning(
                "[PROXY][COOLDOWN] proxy=%s fail_count=%d cooldown_until=%s reason=%s",
                proxy_url, health["fail_count"],
                time.strftime("%H:%M:%S", time.localtime(health["cooldown_until"])),
                reason
            )
        else:
            logging.info("[PROXY][FAIL_COUNT] proxy=%s fail_count=%d reason=%s", proxy_url, health["fail_count"], reason)

    def _mark_proxy_ok(self, proxy_url: str, latency_ms: float = 0):
        """标记代理健康，重置失败计数。"""
        self._proxy_health[proxy_url] = {
            "healthy": True,
            "last_check": time.time(),
            "fail_count": 0,
            "cooldown_until": 0,
            "latency_ms": latency_ms,
        }

    def _is_proxy_available(self, proxy_url: str) -> bool:
        """判断代理是否可用（不在冷却期）。"""
        health = self._proxy_health.get(proxy_url)
        if not health:
            return True  # 未记录的代理默认可用
        if health["healthy"]:
            return True
        # 检查冷却是否结束
        if time.time() >= health.get("cooldown_until", 0):
            health["healthy"] = True
            health["fail_count"] = 0
            logging.info("[PROXY][RECOVER] proxy=%s cooldown expired, re-enabling", proxy_url)
            return True
        return False

    def get_proxy(self, target_url=None, provider=""):
        """
        智能轮询获取代理。
        1. 优先选择健康代理（跳过冷却中的代理）
        2. 快速预检（TCP + 单次HTTP，3秒超时）
        3. 失败自动跳过，累计失败进入冷却
        4. 所有代理都不可用时抛出异常
        """
        if not self.proxies:
            if self.auto_proxy:
                logging.info("[PROXY][SKIP] auto_proxy=true but proxy list is empty; free-proxy fallback disabled")
            return None

        total = len(self.proxies)
        now = time.time()

        # 统计当前状态
        available_count = sum(1 for p in self.proxies if self._is_proxy_available(p))
        cooled_count = total - available_count
        if cooled_count:
            logging.info(
                "[PROXY] available=%d/%d cooled=%d provider=%s",
                available_count, total, cooled_count, provider or "<generic>"
            )

        # 第一轮：只尝试可用代理
        checked = 0
        while checked < total:
            index = self._proxy_index % total
            proxy = self.proxies[index]
            self._proxy_index += 1
            checked += 1

            # 跳过冷却中的代理
            if not self._is_proxy_available(proxy):
                continue

            # 不做预检（recheck=False）直接返回
            if not self.proxy_recheck:
                logging.info("[PROXY] selected=%s index=%s total=%s recheck=false", proxy, index, total)
                return proxy

            # 快速预检
            check_result = self._quick_proxy_check(proxy, target_url or "")
            if check_result["ok"]:
                self._mark_proxy_ok(proxy, check_result["latency_ms"])
                logging.info(
                    "[PROXY][OK] selected=%s provider=%s target=%s index=%s total=%s latency_ms=%s",
                    proxy,
                    provider or "<generic>",
                    target_url or "<generic>",
                    index,
                    total,
                    check_result["latency_ms"],
                )
                return proxy
            else:
                self._mark_proxy_fail(proxy, check_result["error"])

        # 第二轮：如果第一轮全部失败，尝试冷却中的代理（强制预检）
        logging.warning("[PROXY][RETRY] 第一轮全部失败，尝试冷却中的代理")
        for proxy in self.proxies:
            check_result = self._quick_proxy_check(proxy, target_url or "")
            if check_result["ok"]:
                self._mark_proxy_ok(proxy, check_result["latency_ms"])
                logging.info("[PROXY][RECOVERED] proxy=%s latency_ms=%s", proxy, check_result["latency_ms"])
                return proxy

        logging.warning("[PROXY][BLOCK] all %d proxies failed quick recheck", total)
        raise ValueError(f"no_available_proxy: all {total} proxies failed quick recheck")

    def get_captcha_key(self, email_provider):
        """
        Retrieves the captcha key for the specified email provider if available.

        Raises a ValueError if no captcha key is provided for the email provider.
        """
        for solver in self.supported_solvers_by_email.get(email_provider.lower(), []):
            if solver in self.captcha_keys:
                key = self.captcha_keys[solver]
                if not key and solver == "nopecha":
                    logging.info("[CAPTCHA] provider=nopecha status=ip_free_no_key email_provider=%s", email_provider)
                    return {"name": solver, "key": ""}
                if not key:
                    logging.warning("[CAPTCHA][BLOCK] provider=%s status=captcha_key_empty email_provider=%s", solver, email_provider)
                    raise ValueError(f"captcha_key_empty for provider: {solver}")
                logging.info("[CAPTCHA] provider=%s status=selected email_provider=%s", solver, email_provider)
                return {"name": solver, "key": key}
        logging.info(f'Supported captcha solving services for {email_provider} are: { self.supported_solvers_by_email[email_provider.lower()]}')
        logging.warning("[CAPTCHA][BLOCK] no_supported_key email_provider=%s", email_provider)
        raise ValueError(f"No captcha key provided for email provider: {email_provider}")

    def get_sms_key(self):
        """
        Retrieves the SMS key for the default SMS service or a randomly chosen one if multiple provided.

        Raises a ValueError if no SMS keys are provided.
        """
        if not self.sms_keys:
            logging.warning("[SMS][BLOCK] no_sms_key")
            raise ValueError("No SMS API keys provided for SMS verification.")

        if self.default_sms_service in self.sms_keys:
            logging.info("[SMS] provider=%s status=selected_default", self.default_sms_service)
            return {"name": self.default_sms_service, "data": self.sms_keys[self.default_sms_service]}
        else:
            selected_service = secrets.choice(list(self.sms_keys.keys()))
            logging.info("[SMS] provider=%s status=selected_fallback default=%s", selected_service, self.default_sms_service)
            return {"name": selected_service, "data": self.sms_keys[selected_service]}

    def set_use_cdp_hybrid(self, enabled: bool):
        """Enable/disable CDP hybrid mode for Outlook registration."""
        global USE_CDP_HYBRID
        if enabled and not CDP_AVAILABLE:
            raise ValueError("CDP hybrid mode not available: cdp_outlook module not found")
        USE_CDP_HYBRID = bool(enabled)
        logging.info("[CDP] hybrid mode %s", "enabled" if enabled else "disabled")

    def create_outlook_account_cdp(
        self,
        username="",
        password="",
        first_name="",
        last_name="",
        country="",
        birthdate="",
        hotmail=False,
        use_proxy=True,
        pause_checker=None,
    ):
        """
        Creates an Outlook/Hotmail account using the CDP hybrid approach.
        Clean Chrome + CDP DOM queries + touch long-press CAPTCHA.
        Supports automatic proxy rotation on failure.

        Returns:
            tuple: (email, password) of the created account.
        """
        if not CDP_AVAILABLE:
            raise ValueError("CDP hybrid mode not available: cdp_outlook module not found")

        report = self.flow_report
        self._flow_start("outlook.cdp_create")

        # Generate account data once
        self._flow_start("outlook.cdp_generate_inputs")
        username, password, first_name, last_name, country, birthdate = generate_missing_info(
            username, password, first_name, last_name, country, birthdate
        )
        month, day, year = get_birthdate(birthdate)
        self._flow_ok("outlook.cdp_generate_inputs", username=username, country=country)

        domain = "hotmail.com" if hotmail else "outlook.com"
        account = CDPOutlookAccount(
            username=username,
            email=f"{username}@{domain}",
            password=password,
            first_name=first_name,
            last_name=last_name,
            country=country,
            birth_month=str(month),
            birth_day=str(day),
            birth_year=str(year),
            domain=domain,
            provider="hotmail" if hotmail else "outlook",
        )

        # ── Retry loop with proxy rotation ──
        max_retries = 3 if use_proxy and self.proxies else 1
        last_error = None
        tried_proxies: list[str] = []

        for attempt in range(1, max_retries + 1):
            try:
                proxy = None
                if use_proxy:
                    self._flow_start("outlook.cdp_proxy", attempt=attempt)
                    target_url = PROVIDER_TARGET_URLS["outlook"]
                    proxy = self.get_proxy(target_url=target_url, provider="outlook")
                    tried_proxies.append(proxy or "<none>")
                    self._flow_ok("outlook.cdp_proxy", proxy=proxy or "<none>", attempt=attempt)

                self._flow_start("outlook.cdp_register", attempt=attempt)
                result = cdp_register_outlook(
                    account=account,
                    proxy=proxy or "",
                    headless=not self.webdriver_visible,
                    flow_report=report,
                    keep_browser_open=True,
                    extract_rt=True,
                    pause_checker=pause_checker,
                )

                if result.browser:
                    self.active_driver = result.browser

                if result.success:
                    self._flow_ok("outlook.cdp_register", email=result.email, attempt=attempt)
                    self._flow_ok("outlook.cdp_create")
                    return result.email, result.password, result.refresh_token
                else:
                    if result.email and result.password:
                        logging.warning("[CDP] State detect failed but account data generated: email=%s, error=%s", result.email, result.error)
                        self._flow_ok("outlook.cdp_register", email=result.email, warning="state_detect_failed", attempt=attempt)
                        self._flow_ok("outlook.cdp_create")
                        return result.email, result.password, ""
                    last_error = AccountCreationError(f"CDP registration failed: {result.error}")
                    logging.warning("[CDP] Attempt %d/%d failed: %s", attempt, max_retries, result.error)
                    if proxy:
                        self._mark_proxy_fail(proxy, str(result.error))

            except Exception as exc:
                last_error = exc
                logging.warning("[CDP] Attempt %d/%d exception: %s", attempt, max_retries, exc)
                if proxy:
                    self._mark_proxy_fail(proxy, str(exc))

            # Check if stop was requested
            if self._stop_requested:
                logging.info("[CDP] Stop requested, aborting retries")
                break

        self._flow_fail("outlook.cdp_create", last_error)
        raise last_error

    def create_outlook_account(self, 
                               username="", 
                               password="", 
                               first_name="", 
                               last_name="",
                               country="",
                               birthdate="",
                               hotmail=False,
                               use_proxy=True):
        """
        Creates an Outlook/Hotmail account using the provided information.

        If USE_CDP_HYBRID is enabled, uses the CDP hybrid approach:
        - Clean Chrome (no automation flags) connected via CDP
        - Extension-like DOM detection logic
        - Touch long-press CAPTCHA bypass

        Otherwise uses the traditional Selenium WebDriver approach.

        Args:
            username (str, optional): The desired username for the Outlook account.
            password (str, optional): The desired password for the Outlook account.
            first_name (str, optional): The first name of the account holder.
            last_name (str, optional): The last name of the account holder.
            country (str, optional): The country of residence for the account holder.
            birthdate (str, optional): The birthdate of the account holder in the format "MM-DD-YYYY".
            hotmail (bool, optional): Flag indicating whether to create a Hotmail account. Default is False.
            use_proxy (bool, optional): Flag indicating whether to use a proxy to create the account. Default is True.

        Returns:
            tuple: A tuple containing the username and password of the created account.
        """
        # Route to CDP hybrid mode if enabled
        if USE_CDP_HYBRID and CDP_AVAILABLE:
            logging.info("[MODE] Using CDP hybrid approach for Outlook registration")
            return self.create_outlook_account_cdp(
                username=username, password=password,
                first_name=first_name, last_name=last_name,
                country=country, birthdate=birthdate,
                hotmail=hotmail, use_proxy=use_proxy,
            )

        report = self.flow_report
        driver = None
        self._flow_start("outlook.create")
        try:
            self._flow_start("outlook.captcha_key")
            captcha_key = self.get_captcha_key('outlook')
            self._flow_ok("outlook.captcha_key", provider=captcha_key.get("name"))

            proxy = None
            if use_proxy:
                self._flow_start("outlook.proxy")
                target_url = PROVIDER_TARGET_URLS["outlook"]
                proxy = self.get_proxy(target_url=target_url, provider="outlook")
                self._flow_ok("outlook.proxy", proxy=proxy or "<none>", target_url=target_url)
            else:
                logging.info("[PROXY] disabled for outlook")

            self._flow_start("outlook.create_driver", browser=self.browser, proxy=bool(proxy), captcha=captcha_key.get("name"))
            driver = create_driver(
                self.browser,
                captcha_extension=True,
                proxy=proxy,
                captcha_key=captcha_key,
                headless=not self.webdriver_visible,
                persistent_profile=self.persistent_browser_profile,
                extra_extensions=self.browser_plugin_paths,
            )
            self.active_driver = driver
            self._flow_ok("outlook.create_driver")

            # 验证代理是否真正生效
            if proxy:
                self._flow_start("outlook.proxy_verify")
                verify = self._verify_proxy_exit_ip(driver, proxy)
                if verify["ok"] and not verify.get("is_proxy", False):
                    self._flow_block("outlook.proxy_verify",
                                     reason=f"proxy_not_effective: exit_ip={verify['exit_ip']}",
                                     exit_ip=verify["exit_ip"])
                    logging.warning("[PROXY][ALERT] 代理可能未生效！出口IP: %s", verify["exit_ip"])
                elif verify["ok"]:
                    self._flow_ok("outlook.proxy_verify", exit_ip=verify["exit_ip"])
                else:
                    self._flow_block("outlook.proxy_verify",
                                     reason=verify.get("error", "verify_failed"))

            self._flow_start("outlook.generate_inputs")
            username, password, first_name, last_name, \
                country, birthdate = generate_missing_info(username, password, first_name, last_name, country, birthdate)
            month, day, year = get_birthdate(birthdate)
            self._flow_ok("outlook.generate_inputs", username=bool(username), country=country, birthdate=birthdate)

            self._flow_start("outlook.provider.create_account")
            result = outlook.create_account(driver,
                                            username,
                                            password,
                                            first_name,
                                            last_name,
                                            country,
                                            month,
                                            day,
                                            year,
                                            hotmail,
                                            flow_report=report,
                                            captcha_provider=captcha_key.get("name", ""))
            self._flow_ok("outlook.provider.create_account")
            self._flow_ok("outlook.create")
            return result
        except Exception as exc:
            self._capture_driver_context(report, driver, "outlook.error")
            self._flow_fail("outlook.create", exc)
            raise

    def create_gmail_account(self, 
                               username="", 
                               password="", 
                               first_name="", 
                               last_name="",
                               birthdate="",
                               use_proxy=True):
        """
        Creates a Gmail account using the provided information.

        Args:
            username (str, optional): The desired username for the Gmail account.
            password (str, optional): The desired password for the Gmail account.
            first_name (str, optional): The first name of the account holder.
            last_name (str, optional): The last name of the account holder.
            birthdate (str, optional): The birthdate of the account holder in the format "MM-DD-YYYY".
            use_proxy (bool, optional): Flag indicating whether to use a proxy to create the account. Default is True.

        Returns:
            tuple: A tuple containing the username and password of the created account.

        """
        report = self.flow_report
        driver = None
        self._flow_start("gmail.create")
        try:
            proxy = None
            if use_proxy:
                self._flow_start("gmail.proxy")
                target_url = PROVIDER_TARGET_URLS["gmail"]
                proxy = self.get_proxy(target_url=target_url, provider="gmail")
                self._flow_ok("gmail.proxy", proxy=proxy or "<none>", target_url=target_url)
            else:
                logging.info("[PROXY] disabled for gmail")

            self._flow_start("gmail.create_driver", browser=self.browser, proxy=bool(proxy))
            driver = create_driver(
                self.browser,
                proxy=proxy,
                headless=not self.webdriver_visible,
                persistent_profile=self.persistent_browser_profile,
                extra_extensions=self.browser_plugin_paths,
            )
            self.active_driver = driver
            self._flow_ok("gmail.create_driver")

            # 验证代理是否真正生效
            if proxy:
                self._flow_start("gmail.proxy_verify")
                verify = self._verify_proxy_exit_ip(driver, proxy)
                if verify["ok"] and not verify.get("is_proxy", False):
                    self._flow_block("gmail.proxy_verify",
                                     reason=f"proxy_not_effective: exit_ip={verify['exit_ip']}",
                                     exit_ip=verify["exit_ip"])
                    logging.warning("[PROXY][ALERT] Gmail代理可能未生效！出口IP: %s", verify["exit_ip"])
                elif verify["ok"]:
                    self._flow_ok("gmail.proxy_verify", exit_ip=verify["exit_ip"])
                else:
                    self._flow_block("gmail.proxy_verify",
                                     reason=verify.get("error", "verify_failed"))

            self._flow_start("gmail.generate_inputs")
            username, password, first_name, last_name, \
                _, birthdate = generate_missing_info(username, password, first_name, last_name, '', birthdate)
            month, day, year = get_birthdate(birthdate)
            self._flow_ok("gmail.generate_inputs", username=bool(username), birthdate=birthdate)

            self._flow_start("gmail.sms_key")
            sms_key = self.get_sms_key()
            self._flow_ok("gmail.sms_key", provider=sms_key.get("name"))

            self._flow_start("gmail.provider.create_account")
            result = gmail.create_account(driver,
                                          sms_key,
                                          username,
                                          password,
                                          first_name,
                                          last_name,
                                          month,
                                          day,
                                          year,
                                          flow_report=report)
            self._flow_ok("gmail.provider.create_account")
            self._flow_ok("gmail.create")
            return result
        except Exception as exc:
            self._capture_driver_context(report, driver, "gmail.error")
            self._flow_fail("gmail.create", exc)
            raise

    # ── Generic provider routing ──
    SUPPORTED_CREATE_PROVIDERS = frozenset({
        "outlook", "hotmail", "gmail", "yahoo", "myyahoo",
    })

    def create_account(self, provider: str, **kwargs):
        """
        Generic entry point: route to the correct provider-specific method.

        Supported providers:
          outlook, hotmail  → create_outlook_account
          gmail             → create_gmail_account
          yahoo, myyahoo    → create_yahoo_account

        Other providers are only available via the browser extension.
        """
        provider = (provider or "").strip().lower()
        if provider in {"outlook", "hotmail"}:
            return self.create_outlook_account(
                username=kwargs.get("username", ""),
                password=kwargs.get("password", ""),
                first_name=kwargs.get("first_name", ""),
                last_name=kwargs.get("last_name", ""),
                country=kwargs.get("country", ""),
                birthdate=kwargs.get("birthdate", ""),
                hotmail=(provider == "hotmail"),
                use_proxy=kwargs.get("use_proxy", True),
            )
        elif provider == "gmail":
            return self.create_gmail_account(
                username=kwargs.get("username", ""),
                password=kwargs.get("password", ""),
                first_name=kwargs.get("first_name", ""),
                last_name=kwargs.get("last_name", ""),
                birthdate=kwargs.get("birthdate", ""),
                use_proxy=kwargs.get("use_proxy", True),
            )
        elif provider in {"yahoo", "myyahoo"}:
            return self.create_yahoo_account(
                username=kwargs.get("username", ""),
                password=kwargs.get("password", ""),
                first_name=kwargs.get("first_name", ""),
                last_name=kwargs.get("last_name", ""),
                birthdate=kwargs.get("birthdate", ""),
                use_proxy=kwargs.get("use_proxy", True),
            )
        else:
            raise ValueError(
                f"Provider '{provider}' not supported in Python backend. "
                f"Use the browser extension for: proton, gmx, aol, zoho, yandex, "
                f"mailcom, icloud, mailru, naver, kakao, netease163, netease126, "
                f"neteaseyeah, qq, sina, sohu, tutanota"
            )

    def create_yahoo_account(self, 
                               username="", 
                               password="", 
                               first_name="", 
                               last_name="",
                               birthdate="",
                               use_proxy=True):
        """
        Creates a Yahoo/Myyahoo account using the provided information.

        Args:
            username (str, optional): The desired username for the Yahoo account.
            password (str, optional): The desired password for the Yahoo account.
            first_name (str, optional): The first name of the account holder.
            last_name (str, optional): The last name of the account holder.
            birthdate (str, optional): The birthdate of the account holder in the format "MM-DD-YYYY".
            use_proxy (bool, optional): Flag indicating whether to use a proxy to create the account. Default is True.

        Returns:
            dict: A dictionary containing the email and password of the created account.
        """
        report = self.flow_report
        driver = None
        self._flow_start("yahoo.create")
        try:
            self._flow_start("yahoo.captcha_key")
            captcha_key = self.get_captcha_key('yahoo')
            self._flow_ok("yahoo.captcha_key", provider=captcha_key.get("name"))

            proxy = None
            if use_proxy:
                self._flow_start("yahoo.proxy")
                target_url = PROVIDER_TARGET_URLS["yahoo"]
                proxy = self.get_proxy(target_url=target_url, provider="yahoo")
                self._flow_ok("yahoo.proxy", proxy=proxy or "<none>", target_url=target_url)
            else:
                logging.info("[PROXY] disabled for yahoo")

            self._flow_start("yahoo.create_driver", browser=self.browser, proxy=bool(proxy), captcha=captcha_key.get("name"))
            driver = create_driver(
                self.browser,
                captcha_extension=True,
                proxy=proxy,
                captcha_key=captcha_key,
                headless=not self.webdriver_visible,
                persistent_profile=self.persistent_browser_profile,
                extra_extensions=self.browser_plugin_paths,
            )
            self.active_driver = driver
            self._flow_ok("yahoo.create_driver")

            # 验证代理是否真正生效
            if proxy:
                self._flow_start("yahoo.proxy_verify")
                verify = self._verify_proxy_exit_ip(driver, proxy)
                if verify["ok"] and not verify.get("is_proxy", False):
                    self._flow_block("yahoo.proxy_verify",
                                     reason=f"proxy_not_effective: exit_ip={verify['exit_ip']}",
                                     exit_ip=verify["exit_ip"])
                    logging.warning("[PROXY][ALERT] Yahoo代理可能未生效！出口IP: %s", verify["exit_ip"])
                elif verify["ok"]:
                    self._flow_ok("yahoo.proxy_verify", exit_ip=verify["exit_ip"])
                else:
                    self._flow_block("yahoo.proxy_verify",
                                     reason=verify.get("error", "verify_failed"))

            self._flow_start("yahoo.sms_key")
            sms_key = self.get_sms_key()
            self._flow_ok("yahoo.sms_key", provider=sms_key.get("name"))

            self._flow_start("yahoo.generate_inputs")
            username, password, first_name, last_name, \
                _, birthdate = generate_missing_info(username, password, first_name, last_name, '', birthdate)
            month, day, year = get_birthdate(birthdate)
            self._flow_ok("yahoo.generate_inputs", username=bool(username), birthdate=birthdate)

            self._flow_start("yahoo.provider.create_account")
            result = yahoo.create_account(driver,
                                          sms_key,
                                          username,
                                          password,
                                          first_name,
                                          last_name,
                                          month,
                                          day,
                                          year,
                                          flow_report=report,
                                          captcha_provider=captcha_key.get("name", ""))
            self._flow_ok("yahoo.provider.create_account")
            self._flow_ok("yahoo.create")
            return result
        except Exception as exc:
            self._capture_driver_context(report, driver, "yahoo.error")
            self._flow_fail("yahoo.create", exc)
            raise

