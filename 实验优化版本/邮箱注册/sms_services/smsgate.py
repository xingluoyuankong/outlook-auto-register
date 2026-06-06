import logging
import re
import time
from typing import Any

import requests


class APIError(Exception):
    pass


class SMSGateSMS:
    """Receive verification codes through SMS Gateway for Android local server mode."""

    code_patt = re.compile(r"\b([0-9]{4,8})\b")

    def __init__(
        self,
        user,
        token,
        phone_number,
        base_url,
        device_id="",
        poll_seconds=180,
        poll_interval=5,
        **_,
    ):
        self.user = str(user or "").strip()
        self.token = str(token or "").strip()
        self.phone_number = str(phone_number or "").strip()
        self.base_url = str(base_url or "").strip().rstrip("/")
        self.device_id = str(device_id or "").strip()
        self.poll_seconds = int(poll_seconds or 180)
        self.poll_interval = int(poll_interval or 5)
        if not self.base_url:
            raise APIError("SMSGate base_url is required, for example http://192.168.1.23:8080")
        if not self.user or not self.token:
            raise APIError("SMSGate username and password/token are required")
        if not self.phone_number:
            raise APIError("SMSGate phone_number is required")

    def _auth(self):
        return (self.user, self.token)

    def _fetch_messages(self):
        params = {"type": "SMS", "limit": 50, "offset": 0}
        if self.device_id:
            params["deviceId"] = self.device_id
        response = requests.get(
            f"{self.base_url}/inbox",
            params=params,
            auth=self._auth(),
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, list) else []

    def _message_text(self, row: dict[str, Any]) -> str:
        for key in ("contentPreview", "content", "body", "text", "message"):
            value = row.get(key)
            if value:
                return str(value)
        return ""

    def get_phone(self, send_prefix=False):
        logging.info("[SMS] provider=smsgate status=using_own_device phone=set")
        phone = self.phone_number.lstrip("+")
        if send_prefix:
            return phone
        if phone.startswith("1") and len(phone) == 11:
            return phone[1:]
        return phone

    def get_code(self, _order_id_or_phone=None):
        logging.info("[SMS] provider=smsgate status=polling_inbox timeout_s=%s", self.poll_seconds)
        deadline = time.time() + self.poll_seconds
        last_error = ""
        seen_ids = set()
        while time.time() < deadline:
            try:
                for row in self._fetch_messages():
                    row_id = str(row.get("id") or row.get("createdAt") or self._message_text(row))
                    if row_id in seen_ids:
                        continue
                    seen_ids.add(row_id)
                    text = self._message_text(row)
                    match = self.code_patt.search(text)
                    if match:
                        logging.info("[SMS] provider=smsgate status=code_found")
                        return match.group(1)
            except Exception as exc:
                last_error = str(exc)
                logging.warning("[SMS][WAIT] provider=smsgate reason=%s", last_error)
            time.sleep(self.poll_interval)
        raise APIError(f"SMSGate verification code not found before timeout. last_error={last_error}")

