import logging
import random
import re
import secrets
import time
from typing import Optional, Tuple
from utils.web_helpers import wait_and_click, set_input_value
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait, Select
try:
    from challenge_detection import ChallengeInfo, detect_challenge, wait_for_manual_takeover
except ImportError:
    from ..challenge_detection import ChallengeInfo, detect_challenge, wait_for_manual_takeover

logger = logging.getLogger(__name__)

# Centralized selector configuration
SELECTORS = {
    "email_input_new": (By.CSS_SELECTOR, "input[name='email']"),
    "next_button_new": (By.CSS_SELECTOR, "button[type='submit']"),
    "password_input_new": (By.CSS_SELECTOR, "input[type='password']"),
    "email_switch": (By.ID, 'liveSwitch'),
    "username_input": (By.ID, 'usernameInput'),
    "domain_dropdown_new": (By.ID, "domainDropdownId"),
    "domain_select": (By.ID, 'domainSelect'),
    "next_button": (By.ID, 'nextButton'),
    "show_password": (By.ID, 'ShowHidePasswordCheckbox'),
    "optin_email": (By.ID, 'iOptinEmail'),
    "password_input": (By.ID, 'Password'),
    "first_name_input": (By.ID, 'firstNameInput'),
    "last_name_input": (By.ID, 'lastNameInput'),
    "country_select": (By.ID, 'countryRegionDropdown'),
    "birth_month": (By.ID, 'BirthMonth'),
    "birth_month_new": (By.ID, "BirthMonthDropdown"),
    "birth_day": (By.ID, 'BirthDay'),
    "birth_day_new": (By.ID, "BirthDayDropdown"),
    "birth_year": (By.ID, 'BirthYear'),
    "birth_year_new": (By.CSS_SELECTOR, "input[name='BirthYear'], input[aria-label='Birth year']"),
    "captcha_frame": (By.ID, "enforcementFrame"),
    "captcha_reload": (By.XPATH, "//button[contains(text(), 'Reload Challenge')]"),
    "success_message": (By.XPATH, "//span[contains(text(), 'A quick note about your Microsoft account')]"),
    "ok_button": (By.ID, "id__0")
}

WAIT_TIMEOUT = 10
MAX_CAPTCHA_RETRIES = 3
CAPTCHA_RETRY_DELAY = 60
FUNCAPTCHA_SMART_TIMEOUT = 90
POST_CHALLENGE_TIMEOUT = 90
MANUAL_CHALLENGE_TIMEOUT = 1800

class AccountCreationError(Exception):
    """Base exception for account creation failures"""
    pass


def _first_present(driver: WebDriver, selectors: list[Tuple[str, str]], timeout: int = WAIT_TIMEOUT):
    def _find(current_driver):
        for selector in selectors:
            elements = current_driver.find_elements(*selector)
            if elements:
                return elements[0]
        return False

    return WebDriverWait(driver, timeout).until(_find)


def _first_clickable(driver: WebDriver, selectors: list[Tuple[str, str]], timeout: int = WAIT_TIMEOUT):
    def _find(current_driver):
        for selector in selectors:
            elements = current_driver.find_elements(*selector)
            for element in elements:
                if element.is_displayed() and element.is_enabled():
                    return element
        return False

    return WebDriverWait(driver, timeout).until(_find)


def _js_click(driver: WebDriver, element) -> None:
    driver.execute_script("arguments[0].scrollIntoView({block:'center'}); arguments[0].click();", element)


def _clear_and_type(element, value: str) -> None:
    try:
        element.clear()
    except Exception:
        pass
    element.send_keys(str(value))


def _body_text(driver: WebDriver) -> str:
    try:
        return str(driver.execute_script("return document.body ? document.body.innerText : ''") or "")
    except Exception:
        return ""


def _visible_elements(driver: WebDriver, selector: Tuple[str, str]):
    try:
        return [element for element in driver.find_elements(*selector) if element.is_displayed()]
    except Exception:
        return []


def _has_visible(driver: WebDriver, selector: Tuple[str, str]) -> bool:
    return bool(_visible_elements(driver, selector))


def _xpath_literal(value: str) -> str:
    if "'" not in value:
        return f"'{value}'"
    if '"' not in value:
        return f'"{value}"'
    return "concat(" + ", \"'\", ".join(f"'{part}'" for part in value.split("'")) + ")"


def _select_fluent_option(driver: WebDriver, combo_selector: Tuple[str, str], visible_text: str) -> None:
    combo = WebDriverWait(driver, WAIT_TIMEOUT).until(EC.presence_of_element_located(combo_selector))
    _js_click(driver, combo)
    option_xpath = (
        "//*[not(self::script) and not(self::style) "
        f"and normalize-space(.)={_xpath_literal(str(visible_text))}]"
    )
    option = WebDriverWait(driver, WAIT_TIMEOUT).until(
        lambda current_driver: next(
            (
                element
                for element in current_driver.find_elements(By.XPATH, option_xpath)
                if element.is_displayed() and element != combo
            ),
            False,
        )
    )
    _js_click(driver, option)


def _click_next(driver: WebDriver) -> None:
    button = _first_clickable(driver, [SELECTORS["next_button_new"], SELECTORS["next_button"]])
    # Human-like: move mouse to button, pause, then click
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", button)
        time.sleep(random.uniform(0.2, 0.5))
        actions = ActionChains(driver)
        actions.move_to_element(button)
        actions.pause(random.uniform(0.1, 0.3))
        actions.click()
        actions.perform()
    except Exception:
        _js_click(driver, button)
    # Random pause after clicking next (human reading time)
    time.sleep(random.uniform(0.5, 1.5))


def _month_name(month: str) -> str:
    names = {
        "1": "January",
        "2": "February",
        "3": "March",
        "4": "April",
        "5": "May",
        "6": "June",
        "7": "July",
        "8": "August",
        "9": "September",
        "10": "October",
        "11": "November",
        "12": "December",
    }
    return names.get(str(month).lstrip("0"), str(month))


def _normalize_country(country: str) -> str:
    aliases = {
        "us": "United States",
        "usa": "United States",
        "united states of america": "United States",
        "uk": "United Kingdom",
    }
    text = str(country or "").strip()
    return aliases.get(text.lower(), text)


def _local_username(username: str) -> str:
    local = str(username or "").strip().split("@", 1)[0]
    local = re.sub(r"[^a-zA-Z0-9]", "", local).lower()
    if len(local) < 6:
        local = f"mx{secrets.token_hex(5)}"
    return local[:48]


def _username_candidates(username: str) -> list[str]:
    base = _local_username(username)
    candidates = [base]
    for _ in range(7):
        stem = base[: max(6, 40 - 10)]
        candidates.append(f"{stem}{secrets.token_hex(5)}"[:48])
    return list(dict.fromkeys(candidates))


def _email_unavailable(driver: WebDriver) -> bool:
    text = _body_text(driver).lower()
    return any(
        marker in text
        for marker in (
            "isn't available",
            "is not available",
            "already a microsoft account",
            "try another",
            "someone already has",
        )
    )


def _wait_for_state(driver: WebDriver, *states: str, timeout: int = 20) -> str:
    wanted = set(states)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        text = _body_text(driver).lower()
        if "password" in wanted and _has_visible(driver, SELECTORS["password_input_new"]):
            return "password"
        if "details" in wanted and (
            _has_visible(driver, SELECTORS["birth_month_new"])
            or _has_visible(driver, SELECTORS["birth_year_new"])
            or _has_visible(driver, SELECTORS["birth_month"])
        ):
            return "details"
        if "profile" in wanted and _has_visible(driver, SELECTORS["first_name_input"]):
            return "profile"
        if "captcha" in wanted and ("prove you're human" in text or _detect_hsprotect(driver) or _has_visible(driver, SELECTORS["captcha_frame"])):
            return "captcha"
        if "username_unavailable" in wanted and _email_unavailable(driver):
            return "username_unavailable"
        time.sleep(0.25)
    raise TimeoutException(f"outlook_state_timeout states={','.join(states)} title={getattr(driver, 'title', '')} url={getattr(driver, 'current_url', '')}")


def _detect_hsprotect(driver: WebDriver) -> bool:
    text = _body_text(driver).lower()
    if "press and hold the button" in text or "prove you're human" in text:
        return True
    try:
        frames = driver.execute_script(
            """
            return [...document.querySelectorAll('iframe')].map((frame) => {
                const style = window.getComputedStyle(frame);
                const rect = frame.getBoundingClientRect();
                const visible = style.display !== 'none'
                    && style.visibility !== 'hidden'
                    && Number(style.opacity || 1) !== 0
                    && rect.width > 80
                    && rect.height > 50;
                return {
                    src: (frame.src || '').toLowerCase(),
                    title: (frame.title || '').toLowerCase(),
                    visible,
                };
            });
            """
        )
        return any(
            "hsprotect" in str(item.get("src", "")) or "human iframe" in str(item.get("title", ""))
            for item in (frames or [])
            if item.get("visible")
        )
    except Exception:
        return False


def _observed_state(driver: WebDriver) -> str:
    text = _body_text(driver).lower()
    if _has_visible(driver, SELECTORS["email_input_new"]) or _has_visible(driver, SELECTORS["username_input"]):
        return "fill_username"
    if _has_visible(driver, SELECTORS["password_input"]) or _has_visible(driver, SELECTORS["password_input_new"]):
        return "fill_password"
    if _has_visible(driver, SELECTORS["first_name_input"]) or _has_visible(driver, SELECTORS["last_name_input"]):
        return "fill_profile"
    if _has_visible(driver, SELECTORS["birth_month"]) or _has_visible(driver, SELECTORS["birth_month_new"]) or _has_visible(driver, SELECTORS["birth_year"]) or _has_visible(driver, SELECTORS["birth_year_new"]):
        return "fill_birthdate"
    if "privacynotice" in text or "privacy notice" in text or "privacy statement" in text:
        return "privacynotice"
    if "stay signed in" in text:
        return "stay_signed_in"
    if any(token in text for token in ("add security info", "help us protect your account", "recovery email", "add an email")):
        return "add_recovery"
    if _has_visible(driver, SELECTORS["success_message"]) or "quick note about your microsoft account" in text:
        return "success_message"
    if any(token in str(getattr(driver, "current_url", "") or "").lower() for token in ("account.microsoft.com", "outlook.live.com", "mail.live.com")):
        return "account_home"
    if detect_challenge(driver) or _detect_hsprotect(driver):
        return "captcha"
    return "unknown"


def _report_step_timeout(
    flow_report,
    name: str,
    driver: WebDriver,
    exc: Exception,
    *,
    expected_state: str,
) -> None:
    current_url, title, _ = _driver_context(driver)
    observed_state = _observed_state(driver)
    screenshot = flow_report.capture_screenshot(driver, f"outlook.{name}_timeout") if flow_report else ""
    if flow_report:
        flow_report.keep_browser_open = True
        flow_report.block(
            f"outlook.{name}",
            f"{name}_timeout expected={expected_state} observed={observed_state}",
            blocker="selector",
            expected_state=expected_state,
            observed_state=observed_state,
            current_url=current_url,
            title=title,
            screenshot=screenshot,
            latest_screenshot=screenshot,
        )
    raise TimeoutException(
        f"{name}_timeout expected={expected_state} observed={observed_state} title={title} url={current_url}"
    ) from exc


def _driver_context(driver: WebDriver) -> tuple[str, str, str]:
    try:
        current_url = str(getattr(driver, "current_url", "") or "")
    except Exception:
        current_url = ""
    try:
        title = str(getattr(driver, "title", "") or "")
    except Exception:
        title = ""
    return current_url, title, _body_text(driver)


def _browser_error_reason(driver: WebDriver) -> str:
    current_url, title, body = _driver_context(driver)
    haystack = "\n".join([current_url, title, body]).lower()
    for marker in (
        "err_timed_out",
        "err_proxy_connection_failed",
        "err_tunnel_connection_failed",
        "err_connection_reset",
        "err_connection_refused",
        "this site can't be reached",
        "took too long to respond",
    ):
        if marker in haystack:
            return marker.upper()
    return ""


def _is_browser_network_error(exc: Exception) -> bool:
    text = f"{type(exc).__name__}: {exc}".lower()
    return any(
        marker in text
        for marker in (
            "browser_error_page",
            "err_timed_out",
            "err_proxy_connection_failed",
            "err_tunnel_connection_failed",
            "net::err_",
        )
    )


def _button_xpath(*labels: str) -> str:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    lower = "abcdefghijklmnopqrstuvwxyz"
    conditions = []
    for label in labels:
        needle = _xpath_literal(label.lower())
        conditions.append(
            f"contains(translate(normalize-space(.), '{alphabet}', '{lower}'), {needle})"
            f" or contains(translate(@value, '{alphabet}', '{lower}'), {needle})"
        )
    return (
        "//*[self::button or self::a or self::input or @role='button']"
        "[not(@disabled) and (" + " or ".join(conditions) + ")]"
    )


def _click_first_available(driver: WebDriver, selectors: list[Tuple[str, str]], timeout: float = 1.0) -> str:
    for selector in selectors:
        try:
            element = WebDriverWait(driver, timeout).until(
                lambda current_driver: next(
                    (
                        item
                        for item in current_driver.find_elements(*selector)
                        if item.is_displayed() and item.is_enabled()
                    ),
                    False,
                )
            )
            _js_click(driver, element)
            return f"{selector[0]}={selector[1][:80]}"
        except Exception:
            continue
    return ""


def detect_post_challenge_state(driver: WebDriver) -> str:
    current_url, title, body = _driver_context(driver)
    lower_url = current_url.lower()
    lower_text = "\n".join([title, body]).lower()
    if _has_visible(driver, SELECTORS["first_name_input"]) or "add your name" in lower_text:
        return "profile_name"
    if _has_visible(driver, SELECTORS["success_message"]) or "quick note about your microsoft account" in lower_text:
        return "success_message"
    if "stay signed in" in lower_text or _has_visible(driver, (By.ID, "idSIButton9")) or _has_visible(driver, (By.ID, "idBtn_Back")):
        return "stay_signed_in"
    if any(token in lower_text for token in ("add security info", "help us protect your account", "recovery email", "add an email")):
        return "add_recovery"
    if "privacynotice" in lower_url or "privacy notice" in lower_text or "privacy statement" in lower_text:
        return "privacynotice"
    if any(token in lower_url for token in ("account.microsoft.com", "outlook.live.com", "mail.live.com")):
        return "account_home"
    if detect_challenge(driver) or _detect_hsprotect(driver):
        return "challenge_still_present"
    return "unknown_post_challenge"


def _advance_post_challenge_state(driver: WebDriver, state: str) -> str:
    selectors_by_state = {
        "success_message": [
            SELECTORS["ok_button"],
            (By.XPATH, _button_xpath("OK", "Continue", "Next")),
        ],
        "stay_signed_in": [
            (By.ID, "idBtn_Back"),
            (By.XPATH, _button_xpath("No", "Not now")),
        ],
        "add_recovery": [
            (By.XPATH, _button_xpath("Skip", "Skip for now", "Not now", "Maybe later")),
            (By.ID, "iShowSkip"),
        ],
        "privacynotice": [
            (By.XPATH, _button_xpath("OK", "Continue", "Next")),
            SELECTORS["next_button_new"],
            SELECTORS["next_button"],
        ],
    }
    return _click_first_available(driver, selectors_by_state.get(state, []), timeout=1.0)


def handle_post_challenge_state(
    driver: WebDriver,
    flow_report=None,
    timeout: int = POST_CHALLENGE_TIMEOUT,
    first_name: str = "",
    last_name: str = "",
    captcha_provider: str = "",
) -> str:
    _step(flow_report, "post_challenge_state", timeout_seconds=timeout)
    deadline = time.monotonic() + timeout
    last_state = ""
    actions = 0
    profile_filled_count = 0  # Guard against repeated profile filling
    max_profile_fills = 2  # Allow at most 2 profile fills (original + one retry after captcha)
    while time.monotonic() < deadline:
        state = detect_post_challenge_state(driver)
        current_url, title, _ = _driver_context(driver)
        if state != last_state:
            logger.info("[STEP] post_challenge_state=%s url=%s title=%s", state, current_url, title)
            last_state = state
        if state in {"success_message", "account_home"}:
            action = _advance_post_challenge_state(driver, state)
            screenshot = flow_report.capture_screenshot(driver, f"outlook.post_challenge_{state}") if flow_report else ""
            _ok(
                flow_report,
                "post_challenge_state",
                post_challenge_state=state,
                action=action or "<none>",
                last_url=current_url,
                last_title=title,
                latest_screenshot=screenshot,
            )
            return state
        if state == "profile_name":
            profile_filled_count += 1
            if profile_filled_count > max_profile_fills:
                logger.error(
                    "[STEP] post_challenge_state profile_name filled %d times (max %d), skipping to avoid loop",
                    profile_filled_count, max_profile_fills,
                )
                # Try clicking Next directly instead of re-filling the form
                _click_first_available(driver, [
                    SELECTORS["next_button_new"],
                    SELECTORS["next_button"],
                    (By.XPATH, _button_xpath("Next", "Continue", "Submit")),
                ], timeout=2.0)
                time.sleep(2)
                continue
            logger.info("[STEP] post_challenge_action state=profile_name action=fill_profile (count=%d)", profile_filled_count)
            next_state = fill_profile_step(driver, first_name, last_name, flow_report=flow_report)
            actions += 1
            if next_state == "captcha":
                handle_captcha(driver, flow_report=flow_report, captcha_provider=captcha_provider)
                actions += 1
            time.sleep(1)
            continue
        action = _advance_post_challenge_state(driver, state)
        if action:
            actions += 1
            logger.info("[OK] post_challenge_action state=%s action=%s", state, action)
            time.sleep(2)
            continue
        time.sleep(1)

    screenshot = flow_report.capture_screenshot(driver, "outlook.post_challenge_unknown") if flow_report else ""
    current_url, title, _ = _driver_context(driver)
    if flow_report:
        flow_report.keep_browser_open = True
        flow_report.block(
            "outlook.post_challenge_state",
            f"unknown_post_challenge state={last_state or 'unknown_post_challenge'}",
            blocker="selector",
            post_challenge_state=last_state or "unknown_post_challenge",
            actions=actions,
            last_url=current_url,
            last_title=title,
            latest_screenshot=screenshot,
            screenshot=screenshot,
        )
    raise AccountCreationError(f"unknown_post_challenge state={last_state or 'unknown_post_challenge'}")


def _select_outlook_domain(driver: WebDriver, hotmail: bool) -> None:
    desired = "@hotmail.com" if hotmail else "@outlook.com"
    if _has_visible(driver, SELECTORS["domain_select"]):
        if hotmail:
            select_dropdown_by_index(driver, SELECTORS["domain_select"], 1)
        return
    if not _has_visible(driver, SELECTORS["domain_dropdown_new"]):
        return
    dropdown = _visible_elements(driver, SELECTORS["domain_dropdown_new"])[0]
    current = (dropdown.text or "").strip().lower()
    if desired.lower() in current:
        return
    try:
        _select_fluent_option(driver, SELECTORS["domain_dropdown_new"], desired)
    except Exception as exc:
        logger.warning("[CREATE] provider=outlook step=domain_select status=failed desired=%s reason=%s", desired, exc)


def _step(flow_report, name: str, **details) -> None:
    logger.info("[STEP] provider=outlook step=%s", name)
    if flow_report:
        flow_report.start_step(f"outlook.{name}", **details)


def _ok(flow_report, name: str, **details) -> None:
    logger.info("[OK] provider=outlook step=%s", name)
    if flow_report:
        flow_report.ok(f"outlook.{name}", **details)


def _fail(flow_report, name: str, exc: Exception, driver: Optional[WebDriver] = None) -> None:
    logger.error("[BLOCK] provider=outlook step=%s error=%s", name, exc)
    if flow_report:
        if driver is not None:
            flow_report.capture_screenshot(driver, f"outlook.{name}")
        if getattr(flow_report, "mode", "") == "visible_flow_probe" and not _is_browser_network_error(exc):
            flow_report.keep_browser_open = True
        flow_report.fail(f"outlook.{name}", exc)

def select_dropdown(driver: WebDriver, by: Tuple[str, str], value: str) -> None:
    """Select an option from a dropdown menu"""
    element = WebDriverWait(driver, WAIT_TIMEOUT).until(
        EC.presence_of_element_located(by)
    )
    Select(element).select_by_visible_text(value)

def select_dropdown_by_index(driver: WebDriver, by: Tuple[str, str], index: int) -> None:
    """Select a dropdown option by index"""
    element = WebDriverWait(driver, WAIT_TIMEOUT).until(
        EC.presence_of_element_located(by)
    )
    Select(element).select_by_index(index)


def fill_username_step(driver: WebDriver, username: str, hotmail: bool, flow_report=None) -> str:
    for attempt, local in enumerate(_username_candidates(username), 1):
        _step(flow_report, "fill_username_attempt", attempt=attempt, candidate=local, hotmail=hotmail)
        try:
            wait_and_click(driver, SELECTORS["email_switch"], timeout=2)
            time.sleep(random.uniform(0.3, 0.8))
            uname_input = _first_present(driver, [SELECTORS["username_input"]])
            try:
                uname_input.click()
            except Exception:
                driver.execute_script("arguments[0].focus();", uname_input)
            time.sleep(random.uniform(0.2, 0.5))
            _human_type(uname_input, local)
            time.sleep(random.uniform(0.3, 0.7))
            _select_outlook_domain(driver, hotmail)
        except TimeoutException:
            logger.info("[CREATE] provider=outlook step=fill_username layout=new_email_input attempt=%s", attempt)
            email_input = _first_present(driver, [SELECTORS["email_input_new"], SELECTORS["username_input"]])
            has_domain_dropdown = _has_visible(driver, SELECTORS["domain_dropdown_new"])
            value = local if has_domain_dropdown else f"{local}@{'hotmail' if hotmail else 'outlook'}.com"
            try:
                email_input.click()
            except Exception:
                driver.execute_script("arguments[0].focus();", email_input)
            time.sleep(random.uniform(0.2, 0.5))
            _human_type(email_input, value)
            time.sleep(random.uniform(0.3, 0.7))
            _select_outlook_domain(driver, hotmail)

        _click_next(driver)
        try:
            state = _wait_for_state(driver, "password", "username_unavailable", timeout=18)
        except TimeoutException as exc:
            _report_step_timeout(
                flow_report,
                "fill_username_attempt",
                driver,
                exc,
                expected_state="password|username_unavailable",
            )
        if state == "password":
            _ok(flow_report, "fill_username_attempt", selected=local, attempt=attempt)
            return local
        logger.warning("[CREATE] provider=outlook step=fill_username candidate=%s status=unavailable", local)
        _ok(flow_report, "fill_username_attempt", selected=local, attempt=attempt, status="unavailable")

    raise AccountCreationError("username_unavailable: exhausted Outlook username candidates")


def fill_password_step(driver: WebDriver, password: str, flow_report=None) -> str:
    _step(flow_report, "fill_password")
    try:
        wait_and_click(driver, SELECTORS["show_password"], timeout=2)
        time.sleep(random.uniform(0.3, 0.7))
        wait_and_click(driver, SELECTORS["optin_email"], timeout=2)
        time.sleep(random.uniform(0.2, 0.5))
    except TimeoutException:
        logger.debug("Optional password visibility elements not found")

    password_input = _first_present(driver, [SELECTORS["password_input"], SELECTORS["password_input_new"]])
    # Human-like: click focus, then type with random delays
    try:
        password_input.click()
    except Exception:
        driver.execute_script("arguments[0].focus();", password_input)
    time.sleep(random.uniform(0.2, 0.5))
    _human_type(password_input, password)
    time.sleep(random.uniform(0.3, 0.8))
    _click_next(driver)
    try:
        state = _wait_for_state(driver, "details", "profile", timeout=20)
    except TimeoutException as exc:
        _report_step_timeout(
            flow_report,
            "fill_password",
            driver,
            exc,
            expected_state="details|profile",
        )
    _ok(flow_report, "fill_password", next_state=state)
    return state


def fill_birthdate_step(driver: WebDriver, country: str, month: str, day: str, year: str, flow_report=None) -> str:
    _step(flow_report, "fill_birthdate", country=country)
    if _has_visible(driver, SELECTORS["country_select"]):
        select_dropdown(driver, SELECTORS["country_select"], country)
    elif _has_visible(driver, (By.ID, "countryDropdownId")):
        normalized_country = _normalize_country(country)
        if normalized_country:
            try:
                _select_fluent_option(driver, (By.ID, "countryDropdownId"), normalized_country)
            except Exception as exc:
                logger.warning("[CREATE] provider=outlook step=country_select status=kept_default desired=%s reason=%s", normalized_country, exc)

    if _has_visible(driver, SELECTORS["birth_month"]):
        select_dropdown_by_index(driver, SELECTORS["birth_month"], int(month))
        select_dropdown_by_index(driver, SELECTORS["birth_day"], int(day))
        set_input_value(driver, SELECTORS["birth_year"], year)
    else:
        _select_fluent_option(driver, SELECTORS["birth_month_new"], _month_name(month))
        _select_fluent_option(driver, SELECTORS["birth_day_new"], str(int(day)))
        year_input = _first_present(driver, [SELECTORS["birth_year_new"], SELECTORS["birth_year"]])
        _clear_and_type(year_input, year)

    _click_next(driver)
    try:
        state = _wait_for_state(driver, "profile", "captcha", timeout=20)
    except TimeoutException as exc:
        _report_step_timeout(
            flow_report,
            "fill_birthdate",
            driver,
            exc,
            expected_state="profile|captcha",
        )
    _ok(flow_report, "fill_birthdate", next_state=state)
    return state


def fill_profile_step(driver: WebDriver, first_name: str, last_name: str, flow_report=None) -> str:
    _step(flow_report, "fill_profile")

    # Check if the form is pre-filled (e.g., called again after captcha)
    # Only type if the fields are empty or have different values
    fn_input = _first_present(driver, [SELECTORS["first_name_input"]])
    try:
        fn_input.click()
    except Exception:
        driver.execute_script("arguments[0].focus();", fn_input)
    time.sleep(random.uniform(0.2, 0.5))

    current_fn = fn_input.get_attribute("value") or ""
    if current_fn.strip() != first_name.strip():
        _human_type(fn_input, first_name)
        time.sleep(random.uniform(0.3, 0.7))
    else:
        logger.info("[STEP] fill_profile first_name already filled, skipping typing")

    ln_input = _first_present(driver, [SELECTORS["last_name_input"]])
    try:
        ln_input.click()
    except Exception:
        driver.execute_script("arguments[0].focus();", ln_input)
    time.sleep(random.uniform(0.2, 0.5))

    current_ln = ln_input.get_attribute("value") or ""
    if current_ln.strip() != last_name.strip():
        _human_type(ln_input, last_name)
        time.sleep(random.uniform(0.3, 0.8))
    else:
        logger.info("[STEP] fill_profile last_name already filled, skipping typing")

    # Try clicking Next with retries to ensure the form actually submits
    max_next_attempts = 3
    state = None
    for attempt in range(max_next_attempts):
        _click_next(driver)
        try:
            state = _wait_for_state(driver, "details", "captcha", timeout=15)
            break  # Successfully transitioned
        except TimeoutException:
            # Check if we're still on the profile page (Next click may not have worked)
            if _has_visible(driver, SELECTORS["first_name_input"]):
                logger.warning(
                    "[STEP] fill_profile still on profile page after Next click (attempt %d/%d), retrying",
                    attempt + 1, max_next_attempts,
                )
                # Try a more aggressive click via JavaScript
                try:
                    next_btn = _first_clickable(driver, [SELECTORS["next_button_new"], SELECTORS["next_button"]], timeout=3)
                    driver.execute_script("arguments[0].click();", next_btn)
                    time.sleep(1.0)
                except Exception:
                    pass
                continue
            else:
                # Page changed but not to expected state
                break

    if state is None:
        exc = TimeoutException("fill_profile: page did not transition after Next click")
        _report_step_timeout(
            flow_report,
            "fill_profile",
            driver,
            exc,
            expected_state="details|captcha",
        )

    _ok(flow_report, "fill_profile", next_state=state)
    return state

# ---------------------------------------------------------------------------
# FunCaptcha (Arkose Labs) smart solver
# ---------------------------------------------------------------------------

# FunCaptcha monitor JS — purely graphical progress bar, detect by confirm button appearance
FUNCAPTCHA_MONITOR_JS = """
(function() {
    var result = {
        hasConfirmButton: false,
        confirmText: '',
        buttonText: '',
        allButtons: [],
        domSnapshot: ''
    };

    // Detect confirm / action buttons (key signal: progress bar completed)
    var keywords = [
        'click again', 'continue', 'verify', 'confirm', 'submit',
        'next', 'try again', 'reload', 'solve',
        '\u518d\u6b21\u70b9\u51fb', '\u7ee7\u7eed', '\u786e\u8ba4', '\u9a8c\u8bc1', '\u63d0\u4ea4'
    ];
    var buttons = document.querySelectorAll('button, [role="button"], a[role="button"]');
    var visibleButtons = [];
    for (var b = 0; b < buttons.length; b++) {
        var btn = buttons[b];
        if (!btn.offsetParent && !btn.offsetWidth) continue; // skip invisible
        var text = (btn.innerText || btn.textContent || btn.getAttribute('aria-label') || '').toLowerCase().trim();
        visibleButtons.push(text || '(no-text)');
        if (!text) continue;
        result.buttonText = text;
        for (var k = 0; k < keywords.length; k++) {
            if (text.indexOf(keywords[k]) !== -1) {
                result.hasConfirmButton = true;
                result.confirmText = text;
                break;
            }
        }
        if (result.hasConfirmButton) break;
    }
    result.allButtons = visibleButtons;

    // Brief DOM snapshot for debugging
    try {
        var bodyText = (document.body ? document.body.innerText : '').substring(0, 200);
        result.domSnapshot = bodyText;
    } catch(e) {}

    return result;
})();
"""

# Selectors for the confirm / "click again" button
FUNCAPTCHA_CONFIRM_BUTTON_SELECTORS = [
    (By.XPATH, "//button[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'click again')]"),
    (By.XPATH, "//button[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'continue')]"),
    (By.XPATH, "//button[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'verify')]"),
    (By.XPATH, "//button[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'confirm')]"),
    (By.CSS_SELECTOR, "div#root button"),
    (By.XPATH, "//button[not(@disabled) and string-length(normalize-space(.)) > 0]"),
]


def _human_like_click(driver: WebDriver, element) -> None:
    """Simulate human-like click with scroll + hover + random delay."""
    driver.execute_script(
        "arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});",
        element,
    )
    time.sleep(random.uniform(0.1, 0.35))
    try:
        actions = ActionChains(driver)
        actions.move_to_element(element)
        actions.pause(random.uniform(0.05, 0.2))
        actions.click()
        actions.perform()
    except Exception:
        _js_click(driver, element)


def _human_like_long_press(driver: WebDriver, element, duration: float = 3.0) -> None:
    """
    Simulate human-like long press (click and hold) for progress bar interaction.
    
    Args:
        element: The element to long-press
        duration: How long to hold (default 3s, random added)
    """
    driver.execute_script(
        "arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});",
        element,
    )
    time.sleep(random.uniform(0.1, 0.3))
    
    actual_duration = duration + random.uniform(-0.5, 1.0)
    actual_duration = max(2.0, actual_duration)  # minimum 2s hold
    
    try:
        actions = ActionChains(driver)
        actions.move_to_element(element)
        actions.pause(random.uniform(0.05, 0.15))
        actions.click_and_hold()
        actions.pause(actual_duration)
        actions.release()
        actions.perform()
        logger.info("[FunCaptcha] Long-pressed element for %.2fs", actual_duration)
    except Exception as e:
        logger.warning("[FunCaptcha] ActionChains long-press failed: %s, using JS fallback", e)
        # JS fallback: dispatch pointer events
        driver.execute_script(
            """
            var el = arguments[0];
            var dur = arguments[1];
            el.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true}));
            setTimeout(function() {
                el.dispatchEvent(new PointerEvent('pointerup', {bubbles: true}));
            }, dur * 1000);
            """,
            element,
            actual_duration,
        )


def _trigger_funcaptcha_method1_click(driver: WebDriver) -> bool:
    """
    Method 1: Click the left-side human/figure icon to start progress bar.
    """
    # Selectors for the left-side human icon button
    icon_selectors = [
        (By.CSS_SELECTOR, "button[aria-label*='human']"),
        (By.CSS_SELECTOR, "button[aria-label*='figure']"),
        (By.CSS_SELECTOR, "button[aria-label*='person']"),
        (By.CSS_SELECTOR, "div[role='button'][aria-label*='human']"),
        (By.XPATH, "//button[contains(@aria-label, 'human') or contains(@aria-label, 'figure')]"),
        # Generic: first button in the captcha area
        (By.CSS_SELECTOR, "div#root button:first-child"),
        (By.CSS_SELECTOR, "#game-core-frame button:first-of-type"),
    ]
    
    for selector in icon_selectors:
        try:
            btn = WebDriverWait(driver, 2).until(
                EC.element_to_be_clickable(selector)
            )
            _human_like_click(driver, btn)
            logger.info("[FunCaptcha] Method1: Clicked left-side icon via %s", selector)
            return True
        except Exception:
            continue
    
    # Fallback: find leftmost clickable element
    try:
        clicked = driver.execute_script(
            """
            var btns = document.querySelectorAll('button, [role="button"]');
            if (btns.length > 0) {
                var btn = btns[0];
                btn.scrollIntoView({block:'center'});
                btn.click();
                return true;
            }
            return false;
            """
        )
        if clicked:
            logger.info("[FunCaptcha] Method1: Clicked first button via JS fallback")
            return True
    except Exception:
        pass
    
    return False


def _trigger_funcaptcha_method2_longpress(driver: WebDriver) -> bool:
    """
    Method 2: Long-press the middle progress bar area to start filling.
    """
    # Selectors for the progress bar / middle area
    progress_selectors = [
        (By.CSS_SELECTOR, "[role='progressbar']"),
        (By.CSS_SELECTOR, "div[class*='progress']"),
        (By.CSS_SELECTOR, "div[class*='bar']"),
        (By.XPATH, "//div[contains(@class, 'progress') or contains(@class, 'bar')]"),
        (By.CSS_SELECTOR, "svg[class*='progress']"),
        (By.CSS_SELECTOR, "#game-core-frame div"),
    ]
    
    for selector in progress_selectors:
        try:
            elem = WebDriverWait(driver, 2).until(
                EC.presence_of_element_located(selector)
            )
            if not elem.is_displayed():
                continue
            _human_like_long_press(driver, elem, duration=3.5)
            logger.info("[FunCaptcha] Method2: Long-pressed progress bar via %s", selector)
            return True
        except Exception:
            continue
    
    # Fallback: find a large clickable area in the center and long-press it
    try:
        result = driver.execute_script(
            """
            var divs = document.querySelectorAll('div');
            var candidates = [];
            for (var i = 0; i < divs.length; i++) {
                var d = divs[i];
                var rect = d.getBoundingClientRect();
                if (rect.width > 50 && rect.height > 30 && d.offsetParent !== null) {
                    candidates.push({elem: d, area: rect.width * rect.height});
                }
            }
            if (candidates.length > 0) {
                candidates.sort(function(a, b) { return b.area - a.area; });
                candidates[0].elem.scrollIntoView({block:'center'});
                return candidates[0].elem;
            }
            return null;
            """
        )
        if result:
            _human_like_long_press(driver, result, duration=3.5)
            logger.info("[FunCaptcha] Method2: Long-pressed largest center area via JS")
            return True
    except Exception:
        pass
    
    return False


def _trigger_funcaptcha_initial(driver: WebDriver, prefer_method: int = 1) -> bool:
    """
    Trigger FunCaptcha using one of two methods:
    
    Method 1: Click the left-side human/figure icon (single click)
    Method 2: Long-press the middle progress bar area
    
    Args:
        driver: WebDriver instance
        prefer_method: 1 or 2, which method to try first
    
    Returns:
        True if successfully triggered, False otherwise
    """
    methods = []
    if prefer_method == 1:
        methods = [_trigger_funcaptcha_method1_click, _trigger_funcaptcha_method2_longpress]
    else:
        methods = [_trigger_funcaptcha_method2_longpress, _trigger_funcaptcha_method1_click]
    
    for method_func in methods:
        try:
            if method_func(driver):
                return True
        except Exception as e:
            logger.warning("[FunCaptcha] Method failed: %s", e)
            continue
    
    return False


def _click_funcaptcha_confirm(driver: WebDriver, confirm_text: str = "") -> bool:
    """Click the confirm / 'click again' button after progress bar fills."""
    # Try keyword-based selectors first
    for selector in FUNCAPTCHA_CONFIRM_BUTTON_SELECTORS:
        try:
            btn = WebDriverWait(driver, 2).until(
                EC.element_to_be_clickable(selector)
            )
            _human_like_click(driver, btn)
            logger.info("[FunCaptcha] Clicked confirm button via %s", selector)
            return True
        except Exception:
            continue

    # Fallback: find any visible button with matching text
    if confirm_text:
        try:
            btns = driver.find_elements(By.TAG_NAME, "button")
            for btn in btns:
                if not btn.is_displayed() or not btn.is_enabled():
                    continue
                text = (btn.text or btn.get_attribute("aria-label") or "").lower()
                if confirm_text.lower() in text:
                    _human_like_click(driver, btn)
                    logger.info("[FunCaptcha] Clicked confirm button by text match: %s", text)
                    return True
        except Exception:
            pass

    # Last resort: click any newly visible button (not the initial one)
    try:
        driver.execute_script(
            """
            var btns = document.querySelectorAll('button');
            var clicked = false;
            for (var i = btns.length - 1; i >= 0; i--) {
                if (btns[i].offsetParent !== null && !btns[i].disabled) {
                    btns[i].scrollIntoView({block:'center'});
                    btns[i].click();
                    clicked = true;
                    break;
                }
            }
            return clicked;
            """
        )
        logger.info("[FunCaptcha] Clicked confirm via JS fallback")
        return True
    except Exception:
        return False


def _human_type(element, value: str, min_delay: float = 0.05, max_delay: float = 0.15) -> None:
    """Type text character by character with random delays to simulate human typing."""
    try:
        element.clear()
    except Exception:
        pass
    for char in str(value):
        element.send_keys(char)
        time.sleep(random.uniform(min_delay, max_delay))


def _switch_to_game_core_frame(driver: WebDriver, retries: int = 5) -> bool:
    """Switch WebDriver context into game-core-frame with robust retry logic."""
    for attempt in range(retries):
        try:
            driver.switch_to.default_content()
            time.sleep(0.5)
            # Strategy 1: enforcementFrame -> iframe -> game-core-frame
            try:
                WebDriverWait(driver, 5).until(
                    EC.frame_to_be_available_and_switch_to_it(SELECTORS["captcha_frame"])
                )
                time.sleep(0.3)
                iframes = driver.find_elements(By.TAG_NAME, "iframe")
                if iframes:
                    driver.switch_to.frame(iframes[0])
                    time.sleep(0.3)
                WebDriverWait(driver, 5).until(
                    EC.frame_to_be_available_and_switch_to_it((By.ID, "game-core-frame"))
                )
                time.sleep(0.3)
                return True
            except Exception:
                pass
            # Strategy 2: brute-force all iframes
            try:
                driver.switch_to.default_content()
                time.sleep(0.3)
                for iframe in driver.find_elements(By.TAG_NAME, "iframe"):
                    try:
                        driver.switch_to.frame(iframe)
                        time.sleep(0.2)
                        gf = driver.find_elements(By.ID, "game-core-frame")
                        if gf:
                            driver.switch_to.frame(gf[0])
                            return True
                        for ni in driver.find_elements(By.TAG_NAME, "iframe"):
                            driver.switch_to.frame(ni)
                            gf2 = driver.find_elements(By.ID, "game-core-frame")
                            if gf2:
                                driver.switch_to.frame(gf2[0])
                                return True
                            driver.switch_to.parent_frame()
                        driver.switch_to.parent_frame()
                    except Exception:
                        driver.switch_to.default_content()
            except Exception:
                pass
            logger.warning("[FunCaptcha] iframe switch attempt %d/%d failed", attempt + 1, retries)
            time.sleep(1)
        except Exception as e:
            logger.warning("[FunCaptcha] iframe switch attempt %d/%d error: %s", attempt + 1, retries, e)
            time.sleep(1)
    # Final: check if game-core-frame exists without iframe
    try:
        driver.switch_to.default_content()
        if driver.find_elements(By.ID, "game-core-frame"):
            return True
    except Exception:
        pass
    return False


def _handle_hsprotect(driver: WebDriver, flow_report=None, timeout: int = 120) -> bool:
    """Auto-handle HUMAN Security (hsprotect) press-and-hold challenge."""
    _step(flow_report, "hsprotect_auto")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            driver.switch_to.default_content()
            if not _detect_hsprotect(driver):
                _ok(flow_report, "hsprotect_auto", result="cleared")
                return True
            btn = None
            for sel in [
                (By.XPATH, "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'press')]"),
                (By.XPATH, "//div[@role='button'][contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'press')]"),
                (By.CSS_SELECTOR, "[class*='press']"),
                (By.TAG_NAME, "button"),
            ]:
                for el in driver.find_elements(*sel):
                    if el.is_displayed() and el.is_enabled():
                        txt = (el.text or el.get_attribute("aria-label") or "").lower()
                        if any(k in txt for k in ["press", "hold", "human", "verify", "prove"]):
                            btn = el
                            break
                if btn:
                    break
            if not btn:
                for iframe in driver.find_elements(By.TAG_NAME, "iframe"):
                    try:
                        driver.switch_to.frame(iframe)
                        for sel in [(By.TAG_NAME, "button"), (By.XPATH, "//div[@role='button']")]:
                            for el in driver.find_elements(*sel):
                                if el.is_displayed() and el.is_enabled():
                                    btn = el
                                    break
                            if btn:
                                break
                        if btn:
                            break
                        driver.switch_to.parent_frame()
                    except Exception:
                        try:
                            driver.switch_to.parent_frame()
                        except Exception:
                            pass
            if btn:
                hold_dur = random.uniform(3.5, 5.0)
                try:
                    actions = ActionChains(driver)
                    actions.move_to_element(btn).pause(0.2).click_and_hold().pause(hold_dur).release().perform()
                except Exception:
                    driver.execute_script(
                        "var el=arguments[0];el.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}));"
                        "setTimeout(function(){el.dispatchEvent(new PointerEvent('pointerup',{bubbles:true}));},arguments[1]*1000);",
                        btn, hold_dur)
                time.sleep(random.uniform(1.0, 2.0))
        except Exception as e:
            logger.warning("[hsprotect] error: %s", e)
            try:
                driver.switch_to.default_content()
            except Exception:
                pass
        time.sleep(2)
    return False


def _handle_funcaptcha_smart(driver: WebDriver, flow_report=None, timeout: int = 90) -> bool:
    """
    Smart FunCaptcha handler for Arkose Labs challenges.

    Workflow:
        1. Switch into game-core-frame iframe
        2. Trigger the captcha using Method 1 (click) or Method 2 (long-press)
        3. Poll for confirm button appearance (progress bar is graphical, no percentage)
        4. Click confirm when it appears
        5. Retry with alternate method if no confirm appears
        6. Return True on success, False on failure
    """
    _step(flow_report, "funcaptcha_smart", timeout_seconds=timeout)

    if not _switch_to_game_core_frame(driver):
        logger.error("[FunCaptcha] Failed to switch into game-core-frame")
        return False

    # --- Phase 1: Trigger captcha with Method 1 (click) first ---
    time.sleep(random.uniform(0.5, 1.0))
    current_method = 1
    if not _trigger_funcaptcha_initial(driver, prefer_method=current_method):
        logger.warning("[FunCaptcha] Could not trigger with Method 1, trying Method 2")
        current_method = 2
        if not _trigger_funcaptcha_initial(driver, prefer_method=current_method):
            logger.error("[FunCaptcha] Both trigger methods failed")
            return False
    
    _ok(flow_report, f"funcaptcha_trigger_method{current_method}")
    time.sleep(random.uniform(1.0, 2.0))  # Wait for progress bar to start

    # --- Phase 2: Monitor for confirm button appearance ---
    deadline = time.monotonic() + timeout
    confirm_clicks = 0
    max_confirm_rounds = 5
    no_confirm_checks = 0
    max_no_confirm_checks = 20  # ~10s with 0.5s polling
    last_method_used = current_method

    while time.monotonic() < deadline:
        try:
            result = driver.execute_script(FUNCAPTCHA_MONITOR_JS)
            if not result or not isinstance(result, dict):
                time.sleep(0.5)
                continue

            has_confirm = bool(result.get("hasConfirmButton", False))
            confirm_text = str(result.get("confirmText", "") or "")
            button_text = str(result.get("buttonText", "") or "")
            all_buttons = result.get("allButtons", [])
            dom_snap = str(result.get("domSnapshot", "") or "")[:100]

            # Log state periodically
            if no_confirm_checks % 5 == 0:
                logger.info(
                    "[FunCaptcha] hasConfirm=%s | confirmText='%s' | buttons=%s | dom='%s'",
                    has_confirm, confirm_text, all_buttons[:3], dom_snap,
                )

            # --- Confirm button appeared ---
            if has_confirm:
                time.sleep(random.uniform(0.3, 0.7))  # Human-like reaction

                if _click_funcaptcha_confirm(driver, confirm_text):
                    confirm_clicks += 1
                    logger.info(
                        "[FunCaptcha] Clicked confirm (#%d) | text='%s'",
                        confirm_clicks, confirm_text,
                    )
                    _ok(flow_report, f"funcaptcha_confirm_{confirm_clicks}")
                    time.sleep(random.uniform(1.0, 2.0))

                    # Check if challenge cleared
                    try:
                        driver.switch_to.default_content()
                        current_url = str(getattr(driver, "current_url", "") or "").lower()
                        body_lower = _body_text(driver).lower()

                        if any(token in current_url for token in ("privacynotice", "account.microsoft.com", "outlook.live.com", "mail.live.com")):
                            logger.info("[FunCaptcha] Challenge cleared! URL=%s", current_url)
                            _ok(flow_report, "funcaptcha_smart", result="challenge_cleared_url")
                            return True
                        if any(token in body_lower for token in ("quick note about your microsoft account", "stay signed in", "privacy notice")):
                            logger.info("[FunCaptcha] Challenge cleared! Body text indicates next step.")
                            return True
                        if _has_visible(driver, SELECTORS["first_name_input"]):
                            logger.info("[FunCaptcha] Challenge cleared! Profile form visible.")
                            return True

                        # Re-enter frame and continue monitoring
                        if not _switch_to_game_core_frame(driver):
                            if not _has_visible(driver, SELECTORS["captcha_frame"]):
                                logger.info("[FunCaptcha] Captcha frame gone, challenge cleared")
                                return True
                            return False
                    except Exception as e:
                        logger.warning("[FunCaptcha] Post-confirm check error: %s", e)
                        try:
                            driver.switch_to.default_content()
                            if not _switch_to_game_core_frame(driver):
                                return False
                        except Exception:
                            return False

                    if confirm_clicks >= max_confirm_rounds:
                        logger.warning("[FunCaptcha] Max confirm rounds reached")
                        break
                    continue

            # --- No confirm button for too long → retry with alternate method ---
            no_confirm_checks += 1
            if no_confirm_checks >= max_no_confirm_checks:
                alternate_method = 2 if last_method_used == 1 else 1
                logger.info(
                    "[FunCaptcha] No confirm for %d checks, trying Method %d",
                    no_confirm_checks, alternate_method,
                )
                
                if _trigger_funcaptcha_initial(driver, prefer_method=alternate_method):
                    last_method_used = alternate_method
                    _ok(flow_report, f"funcaptcha_retry_method{alternate_method}")
                    no_confirm_checks = 0
                    time.sleep(random.uniform(1.0, 2.0))
                else:
                    logger.warning("[FunCaptcha] Retry method %d failed", alternate_method)
                    no_confirm_checks = 0  # Reset to avoid immediate retry spam

            time.sleep(0.5)

        except Exception as e:
            logger.warning("[FunCaptcha] Monitor error: %s", e)
            try:
                driver.switch_to.default_content()
                current_url = str(getattr(driver, "current_url", "") or "").lower()
                if any(token in current_url for token in ("privacynotice", "account.microsoft.com", "outlook.live.com")):
                    return True
                if not _switch_to_game_core_frame(driver):
                    if not _has_visible(driver, SELECTORS["captcha_frame"]):
                        return True
                    return False
            except Exception:
                return False

    logger.warning("[FunCaptcha] Timed out after %ds (confirm_clicks=%d)", timeout, confirm_clicks)
    return False


# ---------------------------------------------------------------------------
# Main captcha handler
# ---------------------------------------------------------------------------

def handle_captcha(driver: WebDriver, flow_report=None, captcha_provider: str = "") -> None:
    """Handle Microsoft account captcha challenge"""
    
    # CRITICAL: Wait for iframe to appear before detection (FunCaptcha loads asynchronously)
    iframe_wait_attempts = 5
    for attempt in range(iframe_wait_attempts):
        # First check if captcha frame is already visible
        if _has_visible(driver, SELECTORS["captcha_frame"]):
            logger.info("[FunCaptcha] enforcementFrame visible after %d checks", attempt + 1)
            break
        
        # Poll for iframe appearance
        try:
            WebDriverWait(driver, 2).until(
                EC.presence_of_element_located(SELECTORS["captcha_frame"])
            )
            # Additional wait for iframe to become visible
            time.sleep(0.5)
            if _has_visible(driver, SELECTORS["captcha_frame"]):
                logger.info("[FunCaptcha] enforcementFrame became visible on attempt %d", attempt + 1)
                break
        except TimeoutException:
            pass
        
        # Check for hsprotect as fallback
        if _detect_hsprotect(driver):
            logger.info("[Captcha] hsprotect detected on attempt %d", attempt + 1)
            break
        
        time.sleep(0.5)
    
    # Now run detection with iframe likely loaded
    challenge = detect_challenge(driver)
    if (challenge and challenge.kind == "hsprotect") or _detect_hsprotect(driver):
        _step(flow_report, "captcha_hsprotect", provider="hsprotect")
        challenge = challenge or ChallengeInfo(
            kind="hsprotect",
            label="HUMAN Security press-and-hold",
            evidence="press and hold challenge detected",
            current_url=getattr(driver, "current_url", ""),
            title=getattr(driver, "title", ""),
        )
        # Try auto-handler first
        auto_ok = _handle_hsprotect(driver, flow_report, timeout=120)
        if auto_ok:
            _ok(flow_report, "captcha_hsprotect", result="auto_cleared")
            return
        # Fallback to manual takeover
        logger.warning("[hsprotect] Auto-handler did not clear, falling back to manual")
        wait_for_manual_takeover(
            driver,
            flow_report,
            provider="outlook",
            challenge=challenge,
            captcha_provider=captcha_provider,
            timeout_seconds=MANUAL_CHALLENGE_TIMEOUT,
        )
        _ok(flow_report, "captcha_hsprotect")
        return

    if not challenge and not _detect_hsprotect(driver) and not _has_visible(driver, SELECTORS["captcha_frame"]):
        _step(flow_report, "captcha_skip", observed_state=_observed_state(driver))
        _ok(flow_report, "captcha_skip", reason="no_visible_captcha")
        return

    # --- FunCaptcha: use smart solver ---
    if challenge and challenge.kind == "funcaptcha":
        _step(flow_report, "captcha_funcaptcha_smart")
        try:
            success = _handle_funcaptcha_smart(driver, flow_report, timeout=FUNCAPTCHA_SMART_TIMEOUT)
            if success:
                _ok(flow_report, "captcha_funcaptcha_smart")
                return
            # Smart solver failed — fall through to manual fallback below
            logger.warning("[FunCaptcha] Smart solver did not succeed, falling back")
        except Exception as e:
            logger.warning("[FunCaptcha] Smart solver exception: %s", e)
            try:
                driver.switch_to.default_content()
            except Exception:
                pass

    # --- Fallback / legacy FunCaptcha handling ---
    # If challenge is funcaptcha (smart solver failed) or detected as generic captcha
    if challenge or _has_visible(driver, SELECTORS["captcha_frame"]):
        _step(flow_report, "captcha_frame_fallback")
        success = False
        try:
            # Switch to captcha frames
            WebDriverWait(driver, WAIT_TIMEOUT).until(
                EC.frame_to_be_available_and_switch_to_it(SELECTORS["captcha_frame"])
            )
            WebDriverWait(driver, WAIT_TIMEOUT).until(
                EC.frame_to_be_available_and_switch_to_it((By.TAG_NAME, "iframe"))
            )
            WebDriverWait(driver, WAIT_TIMEOUT).until(
                EC.frame_to_be_available_and_switch_to_it((By.ID, "game-core-frame"))
            )

            # Initial captcha click
            wait_and_click(driver, (By.CSS_SELECTOR, "div#root > div > div > button"))
            _ok(flow_report, "captcha_frame")

            # Handle potential retries — wait for URL change
            _step(flow_report, "captcha_wait", timeout_seconds=CAPTCHA_RETRY_DELAY)
            for _ in range(MAX_CAPTCHA_RETRIES):
                try:
                    WebDriverWait(driver, CAPTCHA_RETRY_DELAY).until(
                        EC.url_contains('privacynotice')
                    )
                    if 'privacynotice' in driver.current_url:
                        success = True
                        break
                except TimeoutException:
                    continue
            if not success:
                raise AccountCreationError("The captcha was not solved")
            _ok(flow_report, "captcha_wait")
        except Exception as e:
            if _detect_hsprotect(driver):
                driver.switch_to.default_content()
                return handle_captcha(driver, flow_report=flow_report, captcha_provider=captcha_provider)
            logger.error("Captcha handling failed: %s", str(e))
            _fail(flow_report, "captcha", e, driver)
            raise AccountCreationError("Captcha challenge failed") from e
        finally:
            driver.switch_to.default_content()
        return

    # Should not reach here, but just in case
    _step(flow_report, "captcha_unknown_fallback")
    challenge_info = challenge or ChallengeInfo(
        kind="unknown",
        label="Unknown captcha",
        evidence="captcha detected but type unclear",
        current_url=getattr(driver, "current_url", ""),
        title=getattr(driver, "title", ""),
    )
    wait_for_manual_takeover(
        driver,
        flow_report,
        provider="outlook",
        challenge=challenge_info,
        captcha_provider=captcha_provider,
        timeout_seconds=MANUAL_CHALLENGE_TIMEOUT,
    )

def verify_account_creation(driver: WebDriver, flow_report=None) -> bool:
    """Verify successful account creation and complete final steps"""
    try:
        _step(flow_report, "success_verify")
        WebDriverWait(driver, WAIT_TIMEOUT).until(
            EC.visibility_of_element_located(SELECTORS["success_message"])
        )
        
        # Complete post-creation steps
        wait_and_click(driver, SELECTORS["ok_button"])
        
        _ok(flow_report, "success_verify")
        return True
    except TimeoutException:
        logger.error("Account creation verification timeout")
        _fail(flow_report, "success_verify", TimeoutException("success verification timeout"), driver)
        return False

def create_account(
    driver: WebDriver,
    username: str,
    password: str,
    first_name: str,
    last_name: str,
    country: str,
    month: str,
    day: str,
    year: str,
    hotmail: bool,
    flow_report=None,
    captcha_provider: str = "",
) -> Tuple[Optional[str], Optional[str]]:
    """
    Create a new Microsoft account (Outlook/Hotmail) with enhanced reliability
    
    Returns:
        Tuple: (email, password) or (None, None) on failure
    """
    try:
        logger.info('Starting Microsoft account creation process')
        _step(flow_report, "open_signup", url="https://signup.live.com/signup")
        driver.get('https://signup.live.com/signup')
        error_reason = _browser_error_reason(driver)
        if error_reason:
            current_url, title, _ = _driver_context(driver)
            screenshot = flow_report.capture_screenshot(driver, "outlook.open_signup_error") if flow_report else ""
            if flow_report:
                flow_report.keep_browser_open = False
                flow_report.block(
                    "outlook.open_signup",
                    f"browser_error_page: {error_reason}",
                    blocker="network",
                    evidence=error_reason,
                    current_url=current_url,
                    title=title,
                    screenshot=screenshot,
                )
            raise AccountCreationError(f"browser_error_page: {error_reason}")
        _ok(flow_report, "open_signup", current_url=getattr(driver, "current_url", ""))

        _step(flow_report, "fill_username", hotmail=hotmail)
        selected_username = fill_username_step(driver, username, hotmail, flow_report=flow_report)
        _ok(flow_report, "fill_username", selected=selected_username)

        next_state = fill_password_step(driver, password, flow_report=flow_report)
        if next_state == "details":
            next_state = fill_birthdate_step(driver, country, month, day, year, flow_report=flow_report)
            if next_state == "profile":
                next_state = fill_profile_step(driver, first_name, last_name, flow_report=flow_report)
        elif next_state == "profile":
            next_state = fill_profile_step(driver, first_name, last_name, flow_report=flow_report)
            if next_state == "details":
                next_state = fill_birthdate_step(driver, country, month, day, year, flow_report=flow_report)

        if next_state != "captcha":
            logger.warning(
                "[CREATE][WARN] provider=outlook step=pre_captcha expected=captcha observed_state=%s page_state=%s",
                next_state,
                _observed_state(driver),
            )

        # Captcha handling
        handle_captcha(driver, flow_report=flow_report, captcha_provider=captcha_provider)

        # Post-challenge pages vary; walk optional Microsoft prompts until a final state is reached.
        final_state = handle_post_challenge_state(
            driver,
            flow_report=flow_report,
            first_name=first_name,
            last_name=last_name,
            captcha_provider=captcha_provider,
        )
        logger.info("[OK] provider=outlook final_state=%s", final_state)

        # Log successful creation
        logger.info(f"{'Hotmail' if hotmail else 'Outlook'} account created successfully")
        logger.debug("Account details: %s@%s.com", selected_username, "hotmail" if hotmail else "outlook")
        
        return f"{selected_username}@{'hotmail' if hotmail else 'outlook'}.com", password

    except Exception as e:
        logger.error("Account creation failed: %s", str(e))
        _fail(flow_report, "create_account", e, driver)
        raise AccountCreationError("Microsoft account creation process failed") from e
    finally:
        if flow_report is not None and getattr(flow_report, "keep_browser_open", False):
            logger.warning("[NEXT] provider=outlook browser_kept_open reason=manual_takeover")
        else:
            driver.quit()
