from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from .outlook_token_export import BUILTIN_CLIENT_ID, combo_line, normalize_email, safe_filename


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BROWSER_EXTENSION_ROOT = PROJECT_ROOT / "browser_extension"
DEFAULT_CREDENTIAL_DIR = BROWSER_EXTENSION_ROOT / "邮箱凭证"
AUXILIARY_MAIL_DIR = BROWSER_EXTENSION_ROOT / "辅助邮箱"

TOKEN_ENDPOINTS = [
    ("consumers-graph", "https://login.microsoftonline.com/consumers/oauth2/v2.0/token", "offline_access https://graph.microsoft.com/Mail.Read https://graph.microsoft.com/User.Read"),
    ("common-graph", "https://login.microsoftonline.com/common/oauth2/v2.0/token", "offline_access https://graph.microsoft.com/Mail.Read https://graph.microsoft.com/User.Read"),
    ("common-outlook", "https://login.microsoftonline.com/common/oauth2/v2.0/token", ""),
]


@dataclass
class MailCredential:
    email: str
    password: str
    client_id: str
    refresh_token: str
    source_path: str = ""


def ensure_credential_dirs() -> dict[str, str]:
    DEFAULT_CREDENTIAL_DIR.mkdir(parents=True, exist_ok=True)
    AUXILIARY_MAIL_DIR.mkdir(parents=True, exist_ok=True)
    return {
        "credential_dir": str(DEFAULT_CREDENTIAL_DIR),
        "auxiliary_dir": str(AUXILIARY_MAIL_DIR),
    }


def default_output_dir(path: str | None = None) -> Path:
    if path and str(path).strip():
        target = Path(path).expanduser()
    else:
        target = DEFAULT_CREDENTIAL_DIR
    target.mkdir(parents=True, exist_ok=True)
    return target


def strip_value(value: str) -> str:
    return str(value or "").strip().strip("\"'` \t\r\n")


def extract_email(value: str) -> str:
    match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", str(value or ""), re.I)
    return normalize_email(match.group(0)) if match else ""


def looks_like_client_id(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", strip_value(value)))


def looks_like_refresh_token(value: str) -> bool:
    text = strip_value(value)
    return len(text) >= 40 and bool(re.search(r"[._-]", text)) and not extract_email(text)


def parse_credential_text(text: str, source_path: str = "") -> MailCredential | None:
    source = str(text or "").strip()
    if not source:
        return None

    fields: dict[str, str] = {}
    key_map = {
        "email": "email",
        "邮箱": "email",
        "mail": "email",
        "account": "email",
        "password": "password",
        "密码": "password",
        "pwd": "password",
        "clientid": "client_id",
        "client_id": "client_id",
        "client id": "client_id",
        "refresh_token": "refresh_token",
        "refreshtoken": "refresh_token",
        "refresh token": "refresh_token",
        "token": "refresh_token",
    }
    for line in source.splitlines():
        match = re.match(r"\s*([^:=：]+)\s*[:=：]\s*(.+?)\s*$", line)
        if not match:
            continue
        key = re.sub(r"\s+", " ", match.group(1).strip().lower())
        mapped = key_map.get(key.replace("-", "_")) or key_map.get(key)
        if mapped:
            fields[mapped] = strip_value(match.group(2))

    if not fields:
        for delimiter in ("----", "|", ",", "\t"):
            if delimiter in source:
                parts = [strip_value(item) for item in source.splitlines()[0].split(delimiter)]
                break
        else:
            parts = [strip_value(item) for item in re.split(r"\s+", source) if strip_value(item)]

        email_index = next((idx for idx, item in enumerate(parts) if extract_email(item)), -1)
        if email_index >= 0:
            fields["email"] = extract_email(parts[email_index])
            remaining = [item for idx, item in enumerate(parts) if idx != email_index]
            client = next((item for item in remaining if looks_like_client_id(item)), "")
            refresh = next((item for item in remaining if looks_like_refresh_token(item)), "")
            password = next((item for item in remaining if item not in {client, refresh}), "")
            fields["password"] = password
            fields["client_id"] = client
            fields["refresh_token"] = refresh

    email = extract_email(fields.get("email", ""))
    client_id = strip_value(fields.get("client_id", "")) or BUILTIN_CLIENT_ID
    refresh_token = strip_value(fields.get("refresh_token", ""))
    if not email or not refresh_token:
        return None
    return MailCredential(
        email=email,
        password=strip_value(fields.get("password", "")),
        client_id=client_id,
        refresh_token=refresh_token,
        source_path=source_path,
    )


def read_credential_file(path: Path) -> MailCredential | None:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        text = path.read_text(encoding="gbk", errors="ignore")
    return parse_credential_text(text, str(path))


def credential_files(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(path for path in folder.glob("*.txt") if path.is_file())


def exchange_refresh_token(credential: MailCredential, timeout: int = 15) -> dict[str, Any]:
    last_error = ""
    for name, url, scope in TOKEN_ENDPOINTS:
        payload = {
            "client_id": credential.client_id,
            "grant_type": "refresh_token",
            "refresh_token": credential.refresh_token,
        }
        if scope:
            payload["scope"] = scope
        try:
            response = requests.post(url, data=payload, timeout=timeout)
            data = response.json() if response.content else {}
        except Exception as exc:
            last_error = str(exc)
            continue
        if response.ok and data.get("access_token"):
            return {
                "ok": True,
                "strategy": name,
                "access_token": data.get("access_token", ""),
                "refresh_token": data.get("refresh_token") or credential.refresh_token,
                "expires_in": data.get("expires_in", ""),
                "scope": data.get("scope", ""),
            }
        last_error = data.get("error_description") or data.get("error") or response.text[:300]
    return {"ok": False, "reason": last_error or "token_exchange_failed"}


def validate_credential(credential: MailCredential, update_file: bool = True) -> dict[str, Any]:
    token = exchange_refresh_token(credential)
    result = {
        "ok": bool(token.get("ok")),
        "email": credential.email,
        "client_id": credential.client_id,
        "source_path": credential.source_path,
        "strategy": token.get("strategy", ""),
        "reason": token.get("reason", ""),
        "has_refresh_token": bool(credential.refresh_token),
    }
    next_refresh = str(token.get("refresh_token") or "").strip()
    if token.get("ok") and next_refresh and next_refresh != credential.refresh_token and credential.source_path and update_file:
        path = Path(credential.source_path)
        path.write_text(combo_line(credential.email, credential.password, credential.client_id, next_refresh) + "\n", encoding="utf-8")
        result["updated_refresh_token"] = True
    return result


def validate_credentials(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    ensure_credential_dirs()
    folder = default_output_dir(str(payload.get("output_dir") or payload.get("outputDir") or "").strip() or None)
    text = str(payload.get("credential_text") or payload.get("credentialText") or "").strip()
    target_email = normalize_email(str(payload.get("email") or ""))
    credentials: list[MailCredential] = []
    if text:
        parsed = parse_credential_text(text, "<payload>")
        if parsed:
            credentials.append(parsed)
    else:
        for path in credential_files(folder):
            parsed = read_credential_file(path)
            if parsed and (not target_email or parsed.email == target_email):
                credentials.append(parsed)
    results = [validate_credential(item, update_file=item.source_path != "<payload>") for item in credentials]
    return {
        "ok": bool(results) and all(item.get("ok") for item in results),
        "credential_dir": str(folder),
        "checked": len(results),
        "valid": sum(1 for item in results if item.get("ok")),
        "failed": sum(1 for item in results if not item.get("ok")),
        "results": results,
        "reason": "" if results else "no_credentials_found",
    }


def fetch_messages(credential: MailCredential, top: int = 10) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    token = exchange_refresh_token(credential)
    if not token.get("ok"):
        return token, []
    headers = {"Authorization": f"Bearer {token['access_token']}", "Accept": "application/json"}
    url = "https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages"
    params = {
        "$top": max(1, min(int(top or 10), 30)),
        "$select": "id,subject,from,toRecipients,bodyPreview,body,receivedDateTime",
        "$orderby": "receivedDateTime desc",
    }
    response = requests.get(url, headers=headers, params=params, timeout=20)
    if not response.ok:
        return {"ok": False, "reason": response.text[:300]}, []
    data = response.json()
    return token, data.get("value") if isinstance(data.get("value"), list) else []


def extract_code(text: str) -> str:
    source = re.sub(r"<[^>]+>", " ", str(text or ""))
    patterns = [
        r"(?:验证码|驗證碼|代码|代碼|code)[^0-9]{0,120}(\d{4,8})",
        r"(\d{4,8})[^0-9]{0,120}(?:验证码|驗證碼|代码|代碼|code)",
        r"(?:security|verification|one[-\s]?time|login)[^0-9]{0,120}(\d{4,8})",
        r"\b(\d{6})\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, source, re.I)
        if match:
            return match.group(1)
    return ""


def message_text(message: dict[str, Any]) -> str:
    body = message.get("body") or {}
    sender = (((message.get("from") or {}).get("emailAddress") or {}).get("address") or "")
    return " ".join([
        str(message.get("subject") or ""),
        str(message.get("bodyPreview") or ""),
        str(body.get("content") or ""),
        str(sender),
    ])


def pick_auxiliary_mailbox(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    ensure_credential_dirs()
    folder = Path(str(payload.get("auxiliary_dir") or payload.get("auxiliaryDir") or AUXILIARY_MAIL_DIR)).expanduser()
    files = credential_files(folder)
    credentials = [item for item in (read_credential_file(path) for path in files) if item]
    if not credentials:
        return {"ok": False, "reason": "no_auxiliary_credentials", "auxiliary_dir": str(folder), "count": 0}
    seed = str(payload.get("seed") or time.time())
    rng = random.Random(seed)
    credential = rng.choice(credentials)
    return {
        "ok": True,
        "email": credential.email,
        "client_id": credential.client_id,
        "source_path": credential.source_path,
        "auxiliary_dir": str(folder),
        "count": len(credentials),
    }


def poll_auxiliary_code(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    ensure_credential_dirs()
    source_path = str(payload.get("source_path") or payload.get("sourcePath") or "").strip()
    target_email = normalize_email(str(payload.get("email") or ""))
    folder = Path(str(payload.get("auxiliary_dir") or payload.get("auxiliaryDir") or AUXILIARY_MAIL_DIR)).expanduser()
    candidates = []
    if source_path:
        parsed = read_credential_file(Path(source_path))
        if parsed:
            candidates.append(parsed)
    else:
        for path in credential_files(folder):
            parsed = read_credential_file(path)
            if parsed and (not target_email or parsed.email == target_email):
                candidates.append(parsed)
    if not candidates:
        return {"ok": False, "reason": "auxiliary_credential_not_found", "auxiliary_dir": str(folder)}
    credential = candidates[0]
    deadline = time.time() + max(5, min(int(payload.get("timeout_seconds") or payload.get("timeoutSeconds") or 60), 180))
    interval = max(2, min(int(payload.get("interval_seconds") or payload.get("intervalSeconds") or 5), 30))
    last_reason = ""
    while time.time() < deadline:
        token, messages = fetch_messages(credential, top=10)
        if not token.get("ok"):
            last_reason = token.get("reason") or "fetch_failed"
        for message in messages:
            code = extract_code(message_text(message))
            if code:
                return {
                    "ok": True,
                    "email": credential.email,
                    "code": code,
                    "source_path": credential.source_path,
                    "subject": message.get("subject") or "",
                    "receivedDateTime": message.get("receivedDateTime") or "",
                }
        last_reason = "code_not_found"
        time.sleep(interval)
    return {"ok": False, "email": credential.email, "reason": last_reason or "timeout", "source_path": credential.source_path}
