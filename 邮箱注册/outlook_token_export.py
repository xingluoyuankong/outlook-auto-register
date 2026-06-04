from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
import time
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "created_accounts"
DEFAULT_TOKEN_TOOL_DIR = Path(r"C:\Users\XZXyuan\Downloads\outlook-token-tool")
BUILTIN_CLIENT_ID = "14d82eec-204b-4c2f-b7e8-296a70dab67e"


@dataclass
class ComboSaveResult:
    ok: bool
    combo_path: str
    event_path: str
    line: str
    reason: str = "ok"


@dataclass
class TokenExportJob:
    ok: bool
    status: str
    pid: int | None = None
    log_path: str = ""
    reason: str = ""
    auth_url: str = ""


ACTIVE_TOKEN_JOBS: dict[str, "TokenExportJob"] = {}
ACTIVE_TOKEN_JOBS_LOCK = threading.Lock()


def safe_filename(value: str | None) -> str:
    raw = (value or "outlook").strip().lower()
    raw = re.sub(r"[^a-z0-9@._-]+", "_", raw)
    return raw.strip("._-") or "outlook"


def normalize_email(email: str | None) -> str:
    return (email or "").strip().lower()


def output_dir(path: str | Path | None = None) -> Path:
    target = Path(path).expanduser() if path else DEFAULT_OUTPUT_DIR
    target.mkdir(parents=True, exist_ok=True)
    return target


def combo_line(
    email: str,
    password: str,
    client_id: str = BUILTIN_CLIENT_ID,
    refresh_token: str = "",
) -> str:
    return f"{normalize_email(email)}----{password or ''}----{client_id or BUILTIN_CLIENT_ID}----{refresh_token or ''}"


def _read_combo_lines(path: Path) -> list[str]:
    if not path.is_file():
        return []
    return [line.rstrip("\n") for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _line_email(line: str) -> str:
    return normalize_email(line.split("----", 1)[0])


def _line_has_refresh_token(line: str) -> bool:
    parts = line.split("----")
    return len(parts) >= 4 and bool(parts[3].strip())


def credential_file_for(email: str, out_dir: str | Path | None = None) -> Path:
    return output_dir(out_dir) / f"{safe_filename(email)}.txt"


def matching_credential_files(email: str, out_dir: str | Path | None = None) -> list[Path]:
    folder = output_dir(out_dir)
    safe = safe_filename(email)
    matches: list[Path] = []
    base = folder / f"{safe}.txt"
    if base.is_file():
        matches.append(base)
    suffixed = sorted(
        (path for path in folder.glob(f"{safe}__*.txt") if path.is_file()),
        key=lambda path: (path.stat().st_mtime, path.name.lower()),
        reverse=True,
    )
    seen: set[Path] = set()
    ordered: list[Path] = []
    for path in [*matches, *suffixed]:
        if path in seen:
            continue
        seen.add(path)
        ordered.append(path)
    return ordered


def locate_credential_file(email: str, out_dir: str | Path | None = None) -> Path | None:
    matches = matching_credential_files(email, out_dir)
    return matches[0] if matches else None


def save_combo(
    email: str,
    password: str,
    *,
    client_id: str = BUILTIN_CLIENT_ID,
    refresh_token: str = "",
    out_dir: str | Path | None = None,
    source: str = "邮箱注册",
    final_state: str = "",
    url: str = "",
) -> ComboSaveResult:
    email = normalize_email(email)
    if not email or "@" not in email:
        return ComboSaveResult(False, "", "", "", "invalid_email")

    combo_path = credential_file_for(email, out_dir)
    new_line = combo_line(email, password, client_id, refresh_token)
    existing_lines = _read_combo_lines(combo_path)
    existing_line = existing_lines[0] if existing_lines else ""
    if not refresh_token:
        if existing_line and _line_has_refresh_token(existing_line):
            return ComboSaveResult(True, str(combo_path), "", existing_line, "existing_refresh_kept")
        return ComboSaveResult(True, str(combo_path), "", new_line, "pending_refresh_token")
    combo_path.write_text(new_line + "\n", encoding="utf-8")
    return ComboSaveResult(True, str(combo_path), "", new_line)


def token_file_for(email: str, out_dir: str | Path | None = None) -> Path:
    return output_dir(out_dir) / f"tokens_{safe_filename(email)}.json"


def token_artifact_paths(email: str, out_dir: str | Path | None = None) -> dict[str, Path]:
    return {"credential_path": credential_file_for(email, out_dir)}


def _env_value(value: Any) -> str:
    return json.dumps(str(value or ""), ensure_ascii=False)


def save_token_artifacts(
    email: str,
    password: str,
    *,
    client_id: str = BUILTIN_CLIENT_ID,
    refresh_token: str = "",
    access_token: str = "",
    expires_in: str | int = "",
    token_type: str = "",
    scope: str = "",
    out_dir: str | Path | None = None,
) -> dict[str, str]:
    email = normalize_email(email)
    if not email or "@" not in email or not refresh_token:
        return {}

    result = save_combo(
        email,
        password,
        client_id=client_id,
        refresh_token=refresh_token,
        out_dir=out_dir,
        source="token_artifacts",
        final_state="token_exported",
    )
    return {"credential_path": result.combo_path, "combo_path": result.combo_path} if result.ok else {}


def _read_refresh_token(email: str, out_dir: str | Path | None = None) -> str:
    path = token_file_for(email, out_dir)
    if not path.is_file():
        return ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    return str(data.get("refresh_token") or "").strip()


def _cleanup_token_tool_artifacts(email: str, out_dir: Path, log_path: Path | None = None) -> None:
    safe = safe_filename(email)
    targets = [
        out_dir / f"tokens_{safe}.json",
        out_dir / f"tokens_{safe}.env",
        out_dir / f"tokens_{safe}_combo.txt",
    ]
    if log_path:
        targets.append(log_path)
    for path in targets:
        try:
            if path.is_file():
                path.unlink()
        except Exception:
            pass


def _reader_token_tool_output(
    process: subprocess.Popen[Any],
    log_path: Path,
    auth_url_holder: dict[str, str],
    auth_url_ready: threading.Event,
) -> None:
    try:
      with log_path.open("a", encoding="utf-8") as log_handle:
        stdout = process.stdout
        if stdout is None:
            return
        for line in stdout:
            text = str(line)
            log_handle.write(text)
            log_handle.flush()
            stripped = text.strip()
            if "oauth2/v2.0/authorize?" in stripped and stripped.startswith("https://login.microsoftonline.com/"):
                auth_url_holder["auth_url"] = stripped
                auth_url_ready.set()
    finally:
        auth_url_ready.set()


def _monitor_token_export(
    process: subprocess.Popen[Any],
    email: str,
    password: str,
    client_id: str,
    out_dir: Path,
    log_path: Path,
    timeout_seconds: int,
) -> None:
    deadline = time.time() + timeout_seconds + 30
    while time.time() < deadline:
        refresh = _read_refresh_token(email, out_dir)
        if refresh:
            save_combo(
                email,
                password,
                client_id=client_id,
                refresh_token=refresh,
                out_dir=out_dir,
                source="outlook-token-tool",
                final_state="token_exported",
            )
            _cleanup_token_tool_artifacts(email, out_dir, log_path)
            with ACTIVE_TOKEN_JOBS_LOCK:
                ACTIVE_TOKEN_JOBS.pop(email, None)
            return
        if process.poll() is not None:
            break
        time.sleep(2)

    refresh = _read_refresh_token(email, out_dir)
    if refresh:
        save_combo(
            email,
            password,
            client_id=client_id,
            refresh_token=refresh,
            out_dir=out_dir,
            source="outlook-token-tool",
            final_state="token_exported",
        )
    _cleanup_token_tool_artifacts(email, out_dir, log_path)
    with ACTIVE_TOKEN_JOBS_LOCK:
        ACTIVE_TOKEN_JOBS.pop(email, None)


def start_token_export(
    email: str,
    password: str,
    *,
    client_id: str = BUILTIN_CLIENT_ID,
    out_dir: str | Path | None = None,
    token_tool_dir: str | Path | None = None,
    timeout_seconds: int = 600,
) -> TokenExportJob:
    email = normalize_email(email)
    if not email or "@" not in email:
        return TokenExportJob(False, "not_started", reason="invalid_email")
    tool_dir = Path(token_tool_dir).expanduser() if token_tool_dir else DEFAULT_TOKEN_TOOL_DIR
    script = tool_dir / "get_outlook_token.py"
    if not script.is_file():
        return TokenExportJob(False, "not_started", reason=f"token_tool_missing: {script}")

    with ACTIVE_TOKEN_JOBS_LOCK:
        existing = ACTIVE_TOKEN_JOBS.get(email)
        if existing and existing.pid:
            return existing

    target_dir = output_dir(out_dir)
    log_path = target_dir / f"outlook_token_export_{safe_filename(email)}_{int(time.time())}.log"
    cmd = [
        sys.executable,
        str(script),
        "--account-email",
        email,
        "--account-password",
        password or "",
        "--output-dir",
        str(target_dir),
        "--timeout",
        str(timeout_seconds),
        "--no-open",
    ]
    if client_id and client_id != BUILTIN_CLIENT_ID:
        cmd.extend(["--client-id", client_id])

    log_path.write_text("", encoding="utf-8")
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    process = subprocess.Popen(
        cmd,
        cwd=str(tool_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        creationflags=creationflags,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    auth_url_holder: dict[str, str] = {}
    auth_url_ready = threading.Event()
    reader = threading.Thread(
        target=_reader_token_tool_output,
        args=(process, log_path, auth_url_holder, auth_url_ready),
        daemon=True,
    )
    reader.start()
    auth_url_ready.wait(timeout=8)
    auth_url = auth_url_holder.get("auth_url", "")

    thread = threading.Thread(
        target=_monitor_token_export,
        args=(process, email, password, client_id or BUILTIN_CLIENT_ID, target_dir, log_path, timeout_seconds),
        daemon=True,
    )
    thread.start()
    status = "started" if auth_url else "started_without_auth_url"
    job = TokenExportJob(True, status, pid=process.pid, log_path=str(log_path), auth_url=auth_url)
    with ACTIVE_TOKEN_JOBS_LOCK:
        ACTIVE_TOKEN_JOBS[email] = job
    return job


def save_created_outlook_account(
    email: str,
    password: str,
    *,
    client_id: str = BUILTIN_CLIENT_ID,
    access_token: str = "",
    refresh_token: str = "",
    expires_in: str | int = "",
    token_type: str = "",
    scope: str = "",
    out_dir: str | Path | None = None,
    source: str = "邮箱注册",
    final_state: str = "",
    url: str = "",
    start_token_job: bool = False,
) -> dict[str, Any]:
    saved = save_combo(
        email,
        password,
        client_id=client_id,
        refresh_token=refresh_token,
        out_dir=out_dir,
        source=source,
        final_state=final_state,
        url=url,
    )
    token_job = TokenExportJob(False, "not_requested")
    if saved.ok and start_token_job and not refresh_token:
        token_job = TokenExportJob(False, "not_started", reason="plugin_integrated_oauth_only")
    return {
        "ok": saved.ok,
        "reason": saved.reason,
        "credential_path": saved.combo_path,
        "combo_path": saved.combo_path,
        "client_id": client_id or BUILTIN_CLIENT_ID,
        "has_refresh_token": bool(refresh_token),
        "token_job": token_job.__dict__,
    }

