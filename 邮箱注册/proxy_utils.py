"""
代理格式智能解析与标准化

支持格式:
  host:port:user:pass     (IPWEB/代理商格式)
  user:pass@host:port     (标准认证格式)
  http://host:port        (HTTP 代理)
  http://user:pass@host:port
  socks5://host:port
  socks5://user:pass@host:port
  host:port               (无认证)

自动:
  - 去 BOM、首尾空白、行内注释
  - 识别协议（无协议默认 http）
  - 提取 user:pass 认证信息
  - 输出标准化 URL: protocol://[user:pass@]host:port
"""

from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ProxyInfo:
    """Parsed proxy information."""
    host: str
    port: int
    username: str = ""
    password: str = ""
    protocol: str = "http"
    original: str = ""

    @property
    def url(self) -> str:
        """Standard URL format: protocol://[user:pass@]host:port"""
        if self.username:
            return f"{self.protocol}://{self.username}:{self.password}@{self.host}:{self.port}"
        return f"{self.protocol}://{self.host}:{self.port}"

    @property
    def host_port(self) -> str:
        return f"{self.host}:{self.port}"

    @property
    def has_auth(self) -> bool:
        return bool(self.username)

    @property
    def curl_arg(self) -> str:
        """Format for curl -x flag: user:pass@host:port"""
        if self.username:
            return f"{self.username}:{self.password}@{self.host}:{self.port}"
        return f"{self.host}:{self.port}"

    @property
    def chrome_proxy(self) -> str:
        """Format for Chrome --proxy-server: protocol://host:port (no auth)"""
        return f"{self.protocol}://{self.host}:{self.port}"

    def __str__(self) -> str:
        return self.url


def parse_proxy(raw: str) -> Optional[ProxyInfo]:
    """
    Parse a proxy string in any supported format.
    
    Args:
        raw: Raw proxy string in any format
        
    Returns:
        ProxyInfo if valid, None if unparseable
    """
    if not raw or not isinstance(raw, str):
        return None

    # Strip BOM, whitespace, inline comments
    line = raw.replace('\ufeff', '').strip()
    line = re.sub(r'\s*(#.*)$', '', line)
    line = re.sub(r'(?<!:)\s*//.*$', '', line)
    line = line.strip()
    if not line:
        return None

    protocol = "http"
    auth = ""
    host_port = line

    # Extract protocol prefix
    proto_match = re.match(r'^(https?|socks[45]?)\s*://', line, re.IGNORECASE)
    if proto_match:
        protocol = proto_match.group(1).lower()
        if protocol == "https":
            protocol = "http"  # HTTPS proxy still uses HTTP CONNECT
        host_port = line[len(proto_match.group(0)):]

    # Extract user:pass@ auth
    auth_match = re.match(r'^([^@\s]+)@(.+)$', host_port)
    if auth_match:
        auth = auth_match.group(1)
        host_port = auth_match.group(2)

    # ── IPWEB format: host:port:user:pass ──
    if not auth:
        colon_parts = host_port.split(':')
        if len(colon_parts) == 4:
            maybe_port = _try_int(colon_parts[1])
            maybe_user = colon_parts[2].strip()
            maybe_pass = colon_parts[3].strip()
            # port is valid number, user is non-empty and not pure digits
            if (maybe_port and 1 <= maybe_port <= 65535 
                and maybe_user and not maybe_user.isdigit()):
                host_port = f"{colon_parts[0]}:{colon_parts[1]}"
                auth = f"{maybe_user}:{maybe_pass}"

    # Parse host:port
    host, port = _parse_host_port(host_port)
    if not host or not port:
        return None

    # Validate host
    if not re.match(r'^[a-zA-Z0-9._\-:]+$', host):
        return None

    host = host.lower()

    # Parse auth
    username = ""
    password = ""
    if auth:
        parts = auth.split(':', 1)
        username = parts[0]
        password = parts[1] if len(parts) > 1 else ""

    return ProxyInfo(
        host=host,
        port=port,
        username=username,
        password=password,
        protocol=protocol,
        original=raw.strip(),
    )


def parse_proxies(text: str) -> list[ProxyInfo]:
    """Parse multiple proxy lines from text."""
    results = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        p = parse_proxy(line)
        if p:
            results.append(p)
    return results


def normalize_proxy_line(raw: str) -> Optional[str]:
    """Parse and return normalized proxy URL string."""
    p = parse_proxy(raw)
    return p.url if p else None


def normalize_proxies(text: str) -> str:
    """Normalize multiple proxy lines, returning newline-joined URLs."""
    return '\n'.join(p.url for p in parse_proxies(text))


def _try_int(s: str) -> Optional[int]:
    try:
        return int(s.strip())
    except (ValueError, AttributeError):
        return None


def _parse_host_port(host_port: str) -> tuple[str, int]:
    """Parse host:port string, supporting IPv6."""
    # IPv6: [::1]:port
    m = re.match(r'^\[([^\]]+)\]:(\d+)$', host_port)
    if m:
        return m.group(1), int(m.group(2))

    parts = host_port.split(':')
    if len(parts) != 2:
        return "", 0

    host = parts[0].strip()
    port = _try_int(parts[1])
    if not host or not port or port < 1 or port > 65535:
        return "", 0

    return host, port


# ── Quick test ──
if __name__ == "__main__":
    test_cases = [
        "gate2.ipweb.cc:7778:B_72756_JP___90_pphKvB9y:2442375",
        "http://user:pass@proxy.example.com:8080",
        "socks5://user:pass@127.0.0.1:1080",
        "192.168.1.1:3128",
        "user:pass@gate1.ipweb.cc:7778",
        "  # comment line  ",
        "",
    ]
    for tc in test_cases:
        p = parse_proxy(tc)
        if p:
            print(f"  {tc!r:60s} → {p.url}")
            if p.has_auth:
                print(f"    auth: {p.username}:{'*' * len(p.password)}  chrome: {p.chrome_proxy}  curl: {p.curl_arg}")
        else:
            print(f"  {tc!r:60s} → INVALID")
