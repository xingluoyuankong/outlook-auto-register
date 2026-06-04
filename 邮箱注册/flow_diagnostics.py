from __future__ import annotations

import json
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .provider_capabilities import REAL_CAPTCHA_SERVICES, REAL_SMS_SERVICES
except ImportError:
    from provider_capabilities import REAL_CAPTCHA_SERVICES, REAL_SMS_SERVICES


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTICS_DIR = PROJECT_ROOT / "diagnostics_runs"
SECRET_KEYS = {"api_key", "token", "password", "key", "webshare_token"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _compact(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).lower() in SECRET_KEYS:
                result[key] = _mask_secret(item)
            else:
                result[key] = _compact(item)
        return result
    if isinstance(value, list):
        return [_compact(item) for item in value]
    return value


def _mask_secret(value: Any) -> str:
    text = str(value or "")
    if not text:
        return "<empty>"
    if len(text) <= 8:
        return text[:1] + "***" + text[-1:]
    return text[:4] + "***" + text[-4:]


def classify_blocker(exc: BaseException | str) -> str:
    text = str(exc).lower()
    exc_name = type(exc).__name__.lower() if isinstance(exc, BaseException) else ""
    if "browser_error_page" in text or "err_timed_out" in text or "无法访问此网站" in text or "net::err_" in text:
        return "network"
    if (
        "could not reach host" in text
        or "are you offline" in text
        or "driver_download" in text
        or "unable to obtain driver" in text
        or "selenium manager" in text
        or "timed out receiving message from renderer" in text
    ):
        return "driver"
    if "no_stable_proxy" in text or "proxy" in text:
        return "proxy"
    if "captcha" in text or "solver" in text or "nopecha" in text or "capsolver" in text or "hsprotect" in text or "press-and-hold" in text:
        return "captcha"
    if "sms" in text or "phone" in text or "token" in text:
        return "sms"
    if "selector" in text or "timeout" in text or "nosuchelement" in exc_name:
        return "selector"
    if "webdriver" in text or "driver" in text or "chrome" in text or "firefox" in text:
        return "driver"
    if "unsupported" in text or "config" in text or "provider" in text:
        return "config"
    return "provider"


def repair_hint(blocker: str, reason: str) -> str:
    reason_l = str(reason or "").lower()
    if "manual_required" in reason_l or "manual_waiting" in reason_l:
        return "Visible browser is waiting at the challenge. Complete it manually; the flow will continue automatically when the challenge clears."
    if "timed out receiving message from renderer" in reason_l:
        return "浏览器页面加载卡死：优先检查代理到目标站点/验证码设置页是否可达；空 Key 的 NopeCHA 已改为跳过 setup 页。"
    if "browser_error_page" in reason_l or "err_timed_out" in reason_l:
        return "目标页面在浏览器里没有真实打开：换下当前代理、重新跑三轮稳定代理，或临时关闭“使用代理”跑 page_check 对比。"
    if "could not reach host" in reason_l or "are you offline" in reason_l or "driver_download" in reason_l:
        return "驱动下载/启动网络失败：优先使用本机已缓存的 ChromeDriver；如果仍失败，请确认系统代理 127.0.0.1:7897 可用，或把浏览器切到 chrome 后重新初始化。"
    if "no_sms_key" in reason_l or "no sms api keys" in reason_l or "sms_token_missing" in reason_l:
        return "Configure a real SMS provider. Free self-owned-device options: textbee requires device_id, API key, and phone_number; smsgate requires local server base_url, username, password/token, and phone_number."
    if "textbee" in reason_l:
        return "For TextBee, fill SMS service=textbee, username/device_id, API token, own phone number, and base_url=https://api.textbee.dev."
    if "smsgate" in reason_l:
        return "For SMSGate, start Android SMS Gateway local server, then fill service=smsgate, base_url like http://PHONE_IP:8080, username, password/token, and own phone number."
    if "captcha_key_empty" in reason_l:
        return "Use NopeCHA without a key for IP free quota, or fill a real CapSolver/NopeCHA key before real_run."
    if "hsprotect" in reason_l or "press-and-hold" in reason_l:
        return "Microsoft is showing a Human Security press-and-hold challenge. The form flow is repaired up to this point; use a captcha provider that supports this challenge or complete this verification manually."
    if "no_stable_proxy" in reason_l or blocker == "proxy":
        return "Run the stable proxy recheck and keep only proxies that pass every round, or disable proxy for a page_check."
    if blocker == "selector":
        return "Open page_check mode to capture a screenshot/current URL/title before updating selectors."
    if blocker == "driver":
        return "浏览器/驱动启动失败：本机当前可用 Chrome，未检测到 Firefox；请使用 chrome，或安装 Firefox + geckodriver 后再选 firefox。"
    return "Inspect the step details and latest screenshot/current URL in this report."


@dataclass
class FlowStep:
    name: str
    status: str = "running"
    started_at: str = field(default_factory=_now_iso)
    ended_at: str = ""
    duration_ms: int = 0
    details: dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    exception_type: str = ""
    blocker: str = ""
    screenshot_path: str = ""


class FlowRunReport:
    def __init__(
        self,
        *,
        mode: str,
        provider: str,
        config_snapshot: dict[str, Any] | None = None,
        output_dir: Path | str | None = None,
        run_id: str | None = None,
    ) -> None:
        self.mode = mode
        self.provider = provider
        safe_provider = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in provider)[:40]
        self.run_id = run_id or f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{safe_provider}"
        self.output_dir = Path(output_dir) if output_dir else DIAGNOSTICS_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.config_snapshot = _compact(config_snapshot or {})
        self.steps: list[FlowStep] = []
        self.blockers: list[dict[str, Any]] = []
        self.artifacts: list[str] = []
        self.root_cause: dict[str, Any] = {}
        self.keep_browser_open = False
        self.started_at = _now_iso()
        self.ended_at = ""
        self.status = "running"
        self._active: dict[str, float] = {}

    def start_step(self, name: str, **details: Any) -> FlowStep:
        step = FlowStep(name=name, details=_compact(details))
        self.steps.append(step)
        self._active[name] = time.perf_counter()
        return step

    def end_step(self, name: str, status: str = "ok", **details: Any) -> None:
        step = self._find_step(name)
        if step is None:
            step = self.start_step(name)
        started = self._active.pop(name, None)
        step.status = status
        step.ended_at = _now_iso()
        if started is not None:
            step.duration_ms = int((time.perf_counter() - started) * 1000)
        if details:
            step.details.update(_compact(details))

    def ok(self, name: str, **details: Any) -> None:
        self.end_step(name, "ok", **details)

    def set_root_cause(
        self,
        *,
        blocker: str,
        reason: str,
        evidence: str = "",
        next_action: str = "",
        latest_screenshot: str = "",
        details: dict[str, Any] | None = None,
        replace: bool = False,
    ) -> None:
        transient_reason = str(self.root_cause.get("reason", "")).lower() if self.root_cause else ""
        transient = any(
            token in transient_reason
            for token in ("manual_required", "manual_waiting", "manual_takeover_cleared")
        )
        if self.root_cause and not replace and not transient:
            if latest_screenshot:
                self.root_cause["latest_screenshot"] = latest_screenshot
            return
        self.root_cause = {
            "blocker": blocker,
            "reason": reason,
            "evidence": evidence,
            "next_action": next_action or repair_hint(blocker, reason),
            "latest_screenshot": latest_screenshot,
            "details": _compact(details or {}),
        }

    def block(self, name: str, reason: str, *, blocker: str | None = None, **details: Any) -> None:
        step = self._find_step(name)
        if step is None:
            step = self.start_step(name)
        self.end_step(name, "block", **details)
        step.reason = reason
        step.blocker = blocker or classify_blocker(reason)
        self.set_root_cause(
            blocker=step.blocker,
            reason=reason,
            evidence=str(details.get("evidence") or details.get("challenge") or ""),
            next_action=repair_hint(step.blocker, reason),
            latest_screenshot=str(details.get("screenshot") or details.get("screenshot_path") or ""),
            details=details,
        )
        self.blockers.append(
            {
                "step": name,
                "blocker": step.blocker,
                "reason": reason,
                "repair_hint": repair_hint(step.blocker, reason),
                "details": _compact(details),
            }
        )
        self.status = "blocked"

    def fail(self, name: str, exc: BaseException, *, blocker: str | None = None, **details: Any) -> None:
        step = self._find_step(name)
        if step is None:
            step = self.start_step(name)
        self.end_step(name, "fail", **details)
        step.exception_type = type(exc).__name__
        step.reason = str(exc)
        step.blocker = blocker or classify_blocker(exc)
        self.set_root_cause(
            blocker=step.blocker,
            reason=step.reason,
            evidence=str(details.get("evidence") or ""),
            next_action=repair_hint(step.blocker, step.reason),
            latest_screenshot=str(details.get("screenshot") or details.get("screenshot_path") or ""),
            details=details,
        )
        self.blockers.append(
            {
                "step": name,
                "blocker": step.blocker,
                "exception_type": step.exception_type,
                "reason": step.reason,
                "repair_hint": repair_hint(step.blocker, step.reason),
                "details": _compact(details),
                "traceback": traceback.format_exception_only(type(exc), exc)[-1].strip(),
            }
        )
        self.status = "failed"
        self._close_active_steps(status="fail", reason=step.reason, exception_type=step.exception_type, blocker=step.blocker)

    def fail_step(self, name: str, exc: BaseException, *, blocker: str | None = None, **details: Any) -> None:
        step = self._find_step(name)
        if step is None:
            step = self.start_step(name)
        self.end_step(name, "fail", **details)
        step.exception_type = type(exc).__name__
        step.reason = str(exc)
        step.blocker = blocker or classify_blocker(exc)

    def capture_screenshot(self, driver: Any, label: str) -> str:
        safe_label = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in label)[:80]
        path = self.output_dir / f"flow_run_{self.run_id}_{safe_label}.png"
        try:
            driver.save_screenshot(str(path))
            self.artifacts.append(str(path))
            step = self.steps[-1] if self.steps else None
            if step:
                step.screenshot_path = str(path)
            if self.root_cause and not self.root_cause.get("latest_screenshot"):
                self.root_cause["latest_screenshot"] = str(path)
            return str(path)
        except Exception as exc:
            self.blockers.append(
                {
                    "step": label,
                    "blocker": "screenshot",
                    "reason": f"screenshot_failed: {type(exc).__name__}: {exc}",
                }
            )
            return ""

    def finish(self, status: str | None = None) -> None:
        if status:
            self.status = status
        elif self.status == "running":
            self.status = "ok"
        if self._active:
            close_status = "fail" if self.status == "failed" else "block" if self.status == "blocked" else "ok"
            self._close_active_steps(
                status=close_status,
                reason="run_finished_with_open_step",
                exception_type="",
                blocker="" if close_status == "ok" else "flow",
                add_blockers=close_status != "ok",
            )
        for step in self.steps:
            if step.status == "running":
                step.status = "fail" if self.status == "failed" else "block" if self.status == "blocked" else "ok"
                step.ended_at = _now_iso()
                step.reason = step.reason or "run_finished_with_open_step"
                step.blocker = step.blocker or ("" if step.status == "ok" else "flow")
        self.ended_at = _now_iso()

    def save_json(self) -> Path:
        if not self.ended_at:
            self.finish()
        path = self.output_dir / f"flow_run_{self.run_id}.json"
        payload = self.to_dict()
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        return path

    def save_markdown(self) -> Path:
        if not self.ended_at:
            self.finish()
        path = self.output_dir / f"flow_run_{self.run_id}.md"
        lines = [
            f"# Flow Run {self.run_id}",
            "",
            f"- mode: `{self.mode}`",
            f"- provider: `{self.provider}`",
            f"- status: `{self.status}`",
            f"- started_at: `{self.started_at}`",
            f"- ended_at: `{self.ended_at}`",
            "",
            "## Root Cause",
            "",
        ]
        if self.root_cause:
            lines.extend(
                [
                    f"- blocker: `{self.root_cause.get('blocker', '')}`",
                    f"- reason: {self.root_cause.get('reason', '')}",
                    f"- evidence: {self.root_cause.get('evidence', '')}",
                    f"- next_action: {self.root_cause.get('next_action', '')}",
                    f"- latest_screenshot: `{self.root_cause.get('latest_screenshot', '')}`",
                    "",
                ]
            )
        else:
            lines.extend(["- none", ""])
        lines.extend(
            [
            "## Steps",
            "",
            ]
        )
        for index, step in enumerate(self.steps, 1):
            suffix = f" reason={step.reason}" if step.reason else ""
            lines.append(
                f"{index}. `{step.name}` status=`{step.status}` duration_ms=`{step.duration_ms}` blocker=`{step.blocker}`{suffix}"
            )
            if step.screenshot_path:
                lines.append(f"   screenshot: `{step.screenshot_path}`")
        lines.extend(["", "## Blockers", ""])
        if self.blockers:
            for blocker in self.blockers:
                lines.append(
                    f"- `{blocker.get('blocker')}` at `{blocker.get('step')}`: {blocker.get('reason')}"
                )
                if blocker.get("repair_hint"):
                    lines.append(f"  repair: {blocker.get('repair_hint')}")
        else:
            lines.append("- none")
        lines.extend(
            [
                "",
                "## Real Creation Providers",
                "",
                f"- captcha: `{', '.join(REAL_CAPTCHA_SERVICES)}`",
                f"- sms: `{', '.join(REAL_SMS_SERVICES)}`",
                "",
            ]
        )
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def save_all(self) -> tuple[Path, Path]:
        self.finish()
        return self.save_json(), self.save_markdown()

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "mode": self.mode,
            "provider": self.provider,
            "status": self.status,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "config_snapshot": self.config_snapshot,
            "root_cause": self.root_cause,
            "keep_browser_open": self.keep_browser_open,
            "steps": [step.__dict__ for step in self.steps],
            "blockers": self.blockers,
            "artifacts": self.artifacts,
        }

    def _find_step(self, name: str) -> FlowStep | None:
        for step in reversed(self.steps):
            if step.name == name and step.status == "running":
                return step
        for step in reversed(self.steps):
            if step.name == name:
                return step
        return None

    def _close_active_steps(
        self,
        *,
        status: str,
        reason: str,
        exception_type: str = "",
        blocker: str = "",
        add_blockers: bool = True,
    ) -> None:
        for active_name in list(self._active.keys()):
            step = self._find_step(active_name)
            if step is None or step.status != "running":
                self._active.pop(active_name, None)
                continue
            self.end_step(active_name, status)
            step.reason = reason
            step.exception_type = exception_type
            step.blocker = blocker or classify_blocker(reason)
            if add_blockers:
                self.blockers.append(
                    {
                        "step": active_name,
                        "blocker": step.blocker,
                        "exception_type": exception_type,
                        "reason": reason,
                        "repair_hint": repair_hint(step.blocker, reason),
                        "details": _compact(step.details),
                    }
                )
