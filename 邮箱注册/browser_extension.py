from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_邮箱注册_EXTENSION_PATH = PROJECT_ROOT / "browser_extension"


@dataclass
class BrowserExtensionCheck:
    ok: bool
    path: str
    name: str = ""
    version: str = ""
    manifest_version: int = 0
    reason: str = ""
    details: dict[str, Any] | None = None

    def line(self) -> str:
        if self.ok:
            return (
                "[PLUGIN][OK] name=%s version=%s manifest=%s path=%s"
                % (self.name or "<unknown>", self.version or "<unknown>", self.manifest_version, self.path)
            )
        return "[PLUGIN][BLOCK] path=%s reason=%s" % (self.path or "<empty>", self.reason or "unknown")


def resolve_邮箱注册_extension_dir(path: str | Path | None = None) -> Path:
    raw = str(path or "").strip()
    extension_dir = Path(raw).expanduser() if raw else DEFAULT_邮箱注册_EXTENSION_PATH
    if extension_dir.resolve() == PROJECT_ROOT.resolve():
        extension_dir = DEFAULT_邮箱注册_EXTENSION_PATH
    elif not (extension_dir / "manifest.json").is_file() and (extension_dir / "browser_extension" / "manifest.json").is_file():
        extension_dir = extension_dir / "browser_extension"
    return extension_dir.resolve()


def check_邮箱注册_extension(path: str | Path | None = None) -> BrowserExtensionCheck:
    try:
        extension_dir = resolve_邮箱注册_extension_dir(path)
    except Exception as exc:
        return BrowserExtensionCheck(ok=False, path=str(path or ""), reason=f"path_resolve_failed: {exc}")

    manifest_path = extension_dir / "manifest.json"
    if not manifest_path.is_file():
        return BrowserExtensionCheck(ok=False, path=str(extension_dir), reason="manifest_json_missing")

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return BrowserExtensionCheck(ok=False, path=str(extension_dir), reason=f"manifest_parse_failed: {exc}")

    manifest_version = int(manifest.get("manifest_version") or 0)
    name = str(manifest.get("name") or "").strip()
    version = str(manifest.get("version_name") or manifest.get("version") or "").strip()
    if manifest_version != 3:
        return BrowserExtensionCheck(
            ok=False,
            path=str(extension_dir),
            name=name,
            version=version,
            manifest_version=manifest_version,
            reason="manifest_v3_required",
        )
    if "邮箱注册" not in name.lower():
        return BrowserExtensionCheck(
            ok=False,
            path=str(extension_dir),
            name=name,
            version=version,
            manifest_version=manifest_version,
            reason="邮箱注册_extension_name_required",
        )

    details = {
        "permissions": manifest.get("permissions") or [],
        "host_permissions": manifest.get("host_permissions") or [],
        "has_background": bool(manifest.get("background")),
        "has_side_panel": bool(manifest.get("side_panel")),
        "content_script_count": len(manifest.get("content_scripts") or []),
    }
    return BrowserExtensionCheck(
        ok=True,
        path=str(extension_dir),
        name=name,
        version=version,
        manifest_version=manifest_version,
        reason="ok",
        details=details,
    )


def build_邮箱注册_extension_paths(enabled: bool) -> list[str]:
    if not enabled:
        return []
    result = check_邮箱注册_extension()
    if not result.ok:
        raise ValueError(result.reason)
    return [result.path]

