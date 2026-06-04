import ninjemail
import pytest
import toml
from pathlib import Path
from unittest.mock import MagicMock, patch
from unittest import mock

from ..ninjemail_manager import Ninjemail, FreeProxyException
from ..challenge_detection import provider_supports_challenge
from ..email_providers import outlook
from ..flow_diagnostics import FlowRunReport
from ..provider_capabilities import REAL_SMS_SERVICES
from ..sms_services import get_sms_instance



def test_init_valid_browser():
  """Tests Ninjemail initialization with a valid browser."""
  manager = Ninjemail()
  assert manager.browser == "firefox"

def test_init_valid_browser_undetected_chrome():
  """Tests Ninjemail initialization with a valid browser."""
  manager = Ninjemail(browser="undetected-chrome")
  assert manager.browser == "undetected-chrome"

def test_init_invalid_browser():
  """Tests Ninjemail initialization with an invalid browser."""
  with pytest.raises(ValueError) as excinfo:
    Ninjemail(browser="invalid_browser")
  assert "Unsupported browser" in str(excinfo.value)


@patch('ninjemail_manager.FreeProxy.get')  # Patching FreeProxy.get for mocking
def test_get_proxy_with_provided_proxy(mocker):
  """Tests get_proxy with a user-provided proxy."""
  proxy = "http://myproxy:8080"
  manager = Ninjemail(proxies=[proxy])
  assert manager.get_proxy() == proxy
  mocker.assert_not_called()  # Assert FreeProxy.get wasn't called


@patch('ninjemail_manager.FreeProxy.get')
def test_get_proxy_rotates_stable_pool(mocker):
  manager = Ninjemail(proxies=["http://proxy-one:8080", "http://proxy-two:8080"])
  assert manager.get_proxy() == "http://proxy-one:8080"
  assert manager.get_proxy() == "http://proxy-two:8080"
  assert manager.get_proxy() == "http://proxy-one:8080"
  mocker.assert_not_called()


@patch('ninjemail_manager.FreeProxy.get')  # Patching FreeProxy.get for mocking
def test_get_proxy_with_auto_proxy_success(mocker):
  """Tests get_proxy with auto_proxy and successful free proxy retrieval."""
  manager = Ninjemail(auto_proxy=True)
  mock_proxy = {"http": "http://freeproxy:3128"}
  mocker.return_value = mock_proxy
  assert manager.get_proxy() == mock_proxy


@patch('ninjemail_manager.FreeProxy.get')  # Patching FreeProxy.get for mocking
def test_get_proxy_with_auto_proxy_failure(mocker):
  """Tests get_proxy with auto_proxy and free proxy retrieval failure."""
  manager = Ninjemail(auto_proxy=True)
  mocker.side_effect = FreeProxyException("No free proxies available")
  assert manager.get_proxy() is None


def test_get_captcha_key_valid_provider(mocker):
  """Tests get_captcha_key with a valid email provider and key."""
  mocker.patch.dict('ninjemail_manager.SUPPORTED_SOLVERS_BY_EMAIL', {'outlook': ['solver1']})
  manager = Ninjemail(captcha_keys={"solver1": "key"})
  assert manager.get_captcha_key('outlook') == {"name" : "solver1", "key": "key"}


def test_get_captcha_key_invalid_provider():
  """Tests get_captcha_key with an invalid email provider (won't pass)."""
  manager = Ninjemail()
  with pytest.raises(KeyError):  # Expecting KeyError here
    manager.get_captcha_key('invalid_provider')


def test_get_captcha_key_no_key_for_provider(mocker):
  """Tests get_captcha_key with a valid provider but no key."""
  mocker.patch.dict('ninjemail_manager.SUPPORTED_SOLVERS_BY_EMAIL', {'outlook': ['solver1']})
  manager = Ninjemail()
  with pytest.raises(ValueError) as excinfo:
    manager.get_captcha_key('outlook')
  assert "No captcha key provided for email provider: outlook" in str(excinfo.value)


def test_get_sms_key_with_keys(mocker):
  """Tests get_sms_key with multiple SMS keys provided."""
  manager = Ninjemail(sms_keys={"service1": "key1", "service2": "key2"})
  selected_service = manager.get_sms_key()
  assert selected_service["name"] in ["service1", "service2"]


def test_get_sms_key_no_keys():
  """Tests get_sms_key with no SMS keys provided."""
  manager = Ninjemail()
  with pytest.raises(ValueError) as excinfo:
    manager.get_sms_key()
  # Check both type and message
  assert isinstance(excinfo.value, ValueError)
  assert str(excinfo.value) == "No SMS API keys provided for SMS verification."


def test_default_sms_service_is_real_creation_provider():
  config_path = Path(__file__).resolve().parents[1] / "config.toml"
  config = toml.load(config_path)
  assert config["DEFAULT_SMS_SERVICE"] in REAL_SMS_SERVICES


def test_get_sms_instance_unknown_provider_raises_clear_error():
  with pytest.raises(ValueError) as excinfo:
    get_sms_instance({"name": "receive_sms_live", "data": {}}, "google")
  assert "Unsupported SMS provider for real creation" in str(excinfo.value)


def test_get_sms_instance_textbee_own_device_provider():
  provider = get_sms_instance(
    {
      "name": "textbee",
      "data": {
        "device_id": "device-demo",
        "token": "token-demo",
        "phone_number": "+15551234567",
        "base_url": "https://api.textbee.dev",
      },
    },
    "google",
  )
  assert provider.get_phone(send_prefix=True) == "15551234567"


def test_get_sms_instance_smsgate_own_device_provider():
  provider = get_sms_instance(
    {
      "name": "smsgate",
      "data": {
        "user": "user-demo",
        "token": "pass-demo",
        "phone_number": "+15557654321",
        "base_url": "http://192.168.1.23:8080",
      },
    },
    "google",
  )
  assert provider.get_phone(send_prefix=True) == "15557654321"


def test_flow_report_saves_json_and_markdown(tmp_path):
  report = FlowRunReport(mode="probe", provider="gmail", output_dir=tmp_path)
  report.start_step("config.provider_capability")
  report.block("config.provider_capability", "missing_sms_token", blocker="sms")
  json_path, md_path = report.save_all()
  assert json_path.exists()
  assert md_path.exists()
  assert "missing_sms_token" in md_path.read_text(encoding="utf-8")


def test_flow_report_closes_open_steps_with_root_cause(tmp_path):
  report = FlowRunReport(mode="visible_flow_probe", provider="outlook", output_dir=tmp_path)
  report.start_step("outlook.create_driver")
  report.block("outlook.challenge_detected", "unsupported_challenge: hsprotect", blocker="captcha")
  report.finish("blocked")
  assert report.root_cause["blocker"] == "captcha"
  assert all(step.status != "running" for step in report.steps)


def test_captcha_provider_capabilities_do_not_claim_hsprotect():
  assert provider_supports_challenge("nopecha", "hsprotect") is False
  assert provider_supports_challenge("capsolver", "hsprotect") is False
  assert provider_supports_challenge("nopecha", "funcaptcha") is True


@pytest.fixture(autouse=True)
def mock_create_account_methods(monkeypatch):
    def mock_outlook(*args, **kwargs):
        return "outlook_username", "outlook_password"

    def mock_gmail(*args, **kwargs):
        return "gmail_username", "gmail_password"

    def mock_yahoo(*args, **kwargs):
        return "yahoo_username", "yahoo_password"

    monkeypatch.setattr('email_providers.outlook.create_account', mock_outlook)
    monkeypatch.setattr('email_providers.gmail.create_account', mock_gmail)
    monkeypatch.setattr('email_providers.yahoo.create_account', mock_yahoo)

    def mock_gecko_install(*args, **kwargs):
        return 'gecko_driver_path'

    def mock_chrome_install(*args, **kwargs):
        return 'chrome_driver_path'

    def mock_firefox_service(*args, **kwargs):
        return None

    def mock_chrome_service(*args, **kwargs):
        return None

    def mock_firefox(*args, **kwargs):
        pass

    def mock_chrome(*args, **kwargs):
        pass

    def mock_firefox_quit(self):
        pass

    def mock_chrome_quit(self):
        pass

    monkeypatch.setattr('webdriver_manager.firefox.GeckoDriverManager.install', mock_gecko_install)
    monkeypatch.setattr('webdriver_manager.chrome.ChromeDriverManager.install', mock_chrome_install)
    monkeypatch.setattr('selenium.webdriver.firefox.service.Service.__init__', mock_firefox_service)
    monkeypatch.setattr('selenium.webdriver.chrome.service.Service.__init__', mock_chrome_service)
    monkeypatch.setattr('selenium.webdriver.Firefox.__init__', mock_firefox)
    monkeypatch.setattr('selenium.webdriver.Chrome.__init__', mock_chrome)
    monkeypatch.setattr('selenium.webdriver.Firefox.quit', mock_firefox_quit)
    monkeypatch.setattr('selenium.webdriver.Chrome.quit', mock_chrome_quit)

def test_create_outlook_account():

    manager = Ninjemail(browser='chrome', captcha_keys={'capsolver': 'token'})
    username, password = manager.create_outlook_account(
        username="testuser", 
        password="testpassword",
        first_name="Test",
        last_name="User",
        country="US",
        birthdate="01-01-2000"
    )

    assert username == "outlook_username"
    assert password == "outlook_password"

def test_create_outlook_account_no_info():

    manager = Ninjemail(browser='chrome', captcha_keys={'capsolver': 'token'})
    username, password = manager.create_outlook_account(
    )

    assert username == "outlook_username"
    assert password == "outlook_password"

def test_create_outlook_account_with_proxy():

    manager = Ninjemail(browser='chrome', captcha_keys={'capsolver': 'token'}, proxies=['http://127.0.0.1:8080'])
    username, password = manager.create_outlook_account(
    )

    assert username == "outlook_username"
    assert password == "outlook_password"

def test_create_outlook_account_no_captcha_key():

    manager = Ninjemail()
    with pytest.raises(ValueError) as excinfo:
        manager.create_outlook_account(
            username="testuser", 
            password="testpassword",
            first_name="Test",
            last_name="User",
            country="US",
            birthdate="01-01-2000"
        )
    assert isinstance(excinfo.value, ValueError)
    assert str(excinfo.value) == "No captcha key provided for email provider: outlook"

def test_create_gmail_account():

    manager = Ninjemail(sms_keys={'smspool': {'token': 'aaaaaaaa'}})
    username, password = manager.create_gmail_account(
        username="testuser", 
        password="testpassword",
        first_name="Test",
        last_name="User",
        birthdate="01-01-2000"
    )

    assert username == "gmail_username"
    assert password == "gmail_password"

def test_create_gmail_account_no_info():

    manager = Ninjemail(sms_keys={'smspool': {'token': 'aaaaaaaa'}})
    username, password = manager.create_gmail_account(
    )

    assert username == "gmail_username"
    assert password == "gmail_password"

def test_create_gmail_account_with_proxy():

    manager = Ninjemail(sms_keys={'smspool': {'token': 'aaaaaaaa'}}, proxies=['http://127.0.0.1:8080'])
    username, password = manager.create_gmail_account(
    )

    assert username == "gmail_username"
    assert password == "gmail_password"

def test_create_gmail_account_no_sms_key():

    manager = Ninjemail()
    with pytest.raises(ValueError) as excinfo:
        manager.create_gmail_account(
            username="testuser", 
            password="testpassword",
            first_name="Test",
            last_name="User",
            birthdate="01-01-2000"
        )
    assert isinstance(excinfo.value, ValueError)
    assert str(excinfo.value) == "No SMS API keys provided for SMS verification."
    
def test_create_yahoo_account():

    manager = Ninjemail(browser='chrome', captcha_keys={'capsolver': 'token'},
                        sms_keys={'smspool': {'token': 'bbbbbb'}})
    username, password = manager.create_yahoo_account(
        username="testuser", 
        password="testpassword",
        first_name="Test",
        last_name="User",
        birthdate="01-01-2000"
    )

    assert username == "yahoo_username"
    assert password == "yahoo_password"

def test_create_yahoo_account_no_info():

    manager = Ninjemail(browser='chrome', captcha_keys={'capsolver': 'token'},
                        sms_keys={'smspool': {'token': 'bbbbbb'}})
    username, password = manager.create_yahoo_account(
    )

    assert username == "yahoo_username"
    assert password == "yahoo_password"

def test_create_yahoo_account_with_proxy():

    manager = Ninjemail(browser='chrome', captcha_keys={'capsolver': 'token'},
                        sms_keys={'smspool': {'token': 'bbbbbb'}}, proxies=['http://127.0.0.1:8080'])
    username, password = manager.create_yahoo_account(
    )

    assert username == "yahoo_username"
    assert password == "yahoo_password"

def test_create_yahoo_account_no_captcha_key():

    manager = Ninjemail(sms_keys={'smspool': {'token': 'bbbbbb'}})
    with pytest.raises(ValueError) as excinfo:
        manager.create_yahoo_account(
            username="testuser", 
            password="testpassword",
            first_name="Test",
            last_name="User",
            birthdate="01-01-2000"
        )
    assert isinstance(excinfo.value, ValueError)
    assert str(excinfo.value) == "No captcha key provided for email provider: yahoo"

def test_create_yahoo_account_no_sms_key():

    manager = Ninjemail(browser='chrome', captcha_keys={'capsolver': 'token'})
    with pytest.raises(ValueError) as excinfo:
        manager.create_yahoo_account(
            username="testuser", 
            password="testpassword",
            first_name="Test",
            last_name="User",
            birthdate="01-01-2000"
        )
    assert isinstance(excinfo.value, ValueError)
    assert str(excinfo.value) == "No SMS API keys provided for SMS verification."
