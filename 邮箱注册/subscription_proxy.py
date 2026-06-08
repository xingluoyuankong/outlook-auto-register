"""
订阅代理管理器 (mihomo 子进程版)

自动管理 mihomo 子进程，将订阅链接中的 SSR/Trojan/Hysteria2 节点
转换为 HTTP/SOCKS5 代理供邮箱注册使用。

端口: mixed-port=28888, API=29090
(17890 端口在 Windows 上被 Hyper-V 动态端口保留拦截，不可用)
"""

from __future__ import annotations

import json
import logging
import os
import re
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

import requests
import yaml

logger = logging.getLogger(__name__)

# ─── 常量 ───
MIHOMO_DIR = Path(__file__).parent / "mihomo_runtime"
MIHOMO_EXE = MIHOMO_DIR / "mihomo.exe"
MIHOMO_LINUX = MIHOMO_DIR / "mihomo-linux"
CONFIG_PATH = MIHOMO_DIR / "config.yaml"
SUBS_FILE = MIHOMO_DIR / "subscriptions.json"


def _mihomo_executable() -> Path:
    """Return the platform-appropriate mihomo executable."""
    if sys.platform == "win32":
        return MIHOMO_EXE
    if MIHOMO_LINUX.exists():
        return MIHOMO_LINUX
    return MIHOMO_EXE

MIXED_PORT = 28888       # HTTP+SOCKS5 混合代理端口
API_PORT = 29090         # mihomo RESTful API 端口
API_URL = f"http://127.0.0.1:{API_PORT}"

PROXY_URL = f"http://127.0.0.1:{MIXED_PORT}"

# 备用：系统代理检测端口
SYSTEM_PROXY_PORTS = [7897, 7890, 1080, 7891]

# 订阅链接正则
SUB_URL_RE = re.compile(r'https?://[^\s<>"\']+', re.IGNORECASE)


# ─── 工具函数 ───

def _check_port(host: str, port: int, timeout: float = 1.5) -> bool:
    """检查端口是否可连接"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        return False


def _kill_all_mihomo():
    """杀掉所有 mihomo 进程"""
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/IM", "mihomo.exe"],
                           capture_output=True, timeout=5)
        else:
            subprocess.run(["pkill", "-f", "mihomo"],
                           capture_output=True, timeout=5)
    except Exception:
        pass
    time.sleep(0.5)


def _request_no_proxy() -> dict:
    """返回绕过系统代理的 proxies 配置"""
    return {"http": PROXY_URL, "https": PROXY_URL}


def _api_get(path: str, timeout: float = 5) -> Optional[dict]:
    """调用 mihomo API（带重试）"""
    for attempt in range(2):
        try:
            os.environ["NO_PROXY"] = "127.0.0.1,localhost"
            r = requests.get(f"{API_URL}{path}", timeout=timeout)
            if r.status_code == 200:
                return r.json()
        except (ConnectionError, ConnectionAbortedError, ConnectionResetError, OSError):
            if attempt == 0:
                time.sleep(0.3)
                continue
        except Exception as e:
            logger.debug(f"[mihomo API] {path} 失败: {e}")
            break
    return None


def _api_put(path: str, data: dict, timeout: float = 5) -> bool:
    """调用 mihomo API (PUT, 带重试)"""
    for attempt in range(2):
        try:
            os.environ["NO_PROXY"] = "127.0.0.1,localhost"
            r = requests.put(f"{API_URL}{path}", json=data, timeout=timeout)
            return r.status_code in (200, 204)
        except (ConnectionError, ConnectionAbortedError, ConnectionResetError, OSError):
            if attempt == 0:
                time.sleep(0.3)
                continue
        except Exception:
            break
    return False


# ─── 核心管理器 ───

class SubscriptionProxyManager:
    """mihomo 订阅代理管理器"""

    def __init__(self):
        self._process: Optional[subprocess.Popen] = None
        self._subscriptions: list[dict] = []   # [{url, name}]
        self._load_subscriptions()
        self._started_by_us = False

    # ─── 订阅管理 ───

    def _load_subscriptions(self):
        try:
            if SUBS_FILE.exists():
                with open(SUBS_FILE, "r", encoding="utf-8") as f:
                    self._subscriptions = json.load(f)
        except Exception:
            self._subscriptions = []

    def _save_subscriptions(self):
        try:
            with open(SUBS_FILE, "w", encoding="utf-8") as f:
                json.dump(self._subscriptions, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[订阅] 保存失败: {e}")

    @property
    def subscriptions(self) -> list[dict]:
        return self._subscriptions

    def add(self, url: str, name: str = "") -> tuple[bool, str]:
        url = url.strip()
        if not url:
            return False, "URL 为空"
        # 去重
        for s in self._subscriptions:
            if s["url"] == url:
                return False, "该订阅已存在"
        name = name or url.split("/")[-1][:32] or "sub"
        self._subscriptions.append({"url": url, "name": name})
        self._save_subscriptions()
        return True, f"已添加订阅: {name}"

    def remove(self, url: str) -> tuple[bool, str]:
        url = url.strip()
        before = len(self._subscriptions)
        self._subscriptions = [s for s in self._subscriptions if s["url"] != url]
        self._save_subscriptions()
        if len(self._subscriptions) < before:
            return True, "已移除"
        return False, "未找到该订阅"

    def clear(self):
        self._subscriptions.clear()
        self._save_subscriptions()

    # ─── mihomo 生命周期 ───

    def _update_config(self) -> bool:
        """根据当前订阅列表更新 mihomo 配置"""
        try:
            cfg = {}

            # 基础配置
            cfg["mixed-port"] = MIXED_PORT
            cfg["external-controller"] = f"127.0.0.1:{API_PORT}"
            cfg["allow-lan"] = False
            cfg["mode"] = "global"
            cfg["log-level"] = "info"
            cfg["global-client-fingerprint"] = "chrome"
            cfg["tcp-concurrent"] = True
            cfg["unified-delay"] = True
            cfg["skip-auth"] = True
            cfg["find-process-mode"] = "off"
            cfg["ipv6"] = False

            # DNS 配置
            cfg["dns"] = {
                "enable": True,
                "listen": "127.0.0.1:53553",
                "ipv6": False,
                "enhanced-mode": "fake-ip",
                "fake-ip-range": "198.18.0.1/16",
                "default-nameserver": ["223.5.5.5", "119.29.29.29", "8.8.8.8"],
                "nameserver": ["https://dns.alidns.com/dns-query", "https://doh.pub/dns-query"],
                "fallback": ["https://dns.google/dns-query", "https://cloudflare-dns.com/dns-query", "tls://8.8.4.4"],
                "fallback-filter": {
                    "geoip": True,
                    "geoip-code": "CN",
                    "ipcidr": ["240.0.0.0/4", "0.0.0.0/32"],
                },
            }

            # 直接下载订阅并提取 proxies（不使用 proxy-providers）
            all_proxies = []
            seen_names = set()
            for i, sub in enumerate(self._subscriptions):
                try:
                    resp = requests.get(sub["url"], timeout=15, headers={
                        "User-Agent": "ClashForAndroid/2.5.12"
                    }, proxies={"http": None, "https": None})
                    resp.raise_for_status()
                    data = yaml.safe_load(resp.text)
                    if isinstance(data, dict) and "proxies" in data:
                        for p in data["proxies"]:
                            name = p.get("name", "")
                            if name and name not in seen_names:
                                seen_names.add(name)
                                all_proxies.append(p)
                except Exception as e:
                    logger.warning(f"[mihomo] 订阅 {i} 下载失败: {e}")

            if not all_proxies:
                logger.error("[mihomo] 没有获取到任何代理节点")
                return False

            cfg["proxies"] = all_proxies

            # 构建代理组
            node_names = [p["name"] for p in all_proxies]
            cfg["proxy-groups"] = [{
                "name": "AUTO",
                "type": "url-test",
                "proxies": node_names,
                "url": "http://connect.rom.miui.com/generate_204",
                "interval": 300,
                "tolerance": 100,
            }]

            cfg["rules"] = ["MATCH,AUTO"]

            # 写入
            MIHOMO_DIR.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)

            logger.info(f"[mihomo] 配置已更新: {len(all_proxies)} 个节点")
            return True
        except Exception as e:
            logger.error(f"[mihomo] 配置更新失败: {e}")
            return False

    def start(self) -> tuple[bool, str]:
        """启动 mihomo 子进程"""
        if self.is_running and _check_port("127.0.0.1", MIXED_PORT):
            return True, f"mihomo 已在运行 (端口 {MIXED_PORT})"
        if self.is_running:
            logger.warning("[mihomo] 状态异常(API/残留)，重启")
            _kill_all_mihomo()
            time.sleep(0.5)

        if not self._subscriptions:
            return False, "没有订阅链接，请先添加订阅"

        # 更新配置（快速启动模式下复用已有配置，避免每次启动都重新拉取大量订阅）
        fast_start = os.environ.get("SUB_PROXY_FAST_START") == "1" and CONFIG_PATH.exists()
        if fast_start:
            logger.info("[mihomo] 快速启动：复用已有配置 %s", CONFIG_PATH)
        elif not self._update_config():
            return False, "配置文件更新失败"

        # 清理旧进程
        _kill_all_mihomo()

        # 确保端口可用
        if _check_port("127.0.0.1", MIXED_PORT):
            return False, f"端口 {MIXED_PORT} 已被占用"

        # 启动 mihomo
        try:
            cmd = [str(_mihomo_executable()), "-d", str(MIHOMO_DIR), "-f", str(CONFIG_PATH)]
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            self._started_by_us = True
            logger.info(f"[mihomo] 已启动 PID={self._process.pid}")
        except Exception as e:
            return False, f"mihomo 启动失败: {e}"

        # 等待就绪
        for i in range(30):  # 最多 15 秒
            time.sleep(0.5)
            if _check_port("127.0.0.1", MIXED_PORT):
                break
        else:
            return False, f"mihomo 启动超时 (端口 {MIXED_PORT} 未监听)"

        # 验证代理可用
        time.sleep(2)  # 给 mihomo 时间拉取订阅和初始化节点
        # 尝试找到一个 alive 节点
        try:
            ok, msg = self.find_alive_node()
            if ok:
                logger.info(f"[mihomo] {msg}")
            else:
                logger.warning(f"[mihomo] 找不到 alive 节点: {msg}")
        except Exception as e:
            logger.debug(f"[mihomo] alive 节点搜索失败: {e}")
        # 验证代理连通性
        try:
            os.environ["NO_PROXY"] = "127.0.0.1,localhost"
            r = requests.get("https://ipinfo.io/json",
                             proxies=_request_no_proxy(), timeout=15)
            if r.status_code == 200:
                d = r.json()
                ip = d.get("ip", "?")
                country = d.get("country", "?")
                node_count = self.node_count
                return True, f"mihomo 已启动 → {ip} ({country}), {node_count} 个节点"
        except Exception as e:
            logger.warning(f"[mihomo] 初始验证失败: {e}")
            return True, f"mihomo 已启动，但代理验证失败: {e}"

        return True, "mihomo 已启动"

    def stop(self) -> tuple[bool, str]:
        """停止 mihomo"""
        _kill_all_mihomo()
        self._process = None
        self._started_by_us = False
        return True, "mihomo 已停止"

    @property
    def is_running(self) -> bool:
        """检查 mihomo 是否在运行"""
        return _check_port("127.0.0.1", MIXED_PORT)

    @property
    def proxy_url(self) -> Optional[str]:
        """获取代理地址"""
        if self.is_running:
            return PROXY_URL
        return None

    @property
    def node_count(self) -> int:
        """获取可用节点数"""
        data = _api_get("/proxies")
        if not data:
            return 0
        proxies = data.get("proxies", {})
        auto_group = proxies.get("AUTO", {})
        return len(auto_group.get("all", []))

    # ─── 代理测试 ───

    def test_proxy(self) -> dict:
        """测试代理连通性（带重试）"""
        if not self.is_running:
            return {"ok": False, "error": "mihomo 未运行"}
        last_err = ""
        for attempt in range(3):
            try:
                os.environ["NO_PROXY"] = "127.0.0.1,localhost"
                r = requests.get("https://ipinfo.io/json",
                                 proxies=_request_no_proxy(), timeout=15)
                if r.status_code == 200:
                    d = r.json()
                    return {"ok": True, "ip": d.get("ip", ""), "country": d.get("country", "")}
                last_err = f"HTTP {r.status_code}"
            except (ConnectionError, ConnectionAbortedError, ConnectionResetError, OSError) as e:
                last_err = str(e)
                time.sleep(0.5)
            except Exception as e:
                last_err = str(e)
                break
        return {"ok": False, "error": last_err or "测试失败"}

    # ─── 节点轮询 ───

    def switch_to_next_node(self) -> tuple[bool, str]:
        """切换到下一个节点 (round-robin, 自动去重, 优先 alive 节点)"""
        data = _api_get("/proxies")
        if not data:
            return False, "无法获取代理组信息"

        proxies = data.get("proxies", {})
        auto = proxies.get("AUTO", {})
        all_nodes = auto.get("all", [])
        current = auto.get("now", "")

        if not all_nodes:
            return False, "没有可用节点"

        # 去重: 保持顺序，跳过重复节点
        seen = set()
        unique_nodes = []
        for n in all_nodes:
            if n not in seen:
                seen.add(n)
                unique_nodes.append(n)

        if len(unique_nodes) < 2:
            return False, "只有一个节点，无需切换"

        # 区分 alive 和 dead 节点
        alive_nodes = []
        dead_nodes = []
        for n in unique_nodes:
            info = proxies.get(n, {})
            if info.get("alive", False) and n not in ("COMPATIBLE", "DIRECT", "PASS", "REJECT", "REJECT-DROP"):
                alive_nodes.append(n)
            elif n not in ("COMPATIBLE", "DIRECT", "PASS", "REJECT", "REJECT-DROP"):
                dead_nodes.append(n)

        # 优先在 alive 节点中轮换
        pool = alive_nodes if alive_nodes else unique_nodes
        pool_type = "alive" if alive_nodes else "all"

        # 找到当前节点在 pool 中的位置
        try:
            idx = pool.index(current)
        except ValueError:
            idx = -1

        next_idx = (idx + 1) % len(pool)
        next_name = pool[next_idx]

        if _api_put("/proxies/AUTO", {"name": next_name}):
            return True, f"切换: {current} → {next_name} ({next_idx+1}/{len(pool)} {pool_type})"
        return False, f"切换失败: {current} → {next_name}"

    def find_alive_node(self) -> tuple[bool, str]:
        """找到第一个 alive 节点并切换"""
        data = _api_get("/proxies")
        if not data:
            return False, "无法获取代理组信息"
        proxies = data.get("proxies", {})
        auto = proxies.get("AUTO", {})
        all_nodes = auto.get("all", [])
        seen = set()
        for n in all_nodes:
            if n in seen:
                continue
            seen.add(n)
            if n in ("COMPATIBLE", "DIRECT", "PASS", "REJECT", "REJECT-DROP"):
                continue
            info = proxies.get(n, {})
            if info.get("alive", False):
                current = auto.get("now", "")
                if current == n:
                    return True, f"当前已是 alive 节点: {n}"
                if _api_put("/proxies/AUTO", {"name": n}):
                    return True, f"已切换到 alive 节点: {n}"
                return False, f"切换失败: {n}"
        return False, "没有 alive 的节点"

    def rotate_node(self) -> dict:
        ok, msg = self.switch_to_next_node()
        return {"ok": ok, "message": msg}

    def switch_to_node(self, node_name: str) -> tuple[bool, str]:
        """切换到指定节点"""
        data = _api_get("/proxies")
        if not data:
            return False, "无法获取代理组信息"
        proxies = data.get("proxies", {})
        auto = proxies.get("AUTO", {})
        all_nodes = auto.get("all", [])
        if node_name not in all_nodes:
            return False, f"节点 {node_name} 不存在"
        current = auto.get("now", "")
        if _api_put("/proxies/AUTO", {"name": node_name}):
            return True, f"切换: {current} → {node_name}"
        return False, f"切换失败"

    def get_nodes(self) -> list[dict]:
        """获取去重后的节点信息"""
        data = _api_get("/proxies")
        if not data:
            return []
        proxies = data.get("proxies", {})
        auto = proxies.get("AUTO", {})
        all_names = auto.get("all", [])
        current = auto.get("now", "")
        seen = set()
        result = []
        for name in all_names:
            if name in seen:
                continue
            seen.add(name)
            info = proxies.get(name, {})
            result.append({
                "name": name,
                "type": info.get("type", ""),
                "delay": info.get("history", [{}])[-1].get("delay", 0) if info.get("history") else 0,
                "alive": info.get("alive", False),
                "current": name == current,
            })
        return result

    # ─── 并发工作实例 ───

    def create_worker(self, node_name: str, port: int) -> tuple[bool, str, Optional[subprocess.Popen]]:
        """创建一个独立的 mihomo 工作实例，使用指定节点和端口。
        用于并发注册：每个并发任务一个独立实例，互不干扰。
        返回 (ok, proxy_url_or_error, process)"""
        exe = _mihomo_executable()
        if not exe.exists():
            return False, f"mihomo 不存在: {exe}", None
        if _check_port("127.0.0.1", port):
            return False, f"端口 {port} 已被占用", None

        # 读取当前配置并修改
        try:
            if not CONFIG_PATH.exists():
                return False, "主配置不存在", None
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
        except Exception as e:
            return False, f"读取配置失败: {e}", None

        # 修改端口和代理组
        cfg["mixed-port"] = port
        cfg["external-controller"] = f"127.0.0.1:{port + 1000}"  # 避免端口冲突

        # 将 AUTO 组从 url-test 改为 select，指定默认节点
        for g in cfg.get("proxy-groups", []):
            if g.get("name") == "AUTO":
                g["type"] = "select"
                g["proxies"] = [node_name] + [n for n in g.get("proxies", []) if n != node_name]
                # 移除 url-test 特有字段
                for k in ("url", "interval", "tolerance"):
                    g.pop(k, None)
                break

        # 写入临时配置
        worker_dir = MIHOMO_DIR / f"worker_{port}"
        worker_dir.mkdir(parents=True, exist_ok=True)
        worker_cfg = worker_dir / "config.yaml"
        try:
            with open(worker_cfg, "w", encoding="utf-8") as f:
                yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)
        except Exception as e:
            return False, f"写入配置失败: {e}", None

        # 启动 mihomo
        try:
            cmd = [str(exe), "-d", str(worker_dir), "-f", str(worker_cfg)]
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            logger.info(f"[mihomo worker] 已启动 PID={proc.pid} port={port} node={node_name}")
        except Exception as e:
            return False, f"启动失败: {e}", None

        # 等待就绪
        proxy_url = f"http://127.0.0.1:{port}"
        for _ in range(30):
            time.sleep(0.5)
            if _check_port("127.0.0.1", port):
                return True, proxy_url, proc

        # 超时，杀掉进程
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            proc.kill()
        return False, f"启动超时 (端口 {port} 未监听)", None

    def get_alive_nodes(self) -> list[str]:
        """获取所有 alive 节点名称列表"""
        nodes = self.get_nodes()
        alive = [n["name"] for n in nodes if n.get("alive", False)
                 and n["name"] not in ("COMPATIBLE", "DIRECT", "PASS", "REJECT", "REJECT-DROP")]
        return alive if alive else [n["name"] for n in nodes
                                    if n["name"] not in ("COMPATIBLE", "DIRECT", "PASS", "REJECT", "REJECT-DROP")]

    @staticmethod
    def cleanup_worker(proc: Optional[subprocess.Popen]):
        """清理单个工作实例"""
        if not proc:
            return
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    # ─── 状态 ───

    def cleanup(self):
        """清理: 停止 mihomo 子进程（服务器关闭时调用）"""
        try:
            if self._process:
                self._process.terminate()
                try:
                    self._process.wait(timeout=5)
                except Exception:
                    self._process.kill()
        except Exception:
            pass
        _kill_all_mihomo()
        self._process = None
        self._started_by_us = False
        logger.info("[mihomo] cleanup 完成，进程已清理")

    def status(self) -> dict:
        running = self.is_running
        current_node = ""
        if running:
            data = _api_get("/proxies")
            if data:
                current_node = data.get("proxies", {}).get("AUTO", {}).get("now", "")
        return {
            "running": running,
            "proxy_url": PROXY_URL if running else None,
            "node_count": self.node_count if running else 0,
            "subscription_count": len(self._subscriptions),
            "mode": "mihomo_subprocess",
            "mixed_port": MIXED_PORT,
            "api_port": API_PORT,
            "current_node": current_node,
        }


# ─── 全局单例 ───

_manager: Optional[SubscriptionProxyManager] = None


def get_manager() -> SubscriptionProxyManager:
    global _manager
    if _manager is None:
        _manager = SubscriptionProxyManager()
    return _manager


# ─── 便捷函数 (兼容旧接口) ───

def detect_system_proxy() -> Optional[str]:
    """检测代理：优先使用 mihomo，回退到系统代理"""
    mgr = get_manager()
    if mgr.is_running:
        return PROXY_URL
    # 回退：检测系统代理
    for port in SYSTEM_PROXY_PORTS:
        if _check_port("127.0.0.1", port):
            proxy_url = f"http://127.0.0.1:{port}"
            try:
                os.environ["NO_PROXY"] = "127.0.0.1,localhost"
                r = requests.get("https://ipinfo.io/json",
                                 proxies={"http": proxy_url, "https": proxy_url},
                                 timeout=10)
                if r.status_code == 200:
                    return proxy_url
            except Exception:
                pass
    return None


def get_proxy_url() -> Optional[str]:
    return detect_system_proxy()


def test_proxy() -> dict:
    mgr = get_manager()
    if mgr.is_running:
        return mgr.test_proxy()
    # 回退系统代理
    proxy = detect_system_proxy()
    if not proxy:
        return {"ok": False, "error": "未检测到代理"}
    try:
        os.environ["NO_PROXY"] = "127.0.0.1,localhost"
        r = requests.get("https://ipinfo.io/json",
                         proxies={"http": proxy, "https": proxy}, timeout=10)
        if r.status_code == 200:
            d = r.json()
            return {"ok": True, "ip": d.get("ip", ""), "country": d.get("country", "")}
        return {"ok": False, "error": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}