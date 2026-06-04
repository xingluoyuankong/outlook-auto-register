from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any


logger = logging.getLogger(__name__)


CAPTCHA_PROVIDER_CAPABILITIES: dict[str, set[str]] = {
    "nopecha": {"recaptcha", "hcaptcha", "funcaptcha", "turnstile", "aws_waf", "image", "text"},
    "capsolver": {"recaptcha", "hcaptcha", "funcaptcha", "turnstile", "aws_waf", "cloudflare", "image"},
    "capmonster": {"recaptcha", "hcaptcha", "funcaptcha", "turnstile", "image"},
    "anti_captcha": {"recaptcha", "hcaptcha", "funcaptcha", "turnstile", "image"},
    "2captcha": {"recaptcha", "hcaptcha", "funcaptcha", "turnstile", "image"},
    "yescaptcha": {"recaptcha", "hcaptcha", "funcaptcha", "turnstile", "image"},
}


@dataclass
class ChallengeInfo:
    kind: str
    label: str
    evidence: str
    current_url: str = ""
    title: str = ""
    iframe_sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "label": self.label,
            "evidence": self.evidence,
            "current_url": self.current_url,
            "title": self.title,
            "iframe_sources": self.iframe_sources,
        }


def provider_supports_challenge(provider: str, challenge_kind: str) -> bool:
    provider = str(provider or "").strip().lower()
    challenge_kind = str(challenge_kind or "").strip().lower()
    return challenge_kind in CAPTCHA_PROVIDER_CAPABILITIES.get(provider, set())


def _body_text(driver: Any) -> str:
    try:
        return str(driver.execute_script("return document.body ? document.body.innerText : ''") or "")
    except Exception:
        try:
            return str(driver.page_source or "")
        except Exception:
            return ""


def _iframe_infos(driver: Any) -> list[dict[str, Any]]:
    try:
        frames = driver.execute_script(
            """
            return [...document.querySelectorAll('iframe')].map((frame) => {
              const style = window.getComputedStyle(frame);
              const rect = frame.getBoundingClientRect();
              const visible = style.display !== 'none'
                && style.visibility !== 'hidden'
                && Number(style.opacity || 1) !== 0
                && rect.width > 80
                && rect.height > 50;
              return {
                text: `${frame.title || ''} ${frame.name || ''} ${frame.id || ''} ${frame.src || ''}`,
                visible
              };
            });
            """
        )
        result = []
        for item in frames or []:
            if isinstance(item, dict):
                result.append({"text": str(item.get("text") or ""), "visible": bool(item.get("visible"))})
            else:
                result.append({"text": str(item or ""), "visible": False})
        return result
    except Exception:
        return []


def _iframe_sources(driver: Any) -> list[str]:
    return [item["text"] for item in _iframe_infos(driver)]


def detect_challenge(driver: Any) -> ChallengeInfo | None:
    current_url = ""
    title = ""
    try:
        current_url = str(getattr(driver, "current_url", "") or "")
    except Exception:
        pass
    try:
        title = str(getattr(driver, "title", "") or "")
    except Exception:
        pass
    body = _body_text(driver)
    iframe_infos = _iframe_infos(driver)
    iframe_sources = [item["text"] for item in iframe_infos]
    visible_iframe_sources = [item["text"] for item in iframe_infos if item["visible"]]
    visible_haystack = "\n".join([current_url, title, body, *visible_iframe_sources]).lower()
    haystack = "\n".join([current_url, title, body, *iframe_sources]).lower()

    hsprotect_visible = "hsprotect" in visible_haystack or "human iframe" in visible_haystack
    hsprotect_top = "hsprotect.net" in str(current_url).lower()
    hsprotect_text = "press and hold" in visible_haystack or "prove you're human" in visible_haystack
    if hsprotect_top or hsprotect_text or hsprotect_visible:
        evidence = "press and hold the button" if hsprotect_text else "visible hsprotect frame"
        return ChallengeInfo(
            kind="hsprotect",
            label="HUMAN Security press-and-hold",
            evidence=evidence,
            current_url=current_url,
            title=title,
            iframe_sources=iframe_sources[:8],
        )

    markers: list[tuple[str, str, tuple[str, ...]]] = [
        ("funcaptcha", "Arkose/FunCaptcha", ("arkose", "funcaptcha", "game-core-frame")),
        ("recaptcha", "reCAPTCHA", ("recaptcha", "g-recaptcha")),
        ("hcaptcha", "hCaptcha", ("hcaptcha", "h-captcha")),
        ("turnstile", "Cloudflare Turnstile", ("challenges.cloudflare.com", "cf-turnstile", "turnstile")),
        ("aws_waf", "AWS WAF CAPTCHA", ("awswaf", "amzn-captcha", "aws waf")),
        ("image", "image captcha", ("captcha", "enter the characters", "type the characters")),
    ]
    for kind, label, tokens in markers:
        for token in tokens:
            if token in haystack:
                evidence = token
                if kind == "hsprotect" and "press and hold" in haystack:
                    evidence = "press and hold the button"
                return ChallengeInfo(
                    kind=kind,
                    label=label,
                    evidence=evidence,
                    current_url=current_url,
                    title=title,
                    iframe_sources=iframe_sources[:8],
                )
    return None


def wait_for_manual_takeover(
    driver: Any,
    report: Any,
    *,
    provider: str,
    challenge: ChallengeInfo,
    captcha_provider: str = "",
    timeout_seconds: int = 600,
    poll_seconds: float = 2.0,
) -> None:
    supported = provider_supports_challenge(captcha_provider, challenge.kind)
    start_time = time.monotonic()
    details = {
        **challenge.to_dict(),
        "captcha_provider": captcha_provider or "<none>",
        "provider_supported": supported,
        "action": "manual_waiting",
        "timeout_seconds": timeout_seconds,
        "manual_wait_seconds": 0,
    }
    screenshot = ""
    if report:
        screenshot = report.capture_screenshot(driver, f"{provider}.challenge_{challenge.kind}")
        details["screenshot"] = screenshot
        reason = f"manual_required: {challenge.kind}"
        report.block(f"{provider}.{challenge.kind}_manual_wait", reason, blocker="captcha", **details)
        report.set_root_cause(
            blocker="captcha",
            reason=reason,
            evidence=challenge.evidence,
            next_action="Waiting for the visible challenge to be completed manually; the flow will continue automatically.",
            latest_screenshot=screenshot,
            details=details,
            replace=True,
        )
        report.keep_browser_open = True

    logger.warning(
        "[BLOCK] provider=%s challenge=%s action=hsprotect_manual_wait evidence=%s screenshot=%s",
        provider,
        challenge.kind,
        challenge.evidence,
        screenshot or "<none>",
    )
    logger.info("[NEXT] Complete the visible challenge manually; polling continues for %ss.", timeout_seconds)

    if report:
        report.start_step(f"{provider}.manual_takeover", challenge=challenge.kind, timeout_seconds=timeout_seconds)

    deadline = time.monotonic() + max(1, timeout_seconds)
    while time.monotonic() < deadline:
        time.sleep(max(0.2, poll_seconds))
        elapsed = int(time.monotonic() - start_time)
        remaining = max(0, int(deadline - time.monotonic()))
        if report and report.root_cause:
            report.root_cause["details"] = {
                **(report.root_cause.get("details") or {}),
                "manual_wait_seconds": elapsed,
                "remaining_seconds": remaining,
                "last_url": str(getattr(driver, "current_url", "") or ""),
                "last_title": str(getattr(driver, "title", "") or ""),
            }
        latest = detect_challenge(driver)
        if latest is None or latest.kind != challenge.kind:
            if report:
                report.keep_browser_open = False
                report.status = "running"
                waited = int(time.monotonic() - start_time)
                report.ok(
                    f"{provider}.manual_takeover",
                    action="challenge_cleared",
                    manual_wait_seconds=waited,
                    last_url=str(getattr(driver, "current_url", "") or ""),
                    last_title=str(getattr(driver, "title", "") or ""),
                )
                report.set_root_cause(
                    blocker="captcha",
                    reason=f"manual_takeover_cleared: {challenge.kind}",
                    evidence=challenge.evidence,
                    next_action="Continuing Outlook post-challenge checks.",
                    latest_screenshot=screenshot,
                    details={
                        **details,
                        "manual_wait_seconds": waited,
                        "last_url": str(getattr(driver, "current_url", "") or ""),
                        "last_title": str(getattr(driver, "title", "") or ""),
                    },
                    replace=True,
                )
            logger.info("[OK] provider=%s challenge=%s action=challenge_cleared", provider, challenge.kind)
            return

    if report:
        screenshot = report.capture_screenshot(driver, f"{provider}.manual_takeover_timeout")
        waited = int(time.monotonic() - start_time)
        report.block(
            f"{provider}.manual_takeover",
            f"manual_takeover_timeout challenge={challenge.kind}",
            blocker="captcha",
            screenshot=screenshot,
            manual_wait_seconds=waited,
            last_url=str(getattr(driver, "current_url", "") or ""),
            last_title=str(getattr(driver, "title", "") or ""),
        )
        report.keep_browser_open = True
    raise TimeoutError(f"manual_takeover_timeout challenge={challenge.kind}")
