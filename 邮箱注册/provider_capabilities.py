"""Provider capability groups used by diagnostics and real creation flows."""

REAL_CAPTCHA_SERVICES = ("capsolver", "nopecha")

DIAGNOSTIC_CAPTCHA_SERVICES = (
    "nopecha",
    "ddddocr",
    "ocr_space",
    "capsolver",
    "capmonster",
    "anti_captcha",
    "2captcha",
    "yescaptcha",
    "buster",
    "local_solver",
)

REAL_SMS_SERVICES = ("getsmscode", "smspool", "5sim", "textbee", "smsgate", "vendel")

DIAGNOSTIC_SMS_SERVICES = (
    "receive_sms_live",
    "quackr",
    "anonymsms",
    "sms24_me",
    "receive_sms_cc",
    "sms_receive_free",
    "numtapper",
    "receivesms_it",
    "temporary_phone_number_io",
    "freephonenum",
    "receive_sms_online_info",
    "sms_online_co",
    "mytrashmobile",
    "receive_sms_io",
    "receive_sms_free_cc",
    "temporary_phone_number_com",
    "receivefreesms_net",
    "freeonlinephone_org",
    "receivesms_net",
    "receivesmsonline_net",
    "sms24_info",
    *REAL_SMS_SERVICES,
)


def is_real_captcha_provider(provider: str) -> bool:
    return str(provider or "").lower() in REAL_CAPTCHA_SERVICES


def is_real_sms_provider(provider: str) -> bool:
    return str(provider or "").lower() in REAL_SMS_SERVICES
