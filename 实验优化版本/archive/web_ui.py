#!/usr/bin/env python3
"""
Ninjemail Web UI - Gradio界面
用于创建邮箱账户的Web控制面板
"""

import gradio as gr
from ninjemail import Ninjemail
from ninjemail.browser_extension import DEFAULT_NINJEMAIL_EXTENSION_PATH, check_ninjemail_extension
from ninjemail.outlook_token_export import (
    BUILTIN_CLIENT_ID,
    credential_file_for,
    locate_credential_file,
    matching_credential_files,
    safe_filename,
    save_created_outlook_account,
)
from ninjemail.credential_tools import (
    DEFAULT_CREDENTIAL_DIR,
    AUXILIARY_MAIL_DIR,
    ensure_credential_dirs,
    pick_auxiliary_mailbox,
    poll_auxiliary_code,
    validate_credentials,
)
import json
import logging
import os
import threading
import time
import urllib.error
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from ninjemail.service_adapters import (
    auto_configure_free_services,
    build_stable_proxy_pool,
    check_captcha_service,
    check_proxy_list,
    check_sms_service,
    fetch_free_proxies,
    fetch_public_sms_messages,
    list_public_sms_numbers,
    load_runtime_config,
    probe_network_routes,
    render_proxy_list,
    save_runtime_config,
)
from ninjemail.flow_diagnostics import FlowRunReport
from ninjemail.provider_capabilities import (
    DIAGNOSTIC_CAPTCHA_SERVICES,
    DIAGNOSTIC_SMS_SERVICES,
    REAL_CAPTCHA_SERVICES,
    REAL_SMS_SERVICES,
    is_real_captcha_provider,
    is_real_sms_provider,
)
from ninjemail.utils.webdriver_utils import create_driver

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def _normalize_proxy(proxy: str | None) -> str:
    proxy = (proxy or "").strip()
    if not proxy:
        return ""
    if "://" not in proxy:
        proxy = "http://" + proxy
    return proxy


def _proxy_map_from_server(proxy_server: str | None) -> dict[str, str]:
    proxy_server = (proxy_server or "").strip()
    if not proxy_server:
        return {}
    if "=" not in proxy_server:
        proxy = _normalize_proxy(proxy_server)
        return {"http": proxy, "https": proxy}

    result: dict[str, str] = {}
    for item in proxy_server.split(";"):
        if "=" not in item:
            continue
        scheme, value = item.split("=", 1)
        scheme = scheme.strip().lower()
        if scheme in ("http", "https"):
            result[scheme] = _normalize_proxy(value)
    return result


def _windows_proxy_map() -> dict[str, str]:
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
        ) as key:
            proxy_enable = winreg.QueryValueEx(key, "ProxyEnable")[0]
            proxy_server = winreg.QueryValueEx(key, "ProxyServer")[0]
    except Exception:
        return {}
    if not proxy_enable:
        return {}
    return _proxy_map_from_server(proxy_server)


def _discover_proxy_routes() -> list[tuple[str, dict[str, str]]]:
    routes: list[tuple[str, dict[str, str]]] = [("direct", {})]
    seen = {tuple()}

    env_proxies = urllib.request.getproxies()
    if env_proxies:
        key = tuple(sorted(env_proxies.items()))
        if key not in seen:
            routes.append((f"env_proxy:{env_proxies}", env_proxies))
            seen.add(key)

    win_proxies = _windows_proxy_map()
    if win_proxies:
        key = tuple(sorted(win_proxies.items()))
        if key not in seen:
            routes.append((f"windows_proxy:{win_proxies}", win_proxies))
            seen.add(key)
    return routes


def _post_form_with_proxy_routes(url: str, form: dict[str, str], timeout: int = 30) -> tuple[dict[str, Any], str]:
    data = urllib.parse.urlencode(form).encode("utf-8")
    failures: list[str] = []
    for route_name, proxies in _discover_proxy_routes():
        request = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        opener = urllib.request.build_opener(urllib.request.ProxyHandler(proxies))
        try:
            with opener.open(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8")), route_name
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                payload = {"error": "http_error", "error_description": body}
            reason = str(payload.get("error_description") or payload.get("error") or f"token_http_{exc.code}")
            raise RuntimeError(f"{reason} | route={route_name}") from exc
        except Exception as exc:
            failures.append(f"{route_name}: {exc}")
    raise RuntimeError("all_token_routes_failed: " + " | ".join(failures))

# 前端日志缓冲区
WEB_LOG_LIMIT = 500
WEB_LOG_LOCK = threading.Lock()
WEB_LOG_LINES: list[str] = []
ROOT_CAUSE_LOCK = threading.Lock()
LAST_ROOT_CAUSE: dict[str, Any] = {}


class WebLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        if record.name not in {"root", __name__} and not record.name.startswith("ninjemail") and record.levelno < logging.WARNING:
            return
        try:
            message = self.format(record)
            with WEB_LOG_LOCK:
                WEB_LOG_LINES.append(message)
                if len(WEB_LOG_LINES) > WEB_LOG_LIMIT:
                    del WEB_LOG_LINES[:-WEB_LOG_LIMIT]
        except Exception:
            self.handleError(record)


def attach_web_log_handler() -> None:
    root_logger = logging.getLogger()
    if any(isinstance(handler, WebLogHandler) for handler in root_logger.handlers):
        return
    handler = WebLogHandler()
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(message)s"))
    root_logger.addHandler(handler)
    if root_logger.level > logging.INFO:
        root_logger.setLevel(logging.INFO)


def get_web_log_text() -> str:
    with WEB_LOG_LOCK:
        return "\n".join(WEB_LOG_LINES)


def clear_web_logs() -> str:
    with WEB_LOG_LOCK:
        WEB_LOG_LINES.clear()
    logger.info("[STEP] logs_cleared")
    return get_web_log_text()


def clear_root_cause_and_logs() -> tuple[str, str]:
    with ROOT_CAUSE_LOCK:
        LAST_ROOT_CAUSE.clear()
    return get_root_cause_text(), clear_web_logs()


def set_root_cause_from_report(report: FlowRunReport) -> None:
    with ROOT_CAUSE_LOCK:
        LAST_ROOT_CAUSE.clear()
        if report.root_cause:
            LAST_ROOT_CAUSE.update(report.root_cause)
        else:
            LAST_ROOT_CAUSE.update(
                {
                    "blocker": "",
                    "reason": f"{report.provider}.{report.mode} status={report.status}",
                    "evidence": "no blocker recorded",
                    "next_action": "Run visible_flow_probe when you need to see the next live page blocker.",
                    "latest_screenshot": "",
                }
            )


def get_root_cause_text() -> str:
    live_cause = None
    try:
        report = getattr(ninja, "flow_report", None) if ninja else None
        if report and getattr(report, "root_cause", None):
            live_cause = report.root_cause
    except Exception:
        live_cause = None
    with ROOT_CAUSE_LOCK:
        cause = live_cause or LAST_ROOT_CAUSE
        if not cause:
            return "当前根因: 暂无。先运行 page_check / visible_flow_probe / real_run。"
        details = cause.get("details") or {}
        extra_lines = []
        for key in ("post_challenge_state", "manual_wait_seconds", "remaining_seconds", "last_url", "last_title"):
            if key in details and details.get(key) not in ("", None):
                extra_lines.append(f"{key}: {details.get(key)}")
        return (
            f"root_cause: {cause.get('reason') or '<none>'}\n"
            f"blocker: {cause.get('blocker') or '<none>'}\n"
            f"evidence: {cause.get('evidence') or '<none>'}\n"
            f"next_action: {cause.get('next_action') or '<none>'}\n"
            f"latest_screenshot: {cause.get('latest_screenshot') or '<none>'}"
            + (("\n" + "\n".join(extra_lines)) if extra_lines else "")
        )


def get_root_cause_and_logs() -> tuple[str, str]:
    return get_root_cause_text(), get_web_log_text()


def save_outlook_account_from_extension(payload: dict[str, Any]) -> dict[str, Any]:
    email = str(payload.get("email") or payload.get("account", {}).get("email") or "").strip()
    password = str(payload.get("password") or payload.get("account", {}).get("password") or "").strip()
    if not email or not password:
        return {"ok": False, "reason": "missing_email_or_password"}

    client_id = str(payload.get("client_id") or payload.get("clientId") or BUILTIN_CLIENT_ID).strip() or BUILTIN_CLIENT_ID
    access_token = str(payload.get("access_token") or payload.get("accessToken") or "").strip()
    refresh_token = str(payload.get("refresh_token") or payload.get("refreshToken") or "").strip()
    expires_in = payload.get("expires_in") or payload.get("expiresIn") or ""
    token_type = str(payload.get("token_type") or payload.get("tokenType") or "").strip()
    scope = str(payload.get("scope") or "").strip()
    start_token_export = False
    ensure_credential_dirs()
    output_dir = str(payload.get("output_dir") or payload.get("outputDir") or "").strip() or str(DEFAULT_CREDENTIAL_DIR)
    result = save_created_outlook_account(
        email,
        password,
        client_id=client_id,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        token_type=token_type,
        scope=scope,
        out_dir=output_dir,
        source=str(payload.get("source") or "browser_extension"),
        final_state=str(payload.get("final_state") or payload.get("finalState") or ""),
        url=str(payload.get("url") or ""),
        start_token_job=start_token_export,
    )
    if refresh_token:
        result["ok"] = True
        result["reason"] = "ok"
        result["credential_path"] = result.get("credential_path") or str(credential_file_for(email, output_dir))
        result["combo_path"] = result.get("combo_path") or result["credential_path"]
        result["has_refresh_token"] = True
    token_job = result.get("token_job") or {}
    logger.info(
        "[OK] outlook_account_saved email=%s credential=%s token_job=%s",
        email,
        result.get("credential_path") or result.get("combo_path") or "<none>",
        token_job.get("status") or "not_requested",
    )
    if output_dir:
        logger.info("[STEP] credential_output_dir path=%s", output_dir)
    if token_job.get("log_path"):
        logger.info("[STEP] outlook_token_export_log path=%s", token_job.get("log_path"))
    if result.get("credential_path"):
        logger.info("[OK] outlook_credential_path path=%s", result.get("credential_path"))
    return result


def exchange_outlook_oauth_code_from_extension(payload: dict[str, Any]) -> dict[str, Any]:
    code = str(payload.get("code") or "").strip()
    code_verifier = str(payload.get("code_verifier") or payload.get("codeVerifier") or "").strip()
    client_id = str(payload.get("client_id") or payload.get("clientId") or BUILTIN_CLIENT_ID).strip() or BUILTIN_CLIENT_ID
    redirect_uri = str(payload.get("redirect_uri") or payload.get("redirectUri") or "http://localhost:8765").strip() or "http://localhost:8765"
    scope = str(payload.get("scope") or "offline_access openid profile https://graph.microsoft.com/User.Read https://graph.microsoft.com/Mail.Read").strip()
    tenant = str(payload.get("tenant") or "consumers").strip() or "consumers"
    email = str(payload.get("email") or "").strip().lower()
    if not code or not code_verifier:
        return {"ok": False, "reason": "missing_code_or_code_verifier"}

    token_url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
    try:
        data, route_name = _post_form_with_proxy_routes(
            token_url,
            {
                "client_id": client_id,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "scope": scope,
                "code_verifier": code_verifier,
            },
            timeout=30,
        )
        logger.info(
            "[OK] oauth_code_exchange_via_web_ui email=%s route=%s has_refresh=%s",
            email or "<unknown>",
            route_name,
            bool(data.get("refresh_token")),
        )
        return {
            "ok": True,
            "access_token": str(data.get("access_token") or ""),
            "refresh_token": str(data.get("refresh_token") or ""),
            "expires_in": data.get("expires_in") or "",
            "token_type": str(data.get("token_type") or ""),
            "scope": str(data.get("scope") or ""),
            "id_token": str(data.get("id_token") or ""),
            "route": route_name,
            "reason": "ok",
        }
    except Exception as exc:
        reason = str(exc)
        logger.warning(
            "[BLOCK] oauth_code_exchange_via_web_ui_failed email=%s reason=%s",
            email or "<unknown>",
            reason,
        )
        return {"ok": False, "reason": reason}


def save_outlook_account_candidate_from_extension(payload: dict[str, Any]) -> dict[str, Any]:
    email = str(payload.get("email") or payload.get("account", {}).get("email") or "").strip().lower()
    password = str(payload.get("password") or payload.get("account", {}).get("password") or "").strip()
    if not email or not password:
        return {"ok": False, "reason": "missing_email_or_password"}
    logger.info("[STEP] outlook_account_candidate_ignored email=%s reason=single_credential_file_only", email)
    return {
        "ok": True,
        "reason": "single_credential_file_only",
        "email": email,
        "client_id": str(payload.get("client_id") or payload.get("clientId") or BUILTIN_CLIENT_ID),
    }


def export_three_credentials_from_extension(payload: dict[str, Any]) -> dict[str, Any]:
    email = str(payload.get("email") or payload.get("account", {}).get("email") or "").strip().lower()
    password = str(payload.get("password") or payload.get("account", {}).get("password") or "").strip()
    client_id = str(payload.get("client_id") or payload.get("clientId") or BUILTIN_CLIENT_ID).strip() or BUILTIN_CLIENT_ID
    if not email or not password:
        return {"ok": False, "reason": "missing_email_or_password"}
    ensure_credential_dirs()
    output_dir = str(payload.get("output_dir") or payload.get("outputDir") or "").strip() or str(DEFAULT_CREDENTIAL_DIR)
    target_dir = Path(output_dir).expanduser()
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{safe_filename(email)}.triple.txt"
    target_path.write_text(f"{email}----{password}----{client_id}\n", encoding="utf-8")
    logger.info("[OK] outlook_three_credentials_exported email=%s path=%s", email, target_path)
    return {
        "ok": True,
        "email": email,
        "client_id": client_id,
        "credential_path": str(target_path),
        "three_credential_path": str(target_path),
        "reason": "ok",
    }


def open_credential_output_dir_from_extension(payload: dict[str, Any]) -> dict[str, Any]:
    credential_path = str(payload.get("credential_path") or payload.get("credentialPath") or "").strip()
    output_dir = str(payload.get("output_dir") or payload.get("outputDir") or "").strip()
    target = Path(credential_path).expanduser() if credential_path else Path(output_dir).expanduser()
    if target.is_file():
      target = target.parent
    if not target.exists():
      target.mkdir(parents=True, exist_ok=True)
    try:
      os.startfile(str(target))
    except Exception as exc:
      return {"ok": False, "reason": str(exc), "output_dir": str(target)}
    logger.info("[OK] credential_output_dir_opened path=%s", target)
    return {"ok": True, "output_dir": str(target), "reason": "ok"}


def clear_previous_outlook_credentials_from_extension(payload: dict[str, Any]) -> dict[str, Any]:
    raw_emails = payload.get("emails") or payload.get("email") or []
    if isinstance(raw_emails, str):
        emails = [raw_emails]
    else:
        emails = list(raw_emails or [])
    emails = sorted({str(email or "").strip().lower() for email in emails if str(email or "").strip()})
    ensure_credential_dirs()
    output_dir = str(payload.get("output_dir") or payload.get("outputDir") or "").strip()
    target_dir = Path(output_dir).expanduser() if output_dir else DEFAULT_CREDENTIAL_DIR
    delete_saved = bool(payload.get("delete_saved") or payload.get("deleteSaved"))
    deleted: list[str] = []

    def unlink(path: Path) -> None:
        try:
            if path.is_file():
                path.unlink()
                deleted.append(str(path))
        except Exception as exc:
            logger.warning("[WARN] credential_cleanup_failed path=%s reason=%s", path, exc)

    target_dir.mkdir(parents=True, exist_ok=True)
    if not delete_saved:
        logger.info("[STEP] outlook_previous_credentials_preserved emails=%s reason=%s", ",".join(emails), payload.get("reason") or "")
        return {"ok": True, "emails": emails, "deleted_paths": [], "preserved": True}

    for email in emails:
        for credential_path in matching_credential_files(email, target_dir):
            unlink(credential_path)
        safe = safe_filename(email)
        for name in [
            f"tokens_{safe}.json",
            f"tokens_{safe}.env",
            f"tokens_{safe}_combo.txt",
        ]:
            unlink(target_dir / name)
        for log_path in target_dir.glob(f"outlook_token_export_{safe}_*.log"):
            unlink(log_path)

    for legacy_name in [
        "outlook_accounts_combo.txt",
        "outlook_accounts_events.jsonl",
        "outlook_account_candidates.jsonl",
    ]:
        unlink(target_dir / legacy_name)

    logger.info("[STEP] outlook_previous_credentials_cleared emails=%s deleted=%s", ",".join(emails), len(deleted))
    return {"ok": True, "emails": emails, "deleted_paths": deleted}


def check_outlook_credential_from_extension(payload: dict[str, Any]) -> dict[str, Any]:
    email = str(payload.get("email") or "").strip().lower()
    ensure_credential_dirs()
    output_dir = str(payload.get("output_dir") or payload.get("outputDir") or "").strip() or str(DEFAULT_CREDENTIAL_DIR)
    if not email or "@" not in email:
        return {"ok": False, "reason": "missing_email"}
    path = locate_credential_file(email, output_dir)
    if not path or not path.is_file():
        return {
            "ok": True,
            "email": email,
            "exists": False,
            "has_refresh_token": False,
            "credential_path": str(credential_file_for(email, output_dir)),
        }
    line = path.read_text(encoding="utf-8").splitlines()[0].strip()
    parts = line.split("----")
    refresh_token = parts[3].strip() if len(parts) >= 4 else ""
    return {
        "ok": True,
        "email": email,
        "exists": True,
        "has_refresh_token": bool(refresh_token),
        "credential_path": str(path),
        "combo": line,
        "refresh_token": refresh_token,
    }


def validate_outlook_credentials_from_extension(payload: dict[str, Any]) -> dict[str, Any]:
    result = validate_credentials(payload or {})
    logger.info(
        "[STEP] credential_validation checked=%s valid=%s failed=%s dir=%s",
        result.get("checked"),
        result.get("valid"),
        result.get("failed"),
        result.get("credential_dir"),
    )
    return result


def auxiliary_mailbox_pick_from_extension(payload: dict[str, Any]) -> dict[str, Any]:
    ensure_credential_dirs()
    result = pick_auxiliary_mailbox(payload or {})
    logger.info(
        "[STEP] auxiliary_mailbox_pick ok=%s email=%s dir=%s count=%s",
        result.get("ok"),
        result.get("email") or "",
        result.get("auxiliary_dir") or str(AUXILIARY_MAIL_DIR),
        result.get("count") or 0,
    )
    return result


def auxiliary_mailbox_code_from_extension(payload: dict[str, Any]) -> dict[str, Any]:
    ensure_credential_dirs()
    result = poll_auxiliary_code(payload or {})
    logger.info(
        "[STEP] auxiliary_mailbox_code ok=%s email=%s code=%s reason=%s",
        result.get("ok"),
        result.get("email") or "",
        result.get("code") or "",
        result.get("reason") or "",
    )
    return result


FREE_SMS_BASE_URLS = {
    "receive_sms_live": "https://receive-smss.live",
    "quackr": "https://quackr.io",
    "anonymsms": "https://anonymsms.com",
    "sms24_me": "https://sms24.me",
    "receive_sms_cc": "https://receive-sms.cc",
    "sms_receive_free": "https://www.free-sms-receive.com",
    "numtapper": "https://www.numtapper.com",
    "receivesms_it": "https://receivesms.it.com",
    "temporary_phone_number_io": "https://temporary-phone-number.io",
    "freephonenum": "https://freephonenum.com",
    "receive_sms_online_info": "https://receive-sms-online.info",
    "sms_online_co": "https://sms-online.co",
    "mytrashmobile": "https://www.mytrashmobile.com",
    "receive_sms_io": "https://receive-sms.io",
    "receive_sms_free_cc": "https://receive-sms-free.cc",
    "temporary_phone_number_com": "https://temporary-phone-number.com",
    "receivefreesms_net": "https://receivefreesms.net",
    "freeonlinephone_org": "https://www.freeonlinephone.org",
    "receivesms_net": "https://www.receivesms.net",
    "receivesmsonline_net": "https://www.receivesmsonline.net",
    "sms24_info": "https://sms24.info",
}


def _free_temp_sms_providers() -> list[str]:
    return [provider for provider in FREE_SMS_BASE_URLS if not is_real_sms_provider(provider)]


def _sms_diag_item(row: dict[str, Any]) -> dict[str, Any]:
    provider = str(row.get("provider") or "").strip()
    details = row.get("details") or {}
    url = str(details.get("url") or details.get("base_url") or FREE_SMS_BASE_URLS.get(provider, "") or "")
    return {
        "provider": provider,
        "ok": bool(row.get("ok")),
        "status": str(row.get("status") or ("ok" if row.get("ok") else "not_checked")),
        "reason": str(row.get("reason") or ""),
        "url": url,
        "route": str(details.get("route") or details.get("message_page_route") or ""),
        "latency_ms": details.get("route_latency_ms") or details.get("latency_ms") or details.get("message_page_latency_ms") or row.get("duration_ms") or "",
        "numbers": details.get("numbers") or details.get("phone_count") or details.get("count") or "",
        "requires_key": is_real_sms_provider(provider),
        "category": "real_sms" if is_real_sms_provider(provider) else "free_temp_sms",
    }


def proxy_load_for_extension(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """从 runtime_config.toml 加载当前代理列表，返回给浏览器插件。"""
    payload = payload or {}
    try:
        config = load_runtime_config()
        proxy = config.get("proxy", {}) or {}
        items = _creation_proxy_items(proxy)
        all_items = proxy.get("all_items") or proxy.get("items") or []
        stable_items = proxy.get("stable_items") or []
        return {
            "ok": True,
            "proxies": items,
            "proxy_text": "\n".join(items),
            "count": len(items),
            "all_count": len(all_items),
            "stable_count": len(stable_items),
            "auto_proxy": bool(config.get("auto_proxy", False)),
        }
    except Exception as exc:
        logger.warning("[PROXY] 加载代理配置失败: %s", exc)
        return {"ok": False, "reason": str(exc), "proxies": [], "proxy_text": "", "count": 0}


def proxy_save_for_extension(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """接收浏览器插件发送的代理列表，检测后保存到 runtime_config.toml。"""
    payload = payload or {}
    proxy_text = str(payload.get("proxy_text") or "").strip()
    if not proxy_text:
        return {"ok": False, "reason": "代理列表为空", "count": 0}

    lines = [line.strip() for line in proxy_text.splitlines() if line.strip()]
    if not lines:
        return {"ok": False, "reason": "代理列表为空", "count": 0}

    logger.info("[PROXY] 浏览器插件提交 %d 个代理，开始检测", len(lines))

    # 检测代理
    proxies, check_lines = check_proxy_list(proxy_text, max_checks=min(len(lines), 40), max_working=20)
    _safe_lines(check_lines)

    if not proxies:
        return {"ok": False, "reason": f"❌ {len(lines)} 个代理全部检测失败，未保存", "count": 0}

    proxy_dicts = [p.to_dict() for p in proxies]
    checked_text = render_proxy_list(proxies)
    checked_items = [line.strip() for line in checked_text.splitlines() if line.strip()]

    # 读取现有配置并更新代理部分
    try:
        config = load_runtime_config()
    except Exception:
        config = {}

    proxy_section = config.get("proxy", {}) or {}
    proxy_section["items"] = checked_items
    proxy_section["stable_items"] = checked_items
    proxy_section["all_items"] = lines
    proxy_section["pool"] = proxy_dicts
    proxy_section["working"] = proxy_dicts
    config["proxy"] = proxy_section

    try:
        save_runtime_config(config)
        logger.info("[PROXY] 已保存 %d 个可用代理到 runtime_config.toml", len(proxies))
        return {
            "ok": True,
            "reason": f"✅ {len(proxies)}/{len(lines)} 个代理通过检测，已保存",
            "count": len(proxies),
            "total_input": len(lines),
            "proxy_text": checked_text,
            "proxies": checked_items,
        }
    except Exception as exc:
        logger.warning("[PROXY] 保存代理配置失败: %s", exc)
        return {"ok": False, "reason": f"保存失败: {exc}", "count": 0}


def proxy_check_for_extension(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """检测浏览器插件传入的代理列表，返回检测结果（不保存）。"""
    payload = payload or {}
    proxy_text = str(payload.get("proxy_text") or "").strip()
    if not proxy_text:
        return {"ok": False, "reason": "代理列表为空", "count": 0}

    lines = [line.strip() for line in proxy_text.splitlines() if line.strip()]
    logger.info("[PROXY] 浏览器插件请求检测 %d 个代理", len(lines))

    # 检测最多 100 个，返回最多 80 个可用代理，50 并发线程
    proxies, check_lines = check_proxy_list(proxy_text, max_checks=min(len(lines), 100), max_working=80)
    _safe_lines(check_lines)

    if not proxies:
        return {"ok": False, "reason": f"❌ {len(lines)} 个代理全部检测失败", "count": 0}

    checked_text = render_proxy_list(proxies)
    return {
        "ok": True,
        "reason": f"✅ {len(proxies)}/{min(len(lines), 100)} 个代理可用",
        "count": len(proxies),
        "total_input": len(lines),
        "proxy_text": checked_text,
        "proxies": [line.strip() for line in checked_text.splitlines() if line.strip()],
    }


def _probe_free_sms_for_extension(country: str) -> list[dict[str, Any]]:
    providers = _free_temp_sms_providers()
    rows_by_provider: dict[str, dict[str, Any]] = {}

    def check(provider: str) -> dict[str, Any]:
        result = check_sms_service(
            provider,
            base_url=FREE_SMS_BASE_URLS.get(provider, ""),
            country=country or "USA",
        )
        return result.to_dict()

    with ThreadPoolExecutor(max_workers=min(14, max(1, len(providers)))) as executor:
        futures = {executor.submit(check, provider): provider for provider in providers}
        for future in as_completed(futures):
            provider = futures[future]
            try:
                rows_by_provider[provider] = future.result()
            except Exception as exc:
                rows_by_provider[provider] = {
                    "provider": provider,
                    "ok": False,
                    "status": "fail",
                    "reason": str(exc)[:240],
                    "details": {"url": FREE_SMS_BASE_URLS.get(provider, "")},
                    "duration_ms": 0,
                }

    return [rows_by_provider[provider] for provider in providers if provider in rows_by_provider]


def _refresh_free_sms_diagnostics(config: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    sms = config.setdefault("sms", {})
    diagnostics = config.setdefault("diagnostics", {})
    country = str(payload.get("country") or sms.get("country") or "USA")
    rows = _probe_free_sms_for_extension(country)
    items = [_sms_diag_item(row) for row in rows]
    primary_item = next((item for item in items if item.get("ok")), None)
    sms["diagnostic_primary"] = str(primary_item.get("provider") if primary_item else "")
    sms["diagnostic_status"] = str(primary_item.get("status") if primary_item else "block")
    sms["diagnostic_reason"] = str(primary_item.get("reason") if primary_item else "没有免费短信 provider 通过健康检查")
    sms["country"] = country
    sms["providers"] = rows
    diagnostics["last_checked_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    diagnostics["sms"] = rows
    save_runtime_config(config)
    logger.info(
        "[OK] extension_sms_diagnostics_refreshed ok=%s total=%s primary=%s",
        len([item for item in items if item.get("ok")]),
        len(items),
        sms.get("diagnostic_primary") or "",
    )
    return config


def sms_diagnostics_for_extension(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    try:
        config = load_runtime_config()
    except Exception as exc:
        config = {}
        load_error = str(exc)
    else:
        load_error = ""

    if config and not load_error and bool(payload.get("probe")):
        try:
            config = _refresh_free_sms_diagnostics(config, payload)
        except Exception as exc:
            load_error = str(exc)

    sms = config.get("sms", {}) or {}
    diagnostics = config.get("diagnostics", {}) or {}
    diagnostic_rows = diagnostics.get("sms", []) or sms.get("providers", []) or []
    free_rows = [
        _sms_diag_item(item)
        for item in diagnostic_rows
        if isinstance(item, dict) and item.get("provider") and not is_real_sms_provider(str(item.get("provider") or ""))
    ]
    configured_free_provider = str(
        sms.get("diagnostic_primary")
        or (sms.get("primary") if not is_real_sms_provider(str(sms.get("primary") or "")) else "")
        or (sms.get("provider") if not is_real_sms_provider(str(sms.get("provider") or "")) else "")
        or ""
    )
    if not free_rows:
        free_rows = [
            _sms_diag_item({
                "provider": provider,
                "ok": False,
                "status": "configured" if provider == configured_free_provider else "not_checked",
                "reason": "configured in runtime_config" if provider == configured_free_provider else "not checked yet",
            })
            for provider in DIAGNOSTIC_SMS_SERVICES
            if not is_real_sms_provider(provider)
        ]

    primary = configured_free_provider
    if not primary:
        ok_item = next((item for item in free_rows if item.get("ok")), None)
        primary = str(ok_item.get("provider") if ok_item else "")

    ok_count = len([item for item in free_rows if item.get("ok")])
    return {
        "ok": not load_error,
        "reason": load_error,
        "source": "runtime_config.toml" if config else "built_in_supported_list",
        "requested_by": str(payload.get("source") or "browser_extension"),
        "checked_at": str((diagnostics.get("last_checked_at") if isinstance(diagnostics, dict) else "") or ""),
        "diagnostic_primary": primary,
        "diagnostic_status": str(sms.get("diagnostic_status") or ("ok" if ok_count else "not_checked")),
        "diagnostic_reason": str(sms.get("diagnostic_reason") or ""),
        "real_provider": str(sms.get("provider") or sms.get("real_provider") or ""),
        "country": str(sms.get("country") or payload.get("country") or ""),
        "providers": free_rows,
        "ok_count": ok_count,
        "total": len(free_rows),
    }


def sms_numbers_for_extension(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    try:
        config = load_runtime_config()
    except Exception:
        config = {}
    sms = config.get("sms", {}) or {}
    provider = str(
        payload.get("provider")
        or sms.get("diagnostic_primary")
        or sms.get("primary")
        or "receive_sms_live"
    )
    if is_real_sms_provider(provider):
        provider = "receive_sms_live"
    country = str(payload.get("country") or sms.get("country") or "USA")
    base_url = str(payload.get("base_url") or FREE_SMS_BASE_URLS.get(provider, ""))
    limit = int(payload.get("limit") or 30)
    result = list_public_sms_numbers(provider, base_url=base_url, country=country, limit=limit)
    result["requested_by"] = str(payload.get("source") or "browser_extension")
    result["country"] = country
    return result


def sms_messages_for_extension(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    try:
        config = load_runtime_config()
    except Exception:
        config = {}
    sms = config.get("sms", {}) or {}
    provider = str(
        payload.get("provider")
        or sms.get("diagnostic_primary")
        or sms.get("primary")
        or "receive_sms_live"
    )
    if is_real_sms_provider(provider):
        provider = "receive_sms_live"
    country = str(payload.get("country") or sms.get("country") or "USA")
    base_url = str(payload.get("base_url") or FREE_SMS_BASE_URLS.get(provider, ""))
    result = fetch_public_sms_messages(
        provider,
        phone=str(payload.get("phone") or payload.get("number") or ""),
        message_url=str(payload.get("message_url") or payload.get("messageUrl") or ""),
        base_url=base_url,
        country=country,
        limit=int(payload.get("limit") or 30),
    )
    result["requested_by"] = str(payload.get("source") or "browser_extension")
    result["country"] = country
    return result


def save_outlook_result_if_ready(provider: str, email: str, password: str, source: str) -> None:
    if provider not in {"outlook", "hotmail"} or not email or not password:
        return
    result = save_created_outlook_account(
        email,
        password,
        client_id=BUILTIN_CLIENT_ID,
        source=source,
        final_state="provider_success",
        start_token_job=False,
    )
    logger.info(
        "[OK] outlook_account_saved email=%s credential=%s token_job=%s",
        email,
        result.get("credential_path") or result.get("combo_path") or "<none>",
        (result.get("token_job") or {}).get("status") or "not_requested",
    )


attach_web_log_handler()
logger.info("Web UI 日志面板已启用")

# 全局Ninjemail实例
ninja = None

ACCOUNT_CAPTCHA_SERVICES = set(REAL_CAPTCHA_SERVICES)
ACCOUNT_SMS_SERVICES = set(REAL_SMS_SERVICES)
RUN_MODES = ["probe", "page_check", "visible_flow_probe", "real_run"]
PROVIDER_TARGET_URLS = {
    "outlook": "https://signup.live.com/signup",
    "gmail": "https://accounts.google.com/signup/v2/createaccount?flowName=GlifWebSignIn&flowEntry=SignUp",
    "yahoo": "https://login.yahoo.com/account/create",
}
PAGE_READY_SELECTORS = {
    "outlook": [
        (By.CSS_SELECTOR, "input[name='email']"),
        (By.CSS_SELECTOR, "button[type='submit']"),
        (By.ID, "liveSwitch"),
        (By.ID, "usernameInput"),
        (By.ID, "nextButton"),
    ],
    "gmail": [(By.ID, "firstName"), (By.ID, "lastName")],
    "yahoo": [(By.ID, "usernamereg-userId"), (By.ID, "usernamereg-password")],
}


def _creation_proxy_items(proxy: dict[str, Any]) -> list[str]:
    target_pools = proxy.get("target_stable_pools") or {}
    if isinstance(target_pools, dict):
        urls: list[str] = []
        for pool in target_pools.values():
            for item in pool or []:
                if isinstance(item, dict):
                    value = str(item.get("url") or "").strip()
                else:
                    value = str(item or "").strip()
                if value and value not in urls:
                    urls.append(value)
        if urls:
            return urls
    stable_items = proxy.get("stable_items") or []
    if stable_items:
        return [str(item) for item in stable_items if str(item).strip()]
    stable_pool = proxy.get("stable_pool") or []
    urls = [str(item.get("url") or "") for item in stable_pool if isinstance(item, dict)]
    urls = [item for item in urls if item.strip()]
    if urls:
        return urls
    return [str(item) for item in proxy.get("items", []) or [] if str(item).strip()]


def _initial_config() -> dict[str, Any]:
    try:
        return load_runtime_config()
    except Exception as exc:
        logger.warning("[BLOCK] 启动时读取 runtime_config.toml 失败: %s", exc)
        return {}


INITIAL_CONFIG = _initial_config()


def _config_section(name: str) -> dict[str, Any]:
    return INITIAL_CONFIG.get(name, {}) or {}


def _initial_proxy_text() -> str:
    proxy = _config_section("proxy")
    return "\n".join(_creation_proxy_items(proxy))


def _initial_ninjemail_extension_enabled() -> bool:
    extension_cfg = _config_section("browser_extension")
    if "enabled" in extension_cfg:
        return bool(extension_cfg.get("enabled"))
    return True


def _initial_ninjemail_extension_path() -> str:
    return str(DEFAULT_NINJEMAIL_EXTENSION_PATH)


def _initial_status() -> str:
    if not INITIAL_CONFIG:
        return "未加载到 runtime_config.toml；请点“实测更多服务并更新配置”。"
    proxy = _config_section("proxy")
    captcha = _config_section("captcha")
    sms = _config_section("sms")
    stable_count = len(_creation_proxy_items(proxy))
    working_count = len(proxy.get("all_items", []) or proxy.get("items", []) or [])
    sms_display = sms.get("primary") or sms.get("provider") or f"真实创建未配置；诊断可用: {sms.get('diagnostic_primary') or '未配置'}"
    return (
        "已加载 runtime_config.toml\n"
        f"代理: stable={stable_count} working={working_count}\n"
        f"验证码: {captcha.get('primary') or captcha.get('provider') or '未配置'}\n"
        f"短信: {sms_display}"
    )


if INITIAL_CONFIG:
    logger.info(
        "[STEP] 启动时已自动加载 runtime_config.toml: proxy=%d captcha=%s sms=%s",
        len(_creation_proxy_items(_config_section("proxy"))),
        _config_section("captcha").get("primary") or _config_section("captcha").get("provider") or "<none>",
        _config_section("sms").get("primary") or _config_section("sms").get("provider") or "<none>",
    )


def _safe_lines(lines: list[str]) -> str:
    for line in lines:
        logger.info(line)
    return "\n".join(lines)


def _needs_key(provider: str, category: str) -> str:
    provider = str(provider or "").lower()
    if category == "captcha" and provider in {"capsolver", "capmonster", "anti_captcha", "2captcha", "twocaptcha", "yescaptcha"}:
        return "是"
    if category == "sms" and provider in {"textbee", "vendel", "getsmscode", "smspool", "5sim"}:
        return "是"
    if category == "proxy" and provider in {"webshare", "getfreeproxy"}:
        return "是"
    return "否"


def _health_row(category: str, provider: str, ok: bool, status: str, reason: str, details: dict[str, Any] | None = None) -> list[Any]:
    details = details or {}
    count = details.get("numbers") or details.get("working_count") or details.get("fetched") or ""
    route = details.get("route") or details.get("source_route") or details.get("message_page_route") or ""
    latency = details.get("route_latency_ms") or details.get("latency_ms") or details.get("source_latency_ms") or ""
    return [
        category,
        provider,
        "ok" if ok else status,
        _needs_key(provider, category),
        route,
        latency,
        count,
        reason,
    ]


def _rows_from_config(config: dict[str, Any]) -> list[list[Any]]:
    rows: list[list[Any]] = []
    diagnostics = config.get("diagnostics", {}) or {}
    proxy = config.get("proxy", {}) or {}
    target_pools = proxy.get("target_stable_pools") or {}
    if isinstance(target_pools, dict):
        for target_name, pool in target_pools.items():
            for item in pool or []:
                if isinstance(item, dict):
                    rows.append(
                        _health_row(
                            f"proxy({target_name})",
                            str(item.get("source") or "target_pool"),
                            True,
                            "ok",
                            str(item.get("url") or ""),
                            item,
                        )
                    )
    for item in proxy.get("stable_pool", []) or []:
        rows.append(
            _health_row(
                "proxy(real)",
                str(item.get("source") or "stable_pool"),
                True,
                "ok",
                str(item.get("url") or ""),
                item,
            )
        )
    for item in proxy.get("pool", []) or proxy.get("working", []) or []:
        rows.append(
            _health_row(
                "proxy(diag)",
                str(item.get("source") or "proxy"),
                True,
                "ok",
                str(item.get("url") or ""),
                item,
            )
        )
    for item in diagnostics.get("captcha", []) or config.get("captcha", {}).get("providers", []) or []:
        rows.append(_health_row("captcha", item.get("provider", ""), bool(item.get("ok")), item.get("status", ""), item.get("reason", ""), item.get("details", {}) or {}))
    for item in diagnostics.get("sms", []) or config.get("sms", {}).get("providers", []) or []:
        rows.append(_health_row("sms", item.get("provider", ""), bool(item.get("ok")), item.get("status", ""), item.get("reason", ""), item.get("details", {}) or {}))
    for item in diagnostics.get("network_route_checks", []) or []:
        rows.append([
            "network",
            str(item.get("url", ""))[:54],
            "ok" if item.get("ok") else "fail",
            "否",
            item.get("route", ""),
            item.get("latency_ms", ""),
            "",
            f"HTTP {item.get('http_status', 0)} {item.get('error', '')}",
        ])
    extension_cfg = config.get("browser_extension", {}) or {}
    if extension_cfg.get("enabled"):
        rows.append([
            "plugin",
            "ninjemail",
            "enabled",
            "否",
            "",
            "",
            "",
            extension_cfg.get("path", "") or str(DEFAULT_NINJEMAIL_EXTENSION_PATH),
        ])
    return rows


def _row_from_result(category: str, result) -> list[list[Any]]:
    return [_health_row(category, result.provider or category, result.ok, result.status, result.reason, result.details)]


def probe_network_routes_ui():
    logger.info("[STEP] 开始双通道网络实测")
    rows = []
    for item in probe_network_routes():
        logger.info(
            "[NETWORK][CHECK] url=%s status=%s route=%s latency_ms=%s http_status=%s",
            item.get("url"),
            "ok" if item.get("ok") else "fail",
            item.get("route") or "<none>",
            item.get("latency_ms") or 0,
            item.get("http_status") or 0,
        )
        rows.append([
            "network",
            str(item.get("url", ""))[:54],
            "ok" if item.get("ok") else "fail",
            "否",
            item.get("route", ""),
            item.get("latency_ms", ""),
            "",
            f"HTTP {item.get('http_status', 0)} {item.get('error', '')}",
        ])
    return rows, get_web_log_text()


def fetch_free_proxy_ui(proxy_api_key, webshare_token):
    logger.info("[STEP] 开始获取免费代理")
    proxies, lines = fetch_free_proxies(api_key=proxy_api_key or "", webshare_token=webshare_token or "")
    _safe_lines(lines)
    if not proxies:
        return "", "❌ 未获取到可用代理，仍可手动填写代理。", [], get_web_log_text()
    rows = [_health_row("proxy", proxy.source, True, "ok", proxy.url, proxy.to_dict()) for proxy in proxies]
    return render_proxy_list(proxies), f"✅ 获取到 {len(proxies)} 个通过检测的代理。", rows, get_web_log_text()


def check_proxy_ui(proxy_list):
    logger.info("[STEP] 开始检测代理列表")
    proxies, lines = check_proxy_list(proxy_list or "")
    _safe_lines(lines)
    if not proxies:
        return proxy_list or "", "❌ 没有代理通过检测。", [], get_web_log_text()
    rows = [_health_row("proxy", proxy.source, True, "ok", proxy.url, proxy.to_dict()) for proxy in proxies]
    return render_proxy_list(proxies), f"✅ {len(proxies)} 个代理通过检测，已筛选回代理框。", rows, get_web_log_text()


def stable_proxy_ui(proxy_list):
    logger.info("[STEP] proxy_stable_recheck rounds=3 target=generic+provider_domains")
    stable, lines, summary = build_stable_proxy_pool(proxy_list or "", rounds=3, required_success_rate=1.0, max_checks=30)
    _safe_lines(lines)
    rows = [_health_row("proxy(real)", proxy.source, True, "ok", proxy.url, proxy.to_dict()) for proxy in stable]
    target_union: list[str] = []
    target_counts: dict[str, int] = {}
    for target_name, target_url in PROVIDER_TARGET_URLS.items():
        target_stable, target_lines, target_summary = build_stable_proxy_pool(
            proxy_list or "",
            rounds=3,
            required_success_rate=1.0,
            max_checks=20,
            target_url=target_url,
            target_name=target_name,
        )
        _safe_lines(target_lines)
        target_counts[target_name] = int(target_summary.get("stable_count", 0) or 0)
        for proxy in target_stable:
            if proxy.url not in target_union:
                target_union.append(proxy.url)
            rows.append(_health_row(f"proxy({target_name})", proxy.source, True, "ok", proxy.url, proxy.to_dict()))
    if target_union:
        return (
            "\n".join(target_union),
            f"✅ target_stable_pool={len(target_union)} generic={len(stable)} targets={target_counts}",
            rows,
            get_web_log_text(),
        )
    if not stable:
        return "", f"❌ no_stable_proxy: {summary.get('stable_count', 0)} passed all rounds", rows, get_web_log_text()
    return render_proxy_list(stable), f"✅ stable_pool={len(stable)} / candidates={summary.get('candidates', 0)}", rows, get_web_log_text()


def check_captcha_ui(captcha_service, captcha_key, captcha_local_url):
    result = check_captcha_service(captcha_service, captcha_key or "", captcha_local_url or "")
    logger.info(result.line("CAPTCHA"))
    prefix = "✅" if result.ok else "❌"
    message = f"{prefix} {result.provider or 'captcha'}: {result.reason}"
    primary = _config_section("captcha").get("primary") or _config_section("captcha").get("provider") or ""
    if not result.ok and primary and result.provider != primary:
        message += f"\n建议先用已实测可用项：{primary}"
    return message, _row_from_result("captcha", result), get_web_log_text()


def check_sms_ui(sms_service, sms_user, sms_token, sms_phone, sms_base_url, sms_country):
    result = check_sms_service(
        sms_service,
        user=sms_user or "",
        token=sms_token or "",
        base_url=sms_base_url or "",
        country=sms_country or "",
    )
    logger.info(result.line("SMS"))
    prefix = "✅" if result.ok else "❌"
    message = f"{prefix} {result.provider or 'sms'}: {result.reason}"
    if str(sms_service or "").lower() in {"textbee", "smsgate"} and not sms_phone:
        message += "\n真实创建还需要填写自有手机号 phone_number。"
    primary = _config_section("sms").get("primary") or _config_section("sms").get("provider") or ""
    if not result.ok and primary and result.provider != primary:
        message += f"\n建议先用已实测可用项：{primary}"
    return message, _row_from_result("sms", result), get_web_log_text()


def check_ninjemail_extension_ui():
    result = check_ninjemail_extension()
    logger.info(result.line())
    if not result.ok:
        return f"❌ Ninjemail 内置浏览器插件不可用: {result.reason}\npath={result.path}", get_web_log_text()
    details = result.details or {}
    return (
        "✅ Ninjemail 内置浏览器插件可加载\n"
        f"name={result.name}\n"
        f"version={result.version}\n"
        f"manifest={result.manifest_version}\n"
        f"background={details.get('has_background')}\n"
        f"sidepanel={details.get('has_side_panel')}\n"
        f"content_scripts={details.get('content_script_count')}\n"
        f"path={result.path}",
        get_web_log_text(),
    )


def dry_run_config(
    captcha_service,
    captcha_key,
    captcha_local_url,
    sms_service,
    sms_user,
    sms_token,
    sms_phone,
    sms_base_url,
    sms_country,
    use_auto_proxy,
    proxy_list,
):
    logger.info("[STEP] dry-run 检查当前基础服务配置")
    messages = []
    proxy_count = len([p for p in str(proxy_list or "").splitlines() if p.strip()])
    logger.info("[STEP] proxy configured=%d auto_proxy=%s", proxy_count, use_auto_proxy)
    if proxy_count:
        proxies, lines = check_proxy_list(proxy_list or "", max_checks=min(proxy_count, 40), max_working=20)
        _safe_lines(lines)
        messages.append(f"代理: {len(proxies)} 个可用 / {proxy_count} 个输入")
    else:
        messages.append("代理: 未手动配置；可点击获取免费代理或继续留空")

    if captcha_service:
        captcha_result = check_captcha_service(captcha_service, captcha_key or "", captcha_local_url or "")
        logger.info(captcha_result.line("CAPTCHA"))
        messages.append(f"验证码: {'通过' if captcha_result.ok else '未通过'} - {captcha_result.reason}")
        if not is_real_captcha_provider(captcha_service):
            messages.append(f"验证码创建链路: BLOCK - {captcha_service} 只用于诊断，真实创建仅支持 {', '.join(REAL_CAPTCHA_SERVICES)}")
    else:
        messages.append("验证码: 未选择")

    if sms_service:
        sms_result = check_sms_service(
            sms_service,
            user=sms_user or "",
            token=sms_token or "",
            base_url=sms_base_url or "",
            country=sms_country or "",
        )
        logger.info(sms_result.line("SMS"))
        messages.append(f"短信: {'通过' if sms_result.ok else '未通过'} - {sms_result.reason}")
        if not is_real_sms_provider(sms_service):
            messages.append(f"短信创建链路: BLOCK - {sms_service} 只用于诊断，真实创建仅支持 {', '.join(REAL_SMS_SERVICES)}")
        elif str(sms_service or "").lower() in {"textbee", "smsgate"} and not sms_phone:
            messages.append(f"短信创建链路: BLOCK - {sms_service} 需要填写自有手机号 phone_number")
    else:
        messages.append("短信: 未选择")

    return "\n".join(messages), get_web_log_text()


def save_current_config(
    browser,
    use_auto_proxy,
    persistent_browser_profile,
    ninjemail_extension_enabled,
    proxy_list,
    proxy_api_key,
    webshare_token,
    captcha_service,
    captcha_key,
    captcha_local_url,
    sms_service,
    sms_user,
    sms_token,
    sms_phone,
    sms_base_url,
    sms_country,
):
    logger.info("[STEP] 保存当前运行配置前执行健康检查")
    checked_proxy_text = proxy_list or ""
    all_proxy_text = proxy_list or ""
    proxy_pool = []
    stable_pool = []
    target_stable_pools: dict[str, list[dict[str, Any]]] = {}
    stable_summary = {}
    health_rows: list[list[Any]] = []
    if str(proxy_list or "").strip():
        proxies, lines = check_proxy_list(proxy_list or "")
        _safe_lines(lines)
        if not proxies:
            logger.warning("[PROXY][BLOCK] 代理列表未通过检测，配置未保存")
            return "❌ 代理列表没有可用项，配置未保存。", checked_proxy_text, health_rows, get_web_log_text()
        all_proxy_text = render_proxy_list(proxies)
        proxy_pool = [proxy.to_dict() for proxy in proxies]
        stable_proxies, stable_lines, stable_summary = build_stable_proxy_pool(all_proxy_text, rounds=3, required_success_rate=1.0, max_checks=30)
        _safe_lines(stable_lines)
        if not stable_proxies:
            logger.warning("[PROXY][BLOCK] no_stable_proxy, 配置未保存")
            return "❌ no_stable_proxy：三轮复测没有代理全通过，配置未保存。", all_proxy_text, health_rows, get_web_log_text()
        checked_proxy_text = render_proxy_list(stable_proxies)
        stable_pool = [proxy.to_dict() for proxy in stable_proxies]
        health_rows.extend(_health_row("proxy(real)", proxy.source, True, "ok", proxy.url, proxy.to_dict()) for proxy in stable_proxies)
        health_rows.extend(_health_row("proxy(diag)", proxy.source, True, "ok", proxy.url, proxy.to_dict()) for proxy in proxies)
        target_union: list[str] = []
        for target_name, target_url in PROVIDER_TARGET_URLS.items():
            target_stable, target_lines, target_summary = build_stable_proxy_pool(
                all_proxy_text,
                rounds=2,
                required_success_rate=1.0,
                max_checks=20,
                target_url=target_url,
                target_name=target_name,
            )
            _safe_lines(target_lines)
            stable_summary[f"{target_name}_target"] = target_summary
            if not target_stable:
                logger.warning("[PROXY][BLOCK] target=%s no_target_stable_proxy", target_name)
                continue
            target_stable_pools[target_name] = [proxy.to_dict() for proxy in target_stable]
            for proxy in target_stable:
                if proxy.url not in target_union:
                    target_union.append(proxy.url)
                health_rows.append(_health_row(f"proxy({target_name})", proxy.source, True, "ok", proxy.url, proxy.to_dict()))
        if target_union:
            checked_proxy_text = "\n".join(target_union)

    if captcha_service:
        captcha_result = check_captcha_service(captcha_service, captcha_key or "", captcha_local_url or "")
        logger.info(captcha_result.line("CAPTCHA"))
        health_rows.extend(_row_from_result("captcha", captcha_result))
        if not captcha_result.ok:
            return f"❌ 验证码服务未通过检查，配置未保存：{captcha_result.reason}", checked_proxy_text, health_rows, get_web_log_text()

    if sms_service:
        if str(sms_service or "").lower() in {"textbee", "smsgate"} and not sms_phone:
            return f"❌ {sms_service} 需要填写自有手机号 phone_number，配置未保存。", checked_proxy_text, health_rows, get_web_log_text()
        sms_result = check_sms_service(
            sms_service,
            user=sms_user or "",
            token=sms_token or "",
            base_url=sms_base_url or "",
            country=sms_country or "",
        )
        logger.info(sms_result.line("SMS"))
        health_rows.extend(_row_from_result("sms", sms_result))
        if not sms_result.ok:
            return f"❌ 短信服务未通过检查，配置未保存：{sms_result.reason}", checked_proxy_text, health_rows, get_web_log_text()

    if ninjemail_extension_enabled:
        plugin_result = check_ninjemail_extension()
        logger.info(plugin_result.line())
        if not plugin_result.ok:
            return f"❌ Ninjemail 内置浏览器插件未通过检查，配置未保存：{plugin_result.reason}", checked_proxy_text, health_rows, get_web_log_text()
        health_rows.append(_health_row("plugin", "ninjemail", True, "ok", plugin_result.reason, plugin_result.details or {}))

    path = save_runtime_config(
        {
            "browser": browser,
            "auto_proxy": bool(use_auto_proxy),
            "persistent_browser_profile": bool(persistent_browser_profile),
            "browser_extension": {
                "enabled": bool(ninjemail_extension_enabled),
                "path": str(DEFAULT_NINJEMAIL_EXTENSION_PATH),
            },
            "proxy": {
                "api_key": proxy_api_key or "",
                "webshare_token": webshare_token or "",
                "items": [line.strip() for line in checked_proxy_text.splitlines() if line.strip()],
                "stable_items": [line.strip() for line in checked_proxy_text.splitlines() if line.strip()],
                "all_items": [line.strip() for line in all_proxy_text.splitlines() if line.strip()],
                "stable_pool": stable_pool,
                "target_stable_pools": target_stable_pools,
                "pool": proxy_pool,
                "working": proxy_pool,
                "stable_summary": stable_summary,
            },
            "captcha": {
                "provider": captcha_service or "",
                "primary": captcha_service or "",
                "api_key": captcha_key or "",
                "local_url": captcha_local_url or "",
            },
            "sms": {
                "provider": sms_service or "",
                "primary": sms_service or "",
                "user": sms_user or "",
                "token": sms_token or "",
                "phone_number": sms_phone or "",
                "base_url": sms_base_url or "",
                "country": sms_country or "",
            },
        }
    )
    logger.info("[STEP] 当前运行配置已保存到 %s", path)
    return f"✅ 配置已保存：{path}", checked_proxy_text, health_rows, get_web_log_text()


def reload_current_config():
    logger.info("[STEP] 重新加载 runtime_config.toml")
    config = load_runtime_config()
    if not config:
        logger.warning("[BLOCK] 未找到 runtime_config.toml")
        return (
            "chrome",
            False,
            False,
            True,
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "USA",
            "❌ 未找到 runtime_config.toml",
            [],
            get_web_log_text(),
        )
    proxy = config.get("proxy", {}) or {}
    captcha = config.get("captcha", {}) or {}
    sms = config.get("sms", {}) or {}
    browser_extension = config.get("browser_extension", {}) or {}
    proxy_text = "\n".join(_creation_proxy_items(proxy))
    logger.info("[STEP] 已加载 runtime_config.toml")
    return (
        config.get("browser") or "chrome",
        bool(config.get("auto_proxy", False)),
        bool(config.get("persistent_browser_profile", False)),
        bool(browser_extension.get("enabled", True)),
        proxy_text,
        proxy.get("api_key", "") or "",
        proxy.get("webshare_token", "") or "",
        captcha.get("provider", "") or "",
        captcha.get("api_key", "") or "",
        captcha.get("local_url", "") or "",
        sms.get("provider", "") or "",
        sms.get("user", "") or "",
        sms.get("token", "") or "",
        sms.get("phone_number", "") or "",
        sms.get("base_url", "") or "",
        sms.get("country", "") or "USA",
        "✅ 已重新加载运行配置。",
        _rows_from_config(config),
        get_web_log_text(),
    )


def auto_configure_free_services_ui(browser, proxy_api_key, webshare_token, sms_country):
    logger.info("[STEP] 实测更多服务并更新配置")
    config, lines = auto_configure_free_services(
        browser=browser or "chrome",
        country=sms_country or "USA",
        proxy_api_key=proxy_api_key or "",
        webshare_token=webshare_token or "",
    )
    _safe_lines(lines)
    proxy = config.get("proxy", {}) or {}
    captcha = config.get("captcha", {}) or {}
    sms = config.get("sms", {}) or {}
    proxy_text = "\n".join(_creation_proxy_items(proxy))
    stable_count = len(_creation_proxy_items(proxy))
    working_count = len(proxy.get("all_items", []) or proxy.get("items", []) or [])
    sms_display = sms.get("provider") or f"真实创建未配置；诊断可用: {sms.get('diagnostic_primary') or '无'}"
    status = (
        f"✅ 自动配置完成\n"
        f"代理: stable={stable_count} working={working_count}\n"
        f"验证码: {captcha.get('provider') or '无可用项'} - {captcha.get('reason') or ''}\n"
        f"短信: {sms_display} - {sms.get('reason') or sms.get('diagnostic_reason') or ''}"
    )
    return (
        proxy_text,
        captcha.get("provider", "") or "",
        captcha.get("api_key", "") or "",
        captcha.get("local_url", "") or "",
        sms.get("provider", "") or "",
        sms.get("user", "") or "",
        sms.get("token", "") or "",
        sms.get("phone_number", "") or "",
        sms.get("base_url", "") or "",
        sms.get("country", "") or "USA",
        status,
        _rows_from_config(config),
        get_web_log_text(),
    )


def init_ninjemail(browser, captcha_service, captcha_key, sms_service, sms_user, sms_token, sms_phone, sms_base_url, use_auto_proxy, persistent_browser_profile, ninjemail_extension_enabled, proxy_list):
    """初始化Ninjemail实例"""
    global ninja
    proxy_text = str(proxy_list or "")
    proxy_count = len([p for p in proxy_text.split("\n") if p.strip()])
    logger.info("[STEP 1/3] 开始初始化后端")
    logger.info(
        "输入概览: browser=%s, captcha_service=%s, captcha_key=%s, sms_service=%s, sms_user=%s, sms_token=%s, sms_phone=%s, auto_proxy=%s, proxy_count=%d",
        browser or "<empty>",
        captcha_service or "<none>",
        "set" if captcha_key else "empty",
        sms_service or "<none>",
        "set" if sms_user else "empty",
        "set" if sms_token else "empty",
        "set" if sms_phone else "empty",
        use_auto_proxy,
        proxy_count,
    )
    try:
        logger.info("[STEP 2/3] 解析代理列表")
        proxies = None
        if proxy_text.strip():
            proxies = [p.strip() for p in proxy_text.split('\n') if p.strip()]
            logger.info("代理数量: %d", len(proxies))
        else:
            logger.info("未提供代理列表")

        captcha_keys = {}
        unsupported_notes = []
        if captcha_service and captcha_service not in ACCOUNT_CAPTCHA_SERVICES:
            unsupported_notes.append(f"验证码 provider {captcha_service} 目前只接入诊断/配置，未接入创建流程")
            logger.warning("[CAPTCHA][BLOCK] %s", unsupported_notes[-1])
        elif captcha_service and captcha_service != "nopecha" and not captcha_key:
            logger.warning("[BLOCK] 已选择验证码服务，但未填写 API Key")
            return "❌ 初始化失败：请选择验证码服务后必须填写 API Key。", get_web_log_text()
        elif captcha_service:
            captcha_keys[captcha_service] = captcha_key or ""
        
        sms_keys = {}
        if sms_service and sms_service not in ACCOUNT_SMS_SERVICES:
            unsupported_notes.append(f"短信 provider {sms_service} 目前只接入诊断/配置，未接入创建流程")
            logger.warning("[SMS][BLOCK] %s", unsupported_notes[-1])
        elif sms_service and not sms_token:
            logger.warning("[BLOCK] 已选择短信服务，但未填写 Token")
            return "❌ 初始化失败：请选择短信服务后必须填写 Token。", get_web_log_text()
        elif sms_service and sms_token:
            if sms_service in {"textbee", "smsgate"}:
                if not sms_user or not sms_phone:
                    logger.warning("[SMS][BLOCK] own_device_sms_missing_device_or_phone")
                    return f"❌ 初始化失败：{sms_service} 需要填写设备/用户名、Token/密码 和自有手机号。", get_web_log_text()
                if sms_service == "textbee":
                    sms_keys[sms_service] = {
                        "device_id": sms_user,
                        "user": sms_user,
                        "token": sms_token,
                        "phone_number": sms_phone,
                        "base_url": sms_base_url or "https://api.textbee.dev",
                    }
                else:
                    if not sms_base_url:
                        logger.warning("[SMS][BLOCK] smsgate_missing_base_url")
                        return "❌ 初始化失败：SMSGate 需要填写 Local Server Base URL，例如 http://192.168.1.23:8080。", get_web_log_text()
                    sms_keys[sms_service] = {
                        "user": sms_user,
                        "token": sms_token,
                        "phone_number": sms_phone,
                        "base_url": sms_base_url,
                    }
            elif sms_user:
                sms_keys[sms_service] = {"user": sms_user, "token": sms_token}
            else:
                sms_keys[sms_service] = {"token": sms_token}
        logger.info("[STEP 3/3] 创建 Ninjemail 实例")
        browser_plugin_paths = []
        if ninjemail_extension_enabled:
            if str(browser or "").lower() not in {"chrome", "edge"}:
                return "❌ 初始化失败：Ninjemail 内置浏览器插件是 Chromium 扩展，请选择 edge 或 chrome。", get_web_log_text()
            plugin_result = check_ninjemail_extension()
            logger.info(plugin_result.line())
            if not plugin_result.ok:
                return f"❌ 初始化失败：Ninjemail 内置浏览器插件不可用：{plugin_result.reason}", get_web_log_text()
            browser_plugin_paths = [plugin_result.path]

        ninja = Ninjemail(
            browser=browser,
            captcha_keys=captcha_keys,
            sms_keys=sms_keys,
            proxies=proxies,
            auto_proxy=use_auto_proxy,
            proxy_recheck=True,
            persistent_browser_profile=persistent_browser_profile,
            browser_plugin_paths=browser_plugin_paths,
        )
        
        logger.info("初始化完成")
        if unsupported_notes:
            return "⚠️ Ninjemail 已初始化，但有 provider 只完成基础服务诊断，尚未接入创建流程：\n" + "\n".join(unsupported_notes), get_web_log_text()
        return "✅ Ninjemail 初始化成功！", get_web_log_text()
    except Exception as e:
        logger.exception("[BLOCK] 初始化失败")
        return f"❌ 初始化失败: {type(e).__name__}: {str(e)}", get_web_log_text()

def _flow_snapshot(provider: str, use_proxy: bool) -> dict[str, Any]:
    if not ninja:
        return {"provider": provider, "initialized": False, "snapshot_kind": "historical_config"}
    return {
        "provider": provider,
        "initialized": True,
        "snapshot_kind": "active_config",
        "browser": getattr(ninja, "browser", ""),
        "use_proxy": bool(use_proxy),
        "webdriver_visible": bool(getattr(ninja, "webdriver_visible", False)),
        "persistent_browser_profile": bool(getattr(ninja, "persistent_browser_profile", False)),
        "browser_plugin_paths": list(getattr(ninja, "browser_plugin_paths", []) or []),
        "proxy_count": len(getattr(ninja, "proxies", []) or []),
        "auto_proxy": bool(getattr(ninja, "auto_proxy", False)),
        "captcha_providers": list((getattr(ninja, "captcha_keys", {}) or {}).keys()),
        "sms_providers": list((getattr(ninja, "sms_keys", {}) or {}).keys()),
        "real_captcha_services": list(REAL_CAPTCHA_SERVICES),
        "real_sms_services": list(REAL_SMS_SERVICES),
    }


def _provider_needs(provider: str) -> tuple[bool, bool]:
    provider = provider.lower()
    return provider in {"outlook", "yahoo"}, provider in {"gmail", "yahoo"}


def _validate_creation_ready(provider: str, use_proxy: bool, report: FlowRunReport, *, include_sms: bool = True) -> bool:
    if not ninja:
        report.block("config.initialized", "ninjemail_not_initialized", blocker="config")
        return False
    needs_captcha, needs_sms = _provider_needs(provider)
    report.start_step("config.provider_capability", provider=provider)
    if needs_captcha:
        try:
            captcha_key = ninja.get_captcha_key("outlook" if provider == "outlook" else "yahoo")
            if not is_real_captcha_provider(captcha_key.get("name", "")):
                report.block("config.provider_capability", f"captcha_provider_not_real: {captcha_key.get('name')}", blocker="captcha")
                return False
        except Exception as exc:
            report.fail("config.provider_capability", exc)
            return False
    if needs_sms and include_sms:
        try:
            sms_key = ninja.get_sms_key()
            sms_name = sms_key.get("name", "")
            sms_data = sms_key.get("data") or {}
            if not is_real_sms_provider(sms_name):
                report.block("config.provider_capability", f"sms_provider_not_real: {sms_name}", blocker="sms")
                return False
            if isinstance(sms_data, dict) and not sms_data.get("token"):
                report.block("config.provider_capability", f"sms_token_missing: {sms_name}", blocker="sms")
                return False
            if sms_name in {"textbee", "smsgate"} and isinstance(sms_data, dict):
                if sms_name == "textbee" and not sms_data.get("device_id"):
                    report.block("config.provider_capability", "textbee_device_id_missing", blocker="sms")
                    return False
                if not sms_data.get("phone_number"):
                    report.block("config.provider_capability", f"{sms_name}_phone_number_missing", blocker="sms")
                    return False
                if sms_name == "smsgate" and not sms_data.get("base_url"):
                    report.block("config.provider_capability", "smsgate_base_url_missing", blocker="sms")
                    return False
        except Exception as exc:
            report.fail("config.provider_capability", exc)
            return False
    if use_proxy and not (getattr(ninja, "proxies", None) or getattr(ninja, "auto_proxy", False)):
        report.block("config.provider_capability", "no_stable_proxy", blocker="proxy")
        return False
    report.ok("config.provider_capability")
    return True


def _save_flow_report(report: FlowRunReport) -> str:
    json_path, md_path = report.save_all()
    set_root_cause_from_report(report)
    root_reason = (report.root_cause or {}).get("reason") or "<none>"
    logger.info("[OK] flow_report status=%s root_cause=%s", report.status, root_reason)
    logger.info("[NEXT] report_json=%s report_md=%s", json_path, md_path)
    hint = ""
    if report.blockers:
        first = report.blockers[0]
        if first.get("repair_hint"):
            hint = f"\nrepair_hint: {first.get('repair_hint')}"
    compact_root = " ".join(str(root_reason or "").split())
    root_line = f"\nroot_cause: {compact_root[:500]}" if compact_root and compact_root != "<none>" else ""
    return f"{hint}{root_line}\nreport_json: {json_path}\nreport_md: {md_path}"


def _browser_error_reason(driver) -> str:
    markers = [
        "ERR_TIMED_OUT",
        "ERR_PROXY_CONNECTION_FAILED",
        "ERR_CONNECTION_RESET",
        "ERR_TUNNEL_CONNECTION_FAILED",
        "This site can't be reached",
        "This site can’t be reached",
        "took too long to respond",
        "无法访问此网站",
        "响应时间过长",
    ]
    fragments = []
    for attr in ("title", "current_url"):
        try:
            fragments.append(str(getattr(driver, attr, "") or ""))
        except Exception:
            pass
    try:
        fragments.append(str(driver.page_source or "")[:6000])
    except Exception:
        pass
    haystack = "\n".join(fragments)
    lower = haystack.lower()
    for marker in markers:
        if marker.lower() in lower:
            return marker
    return ""


def _should_retry_direct_after_proxy_failure(status_text: str, report_text: str) -> bool:
    combined = f"{status_text}\n{report_text}".lower()
    return any(
        token in combined
        for token in (
            "no_stable_proxy",
            "err_proxy_connection_failed",
            "err_tunnel_connection_failed",
            "err_timed_out",
            "net::err_",
            "browser_error_page",
            "proxy_connection_failed",
            "proxy target unreachable",
        )
    )


def _retryable_page_check_error(exc: BaseException) -> bool:
    text = f"{type(exc).__name__}: {exc}".lower()
    return any(
        token in text
        for token in (
            "net::err_",
            "browser_error_page",
            "err_timed_out",
            "page_ready_selector_timeout",
            "timed out receiving message from renderer",
            "timeout",
            "connection reset",
            "connection refused",
        )
    )


def _wait_for_page_ready(driver, provider: str, timeout: int = 20) -> str:
    selectors = PAGE_READY_SELECTORS.get(provider, [])
    if not selectors:
        return ""

    def _find_ready(current_driver):
        for by, value in selectors:
            try:
                elements = current_driver.find_elements(by, value)
            except Exception:
                elements = []
            if elements:
                return f"{by}={value}"
        return False

    try:
        return WebDriverWait(driver, timeout).until(_find_ready)
    except TimeoutException as exc:
        selectors_text = ", ".join(f"{by}={value}" for by, value in selectors)
        raise TimeoutException(f"page_ready_selector_timeout provider={provider} selectors={selectors_text}") from exc


def _run_page_check(provider: str, use_proxy: bool, report: FlowRunReport) -> None:
    urls = {
        "outlook": "https://signup.live.com/signup",
        "gmail": "https://accounts.google.com/signup/v2/createaccount?flowName=GlifWebSignIn&flowEntry=SignUp",
        "yahoo": "https://login.yahoo.com/account/create",
    }
    needs_captcha, _ = _provider_needs(provider)
    max_attempts = 1
    if use_proxy:
        max_attempts = max(1, min(len(getattr(ninja, "proxies", []) or []), 5))
    last_exc: BaseException | None = None

    for attempt in range(1, max_attempts + 1):
        driver = None
        captcha_key = {}
        proxy = None
        try:
            if use_proxy:
                report.start_step("page_check.proxy", attempt=attempt)
                proxy = ninja.get_proxy(target_url=urls[provider], provider=provider)
                report.ok("page_check.proxy", proxy=proxy or "<none>", attempt=attempt)
            if needs_captcha:
                report.start_step("page_check.captcha_key", attempt=attempt)
                captcha_key = ninja.get_captcha_key("outlook" if provider == "outlook" else "yahoo")
                report.ok("page_check.captcha_key", provider=captcha_key.get("name"), attempt=attempt)
            report.start_step("page_check.create_driver", browser=ninja.browser, proxy=bool(proxy), attempt=attempt)
            driver = create_driver(ninja.browser, captcha_extension=needs_captcha, proxy=proxy, captcha_key=captcha_key)
            report.ok("page_check.create_driver", attempt=attempt)
            report.start_step("page_check.open_signup", url=urls[provider], proxy=proxy or "<none>", attempt=attempt)
            driver.get(urls[provider])
            error_reason = _browser_error_reason(driver)
            if error_reason:
                screenshot = report.capture_screenshot(driver, f"{provider}.page_check_error_attempt_{attempt}")
                raise RuntimeError(f"browser_error_page: {error_reason}; screenshot={screenshot}")
            ready_selector = _wait_for_page_ready(driver, provider)
            screenshot = report.capture_screenshot(driver, f"{provider}.page_check")
            report.ok(
                "page_check.open_signup",
                current_url=getattr(driver, "current_url", ""),
                title=getattr(driver, "title", ""),
                ready_selector=ready_selector,
                screenshot=screenshot,
                attempt=attempt,
            )
            return
        except Exception as exc:
            last_exc = exc
            details = {"attempt": attempt, "proxy": proxy or "<none>"}
            if driver is not None:
                screenshot = report.capture_screenshot(driver, f"{provider}.page_check_exception_attempt_{attempt}")
                details.update(
                    {
                        "current_url": getattr(driver, "current_url", ""),
                        "title": getattr(driver, "title", ""),
                        "screenshot": screenshot,
                    }
                )
            for step_name in ("page_check.open_signup", "page_check.create_driver"):
                step = report._find_step(step_name)
                if step is not None and step.status == "running":
                    report.fail_step(step_name, exc, blocker="network", **details)
            if use_proxy and attempt < max_attempts and _retryable_page_check_error(exc):
                logger.warning(
                    "[PAGE_CHECK][RETRY] provider=%s attempt=%s/%s proxy=%s reason=%s",
                    provider,
                    attempt,
                    max_attempts,
                    proxy or "<none>",
                    exc,
                )
                if driver is not None:
                    try:
                        driver.quit()
                    except Exception:
                        pass
                continue
            report.fail("page_check", exc, **details)
            raise
        finally:
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass

    if last_exc is not None:
        report.fail("page_check", last_exc)
        raise last_exc


def _run_creation_flow(provider: str, run_mode: str, use_proxy: bool, real_callback):
    mode = run_mode if run_mode in RUN_MODES else "probe"
    report = FlowRunReport(mode=mode, provider=provider, config_snapshot=_flow_snapshot(provider, use_proxy))
    logger.info("[STEP] provider=%s mode=%s start", provider, mode)
    previous_visible = bool(getattr(ninja, "webdriver_visible", False)) if ninja else False
    visible_mode = mode in {"visible_flow_probe", "real_run"}
    if ninja:
        ninja.set_flow_report(report)
        if visible_mode:
            ninja.set_webdriver_visible(True)
            logger.info("[STEP] visible_browser enabled mode=%s provider=%s", mode, provider)
    try:
        if mode == "probe":
            ready = _validate_creation_ready(provider, use_proxy, report, include_sms=True)
            if use_proxy and ready:
                report.start_step("probe.proxy_quick_recheck")
                target_url = PROVIDER_TARGET_URLS.get(provider, "")
                proxy = ninja.get_proxy(target_url=target_url, provider=provider)
                report.ok("probe.proxy_quick_recheck", proxy=proxy or "<none>", target_url=target_url)
            report.start_step("probe.provider_create_account")
            if ready:
                report.ok("probe.provider_create_account", action="planned_only")
                report.finish("ok")
                return "✅ probe 完成，未打开第三方页面。", "", _save_flow_report(report)
            report.block("probe.provider_create_account", "blocked_before_real_flow")
            report.finish("blocked")
            return "❌ probe 发现阻碍，未进入真实创建。", "", _save_flow_report(report)
        if mode == "page_check":
            if not _validate_creation_ready(provider, use_proxy, report, include_sms=False):
                report.finish("blocked")
                return "❌ page_check 前置检查失败。", "", _save_flow_report(report)
            _run_page_check(provider, use_proxy, report)
            report.finish("ok")
            return "✅ page_check 完成，只打开并截图页面，未提交表单。", "", _save_flow_report(report)
        if mode == "visible_flow_probe":
            if not _validate_creation_ready(provider, use_proxy, report, include_sms=True):
                report.finish("blocked")
                return "❌ visible_flow_probe 前置检查失败，未打开第三方提交步骤。", "", _save_flow_report(report)
            logger.info("[STEP] visible_flow_probe will run until first live blocker or success")
            email, pwd = real_callback()
            save_outlook_result_if_ready(provider, email, pwd, "web_ui_visible_flow_probe")
            report.finish("ok")
            return "✅ visible_flow_probe 完成：流程未遇到阻塞。", f"邮箱: {email}\n密码: {pwd}", _save_flow_report(report)
        if not _validate_creation_ready(provider, use_proxy, report, include_sms=True):
            report.finish("blocked")
            return "❌ real_run 前置检查失败，未打开第三方提交步骤。", "", _save_flow_report(report)
        email, pwd = real_callback()
        save_outlook_result_if_ready(provider, email, pwd, "web_ui_real_run")
        report.finish("ok")
        return "✅ 创建成功！", f"邮箱: {email}\n密码: {pwd}", _save_flow_report(report)
    except Exception as exc:
        if getattr(report, "keep_browser_open", False) or report.status == "blocked":
            if not report.root_cause:
                report.block(f"{provider}.{mode}", str(exc), blocker="provider")
            report.finish("blocked")
            logger.warning("[BLOCK] provider=%s mode=%s stopped_at_blocker reason=%s", provider, mode, exc)
            return f"⏸ {mode} 已停在阻塞点: {type(exc).__name__}: {exc}", "", _save_flow_report(report)
        report.fail(f"{provider}.{mode}", exc)
        report.finish("failed")
        return f"❌ {mode} 失败: {type(exc).__name__}: {exc}", "", _save_flow_report(report)
    finally:
        if ninja:
            ninja.set_webdriver_visible(previous_visible)
            ninja.set_flow_report(None)


def create_outlook(username, password, first_name, last_name, country, birthdate, use_proxy, run_mode, hotmail=False):
    """创建Outlook/Hotmail账户"""
    if not ninja:
        logger.warning("[BLOCK] 请先初始化 Ninjemail")
        return "请先初始化Ninjemail！", "", get_web_log_text()

    logger.info("[FLOW] requested Outlook/Hotmail mode=%s use_proxy=%s", run_mode, use_proxy)
    def _callback(proxy_enabled: bool):
        return ninja.create_outlook_account(
            username=username or "",
            password=password or "",
            first_name=first_name or "",
            last_name=last_name or "",
            country=country or "",
            birthdate=birthdate or "",
            hotmail=bool(hotmail),
            use_proxy=proxy_enabled,
        )

    status, result, report = _run_creation_flow(
        "outlook",
        run_mode,
        bool(use_proxy),
        lambda: _callback(bool(use_proxy)),
    )
    if bool(use_proxy) and _should_retry_direct_after_proxy_failure(status, report):
        logger.warning("[FIX] provider=outlook proxy_failure action=retry_direct")
        status, result, report = _run_creation_flow(
            "outlook",
            run_mode,
            False,
            lambda: _callback(False),
        )
    return status + report, result, get_web_log_text()


def create_gmail(username, password, first_name, last_name, birthdate, use_proxy, run_mode):
    """创建Gmail账户"""
    if not ninja:
        logger.warning("[BLOCK] 请先初始化 Ninjemail")
        return "请先初始化Ninjemail！", "", get_web_log_text()

    logger.info("[FLOW] requested Gmail mode=%s use_proxy=%s", run_mode, use_proxy)
    status, result, report = _run_creation_flow(
        "gmail",
        run_mode,
        bool(use_proxy),
        lambda: ninja.create_gmail_account(
            username=username or "",
            password=password or "",
            first_name=first_name or "",
            last_name=last_name or "",
            birthdate=birthdate or "",
            use_proxy=use_proxy,
        ),
    )
    if bool(use_proxy) and _should_retry_direct_after_proxy_failure(status, report):
        logger.warning("[FIX] provider=gmail proxy_failure action=retry_direct")
        status, result, report = _run_creation_flow(
            "gmail",
            run_mode,
            False,
            lambda: ninja.create_gmail_account(
                username=username or "",
                password=password or "",
                first_name=first_name or "",
                last_name=last_name or "",
                birthdate=birthdate or "",
                use_proxy=False,
            ),
        )
    return status + report, result, get_web_log_text()


def create_yahoo(username, password, first_name, last_name, birthdate, use_proxy, run_mode):
    """创建Yahoo账户"""
    if not ninja:
        logger.warning("[BLOCK] 请先初始化 Ninjemail")
        return "请先初始化Ninjemail！", "", get_web_log_text()

    logger.info("[FLOW] requested Yahoo mode=%s use_proxy=%s", run_mode, use_proxy)
    status, result, report = _run_creation_flow(
        "yahoo",
        run_mode,
        bool(use_proxy),
        lambda: ninja.create_yahoo_account(
            username=username or "",
            password=password or "",
            first_name=first_name or "",
            last_name=last_name or "",
            birthdate=birthdate or "",
            use_proxy=use_proxy,
        ),
    )
    if bool(use_proxy) and _should_retry_direct_after_proxy_failure(status, report):
        logger.warning("[FIX] provider=yahoo proxy_failure action=retry_direct")
        status, result, report = _run_creation_flow(
            "yahoo",
            run_mode,
            False,
            lambda: ninja.create_yahoo_account(
                username=username or "",
                password=password or "",
                first_name=first_name or "",
                last_name=last_name or "",
                birthdate=birthdate or "",
                use_proxy=False,
            ),
        )
    return status + report, result, get_web_log_text()


def pause_registration():
    """暂停当前注册流程"""
    import requests as _req
    try:
        resp = _req.post("http://localhost:18080/api/register/pause", timeout=3)
        data = resp.json()
        msg = data.get("message", str(data))
        logger.info("[CONTROL] 用户触发暂停: %s", msg)
        return f"⏸ {msg}", get_web_log_text()
    except Exception as e:
        return f"❌ 暂停失败: {e}", get_web_log_text()


def resume_registration():
    """继续已暂停的注册流程"""
    import requests as _req
    try:
        resp = _req.post("http://localhost:18080/api/register/resume", timeout=3)
        data = resp.json()
        msg = data.get("message", str(data))
        logger.info("[CONTROL] 用户触发继续: %s", msg)
        return f"▶ {msg}", get_web_log_text()
    except Exception as e:
        return f"❌ 继续失败: {e}", get_web_log_text()


def stop_registration():
    """停止当前注册流程"""
    import requests as _req
    try:
        resp = _req.post("http://localhost:18080/api/register/stop", timeout=3)
        data = resp.json()
        msg = data.get("message", str(data))
        logger.info("[CONTROL] 用户触发停止: %s", msg)
        return f"⏹ {msg}", get_web_log_text()
    except Exception as e:
        return f"❌ 停止失败: {e}", get_web_log_text()


def get_proxy_status():
    """获取当前代理轮循状态"""
    if not ninja:
        return "未初始化"
    proxies = getattr(ninja, 'proxies', []) or []
    proxy_index = getattr(ninja, '_proxy_index', 0)
    proxy_health = getattr(ninja, '_proxy_health', {})
    total = len(proxies)
    if total == 0:
        return "无代理"
    available = sum(1 for p in proxies if ninja._is_proxy_available(p))
    cooled = total - available
    current = proxies[proxy_index % total] if total > 0 else "无"
    # Mask password in display
    try:
        from ninjemail.proxy_utils import parse_proxy
        pi = parse_proxy(current)
        if pi and pi.has_auth:
            display = f"{pi.protocol}://{pi.username}:***@{pi.host}:{pi.port}"
        else:
            display = current
    except Exception:
        display = current[:30] + "..." if len(current) > 30 else current
    status = f"代理轮循: {proxy_index % total + 1}/{total} | 可用: {available} | 冷却: {cooled}\n当前: {display}"
    return status


# 构建Gradio界面
with gr.Blocks(title="Ninjemail 邮箱自动注册") as demo:
    gr.Markdown("""
    # 📧 Ninjemail 邮箱自动注册工具
    
    自动化创建 Gmail / Outlook / Yahoo 邮箱账户
    """)

    gr.Markdown("### 统一执行日志")
    root_cause_view = gr.Textbox(label="当前根因 / 下一步", value=get_root_cause_text(), lines=5, interactive=False)
    log_view = gr.Textbox(label="所有步骤 / 服务检测 / 阻碍点日志", value=get_web_log_text(), lines=22, interactive=False)
    with gr.Row():
        refresh_log_btn = gr.Button("刷新日志")
        clear_log_btn = gr.Button("清空日志")
    refresh_log_btn.click(get_root_cause_and_logs, outputs=[root_cause_view, log_view], queue=False)
    clear_log_btn.click(clear_root_cause_and_logs, outputs=[root_cause_view, log_view], queue=False)
    log_timer = gr.Timer(value=1.0, active=True)
    log_timer.tick(get_root_cause_and_logs, outputs=[root_cause_view, log_view], queue=False)
    account_created_payload = gr.JSON(visible=False)
    account_created_result = gr.JSON(visible=False)
    account_created_payload.change(
        save_outlook_account_from_extension,
        inputs=account_created_payload,
        outputs=account_created_result,
        api_name="ninjemail_account_created",
        queue=False,
    )
    oauth_exchange_payload = gr.JSON(visible=False)
    oauth_exchange_result = gr.JSON(visible=False)
    oauth_exchange_payload.change(
        exchange_outlook_oauth_code_from_extension,
        inputs=oauth_exchange_payload,
        outputs=oauth_exchange_result,
        api_name="ninjemail_oauth_code_exchange",
        queue=False,
    )
    account_candidate_payload = gr.JSON(visible=False)
    account_candidate_result = gr.JSON(visible=False)
    account_candidate_payload.change(
        save_outlook_account_candidate_from_extension,
        inputs=account_candidate_payload,
        outputs=account_candidate_result,
        api_name="ninjemail_account_candidate",
        queue=False,
    )
    export_three_credential_payload = gr.JSON(visible=False)
    export_three_credential_result = gr.JSON(visible=False)
    export_three_credential_payload.change(
        export_three_credentials_from_extension,
        inputs=export_three_credential_payload,
        outputs=export_three_credential_result,
        api_name="ninjemail_export_three_credentials",
        queue=False,
    )
    open_credential_dir_payload = gr.JSON(visible=False)
    open_credential_dir_result = gr.JSON(visible=False)
    open_credential_dir_payload.change(
        open_credential_output_dir_from_extension,
        inputs=open_credential_dir_payload,
        outputs=open_credential_dir_result,
        api_name="ninjemail_open_credential_output_dir",
        queue=False,
    )
    credential_clear_payload = gr.JSON(visible=False)
    credential_clear_result = gr.JSON(visible=False)
    credential_clear_payload.change(
        clear_previous_outlook_credentials_from_extension,
        inputs=credential_clear_payload,
        outputs=credential_clear_result,
        api_name="ninjemail_clear_previous_credentials",
        queue=False,
    )
    credential_status_payload = gr.JSON(visible=False)
    credential_status_result = gr.JSON(visible=False)
    credential_status_payload.change(
        check_outlook_credential_from_extension,
        inputs=credential_status_payload,
        outputs=credential_status_result,
        api_name="ninjemail_credential_status",
        queue=False,
    )
    credential_validate_payload = gr.JSON(visible=False)
    credential_validate_result = gr.JSON(visible=False)
    credential_validate_payload.change(
        validate_outlook_credentials_from_extension,
        inputs=credential_validate_payload,
        outputs=credential_validate_result,
        api_name="ninjemail_validate_credentials",
        queue=False,
    )
    auxiliary_pick_payload = gr.JSON(visible=False)
    auxiliary_pick_result = gr.JSON(visible=False)
    auxiliary_code_payload = gr.JSON(visible=False)
    auxiliary_code_result = gr.JSON(visible=False)
    auxiliary_pick_payload.change(
        auxiliary_mailbox_pick_from_extension,
        inputs=auxiliary_pick_payload,
        outputs=auxiliary_pick_result,
        api_name="ninjemail_auxiliary_mailbox_pick",
        queue=False,
    )
    auxiliary_code_payload.change(
        auxiliary_mailbox_code_from_extension,
        inputs=auxiliary_code_payload,
        outputs=auxiliary_code_result,
        api_name="ninjemail_auxiliary_mailbox_code",
        queue=False,
    )
    sms_diagnostics_payload = gr.JSON(visible=False)
    sms_diagnostics_result = gr.JSON(visible=False)
    sms_numbers_payload = gr.JSON(visible=False)
    sms_numbers_result = gr.JSON(visible=False)
    sms_messages_payload = gr.JSON(visible=False)
    sms_messages_result = gr.JSON(visible=False)
    sms_diagnostics_payload.change(
        sms_diagnostics_for_extension,
        inputs=sms_diagnostics_payload,
        outputs=sms_diagnostics_result,
        api_name="ninjemail_sms_diagnostics",
        queue=False,
    )
    sms_numbers_payload.change(
        sms_numbers_for_extension,
        inputs=sms_numbers_payload,
        outputs=sms_numbers_result,
        api_name="ninjemail_sms_numbers",
        queue=False,
    )
    sms_messages_payload.change(
        sms_messages_for_extension,
        inputs=sms_messages_payload,
        outputs=sms_messages_result,
        api_name="ninjemail_sms_messages",
        queue=False,
    )

    # ── 代理管理 API（供浏览器插件调用） ──
    proxy_load_payload = gr.JSON(visible=False)
    proxy_load_result = gr.JSON(visible=False)
    proxy_load_payload.change(
        proxy_load_for_extension,
        inputs=proxy_load_payload,
        outputs=proxy_load_result,
        api_name="ninjemail_proxy_load",
        queue=False,
    )
    proxy_save_payload = gr.JSON(visible=False)
    proxy_save_result = gr.JSON(visible=False)
    proxy_save_payload.change(
        proxy_save_for_extension,
        inputs=proxy_save_payload,
        outputs=proxy_save_result,
        api_name="ninjemail_proxy_save",
        queue=False,
    )
    proxy_check_payload = gr.JSON(visible=False)
    proxy_check_result = gr.JSON(visible=False)
    proxy_check_payload.change(
        proxy_check_for_extension,
        inputs=proxy_check_payload,
        outputs=proxy_check_result,
        api_name="ninjemail_proxy_check",
        queue=False,
    )

    with gr.Tab("⚙️ 全局配置"):
        gr.Markdown("### 基础设置")
        with gr.Row():
            browser = gr.Dropdown(
                choices=["chrome", "edge", "brave", "chromium", "vivaldi", "thorium", "opera", "ungoogled", "cent", "360", "qq", "sogou", "maxthon", "yandex", "srware", "slimjet"],
                value=INITIAL_CONFIG.get("browser") or "chrome",
                label="浏览器",
            )
            use_auto_proxy = gr.Checkbox(
                label="初始化时允许自动代理",
                value=bool(INITIAL_CONFIG.get("auto_proxy", False)),
            )
            run_mode = gr.Dropdown(
                choices=RUN_MODES,
                value="probe",
                label="执行模式",
            )
        
        gr.Markdown("### 代理池")
        persistent_browser_profile = gr.Checkbox(
            label="使用普通浏览器持久会话",
            value=bool(INITIAL_CONFIG.get("persistent_browser_profile", False)),
        )
        gr.Markdown("### Ninjemail 浏览器插件")
        with gr.Row():
            ninjemail_extension_enabled = gr.Checkbox(
                label="加载 Ninjemail 内置插件",
                value=_initial_ninjemail_extension_enabled(),
            )
            ninjemail_extension_path = gr.Textbox(
                label="内置插件目录",
                value=_initial_ninjemail_extension_path(),
                interactive=False,
            )
            check_ninjemail_extension_btn = gr.Button("检测 Ninjemail 插件")
        proxy_api_key = gr.Textbox(
            label="GetFreeProxy API Key（可选）",
            placeholder="可留空；公开 GitHub 代理源无需 Key",
            type="password",
            value=_config_section("proxy").get("api_key", "") or "",
        )
        proxy_webshare_token = gr.Textbox(
            label="Webshare API Token（可选）",
            placeholder="Webshare 免费账户 Token；未填写时跳过",
            type="password",
            value=_config_section("proxy").get("webshare_token", "") or "",
        )
        proxy_list = gr.TextArea(
            label="代理列表（每行一个）",
            placeholder="http://ip:port 或 http://user:pass@ip:port",
            lines=6,
            value=_initial_proxy_text(),
        )
        with gr.Row():
            fetch_proxy_btn = gr.Button("获取免费代理")
            check_proxy_btn = gr.Button("检测代理")
            stable_proxy_btn = gr.Button("三轮复测稳定代理")
        
        gr.Markdown("### 验证码服务")
        gr.Markdown(f"真实创建可用验证码 provider: `{', '.join(REAL_CAPTCHA_SERVICES)}`；其他 provider 只用于诊断。")
        with gr.Row():
            captcha_service = gr.Dropdown(
                choices=["", *DIAGNOSTIC_CAPTCHA_SERVICES],
                value=_config_section("captcha").get("primary") or _config_section("captcha").get("provider") or "",
                label="验证码服务"
            )
            captcha_key = gr.Textbox(
                label="API密钥",
                placeholder="API 型服务填写 Key；本地型可留空",
                type="password",
                value=_config_section("captcha").get("api_key", "") or "",
            )
            captcha_local_url = gr.Textbox(
                label="本地服务 URL",
                placeholder="例如 http://127.0.0.1:8889",
                value=_config_section("captcha").get("local_url", "") or "",
            )
        check_captcha_btn = gr.Button("检测验证码服务")
        
        gr.Markdown("### 短信服务")
        gr.Markdown(f"真实创建可用短信 provider: `{', '.join(REAL_SMS_SERVICES)}`；公共免费接码页面只用于诊断，不能当作指定验证码接收链路。")
        with gr.Row():
            sms_service = gr.Dropdown(
                choices=["", *DIAGNOSTIC_SMS_SERVICES],
                value=_config_section("sms").get("primary") or _config_section("sms").get("provider") or "",
                label="短信服务"
            )
            sms_user = gr.Textbox(
                label="用户名 / 设备 ID",
                placeholder="getsmscode 用户名，或 TextBee 设备 ID",
                value=_config_section("sms").get("user", "") or "",
            )
            sms_token = gr.Textbox(
                label="API Token",
                placeholder="Token 型服务填写",
                type="password",
                value=_config_section("sms").get("token", "") or "",
            )
            sms_phone = gr.Textbox(
                label="自有手机号",
                placeholder="TextBee/SMSGate 用你的 Android 手机号，例如 +15551234567",
                value=_config_section("sms").get("phone_number", "") or "",
            )
        with gr.Row():
            sms_base_url = gr.Textbox(
                label="Base URL（可选）",
                placeholder="TextBee 可留空；SMSGate 填 http://手机IP:8080",
                value=_config_section("sms").get("base_url", "") or "",
            )
            sms_country = gr.Textbox(
                label="国家/地区",
                value=_config_section("sms").get("country", "") or "USA",
                placeholder="USA / us / UK 等",
            )
        check_sms_btn = gr.Button("检测短信服务")
        
        with gr.Row():
            auto_config_btn = gr.Button("实测更多服务并更新配置")
            probe_network_btn = gr.Button("双通道网络实测")
            check_config_btn = gr.Button("dry-run 检查配置")
            save_config_btn = gr.Button("保存当前配置")
            reload_config_btn = gr.Button("重新加载配置")
            init_btn = gr.Button("🚀 初始化 Ninjemail", variant="primary")
        init_output = gr.Textbox(label="当前执行结果", value=_initial_status(), lines=5, interactive=False)
        health_table = gr.Dataframe(
            headers=["类别", "Provider", "状态", "需要Key", "路由", "延迟ms", "数量", "原因"],
            datatype=["str", "str", "str", "str", "str", "str", "str", "str"],
            label="服务健康表",
            value=_rows_from_config(INITIAL_CONFIG),
            interactive=False,
            wrap=True,
        )

        fetch_proxy_btn.click(
            fetch_free_proxy_ui,
            inputs=[proxy_api_key, proxy_webshare_token],
            outputs=[proxy_list, init_output, health_table, log_view],
        )

        check_proxy_btn.click(
            check_proxy_ui,
            inputs=[proxy_list],
            outputs=[proxy_list, init_output, health_table, log_view],
        )

        stable_proxy_btn.click(
            stable_proxy_ui,
            inputs=[proxy_list],
            outputs=[proxy_list, init_output, health_table, log_view],
        )

        check_captcha_btn.click(
            check_captcha_ui,
            inputs=[captcha_service, captcha_key, captcha_local_url],
            outputs=[init_output, health_table, log_view],
        )

        check_sms_btn.click(
            check_sms_ui,
            inputs=[sms_service, sms_user, sms_token, sms_phone, sms_base_url, sms_country],
            outputs=[init_output, health_table, log_view],
        )

        check_ninjemail_extension_btn.click(
            check_ninjemail_extension_ui,
            outputs=[init_output, log_view],
        )

        probe_network_btn.click(
            probe_network_routes_ui,
            outputs=[health_table, log_view],
        )

        auto_config_btn.click(
            auto_configure_free_services_ui,
            inputs=[browser, proxy_api_key, proxy_webshare_token, sms_country],
            outputs=[
                proxy_list,
                captcha_service,
                captcha_key,
                captcha_local_url,
                sms_service,
                sms_user,
                sms_token,
                sms_phone,
                sms_base_url,
                sms_country,
                init_output,
                health_table,
                log_view,
            ],
        )

        check_config_btn.click(
            dry_run_config,
            inputs=[
                captcha_service,
                captcha_key,
                captcha_local_url,
                sms_service,
                sms_user,
                sms_token,
                sms_phone,
                sms_base_url,
                sms_country,
                use_auto_proxy,
                proxy_list,
            ],
            outputs=[init_output, log_view],
        )

        save_config_btn.click(
            save_current_config,
            inputs=[
                browser,
                use_auto_proxy,
                persistent_browser_profile,
                ninjemail_extension_enabled,
                proxy_list,
                proxy_api_key,
                proxy_webshare_token,
                captcha_service,
                captcha_key,
                captcha_local_url,
                sms_service,
                sms_user,
                sms_token,
                sms_phone,
                sms_base_url,
                sms_country,
            ],
            outputs=[init_output, proxy_list, health_table, log_view],
        )

        reload_config_btn.click(
            reload_current_config,
            outputs=[
                browser,
                use_auto_proxy,
                persistent_browser_profile,
                ninjemail_extension_enabled,
                proxy_list,
                proxy_api_key,
                proxy_webshare_token,
                captcha_service,
                captcha_key,
                captcha_local_url,
                sms_service,
                sms_user,
                sms_token,
                sms_phone,
                sms_base_url,
                sms_country,
                init_output,
                health_table,
                log_view,
            ],
        )
        
        init_btn.click(
            init_ninjemail,
            inputs=[browser, captcha_service, captcha_key, sms_service, sms_user, sms_token, sms_phone, sms_base_url, use_auto_proxy, persistent_browser_profile, ninjemail_extension_enabled, proxy_list],
            outputs=[init_output, log_view]
        )
    
    with gr.Tab("📧 Outlook / Hotmail"):
        gr.Markdown("### 创建 Outlook 或 Hotmail 账户")
        with gr.Row():
            outlook_username = gr.Textbox(label="用户名", placeholder="留空则自动生成")
            outlook_password = gr.Textbox(label="密码", placeholder="留空则自动生成", type="password")
        with gr.Row():
            outlook_first = gr.Textbox(label="名字", placeholder="留空则自动生成")
            outlook_last = gr.Textbox(label="姓氏", placeholder="留空则自动生成")
        with gr.Row():
            outlook_country = gr.Textbox(label="国家", placeholder="如: USA, CN 等")
            outlook_birth = gr.Textbox(label="出生日期", placeholder="格式: MM-DD-YYYY")
        outlook_proxy = gr.Checkbox(label="使用代理", value=True)
        
        with gr.Row():
            outlook_btn = gr.Button("创建 Outlook 账户", variant="primary")
            outlook_hotmail_btn = gr.Button("创建 Hotmail 账户")
        
        gr.Markdown("### 流程控制")
        with gr.Row():
            pause_btn = gr.Button("⏸ 暂停")
            resume_btn = gr.Button("▶ 继续")
            stop_btn = gr.Button("⏹ 停止")
        control_status = gr.Textbox(label="控制状态", interactive=False, value="")
        proxy_status_view = gr.Textbox(label="代理轮循状态", interactive=False, value="无代理", lines=2)
        refresh_proxy_btn = gr.Button("刷新代理状态")
        
        outlook_status = gr.Textbox(label="状态", interactive=False)
        outlook_result = gr.Textbox(label="账户信息", lines=3, interactive=False)
        
        outlook_btn.click(
            create_outlook,
            inputs=[outlook_username, outlook_password, outlook_first, outlook_last, outlook_country, outlook_birth, outlook_proxy, run_mode],
            outputs=[outlook_status, outlook_result, log_view]
        )
        
        def create_hotmail(*args):
            return create_outlook(*args, hotmail=True)
        
        outlook_hotmail_btn.click(
            create_hotmail,
            inputs=[outlook_username, outlook_password, outlook_first, outlook_last, outlook_country, outlook_birth, outlook_proxy, run_mode],
            outputs=[outlook_status, outlook_result, log_view]
        )
        
        pause_btn.click(pause_registration, outputs=[control_status, log_view])
        resume_btn.click(resume_registration, outputs=[control_status, log_view])
        stop_btn.click(stop_registration, outputs=[control_status, log_view])
        refresh_proxy_btn.click(get_proxy_status, outputs=[proxy_status_view])
    
    with gr.Tab("📧 Gmail"):
        gr.Markdown("### 创建 Gmail 账户")
        with gr.Row():
            gmail_username = gr.Textbox(label="用户名", placeholder="留空则自动生成")
            gmail_password = gr.Textbox(label="密码", placeholder="留空则自动生成", type="password")
        with gr.Row():
            gmail_first = gr.Textbox(label="名字", placeholder="留空则自动生成")
            gmail_last = gr.Textbox(label="姓氏", placeholder="留空则自动生成")
        gmail_birth = gr.Textbox(label="出生日期", placeholder="格式: MM-DD-YYYY")
        gmail_proxy = gr.Checkbox(label="使用代理", value=True)
        
        gmail_btn = gr.Button("创建 Gmail 账户", variant="primary")
        gmail_status = gr.Textbox(label="状态", interactive=False)
        gmail_result = gr.Textbox(label="账户信息", lines=3, interactive=False)
        
        gmail_btn.click(
            create_gmail,
            inputs=[gmail_username, gmail_password, gmail_first, gmail_last, gmail_birth, gmail_proxy, run_mode],
            outputs=[gmail_status, gmail_result, log_view]
        )
    
    with gr.Tab("📧 Yahoo"):
        gr.Markdown("### 创建 Yahoo 账户")
        with gr.Row():
            yahoo_username = gr.Textbox(label="用户名", placeholder="留空则自动生成")
            yahoo_password = gr.Textbox(label="密码", placeholder="留空则自动生成", type="password")
        with gr.Row():
            yahoo_first = gr.Textbox(label="名字", placeholder="留空则自动生成")
            yahoo_last = gr.Textbox(label="姓氏", placeholder="留空则自动生成")
        yahoo_birth = gr.Textbox(label="出生日期", placeholder="格式: MM-DD-YYYY")
        yahoo_proxy = gr.Checkbox(label="使用代理", value=True)
        
        yahoo_btn = gr.Button("创建 Yahoo 账户", variant="primary")
        yahoo_status = gr.Textbox(label="状态", interactive=False)
        yahoo_result = gr.Textbox(label="账户信息", lines=3, interactive=False)
        
        yahoo_btn.click(
            create_yahoo,
            inputs=[yahoo_username, yahoo_password, yahoo_first, yahoo_last, yahoo_birth, yahoo_proxy, run_mode],
            outputs=[yahoo_status, yahoo_result, log_view]
        )
    
    gr.Markdown("""
    ---
    **使用说明：**
    1. 先在【全局配置】里获取/检测代理、验证码、短信服务
    2. 检查通过后保存当前配置，配置会写入本机 runtime_config.toml
    3. 初始化 Ninjemail 后再转到对应标签页执行后续流程
    4. 基础服务诊断支持更多 provider，创建流程仍沿用原项目已接入的 provider
    """)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=7860, help='Server port')
    parser.add_argument('--share', action='store_true', help='Create public link')
    parser.add_argument('--no-browser', action='store_true', help='Do not open the browser automatically')
    args = parser.parse_args()
    
    demo.launch(
        server_name="127.0.0.1",
        server_port=args.port,
        share=args.share,
        inbrowser=not args.no_browser,
        theme=gr.themes.Soft(),
    )
