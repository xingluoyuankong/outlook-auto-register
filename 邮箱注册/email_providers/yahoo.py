import logging
from typing import Optional, Tuple
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait, Select
from sms_services import get_sms_instance
from utils.web_helpers import safe_click, wait_and_click, set_input_value
try:
    from challenge_detection import detect_challenge, wait_for_manual_takeover
except ImportError:
    from ..challenge_detection import detect_challenge, wait_for_manual_takeover

logger = logging.getLogger(__name__)

# Constants
URL = 'https://login.yahoo.com/account/create'
WAIT_TIMEOUT = 25
MAX_CAPTCHA_RETRIES = 3
CAPTCHA_SOLVE_TIMEOUT = 120

# Centralized selector configuration
SELECTORS = {
    "username": (By.ID, 'usernamereg-userId'),
    "password": (By.ID, 'usernamereg-password'),
    "first_name": (By.ID, 'usernamereg-firstName'),
    "last_name": (By.ID, 'usernamereg-lastName'),
    "birth_month": (By.ID, 'usernamereg-month'),
    "birth_day": (By.ID, 'usernamereg-day'),
    "birth_year": (By.ID, 'usernamereg-year'),
    "submit_button": (By.ID, 'reg-submit-button'),
    "phone_input": (By.ID, 'usernamereg-phone'),
    "recaptcha_frame": (By.ID, "recaptcha-iframe"),
    "funcaptcha_frame": (By.ID, "arkose-iframe"),
    "verification_code": (By.ID, "verification-code-field"),
    "success_page": (By.XPATH, "//h1[contains(., 'Account created')]")
}

class AccountCreationError(Exception):
    """Base exception for Yahoo account creation failures"""
    pass


def _step(flow_report, name: str, **details) -> None:
    logger.info("[CREATE] provider=yahoo step=%s details=%s", name, details)
    if hasattr(flow_report, "start_step"):
        flow_report.start_step(f"yahoo.{name}", **details)


def _ok(flow_report, name: str, **details) -> None:
    logger.info("[CREATE][OK] provider=yahoo step=%s details=%s", name, details)
    if hasattr(flow_report, "ok"):
        flow_report.ok(f"yahoo.{name}", **details)


def _fail(flow_report, name: str, exc: Exception, driver: Optional[WebDriver] = None) -> None:
    logger.error("[CREATE][BLOCK] provider=yahoo step=%s error=%s", name, exc)
    if hasattr(flow_report, "fail"):
        if driver is not None:
            if hasattr(flow_report, "capture_screenshot"):
                flow_report.capture_screenshot(driver, f"yahoo.{name}")
        if getattr(flow_report, "mode", "") == "visible_flow_probe":
            flow_report.keep_browser_open = True
        flow_report.fail(f"yahoo.{name}", exc)

def handle_captcha(driver: WebDriver, flow_report=None, captcha_provider: str = "") -> None:
    """Handle Yahoo's captcha challenges with retries"""
    challenge = detect_challenge(driver)
    if challenge and challenge.kind not in {"recaptcha", "funcaptcha"}:
        wait_for_manual_takeover(
            driver,
            flow_report,
            provider="yahoo",
            challenge=challenge,
            captcha_provider=captcha_provider,
        )
        return
    try:
        _step(flow_report, "captcha_branch")
        # Try reCAPTCHA first
        WebDriverWait(driver, CAPTCHA_SOLVE_TIMEOUT).until(
            EC.frame_to_be_available_and_switch_to_it(SELECTORS["recaptcha_frame"])
        )
        try:
            complete_btn = WebDriverWait(driver, CAPTCHA_SOLVE_TIMEOUT).until(
                EC.element_to_be_clickable((By.ID, "recaptcha-submit"))
            )
            safe_click(complete_btn)
        finally:
            driver.switch_to.default_content()
        _ok(flow_report, "captcha_branch", branch="recaptcha")
            
    except TimeoutException:
        # Fallback to FunCaptcha
        try:
            _step(flow_report, "captcha_funcaptcha")
            WebDriverWait(driver, WAIT_TIMEOUT).until(
                EC.frame_to_be_available_and_switch_to_it(SELECTORS["funcaptcha_frame"])
            )
            WebDriverWait(driver, CAPTCHA_SOLVE_TIMEOUT).until(
                EC.visibility_of_element_located((By.XPATH, "//h2[contains(., 'Security check complete')]"))
            )
            safe_click(driver.find_element(By.ID, 'arkose-submit'))
            _ok(flow_report, "captcha_funcaptcha", branch="funcaptcha")
        except Exception as exc:
            _fail(flow_report, "captcha_funcaptcha", exc, driver)
            raise
        finally:
            driver.switch_to.default_content()

def handle_phone_submission(driver: WebDriver, sms_key, sms_provider, flow_report=None) -> dict:
    """Handle phone verification process"""
    phone_info = {}
    next_button_selectors = [
        (By.ID, 'reg-sms-button'),
        (By.ID, 'reg-submit-button')
    ]
    try:
        _step(flow_report, "phone_submission", sms_provider=sms_key.get("name"))
        if sms_key['name'] == 'getsmscode':
            phone = sms_provider.get_phone(send_prefix=False)
            phone_info.update({'phone': phone})
        elif sms_key['name'] in ['smspool', '5sim']:
            phone, order_id = sms_provider.get_phone(send_prefix=False)
            phone_info.update({'phone': phone, 'order_id': order_id})

        set_input_value(driver, SELECTORS["phone_input"], str(phone_info.get('phone')))

        for selector in next_button_selectors:
            try:
                wait_and_click(driver, selector, timeout=10)
                _ok(flow_report, "phone_submission", phone="set")
                return phone_info
            except (TimeoutException, NoSuchElementException):
                continue

        raise TimeoutException("No valid next button found after phone entry")
    except Exception as e:
        logger.error("Phone submission failed: %s", str(e))
        _fail(flow_report, "phone_submission", e, driver)
        raise AccountCreationError("Phone verification step failed") from e

def verify_phone(driver: WebDriver, sms_key, sms_provider, phone_info: dict, flow_report=None) -> None:
    """Handle SMS verification process"""
    try:
        _step(flow_report, "sms_code", sms_provider=sms_key.get("name"))
        if sms_key['name'] == 'getsmscode':
            code = sms_provider.get_code(phone_info['phone'])
        elif sms_key['name'] in ['smspool', '5sim']:
            code = sms_provider.get_code(phone_info['order_id'])
        code_input = WebDriverWait(driver, WAIT_TIMEOUT).until(
            EC.element_to_be_clickable(SELECTORS["verification_code"])
        )
        code_input.send_keys(str(code) + Keys.ENTER)
        _ok(flow_report, "sms_code", code="set")
    except Exception as e:
        logger.error("SMS verification failed: %s", str(e))
        _fail(flow_report, "sms_code", e, driver)
        raise AccountCreationError("Phone verification failed") from e

def create_account(
    driver: WebDriver,
    sms_key: dict,
    username: str,
    password: str,
    first_name: str,
    last_name: str,
    month: str,
    day: str,
    year: str,
    myyahoo: bool = False,
    flow_report=None,
    captcha_provider: str = "",
) -> Tuple[Optional[str], Optional[str]]:
    """
    Create a new Yahoo account with improved reliability
    
    Returns:
        Tuple: (email, password) or (None, None) on failure
    """
    if flow_report is None and not isinstance(myyahoo, bool):
        flow_report = myyahoo
        myyahoo = False
    domain = "myyahoo.com" if myyahoo else "yahoo.com"
    try:
        logger.info('Starting Yahoo account creation process')
        _step(flow_report, "open_signup", url=URL)
        driver.get(URL)
        _ok(flow_report, "open_signup", current_url=getattr(driver, "current_url", ""))

        # Account basics
        _step(flow_report, "fill_profile")
        set_input_value(driver, SELECTORS["username"], username)
        set_input_value(driver, SELECTORS["password"], password)
        set_input_value(driver, SELECTORS["first_name"], first_name)
        set_input_value(driver, SELECTORS["last_name"], last_name)
        _ok(flow_report, "fill_profile")

        # Birthdate
        _step(flow_report, "fill_birthdate", month=month, day=day, year=year)
        Select(WebDriverWait(driver, WAIT_TIMEOUT).until(
            EC.presence_of_element_located(SELECTORS["birth_month"])
        )).select_by_index(int(month))
        
        set_input_value(driver, SELECTORS["birth_day"], day)
        set_input_value(driver, SELECTORS["birth_year"], year)

        wait_and_click(driver, SELECTORS["submit_button"])
        _ok(flow_report, "fill_birthdate")

        # Phone verification
        _step(flow_report, "sms_provider", sms_provider=sms_key.get("name"))
        sms_provider = get_sms_instance(sms_key, 'yahoo')
        _ok(flow_report, "sms_provider")
        phone_info = handle_phone_submission(driver, sms_key, sms_provider, flow_report=flow_report)

        # Captcha handling
        if not 'phone-verify' in driver.current_url:
            handle_captcha(driver, flow_report=flow_report, captcha_provider=captcha_provider)
        else:
            logger.info("[CREATE] provider=yahoo step=captcha_branch status=not_present")

        # SMS verification
        verify_phone(driver, sms_key, sms_provider, phone_info, flow_report=flow_report)

        # Verify success state
        _step(flow_report, "success_url")
        WebDriverWait(driver, WAIT_TIMEOUT).until(
            EC.any_of(
                EC.url_contains("create/success"),
                EC.url_contains("account/upsell/webauth")
            )
        )
        _ok(flow_report, "success_url", current_url=getattr(driver, "current_url", ""))

        # Log successful creation
        logger.info("Yahoo account created successfully")
        logger.debug("Account details: %s@%s", username, domain)
        
        return f"{username}@{domain}", password

    except Exception as e:
        logger.error("Account creation failed: %s", str(e))
        _fail(flow_report, "create_account", e, driver)
        raise AccountCreationError(str(e) or "Yahoo account creation failed") from e
    finally:
        if hasattr(flow_report, "keep_browser_open") and getattr(flow_report, "keep_browser_open", False):
            logger.warning("[NEXT] provider=yahoo browser_kept_open reason=manual_takeover")
        else:
            driver.quit()

