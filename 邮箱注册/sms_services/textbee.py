import logging
import re
import time
from typing import Any

import requests


class APIError(Exception):
    pass


class TextBeeSMS:
    """Receive verification codes through a user-owned Android device."""

    code_patt = re.compile(r"\b([0-9]{4,8})\b")

    def __init__(
        self,
        device_id,
        token,
        phone_number,
        base_url="https://api.textbee.dev",
        poll_seconds=180,
        poll_interval=5,
        **_,
    ):
        self.device_id = str(device_id or "").strip()
        self.token = str(token or "").strip()
        self.phone_number = str(phone_number or "").strip()
        self.base_url = str(base_url or "https://api.textbee.dev").rstrip("/")
        self.poll_seconds = int(poll_seconds or 180)
        self.poll_interval = int(poll_interval or 5)
        if not self.device_id:
            raise APIError("TextBee device_id is required")
        if not self.token:
            raise APIError("TextBee API key is required")
        if not self.phone_number:
            raise APIError("TextBee phone_number is required")

    def _headers(self):
        return {"x-api-key": self.token, "Accept": "application/json"}

    def _received_sms_url(self):
        return f"{self.base_url}/api/v1/gateway/devices/{self.device_id}/get-received-sms"

    def _fetch_messages(self):
        response = requests.get(self._received_sms_url(), headers=self._headers(), timeout=20)
        response.raise_for_status()
        payload = response.json()
        return self._extract_message_rows(payload)

    def _extract_message_rows(self, payload: Any):
        rows = []
        if isinstance(payload, list):
            source = payload
        elif isinstance(payload, dict):
            source = (
                payload.get("messages")
                or payload.get("data")
                or payload.get("receivedSms")
                or payload.get("received_sms")
                or payload.get("items")
                or []
            )
            if isinstance(source, dict):
                source = source.get("messages") or source.get("items") or []
        else:
            source = []
        if not isinstance(source, list):
            source = [source]
        for item in source:
            if isinstance(item, str):
                rows.append({"message": item})
            elif isinstance(item, dict):
                rows.append(item)
        return rows

    def _message_text(self, row):
        for key in ("message", "body", "text", "content", "sms", "messageBody"):
            value = row.get(key)
            if value:
                return str(value)
        return ""

    def get_phone(self, send_prefix=False):
        logging.info("[SMS] provider=textbee status=using_own_device phone=set")
        phone = self.phone_number.lstrip("+")
        if send_prefix:
            return phone
        if phone.startswith("1") and len(phone) == 11:
            return phone[1:]
        return phone

    def get_code(self, _order_id_or_phone=None):
        logging.info("[SMS] provider=textbee status=polling_received_sms timeout_s=%s", self.poll_seconds)
        deadline = time.time() + self.poll_seconds
        last_error = ""
        seen_texts = set()
        while time.time() < deadline:
            try:
                rows = self._fetch_messages()
                for row in rows:
                    text = self._message_text(row)
                    if not text or text in seen_texts:
                        continue
                    seen_texts.add(text)
                    match = self.code_patt.search(text)
                    if match:
                        code = match.group(1)
                        logging.info("[SMS] provider=textbee status=code_found")
                        return code
            except Exception as exc:
                last_error = str(exc)
                logging.warning("[SMS][WAIT] provider=textbee reason=%s", last_error)
            time.sleep(self.poll_interval)
        raise APIError(f"TextBee verification code not found before timeout. last_error={last_error}")

