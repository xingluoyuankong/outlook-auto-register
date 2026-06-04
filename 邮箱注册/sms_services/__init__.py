from sms_services import getsmscode
from sms_services import smspool
from sms_services import fivesim
from sms_services import textbee
from sms_services import smsgate

def get_sms_instance(sms_info, email_provider):
    """
    Retrieves an instance of an SMS provider based on the given SMS information.

    Args:
        sms_info (dict): A dictionary containing the SMS service name and associated data.

    Returns:
        object: An instance of the SMS provider based on the provided SMS service.
    """
    service_name = sms_info['name']
    sms_provider = None

    if service_name == 'getsmscode':
        data = sms_info['data']
        project = 1
        if email_provider == 'yahoo':
            project = 15
        data.update({'project': project, 'country': 'us'})
        sms_provider = getsmscode.GetsmsCode(**data)
    elif service_name == 'smspool':
        data = sms_info['data']
        service = 395
        if email_provider == 'yahoo':
            service = 1034
        data.update({'service': service})
        sms_provider = smspool.SMSPool(**data)
    elif service_name == '5sim':
        data = sms_info['data']
        data.update({'service': email_provider})
        sms_provider = fivesim.FiveSim(**data)
    elif service_name == 'textbee':
        data = sms_info['data']
        sms_provider = textbee.TextBeeSMS(**data)
    elif service_name == 'smsgate':
        data = sms_info['data']
        sms_provider = smsgate.SMSGateSMS(**data)

    if sms_provider is None:
        supported = "getsmscode, smspool, 5sim, textbee, smsgate"
        raise ValueError(
            f"Unsupported SMS provider for real creation: {service_name}. "
            f"Supported providers: {supported}"
        )

    return sms_provider
