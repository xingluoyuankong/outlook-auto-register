#!/usr/bin/env python3
"""Desktop control panel and startup helpers for Ninjemail."""

from __future__ import annotations

import importlib.util
import logging
import os
import queue
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Callable, Iterable, Optional

import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk


PROJECT_ROOT = Path(__file__).resolve().parent
PACKAGE_ROOT = PROJECT_ROOT / "ninjemail"
WEB_UI_SCRIPT = PROJECT_ROOT / "web_ui.py"
START_SCRIPT = PROJECT_ROOT / "start.py"
LOGS_DIR = PACKAGE_ROOT / "logs"
DEFAULT_WEB_PORT = 7860

CORE_DEPENDENCIES = [
    ("ninjemail", "ninjemail"),
    ("selenium", "selenium"),
    ("webdriver_manager", "webdriver-manager"),
    ("requests", "requests"),
    ("fake_useragent", "fake-useragent"),
    ("fp", "free-proxy"),
    ("toml", "toml"),
    ("faker", "Faker"),
    ("undetected_chromedriver", "undetected-chromedriver"),
]

WEB_DEPENDENCIES = [("gradio", "gradio")]
DEV_DEPENDENCIES = [("pytest", "pytest"), ("pytest_mock", "pytest-mock"), ("pytest_cov", "pytest-cov")]


def _import_available(import_name: str) -> bool:
    return importlib.util.find_spec(import_name) is not None


def check_dependencies(include_web: bool = False, include_dev: bool = False) -> list[str]:
    """Return pip names for missing dependencies."""
    dependencies = list(CORE_DEPENDENCIES)
    if include_web:
        dependencies.extend(WEB_DEPENDENCIES)
    if include_dev:
        dependencies.extend(DEV_DEPENDENCIES)

    missing: list[str] = []
    for import_name, pip_name in dependencies:
        if not _import_available(import_name):
            missing.append(pip_name)
    return missing


def format_missing_dependencies(missing: Iterable[str]) -> str:
    values = list(missing)
    if not values:
        return "全部依赖已满足"
    return "缺少依赖: " + ", ".join(values)


def find_free_port(start_port: int = DEFAULT_WEB_PORT, end_port: int = 7900) -> int:
    port = max(1, start_port)
    end_port = max(end_port, port + 40)
    while port <= end_port:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                return port
        port += 1
    raise RuntimeError("没有找到可用端口")


def wait_for_port(port: int, host: str = "127.0.0.1", timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex((host, port)) == 0:
                return True
        time.sleep(0.25)
    return False


def open_path(path: Path) -> None:
    target = str(path)
    if hasattr(os, "startfile"):
        os.startfile(target)  # type: ignore[attr-defined]
        return
    if sys.platform == "darwin":
        subprocess.Popen(["open", target], cwd=str(PROJECT_ROOT))
    else:
        subprocess.Popen(["xdg-open", target], cwd=str(PROJECT_ROOT))


def terminate_process(process: Optional[subprocess.Popen[bytes]]) -> None:
    if not process or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


def _command_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    return env


def run_command_streaming(
    command: list[str],
    *,
    cwd: Path = PROJECT_ROOT,
    log: Optional[Callable[[str], None]] = None,
) -> int:
    if log:
        log("执行命令: " + " ".join(command))

    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        env=_command_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    assert process.stdout is not None
    for line in iter(process.stdout.readline, ""):
        stripped = line.rstrip()
        if stripped and log:
            log(stripped)
    process.stdout.close()
    code = process.wait()
    if log:
        log(f"命令结束，退出码 {code}")
    return code


def install_dependencies(
    *,
    include_web: bool = True,
    log: Optional[Callable[[str], None]] = None,
) -> int:
    """Install core runtime dependencies and optional web UI packages."""
    requirements_file = PROJECT_ROOT / "requirements.txt"
    code = run_command_streaming([sys.executable, "-m", "pip", "install", "-r", str(requirements_file)], log=log)
    if code != 0:
        return code

    if include_web:
        return run_command_streaming([sys.executable, "-m", "pip", "install", "gradio"], log=log)
    return code


def run_tests(log: Optional[Callable[[str], None]] = None) -> int:
    return run_command_streaming([sys.executable, "-m", "pytest", "ninjemail/tests", "-q"], log=log)


def launch_web_ui(
    *,
    port: int = DEFAULT_WEB_PORT,
    share: bool = False,
    auto_open: bool = True,
    log: Optional[Callable[[str], None]] = None,
) -> tuple[subprocess.Popen[str], int, str]:
    """Start the Gradio UI in the background and optionally open it in a browser."""
    if not WEB_UI_SCRIPT.exists():
        raise FileNotFoundError(f"找不到 Web UI 脚本: {WEB_UI_SCRIPT}")
    missing_web = check_dependencies(include_web=True)
    if "gradio" in missing_web:
        raise RuntimeError("Web 模式缺少 gradio，请先安装依赖")

    chosen_port = find_free_port(port)
    if chosen_port != port and log:
        log(f"端口 {port} 已被占用，已切换到 {chosen_port}")

    command = [sys.executable, str(WEB_UI_SCRIPT), "--port", str(chosen_port), "--no-browser"]
    if share:
        command.append("--share")

    if log:
        log("启动 Web UI: " + " ".join(command))

    process = subprocess.Popen(
        command,
        cwd=str(PROJECT_ROOT),
        env=_command_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    def _stream_output() -> None:
        if process.stdout is None:
            return
        for line in iter(process.stdout.readline, ""):
            stripped = line.rstrip()
            if stripped and log:
                log(stripped)
        process.stdout.close()
        exit_code = process.wait()
        if log:
            log(f"Web UI 进程已退出，退出码 {exit_code}")

    threading.Thread(target=_stream_output, daemon=True).start()

    url = f"http://127.0.0.1:{chosen_port}"

    if auto_open:
        def _open_when_ready() -> None:
            if wait_for_port(chosen_port):
                time.sleep(0.2)
                webbrowser.open(url)
                if log:
                    log(f"浏览器已打开: {url}")
            elif log:
                log("Web UI 启动超时，未能确认端口已就绪")

        threading.Thread(target=_open_when_ready, daemon=True).start()

    return process, chosen_port, url


def _normalize_proxy_line(line: str) -> str:
    text = line.strip()
    if not text:
        return ""
    if "://" not in text:
        return "http://" + text
    return text


def _parse_proxies(raw: str) -> list[str]:
    proxies: list[str] = []
    for line in raw.splitlines():
        proxy = _normalize_proxy_line(line)
        if proxy:
            proxies.append(proxy)
    return proxies


class UiLogHandler(logging.Handler):
    def __init__(self, queue_ref: queue.Queue[str]):
        super().__init__()
        self.queue_ref = queue_ref

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
            self.queue_ref.put(message)
        except Exception:
            self.handleError(record)


class NinjemailDesktopApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Ninjemail 桌面控制台")
        self.geometry("1180x780")
        self.minsize(1080, 720)

        self.ui_queue: "queue.Queue[tuple[str, object]]" = queue.Queue()
        self.ui_log_handler: Optional[UiLogHandler] = None
        self.backend = None
        self.backend_signature: Optional[tuple[object, ...]] = None
        self.web_process: Optional[subprocess.Popen[str]] = None
        self.web_port: Optional[int] = None
        self.web_url: Optional[str] = None
        self.result_text_content = ""
        self._busy = False

        self._build_variables()
        self._configure_style()
        self._build_layout()
        self.after(120, self._drain_ui_queue)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._update_provider_hint()

    def _build_variables(self) -> None:
        self.browser_var = tk.StringVar(value="chrome")
        self.captcha_service_var = tk.StringVar(value="capsolver")
        self.captcha_key_var = tk.StringVar(value="")
        self.sms_service_var = tk.StringVar(value="smspool")
        self.sms_user_var = tk.StringVar(value="")
        self.sms_token_var = tk.StringVar(value="")
        self.auto_proxy_var = tk.BooleanVar(value=False)
        self.proxy_list_var = tk.StringVar(value="")

        self.provider_var = tk.StringVar(value="outlook")
        self.username_var = tk.StringVar(value="")
        self.password_var = tk.StringVar(value="")
        self.first_name_var = tk.StringVar(value="")
        self.last_name_var = tk.StringVar(value="")
        self.country_var = tk.StringVar(value="")
        self.birthdate_var = tk.StringVar(value="")
        self.use_proxy_var = tk.BooleanVar(value=True)
        self.hotmail_var = tk.BooleanVar(value=False)

        self.web_port_var = tk.StringVar(value=str(DEFAULT_WEB_PORT))
        self.web_share_var = tk.BooleanVar(value=False)
        self.web_auto_open_var = tk.BooleanVar(value=True)

        self.status_var = tk.StringVar(value="就绪")
        self.backend_status_var = tk.StringVar(value="尚未初始化")
        self.provider_hint_var = tk.StringVar(value="")

    def _configure_style(self) -> None:
        try:
            style = ttk.Style(self)
            style.theme_use("clam")
        except tk.TclError:
            return

        self.configure(bg="#eef2f7")
        style.configure("TFrame", background="#eef2f7")
        style.configure("TLabel", background="#eef2f7", foreground="#1f2937")
        style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"), foreground="#0f172a")
        style.configure("Subtitle.TLabel", font=("Segoe UI", 10), foreground="#475569")
        style.configure("Section.TLabelframe", background="#eef2f7", padding=10)
        style.configure("Section.TLabelframe.Label", background="#eef2f7", foreground="#0f172a", font=("Segoe UI", 10, "bold"))
        style.configure("Primary.TButton", padding=(12, 6))
        style.configure("Accent.TButton", padding=(12, 6))

    def _build_layout(self) -> None:
        outer = ttk.Frame(self, padding=14)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x")
        header.columnconfigure(1, weight=1)

        logo_label = ttk.Label(header)
        logo_label.grid(row=0, column=0, rowspan=2, padx=(0, 16), sticky="nw")
        self._load_logo(logo_label)

        ttk.Label(header, text="Ninjemail 桌面控制台", style="Title.TLabel").grid(row=0, column=1, sticky="w")
        ttk.Label(
            header,
            text="统一管理浏览器自动化、验证码服务、短信接码与本地启动入口",
            style="Subtitle.TLabel",
        ).grid(row=1, column=1, sticky="w", pady=(4, 0))

        summary = ttk.Frame(outer)
        summary.pack(fill="x", pady=(12, 0))

        self.summary_label = ttk.Label(
            summary,
            text="支持 Gmail / Outlook / Yahoo，浏览器：chrome、edge、brave 等 Chromium 内核浏览器",
            wraplength=1040,
        )
        self.summary_label.pack(anchor="w")

        notebook = ttk.Notebook(outer)
        notebook.pack(fill="both", expand=True, pady=(12, 0))

        self.start_tab = ttk.Frame(notebook, padding=14)
        self.config_tab = ttk.Frame(notebook, padding=14)
        self.task_tab = ttk.Frame(notebook, padding=14)
        self.log_tab = ttk.Frame(notebook, padding=14)
        self.about_tab = ttk.Frame(notebook, padding=14)

        notebook.add(self.start_tab, text="启动")
        notebook.add(self.config_tab, text="配置")
        notebook.add(self.task_tab, text="任务")
        notebook.add(self.log_tab, text="日志")
        notebook.add(self.about_tab, text="说明")

        self._build_start_tab()
        self._build_config_tab()
        self._build_task_tab()
        self._build_log_tab()
        self._build_about_tab()

        footer = ttk.Frame(outer)
        footer.pack(fill="x", pady=(12, 0))
        footer.columnconfigure(0, weight=1)

        self.progress = ttk.Progressbar(footer, mode="indeterminate")
        self.progress.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        ttk.Label(footer, textvariable=self.status_var).grid(row=0, column=1, sticky="e")

    def _build_start_tab(self) -> None:
        left = ttk.LabelFrame(self.start_tab, text="桌面与浏览器启动", style="Section.TLabelframe")
        left.pack(fill="x")

        grid = ttk.Frame(left)
        grid.pack(fill="x")
        grid.columnconfigure(1, weight=1)

        self._add_labeled_entry(grid, 0, "Web 端口", self.web_port_var, width=16)
        self._add_checkbutton(grid, 0, "公开分享", self.web_share_var, column=2)
        self._add_checkbutton(grid, 1, "自动打开浏览器", self.web_auto_open_var, column=2)

        button_row = ttk.Frame(left)
        button_row.pack(fill="x", pady=(12, 0))

        self.web_start_button = ttk.Button(button_row, text="启动 Web 界面", style="Accent.TButton", command=self._launch_web_ui_async)
        self.web_start_button.pack(side="left", padx=(0, 8))
        self.web_stop_button = ttk.Button(button_row, text="停止 Web 界面", command=self._stop_web_ui)
        self.web_stop_button.pack(side="left", padx=(0, 8))
        self.check_core_button = ttk.Button(button_row, text="检查核心依赖", command=self._check_core_dependencies)
        self.check_core_button.pack(side="left", padx=(0, 8))
        self.check_web_button = ttk.Button(button_row, text="检查 Web 依赖", command=self._check_web_dependencies)
        self.check_web_button.pack(side="left", padx=(0, 8))
        self.install_button = ttk.Button(button_row, text="安装依赖", command=self._install_dependencies_async)
        self.install_button.pack(side="left", padx=(0, 8))
        self.test_button = ttk.Button(button_row, text="运行测试", command=self._run_tests_async)
        self.test_button.pack(side="left", padx=(0, 8))

        util_row = ttk.Frame(left)
        util_row.pack(fill="x", pady=(12, 0))
        self.open_project_button = ttk.Button(util_row, text="打开项目目录", command=lambda: open_path(PROJECT_ROOT))
        self.open_project_button.pack(side="left", padx=(0, 8))
        self.open_logs_button = ttk.Button(util_row, text="打开日志目录", command=lambda: open_path(LOGS_DIR))
        self.open_logs_button.pack(side="left", padx=(0, 8))
        self.open_script_button = ttk.Button(util_row, text="打开启动脚本", command=lambda: open_path(START_SCRIPT))
        self.open_script_button.pack(side="left", padx=(0, 8))

        hint = ttk.Label(
            left,
            text="桌面模式适合本地操作与演示，Web 模式保留原有 Gradio 界面。",
            wraplength=1040,
        )
        hint.pack(anchor="w", pady=(12, 0))

        self.start_buttons = [
            self.web_start_button,
            self.web_stop_button,
            self.check_core_button,
            self.check_web_button,
            self.install_button,
            self.test_button,
            self.open_project_button,
            self.open_logs_button,
            self.open_script_button,
        ]

    def _build_config_tab(self) -> None:
        frame = ttk.LabelFrame(self.config_tab, text="运行配置", style="Section.TLabelframe")
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)

        self._add_labeled_dropdown(frame, 0, "浏览器", self.browser_var, ["chrome", "edge", "brave", "chromium", "vivaldi", "thorium", "opera"])
        self._add_labeled_dropdown(frame, 1, "验证码服务", self.captcha_service_var, ["", "capsolver", "nopecha"])
        self._add_labeled_entry(frame, 2, "验证码 API Key", self.captcha_key_var, show="*")
        self._add_labeled_dropdown(frame, 3, "短信服务", self.sms_service_var, ["", "getsmscode", "smspool", "5sim"])
        self._add_labeled_entry(frame, 4, "短信用户名", self.sms_user_var)
        self._add_labeled_entry(frame, 5, "短信 Token", self.sms_token_var, show="*")
        self._add_checkbutton(frame, 6, "自动代理", self.auto_proxy_var, column=1)

        proxy_label = ttk.Label(frame, text="代理列表")
        proxy_label.grid(row=7, column=0, sticky="nw", padx=(0, 10), pady=(12, 0))
        self.proxy_text = scrolledtext.ScrolledText(frame, height=6, wrap="word")
        self.proxy_text.grid(row=7, column=1, sticky="nsew", pady=(12, 0))
        self.proxy_text.insert("1.0", "")

        self.config_save_button = ttk.Button(frame, text="初始化/刷新后台", style="Accent.TButton", command=self._ensure_backend_async)
        self.config_save_button.grid(row=8, column=1, sticky="e", pady=(12, 0))
        self.config_buttons = [self.config_save_button]

        ttk.Label(
            frame,
            text="提示：Outlook/Yahoo 需要验证码服务；Gmail 需要短信服务。country 字段的可见文本必须与网站下拉项一致。",
            wraplength=980,
        ).grid(row=9, column=0, columnspan=2, sticky="w", pady=(12, 0))

        status_row = ttk.Frame(frame)
        status_row.grid(row=10, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        status_row.columnconfigure(1, weight=1)
        ttk.Label(status_row, text="后台状态").grid(row=0, column=0, sticky="w")
        ttk.Label(status_row, textvariable=self.backend_status_var).grid(row=0, column=1, sticky="w")
        ttk.Label(status_row, textvariable=self.provider_hint_var, wraplength=980).grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))

    def _build_task_tab(self) -> None:
        frame = ttk.LabelFrame(self.task_tab, text="账号创建", style="Section.TLabelframe")
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)

        self._add_labeled_dropdown(frame, 0, "平台", self.provider_var, ["outlook", "gmail", "yahoo"])
        self._add_labeled_entry(frame, 1, "用户名", self.username_var)
        self._add_labeled_entry(frame, 2, "密码", self.password_var, show="*")
        self._add_labeled_entry(frame, 3, "名字", self.first_name_var)
        self._add_labeled_entry(frame, 4, "姓氏", self.last_name_var)
        self._add_labeled_entry(frame, 5, "国家/地区", self.country_var)
        self._add_labeled_entry(frame, 6, "生日 (MM-DD-YYYY)", self.birthdate_var)
        self._add_checkbutton(frame, 7, "使用代理", self.use_proxy_var, column=1)
        self._add_checkbutton(frame, 8, "创建 Hotmail 账号", self.hotmail_var, column=1)

        button_row = ttk.Frame(frame)
        button_row.grid(row=9, column=0, columnspan=2, sticky="w", pady=(12, 0))
        self.create_outlook_button = ttk.Button(button_row, text="创建 Outlook", style="Accent.TButton", command=lambda: self._create_account_async("outlook"))
        self.create_outlook_button.pack(side="left", padx=(0, 8))
        self.create_gmail_button = ttk.Button(button_row, text="创建 Gmail", command=lambda: self._create_account_async("gmail"))
        self.create_gmail_button.pack(side="left", padx=(0, 8))
        self.create_yahoo_button = ttk.Button(button_row, text="创建 Yahoo", command=lambda: self._create_account_async("yahoo"))
        self.create_yahoo_button.pack(side="left", padx=(0, 8))
        self.copy_result_button = ttk.Button(button_row, text="复制结果", command=self._copy_result_to_clipboard)
        self.copy_result_button.pack(side="left", padx=(0, 8))

        self.task_buttons = [
            self.create_outlook_button,
            self.create_gmail_button,
            self.create_yahoo_button,
            self.copy_result_button,
        ]

        ttk.Label(
            frame,
            text="空白字段会由后端自动生成；创建过程会在后台线程执行，日志会同步到本地日志面板。",
            wraplength=980,
        ).grid(row=10, column=0, columnspan=2, sticky="w", pady=(12, 0))

        result_frame = ttk.LabelFrame(frame, text="最近结果", style="Section.TLabelframe")
        result_frame.grid(row=11, column=0, columnspan=2, sticky="nsew", pady=(12, 0))
        result_frame.columnconfigure(0, weight=1)
        result_frame.rowconfigure(0, weight=1)
        self.result_text = scrolledtext.ScrolledText(result_frame, height=9, wrap="word", state="disabled")
        self.result_text.grid(row=0, column=0, sticky="nsew")

    def _build_log_tab(self) -> None:
        frame = ttk.LabelFrame(self.log_tab, text="运行日志", style="Section.TLabelframe")
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        self.log_text = scrolledtext.ScrolledText(frame, height=20, wrap="word", state="disabled")
        self.log_text.grid(row=0, column=0, sticky="nsew")

        log_buttons = ttk.Frame(frame)
        log_buttons.grid(row=1, column=0, sticky="e", pady=(12, 0))
        ttk.Button(log_buttons, text="清空日志", command=self._clear_log).pack(side="left", padx=(0, 8))
        ttk.Button(log_buttons, text="复制日志", command=self._copy_log_to_clipboard).pack(side="left", padx=(0, 8))

    def _build_about_tab(self) -> None:
        frame = ttk.LabelFrame(self.about_tab, text="项目结构", style="Section.TLabelframe")
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        text = scrolledtext.ScrolledText(frame, height=18, wrap="word", state="normal")
        text.grid(row=0, column=0, sticky="nsew")
        text.insert(
            "1.0",
            "\n".join(
                [
                    "1. ninjemail/ninjemail_manager.py 负责总调度：浏览器、代理、验证码与短信服务串联。",
                    "2. ninjemail/utils/webdriver_utils.py 负责创建 Firefox / Chrome / Undetected Chrome 驱动，并注入代理与验证码扩展。",
                    "3. ninjemail/email_providers/*.py 是站点级流程：分别实现 Outlook、Gmail、Yahoo 的表单填写、验证码处理和结果校验。",
                    "4. ninjemail/sms_services/*.py 对接接码平台，把“买号码”和“拉验证码”两步封装成统一接口。",
                    "5. ninjemail/config.toml 统一声明支持的浏览器、验证码服务、短信服务与邮箱服务的映射关系。",
                    "6. desktop_ui.py 是新的桌面控制台，负责本地运行、日志、任务调度和 Web UI 启停。",
                    "7. start.py 是新的统一入口，默认进入桌面模式，也可以切换到 Web 模式。",
                ]
            ),
        )
        text.configure(state="disabled")

    def _load_logo(self, label: ttk.Label) -> None:
        logo_path = PROJECT_ROOT / "logo" / "logo.png"
        try:
            self.logo_image = tk.PhotoImage(file=str(logo_path))
            label.configure(image=self.logo_image)
        except Exception:
            label.configure(text="N", font=("Segoe UI", 28, "bold"), foreground="#2563eb")

    def _add_labeled_entry(
        self,
        parent: ttk.Frame,
        row: int,
        text: str,
        variable: tk.StringVar,
        *,
        width: int = 30,
        show: Optional[str] = None,
        column: int = 0,
    ) -> ttk.Entry:
        ttk.Label(parent, text=text).grid(row=row, column=column, sticky="w", padx=(0, 10), pady=6)
        entry = ttk.Entry(parent, textvariable=variable, width=width, show=show)
        entry.grid(row=row, column=column + 1, sticky="ew", pady=6)
        parent.columnconfigure(column + 1, weight=1)
        return entry

    def _add_labeled_dropdown(
        self,
        parent: ttk.Frame,
        row: int,
        text: str,
        variable: tk.StringVar,
        values: list[str],
        *,
        column: int = 0,
        width: int = 28,
    ) -> ttk.Combobox:
        ttk.Label(parent, text=text).grid(row=row, column=column, sticky="w", padx=(0, 10), pady=6)
        combo = ttk.Combobox(parent, textvariable=variable, values=values, width=width, state="readonly")
        combo.grid(row=row, column=column + 1, sticky="ew", pady=6)
        parent.columnconfigure(column + 1, weight=1)
        return combo

    def _add_checkbutton(
        self,
        parent: ttk.Frame,
        row: int,
        text: str,
        variable: tk.BooleanVar,
        *,
        column: int = 0,
    ) -> ttk.Checkbutton:
        button = ttk.Checkbutton(parent, text=text, variable=variable)
        button.grid(row=row, column=column, columnspan=2, sticky="w", pady=6)
        return button

    def _provider_requirements(self, provider: str) -> tuple[bool, bool]:
        provider = provider.lower().strip()
        if provider == "gmail":
            return False, True
        if provider == "yahoo":
            return True, True
        return True, False

    def _update_provider_hint(self, *_: object) -> None:
        provider = self.provider_var.get().strip().lower()
        if provider == "gmail":
            self.provider_hint_var.set("Gmail：需要短信服务，不使用验证码服务。")
        elif provider == "yahoo":
            self.provider_hint_var.set("Yahoo：需要验证码服务和短信服务，通常也更依赖代理。")
        else:
            self.provider_hint_var.set("Outlook：需要验证码服务；如果你有代理，建议勾选使用代理。")

    def _attach_logging_handler(self) -> None:
        if self.ui_log_handler is not None:
            return
        self.ui_log_handler = UiLogHandler(self.ui_queue)
        self.ui_log_handler.setLevel(logging.INFO)
        self.ui_log_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        root_logger = logging.getLogger()
        root_logger.addHandler(self.ui_log_handler)
        if root_logger.level > logging.INFO:
            root_logger.setLevel(logging.INFO)

    def _detach_logging_handler(self) -> None:
        if self.ui_log_handler is None:
            return
        root_logger = logging.getLogger()
        try:
            root_logger.removeHandler(self.ui_log_handler)
        except ValueError:
            pass
        self.ui_log_handler = None

    def _enqueue(self, kind: str, payload: object) -> None:
        self.ui_queue.put((kind, payload))

    def _enqueue_dialog(self, kind: str, title: str, message: str) -> None:
        self.ui_queue.put((kind, (title, message)))

    def _drain_ui_queue(self) -> None:
        try:
            while True:
                kind, payload = self.ui_queue.get_nowait()
                if kind == "log":
                    self._append_log(str(payload))
                elif kind == "status":
                    self.status_var.set(str(payload))
                elif kind == "backend":
                    self.backend_status_var.set(str(payload))
                elif kind == "result":
                    self._set_result_text(str(payload))
                elif kind == "busy":
                    self._set_busy(bool(payload))
                elif kind == "dialog_info":
                    title, message = payload  # type: ignore[misc]
                    messagebox.showinfo(str(title), str(message))
                elif kind == "dialog_warning":
                    title, message = payload  # type: ignore[misc]
                    messagebox.showwarning(str(title), str(message))
                elif kind == "dialog_error":
                    title, message = payload  # type: ignore[misc]
                    messagebox.showerror(str(title), str(message))
        except queue.Empty:
            pass
        self.after(120, self._drain_ui_queue)

    def _append_log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _set_result_text(self, message: str) -> None:
        self.result_text_content = message
        self.result_text.configure(state="normal")
        self.result_text.delete("1.0", "end")
        self.result_text.insert("end", message)
        self.result_text.see("end")
        self.result_text.configure(state="disabled")

    def _clear_log(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _copy_log_to_clipboard(self) -> None:
        content = self.log_text.get("1.0", "end").strip()
        self.clipboard_clear()
        self.clipboard_append(content)
        self.status_var.set("日志已复制到剪贴板")

    def _copy_result_to_clipboard(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.result_text_content)
        self.status_var.set("结果已复制到剪贴板")

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        state = "disabled" if busy else "normal"
        for button in self.start_buttons + self.config_buttons + self.task_buttons:
            button.configure(state=state)
        if busy:
            self.progress.start(10)
        else:
            self.progress.stop()

    def _backend_signature(self) -> tuple[object, ...]:
        return (
            self.browser_var.get().strip(),
            self.captcha_service_var.get().strip(),
            self.captcha_key_var.get().strip(),
            self.sms_service_var.get().strip(),
            self.sms_user_var.get().strip(),
            self.sms_token_var.get().strip(),
            self.auto_proxy_var.get(),
            tuple(self._parse_proxy_list(self.proxy_text.get("1.0", "end"))),
        )

    def _parse_proxy_list(self, raw: str) -> list[str]:
        proxies: list[str] = []
        for line in raw.splitlines():
            text = line.strip()
            if not text:
                continue
            if "://" not in text:
                text = "http://" + text
            proxies.append(text)
        return proxies

    def _build_backend(self):
        from ninjemail import Ninjemail

        captcha_service = self.captcha_service_var.get().strip()
        captcha_key = self.captcha_key_var.get().strip()
        sms_service = self.sms_service_var.get().strip()
        sms_user = self.sms_user_var.get().strip()
        sms_token = self.sms_token_var.get().strip()
        proxies = self._parse_proxy_list(self.proxy_text.get("1.0", "end"))
        proxy_list = proxies or None

        if captcha_service and not captcha_key:
            raise ValueError("已选择验证码服务，但验证码 API Key 为空")
        if sms_service and not sms_token:
            raise ValueError("已选择短信服务，但短信 Token 为空")
        if sms_service == "getsmscode" and not sms_user:
            raise ValueError("getsmscode 需要短信用户名")

        captcha_keys = {captcha_service: captcha_key} if captcha_service else {}
        sms_keys: dict[str, dict[str, str]] = {}
        if sms_service:
            if sms_service == "getsmscode":
                sms_keys[sms_service] = {"user": sms_user, "token": sms_token}
            else:
                sms_keys[sms_service] = {"token": sms_token}

        backend = Ninjemail(
            browser=self.browser_var.get().strip(),
            captcha_keys=captcha_keys,
            sms_keys=sms_keys,
            proxies=proxy_list,
            auto_proxy=self.auto_proxy_var.get(),
        )
        self._attach_logging_handler()
        self.backend = backend
        self.backend_signature = self._backend_signature()
        self.backend_status_var.set("已初始化")
        return backend

    def _ensure_backend(self):
        signature = self._backend_signature()
        if self.backend is not None and self.backend_signature == signature:
            return self.backend
        backend = self._build_backend()
        self._enqueue("backend", "已初始化并同步当前配置")
        self._enqueue("log", "Ninjemail 后台已刷新")
        return backend

    def _ensure_backend_async(self) -> None:
        self._enqueue("busy", True)

        def worker() -> None:
            try:
                self._ensure_backend()
                self._enqueue("status", "后台初始化完成")
            except Exception as exc:
                self._enqueue("status", f"后台初始化失败: {exc}")
                self._enqueue("log", f"[ERROR] 后台初始化失败: {exc}")
                self._enqueue_dialog("dialog_error", "初始化失败", str(exc))
            finally:
                self._enqueue("busy", False)

        threading.Thread(target=worker, daemon=True).start()

    def _create_account_async(self, provider: str) -> None:
        provider = provider.lower().strip()
        need_captcha, need_sms = self._provider_requirements(provider)
        captcha_service = self.captcha_service_var.get().strip()
        captcha_key = self.captcha_key_var.get().strip()
        sms_service = self.sms_service_var.get().strip()
        sms_token = self.sms_token_var.get().strip()

        if need_captcha and not captcha_service:
            self._enqueue_dialog("dialog_warning", "配置不足", f"{provider} 需要验证码服务")
            return
        if need_captcha and not captcha_key:
            self._enqueue_dialog("dialog_warning", "配置不足", f"{provider} 需要验证码 API Key")
            return
        if need_sms and not sms_service:
            self._enqueue_dialog("dialog_warning", "配置不足", f"{provider} 需要短信服务")
            return
        if need_sms and not sms_token:
            self._enqueue_dialog("dialog_warning", "配置不足", f"{provider} 需要短信 Token")
            return

        self._enqueue("busy", True)

        def worker() -> None:
            try:
                backend = self._ensure_backend()
                self._enqueue("status", f"正在创建 {provider} 账号")
                username = self.username_var.get().strip()
                password = self.password_var.get().strip()
                first_name = self.first_name_var.get().strip()
                last_name = self.last_name_var.get().strip()
                birthdate = self.birthdate_var.get().strip()
                use_proxy = self.use_proxy_var.get()

                if provider == "outlook":
                    email, pwd = backend.create_outlook_account(
                        username=username,
                        password=password,
                        first_name=first_name,
                        last_name=last_name,
                        country=self.country_var.get().strip(),
                        birthdate=birthdate,
                        hotmail=self.hotmail_var.get(),
                        use_proxy=use_proxy,
                    )
                elif provider == "gmail":
                    email, pwd = backend.create_gmail_account(
                        username=username,
                        password=password,
                        first_name=first_name,
                        last_name=last_name,
                        birthdate=birthdate,
                        use_proxy=use_proxy,
                    )
                elif provider == "yahoo":
                    email, pwd = backend.create_yahoo_account(
                        username=username,
                        password=password,
                        first_name=first_name,
                        last_name=last_name,
                        birthdate=birthdate,
                        use_proxy=use_proxy,
                    )
                else:
                    raise ValueError(f"不支持的平台: {provider}")

                result = "\n".join(
                    [
                        f"平台: {provider}",
                        f"邮箱: {email}",
                        f"密码: {pwd}",
                        f"浏览器: {self.browser_var.get().strip()}",
                        f"代理: {'启用' if use_proxy else '关闭'}",
                    ]
                )
                self._enqueue("result", result)
                self._enqueue("status", f"{provider} 创建完成")
                self._enqueue("log", f"[SUCCESS] {provider} 创建完成: {email}")
            except Exception as exc:
                self._enqueue("status", f"{provider} 创建失败: {exc}")
                self._enqueue("log", f"[ERROR] {provider} 创建失败: {exc}")
                self._enqueue_dialog("dialog_error", "创建失败", str(exc))
            finally:
                self._enqueue("busy", False)

        threading.Thread(target=worker, daemon=True).start()

    def _launch_web_ui_async(self) -> None:
        def worker() -> None:
            try:
                port = int(self.web_port_var.get().strip())
            except ValueError:
                self._enqueue_dialog("dialog_error", "端口错误", "请输入有效端口号")
                return

            self._enqueue("busy", True)
            try:
                process, port, url = launch_web_ui(
                    port=port,
                    share=self.web_share_var.get(),
                    auto_open=self.web_auto_open_var.get(),
                    log=lambda msg: self._enqueue("log", msg),
                )
                self.web_process = process
                self.web_port = port
                self.web_url = url
                self._enqueue("status", f"Web UI 已启动: {url}")
            except Exception as exc:
                self._enqueue("status", f"Web UI 启动失败: {exc}")
                self._enqueue("log", f"[ERROR] Web UI 启动失败: {exc}")
                self._enqueue_dialog("dialog_error", "启动失败", str(exc))
                self._enqueue("busy", False)
                return
            finally:
                self._enqueue("busy", False)

        threading.Thread(target=worker, daemon=True).start()

    def _stop_web_ui(self) -> None:
        terminate_process(self.web_process)
        self.web_process = None
        self.web_port = None
        self.web_url = None
        self.status_var.set("Web UI 已停止")
        self._append_log("Web UI 已停止")

    def _check_core_dependencies(self) -> None:
        missing = check_dependencies(include_web=False)
        message = format_missing_dependencies(missing)
        self._append_log(message)
        self.status_var.set(message)
        if missing:
            messagebox.showwarning("依赖检查", message)
        else:
            messagebox.showinfo("依赖检查", message)

    def _check_web_dependencies(self) -> None:
        missing = check_dependencies(include_web=True)
        message = format_missing_dependencies(missing)
        self._append_log(message)
        self.status_var.set(message)
        if "gradio" in missing:
            messagebox.showwarning("依赖检查", "Web 模式缺少 gradio")
        elif missing:
            messagebox.showwarning("依赖检查", message)
        else:
            messagebox.showinfo("依赖检查", message)

    def _install_dependencies_async(self) -> None:
        self._enqueue("busy", True)

        def worker() -> None:
            try:
                code = install_dependencies(include_web=True, log=lambda msg: self._enqueue("log", msg))
                if code == 0:
                    self._enqueue("status", "依赖安装完成")
                    self._enqueue_dialog("dialog_info", "安装完成", "依赖已安装完成")
                else:
                    self._enqueue("status", f"依赖安装失败，退出码 {code}")
                    self._enqueue_dialog("dialog_error", "安装失败", f"依赖安装失败，退出码 {code}")
            except Exception as exc:
                self._enqueue("status", f"依赖安装失败: {exc}")
                self._enqueue("log", f"[ERROR] 依赖安装失败: {exc}")
                self._enqueue_dialog("dialog_error", "安装失败", str(exc))
            finally:
                self._enqueue("busy", False)

        threading.Thread(target=worker, daemon=True).start()

    def _run_tests_async(self) -> None:
        self._enqueue("busy", True)

        def worker() -> None:
            try:
                code = run_tests(log=lambda msg: self._enqueue("log", msg))
                if code == 0:
                    self._enqueue("status", "测试完成")
                    self._enqueue_dialog("dialog_info", "测试完成", "测试已完成")
                else:
                    self._enqueue("status", f"测试失败，退出码 {code}")
                    self._enqueue_dialog("dialog_error", "测试失败", f"测试退出码 {code}")
            except Exception as exc:
                self._enqueue("status", f"测试失败: {exc}")
                self._enqueue("log", f"[ERROR] 测试失败: {exc}")
                self._enqueue_dialog("dialog_error", "测试失败", str(exc))
            finally:
                self._enqueue("busy", False)

        threading.Thread(target=worker, daemon=True).start()

    def _on_close(self) -> None:
        terminate_process(self.web_process)
        self._detach_logging_handler()
        self.destroy()


def main() -> None:
    app = NinjemailDesktopApp()
    app.mainloop()


if __name__ == "__main__":
    main()
