from __future__ import annotations

import importlib.util
import json
import logging
import re
import time
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
import toml


logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_CONFIG_PATH = PROJECT_ROOT / "runtime_config.toml"
PROXY_CACHE_PATH = PROJECT_ROOT / "runtime_proxy_cache.toml"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

PROXY_SOURCE_URLS: dict[str, tuple[str, str]] = {
    "proxifly/http": (
        "http",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt",
    ),
    "proxifly/https": (
        "https",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/https/data.txt",
    ),
    "proxifly/socks4": (
        "socks4",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks4/data.txt",
    ),
    "proxifly/socks5": (
        "socks5",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks5/data.txt",
    ),
    "iplocate/http": (
        "http",
        "https://raw.githubusercontent.com/iplocate/free-proxy-list/main/protocols/http.txt",
    ),
    "iplocate/https": (
        "https",
        "https://raw.githubusercontent.com/iplocate/free-proxy-list/main/protocols/https.txt",
    ),
    "iplocate/socks4": (
        "socks4",
        "https://raw.githubusercontent.com/iplocate/free-proxy-list/main/protocols/socks4.txt",
    ),
    "iplocate/socks5": (
        "socks5",
        "https://raw.githubusercontent.com/iplocate/free-proxy-list/main/protocols/socks5.txt",
    ),
    "shiftytr/raw": (
        "http",
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/proxy.txt",
    ),
    "clarketm/raw": (
        "http",
        "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
    ),
    "monosans/socks4": (
        "socks4",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks4.txt",
    ),
    "monosans/socks5": (
        "socks5",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
    ),
    "proxyscrape/http": (
        "http",
        "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
    ),
    "proxyscrape/socks4": (
        "socks4",
        "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks4&timeout=10000&country=all",
    ),
    "proxyscrape/socks5": (
        "socks5",
        "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks5&timeout=10000&country=all",
    ),
    "dpangestuw/http": (
        "http",
        "https://raw.githubusercontent.com/dpangestuw/Free-Proxy/refs/heads/main/http_proxies.txt",
    ),
    "skillter/all": (
        "http",
        "https://raw.githubusercontent.com/Skillter/ProxyGather/refs/heads/master/proxies/working-proxies-all.txt",
    ),
    "proxifly/all": (
        "http",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/all/data.txt",
    ),
    "roosterkid/https": (
        "https",
        "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
    ),
    "zaeem20/http": (
        "http",
        "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/http.txt",
    ),
    "zaeem20/https": (
        "https",
        "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/https.txt",
    ),
    "aliilapro/http": (
        "http",
        "https://raw.githubusercontent.com/ALIILAPRO/Proxy/main/http.txt",
    ),
}


@dataclass
class ServiceCheckResult:
    provider: str
    ok: bool
    status: str
    reason: str
    details: dict[str, Any] = field(default_factory=dict)
    duration_ms: int = 0

    def line(self, category: str) -> str:
        state = "ok" if self.ok else self.status or "fail"
        route = self.details.get("route") if self.details else ""
        latency = self.details.get("route_latency_ms") or self.duration_ms
        route_text = f" route={route}" if route else ""
        latency_text = f" latency_ms={latency}" if latency else ""
        detail = f" details={self.details}" if self.details else ""
        return (
            f"[{category}] provider={self.provider or '<none>'} "
            f"status={state}{route_text}{latency_text} reason={self.reason}{detail}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "ok": self.ok,
            "status": self.status,
            "reason": self.reason,
            "duration_ms": self.duration_ms,
            "details": self.details,
        }


@dataclass
class ProxyCandidate:
    url: str
    source: str = "manual"
    scheme: str = "http"
    host: str = ""
    port: int = 0
    latency_ms: int | None = None
    exit_ip: str = ""
    anonymity: str = "unknown"
    error: str = ""
    source_route: str = ""
    source_latency_ms: int | None = None
    source_status: int | None = None
    checks: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "source": self.source,
            "scheme": self.scheme,
            "host": self.host,
            "port": self.port,
            "latency_ms": self.latency_ms,
            "exit_ip": self.exit_ip,
            "anonymity": self.anonymity,
            "source_route": self.source_route,
            "source_latency_ms": self.source_latency_ms,
            "source_status": self.source_status,
            "checks": self.checks,
        }


class _TextAndLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.links: list[str] = []

    def handle_data(self, data: str) -> None:
        data = data.strip()
        if data:
            self.parts.append(data)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        for key, value in attrs:
            if key.lower() == "href" and value:
                self.links.append(value)

    @property
    def text(self) -> str:
        return "\n".join(self.parts)


@dataclass
class RouteAttempt:
    route: str
    ok: bool
    latency_ms: int
    status_code: int | None = None
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "route": self.route,
            "ok": self.ok,
            "latency_ms": self.latency_ms,
            "status_code": self.status_code,
            "error": self.error,
        }


@dataclass
class ProbeResponse:
    response: requests.Response | None
    route: str
    ok: bool
    latency_ms: int
    attempts: list[RouteAttempt]

    def meta(self) -> dict[str, Any]:
        status_code = self.response.status_code if self.response is not None else None
        return {
            "route": self.route,
            "route_latency_ms": self.latency_ms,
            "http_status": status_code,
            "attempts": [item.to_dict() for item in self.attempts],
        }


def _normalize_proxy_url(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        return ""
    if "://" not in value:
        return f"http://{value}"
    return value


def _parse_windows_proxy_server(proxy_server: str) -> dict[str, str]:
    proxy_server = str(proxy_server or "").strip()
    if not proxy_server:
        return {}
    if "=" not in proxy_server:
        proxy_url = _normalize_proxy_url(proxy_server)
        return {"http": proxy_url, "https": proxy_url}

    values: dict[str, str] = {}
    for part in proxy_server.split(";"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip().lower()
        proxy_url = _normalize_proxy_url(value)
        if key in {"http", "https"} and proxy_url:
            values[key] = proxy_url
    if "http" in values and "https" not in values:
        values["https"] = values["http"]
    if "https" in values and "http" not in values:
        values["http"] = values["https"]
    return values


def read_windows_system_proxy() -> dict[str, Any]:
    if not str(Path.home().drive).endswith(":"):
        return {"enabled": False, "server": "", "proxies": {}}
    try:
        import winreg

        key_path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            try:
                proxy_enable = int(winreg.QueryValueEx(key, "ProxyEnable")[0])
            except OSError:
                proxy_enable = 0
            try:
                proxy_server = str(winreg.QueryValueEx(key, "ProxyServer")[0] or "")
            except OSError:
                proxy_server = ""
            try:
                auto_config_url = str(winreg.QueryValueEx(key, "AutoConfigURL")[0] or "")
            except OSError:
                auto_config_url = ""
        proxies = _parse_windows_proxy_server(proxy_server) if proxy_enable else {}
        return {
            "enabled": bool(proxy_enable and proxies),
            "server": proxy_server,
            "auto_config_url": auto_config_url,
            "proxies": proxies,
        }
    except Exception as exc:
        error = str(exc).replace("\r", " ").replace("\n", " ").strip()[:240]
        return {"enabled": False, "server": "", "proxies": {}, "error": error or type(exc).__name__}


class NetworkProbeClient:
    """Try direct and Windows-system-proxy routes, then use the fastest success."""

    def __init__(self) -> None:
        self.system_proxy = read_windows_system_proxy()

    def refresh(self) -> None:
        self.system_proxy = read_windows_system_proxy()

    def routes(self) -> list[tuple[str, dict[str, str]]]:
        routes: list[tuple[str, dict[str, str]]] = []
        proxies = self.system_proxy.get("proxies") or {}
        if proxies:
            routes.append(("system_proxy", dict(proxies)))
        routes.append(("direct", {}))
        return routes

    def summary(self) -> dict[str, Any]:
        proxies = self.system_proxy.get("proxies") or {}
        return {
            "system_proxy_enabled": bool(self.system_proxy.get("enabled")),
            "system_proxy": self.system_proxy.get("server", ""),
            "system_proxy_http": proxies.get("http", ""),
            "system_proxy_https": proxies.get("https", ""),
            "routes": [name for name, _ in self.routes()],
        }

    def request(self, method: str, url: str, *, timeout: float = 12.0, **kwargs: Any) -> ProbeResponse:
        probes: list[ProbeResponse] = []
        futures = []
        with ThreadPoolExecutor(max_workers=max(1, len(self.routes()))) as executor:
            for route_name, proxies in self.routes():
                futures.append(
                    executor.submit(
                        self._request_once,
                        route_name,
                        proxies,
                        method,
                        url,
                        timeout,
                        kwargs,
                    )
                )
            seen: set[int] = set()
            try:
                for future in as_completed(futures, timeout=max(timeout + 2.0, 4.0)):
                    seen.add(id(future))
                    probe = future.result()
                    probes.append(probe)
            except TimeoutError:
                for future in futures:
                    if id(future) in seen or not future.done():
                        continue
                    try:
                        probes.append(future.result())
                    except Exception:
                        pass
                for future in futures:
                    future.cancel()

        attempts = [
            RouteAttempt(
                route=probe.route,
                ok=probe.ok,
                latency_ms=probe.latency_ms,
                status_code=probe.response.status_code if probe.response is not None else None,
                error=probe.attempts[0].error if probe.response is None and probe.attempts else "",
            )
            for probe in probes
        ]

        successes = [item for item in probes if item.ok and item.response is not None]
        if successes:
            selected = min(successes, key=lambda item: item.latency_ms)
            selected.attempts = attempts
            setattr(selected.response, "probe_meta", selected.meta())
            return selected

        http_failures = [item for item in probes if item.response is not None]
        if http_failures:
            selected = min(http_failures, key=lambda item: item.latency_ms)
            selected.attempts = attempts
            setattr(selected.response, "probe_meta", selected.meta())
            return selected

        errors = "; ".join(f"{item.route}: {item.error or item.status_code}" for item in attempts)
        raise RuntimeError(errors or f"all routes failed for {url}")

    def _request_once(
        self,
        route_name: str,
        proxies: dict[str, str],
        method: str,
        url: str,
        timeout: float,
        kwargs: dict[str, Any],
    ) -> ProbeResponse:
        start = time.perf_counter()
        session = _session()
        try:
            response = session.request(method, url, timeout=timeout, proxies=proxies, **dict(kwargs))
            response.content
            latency_ms = _elapsed_ms(start)
            ok = response.status_code < 400
            probe = ProbeResponse(response, route_name, ok, latency_ms, [])
            return probe
        except Exception as exc:
            latency_ms = _elapsed_ms(start)
            attempt = RouteAttempt(route_name, False, latency_ms, None, _short_error(exc))
            probe = ProbeResponse(None, route_name, False, latency_ms, [attempt])
            return probe


NETWORK = NetworkProbeClient()


def mask_secret(value: str) -> str:
    value = str(value or "")
    if not value:
        return "<empty>"
    if len(value) <= 8:
        return value[:1] + "***" + value[-1:]
    return value[:4] + "***" + value[-4:]


def _session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "*/*"})
    return session


def _elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def _short_error(exc: BaseException) -> str:
    text = str(exc).replace("\r", " ").replace("\n", " ").strip()
    return text[:240] or type(exc).__name__


def _with_scheme(value: str, default_scheme: str = "http") -> str:
    value = value.strip()
    if "://" in value:
        return value
    return f"{default_scheme}://{value}"


def normalize_proxy(raw: str, *, default_scheme: str = "http", source: str = "manual") -> ProxyCandidate | None:
    text = str(raw or "").strip()
    if not text or text.startswith("#"):
        return None
    text = text.split()[0].strip()
    if not text:
        return None

    # Common export format: host:port:user:pass
    colon_parts = text.split(":")
    if "://" not in text and len(colon_parts) == 4 and colon_parts[1].isdigit():
        host, port, user, password = colon_parts
        text = f"{default_scheme}://{user}:{password}@{host}:{port}"
    else:
        text = _with_scheme(text, default_scheme)

    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https", "socks4", "socks5"}:
        return None
    if not parsed.hostname or not parsed.port:
        return None
    url = text
    return ProxyCandidate(
        url=url,
        source=source,
        scheme=parsed.scheme,
        host=parsed.hostname,
        port=parsed.port,
    )


def parse_proxy_lines(raw_proxy_list: str, *, source: str = "manual") -> list[ProxyCandidate]:
    seen: set[str] = set()
    proxies: list[ProxyCandidate] = []
    for line in str(raw_proxy_list or "").splitlines():
        candidate = normalize_proxy(line, source=source)
        if not candidate:
            continue
        key = candidate.url.lower()
        if key in seen:
            continue
        seen.add(key)
        proxies.append(candidate)
    return proxies


def _proxy_mapping(proxy_url: str) -> dict[str, str]:
    return {"http": proxy_url, "https": proxy_url}


def _extract_ip_from_response(response: requests.Response) -> str:
    try:
        data = response.json()
        if isinstance(data, dict):
            for key in ("ip", "origin", "query"):
                value = data.get(key)
                if value:
                    return str(value).split(",")[0].strip()
    except Exception:
        pass
    match = re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", response.text)
    return match.group(0) if match else ""


def validate_proxy(candidate: ProxyCandidate, *, timeout: float = 6.0, target_url: str = "") -> ProxyCandidate:
    start = time.perf_counter()
    session = _session()
    # 优先 HTTP 测试 URL（免费代理大多不支持 HTTPS CONNECT 隧道）
    proto = getattr(candidate, "scheme", "") or ""
    if proto in ("socks4", "socks5"):
        # SOCKS 代理支持 HTTPS，直接用
        urls = [
            "https://api.ipify.org?format=json",
            "https://httpbin.org/ip",
            "https://www.cloudflare.com/cdn-cgi/trace",
        ]
    else:
        # HTTP/HTTPS 代理：先 HTTP，再 HTTPS 作为回退
        urls = [
            "http://api.ipify.org?format=json",
            "http://icanhazip.com",
            "http://httpbin.org/ip",
            "https://api.ipify.org?format=json",
            "https://httpbin.org/ip",
        ]
    last_error = ""
    for test_url in urls:
        try:
            response = session.get(
                test_url,
                proxies=_proxy_mapping(candidate.url),
                timeout=timeout,
            )
            # 收到任何 HTTP 响应都说明代理通道是通的，不因非 2xx 判死
            # 只有连接超时/拒绝/隧道失败才算真正失败
            route_key = urlparse(test_url).netloc
            candidate.checks[route_key] = {"ok": True, "http_status": response.status_code}
            candidate.latency_ms = _elapsed_ms(start)
            candidate.exit_ip = _extract_ip_from_response(response)
            candidate.anonymity = "exit_ip_detected" if candidate.exit_ip else "reachable"
            candidate.error = ""
            if target_url:
                target_key = f"target:{urlparse(target_url).netloc}"
                try:
                    target_response = session.get(
                        target_url,
                        proxies=_proxy_mapping(candidate.url),
                        timeout=timeout,
                        allow_redirects=True,
                        stream=True,
                    )
                    candidate.checks[target_key] = {
                        "ok": 200 <= target_response.status_code < 400,
                        "http_status": target_response.status_code,
                    }
                    if 200 <= target_response.status_code < 400:
                        return candidate
                    candidate.error = f"target_unreachable http_status={target_response.status_code}"
                    return candidate
                except Exception as exc:
                    last_error = _short_error(exc)
                    candidate.checks[target_key] = {"ok": False, "error": last_error}
                    candidate.error = f"target_unreachable: {last_error}"
                    return candidate
            return candidate
        except Exception as exc:
            last_error = _short_error(exc)
            route_key = urlparse(test_url).netloc
            candidate.checks[route_key] = {"ok": False, "error": last_error}
    candidate.error = last_error or "proxy check failed"
    return candidate


def _fetch_proxy_source(name: str, scheme: str, url: str, *, limit_per_source: int) -> tuple[list[ProxyCandidate], str]:
    start = time.perf_counter()
    try:
        probe = NETWORK.request("GET", url, timeout=8)
        response = probe.response
        if response is None:
            raise RuntimeError("no response")
        response.raise_for_status()
        candidates: list[ProxyCandidate] = []
        for line in response.text.splitlines():
            candidate = normalize_proxy(line, default_scheme=scheme, source=name)
            if candidate:
                candidate.source_route = probe.route
                candidate.source_latency_ms = probe.latency_ms
                candidate.source_status = response.status_code
                candidates.append(candidate)
            if len(candidates) >= limit_per_source:
                break
        return (
            candidates,
            f"[PROXY][SOURCE] {name} route={probe.route} status=ok "
            f"latency_ms={probe.latency_ms} fetched={len(candidates)}",
        )
    except Exception as exc:
        return [], f"[PROXY][SOURCE] {name} status=fail latency_ms={_elapsed_ms(start)} fetched=0 error={_short_error(exc)}"


def _fetch_getfreeproxy(api_key: str, *, limit_per_source: int) -> tuple[list[ProxyCandidate], str]:
    if not api_key:
        return [], "[PROXY][SOURCE] getfreeproxy status=missing_key fetched=0 reason=missing_api_key"
    start = time.perf_counter()
    try:
        probe = NETWORK.request(
            "GET",
            "https://api.getfreeproxy.com/v1/proxies",
            params={"protocol": "http", "page": 1},
            headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
            timeout=20,
        )
        response = probe.response
        if response is None:
            raise RuntimeError("no response")
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            rows = data.get("data") or data.get("proxies") or data.get("results") or []
        else:
            rows = data
        candidates: list[ProxyCandidate] = []
        for row in rows:
            if isinstance(row, str):
                raw = row
                scheme = "http"
            elif isinstance(row, dict):
                scheme = str(row.get("protocol") or row.get("type") or "http").lower()
                host = row.get("ip") or row.get("host") or row.get("proxy")
                port = row.get("port")
                raw = str(host or "")
                if port and ":" not in raw.rsplit("@", 1)[-1]:
                    raw = f"{raw}:{port}"
            else:
                continue
            candidate = normalize_proxy(raw, default_scheme=scheme, source="getfreeproxy")
            if candidate:
                candidate.source_route = probe.route
                candidate.source_latency_ms = probe.latency_ms
                candidate.source_status = response.status_code
                candidates.append(candidate)
            if len(candidates) >= limit_per_source:
                break
        return (
            candidates,
            f"[PROXY][SOURCE] getfreeproxy route={probe.route} status=ok "
            f"latency_ms={probe.latency_ms} fetched={len(candidates)}",
        )
    except Exception as exc:
        return [], f"[PROXY][SOURCE] getfreeproxy status=fail latency_ms={_elapsed_ms(start)} fetched=0 error={_short_error(exc)}"


def _fetch_geonode_public(*, limit_per_source: int) -> tuple[list[ProxyCandidate], str]:
    start = time.perf_counter()
    url = "https://proxylist.geonode.com/api/proxy-list"
    try:
        probe = NETWORK.request(
            "GET",
            url,
            params={
                "limit": min(100, max(10, limit_per_source)),
                "page": 1,
                "sort_by": "lastChecked",
                "sort_type": "desc",
                "protocols": "http,https,socks4,socks5",
            },
            timeout=20,
        )
        response = probe.response
        if response is None:
            raise RuntimeError("no response")
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("data", []) if isinstance(payload, dict) else []
        candidates: list[ProxyCandidate] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            host = row.get("ip") or row.get("host")
            port = row.get("port")
            protocols = row.get("protocols") or row.get("protocol") or ["http"]
            if isinstance(protocols, str):
                protocols = [protocols]
            for scheme in protocols:
                candidate = normalize_proxy(f"{host}:{port}", default_scheme=str(scheme), source="geonode/public")
                if not candidate:
                    continue
                candidate.source_route = probe.route
                candidate.source_latency_ms = probe.latency_ms
                candidate.source_status = response.status_code
                candidates.append(candidate)
                break
            if len(candidates) >= limit_per_source:
                break
        return (
            candidates,
            f"[PROXY][SOURCE] geonode/public route={probe.route} status=ok "
            f"latency_ms={probe.latency_ms} fetched={len(candidates)}",
        )
    except Exception as exc:
        return [], f"[PROXY][SOURCE] geonode/public status=fail latency_ms={_elapsed_ms(start)} fetched=0 error={_short_error(exc)}"


def _fetch_webshare(token: str, *, limit_per_source: int) -> tuple[list[ProxyCandidate], str]:
    if not token:
        return [], "[PROXY][SOURCE] webshare status=missing_key fetched=0 reason=missing_api_token"
    start = time.perf_counter()
    try:
        probe = NETWORK.request(
            "GET",
            "https://proxy.webshare.io/api/v2/proxy/list/",
            params={"mode": "direct", "page": 1, "page_size": min(100, max(10, limit_per_source))},
            headers={"Authorization": f"Token {token}", "Accept": "application/json"},
            timeout=20,
        )
        response = probe.response
        if response is None:
            raise RuntimeError("no response")
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("results", []) if isinstance(payload, dict) else []
        candidates: list[ProxyCandidate] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            host = row.get("proxy_address") or row.get("host") or row.get("ip")
            port = row.get("port")
            user = row.get("username") or row.get("user")
            password = row.get("password") or row.get("pass")
            if not host or not port:
                continue
            auth = f"{user}:{password}@" if user and password else ""
            raw = f"{auth}{host}:{port}"
            candidate = normalize_proxy(raw, default_scheme="http", source="webshare")
            if candidate:
                candidate.source_route = probe.route
                candidate.source_latency_ms = probe.latency_ms
                candidate.source_status = response.status_code
                candidates.append(candidate)
            if len(candidates) >= limit_per_source:
                break
        return (
            candidates,
            f"[PROXY][SOURCE] webshare route={probe.route} status=ok "
            f"latency_ms={probe.latency_ms} fetched={len(candidates)}",
        )
    except Exception as exc:
        return [], f"[PROXY][SOURCE] webshare status=fail latency_ms={_elapsed_ms(start)} fetched=0 error={_short_error(exc)}"


def _dedupe_proxies(candidates: list[ProxyCandidate]) -> list[ProxyCandidate]:
    seen: set[str] = set()
    result: list[ProxyCandidate] = []
    for candidate in candidates:
        key = candidate.url.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(candidate)
    return result


def _write_proxy_cache(proxies: list[ProxyCandidate]) -> None:
    payload = {
        "updated_at": int(time.time()),
        "proxies": [proxy.to_dict() for proxy in proxies],
    }
    with PROXY_CACHE_PATH.open("w", encoding="utf-8") as handle:
        toml.dump(payload, handle)


def _read_proxy_cache(max_age_seconds: int = 21600) -> list[ProxyCandidate]:
    try:
        payload = toml.load(PROXY_CACHE_PATH)
        updated_at = int(payload.get("updated_at") or 0)
        if not updated_at or time.time() - updated_at > max_age_seconds:
            return []
        proxies = []
        for row in payload.get("proxies", []):
            candidate = normalize_proxy(str(row.get("url") or ""), source=str(row.get("source") or "cache"))
            if not candidate:
                continue
            candidate.latency_ms = row.get("latency_ms")
            candidate.exit_ip = str(row.get("exit_ip") or "")
            candidate.anonymity = str(row.get("anonymity") or "cached")
            candidate.source_route = str(row.get("source_route") or "cache")
            candidate.source_latency_ms = row.get("source_latency_ms")
            candidate.source_status = row.get("source_status")
            candidate.checks = row.get("checks") or {}
            proxies.append(candidate)
        return proxies
    except Exception:
        return []


def fetch_free_proxies(
    *,
    api_key: str = "",
    webshare_token: str = "",
    max_candidates: int = 96,
    max_working: int = 20,
    workers: int = 24,
) -> tuple[list[ProxyCandidate], list[str]]:
    NETWORK.refresh()
    network = NETWORK.summary()
    logs = [
        "[PROXY][STEP] fetching free proxy candidates",
        (
            "[NETWORK][STEP] "
            f"system_proxy={network.get('system_proxy') or '<none>'} "
            f"routes={','.join(network.get('routes') or [])}"
        ),
    ]
    cached_before = _read_proxy_cache()
    all_candidates: list[ProxyCandidate] = []
    source_limit = max(12, max_candidates // 4)
    source_executor = ThreadPoolExecutor(max_workers=min(8, len(PROXY_SOURCE_URLS) + 3))
    source_futures = [
        source_executor.submit(_fetch_proxy_source, name, scheme, url, limit_per_source=source_limit)
        for name, (scheme, url) in PROXY_SOURCE_URLS.items()
    ]
    if api_key:
        source_futures.append(source_executor.submit(_fetch_getfreeproxy, api_key, limit_per_source=source_limit))
    source_futures.append(source_executor.submit(_fetch_geonode_public, limit_per_source=source_limit))
    if webshare_token:
        source_futures.append(source_executor.submit(_fetch_webshare, webshare_token, limit_per_source=source_limit))
    try:
        for future in as_completed(source_futures, timeout=90):
            candidates, line = future.result()
            all_candidates.extend(candidates)
            logs.append(line)
    except TimeoutError:
        logs.append("[PROXY][SOURCE] source fetch timed out; keeping completed source results only")
    finally:
        for future in source_futures:
            future.cancel()
        source_executor.shutdown(wait=False, cancel_futures=True)

    candidates = _dedupe_proxies(all_candidates)[:max_candidates]
    logs.append(f"[PROXY][STEP] candidates={len(candidates)} begin_health_check")
    if not candidates:
        cached = _read_proxy_cache()
        if cached:
            logs.append(f"[PROXY][CACHE] cache_used=true using_cached={len(cached)}")
            return cached[:max_working], logs
        logs.append("[PROXY][BLOCK] no candidates fetched")
        return [], logs

    working: list[ProxyCandidate] = []
    executor = ThreadPoolExecutor(max_workers=max(1, workers))
    futures = [executor.submit(validate_proxy, candidate) for candidate in candidates]
    try:
        for future in as_completed(futures, timeout=max(15, int(len(candidates) / max(1, workers)) * 14 + 15)):
            checked = future.result()
            if checked.error:
                continue
            working.append(checked)
            logs.append(
                f"[PROXY][OK] source={checked.source} proxy={checked.url} "
                f"source_route={checked.source_route or 'unknown'} "
                f"latency_ms={checked.latency_ms} exit_ip={checked.exit_ip or 'unknown'}"
            )
            if len(working) >= max_working:
                break
    except TimeoutError:
        logs.append("[PROXY][BLOCK] proxy validation timed out; keeping completed results only")
    finally:
        for future in futures:
            future.cancel()
        executor.shutdown(wait=False, cancel_futures=True)

    if working:
        working.sort(key=lambda item: item.latency_ms if item.latency_ms is not None else 999999)
        min_acceptable = min(5, max_working)
        if len(working) < min_acceptable and len(cached_before) > len(working):
            logs.append(
                f"[PROXY][CACHE] fresh_working={len(working)} below_min={min_acceptable} "
                f"cache_used=true using_cached={len(cached_before)}"
            )
            return cached_before[:max_working], logs
        _write_proxy_cache(working)
        logs.append(f"[PROXY][SUMMARY] candidates={len(candidates)} working={len(working)}")
    else:
        cached = _read_proxy_cache()
        if cached:
            logs.append(f"[PROXY][BLOCK] fresh_check_failed cache_used=true using_cached={len(cached)}")
            return cached[:max_working], logs
        logs.append(f"[PROXY][BLOCK] candidates={len(candidates)} working=0")
    return working[:max_working], logs


def check_proxy_list(raw_proxy_list: str, *, max_checks: int = 80, max_working: int = 40) -> tuple[list[ProxyCandidate], list[str]]:
    candidates = parse_proxy_lines(raw_proxy_list)
    logs = [f"[PROXY][STEP] manual_candidates={len(candidates)}"]
    if not candidates:
        logs.append("[PROXY][BLOCK] no proxy configured")
        return [], logs
    working: list[ProxyCandidate] = []
    checked_candidates = candidates[:max_checks]
    executor = ThreadPoolExecutor(max_workers=min(50, max(1, len(checked_candidates))))
    futures = [executor.submit(validate_proxy, candidate) for candidate in checked_candidates]
    try:
        for future in as_completed(futures, timeout=max(15, int(len(checked_candidates) / 8) * 14 + 15)):
            checked = future.result()
            if checked.error:
                logs.append(f"[PROXY][FAIL] proxy={checked.url} reason={checked.error}")
                continue
            working.append(checked)
            logs.append(f"[PROXY][OK] proxy={checked.url} latency_ms={checked.latency_ms} exit_ip={checked.exit_ip or 'unknown'}")
            if len(working) >= max_working:
                break
    except TimeoutError:
        logs.append("[PROXY][BLOCK] proxy validation timed out; keeping completed results only")
    finally:
        for future in futures:
            future.cancel()
        executor.shutdown(wait=False, cancel_futures=True)
    if working:
        working.sort(key=lambda item: item.latency_ms if item.latency_ms is not None else 999999)
        _write_proxy_cache(working)
        logs.append(f"[PROXY][SUMMARY] checked={min(len(candidates), max_checks)} working={len(working)}")
    else:
        logs.append("[PROXY][BLOCK] no working proxy")
    return working[:max_working], logs


def build_stable_proxy_pool(
    raw_proxy_list: str,
    *,
    rounds: int = 3,
    required_success_rate: float = 1.0,
    max_checks: int = 30,
    workers: int = 16,
    target_url: str = "",
    target_name: str = "",
) -> tuple[list[ProxyCandidate], list[str], dict[str, Any]]:
    candidates = parse_proxy_lines(raw_proxy_list)
    candidates = _dedupe_proxies(candidates)[:max_checks]
    logs = [
        (
            "[PROXY][STABLE] "
            f"candidates={len(candidates)} rounds={rounds} "
            f"required_success_rate={required_success_rate} "
            f"target={target_name or urlparse(target_url).netloc or '<generic>'}"
        )
    ]
    if not candidates:
        summary = {
            "candidates": 0,
            "rounds": rounds,
            "target_url": target_url,
            "target_name": target_name,
            "stable_count": 0,
            "results": [],
        }
        logs.append("[PROXY][BLOCK] no_stable_proxy reason=no_candidates")
        return [], logs, summary

    success_counts: dict[str, int] = {candidate.url: 0 for candidate in candidates}
    latency_totals: dict[str, int] = {candidate.url: 0 for candidate in candidates}
    last_success: dict[str, ProxyCandidate] = {}
    failures: dict[str, list[str]] = {candidate.url: [] for candidate in candidates}

    for round_index in range(1, max(1, rounds) + 1):
        round_candidates = [
            normalize_proxy(candidate.url, default_scheme=candidate.scheme, source=candidate.source) or candidate
            for candidate in candidates
        ]
        round_ok = 0
        executor = ThreadPoolExecutor(max_workers=min(max(1, workers), max(1, len(round_candidates))))
        futures = [
            executor.submit(validate_proxy, candidate, timeout=5.0, target_url=target_url)
            for candidate in round_candidates
        ]
        try:
            for future in as_completed(futures, timeout=max(20, int(len(round_candidates) / 6) * 12 + 20)):
                checked = future.result()
                if checked.error:
                    failures.setdefault(checked.url, []).append(checked.error)
                    continue
                round_ok += 1
                success_counts[checked.url] = success_counts.get(checked.url, 0) + 1
                latency_totals[checked.url] = latency_totals.get(checked.url, 0) + int(checked.latency_ms or 0)
                last_success[checked.url] = checked
        except TimeoutError:
            logs.append(f"[PROXY][STABLE] round={round_index} status=timeout")
        finally:
            for future in futures:
                future.cancel()
            executor.shutdown(wait=False, cancel_futures=True)
        logs.append(f"[PROXY][STABLE] round={round_index} ok={round_ok}/{len(round_candidates)}")

    required_successes = max(1, int(rounds * required_success_rate + 0.999999))
    stable: list[ProxyCandidate] = []
    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        ok_count = success_counts.get(candidate.url, 0)
        avg_latency = int(latency_totals.get(candidate.url, 0) / ok_count) if ok_count else None
        row = {
            "url": candidate.url,
            "successes": ok_count,
            "rounds": rounds,
            "success_rate": round(ok_count / max(1, rounds), 3),
            "avg_latency_ms": avg_latency,
            "last_error": (failures.get(candidate.url) or [""])[-1],
        }
        rows.append(row)
        if ok_count >= required_successes and candidate.url in last_success:
            item = last_success[candidate.url]
            item.latency_ms = avg_latency if avg_latency is not None else item.latency_ms
            item.checks["stable"] = {
                "successes": ok_count,
                "rounds": rounds,
                "success_rate": row["success_rate"],
            }
            stable.append(item)

    stable.sort(key=lambda item: item.latency_ms if item.latency_ms is not None else 999999)
    summary = {
        "candidates": len(candidates),
        "rounds": rounds,
        "required_success_rate": required_success_rate,
        "target_url": target_url,
        "target_name": target_name,
        "stable_count": len(stable),
        "results": rows,
    }
    if stable:
        logs.append(f"[PROXY][STABLE] stable_count={len(stable)}")
        for item in stable:
            stable_info = item.checks.get("stable", {})
            logs.append(
                "[PROXY][STABLE][OK] "
                f"proxy={item.url} successes={stable_info.get('successes')}/{rounds} "
                f"target={target_name or urlparse(target_url).netloc or '<generic>'} "
                f"latency_ms={item.latency_ms} exit_ip={item.exit_ip or 'unknown'}"
            )
    else:
        logs.append("[PROXY][BLOCK] no_stable_proxy reason=no_proxy_passed_all_rounds")
    return stable, logs, summary


def render_proxy_list(proxies: list[ProxyCandidate]) -> str:
    return "\n".join(proxy.url for proxy in proxies)


def _http_json_or_text(method: str, url: str, **kwargs: Any) -> tuple[int, Any]:
    response = NETWORK.request(method, url, **kwargs).response
    if response is None:
        raise RuntimeError(f"no response from {url}")
    status = response.status_code
    try:
        return status, response.json()
    except Exception:
        return status, response.text


def _http_json_or_text_with_meta(method: str, url: str, **kwargs: Any) -> tuple[int, Any, dict[str, Any]]:
    probe = NETWORK.request(method, url, **kwargs)
    if probe.response is None:
        raise RuntimeError(f"no response from {url}")
    response = probe.response
    status = response.status_code
    try:
        payload: Any = response.json()
    except Exception:
        payload = response.text
    return status, payload, probe.meta()


def _response_meta(response: requests.Response) -> dict[str, Any]:
    meta = getattr(response, "probe_meta", None)
    return dict(meta or {})


def _apply_meta(details: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    merged = dict(details or {})
    for key in ("route", "route_latency_ms", "http_status", "attempts"):
        if key in meta:
            merged[key] = meta[key]
    return merged


def _check_client_key_balance(
    provider: str,
    api_key: str,
    url: str,
    start: float,
    *,
    balance_keys: tuple[str, ...] = ("balance",),
) -> ServiceCheckResult:
    if not api_key:
        return ServiceCheckResult(provider, False, "missing_key", f"缺少 {provider} API Key", duration_ms=_elapsed_ms(start))
    status, payload, meta = _http_json_or_text_with_meta(
        "POST",
        url,
        json={"clientKey": api_key},
        timeout=20,
    )
    ok = status == 200 and isinstance(payload, dict) and payload.get("errorId", 0) in {0, "0"}
    details = _apply_meta({"http_status": status}, meta)
    if isinstance(payload, dict):
        for key in balance_keys:
            if key in payload:
                details[key] = payload.get(key)
        if payload.get("errorCode"):
            details["errorCode"] = payload.get("errorCode")
    reason = "balance endpoint ok" if ok else f"balance endpoint failed: {payload}"
    return ServiceCheckResult(provider, ok, "ok" if ok else "fail", reason, details, _elapsed_ms(start))


def _check_ocr_space(api_key: str, start: float) -> ServiceCheckResult:
    key = str(api_key or "").strip() or "helloworld"
    status, payload, meta = _http_json_or_text_with_meta(
        "GET",
        "https://api.ocr.space/parse/imageurl",
        params={
            "apikey": key,
            "url": "https://dl.a9t9.com/ocr/solarcell.jpg",
            "language": "eng",
            "isOverlayRequired": "false",
        },
        timeout=25,
    )
    details = _apply_meta({"http_status": status, "demo_key": not bool(api_key)}, meta)
    parsed_text = ""
    if isinstance(payload, dict):
        results = payload.get("ParsedResults") or []
        if results and isinstance(results[0], dict):
            parsed_text = str(results[0].get("ParsedText") or "")
        details["is_errored"] = bool(payload.get("IsErroredOnProcessing"))
        details["parsed_chars"] = len(parsed_text)
        if payload.get("ErrorMessage"):
            details["error"] = payload.get("ErrorMessage")
    ok = status == 200 and bool(parsed_text.strip()) and not details.get("is_errored")
    reason = "OCR.Space demo OCR endpoint ok" if ok else f"OCR.Space endpoint failed: {payload}"
    return ServiceCheckResult("ocr_space", ok, "ok" if ok else "fail", reason, details, _elapsed_ms(start))


def check_captcha_service(provider: str, api_key: str = "", local_url: str = "") -> ServiceCheckResult:
    provider = str(provider or "").strip().lower()
    start = time.perf_counter()
    if not provider:
        return ServiceCheckResult(provider="", ok=False, status="block", reason="未选择验证码服务")

    try:
        if provider == "capsolver":
            return _check_client_key_balance(
                provider,
                api_key,
                "https://api.capsolver.com/getBalance",
                start,
                balance_keys=("balance",),
            )

        if provider == "nopecha":
            params = {"key": api_key} if api_key else {}
            status, payload, meta = _http_json_or_text_with_meta(
                "GET",
                "https://api.nopecha.com/v1/status",
                params=params,
                timeout=20,
            )
            ok = (
                status == 200
                and isinstance(payload, dict)
                and not payload.get("code")
                and str(payload.get("status", "")).lower() in {"active", "ok", ""}
                and float(payload.get("credit") or payload.get("quota") or 0) > 0
            )
            details = {}
            if isinstance(payload, dict):
                details = {key: payload.get(key) for key in ("plan", "status", "credit", "quota", "ttl", "duration") if key in payload}
            details = _apply_meta(details, meta)
            reason = "free status endpoint ok" if ok and not api_key else ("status endpoint ok" if ok else f"status endpoint failed: {payload}")
            return ServiceCheckResult(provider, ok, "ok" if ok else "fail", reason, details, _elapsed_ms(start))

        if provider == "capmonster":
            return _check_client_key_balance(provider, api_key, "https://api.capmonster.cloud/getBalance", start)

        if provider == "anti_captcha":
            return _check_client_key_balance(provider, api_key, "https://api.anti-captcha.com/getBalance", start)

        if provider in {"2captcha", "twocaptcha"}:
            return _check_client_key_balance("2captcha", api_key, "https://api.2captcha.com/getBalance", start)

        if provider == "yescaptcha":
            return _check_client_key_balance(provider, api_key, "https://api.yescaptcha.com/getBalance", start)

        if provider == "ocr_space":
            return _check_ocr_space(api_key, start)

        if provider == "ddddocr":
            if local_url:
                return _check_local_http_service(provider, local_url, start)
            spec = importlib.util.find_spec("ddddocr")
            ok = spec is not None
            reason = "ddddocr package installed" if ok else "未安装 ddddocr；可选安装后再检查"
            return ServiceCheckResult(provider, ok, "ok" if ok else "missing_component", reason, duration_ms=_elapsed_ms(start))

        if provider in {"buster", "local_solver"}:
            if provider == "local_solver" and not local_url:
                local_url = "http://127.0.0.1:8889"
            if local_url:
                return _check_local_http_service(provider, local_url, start)
            return ServiceCheckResult(provider, False, "missing_component", "需要提供本地服务 URL 或先安装/启动对应组件", duration_ms=_elapsed_ms(start))

        return ServiceCheckResult(provider, False, "block", f"未知验证码 provider: {provider}", duration_ms=_elapsed_ms(start))
    except Exception as exc:
        return ServiceCheckResult(provider, False, "fail", _short_error(exc), duration_ms=_elapsed_ms(start))


def _check_local_http_service(provider: str, local_url: str, start: float) -> ServiceCheckResult:
    base = str(local_url or "").strip().rstrip("/")
    if not base:
        return ServiceCheckResult(provider, False, "block", "缺少本地服务 URL", duration_ms=_elapsed_ms(start))
    for suffix in ("/health", "/"):
        try:
            response = _session().get(base + suffix, timeout=5)
            if response.status_code < 500:
                return ServiceCheckResult(
                    provider,
                    True,
                    "ok",
                    f"local service reachable at {base + suffix}",
                    {"http_status": response.status_code},
                    _elapsed_ms(start),
                )
        except Exception:
            continue
    return ServiceCheckResult(provider, False, "unreachable", f"本地服务不可达: {base}", duration_ms=_elapsed_ms(start))


def _parse_html(html: str) -> _TextAndLinkParser:
    parser = _TextAndLinkParser()
    parser.feed(html or "")
    return parser


def _extract_phone_candidates(value: Any) -> list[str]:
    raw = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    phones: list[str] = []
    for match in re.finditer(r"(?:\+\d[\d\s().-]{7,}\d|\b\d{10,15}\b)", raw):
        text = match.group(0)
        prefix = "+" if text.strip().startswith("+") else ""
        digits = re.sub(r"\D", "", text)
        if 10 <= len(digits) <= 15:
            phones.append(prefix + digits)
    seen: set[str] = set()
    result: list[str] = []
    for phone in phones:
        key = phone.lstrip("+")
        if key in seen:
            continue
        seen.add(key)
        result.append(phone)
    return result


SMS_CODE_PATTERN = re.compile(r"(?<!\d)(\d{4,8})(?!\d)")


FREE_PUBLIC_SMS_BASE_URLS: dict[str, str] = {
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


def _phone_digits(value: str) -> str:
    return re.sub(r"\D", "", str(value or ""))


def _message_paths_for_provider(provider: str, country: str) -> tuple[str, list[str]]:
    provider = str(provider or "").strip().lower()
    if provider == "receive_sms_live":
        return "https://receive-smss.live", [f"sms/{_country_for_receive_sms_live(country)}"]
    if provider == "quackr":
        return "https://quackr.io", ["temporary-numbers", "free-sms-numbers", ""]
    if provider == "anonymsms":
        return "https://anonymsms.com", [_country_slug(country), ""]
    if provider == "sms24_me":
        return "https://sms24.me", [f"en/countries/{_country_iso2(country)}", "en"]
    if provider == "receive_sms_cc":
        return "https://receive-sms.cc", [_country_slug(country), ""]
    if provider == "sms_receive_free":
        return "https://www.free-sms-receive.com", [_country_slug(country), ""]
    if provider == "numtapper":
        return "https://www.numtapper.com", ["free-sms", ""]
    if provider == "receivesms_it":
        return "https://receivesms.it.com", ["", "receive-sms-online"]
    if provider == "temporary_phone_number_io":
        return "https://temporary-phone-number.io", ["", f"country/{_country_iso2(country)}/"]
    if provider == "freephonenum":
        return "https://freephonenum.com", [_country_iso2(country), ""]
    if provider == "receive_sms_online_info":
        return "https://receive-sms-online.info", ["", _country_slug(country)]
    if provider == "sms_online_co":
        return "https://sms-online.co", ["", _country_iso2(country)]
    if provider == "mytrashmobile":
        return "https://www.mytrashmobile.com", ["", "receive-sms-online"]
    if provider == "receive_sms_io":
        return "https://receive-sms.io", ["temporary-numbers/usa/", ""]
    if provider == "receive_sms_free_cc":
        return "https://receive-sms-free.cc", [""]
    if provider == "temporary_phone_number_com":
        return "https://temporary-phone-number.com", [""]
    if provider == "receivefreesms_net":
        return "https://receivefreesms.net", [""]
    if provider == "freeonlinephone_org":
        return "https://www.freeonlinephone.org", [""]
    if provider == "receivesms_net":
        return "https://www.receivesms.net", [""]
    if provider == "receivesmsonline_net":
        return "https://www.receivesmsonline.net", [""]
    if provider == "sms24_info":
        return "https://sms24.info", ["en/numbers", ""]
    return FREE_PUBLIC_SMS_BASE_URLS.get(provider, ""), [""]


def _sms_number_items(
    provider: str,
    *,
    base_url: str,
    source_url: str,
    parser: _TextAndLinkParser,
    limit: int,
) -> list[dict[str, Any]]:
    phones = _extract_phone_candidates(parser.text + "\n" + "\n".join(parser.links))
    links = [urljoin(base_url.rstrip("/") + "/", link) for link in parser.links if str(link or "").strip()]
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for phone in phones:
        digits = _phone_digits(phone)
        if not digits or digits in seen:
            continue
        seen.add(digits)
        message_url = ""
        for link in links:
            link_digits = _phone_digits(link)
            if digits in link_digits:
                message_url = link
                break
        items.append(
            {
                "provider": provider,
                "phone": phone,
                "digits": digits,
                "message_url": message_url or source_url,
                "source_url": source_url,
                "free": True,
            }
        )
        if len(items) >= limit:
            break
    return items


def list_public_sms_numbers(
    provider: str,
    *,
    base_url: str = "",
    country: str = "USA",
    limit: int = 30,
) -> dict[str, Any]:
    provider = str(provider or "").strip().lower()
    start = time.perf_counter()
    if provider not in FREE_PUBLIC_SMS_BASE_URLS:
        return {"ok": False, "provider": provider, "status": "unsupported", "reason": "provider is not a free public SMS source", "numbers": []}
    default_base, paths = _message_paths_for_provider(provider, country)
    base = _normalize_api_base(base_url, default_base)
    last_reason = ""
    last_meta: dict[str, Any] = {}
    for path in paths:
        url = urljoin(base.rstrip("/") + "/", str(path or "").lstrip("/"))
        try:
            probe = NETWORK.request("GET", url, timeout=20)
            response = probe.response
            if response is None:
                last_reason = f"{url} no response"
                last_meta = probe.meta()
                continue
            last_meta = probe.meta()
            if response.status_code >= 400:
                last_reason = f"{url} HTTP {response.status_code}"
                continue
            parser = _parse_html(response.text)
            numbers = _sms_number_items(provider, base_url=base, source_url=url, parser=parser, limit=max(1, int(limit or 30)))
            if numbers:
                return {
                    "ok": True,
                    "provider": provider,
                    "status": "ok",
                    "reason": "numbers_loaded",
                    "numbers": numbers,
                    "count": len(numbers),
                    "url": url,
                    "route": probe.route,
                    "latency_ms": probe.latency_ms,
                    "duration_ms": _elapsed_ms(start),
                }
            last_reason = f"{url} page readable but no phone numbers parsed"
        except Exception as exc:
            last_reason = _short_error(exc)
    return {
        "ok": False,
        "provider": provider,
        "status": "fail",
        "reason": last_reason or "no numbers parsed",
        "numbers": [],
        "count": 0,
        "route": last_meta.get("route", ""),
        "latency_ms": last_meta.get("route_latency_ms", 0),
        "duration_ms": _elapsed_ms(start),
    }


def _extract_sms_codes(text: str, phone: str = "") -> list[str]:
    phone_digits = _phone_digits(phone)
    codes: list[str] = []
    for match in SMS_CODE_PATTERN.finditer(str(text or "")):
        code = match.group(1)
        if phone_digits and code in phone_digits:
            continue
        if len(code) == 4 and 1900 <= int(code) <= 2099:
            continue
        if code not in codes:
            codes.append(code)
    return codes


def _sms_message_items(parts: list[str], *, phone: str = "", limit: int = 30) -> tuple[list[dict[str, str]], list[str]]:
    clean_parts = [re.sub(r"\s+", " ", str(part or "")).strip() for part in parts]
    clean_parts = [part for part in clean_parts if 2 <= len(part) <= 500]
    messages: list[dict[str, str]] = []
    seen: set[str] = set()
    all_codes: list[str] = []
    for index, part in enumerate(clean_parts):
        codes = _extract_sms_codes(part, phone)
        if not codes:
            continue
        window = " ".join(clean_parts[max(0, index - 2): min(len(clean_parts), index + 3)])
        key = window[:500]
        if key in seen:
            continue
        seen.add(key)
        for code in _extract_sms_codes(window, phone):
            if code not in all_codes:
                all_codes.append(code)
        messages.append({"text": key, "code": codes[0]})
        if len(messages) >= limit:
            break
    if not messages:
        for part in clean_parts[:limit]:
            messages.append({"text": part, "code": ""})
    return messages, all_codes


def fetch_public_sms_messages(
    provider: str,
    *,
    phone: str = "",
    message_url: str = "",
    base_url: str = "",
    country: str = "USA",
    limit: int = 30,
) -> dict[str, Any]:
    provider = str(provider or "").strip().lower()
    start = time.perf_counter()
    selected_number: dict[str, Any] = {}
    if not message_url:
        listing = list_public_sms_numbers(provider, base_url=base_url, country=country, limit=80)
        if not listing.get("ok"):
            return {**listing, "messages": [], "codes": [], "code": ""}
        target_digits = _phone_digits(phone)
        for item in listing.get("numbers", []) or []:
            if not target_digits or _phone_digits(str(item.get("phone") or "")) == target_digits:
                selected_number = item
                message_url = str(item.get("message_url") or "")
                phone = str(item.get("phone") or phone or "")
                break
    if not message_url:
        return {"ok": False, "provider": provider, "status": "missing_number", "reason": "no message url for selected number", "messages": [], "codes": [], "code": ""}
    try:
        probe = NETWORK.request("GET", message_url, timeout=20)
        response = probe.response
        if response is None:
            raise RuntimeError("no response")
        if response.status_code >= 400:
            return {
                "ok": False,
                "provider": provider,
                "status": "fail",
                "reason": f"message page HTTP {response.status_code}",
                "phone": phone,
                "message_url": message_url,
                "messages": [],
                "codes": [],
                "code": "",
                "route": probe.route,
                "latency_ms": probe.latency_ms,
            }
        parser = _parse_html(response.text)
        messages, codes = _sms_message_items(parser.parts, phone=phone, limit=max(1, int(limit or 30)))
        return {
            "ok": True,
            "provider": provider,
            "status": "ok",
            "reason": "messages_loaded" if messages else "message page loaded",
            "phone": phone,
            "selected_number": selected_number,
            "message_url": message_url,
            "messages": messages,
            "codes": codes,
            "code": codes[0] if codes else "",
            "route": probe.route,
            "latency_ms": probe.latency_ms,
            "duration_ms": _elapsed_ms(start),
        }
    except Exception as exc:
        return {
            "ok": False,
            "provider": provider,
            "status": "fail",
            "reason": _short_error(exc),
            "phone": phone,
            "message_url": message_url,
            "messages": [],
            "codes": [],
            "code": "",
            "duration_ms": _elapsed_ms(start),
        }


def _country_for_shelex(country: str) -> str:
    text = str(country or "USA").strip()
    aliases = {"us": "USA", "usa": "USA", "united states": "USA", "uk": "UK", "gb": "UK"}
    return aliases.get(text.lower(), text or "USA")


def _country_for_receive_sms_live(country: str) -> str:
    text = str(country or "us").strip().lower()
    aliases = {"usa": "us", "united states": "us", "america": "us", "uk": "gb", "united kingdom": "gb"}
    return aliases.get(text, text or "us")


def _country_slug(country: str, default: str = "united-states") -> str:
    text = str(country or "").strip().lower()
    aliases = {
        "": default,
        "us": "united-states",
        "usa": "united-states",
        "united states": "united-states",
        "america": "united-states",
        "uk": "united-kingdom",
        "gb": "united-kingdom",
        "united kingdom": "united-kingdom",
        "ca": "canada",
        "au": "australia",
        "de": "germany",
        "fr": "france",
        "es": "spain",
        "it": "italy",
        "nl": "netherlands",
        "se": "sweden",
    }
    return aliases.get(text, text.replace(" ", "-") or default)


def _country_iso2(country: str, default: str = "us") -> str:
    text = str(country or "").strip().lower()
    aliases = {
        "": default,
        "usa": "us",
        "united states": "us",
        "america": "us",
        "uk": "uk",
        "united kingdom": "uk",
        "great britain": "uk",
        "canada": "ca",
        "australia": "au",
        "germany": "de",
        "france": "fr",
        "spain": "es",
        "italy": "it",
        "netherlands": "nl",
        "sweden": "se",
    }
    return aliases.get(text, text[:2] or default)


def _normalize_api_base(base_url: str, default: str) -> str:
    return str(base_url or default).strip().rstrip("/")


def _check_free_otp_api(base_url: str, country: str, start: float) -> ServiceCheckResult:
    base = _normalize_api_base(base_url, "https://otp-api.shelex.dev/api")
    country_name = _country_for_shelex(country)
    urls = [
        f"{base}/list/{country_name}",
        f"{base}/numbers?country={country_name}",
    ]
    last_payload: Any = None
    last_meta: dict[str, Any] = {}
    for url in urls:
        status, payload, meta = _http_json_or_text_with_meta("GET", url, timeout=25)
        last_payload = payload
        last_meta = meta
        if status != 200:
            continue
        phones = _extract_phone_candidates(payload)
        if not phones:
            continue
        first_phone = phones[0].lstrip("+")
        sms_urls = [
            f"{base}/{country_name}/{first_phone}?ago=30m",
            f"{base}/sms?number=%2B{first_phone}&ago=30m",
        ]
        message_readable = False
        message_meta: dict[str, Any] = {}
        for sms_url in sms_urls:
            try:
                sms_status, _payload, message_meta = _http_json_or_text_with_meta("GET", sms_url, timeout=15)
                if sms_status == 200:
                    message_readable = True
                    break
            except Exception:
                continue
        return ServiceCheckResult(
            "free_otp_api",
            True,
            "ok",
            "号码列表可读，最近短信端点可访问" if message_readable else "号码列表可读，短信端点暂无可读结果",
            _apply_meta({"numbers": len(phones), "sample": phones[0]}, message_meta or meta),
            _elapsed_ms(start),
        )
    return ServiceCheckResult("free_otp_api", False, "fail", f"未读到号码列表: {last_payload}", _apply_meta({}, last_meta), _elapsed_ms(start))


def _check_receive_sms_live(base_url: str, country: str, start: float) -> ServiceCheckResult:
    base = _normalize_api_base(base_url, "https://receive-smss.live")
    country_code = _country_for_receive_sms_live(country)
    list_url = urljoin(base + "/", f"sms/{country_code}")
    probe = NETWORK.request("GET", list_url, timeout=25)
    response = probe.response
    if response is None:
        raise RuntimeError("no response")
    response.raise_for_status()
    parser = _parse_html(response.text)
    phones = _extract_phone_candidates(parser.text)
    links = [urljoin(base + "/", link) for link in parser.links if f"/sms/{country_code}/" in link]
    if not phones and links:
        phones = _extract_phone_candidates("\n".join(links))
    if not phones:
        return ServiceCheckResult("receive_sms_live", False, "fail", "号码页面可访问，但未解析到号码", _apply_meta({"url": list_url}, probe.meta()), _elapsed_ms(start))
    details: dict[str, Any] = _apply_meta({"numbers": len(phones), "sample": phones[0], "url": list_url}, probe.meta())
    if links:
        detail_probe = NETWORK.request("GET", links[0], timeout=20)
        if detail_probe.response is not None:
            details["message_page_status"] = detail_probe.response.status_code
            details["message_page_route"] = detail_probe.route
    return ServiceCheckResult("receive_sms_live", True, "ok", "免费公共号码列表可读", details, _elapsed_ms(start))


def _check_quackr(base_url: str, token: str, start: float) -> ServiceCheckResult:
    base = _normalize_api_base(base_url, "https://quackr.io")
    if token:
        # Quackr documents API access for rental-number customers. Keep this as a
        # non-mutating reachability check; exact customer endpoints can vary.
        probe = NETWORK.request(
            "GET",
            urljoin(base + "/", "api"),
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=20,
        )
        response = probe.response
        if response is None:
            raise RuntimeError("no response")
        ok = response.status_code < 500
        return ServiceCheckResult("quackr", ok, "ok" if ok else "fail", f"API endpoint HTTP {response.status_code}", _apply_meta({"url": urljoin(base + "/", "api")}, probe.meta()), _elapsed_ms(start))

    for path in ("temporary-numbers", "free-sms-numbers", ""):
        url = urljoin(base + "/", path)
        try:
            probe = NETWORK.request("GET", url, timeout=12)
            response = probe.response
            if response is None:
                continue
            if response.status_code >= 400:
                continue
            parser = _parse_html(response.text)
            phones = _extract_phone_candidates(parser.text)
            if phones:
                details = _apply_meta({"numbers": len(phones), "sample": phones[0], "url": url}, probe.meta())
                return ServiceCheckResult("quackr", True, "ok", "公共号码页面可读", details, _elapsed_ms(start))
        except Exception:
            continue
    return ServiceCheckResult("quackr", False, "block", "Quackr API 需要租号客户 Key；公共页面未解析到号码", duration_ms=_elapsed_ms(start))


def _check_public_sms_page(
    provider: str,
    base_url: str,
    country: str,
    paths: list[str],
    start: float,
) -> ServiceCheckResult:
    base = _normalize_api_base(base_url, "")
    last_reason = ""
    last_meta: dict[str, Any] = {}
    for path in paths:
        url = urljoin(base + "/", path.lstrip("/"))
        try:
            probe = NETWORK.request("GET", url, timeout=20)
            response = probe.response
            if response is None:
                last_reason = f"{url} no response"
                last_meta = probe.meta()
                continue
            last_meta = probe.meta()
            if response.status_code >= 400:
                last_reason = f"{url} HTTP {response.status_code}"
                continue
            parser = _parse_html(response.text)
            phones = _extract_phone_candidates(parser.text + "\n" + "\n".join(parser.links))
            if not phones:
                last_reason = f"{url} 页面可访问但未解析到号码"
                continue
            details: dict[str, Any] = _apply_meta({"numbers": len(phones), "sample": phones[0], "url": url}, probe.meta())
            number_links = [urljoin(base + "/", link) for link in parser.links if phones[0].lstrip("+") in link]
            if number_links:
                try:
                    detail_probe = NETWORK.request("GET", number_links[0], timeout=10)
                    if detail_probe.response is not None:
                        details["message_page_status"] = detail_probe.response.status_code
                        details["message_page_route"] = detail_probe.route
                except Exception:
                    pass
            return ServiceCheckResult(provider, True, "ok", "免费公共号码页面可读", details, _elapsed_ms(start))
        except Exception as exc:
            last_reason = _short_error(exc)
    return ServiceCheckResult(provider, False, "fail", last_reason or "公共号码页面不可读", _apply_meta({}, last_meta), _elapsed_ms(start))


def _check_anonymsms(base_url: str, country: str, start: float) -> ServiceCheckResult:
    slug = _country_slug(country)
    return _check_public_sms_page("anonymsms", base_url or "https://anonymsms.com", country, [slug, ""], start)


def _check_sms24_me(base_url: str, country: str, start: float) -> ServiceCheckResult:
    iso2 = _country_iso2(country)
    return _check_public_sms_page("sms24_me", base_url or "https://sms24.me", country, [f"en/countries/{iso2}", "en"], start)


def _check_receive_sms_cc(base_url: str, country: str, start: float) -> ServiceCheckResult:
    slug = _country_slug(country)
    return _check_public_sms_page("receive_sms_cc", base_url or "https://receive-sms.cc", country, [slug, ""], start)


def _check_temp_number_com(base_url: str, country: str, start: float) -> ServiceCheckResult:
    return _check_public_sms_page("temp_number_com", base_url or "https://temp-number.com", country, ["from/platform/google", "from/platform/microsoft", ""], start)


def _check_receivesms_fast(base_url: str, country: str, start: float) -> ServiceCheckResult:
    return _check_public_sms_page("receivesms_fast", base_url or "https://receivesmsfast.com", country, ["service/GOOGLE", "service/MICROSOFT", ""], start)


def _check_receive_sms_online(base_url: str, country: str, start: float) -> ServiceCheckResult:
    slug = _country_slug(country)
    return _check_public_sms_page("receive_sms_online", base_url or "https://receive-sms-online.com", country, [slug, ""], start)


def _check_sms_receive_free(base_url: str, country: str, start: float) -> ServiceCheckResult:
    # The old sms-receive-free.com domain no longer resolves in this network.
    # free-sms-receive.com is the live public-number site with the same intent.
    slug = _country_slug(country)
    return _check_public_sms_page("sms_receive_free", base_url or "https://www.free-sms-receive.com", country, [slug, ""], start)


def _check_temp_sms_api(base_url: str, country: str, start: float) -> ServiceCheckResult:
    slug = _country_slug(country)
    return _check_public_sms_page("temp_sms_api", base_url or "https://temp-sms-api.com", country, [slug, ""], start)


def _check_sms_number_verifier(base_url: str, country: str, start: float) -> ServiceCheckResult:
    slug = _country_slug(country)
    return _check_public_sms_page("sms_number_verifier", base_url or "https://sms-number-verifier.com", country, [slug, ""], start)


def _check_numtapper(base_url: str, country: str, start: float) -> ServiceCheckResult:
    return _check_public_sms_page("numtapper", base_url or "https://www.numtapper.com", country, ["free-sms", ""], start)


def _check_receivesms_it(base_url: str, country: str, start: float) -> ServiceCheckResult:
    return _check_public_sms_page("receivesms_it", base_url or "https://receivesms.it.com", country, ["", "receive-sms-online"], start)


def _check_temporary_phone_number_io(base_url: str, country: str, start: float) -> ServiceCheckResult:
    return _check_public_sms_page(
        "temporary_phone_number_io",
        base_url or "https://temporary-phone-number.io",
        country,
        ["", f"country/{_country_iso2(country)}/"],
        start,
    )


def _check_freephonenum(base_url: str, country: str, start: float) -> ServiceCheckResult:
    return _check_public_sms_page("freephonenum", base_url or "https://freephonenum.com", country, [_country_iso2(country), ""], start)


def _check_receive_sms_online_info(base_url: str, country: str, start: float) -> ServiceCheckResult:
    return _check_public_sms_page("receive_sms_online_info", base_url or "https://receive-sms-online.info", country, ["", _country_slug(country)], start)


def _check_sms_online_co(base_url: str, country: str, start: float) -> ServiceCheckResult:
    return _check_public_sms_page("sms_online_co", base_url or "https://sms-online.co", country, ["", _country_iso2(country)], start)


def _check_mytrashmobile(base_url: str, country: str, start: float) -> ServiceCheckResult:
    return _check_public_sms_page("mytrashmobile", base_url or "https://www.mytrashmobile.com", country, ["", "receive-sms-online"], start)


def _check_textbee(base_url: str, token: str, device_id: str, start: float) -> ServiceCheckResult:
    if not token:
        return ServiceCheckResult("textbee", False, "missing_token", "缺少 TextBee API Key", duration_ms=_elapsed_ms(start))
    base = _normalize_api_base(base_url, "https://api.textbee.dev")
    if not base.endswith("/api/v1"):
        base = base.rstrip("/") + "/api/v1"
    endpoint = f"{base}/gateway/devices"
    if device_id:
        endpoint = f"{endpoint}/{device_id}"
    probe = NETWORK.request(
        "GET",
        endpoint,
        headers={"x-api-key": token, "Authorization": f"Bearer {token}", "Accept": "application/json"},
        timeout=20,
    )
    response = probe.response
    if response is None:
        raise RuntimeError("no response")
    ok = response.status_code == 200
    reason = "设备/API 可访问" if ok else f"HTTP {response.status_code}: {response.text[:180]}"
    return ServiceCheckResult("textbee", ok, "ok" if ok else "fail", reason, _apply_meta({"url": endpoint}, probe.meta()), _elapsed_ms(start))


def _check_vendel(base_url: str, token: str, start: float) -> ServiceCheckResult:
    if not token:
        return ServiceCheckResult("vendel", False, "missing_token", "缺少 Vendel API Key", duration_ms=_elapsed_ms(start))
    base = _normalize_api_base(base_url, "https://app.vendel.cc")
    for path in ("api/devices", "api/sms/inbound", "api/sms"):
        endpoint = urljoin(base + "/", path)
        probe = NETWORK.request(
            "GET",
            endpoint,
            headers={"X-API-Key": token, "Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=20,
        )
        response = probe.response
        if response is None:
            continue
        if response.status_code in {200, 204}:
            return ServiceCheckResult("vendel", True, "ok", "Vendel API 可访问", _apply_meta({"url": endpoint}, probe.meta()), _elapsed_ms(start))
        if response.status_code in {401, 403}:
            return ServiceCheckResult("vendel", False, "fail", f"鉴权失败 HTTP {response.status_code}", _apply_meta({"url": endpoint}, probe.meta()), _elapsed_ms(start))
    return ServiceCheckResult("vendel", False, "fail", "未找到可用的 Vendel 健康检查端点", duration_ms=_elapsed_ms(start))


def _check_smsgate(base_url: str, user: str, token: str, start: float) -> ServiceCheckResult:
    if not base_url:
        return ServiceCheckResult("smsgate", False, "missing_base_url", "缺少 SMSGate Local Server Base URL", duration_ms=_elapsed_ms(start))
    if not user or not token:
        return ServiceCheckResult("smsgate", False, "missing_token", "缺少 SMSGate Basic Auth 用户名或密码", duration_ms=_elapsed_ms(start))
    base = _normalize_api_base(base_url, "").rstrip("/")
    endpoint = f"{base}/inbox"
    probe = NETWORK.request(
        "GET",
        endpoint,
        params={"type": "SMS", "limit": 1, "offset": 0},
        auth=(user, token),
        timeout=20,
    )
    response = probe.response
    if response is None:
        raise RuntimeError("no response")
    ok = response.status_code == 200
    details = _apply_meta({"url": endpoint, "http_status": response.status_code}, probe.meta())
    reason = "SMSGate inbox endpoint ok" if ok else f"HTTP {response.status_code}: {response.text[:180]}"
    return ServiceCheckResult("smsgate", ok, "ok" if ok else "fail", reason, details, _elapsed_ms(start))


def _check_smspool(token: str, start: float) -> ServiceCheckResult:
    if not token:
        return ServiceCheckResult("smspool", False, "missing_token", "缺少 SMSPool API Token", duration_ms=_elapsed_ms(start))
    status, payload, meta = _http_json_or_text_with_meta(
        "POST",
        "https://api.smspool.net/request/balance",
        data={"key": token},
        timeout=20,
    )
    ok = status == 200 and isinstance(payload, dict) and "balance" in payload
    details = _apply_meta({"http_status": status}, meta)
    if isinstance(payload, dict) and "balance" in payload:
        details["balance"] = payload.get("balance")
    return ServiceCheckResult("smspool", ok, "ok" if ok else "fail", "balance endpoint ok" if ok else f"balance endpoint failed: {payload}", details, _elapsed_ms(start))


def _check_fivesim(token: str, start: float) -> ServiceCheckResult:
    if not token:
        return ServiceCheckResult("5sim", False, "missing_token", "缺少 5sim API Token", duration_ms=_elapsed_ms(start))
    status, payload, meta = _http_json_or_text_with_meta(
        "GET",
        "https://5sim.net/v1/user/profile",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        timeout=20,
    )
    ok = status == 200 and isinstance(payload, dict) and "balance" in payload
    details = _apply_meta({"http_status": status}, meta)
    if isinstance(payload, dict) and "balance" in payload:
        details["balance"] = payload.get("balance")
    return ServiceCheckResult("5sim", ok, "ok" if ok else "fail", "profile endpoint ok" if ok else f"profile endpoint failed: {payload}", details, _elapsed_ms(start))


def _check_getsmscode(user: str, token: str, start: float) -> ServiceCheckResult:
    if not token:
        return ServiceCheckResult("getsmscode", False, "missing_token", "缺少 GetsmsCode Token/API Key", duration_ms=_elapsed_ms(start))
    urls = [f"https://getsmscode.net/api/{token}/getBalance"]
    last_meta: dict[str, Any] = {}
    for url in urls:
        status, payload, last_meta = _http_json_or_text_with_meta("GET", url, timeout=20)
        ok = status == 200 and (
            (isinstance(payload, dict) and "balance" in payload)
            or (isinstance(payload, str) and "balance" in payload.lower())
        )
        if ok:
            return ServiceCheckResult("getsmscode", True, "ok", "balance endpoint ok", _apply_meta({"http_status": status}, last_meta), _elapsed_ms(start))
    if user:
        return ServiceCheckResult(
            "getsmscode",
            False,
            "block",
            "旧版 api.getsmscode.com 需要租号动作才能深检；已确认 user/token 已填写，但未执行扣费动作",
            _apply_meta({}, last_meta),
            duration_ms=_elapsed_ms(start),
        )
    return ServiceCheckResult("getsmscode", False, "fail", "balance endpoint failed", _apply_meta({}, last_meta), _elapsed_ms(start))


def check_sms_service(
    provider: str,
    *,
    user: str = "",
    token: str = "",
    base_url: str = "",
    country: str = "",
) -> ServiceCheckResult:
    provider = str(provider or "").strip().lower()
    start = time.perf_counter()
    if not provider:
        return ServiceCheckResult("", False, "block", "未选择短信服务")
    try:
        if provider == "free_otp_api":
            return _check_free_otp_api(base_url, country, start)
        if provider == "receive_sms_live":
            return _check_receive_sms_live(base_url, country, start)
        if provider == "quackr":
            return _check_quackr(base_url, token, start)
        if provider == "anonymsms":
            return _check_anonymsms(base_url, country, start)
        if provider == "sms24_me":
            return _check_sms24_me(base_url, country, start)
        if provider == "receive_sms_cc":
            return _check_receive_sms_cc(base_url, country, start)
        if provider == "temp_number_com":
            return _check_temp_number_com(base_url, country, start)
        if provider == "receivesms_fast":
            return _check_receivesms_fast(base_url, country, start)
        if provider == "receive_sms_online":
            return _check_receive_sms_online(base_url, country, start)
        if provider == "sms_receive_free":
            return _check_sms_receive_free(base_url, country, start)
        if provider == "temp_sms_api":
            return _check_temp_sms_api(base_url, country, start)
        if provider == "sms_number_verifier":
            return _check_sms_number_verifier(base_url, country, start)
        if provider == "numtapper":
            return _check_numtapper(base_url, country, start)
        if provider == "receivesms_it":
            return _check_receivesms_it(base_url, country, start)
        if provider == "temporary_phone_number_io":
            return _check_temporary_phone_number_io(base_url, country, start)
        if provider == "freephonenum":
            return _check_freephonenum(base_url, country, start)
        if provider == "receive_sms_online_info":
            return _check_receive_sms_online_info(base_url, country, start)
        if provider == "sms_online_co":
            return _check_sms_online_co(base_url, country, start)
        if provider == "mytrashmobile":
            return _check_mytrashmobile(base_url, country, start)
        if provider in FREE_PUBLIC_SMS_BASE_URLS:
            result = list_public_sms_numbers(provider, base_url=base_url, country=country, limit=30)
            numbers = result.get("numbers") or []
            details = {
                "url": result.get("url") or FREE_PUBLIC_SMS_BASE_URLS.get(provider, ""),
                "route": result.get("route") or "",
                "route_latency_ms": result.get("latency_ms") or 0,
                "numbers": len(numbers),
                "sample": (numbers[0] or {}).get("phone") if numbers else "",
            }
            return ServiceCheckResult(
                provider,
                bool(result.get("ok")),
                "ok" if result.get("ok") else str(result.get("status") or "fail"),
                str(result.get("reason") or ""),
                details,
                int(result.get("duration_ms") or _elapsed_ms(start)),
            )
        if provider == "textbee":
            return _check_textbee(base_url, token, user, start)
        if provider == "smsgate":
            return _check_smsgate(base_url, user, token, start)
        if provider == "vendel":
            return _check_vendel(base_url, token, start)
        if provider == "smspool":
            return _check_smspool(token, start)
        if provider == "5sim":
            return _check_fivesim(token, start)
        if provider == "getsmscode":
            return _check_getsmscode(user, token, start)
        return ServiceCheckResult(provider, False, "block", f"未知短信 provider: {provider}", duration_ms=_elapsed_ms(start))
    except Exception as exc:
        return ServiceCheckResult(provider, False, "fail", _short_error(exc), duration_ms=_elapsed_ms(start))


def load_runtime_config() -> dict[str, Any]:
    if not RUNTIME_CONFIG_PATH.exists():
        return {}
    return toml.load(RUNTIME_CONFIG_PATH)


def save_runtime_config(config: dict[str, Any]) -> Path:
    payload = dict(config)
    payload["updated_at"] = int(time.time())
    with RUNTIME_CONFIG_PATH.open("w", encoding="utf-8") as handle:
        toml.dump(payload, handle)
    return RUNTIME_CONFIG_PATH


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def probe_network_routes(urls: list[str] | None = None) -> list[dict[str, Any]]:
    NETWORK.refresh()
    targets = urls or [
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt",
        "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
        "https://receive-smss.live/sms/us",
        "https://quackr.io/temporary-numbers",
    ]
    rows: list[dict[str, Any]] = []
    for url in targets:
        try:
            probe = NETWORK.request("HEAD", url, timeout=8)
            if probe.response is not None and probe.response.status_code in {403, 405}:
                probe = NETWORK.request("GET", url, timeout=8)
            meta = probe.meta()
            rows.append(
                {
                    "url": url,
                    "ok": bool(probe.response is not None and probe.response.status_code < 500),
                    "route": meta.get("route", ""),
                    "latency_ms": meta.get("route_latency_ms", 0),
                    "http_status": meta.get("http_status", 0),
                    "attempts": meta.get("attempts", []),
                }
            )
        except Exception as exc:
            rows.append({"url": url, "ok": False, "route": "", "latency_ms": 0, "http_status": 0, "error": _short_error(exc)})
    return rows


def auto_configure_free_services(
    *,
    browser: str = "chrome",
    country: str = "USA",
    proxy_api_key: str = "",
    webshare_token: str = "",
) -> tuple[dict[str, Any], list[str]]:
    NETWORK.refresh()
    route_checks = probe_network_routes()
    logs: list[str] = ["[AUTO][STEP] start free service discovery"]
    for item in route_checks:
        logs.append(
            "[NETWORK][CHECK] "
            f"url={item.get('url')} status={'ok' if item.get('ok') else 'fail'} "
            f"route={item.get('route') or '<none>'} latency_ms={item.get('latency_ms') or 0} "
            f"http_status={item.get('http_status') or 0} reason={item.get('error', '')}"
        )

    proxies, proxy_logs = fetch_free_proxies(
        api_key=proxy_api_key,
        webshare_token=webshare_token,
        max_candidates=128,
        max_working=30,
        workers=24,
    )
    logs.extend(proxy_logs)
    stable_proxies, stable_proxy_logs, stable_proxy_summary = build_stable_proxy_pool(
        render_proxy_list(proxies),
        rounds=3,
        required_success_rate=1.0,
        max_checks=min(30, len(proxies)),
        workers=16,
    )
    logs.extend(stable_proxy_logs)

    captcha_candidates = [
        ("nopecha", "", ""),
        ("ddddocr", "", ""),
        ("ocr_space", "", ""),
        ("capsolver", "", ""),
        ("capmonster", "", ""),
        ("anti_captcha", "", ""),
        ("2captcha", "", ""),
        ("yescaptcha", "", ""),
    ]
    captcha_results: list[ServiceCheckResult] = []
    for provider, key, local_url in captcha_candidates:
        result = check_captcha_service(provider, key, local_url)
        captcha_results.append(result)
        logs.append(result.line("CAPTCHA"))
    captcha_priority = ["nopecha", "ddddocr", "ocr_space", "capsolver", "capmonster", "anti_captcha", "2captcha", "yescaptcha"]
    captcha_primary = next(
        (item for name in captcha_priority for item in captcha_results if item.provider == name and item.ok),
        None,
    )
    captcha_ok_results = [item for item in captcha_results if item.ok]

    sms_candidates = [
        ("receive_sms_live", "", "", "https://receive-smss.live"),
        ("quackr", "", "", "https://quackr.io"),
        ("anonymsms", "", "", "https://anonymsms.com"),
        ("sms24_me", "", "", "https://sms24.me"),
        ("receive_sms_cc", "", "", "https://receive-sms.cc"),
        ("sms_receive_free", "", "", "https://www.free-sms-receive.com"),
        ("numtapper", "", "", "https://www.numtapper.com"),
        ("receivesms_it", "", "", "https://receivesms.it.com"),
        ("temporary_phone_number_io", "", "", "https://temporary-phone-number.io"),
        ("freephonenum", "", "", "https://freephonenum.com"),
        ("receive_sms_online_info", "", "", "https://receive-sms-online.info"),
        ("sms_online_co", "", "", "https://sms-online.co"),
        ("mytrashmobile", "", "", "https://www.mytrashmobile.com"),
        ("receive_sms_io", "", "", "https://receive-sms.io"),
        ("receive_sms_free_cc", "", "", "https://receive-sms-free.cc"),
        ("temporary_phone_number_com", "", "", "https://temporary-phone-number.com"),
        ("receivefreesms_net", "", "", "https://receivefreesms.net"),
        ("freeonlinephone_org", "", "", "https://www.freeonlinephone.org"),
        ("receivesms_net", "", "", "https://www.receivesms.net"),
        ("receivesmsonline_net", "", "", "https://www.receivesmsonline.net"),
        ("sms24_info", "", "", "https://sms24.info"),
        ("smspool", "", "", ""),
        ("5sim", "", "", ""),
        ("getsmscode", "", "", ""),
        ("textbee", "", "", ""),
        ("smsgate", "", "", ""),
        ("vendel", "", "", ""),
    ]
    sms_results: list[ServiceCheckResult] = []
    for provider, user, token, base_url in sms_candidates:
        result = check_sms_service(provider, user=user, token=token, base_url=base_url, country=country)
        sms_results.append(result)
        logs.append(result.line("SMS"))
    sms_primary = next((item for item in sms_results if item.ok), None)

    config = {
        "browser": browser,
        "auto_proxy": False,
        "network": NETWORK.summary(),
        "proxy": {
            "provider": "free_proxy_pool",
            "primary": stable_proxies[0].url if stable_proxies else "",
            "api_key": proxy_api_key or "",
            "webshare_token": webshare_token or "",
            "items": [proxy.url for proxy in stable_proxies],
            "all_items": [proxy.url for proxy in proxies],
            "stable_items": [proxy.url for proxy in stable_proxies],
            "pool": [proxy.to_dict() for proxy in proxies],
            "working": [proxy.to_dict() for proxy in proxies],
            "stable_pool": [proxy.to_dict() for proxy in stable_proxies],
            "stable_summary": stable_proxy_summary,
        },
        "captcha": {
            "primary": captcha_primary.provider if captcha_primary else "",
            "providers": [item.to_dict() for item in captcha_ok_results],
            "provider": captcha_primary.provider if captcha_primary else "",
            "api_key": "",
            "local_url": "",
            "status": captcha_primary.status if captcha_primary else "block",
            "reason": captcha_primary.reason if captcha_primary else "没有免费验证码 provider 通过健康检查",
        },
        "sms": {
            "primary": "",
            "diagnostic_primary": sms_primary.provider if sms_primary else "",
            "providers": [item.to_dict() for item in sms_results],
            "provider": "",
            "real_provider": "smspool",
            "user": "",
            "token": "",
            "base_url": "",
            "diagnostic_base_url": str((sms_primary.details or {}).get("url", "")).split("/sms/", 1)[0] if sms_primary else "",
            "country": country,
            "status": "missing_token",
            "reason": "real creation provider not configured; choose smspool/5sim/getsmscode and fill token",
            "diagnostic_status": sms_primary.status if sms_primary else "block",
            "diagnostic_reason": sms_primary.reason if sms_primary else "没有免费短信 provider 通过健康检查",
        },
        "diagnostics": {
            "last_checked_at": _now_iso(),
            "network_route_checks": route_checks,
            "captcha": [item.to_dict() for item in captcha_results],
            "sms": [item.to_dict() for item in sms_results],
            "proxy": {
                "working_count": len(proxies),
                "stable_count": len(stable_proxies),
                "pool": [proxy.to_dict() for proxy in proxies],
                "stable_pool": [proxy.to_dict() for proxy in stable_proxies],
                "stable_summary": stable_proxy_summary,
            },
        },
    }
    path = save_runtime_config(config)
    logs.append(f"[AUTO][SUMMARY] config_saved={path}")
    logs.append(
        "[AUTO][SUMMARY] "
        f"proxy_working={len(proxies)} "
        f"proxy_stable={len(stable_proxies)} "
        f"captcha={config['captcha']['provider'] or '<none>'} "
        f"sms_real={config['sms']['provider'] or '<none>'} "
        f"sms_diagnostic={config['sms']['diagnostic_primary'] or '<none>'}"
    )
    return config, logs
