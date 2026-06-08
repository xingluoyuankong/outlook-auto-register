#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import json, datetime as dt, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "runtime_outlook" / "results.jsonl"
RESULTS2 = ROOT / "自动化定时注册Outlook邮箱" / "runtime_outlook" / "results.jsonl"
CLOUD = ROOT / "云端注册邮箱"
THREE = CLOUD / "三凭证"
FOUR = CLOUD / "四凭证"
ALL = CLOUD / "all_success.jsonl"
CLIENT_ID_DEFAULT = "14d82eec-204b-4c2f-b7e8-296a70dab67e"

def safe_name(email: str) -> str:
    return email.replace("@", "_at_").replace("/", "_") + ".txt"

def load_existing_emails() -> set[str]:
    emails = set()
    if ALL.exists():
        for line in ALL.read_text(encoding="utf-8").splitlines():
            try:
                d = json.loads(line)
                if d.get("email"):
                    emails.add(d["email"])
            except Exception:
                pass
    return emails

def load_existing_rt_status() -> dict[str, bool]:
    """Return {email: has_refresh_token} from all_success.jsonl."""
    status = {}
    if ALL.exists():
        for line in ALL.read_text(encoding="utf-8").splitlines():
            try:
                d = json.loads(line)
                if d.get("email"):
                    status[d["email"]] = bool(d.get("has_refresh_token"))
            except Exception:
                pass
    return status

RT_DIR = ROOT / "runtime_outlook" / "rt_tokens"

def load_rt_tokens() -> dict[str, tuple[str, str, str]]:
    """Scan rt_tokens/ directory for all RT files. Returns {email: (password, client_id, rt)}."""
    result = {}
    if not RT_DIR.exists():
        return result
    for f in RT_DIR.glob("*.txt"):
        try:
            content = f.read_text(encoding="utf-8").strip()
            parts = content.split("----")
            if len(parts) >= 4 and parts[3].strip() and len(parts[3].strip()) > 20:
                result[parts[0].strip()] = (parts[1].strip(), parts[2].strip(), parts[3].strip())
        except Exception:
            pass
    return result

def update_jsonl_record(email: str, has_rt: bool) -> None:
    """Update has_refresh_token for an existing record in all_success.jsonl."""
    if not ALL.exists():
        return
    lines = ALL.read_text(encoding="utf-8").splitlines()
    changed = False
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("email") == email and not d.get("has_refresh_token") and has_rt:
            d["has_refresh_token"] = True
            lines[i] = json.dumps(d, ensure_ascii=False)
            changed = True
    if changed:
        ALL.write_text("\n".join(lines) + "\n", encoding="utf-8")

def main(push: bool = False):
    CLOUD.mkdir(parents=True, exist_ok=True)
    THREE.mkdir(parents=True, exist_ok=True)
    FOUR.mkdir(parents=True, exist_ok=True)
    existing = load_existing_emails()
    rt_status = load_existing_rt_status()
    added = []
    upgraded = []
    all_results = []
    for rf in [RESULTS, RESULTS2]:
        if rf.exists():
            all_results.extend(rf.read_text(encoding="utf-8").splitlines())
    if not all_results:
        print("no results file")
    for line in all_results:
        if not line.strip():
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        if not d.get("success") or not d.get("email") or not d.get("password"):
            continue
        email = d["email"].strip()
        ts = d.get("ts") or dt.datetime.now().isoformat()
        day = ts[:10]
        client_id = d.get("client_id") or CLIENT_ID_DEFAULT
        rt = d.get("refresh_token") or ""
        if email in existing:
            # 三凭证→三凭证: skip, 四凭证→四凭证: skip
            # 四凭证→三凭证: upgrade
            if rt and not rt_status.get(email, False):
                four_dir = FOUR / day
                four_dir.mkdir(parents=True, exist_ok=True)
                (four_dir / safe_name(email)).write_text(f"{email}----{d['password']}----{client_id}----{rt}\n", encoding="utf-8")
                # Clean up 三凭证 if exists
                for td in THREE.iterdir():
                    tf = td / safe_name(email)
                    if tf.exists():
                        tf.unlink()
                update_jsonl_record(email, True)
                rt_status[email] = True
                upgraded.append(email)
            continue
        three_dir = THREE / day
        four_dir = FOUR / day
        three_dir.mkdir(parents=True, exist_ok=True)
        four_dir.mkdir(parents=True, exist_ok=True)
        if rt:
            # Has RT → only write 四凭证, skip 三凭证
            (four_dir / safe_name(email)).write_text(f"{email}----{d['password']}----{client_id}----{rt}\n", encoding="utf-8")
        else:
            # No RT → write 三凭证 only
            (three_dir / safe_name(email)).write_text(f"{email}----{d['password']}----{client_id}\n", encoding="utf-8")
        record = {"ts": ts, "email": email, "password": d["password"], "client_id": client_id, "has_refresh_token": bool(rt), "source": "runtime_outlook/results.jsonl"}
        with ALL.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        existing.add(email)
        added.append(email)

    # Also scan rt_tokens/ for any RT files not yet reflected in 四凭证/ or all_success.jsonl
    rt_tokens = load_rt_tokens()
    for email, (pw, cid, token) in rt_tokens.items():
        if not rt_status.get(email, False):
            # This email has an RT file but all_success.jsonl says no RT → upgrade
            day = dt.datetime.now().strftime("%Y-%m-%d")
            four_dir = FOUR / day
            four_dir.mkdir(parents=True, exist_ok=True)
            (four_dir / safe_name(email)).write_text(f"{email}----{pw}----{cid}----{token}\n", encoding="utf-8")
            # Clean up 三凭证 if exists
            for td in THREE.iterdir():
                tf = td / safe_name(email)
                if tf.exists():
                    tf.unlink()
            update_jsonl_record(email, True)
            rt_status[email] = True
            upgraded.append(email)

    readme = CLOUD / "README.md"
    if not readme.exists():
        readme.write_text("# 云端注册邮箱\n\n私有仓库：保存 Outlook 注册成功后的三凭证/四凭证。\n\n- 三凭证：`email----password----client_id`\n- 四凭证：`email----password----client_id----refresh_token`\n", encoding="utf-8")
    print(f"added={len(added)}")
    for e in added:
        print(e)
    if upgraded:
        print(f"upgraded={len(upgraded)} (三凭证→四凭证)")
        for e in upgraded:
            print(f"  {e}")
    if push:
        # Initialize git repo if not exists
        git_dir = CLOUD / ".git"
        if not git_dir.exists():
            subprocess.run(["git", "-C", str(CLOUD), "init"], check=False)
            subprocess.run(["git", "-C", str(CLOUD), "remote", "add", "origin",
                           "https://github.com/xingluoyuankong/cloud-register-email.git"], check=False)
        subprocess.run(["git", "-C", str(CLOUD), "add", "."], check=True)
        staged = subprocess.check_output(["git", "-C", str(CLOUD), "diff", "--cached", "--name-only"], text=True)
        if staged.strip():
            msg = "sync registered outlook credentials " + dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            subprocess.run(["git", "-C", str(CLOUD), "commit", "-m", msg], check=True)
            # pull --rebase before push to avoid rejection
            subprocess.run(["git", "-C", str(CLOUD), "stash"], check=False)
            subprocess.run(["git", "-C", str(CLOUD), "pull", "--rebase", "-X", "ours"], check=False)
            subprocess.run(["git", "-C", str(CLOUD), "stash", "pop"], check=False)
            r = subprocess.run(["git", "-C", str(CLOUD), "push"], check=False)
            if r.returncode != 0:
                subprocess.run(["git", "-C", str(CLOUD), "stash"], check=False)
                subprocess.run(["git", "-C", str(CLOUD), "pull", "--rebase", "-X", "ours"], check=False)
                subprocess.run(["git", "-C", str(CLOUD), "stash", "pop"], check=False)
                subprocess.run(["git", "-C", str(CLOUD), "push"], check=False)
        else:
            print("nothing to commit locally")
    return 0

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--push", action="store_true")
    raise SystemExit(main(push=p.parse_args().push))
