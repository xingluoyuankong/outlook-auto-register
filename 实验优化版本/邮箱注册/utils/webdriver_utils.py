from selenium import webdriver
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.edge.service import Service as EdgeService
from webdriver_manager.firefox import GeckoDriverManager
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
from selenium.webdriver.common.by import By
import undetected_chromedriver as uc
import json
import os
from pathlib import Path
import shutil
from urllib.parse import urlparse
import re
import time
import logging


logger = logging.getLogger(__name__)


def _normalize_proxy_url(value):
    value = str(value or "").strip()
    if not value:
        return ""
    if "://" not in value:
        return "http://" + value
    return value


def _read_windows_system_proxy():
    try:
        import winreg

        key_path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            enabled = int(winreg.QueryValueEx(key, "ProxyEnable")[0])
            server = str(winreg.QueryValueEx(key, "ProxyServer")[0] or "")
        if not enabled or not server:
            return ""
        if "=" in server:
            for part in server.split(";"):
                if part.lower().startswith(("https=", "http=")):
                    return _normalize_proxy_url(part.split("=", 1)[1])
            return ""
        return _normalize_proxy_url(server)
    except Exception:
        return ""


def _apply_system_proxy_env():
    proxy_url = _read_windows_system_proxy()
    if not proxy_url:
        logger.info("[DRIVER] system_proxy=none")
        return ""
    for key in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "WDM_HTTP_PROXY",
        "WDM_HTTPS_PROXY",
    ):
        os.environ[key] = proxy_url
    for key in ("NO_PROXY", "no_proxy"):
        current = os.environ.get(key, "")
        additions = ["localhost", "127.0.0.1", "::1"]
        merged = [part.strip() for part in current.split(",") if part.strip()]
        for part in additions:
            if part not in merged:
                merged.append(part)
        os.environ[key] = ",".join(merged)
    os.environ.setdefault("WDM_PROGRESS_BAR", "0")
    logger.info("[DRIVER] system_proxy_env=%s", proxy_url)
    return proxy_url


def _existing_file(path):
    if not path:
        return ""
    try:
        value = Path(str(path).replace("/", os.sep)).expanduser()
        if value.is_file():
            return str(value)
    except Exception:
        return ""
    return ""


def _read_wdm_driver_cache(driver_name):
    drivers_json = Path.home() / ".wdm" / "drivers.json"
    if not drivers_json.is_file():
        return ""
    try:
        payload = json.loads(drivers_json.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.info("[DRIVER] wdm_cache_read_failed path=%s reason=%s", drivers_json, exc)
        return ""

    candidates = []
    for key, item in payload.items():
        if driver_name.lower() not in str(key).lower():
            continue
        if isinstance(item, dict):
            path = _existing_file(item.get("binary_path"))
            if path:
                candidates.append(path)
    if candidates:
        selected = candidates[-1]
        logger.info("[DRIVER] using_cached_driver driver=%s path=%s", driver_name, selected)
        return selected
    return ""


def _find_cached_driver(driver_name):
    from_cache = _read_wdm_driver_cache(driver_name)
    if from_cache:
        return from_cache
    executable = shutil.which(driver_name)
    if executable:
        logger.info("[DRIVER] using_path_driver driver=%s path=%s", driver_name, executable)
        return executable
    cache_root = Path.home() / ".wdm" / "drivers"
    suffix = ".exe" if os.name == "nt" else ""
    target = driver_name if driver_name.endswith(suffix) else driver_name + suffix
    try:
        matches = sorted(cache_root.rglob(target), key=lambda item: item.stat().st_mtime)
    except Exception:
        matches = []
    if matches:
        selected = str(matches[-1])
        logger.info("[DRIVER] using_scanned_cached_driver driver=%s path=%s", driver_name, selected)
        return selected
    return ""


def _find_browser_binary(browser):
    if browser == "chrome":
        names = ["chrome", "chrome.exe", "google-chrome", "chromium", "chromium-browser"]
        known_paths = [
            Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
            Path(os.environ.get("ProgramFiles", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
            Path(os.environ.get("ProgramFiles(x86)", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
        ]
    elif browser == "firefox":
        names = ["firefox", "firefox.exe"]
        known_paths = [
            Path(os.environ.get("ProgramFiles", "")) / "Mozilla Firefox" / "firefox.exe",
            Path(os.environ.get("ProgramFiles(x86)", "")) / "Mozilla Firefox" / "firefox.exe",
        ]
    elif browser == "edge":
        names = ["msedge", "msedge.exe"]
        known_paths = [
            Path(os.environ.get("ProgramFiles", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        ]
    else:
        return ""

    for name in names:
        executable = shutil.which(name)
        if executable:
            return executable
    for path in known_paths:
        existing = _existing_file(path)
        if existing:
            return existing
    return ""


def _install_driver(manager, driver_name):
    cached = _find_cached_driver(driver_name)
    if cached:
        return cached
    logger.info("[DRIVER] cached_driver_missing driver=%s action=webdriver_manager_install", driver_name)
    return manager().install()


def _should_fallback_to_chrome(exc):
    text = str(exc).lower()
    return any(
        token in text
        for token in (
            "could not reach host",
            "are you offline",
            "geckodriver",
            "firefox",
            "browser binary",
            "unable to obtain driver",
            "cannot find",
            "connection refused",
            "read timed out",
        )
    )


def _safe_profile_part(value):
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9_.-]+", "_", text)
    return text.strip("._-")[:80] or "default"


def _browser_profile_dir(browser, profile_scope="default", reset_profile=False):
    raw = os.environ.get("NINJEMAIL_BROWSER_PROFILE_DIR", "").strip()
    if raw.lower() in {"0", "false", "off", "none"}:
        return ""
    base = Path(raw).expanduser() if raw else Path(__file__).resolve().parents[2] / "browser_profiles"
    profile_dir = base / _safe_profile_part(browser) / _safe_profile_part(profile_scope)
    if reset_profile and profile_dir.exists():
        base_resolved = base.resolve()
        target_resolved = profile_dir.resolve()
        if target_resolved == base_resolved or base_resolved not in target_resolved.parents:
            raise ValueError(f"Refusing to reset unsafe browser profile path: {profile_dir}")
        shutil.rmtree(target_resolved)
        logger.info("[DRIVER] browser_profile_reset path=%s", target_resolved)
    profile_dir.mkdir(parents=True, exist_ok=True)
    return str(profile_dir)


def _profile_lock_error(exc):
    text = str(exc).lower()
    return "user data directory is already in use" in text or "profile appears to be in use" in text


def _normalize_extension_paths(extra_extensions=None):
    paths = []
    for item in extra_extensions or []:
        raw = str(item or "").strip()
        if not raw:
            continue
        path = Path(raw).expanduser()
        if not (path / "manifest.json").is_file() and (path / "browser_extension" / "manifest.json").is_file():
            logger.warning("[PLUGIN][FIX] project_root_given_using_browser_extension path=%s", path)
            path = path / "browser_extension"
        manifest = path / "manifest.json"
        if manifest.is_file():
            forbidden = [child.name for child in path.iterdir() if child.name.startswith("_")]
            if forbidden:
                logger.warning("[PLUGIN][SKIP] extension_reserved_names path=%s names=%s", path, forbidden)
                continue
            value = str(path.resolve())
            if value not in paths:
                paths.append(value)
        else:
            logger.warning("[PLUGIN][SKIP] extension_manifest_missing path=%s", path)
    return paths


def _add_extension_argument(options, extension_paths):
    paths = [str(item) for item in extension_paths or [] if str(item).strip()]
    if not paths:
        return
    options.add_argument("--load-extension=" + ",".join(paths))
    logger.info("[PLUGIN] browser_extensions_loaded count=%s paths=%s", len(paths), paths)


def _configure_chrome_options(
    proxy,
    captcha_extension,
    captcha_key,
    undetected=False,
    headless=True,
    persistent_profile=False,
    profile_scope="default",
    reset_profile=False,
    extra_extensions=None,
):
    options = uc.ChromeOptions() if undetected else ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-gpu')
    options.page_load_strategy = "eager"
    # 默认使用无痕模式，每次启动都是全新会话，避免残留数据影响代理
    if not persistent_profile:
        options.add_argument('--incognito')
    if not undetected and headless:
        options.add_argument('--headless=new')
    if not undetected:
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
    options.add_experimental_option('prefs', {'intl.accept_languages': 'en-us'})
    if persistent_profile and not undetected:
        profile_dir = _browser_profile_dir("chrome", profile_scope=profile_scope, reset_profile=reset_profile)
        if profile_dir:
            options.add_argument(f'--user-data-dir={profile_dir}')
            options.add_argument('--profile-directory=Default')
            logger.info("[DRIVER] browser_profile browser=chrome scope=%s path=%s", profile_scope, profile_dir)

    chrome_binary = _find_browser_binary("chrome")
    if chrome_binary and not undetected:
        options.binary_location = chrome_binary
        logger.info("[DRIVER] chrome_binary=%s", chrome_binary)

    proxy_ext = None
    if proxy:
        parsed_url = urlparse(proxy)
        ip_address = parsed_url.hostname
        port = parsed_url.port
        username = parsed_url.username
        password = parsed_url.password
        if username and password:
            # 有认证凭据的代理：用 --proxy-server 传递地址（不含凭据）
            # 认证通过 PAC 脚本 + webRequest.onAuthRequired 处理
            options.add_argument(f'--proxy-server={ip_address}:{port}')
            background_js = create_backgroundjs(ip_address, port, username, password)
            proxy_ext = create_background_file(background_js)
            logger.info("[DRIVER] Proxy with auth: %s:%d (user=%s, ext=%s)", ip_address, port, username, proxy_ext)
        else:
            options.add_argument(f'--proxy-server={proxy}')
            logger.info("[DRIVER] Proxy without auth: %s", proxy)
    extension_paths = []
    if proxy_ext:
        extension_paths.append(proxy_ext)
    if captcha_extension:
        ext_path = ""
        if captcha_key.get('name', None) == 'capsolver':
            add_capsolver_api_key(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'captcha_solvers/capsolver-chrome-extension/assets/config.js'), captcha_key.get('key', None))
            ext_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'captcha_solvers/capsolver-chrome-extension/')
        elif captcha_key.get('name', None) == 'nopecha':
            ext_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'captcha_solvers/NopeCHA-CAPTCHA-Solver/')
        if ext_path:
            extension_paths.append(ext_path)
    extension_paths.extend(_normalize_extension_paths(extra_extensions))
    _add_extension_argument(options, extension_paths)
    return options


def _create_chrome_driver(
    captcha_extension=False,
    proxy=None,
    captcha_key=None,
    undetected=False,
    headless=True,
    persistent_profile=False,
    profile_scope="default",
    reset_profile=False,
    extra_extensions=None,
):
    captcha_key = captcha_key or {}
    options = _configure_chrome_options(
        proxy,
        captcha_extension,
        captcha_key,
        undetected=undetected,
        headless=headless,
        persistent_profile=persistent_profile,
        profile_scope=profile_scope,
        reset_profile=reset_profile,
        extra_extensions=extra_extensions,
    )
    logger.info(
        "[DRIVER] creating %s driver captcha_extension=%s proxy=%s headless=%s",
        "undetected-chrome" if undetected else "chrome",
        captcha_extension,
        bool(proxy),
        headless,
    )
    if undetected:
        driver_path = _find_cached_driver("chromedriver")
        kwargs = {"options": options, "headless": headless, "use_subprocess": False}
        if driver_path:
            kwargs["driver_executable_path"] = driver_path
        driver = uc.Chrome(**kwargs)
    else:
        try:
            driver_path = _install_driver(ChromeDriverManager, "chromedriver")
            driver = webdriver.Chrome(service=ChromeService(driver_path), options=options)
        except Exception as exc:
            if persistent_profile and _profile_lock_error(exc):
                logger.warning("[DRIVER][FALLBACK] chrome_profile_locked action=temp_profile reason=%s", exc)
                options = _configure_chrome_options(
                    proxy,
                    captcha_extension,
                    captcha_key,
                    undetected=undetected,
                    headless=headless,
                    persistent_profile=False,
                    profile_scope=profile_scope,
                    reset_profile=False,
                    extra_extensions=extra_extensions,
                )
                driver_path = _install_driver(ChromeDriverManager, "chromedriver")
                driver = webdriver.Chrome(service=ChromeService(driver_path), options=options)
            else:
                logger.warning("[DRIVER][FALLBACK] chrome_service_failed action=selenium_manager reason=%s", exc)
                driver = webdriver.Chrome(options=options)
    _apply_driver_timeouts(driver)
    if captcha_key.get('name', None) == 'nopecha':
        nopecha_key = captcha_key.get('key', None) or ""
        if nopecha_key:
            driver.get(f"https://nopecha.com/setup#{nopecha_key}")
        else:
            logger.info("[CAPTCHA] provider=nopecha setup=skipped reason=empty_key_ip_quota")
    return driver


def _configure_edge_options(
    proxy,
    captcha_extension,
    captcha_key,
    headless=True,
    persistent_profile=False,
    profile_scope="default",
    reset_profile=False,
    extra_extensions=None,
):
    options = EdgeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-gpu')
    options.page_load_strategy = "eager"
    # 默认使用无痕模式
    if not persistent_profile:
        options.add_argument('--inprivate')
    if headless:
        options.add_argument('--headless=new')
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    options.add_experimental_option('prefs', {'intl.accept_languages': 'en-us'})
    if persistent_profile:
        profile_dir = _browser_profile_dir("edge", profile_scope=profile_scope, reset_profile=reset_profile)
        if profile_dir:
            options.add_argument(f'--user-data-dir={profile_dir}')
            options.add_argument('--profile-directory=Default')
            logger.info("[DRIVER] browser_profile browser=edge scope=%s path=%s", profile_scope, profile_dir)

    edge_binary = _find_browser_binary("edge")
    if edge_binary:
        options.binary_location = edge_binary
        logger.info("[DRIVER] edge_binary=%s", edge_binary)

    proxy_ext = None
    if proxy:
        parsed_url = urlparse(proxy)
        ip_address = parsed_url.hostname
        port = parsed_url.port
        username = parsed_url.username
        password = parsed_url.password
        if username and password:
            options.add_argument(f'--proxy-server={ip_address}:{port}')
            background_js = create_backgroundjs(ip_address, port, username, password)
            proxy_ext = create_background_file(background_js)
            logger.info("[DRIVER] Proxy with auth: %s:%d (user=%s, ext=%s)", ip_address, port, username, proxy_ext)
        else:
            options.add_argument(f'--proxy-server={proxy}')
            logger.info("[DRIVER] Proxy without auth: %s", proxy)

    extension_paths = []
    if proxy_ext:
        extension_paths.append(proxy_ext)
    if captcha_extension:
        ext_path = ""
        if captcha_key.get('name', None) == 'capsolver':
            add_capsolver_api_key(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'captcha_solvers/capsolver-chrome-extension/assets/config.js'), captcha_key.get('key', None))
            ext_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'captcha_solvers/capsolver-chrome-extension/')
        elif captcha_key.get('name', None) == 'nopecha':
            ext_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'captcha_solvers/NopeCHA-CAPTCHA-Solver/')
        if ext_path:
            extension_paths.append(ext_path)
    extension_paths.extend(_normalize_extension_paths(extra_extensions))
    _add_extension_argument(options, extension_paths)
    return options


def _create_edge_driver(
    captcha_extension=False,
    proxy=None,
    captcha_key=None,
    headless=True,
    persistent_profile=False,
    profile_scope="default",
    reset_profile=False,
    extra_extensions=None,
):
    captcha_key = captcha_key or {}
    options = _configure_edge_options(
        proxy,
        captcha_extension,
        captcha_key,
        headless=headless,
        persistent_profile=persistent_profile,
        profile_scope=profile_scope,
        reset_profile=reset_profile,
        extra_extensions=extra_extensions,
    )
    logger.info(
        "[DRIVER] creating edge driver captcha_extension=%s proxy=%s headless=%s",
        captcha_extension,
        bool(proxy),
        headless,
    )
    try:
        driver_path = _install_driver(EdgeChromiumDriverManager, "msedgedriver")
        driver = webdriver.Edge(service=EdgeService(driver_path), options=options)
    except Exception as exc:
        if persistent_profile and _profile_lock_error(exc):
            logger.warning("[DRIVER][FALLBACK] edge_profile_locked action=temp_profile reason=%s", exc)
            options = _configure_edge_options(
                proxy,
                captcha_extension,
                captcha_key,
                headless=headless,
                persistent_profile=False,
                profile_scope=profile_scope,
                reset_profile=False,
                extra_extensions=extra_extensions,
            )
            driver_path = _install_driver(EdgeChromiumDriverManager, "msedgedriver")
            driver = webdriver.Edge(service=EdgeService(driver_path), options=options)
        else:
            logger.warning("[DRIVER][FALLBACK] edge_service_failed action=selenium_manager reason=%s", exc)
            driver = webdriver.Edge(options=options)
    _apply_driver_timeouts(driver)
    if captcha_key.get('name', None) == 'nopecha':
        nopecha_key = captcha_key.get('key', None) or ""
        if nopecha_key:
            driver.get(f"https://nopecha.com/setup#{nopecha_key}")
        else:
            logger.info("[CAPTCHA] provider=nopecha setup=skipped reason=empty_key_ip_quota")
    return driver


def _create_firefox_driver(captcha_extension=False, proxy=None, captcha_key=None, headless=True):
    captcha_key = captcha_key or {}
    parsed_url = urlparse(proxy) if proxy else None
    ip_address = parsed_url.hostname if parsed_url else None
    port = parsed_url.port if parsed_url else None
    proxy_scheme = ((parsed_url.scheme if parsed_url else "") or "http").lower()

    custom_profile = FirefoxProfile()
    custom_profile.set_preference("extensions.ui.developer_mode", True)

    options = FirefoxOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-gpu')
    if headless:
        options.add_argument('--headless')
    options.page_load_strategy = "eager"
    firefox_binary = _find_browser_binary("firefox")
    if firefox_binary:
        options.binary_location = firefox_binary
        logger.info("[DRIVER] firefox_binary=%s", firefox_binary)
    custom_profile.set_preference("intl.accept_languages", "en-us")

    if proxy:
        options.set_preference("network.proxy.type", 1)
        if proxy_scheme.startswith("socks"):
            options.set_preference('network.proxy.socks', ip_address)
            options.set_preference('network.proxy.socks_port', port)
            options.set_preference('network.proxy.socks_version', 5 if proxy_scheme == "socks5" else 4)
            options.set_preference('network.proxy.socks_remote_dns', True)
        else:
            options.set_preference("network.proxy.http", ip_address)
            options.set_preference("network.proxy.http_port", port)
            options.set_preference("network.proxy.ssl", ip_address)
            options.set_preference("network.proxy.ssl_port", port)

    options.profile = custom_profile

    logger.info("[DRIVER] creating firefox driver captcha_extension=%s proxy=%s headless=%s", captcha_extension, bool(proxy), headless)
    try:
        driver_path = _install_driver(GeckoDriverManager, "geckodriver")
        driver = webdriver.Firefox(service=FirefoxService(driver_path), options=options)
    except Exception as exc:
        logger.warning("[DRIVER][FALLBACK] firefox_service_failed action=selenium_manager reason=%s", exc)
        driver = webdriver.Firefox(options=options)
    _apply_driver_timeouts(driver)

    if captcha_extension:
        if captcha_key.get('name', None) == 'capsolver':
            driver.install_addon(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'captcha_solvers/capsolver_captcha_solver-1.10.4.xpi'))
            driver.get('https://www.google.com')
            capsolver_src = driver.find_element(By.XPATH, '/html/script[2]')
            capsolver_src = capsolver_src.get_attribute('src')
            capsolver_ext_id = capsolver_src.split('/')[2]
            driver.get(f'moz-extension://{capsolver_ext_id}/www/index.html#/popup')
            time.sleep(5)

            api_key_input = driver.find_element(By.XPATH, '//input[@placeholder="Please input your API key"]')
            api_key_input.send_keys(captcha_key.get('key', None))
            driver.find_element(By.ID, 'q-app').click()
        elif captcha_key.get('name', None) == 'nopecha':
            driver.install_addon(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'captcha_solvers/noptcha-0.4.9.xpi'))
            nopecha_key = captcha_key.get('key', None) or ""
            if nopecha_key:
                driver.get(f"https://nopecha.com/setup#{nopecha_key}")
            else:
                logger.info("[CAPTCHA] provider=nopecha setup=skipped reason=empty_key_ip_quota")
    return driver


def _apply_driver_timeouts(driver, page_load_timeout=35, script_timeout=35):
    try:
        driver.set_page_load_timeout(page_load_timeout)
    except Exception:
        pass
    try:
        driver.set_script_timeout(script_timeout)
    except Exception:
        pass

def add_capsolver_api_key(file_path, api_key):
    with open(file_path, 'r') as file:
        content = file.read()

    updated_content = re.sub(r'apiKey:\s*\'[^\']*\'', f'apiKey: \'{api_key}\'', content)

    with open(file_path, 'w', encoding='utf-8',newline='\n') as file:
        file.write(updated_content)

def create_backgroundjs(host, port, username, password):
    return """
        var config = {
                mode: "fixed_servers",
                rules: {
                singleProxy: {
                    scheme: "http",
                    host: "%s",
                    port: parseInt(%s)
                },
                bypassList: ["localhost"]
                }
            };

        chrome.proxy.settings.set({value: config, scope: "regular"}, function() {});

        function callbackFn(details) {
            return {
                authCredentials: {
                    username: "%s",
                    password: "%s"
                }
            };
        }

        chrome.webRequest.onAuthRequired.addListener(
                    callbackFn,
                    {urls: ["<all_urls>"]},
                    ['blocking']
        );
        """ % (host, port, username, password)

def create_background_file(background_js):
    folder_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'proxy_auth_ext')
    file_path = os.path.join(folder_path, 'background.js')

    os.makedirs(folder_path, exist_ok=True)

    with open(file_path, 'w') as file:
        file.write(background_js)

    return folder_path

def create_driver(
    browser,
    captcha_extension=False,
    proxy=None,
    captcha_key={},
    headless=True,
    persistent_profile=False,
    profile_scope="default",
    reset_profile=False,
    extra_extensions=None,
):
    """
    Create a WebDriver instance for the specified browser with optional configurations.

    Parameters:
        browser (str): The name of the browser to use. Supports 'firefox', 'chrome', 'edge', and 'undetected-chrome'.
        captcha_extension (bool, optional): Whether to enable a captcha solving extension (default is False).
        proxy (str, optional): Proxy server address in the format 'http://<ip_address>:<port>' or 'socks5://<ip_address>:<port>'.
        captcha_key (dict, optional): Dict containing the name and api key for the captcha solving service to use.
    
    Returns:
        WebDriver: An instance of WebDriver configured based on the provided parameters.

    Raises:
        ValueError: If an unsupported browser is specified.

    Example:
        To create a headless Firefox driver:
        >>> driver = create_driver('firefox')

        To create a headless Chrome driver with a proxy and captcha solving extension:
        >>> driver = create_driver('chrome', captcha_extension=True, proxy='http://127.0.0.1:8080')
    """
    # 只有在没有明确代理时才使用环境变量代理
    if not proxy:
        _apply_system_proxy_env()
    else:
        logger.info("[DRIVER] Skipping system proxy env (explicit proxy provided)")
    if extra_extensions and headless:
        logger.warning("[PLUGIN] browser_extensions_requested_in_headless count=%s", len(extra_extensions))

    if browser == 'firefox':
        try:
            driver = _create_firefox_driver(captcha_extension=captcha_extension, proxy=proxy, captcha_key=captcha_key, headless=headless)
        except Exception as exc:
            if not _should_fallback_to_chrome(exc):
                raise
            logger.warning("[DRIVER][FALLBACK] requested=firefox fallback=chrome reason=%s", exc)
            driver = _create_chrome_driver(
                captcha_extension=captcha_extension,
                proxy=proxy,
                captcha_key=captcha_key,
                headless=headless,
                persistent_profile=persistent_profile,
                profile_scope=profile_scope,
                reset_profile=reset_profile,
                extra_extensions=extra_extensions,
            )

    elif browser == 'chrome':
        driver = _create_chrome_driver(
            captcha_extension=captcha_extension,
            proxy=proxy,
            captcha_key=captcha_key,
            headless=headless,
            persistent_profile=persistent_profile,
            profile_scope=profile_scope,
            reset_profile=reset_profile,
            extra_extensions=extra_extensions,
        )

    elif browser == 'edge':
        try:
            driver = _create_edge_driver(
                captcha_extension=captcha_extension,
                proxy=proxy,
                captcha_key=captcha_key,
                headless=headless,
                persistent_profile=persistent_profile,
                profile_scope=profile_scope,
                reset_profile=reset_profile,
                extra_extensions=extra_extensions,
            )
        except Exception as exc:
            if not _should_fallback_to_chrome(exc):
                raise
            logger.warning("[DRIVER][FALLBACK] requested=edge fallback=chrome reason=%s", exc)
            driver = _create_chrome_driver(
                captcha_extension=captcha_extension,
                proxy=proxy,
                captcha_key=captcha_key,
                headless=headless,
                persistent_profile=persistent_profile,
                profile_scope=profile_scope,
                reset_profile=reset_profile,
                extra_extensions=extra_extensions,
            )

    elif browser == 'undetected-chrome':
        try:
            driver = _create_chrome_driver(
                captcha_extension=captcha_extension,
                proxy=proxy,
                captcha_key=captcha_key,
                undetected=True,
                headless=headless,
                extra_extensions=extra_extensions,
            )
        except Exception as exc:
            logger.warning("[DRIVER][FALLBACK] requested=undetected-chrome fallback=chrome reason=%s", exc)
            driver = _create_chrome_driver(
                captcha_extension=captcha_extension,
                proxy=proxy,
                captcha_key=captcha_key,
                headless=headless,
                persistent_profile=persistent_profile,
                profile_scope=profile_scope,
                reset_profile=reset_profile,
                extra_extensions=extra_extensions,
            )
    else:
        raise ValueError('Unsupported browser')
    return driver
