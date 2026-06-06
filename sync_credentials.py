#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import json, datetime as dt, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "runtime_outlook" / "results.jsonl"
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

def main(push: bool = False):
    CLOUD.mkdir(parents=True, exist_ok=True)
    THREE.mkdir(parents=True, exist_ok=True)
    FOUR.mkdir(parents=True, exist_ok=True)
    existing = load_existing_emails()
    added = []
    if not RESULTS.exists():
        print("no results file")
        return 0
    for line in RESULTS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        if not d.get("success") or not d.get("email") or not d.get("password"):
            continue
        email = d["email"].strip()
        if email in existing:
            continue
        ts = d.get("ts") or dt.datetime.now().isoformat()
        day = ts[:10]
        client_id = d.get("client_id") or CLIENT_ID_DEFAULT
        rt = d.get("refresh_token") or ""
        three_dir = THREE / day
        four_dir = FOUR / day
        three_dir.mkdir(parents=True, exist_ok=True)
        four_dir.mkdir(parents=True, exist_ok=True)
        (three_dir / safe_name(email)).write_text(f"{email}----{d['password']}----{client_id}\n", encoding="utf-8")
        if rt:
            (four_dir / safe_name(email)).write_text(f"{email}----{d['password']}----{client_id}----{rt}\n", encoding="utf-8")
        record = {"ts": ts, "email": email, "password": d["password"], "client_id": client_id, "has_refresh_token": bool(rt), "source": "runtime_outlook/results.jsonl"}
        with ALL.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        existing.add(email)
        added.append(email)
    readme = CLOUD / "README.md"
    if not readme.exists():
        readme.write_text("# 云端注册邮箱\n\n私有仓库：保存 Outlook 注册成功后的三凭证/四凭证。\n\n- 三凭证：`email----password----client_id`\n- 四凭证：`email----password----client_id----refresh_token`\n", encoding="utf-8")
    print(f"added={len(added)}")
    for e in added:
        print(e)
    if push:
        subprocess.run(["git", "-C", str(CLOUD), "add", "."], check=True)
        status = subprocess.check_output(["git", "-C", str(CLOUD), "status", "--porcelain"], text=True)
        if status.strip():
            msg = "sync registered outlook credentials " + dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            subprocess.run(["git", "-C", str(CLOUD), "commit", "-m", msg], check=True)
            subprocess.run(["git", "-C", str(CLOUD), "push"], check=True)
        else:
            print("nothing to commit")
    return 0

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--push", action="store_true")
    raise SystemExit(main(push=p.parse_args().push))
