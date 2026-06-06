import os, sys, webbrowser, threading, random, string, re, time, json
from pathlib import Path

# Fix Windows GBK encoding crash on emoji characters
try:
    if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Body, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Any
from sqlalchemy.orm import Session
import httpx

# --------------- Verification Code Extraction ---------------
def extract_verification_code(html_body: str, text_body: str, subject: str) -> str:
    """从邮件内容中提取验证码"""
    # 合并所有文本内容
    text = subject + " " + text_body
    # 移除HTML标签
    if html_body:
        import re as regex
        clean_html = regex.sub(r'<[^>]+>', ' ', html_body)
        text += " " + clean_html

    # 常见验证码模式(按优先级排序)
    patterns = [
        # 数字验证码(4-8位)
        r'(?:验证码|code|Code|CODE|验证代码|安全码|security code)[::\s]*(\d{4,8})',
        r'(?:is|is:|:)\s*(\d{4,8})',
        r'(?:Your.*?code.*?is|您的.*?验证码.*?是)[::\s]*(\d{4,8})',
        # 纯数字验证码(在特定上下文中)
        r'(?:使用|use|enter|输入)\s*(\d{4,8})\s*(?:进行|to|for|作为)',
        # 通用数字模式(4-6位,可能是验证码)
        r'\b(\d{4,6})\b(?:\s*(?:是|is|为|code|验证码))',
        # 字母数字混合验证码
        r'(?:验证码|code|Code)[::\s]*([A-Za-z0-9]{4,8})',
        # 更宽松的数字模式
        r'\b(\d{4,8})\b'
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            # 返回第一个匹配的验证码
            return matches[0]

    return ""

from database import engine, get_db, Base, SessionLocal
from models import Account, Group

Base.metadata.create_all(bind=engine)

# --------------- 邮箱注册 credential adapters ---------------
try:
    from 邮箱注册.outlook_token_export import (
        BUILTIN_CLIENT_ID as 邮箱注册_BUILTIN_CLIENT_ID,
        credential_file_for as 邮箱注册_credential_file_for,
        locate_credential_file as 邮箱注册_locate_credential_file,
        save_created_outlook_account,
    )
    from 邮箱注册.credential_tools import (
        DEFAULT_CREDENTIAL_DIR,
        AUXILIARY_MAIL_DIR,
        ensure_credential_dirs,
        validate_credentials as 邮箱注册_validate_credentials,
    )
except Exception as _cred_exc:
    DEFAULT_CREDENTIAL_DIR = None
    AUXILIARY_MAIL_DIR = None
    邮箱注册_BUILTIN_CLIENT_ID = "14d82eec-204b-4c2f-b7e8-296a70dab67e"
    邮箱注册_CREDENTIAL_IMPORT_ERROR = str(_cred_exc)
else:
    邮箱注册_CREDENTIAL_IMPORT_ERROR = ""


# --------------- 邮箱注册 backend adapters ---------------
try:
    from 邮箱注册.service_adapters import (
        normalize_proxy,
        parse_proxy_lines,
        check_proxy_list,
        render_proxy_list,
        load_runtime_config,
        save_runtime_config,
    )
except Exception as _adapter_exc:
    normalize_proxy = None
    parse_proxy_lines = None
    check_proxy_list = None
    render_proxy_list = None
    load_runtime_config = None
    save_runtime_config = None
    邮箱注册_ADAPTER_IMPORT_ERROR = str(_adapter_exc)
else:
    邮箱注册_ADAPTER_IMPORT_ERROR = ""


def _creation_proxy_items_from_config(proxy: dict[str, Any]) -> list[str]:
    proxy = proxy or {}
    target_pools = proxy.get("target_stable_pools") or {}
    if isinstance(target_pools, dict):
        urls: list[str] = []
        for pool in target_pools.values():
            for item in pool or []:
                value = str(item.get("url") or "").strip() if isinstance(item, dict) else str(item or "").strip()
                if value and value not in urls:
                    urls.append(value)
        if urls:
            return urls
    for key in ("stable_items", "items"):
        values = [str(item).strip() for item in proxy.get(key, []) or [] if str(item).strip()]
        if values:
            return values
    for key in ("stable_pool", "pool", "working"):
        pool = proxy.get(key) or []
        values = [str(item.get("url") or "").strip() for item in pool if isinstance(item, dict) and str(item.get("url") or "").strip()]
        if values:
            return values
    return []


def _normalize_proxy_text(raw: str) -> tuple[list[str], list[str]]:
    """使用 邮箱注册 原始代理规范化能力:host:port:user:pass -> http://user:pass@host:port,并去重。"""
    errors: list[str] = []
    if not raw or not raw.strip():
        return [], []
    if parse_proxy_lines is None:
        return [], [f"邮箱注册 service_adapters 导入失败: {邮箱注册_ADAPTER_IMPORT_ERROR}"]
    candidates = parse_proxy_lines(raw, source="token_fastapi")
    normalized = [c.url for c in candidates]
    input_nonempty = [line.strip() for line in str(raw).splitlines() if line.strip() and not line.strip().startswith("#")]
    if input_nonempty and not normalized:
        errors.append("没有解析到有效代理;支持 host:port、host:port:user:pass、user:pass@host:port、http/socks URL")
    elif len(normalized) < len(input_nonempty):
        errors.append(f"已跳过 {len(input_nonempty) - len(normalized)} 行无效或重复代理")
    return normalized, errors


PORT = 18080

@asynccontextmanager
async def lifespan(app_instance):
    """服务器启动时检测系统代理"""
    import os
    os.environ["NO_PROXY"] = "127.0.0.1,localhost"
    # 启动阶段
    def _do_startup():
        import time
        time.sleep(0.5)
        webbrowser.open(f"http://localhost:{PORT}")
    threading.Thread(target=_do_startup, daemon=True).start()
    # 加载本地代理配置（从文件恢复）
    _load_local_proxy_from_file()

    # 启动 mihomo 订阅代理（后台线程，不阻塞服务器启动）
    def _start_mihomo_bg():
        try:
            from 邮箱注册.subscription_proxy import get_manager as _get_sub_mgr
            _mgr = _get_sub_mgr()
            if _mgr.subscriptions:
                ok, msg = _mgr.start()
                if ok:
                    print(f"[代理] ✅ mihomo 启动成功: {msg}")
                else:
                    print(f"[代理] ⚠️ mihomo 启动失败: {msg}")
            else:
                from 邮箱注册.subscription_proxy import detect_system_proxy
                proxy = detect_system_proxy()
                if proxy:
                    print(f"[代理] ✅ 检测到系统代理: {proxy}")
                else:
                    print("[代理] ⚠️ 未检测到代理，请先添加订阅或启动系统代理软件")
        except Exception as e:
            print(f"[代理] 启动异常: {e}")
    threading.Thread(target=_start_mihomo_bg, daemon=True).start()

    yield  # 服务器运行中...

    # ─── 关闭阶段: 清理 mihomo ───
    try:
        from 邮箱注册.subscription_proxy import get_manager as _get_sub_mgr
        _mgr = _get_sub_mgr()
        _mgr.cleanup()
        print("[代理] ✅ mihomo 已随主程序关闭")
    except Exception as e:
        print(f"[代理] 关闭异常: {e}")

app = FastAPI(title="令牌取件系统", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.middleware("http")
async def add_charset_middleware(request, call_next):
    response = await call_next(request)
    ct = response.headers.get("content-type", "")
    if "text/" in ct and "charset" not in ct:
        response.headers["content-type"] = ct + "; charset=utf-8"
    elif "application/json" in ct and "charset" not in ct:
        response.headers["content-type"] = ct + "; charset=utf-8"
    return response

# --------------- Schemas ---------------
class ImportItem(BaseModel):
    email: str
    pwd: str = ""
    client_id: str = ""
    token: str = ""
    raw: str = ""
    group_name: str = "默认分组"

class ImportRequest(BaseModel):
    items: List[ImportItem]

class MoveRequest(BaseModel):
    ids: List[int]
    target_group: str

class GroupCreate(BaseModel):
    name: str

class GroupRename(BaseModel):
    old_name: str
    new_name: str

class FetchMailRequest(BaseModel):
    email: str
    client_id: str
    token: str
    limit: int = 1

class ProxyTextRequest(BaseModel):
    proxy_text: str = ""
    max_checks: int = 100
    max_working: int = 80
    check: bool = False

class RuntimeConfigRequest(BaseModel):
    config: dict[str, Any]

# --------------- Accounts API ---------------
@app.get("/api/accounts")
def list_accounts(group: str = "All", search: str = "", db: Session = Depends(get_db)):
    q = db.query(Account)
    if group != "All":
        q = q.filter(Account.group_name == group)
    if search:
        q = q.filter(Account.email.contains(search))
    return [{"id": a.id, "email": a.email, "pwd": a.pwd, "client_id": a.client_id,
             "token": a.token, "raw": a.raw, "group": a.group_name} for a in q.all()]

@app.post("/api/accounts/import")
def import_accounts(req: ImportRequest, db: Session = Depends(get_db)):
    added = 0
    for item in req.items:
        acc = Account(email=item.email, pwd=item.pwd, client_id=item.client_id,
                      token=item.token, raw=item.raw, group_name=item.group_name)
        db.add(acc)
        added += 1
    db.commit()
    return {"status": "ok", "added": added}

@app.delete("/api/accounts/{acc_id}")
def delete_account(acc_id: int, db: Session = Depends(get_db)):
    acc = db.query(Account).get(acc_id)
    if not acc:
        raise HTTPException(404, "Not found")
    db.delete(acc)
    db.commit()
    return {"status": "ok"}

@app.post("/api/accounts/batch_delete")
def batch_delete(ids: List[int], db: Session = Depends(get_db)):
    db.query(Account).filter(Account.id.in_(ids)).delete(synchronize_session=False)
    db.commit()
    return {"status": "ok", "deleted": len(ids)}

@app.post("/api/accounts/move")
def move_accounts(req: MoveRequest, db: Session = Depends(get_db)):
    db.query(Account).filter(Account.id.in_(req.ids)).update(
        {Account.group_name: req.target_group}, synchronize_session=False)
    db.commit()
    return {"status": "ok", "moved": len(req.ids)}

@app.post("/api/accounts/export")
def export_accounts(ids: List[int], type: str = "acc_pwd", db: Session = Depends(get_db)):
    accs = db.query(Account).filter(Account.id.in_(ids)).all()
    lines = []
    for a in accs:
        if type == "acc":
            lines.append(a.email)
        elif type == "acc_pwd":
            lines.append(f"{a.email}----{a.pwd}")
        elif type == "raw":
            lines.append(a.raw or f"{a.email}----{a.pwd}----{a.client_id}----{a.token}")
    return {"status": "ok", "data": "\n".join(lines)}

# --------------- Groups API ---------------
@app.get("/api/groups")
def list_groups(db: Session = Depends(get_db)):
    groups = db.query(Group).all()
    if not groups:
        db.add(Group(name="默认分组"))
        db.commit()
        groups = db.query(Group).all()
    return [g.name for g in groups]

@app.post("/api/groups")
def create_group(req: GroupCreate, db: Session = Depends(get_db)):
    if db.query(Group).filter(Group.name == req.name).first():
        raise HTTPException(400, "分组已存在")
    db.add(Group(name=req.name))
    db.commit()
    return {"status": "ok"}

@app.put("/api/groups")
def rename_group(req: GroupRename, db: Session = Depends(get_db)):
    g = db.query(Group).filter(Group.name == req.old_name).first()
    if not g:
        raise HTTPException(404, "分组不存在")
    g.name = req.new_name
    db.query(Account).filter(Account.group_name == req.old_name).update(
        {Account.group_name: req.new_name}, synchronize_session=False)
    db.commit()
    return {"status": "ok"}

@app.delete("/api/groups/{name}")
def delete_group(name: str, db: Session = Depends(get_db)):
    db.query(Account).filter(Account.group_name == name).delete(synchronize_session=False)
    db.query(Group).filter(Group.name == name).delete(synchronize_session=False)
    if not db.query(Group).first():
        db.add(Group(name="默认分组"))
    db.commit()
    return {"status": "ok"}

# --------------- Mail Fetch API ---------------
@app.post("/api/fetch_by_token")
async def fetch_by_token(req: FetchMailRequest):
    try:
        token_data = {
            "client_id": req.client_id,
            "scope": "https://graph.microsoft.com/.default offline_access",
            "refresh_token": req.token,
            "grant_type": "refresh_token",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            token_resp = await client.post(
                "https://login.microsoftonline.com/consumers/oauth2/v2.0/token",
                data=token_data
            )
            if token_resp.status_code != 200:
                return {"status": "error", "message": f"Token刷新失败: {token_resp.text[:200]}"}
            access_token = token_resp.json().get("access_token")
            if not access_token:
                return {"status": "error", "message": "未获取到access_token"}

            headers = {"Authorization": f"Bearer {access_token}"}
            params = {"$top": req.limit, "$orderby": "receivedDateTime desc"}
            mail_resp = await client.get(
                "https://graph.microsoft.com/v1.0/me/messages",
                headers=headers, params=params
            )
            if mail_resp.status_code != 200:
                return {"status": "error", "message": f"邮件获取失败: {mail_resp.text[:200]}"}

            messages = mail_resp.json().get("value", [])
            emails = []
            for msg in messages:
                from_info = msg.get("from", {}).get("emailAddress", {})
                body = msg.get("body", {})
                html_body = body.get("contentType") == "html" and body.get("content", "") or ""
                text_body = body.get("contentType") == "text" and body.get("content", "") or ""
                subject = msg.get("subject", "(无主题)")

                # 提取验证码
                verification_code = extract_verification_code(html_body, text_body, subject)

                emails.append({
                    "subject": subject,
                    "from": f"{from_info.get('name', '')} <{from_info.get('address', '')}>",
                    "date": msg.get("receivedDateTime", ""),
                    "html_body": html_body,
                    "text_body": text_body,
                    "verification_code": verification_code,
                })
            return {"status": "ok", "emails": emails}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# --------------- Merge Files API ---------------
import glob as glob_mod

class MergeFilesRequest(BaseModel):
    directory: str
    exclude_dirs: List[str] = ["已经使用"]
    dedup: bool = True
    separator: str = "----"

@app.post("/api/merge_files")
def merge_files(req: MergeFilesRequest):
    """扫描目录下所有 .txt 凭证文件,返回解析后的记录"""
    import logging
    logging.warning(f"[MERGE] Received: directory={req.directory!r}, exclude={req.exclude_dirs}, dedup={req.dedup}")
    base_dir = req.directory
    if not os.path.isdir(base_dir):
        return {"status": "error", "message": f"目录不存在: {base_dir}"}

    separator = req.separator
    exclude_set = set(req.exclude_dirs)
    records = []
    errors = []

    # 扫描根目录 + 子目录
    for root, dirs, files in os.walk(base_dir):
        # 计算相对路径,判断是否在排除目录中
        rel = os.path.relpath(root, base_dir)
        top_dir = rel.split(os.sep)[0] if rel != "." else "."
        if top_dir in exclude_set:
            continue

        for fname in sorted(files):
            if not fname.endswith(".txt"):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read().strip()
            except Exception:
                try:
                    with open(fpath, "r", encoding="gbk") as f:
                        content = f.read().strip()
                except Exception:
                    errors.append(f"无法读取: {fname}")
                    continue

            if separator not in content:
                errors.append(f"格式不符: {fname}")
                continue

            parts = content.split(separator)
            if len(parts) < 4:
                errors.append(f"字段不足: {fname} ({len(parts)}字段)")
                continue

            email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', parts[0])
            if not email_match:
                errors.append(f"邮箱格式错误: {fname}")
                continue

            records.append({
                "email": email_match.group(0),
                "pwd": parts[1].strip(),
                "client_id": parts[2].strip(),
                "token": parts[3].strip(),
                "raw": content,
                "source": fname,
            })

    # 去重
    dup_count = 0
    if req.dedup:
        seen = set()
        unique = []
        for rec in records:
            key = rec["email"].lower()
            if key in seen:
                dup_count += 1
                continue
            seen.add(key)
            unique.append(rec)
        records = unique

    return {
        "status": "ok",
        "records": records,
        "total_scanned": len(records) + dup_count,
        "after_dedup": len(records),
        "duplicates": dup_count,
        "errors": errors,
    }

class AliasGenRequest(BaseModel):
    ids: Optional[List[int]] = None       # 从数据库选账号
    text: Optional[str] = None             # 或手动粘贴文本
    group: Optional[str] = None            # 或按分组选
    count: int = 5                         # 每个邮箱生成数量
    keep_fields: bool = True               # 保留原字段
    stagger: bool = True                   # 错开顺序

# --------------- Alias Generation API ---------------
EMAIL_RE = re.compile(r'([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', re.I)
SUPPORTED_DOMAIN_RE = re.compile(r'^(hotmail|outlook)\.[a-z]{2,}(?:\.[a-z]{2,})*$', re.I)
DELIMITER = "----"

def _random_letters(n=6):
    return ''.join(random.choices(string.ascii_letters, k=n))

def _generate_aliases_for_email(base_email, count, used_set):
    atIndex = base_email.index('@')
    local = base_email[:atIndex].split('+')[0]
    domain = base_email[atIndex+1:]
    aliases = []
    for _ in range(count):
        alias = ""
        for _ in range(20):
            suffix = _random_letters(6)
            alias = f"{local}+{suffix}@{domain}"
            if alias.lower() not in used_set:
                break
        used_set.add(alias.lower())
        aliases.append(alias)
    return aliases

@app.post("/api/alias/generate")
def generate_aliases(req: AliasGenRequest, db: Session = Depends(get_db)):
    lines = []
    # 收集输入行
    if req.ids:
        accs = db.query(Account).filter(Account.id.in_(req.ids)).all()
        for a in accs:
            raw = a.raw or f"{a.email}----{a.pwd}----{a.client_id}----{a.token}"
            lines.append(raw)
    elif req.group:
        accs = db.query(Account).filter(Account.group_name == req.group).all()
        for a in accs:
            raw = a.raw or f"{a.email}----{a.pwd}----{a.client_id}----{a.token}"
            lines.append(raw)
    elif req.text:
        lines = req.text.strip().split('\n')
    else:
        return {"status": "error", "message": "未提供输入源"}

    count = max(1, min(req.count, 50))
    used_set = set()
    outputs = []
    valid = 0
    skipped = 0
    records = []  # 每条记录的别名列表

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split(DELIMITER)
        m = EMAIL_RE.search(parts[0] if parts else line)
        if not m:
            skipped += 1
            continue
        local_base = m.group(1).split('+')[0]
        domain = m.group(2).lower()
        if not SUPPORTED_DOMAIN_RE.match(domain):
            skipped += 1
            continue
        base_email = f"{local_base}@{domain}"
        aliases = _generate_aliases_for_email(base_email, count, used_set)
        valid += 1
        records.append({"aliases": aliases, "parts": parts})

    # 错开顺序输出
    if req.stagger:
        for i in range(count):
            for rec in records:
                if i < len(rec["aliases"]):
                    alias = rec["aliases"][i]
                    if req.keep_fields and len(rec["parts"]) > 1:
                        outputs.append(DELIMITER.join([alias] + rec["parts"][1:]))
                    else:
                        outputs.append(alias)
    else:
        for rec in records:
            for alias in rec["aliases"]:
                if req.keep_fields and len(rec["parts"]) > 1:
                    outputs.append(DELIMITER.join([alias] + rec["parts"][1:]))
                else:
                    outputs.append(alias)

    return {
        "status": "ok",
        "data": "\n".join(outputs),
        "total": len(outputs),
        "valid": valid,
        "skipped": skipped
    }

# --------------- Parse import text ---------------
@app.post("/api/parse_import")
def parse_import_text(text: str = "", group: str = "默认分组"):
    lines = text.strip().split("\n")
    items = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = line.split("----")
        if len(parts) >= 4:
            email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', line)
            if email_match:
                items.append({
                    "email": email_match.group(0),
                    "pwd": parts[1].strip(),
                    "client_id": parts[2].strip(),
                    "token": parts[3].strip(),
                    "raw": line,
                    "group_name": group
                })
    return {"status": "ok", "items": items, "count": len(items)}

# --------------- Static files ---------------
FRONTEND_DIR = os.path.dirname(os.path.abspath(__file__))

@app.get("/")
def serve_index():
    return FileResponse(
        os.path.join(FRONTEND_DIR, "integrated_frontend.html"),
        media_type="text/html; charset=utf-8"
    )

# --------------- Batch Registration ---------------
import logging
import threading

logger = logging.getLogger("registration")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

BATCH_REG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "\u6279\u91cf\u6ce8\u518c\u90ae\u7bb1")
os.makedirs(BATCH_REG_DIR, exist_ok=True)

REG_STATE = {"running": False, "paused": False, "provider": "", "count": 0, "completed": 0,
             "concurrent": 1,
             "success": 0, "failed": 0, "current": "", "errors": [], "results": [], "stop_flag": False,
             "logs": [], "steps": [], "active_proxy": "", "proxy_count": 0, "credential_dir": "", "last_credential_path": "",
             "current_email": "", "current_password": "", "current_client_id": "", "current_step": "",
             "active_slots": [],  # 并发槽位: [{slot_id, status, email, password, client_id, refresh_token, step, proxy}]
             "available_proxies": [], "proxy_rotate": False}
REG_LOCK = threading.Lock()
_FILE_WRITE_LOCK = threading.Lock()  # 保护文件写入的锁（并发注册时避免文件损坏）

# 可用代理列表（独立于 REG_STATE，跨任务持久）
_AVAILABLE_PROXIES: list[str] = []
_PROXY_ROTATE = False
_PROXY_DETECT_PROGRESS = {"running": False, "done": 0, "total": 0, "available": 0, "unavailable": 0}

# 本地代理配置（用户手动设置的本地代理，如 127.0.0.1:7890）
_LOCAL_PROXY = {"url": "", "enabled": False}  # url: 代理地址, enabled: 是否启用
_LOCAL_PROXY_LOCK = threading.Lock()

def _normalize_proxy_url(url: str) -> str:
    """自动补全代理地址的协议前缀"""
    url = url.strip()
    if not url:
        return url
    # 已有协议前缀，不处理
    if "://" in url:
        return url
    # 裸地址自动加 http://（Clash/mihomo 默认端口是 HTTP 代理）
    return f"http://{url}"

def _save_local_proxy_to_file():
    """将本地代理配置持久化到 runtime_config.toml"""
    try:
        with _LOCAL_PROXY_LOCK:
            url = _LOCAL_PROXY["url"]
            enabled = _LOCAL_PROXY["enabled"]
        if load_runtime_config and save_runtime_config:
            config = load_runtime_config()
            if "local_proxy" not in config:
                config["local_proxy"] = {}
            config["local_proxy"]["url"] = url
            config["local_proxy"]["enabled"] = enabled
            save_runtime_config(config)
            logger.info(f"[代理] 本地代理已保存到配置文件: {url} (启用={enabled})")
    except Exception as e:
        logger.warning(f"保存本地代理配置失败: {e}")

def _load_local_proxy_from_file():
    """从 runtime_config.toml 加载本地代理配置"""
    try:
        if not load_runtime_config:
            return
        config = load_runtime_config()
        lp = config.get("local_proxy", {})
        url = lp.get("url", "")
        enabled = lp.get("enabled", False)
        if url:
            with _LOCAL_PROXY_LOCK:
                _LOCAL_PROXY["url"] = url
                _LOCAL_PROXY["enabled"] = enabled
            logger.info(f"[代理] 从配置加载本地代理: {url} (启用={enabled})")
    except Exception as e:
        logger.warning(f"加载本地代理配置失败: {e}")

SUPPORTED_PY_REGISTER_PROVIDERS = {"outlook", "hotmail", "gmail", "yahoo", "myyahoo"}
EXTENSION_ONLY_PROVIDERS = {"proton", "gmx", "aol", "zoho", "yandex", "mailcom", "icloud", "mailru", "naver", "kakao", "netease163", "netease126", "neteaseyeah", "qq", "sina", "sohu", "tutanota"}



def reg_log(message: str, level: str = "info", step: str = ""):
    import datetime as _dt
    icon = {"info": "i️", "ok": "✅", "warn": "⚠️", "error": "❌", "step": "🔹", "proxy": "🌐", "cred": "🔐"}.get(level, "•")
    line = f"{_dt.datetime.now().strftime('%H:%M:%S')} {icon} {message}"
    with REG_LOCK:
        REG_STATE.setdefault("logs", []).append(line)
        REG_STATE["logs"] = REG_STATE["logs"][-300:]
        if step:
            REG_STATE.setdefault("steps", []).append({"time": _dt.datetime.now().strftime('%H:%M:%S'), "step": step, "level": level, "message": message})
            REG_STATE["steps"] = REG_STATE["steps"][-120:]
    try:
        getattr(logger, "error" if level == "error" else "warning" if level == "warn" else "info")(line)
    except Exception:
        pass



def check_pause(stop_event=None):
    """检查暂停状态,阻塞直到暂停解除。返回 True 表示应停止。"""
    while True:
        with REG_LOCK:
            if REG_STATE.get("stop_flag"):
                return True
            if not REG_STATE.get("paused"):
                return False
        time.sleep(0.5)


def _credential_output_dir() -> str:
    """始终使用 批量注册邮箱 目录作为默认保存路径。"""
    os.makedirs(BATCH_REG_DIR, exist_ok=True)
    return BATCH_REG_DIR

def save_credential_file(email, password, client_id="", refresh_token=""):
    """保存四凭证到 邮箱注册 原始凭证目录（并发安全）。"""
    with _FILE_WRITE_LOCK:
        return _save_credential_file_impl(email, password, client_id, refresh_token)

def _save_credential_file_impl(email, password, client_id="", refresh_token=""):
    """保存四凭证的实际实现（内部函数，由 save_credential_file 加锁调用）。"""
    client_id = client_id or (globals().get("邮箱注册_BUILTIN_CLIENT_ID") or "14d82eec-204b-4c2f-b7e8-296a70dab67e")
    output_dir = _credential_output_dir()
    os.makedirs(output_dir, exist_ok=True)
    safe = re.sub(r'[^a-zA-Z0-9@._-]', '_', email.lower()).strip('._-')
    try:
        if callable(save_created_outlook_account):
            result = save_created_outlook_account(
                email, password, client_id=client_id, refresh_token=refresh_token or "",
                out_dir=output_dir, source="token_fastapi_integrated", final_state="registered",
            )
            path = result.get("credential_path") or result.get("combo_path") or str(邮箱注册_credential_file_for(email, output_dir))
            if not os.path.exists(path):
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(f"{email}----{password}----{client_id}----{refresh_token or ''}\n")
            return path
    except Exception as exc:
        reg_log(f"邮箱注册 四凭证保存函数失败,使用兼容写入:{exc}", "warn", "credential_save_fallback")
    path = os.path.join(output_dir, f"{safe}.txt")
    with open(path, 'w', encoding='utf-8') as f:
        f.write(f"{email}----{password}----{client_id}----{refresh_token or ''}\n")
    return path


def auto_import_to_library(email, password, client_id="", refresh_token="", group="批量注册"):
    with _FILE_WRITE_LOCK:
        return _auto_import_to_library_impl(email, password, client_id, refresh_token, group)

def _auto_import_to_library_impl(email, password, client_id="", refresh_token="", group="批量注册"):
    db = SessionLocal()
    try:
        if db.query(Account).filter(Account.email == email).first():
            return None
        acc = Account(email=email, pwd=password,
                      client_id=client_id or "14d82eec-204b-4c2f-b7e8-296a70dab67e",
                      token=refresh_token, raw=f"{email}----{password}----{client_id}----{refresh_token}",
                      group_name=group)
        db.add(acc)
        if not db.query(Group).filter(Group.name == group).first():
            db.add(Group(name=group))
        db.commit()
        return acc.id
    finally:
        db.close()

def _try_obtain_refresh_token(ninja_instance, email, password, provider):
    """注册完成后,尝试通过已登录的浏览器获取 OAuth refresh_token。"""
    if provider not in ("outlook", "hotmail"):
        return ""
    CLIENT_ID = "14d82eec-204b-4c2f-b7e8-296a70dab67e"
    REDIRECT = "https://login.microsoftonline.com/common/oauth2/nativeclient"
    OAUTH_URL = (
        "https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize"
        f"?client_id={CLIENT_ID}&response_type=code"
        f"&redirect_uri={REDIRECT}"
        "&scope=offline_access+https://outlook.office365.com/.default"
        f"&login_hint={email}"
    )
    raw_driver = getattr(ninja_instance, 'active_driver', None)
    if not raw_driver:
        reg_log("⚠️ 无活跃浏览器,跳过 refresh_token 获取", "warn", "no_driver")
        return ""

    # --- CDPBrowser 适配器:将 CDP API 包装成 Selenium WebDriver 接口 ---
    try:
        from 邮箱注册.cdp_browser import CDPBrowser as _CDPBrowser
    except ImportError:
        _CDPBrowser = None

    class _CDPDriverAdapter:
        """Wrap CDPBrowser to look like Selenium WebDriver for OAuth flow."""
        def __init__(self, cdp_browser):
            self._b = cdp_browser

        def get(self, url):
            self._b.navigate(url)

        def find_element(self, by, value):
            if by == "tag name":
                text = self._b.evaluate(
                    "document.body ? document.body.innerText : ''"
                ) or ""
                return _FakeElement(text)
            elif by == "xpath":
                # Try CSS selectors for common OAuth buttons
                css_map = {
                    "//input[@type='submit']": "input[type='submit']",
                    "//input[@value='Accept']": "input[value='Accept']",
                }
                for xpath_key, css in css_map.items():
                    if xpath_key in value:
                        nid = self._b.query_selector(css)
                        if nid:
                            return _FakeCDPElement(self._b, css)
                # Fallback: try clicking by text using JS evaluation
                for text_token in ["Accept", "同意", "Allow", "Yes", "确认"]:
                    clicked = self._b.evaluate(
                        "(() => { const btns = [...document.querySelectorAll('button, input[type=\"submit\"], a')]; "
                        f"const btn = btns.find(b => (b.textContent || b.value || '').includes('{text_token}')); "
                        "if (btn) { btn.click(); return true; } return false; })()"
                    )
                    if clicked:
                        return _FakeElement(text_token)
                raise NoSuchElementException("No matching element")
            raise NoSuchElementException(f"Unsupported locator: {by}")

        @property
        def current_url(self):
            return self._b.current_url

    class _FakeElement:
        def __init__(self, text):
            self.text = text

        def click(self):
            pass

    class _FakeCDPElement:
        def __init__(self, browser, selector):
            self._b = browser
            self._sel = selector
            self.text = ""

        def click(self):
            rect = self._b.get_element_rect_js(self._sel)
            if rect:
                self._b.click_at(rect["center_x"], rect["center_y"])

    class NoSuchElementException(Exception):
        pass

    # Adapt driver to common interface
    if _CDPBrowser and isinstance(raw_driver, _CDPBrowser):
        driver = _CDPDriverAdapter(raw_driver)
    else:
        driver = raw_driver

    try:
        reg_log("🔑 正在获取 OAuth refresh_token...", "step", "oauth_start")
        driver.get(OAUTH_URL)
        time.sleep(8)
        # 检测授权页面
        try:
            body_text = driver.find_element("tag name", "body").text.lower()
        except Exception:
            body_text = ""
        if "accept" in body_text or "同意" in body_text or "allow" in body_text:
            reg_log("检测到授权页面,自动点击同意...", "step", "oauth_consent")
            for xpath in [
                "//input[@type='submit']",
                "//button[contains(text(),'Accept') or contains(text(),'\u540c\u610f') or contains(text(),'Allow')]",
                "//input[@value='Accept']",
            ]:
                try:
                    btn = driver.find_element("xpath", xpath)
                    btn.click()
                    time.sleep(8)
                    break
                except Exception:
                    continue
        final_url = driver.current_url
        reg_log(f"OAuth 最终 URL: {final_url[:120]}...", "step", "oauth_redirect")
        if "code=" in final_url:
            code = final_url.split("code=")[1].split("&")[0]
            reg_log(f"获取到 auth code: {code[:20]}...", "ok", "oauth_code")
            import urllib.request, urllib.parse
            data = urllib.parse.urlencode({
                "client_id": CLIENT_ID,
                "code": code,
                "redirect_uri": REDIRECT,
                "grant_type": "authorization_code",
            }).encode()
            req = urllib.request.Request(
                "https://login.microsoftonline.com/consumers/oauth2/v2.0/token",
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                tokens = json.loads(resp.read())
                rt = tokens.get("refresh_token", "")
                if rt:
                    reg_log(f"✅ refresh_token 获取成功: {rt[:30]}...", "ok", "oauth_rt_ok")
                else:
                    reg_log("⚠️ token 响应中无 refresh_token", "warn", "oauth_no_rt")
                return rt
        else:
            reg_log("⚠️ OAuth 重定向中未找到 code 参数", "warn", "oauth_no_code")
            return ""
    except Exception as e:
        reg_log(f"⚠️ refresh_token 获取失败: {str(e)[:200]}", "warn", "oauth_error")
        return ""
    finally:
        # Token 获取完成后,关闭浏览器释放资源
        if _CDPBrowser and isinstance(raw_driver, _CDPBrowser):
            try:
                raw_driver.close()
                reg_log("🔒 浏览器已关闭", "ok", "browser_closed")
            except Exception:
                pass
        elif hasattr(raw_driver, 'quit'):
            try:
                raw_driver.quit()
            except Exception:
                pass


def _update_slot(slot_id, **kwargs):
    """更新指定槽位的状态"""
    with REG_LOCK:
        slots = REG_STATE.get("active_slots", [])
        for s in slots:
            if s["slot_id"] == slot_id:
                s.update(kwargs)
                break

def run_registration_task(provider, count, password, group_name, proxy_list,
                          captcha_key, sms_config, browser, visible, tun_mode=False, concurrent=1):
    global REG_STATE, _PROXY_ROTATE
    concurrent = max(1, min(int(concurrent or 1), 10))
    # 并发模式下，总注册数 = 用户指定数量（count），concurrent 只控制同时运行的线程数
    actual_count = count
    credential_dir = _credential_output_dir()
    # 初始化并发槽位：槽位数 = 实际任务数，每个任务独占一个槽位
    slots = [{"slot_id": i, "status": "idle", "email": "", "password": "", "client_id": "",
              "refresh_token": "", "step": "等待中", "proxy": ""} for i in range(actual_count)]
    with REG_LOCK:
        REG_STATE.update(running=True, provider=provider, count=actual_count, completed=0,
                         concurrent=concurrent,
                         success=0, failed=0, errors=[], results=[], stop_flag=False, paused=False,
                         logs=[], steps=[], active_proxy="", proxy_count=0,
                         credential_dir=credential_dir, last_credential_path="",
                         current_email="", current_password="", current_client_id="", current_step="",
                         active_slots=slots)
    reg_log(f"任务启动:服务商={provider},数量={actual_count},并发={concurrent},四凭证目录={credential_dir}", "step", "start")
    # 彻底重置 CDP 引擎的所有控制状态（全局变量+线程状态字典），防止残留 stop/paused 导致新任务秒退
    try:
        from 邮箱注册.cdp_outlook import reset_all_states
        reset_all_states()
    except Exception as e:
        logger.warning("重置 CDP 控制状态失败: %s，尝试旧方式", e)
        try:
            from 邮箱注册.cdp_outlook import set_registration_stop, set_registration_paused, set_captcha_force_skip
            set_registration_stop(False)
            set_registration_paused(False)
            set_captcha_force_skip(False)
        except Exception:
            pass
    try:
        from 邮箱注册.cdp_outlook import register_outlook_account, OutlookAccount, _random_account

        normalized_proxies, proxy_errors = _normalize_proxy_text(proxy_list or "")
        if proxy_errors:
            reg_log("代理转换提醒:" + ";".join(proxy_errors), "warn", "proxy_normalize")

        # ====== 代理源优先级: 本地代理 > 订阅代理 > 已检测代理 > 手动代理 ======

        # 1. 检查本地代理是否启用
        _local_proxy_url = ""
        with _LOCAL_PROXY_LOCK:
            _local_enabled = _LOCAL_PROXY["enabled"]
            _local_url = _LOCAL_PROXY["url"]
        if _local_enabled and _local_url:
            _local_proxy_url = _local_url
            reg_log(f"🏠 使用本地代理: {_local_proxy_url}", "ok", "local_proxy")

        # 2. 检查订阅代理
        _sub_proxy_url = ""
        if not _local_proxy_url:  # 本地代理未启用时才尝试订阅代理
            try:
                _spm = _sub_proxy()
                if _spm and _spm.is_running:
                    # 注册前自动切换到 alive 节点
                    try:
                        ok, msg = _spm.find_alive_node()
                        if ok:
                            reg_log(f"🌐 已切换到可用节点: {msg}", "ok", "alive_node")
                        else:
                            reg_log(f"⚠️ 找不到可用节点: {msg}", "warn", "no_alive")
                    except Exception:
                        pass
                    _sub_proxy_url = _spm.proxy_url
                    reg_log(f"🌐 使用订阅代理: {_sub_proxy_url}", "ok", "sub_proxy")
            except Exception:
                pass

        # 3. 根据优先级选择代理源
        if _local_proxy_url:
            proxies = [_local_proxy_url]
            _PROXY_ROTATE = False
            reg_log(f"✅ 使用本地代理: {_local_proxy_url}", "ok", "proxy_local")
        elif _sub_proxy_url:
            proxies = [_sub_proxy_url]
            _PROXY_ROTATE = False
            reg_log(f"✅ 使用订阅代理: {_sub_proxy_url}", "ok", "proxy_sub")
        elif _AVAILABLE_PROXIES:
            proxies = list(_AVAILABLE_PROXIES)
            if _PROXY_ROTATE:
                reg_log(f"🔄 轮询模式:使用 {len(_AVAILABLE_PROXIES)} 个已检测可用代理", "ok", "proxy_rotate")
            else:
                reg_log(f"✅ 使用 {len(_AVAILABLE_PROXIES)} 个已检测可用代理（自动开启轮询）", "ok", "proxy_auto")
                _PROXY_ROTATE = True
                with REG_LOCK:
                    REG_STATE["proxy_rotate"] = True
        elif normalized_proxies:
            proxies = normalized_proxies
            if len(normalized_proxies) > 1:
                _PROXY_ROTATE = True
                with REG_LOCK:
                    REG_STATE["proxy_rotate"] = True
                reg_log(f"🔄 手动输入 {len(normalized_proxies)} 个代理，自动开启轮询", "ok", "proxy_manual_rotate")
            else:
                reg_log(f"使用 {len(normalized_proxies)} 个手动输入代理", "proxy", "proxy_manual")
        else:
            proxies = []
            reg_log("未使用代理:代理列表为空且无已检测可用代理", "warn", "proxy_empty")
        with REG_LOCK:
            REG_STATE["proxy_count"] = len(proxies or [])
            REG_STATE["active_proxy"] = (proxies or [""])[0]
        if proxies:
            reg_log(f"代理已载入:{len(proxies)} 个;当前优先使用:{proxies[0]}", "proxy", "proxy_ready")
        else:
            reg_log("未使用代理:代理列表为空或未解析到有效代理", "warn", "proxy_empty")
        reg_log(f"初始化纯 CDP 注册引擎:可见窗口={visible}", "step", "init_cdp")

        def _curl_proxy_check(proxy_url):
            """curl 通过代理查出口 IP/国家"""
            import subprocess, json as _j
            socks = proxy_url.replace("socks5://", "socks5h://")
            try:
                r = subprocess.run(["curl", "-s", "--max-time", "15", "--proxy", socks, "https://ipinfo.io/json"],
                                   capture_output=True, text=True, timeout=20)
                if r.returncode == 0:
                    info = _j.loads(r.stdout)
                    return info.get("country", ""), info.get("ip", ""), info.get("city", "")
            except:
                pass
            return "", "", ""

        def _pause_checker(step_name):
            """暂停检查:阻塞直到暂停解除,返回True表示应停止"""
            with REG_LOCK:
                REG_STATE["current_step"] = step_name
            while True:
                with REG_LOCK:
                    if REG_STATE.get("stop_flag"):
                        return True
                    if not REG_STATE.get("paused"):
                        return False
                time.sleep(0.5)

        def _do_register(proxy_url, account=None, slot_index=0):
            """纯 CDP 注册,返回 RegistrationResult"""
            reg_log(f"注册引擎参数:browser_type={browser},visible={visible},slot={slot_index}", "step", "browser_type")
            return register_outlook_account(
                account=account,
                browser_type=browser,
                proxy=proxy_url or "",
                headless=not visible,
                extract_rt=True,
                pause_checker=_pause_checker,
                slot_index=slot_index,
            )

        # 代理轮询状态
        proxy_fail_count = {}  # {proxy_url: fail_count}
        proxy_idx = 0  # 当前代理索引
        MAX_PROXY_FAILS = 3  # 单个代理最大失败次数
        _proxy_lock = threading.Lock()  # 保护代理轮询的锁
        _sub_node_idx = 0  # 订阅代理节点轮询索引（并发/批量时每个注册任务递增）

        def _get_next_proxy():
            """获取下一个可用代理，跳过已失败3次的（线程安全）。
            使用订阅代理时，每次调用自动切换 mihomo 节点（顺序轮询1→2→...→n→1）"""
            nonlocal _sub_node_idx, proxy_idx
            with _proxy_lock:
                if not proxies:
                    return ""
                # 订阅代理轮询: 每次调用切换到下一个节点
                if _sub_proxy_url:
                    try:
                        _spm = _sub_proxy()
                        if _spm and _spm.is_running:
                            # 顺序切换到下一个节点
                            nodes = _spm.get_nodes()
                            alive_nodes = [n for n in nodes if n.get("alive", False) and n["name"] not in ("COMPATIBLE", "DIRECT", "PASS", "REJECT", "REJECT-DROP")]
                            pool = alive_nodes if alive_nodes else nodes
                            if pool:
                                # 按顺序轮询
                                target = pool[_sub_node_idx % len(pool)]
                                _sub_node_idx += 1
                                ok, msg = _spm.switch_to_node(target["name"])
                                if ok:
                                    reg_log(f"🔄 订阅节点轮询: {msg}", "ok", "node_rotate")
                                else:
                                    reg_log(f"⚠️ 订阅节点切换失败: {msg}", "warn", "node_rotate_fail")
                    except Exception as e:
                        reg_log(f"订阅节点轮询异常: {e}", "warn", "node_rotate_err")
                    return _sub_proxy_url
                # 本地代理 / 手动代理列表轮询
                for _ in range(len(proxies)):
                    p = proxies[proxy_idx % len(proxies)]
                    proxy_idx += 1
                    if proxy_fail_count.get(p, 0) < MAX_PROXY_FAILS:
                        return p
                # 所有代理都失败3次了，返回第一个继续试
            return proxies[0]

        def _register_single(i, slot_id, pre_assigned_proxy=None):
            """单个账号注册流程（可在线程中运行）
            pre_assigned_proxy: 并发模式下预分配的代理URL，为None时使用_get_next_proxy()
            """
            import threading as _thr
            logger.info(f"[并发] 线程启动: task={i}, slot={slot_id}, thread={_thr.current_thread().name}, proxy={pre_assigned_proxy or 'auto'}")
            with REG_LOCK:
                if REG_STATE["stop_flag"]:
                    REG_STATE["completed"] += 1
                    return
                # 并发时不覆盖全局 current（会互相干扰），用 slot 显示进度
                if concurrent <= 1:
                    REG_STATE["current"] = f"🔹 正在创建第 {i+1}/{actual_count} 个 {provider} 邮箱..."
            if check_pause():
                with REG_LOCK:
                    REG_STATE["completed"] += 1
                return
            reg_log(f"开始第 {i+1}/{actual_count} 个账号注册流程", "step", "account_start")
            _update_slot(slot_id, status="running", step="准备中")
            with REG_LOCK:
                REG_STATE["current_step"] = "preparing"
            # 系统代理由 Clash Verge 管理，无需手动轮循
            # 并发模式下使用预分配的代理，顺序模式下使用轮询
            current_proxy = pre_assigned_proxy if pre_assigned_proxy is not None else _get_next_proxy()
            if current_proxy:
                with REG_LOCK:
                    REG_STATE["active_proxy"] = current_proxy
                fails = proxy_fail_count.get(current_proxy, 0)
                reg_log(f"本次注册使用代理:{current_proxy}" + (f" (已失败{fails}次)" if fails else ""), "proxy", "proxy_use")
            _update_slot(slot_id, proxy=current_proxy or "无")
            try:
                reg_log(f"调用纯 CDP 注册引擎:provider={provider},proxy={current_proxy or 'none'}", "step", "call_cdp")

                # 预生成账号,更新前端凭证显示（优先更新 slot，全局字段仅在单线程时更新）
                pre_account = _random_account(
                    domain="hotmail.com" if provider == "hotmail" else "outlook.com",
                    provider=provider
                )
                with REG_LOCK:
                    # 并发时只更新 slot，不覆盖全局字段（避免线程间覆盖）
                    if concurrent <= 1:
                        REG_STATE["current_email"] = pre_account.email
                        REG_STATE["current_password"] = pre_account.password
                        REG_STATE["current_client_id"] = pre_account.client_id
                _update_slot(slot_id, email=pre_account.email, password=pre_account.password,
                             client_id=pre_account.client_id, step="账号已生成")
                reg_log(f"账号已生成: {pre_account.email} | 密码已就绪 | ClientID={pre_account.client_id}", "cred", "account_ready")

                # 第一层:curl 预检代理
                curl_country, curl_ip, curl_city = "", "", ""
                if current_proxy:
                    curl_country, curl_ip, curl_city = _curl_proxy_check(current_proxy)
                    if curl_ip:
                        reg_log(f"代理 curl 预检:IP={curl_ip},国家={curl_country},城市={curl_city}", "proxy", "curl_check")
                    else:
                        reg_log("代理 curl 预检失败(但继续尝试)", "warn", "curl_fail")

                result = _do_register(current_proxy if not tun_mode else "", account=pre_account, slot_index=slot_id)
                # 注册返回后立即检查停止标志
                with REG_LOCK:
                    if REG_STATE.get("stop_flag"):
                        reg_log("任务已停止（注册引擎返回后检测到停止标志）", "warn", "stopped")
                        _update_slot(slot_id, step="已停止", status="stopped")
                        REG_STATE["completed"] += 1
                        return
                # 如果注册引擎返回 stopped，立即退出
                if result and getattr(result, "error", "") == "stopped":
                    reg_log("注册引擎已停止", "warn", "stopped")
                    _update_slot(slot_id, step="已停止", status="stopped")
                    with REG_LOCK:
                        REG_STATE["completed"] += 1
                    return
                if not result or not result.email:
                    raise ValueError(result.error if result else "注册未返回结果")

                email = result.email
                pwd = result.password
                refresh_token = getattr(result, "refresh_token", "") or ""
                client_id = getattr(result, "client_id", "") or "14d82eec-204b-4c2f-b7e8-296a70dab67e"
                # Update REG_STATE with current credentials for frontend display
                # 并发时只更新 slot，不覆盖全局字段
                with REG_LOCK:
                    if concurrent <= 1:
                        REG_STATE["current_email"] = email or ""
                        REG_STATE["current_password"] = pwd or ""
                        REG_STATE["current_client_id"] = client_id or ""

                # 第二层:从注册流程读取的自动国家 vs curl 国家
                browser_country = getattr(result, "auto_country", "") or ""
                if curl_country and browser_country:
                    match = (curl_country.lower() in browser_country.lower() or
                             browser_country.lower() in curl_country.lower())
                    if match:
                        reg_log(f"代理双重验证通过:curl={curl_country},浏览器={browser_country}", "ok", "proxy_verify")
                    else:
                        reg_log(f"代理国家不匹配:curl={curl_country},浏览器={browser_country}(继续)", "warn", "proxy_mismatch")
                elif curl_country:
                    reg_log(f"代理 curl 验证通过:{curl_country}(浏览器未读到国家)", "proxy", "proxy_verify_partial")

                # ====== 前提:注册成功!才往下走 ======
                if getattr(result, 'error', ''):
                    # 即使有错误，如果注册成功了（有邮箱和密码），先保存三凭证
                    if email and pwd and getattr(result, 'success', False):
                        reg_log(f"⚠️ 注册成功但后续页面出错: {result.error[:100]}（三凭证已保存）", "warn", "partial_success")
                        save_credential_file(email, pwd, client_id=client_id, refresh_token="")
                        auto_import_to_library(email, pwd, client_id=client_id, refresh_token="", group=group_name)
                        reg_log(f"✅ 三凭证已保存（注册成功确认）: {email} | 密码:{pwd} | ClientID:{client_id}", "ok", "cred_saved")
                    raise ValueError(f"注册失败: {result.error}")
                if not getattr(result, 'success', False):
                    raise ValueError("注册未成功(CAPTCHA 未通过或页面未到达账户主页)")
                if not email or not pwd:
                    raise ValueError("注册未返回有效邮箱或密码,视为失败")
                reg_log(f"✅ 注册成功:{email} | 密码:{pwd}", "ok", "reg_success")
                _update_slot(slot_id, email=email, password=pwd, client_id=client_id, step="注册成功")

                # ====== 第一步:立即保存三凭证(邮箱+密码+ID) ======
                cred_path = save_credential_file(email, pwd, client_id=client_id, refresh_token="")
                auto_import_to_library(email, pwd, client_id=client_id, refresh_token="", group=group_name)
                reg_log(f"✅ 三凭证已保存: {email} | 密码:{pwd} | ClientID:{client_id}", "ok", "cred_saved")

                # ====== 第二步：尝试获取 refresh_token ======
                if not refresh_token:
                    reg_log("注册流程未获取到 RT（extract_rt 已尝试过）", "info", "rt_skip")

                # ====== 第三步:有 RT 就补全四凭证 ======
                if refresh_token:
                    cred_path = save_credential_file(email, pwd, client_id=client_id, refresh_token=refresh_token)
                    auto_import_to_library(email, pwd, client_id=client_id, refresh_token=refresh_token, group=group_name)
                    reg_log(f"✅ RT 已补全,四凭证更新: {email}", "ok", "rt_updated")

                four_line = f"{email}----{pwd}----{client_id}----{refresh_token}"
                with REG_LOCK:
                    REG_STATE["success"] += 1
                    REG_STATE["last_credential_path"] = cred_path
                    REG_STATE["results"].append({"email": email, "password": pwd, "client_id": client_id,
                                                  "refresh_token": refresh_token, "four_credential": four_line,
                                                  "status": "success", "credential_path": cred_path,
                                                  "credential_dir": os.path.dirname(cred_path), "account_id": i+1})
                reg_log(f"四凭证最终保存:{email} | 密码:{pwd} | ClientID:{client_id} | RT={refresh_token[:20]+'...' if refresh_token else '无'}", "ok", "account_saved")
                _update_slot(slot_id, refresh_token=refresh_token, step="完成", status="done")
                logger.info(f"[REG] ✅ {i+1}/{actual_count} done: {email}")
            except Exception as exc:
                error_msg = str(exc)
                _update_slot(slot_id, step=f"失败: {error_msg[:50]}", status="failed")
                # 标记当前代理失败（线程安全）
                if current_proxy:
                    with _proxy_lock:
                        proxy_fail_count[current_proxy] = proxy_fail_count.get(current_proxy, 0) + 1
                        fails = proxy_fail_count[current_proxy]
                    if fails >= MAX_PROXY_FAILS:
                        reg_log(f"代理 {current_proxy} 已失败 {fails} 次，标记为不可用，下次自动切换", "warn", "proxy_blacklist")

                # ====== 失败不再重试（代理轮询已在 _get_next_proxy 中每次自动切换节点）======
                # 系统级阻碍（人机验证失败/封号）快速失败，下一个账号会自动用不同代理/节点
                with REG_LOCK:
                    REG_STATE["failed"] += 1
                    REG_STATE["errors"].append(f"#{i+1}: {error_msg[:300]}")
                reg_log(f"第 {i+1}/{actual_count} 个账号失败: {error_msg[:200]}", "error", "account_failed")
                logger.error(f"[REG] ❌ {i+1}/{actual_count} failed: {exc}")
            with REG_LOCK:
                REG_STATE["completed"] += 1

        # 执行注册：并发或顺序
        _worker_procs = []  # 并发模式下的 mihomo 工作实例
        if concurrent > 1:
            from concurrent.futures import ThreadPoolExecutor as _TPE, wait as _futures_wait, ALL_COMPLETED as _ALL_DONE

            # ====== 并发代理分配: 为每个并发任务创建独立的 mihomo 实例 ======
            proxy_per_task = [None] * actual_count  # 每个任务的代理 URL
            if _sub_proxy_url and concurrent > 1:
                try:
                    _spm = _sub_proxy()
                    if _spm and _spm.is_running:
                        alive_nodes = _spm.get_alive_nodes()
                        if alive_nodes:
                            reg_log(f"🔄 并发代理分配: {len(alive_nodes)} 个可用节点, {concurrent} 个并发任务", "ok", "concurrent_proxy")
                            for task_i in range(actual_count):
                                node = alive_nodes[task_i % len(alive_nodes)]
                                port = 28889 + task_i  # 每个任务用不同端口
                                ok, result_or_err, proc = _spm.create_worker(node, port)
                                if ok:
                                    proxy_per_task[task_i] = result_or_err
                                    _worker_procs.append(proc)
                                    reg_log(f"✅ 任务 {task_i+1}: 节点={node}, 代理={result_or_err}", "ok", f"worker_{task_i}")
                                else:
                                    proxy_per_task[task_i] = _sub_proxy_url  # 回退到主实例
                                    reg_log(f"⚠️ 任务 {task_i+1}: 创建失败({result_or_err})，使用主代理", "warn", f"worker_fail_{task_i}")
                        else:
                            reg_log("⚠️ 无可用节点，所有并发任务使用同一代理", "warn", "no_alive_nodes")
                except Exception as e:
                    reg_log(f"⚠️ 并发代理分配异常: {e}，所有任务使用主代理", "warn", "concurrent_proxy_err")

            reg_log(f"并发模式:同时注册 {concurrent} 个账号,总任务数={actual_count},独立代理实例={len(_worker_procs)}", "step", "concurrent_start")
            with _TPE(max_workers=concurrent) as executor:
                futures = []
                for i in range(actual_count):
                    if REG_STATE.get("stop_flag"):
                        break
                    # 每个任务独占一个槽位和一个独立代理
                    futures.append(executor.submit(_register_single, i, i, proxy_per_task[i]))
                # 等待所有线程完成
                _futures_wait(futures, return_when=_ALL_DONE)

            # 清理所有工作实例
            for proc in _worker_procs:
                try:
                    from 邮箱注册.subscription_proxy import SubscriptionProxyManager as _SPM
                    _SPM.cleanup_worker(proc)
                except Exception:
                    pass
            _worker_procs.clear()
            reg_log("所有并发代理实例已清理", "ok", "workers_cleaned")
        else:
            for i in range(count):
                if REG_STATE.get("stop_flag"):
                    break
                _register_single(i, 0)

    except Exception as exc:
        reg_log(f"注册任务发生致命错误:{exc}", "error", "fatal")
        logger.error(f"[REG] Fatal: {exc}")
    finally:
        reg_log(f"任务结束:成功 {REG_STATE.get('success', 0)},失败 {REG_STATE.get('failed', 0)}", "ok" if REG_STATE.get('failed', 0) == 0 else "warn", "finish")
        with REG_LOCK:
            REG_STATE["running"] = False
            REG_STATE["current"] = ""

@app.get("/api/browsers/available")
def available_browsers():
    """检测系统已安装的浏览器 + 所有支持的浏览器下载信息"""
    try:
        from 邮箱注册.cdp_browser import detect_installed_browsers, BROWSER_DOWNLOAD_INFO, BROWSER_PATHS
        installed = detect_installed_browsers()
        # 合并所有支持的浏览器（已安装 + 未安装但可下载）
        all_browsers = {}
        for key in BROWSER_PATHS:
            if key in installed:
                all_browsers[key] = {**installed[key], "installed": True}
            elif key in BROWSER_DOWNLOAD_INFO:
                dl = BROWSER_DOWNLOAD_INFO[key]
                all_browsers[key] = {"name": dl["name"], "installed": False, "download_url": dl["url"], "installer": dl.get("installer", "")}
            else:
                all_browsers[key] = {"name": key, "installed": False}
        return {"browsers": all_browsers, "installed_count": len(installed)}
    except Exception as e:
        return {"browsers": {}, "error": str(e)}


@app.get("/api/register/providers")
def register_providers():
    return {
        "python_supported": sorted(SUPPORTED_PY_REGISTER_PROVIDERS),
        "extension_only": sorted(EXTENSION_ONLY_PROVIDERS),
        "note": "extension_only 服务商需通过 邮箱注册 浏览器扩展流程执行,注册后导入凭证。"
    }

@app.post("/api/register/start")
def register_start(provider: str = Form("outlook"), count: int = Form(1), password: str = Form(""),
                   group_name: str = Form("批量注册"), proxy_list: str = Form(""),
                   captcha_key: str = Form(""), sms_config: str = Form(""),
                   browser: str = Form("chrome"), visible: bool = Form(True),
                   tun_mode: bool = Form(False), concurrent: int = Form(1)):
    provider = (provider or "outlook").strip().lower()
    browser = (browser or "chrome").strip().lower()
    logger.info("[API] register/start received: provider=%s, browser=%s, count=%d, concurrent=%d", provider, browser, count, concurrent)
    if provider not in SUPPORTED_PY_REGISTER_PROVIDERS:
        return {"status": "error", "message": f"{provider} 目前属于浏览器扩展流程,不能由此 FastAPI 后端直接创建。"}
    count = max(1, min(int(count or 1), 100))
    concurrent = max(1, min(int(concurrent or 1), 10))  # 最多10并发
    with REG_LOCK:
        if REG_STATE["running"]:
            return {"status": "error", "message": "注册任务运行中"}
    import json as _json
    ck = _json.loads(captcha_key) if captcha_key else None
    sc = _json.loads(sms_config) if sms_config else None
    t = threading.Thread(target=run_registration_task, args=(
        provider, count, password, group_name, proxy_list, ck, sc, browser, visible, tun_mode, concurrent), daemon=True)
    t.start()
    return {"status": "ok", "message": "注册任务已启动"}

@app.get("/api/register/status")
def register_status():
    with REG_LOCK:
        state = dict(REG_STATE)
    # 同步 CDP 引擎的当前步骤
    try:
        from 邮箱注册.cdp_outlook import get_current_reg_step
        state["current_cdp_step"] = get_current_reg_step()
    except Exception:
        pass
    return state

@app.post("/api/register/stop")
def register_stop():
    """\u505c\u6b62\u5f53\u524d\u6ce8\u518c\u4efb\u52a1\uff08\u53ea\u505c\u6b62\u6ce8\u518c\u6d41\u7a0b\uff0c\u4e0d\u5f71\u54cd\u5176\u4ed6\u529f\u80fd\uff09"""
    with REG_LOCK:
        REG_STATE["stop_flag"] = True
        REG_STATE["paused"] = False  # \u89e3\u9664\u6682\u505c\u4ee5\u4fbf\u7ebf\u7a0b\u80fd\u68c0\u6d4b\u5230\u505c\u6b62\u6807\u5fd7
        REG_STATE["running"] = False  # 立即标记为非运行，让前端按钮立即可用
        REG_STATE["current"] = "\u23f9 \u4efb\u52a1\u5df2\u505c\u6b62"
    try:
        from 邮箱注册.cdp_outlook import set_registration_stop, set_registration_paused, stop_registration_browser
        set_registration_stop(True)
        set_registration_paused(False)
        # \u5173\u95ed\u6ce8\u518c\u6d4f\u89c8\u5668\uff0c\u91ca\u653e\u963b\u585e\u4e2d\u7684 CDP \u8c03\u7528
        stop_registration_browser()
    except Exception:
        pass
    return {"status": "ok", "message": "\u4efb\u52a1\u5df2\u505c\u6b62\uff0c\u53ef\u4ee5\u91cd\u65b0\u5f00\u59cb\u6ce8\u518c"}

@app.post("/api/register/pause")
def register_pause():
    with REG_LOCK:
        if not REG_STATE["running"]:
            return {"status": "error", "message": "没有运行中的注册任务"}
        REG_STATE["paused"] = True
    try:
        from 邮箱注册.cdp_outlook import set_registration_paused
        set_registration_paused(True)
    except Exception:
        pass
    return {"status": "ok", "message": "注册已暂停"}

@app.post("/api/register/resume")
def register_resume():
    """继续注册：解除暂停，自动识别当前页面状态继续执行"""
    with REG_LOCK:
        if not REG_STATE["running"]:
            return {"status": "error", "message": "没有运行中的注册任务"}
        if not REG_STATE["paused"]:
            return {"status": "ok", "message": "任务未在暂停中"}
        REG_STATE["paused"] = False
        REG_STATE["current"] = "▶ 已恢复，正在识别页面状态..."
    try:
        from 邮箱注册.cdp_outlook import set_registration_paused, set_captcha_force_skip
        set_registration_paused(False)
        set_captcha_force_skip(False)  # 重置，让状态机自然处理
    except Exception:
        pass
    return {"status": "ok", "message": "注册已恢复，将自动识别当前页面状态继续"}

@app.post("/api/register/continue_captcha")
def register_continue_captcha():
    """Force-continue past CAPTCHA"""
    with REG_LOCK:
        REG_STATE["captcha_manual_solved"] = True
    try:
        from 邮箱注册.cdp_outlook import set_captcha_force_skip
        set_captcha_force_skip(True)
    except Exception:
        pass
    return {"status": "ok", "message": "已标记 CAPTCHA 为手动完成，程序将自动继续"}



# --------------- 邮箱注册 Credential Compatibility API ---------------
@app.get("/api/邮箱注册/credentials/dirs")
def 邮箱注册_credential_dirs():
    try:
        dirs = ensure_credential_dirs() if callable(ensure_credential_dirs) else {}
    except Exception as exc:
        return {"ok": False, "reason": str(exc), "credential_dir": BATCH_REG_DIR, "batch_dir": BATCH_REG_DIR}
    return {"ok": True, "credential_dir": dirs.get("credential_dir") or _credential_output_dir(), "auxiliary_dir": dirs.get("auxiliary_dir") or "", "batch_dir": BATCH_REG_DIR}

@app.get("/api/邮箱注册/credentials/status")
def 邮箱注册_credential_status(email: str = ""):
    email = (email or "").strip().lower()
    output_dir = _credential_output_dir()
    if not email or "@" not in email:
        return {"ok": False, "reason": "缺少邮箱", "credential_dir": output_dir}
    try:
        path = 邮箱注册_locate_credential_file(email, output_dir) if callable(邮箱注册_locate_credential_file) else None
        expected = 邮箱注册_credential_file_for(email, output_dir) if callable(邮箱注册_credential_file_for) else Path(output_dir) / f"{email}.txt"
        if not path or not Path(path).is_file():
            return {"ok": True, "email": email, "exists": False, "has_refresh_token": False, "credential_path": str(expected), "credential_dir": output_dir}
        line = Path(path).read_text(encoding="utf-8-sig").splitlines()[0].strip()
        parts = line.split("----")
        return {"ok": True, "email": email, "exists": True, "has_refresh_token": len(parts) >= 4 and bool(parts[3].strip()), "credential_path": str(path), "credential_dir": str(Path(path).parent), "combo": line, "refresh_token": parts[3].strip() if len(parts) >= 4 else ""}
    except Exception as exc:
        return {"ok": False, "reason": str(exc), "credential_dir": output_dir}

@app.post("/api/邮箱注册/credentials/validate")
def 邮箱注册_credentials_validate(payload: dict[str, Any] = None):
    payload = payload or {}
    try:
        if callable(邮箱注册_validate_credentials):
            return 邮箱注册_validate_credentials(payload)
        return {"ok": False, "reason": f"凭证校验模块不可用: {邮箱注册_CREDENTIAL_IMPORT_ERROR}"}
    except Exception as exc:
        return {"ok": False, "reason": str(exc)}

@app.post("/api/邮箱注册/credentials/open_dir")
def 邮箱注册_credentials_open_dir(payload: dict[str, Any] = None):
    payload = payload or {}
    target = str(payload.get("credential_path") or payload.get("credentialPath") or payload.get("output_dir") or payload.get("outputDir") or _credential_output_dir()).strip()
    p = Path(target).expanduser()
    if p.is_file():
        p = p.parent
    p.mkdir(parents=True, exist_ok=True)
    try:
        os.startfile(str(p))
        return {"ok": True, "output_dir": str(p), "reason": "ok"}
    except Exception as exc:
        # Fallback: just confirm directory exists
        return {"ok": True, "output_dir": str(p), "reason": f"目录已就绪,自动打开失败({exc}),请手动打开"}

# --------------- 邮箱注册 Backend Compatibility API ---------------
@app.post("/api/邮箱注册/proxy/normalize")
def 邮箱注册_proxy_normalize(req: ProxyTextRequest):
    proxies, errors = _normalize_proxy_text(req.proxy_text)
    return {
        "status": "ok" if proxies else "error",
        "ok": bool(proxies),
        "count": len(proxies),
        "proxy_text": "\n".join(proxies),
        "proxies": proxies,
        "errors": errors,
        "message": f"已转换 {len(proxies)} 个代理" if proxies else (errors[0] if errors else "代理列表为空"),
    }

@app.get("/api/邮箱注册/proxy/load")
def 邮箱注册_proxy_load():
    if load_runtime_config is None:
        return {"ok": False, "status": "error", "reason": f"邮箱注册 service_adapters 导入失败: {邮箱注册_ADAPTER_IMPORT_ERROR}", "proxies": [], "proxy_text": ""}
    try:
        config = load_runtime_config()
        proxy = config.get("proxy", {}) or {}
        items = _creation_proxy_items_from_config(proxy)
        all_items = proxy.get("all_items") or proxy.get("items") or []
        stable_items = proxy.get("stable_items") or []
        return {
            "ok": True,
            "status": "ok",
            "proxies": items,
            "proxy_text": "\n".join(items),
            "count": len(items),
            "all_count": len(all_items),
            "stable_count": len(stable_items),
            "auto_proxy": bool(config.get("auto_proxy", False)),
        }
    except Exception as exc:
        return {"ok": False, "status": "error", "reason": str(exc), "proxies": [], "proxy_text": "", "count": 0}

@app.post("/api/邮箱注册/proxy/check")
def 邮箱注册_proxy_check(req: ProxyTextRequest):
    if check_proxy_list is None or render_proxy_list is None:
        return {"ok": False, "status": "error", "reason": f"邮箱注册 service_adapters 导入失败: {邮箱注册_ADAPTER_IMPORT_ERROR}", "count": 0}
    proxy_text = (req.proxy_text or "").strip()
    if not proxy_text:
        return {"ok": False, "status": "error", "reason": "代理列表为空", "count": 0}
    try:
        max_checks = max(1, min(int(req.max_checks or 100), 300))
        max_working = max(1, min(int(req.max_working or 80), 200))
        proxies, check_lines = check_proxy_list(proxy_text, max_checks=max_checks, max_working=max_working)
        if not proxies:
            return {"ok": False, "status": "error", "reason": f"❌ {len([x for x in proxy_text.splitlines() if x.strip()])} 个代理全部检测失败", "count": 0, "logs": check_lines}
        checked_text = render_proxy_list(proxies)
        items = [line.strip() for line in checked_text.splitlines() if line.strip()]
        return {"ok": True, "status": "ok", "reason": f"✅ {len(items)}/{min(len(proxy_text.splitlines()), max_checks)} 个代理可用", "count": len(items), "proxy_text": checked_text, "proxies": items, "logs": check_lines}
    except Exception as exc:
        return {"ok": False, "status": "error", "reason": str(exc), "count": 0}

@app.post("/api/邮箱注册/proxy/save")
def 邮箱注册_proxy_save(req: ProxyTextRequest):
    if load_runtime_config is None or save_runtime_config is None:
        return {"ok": False, "status": "error", "reason": f"邮箱注册 service_adapters 导入失败: {邮箱注册_ADAPTER_IMPORT_ERROR}", "count": 0}
    raw = (req.proxy_text or "").strip()
    if not raw:
        return {"ok": False, "status": "error", "reason": "代理列表为空", "count": 0}
    try:
        if req.check:
            checked = 邮箱注册_proxy_check(req)
            if not checked.get("ok"):
                return checked
            items = checked.get("proxies") or []
            all_items = [line.strip() for line in raw.splitlines() if line.strip()]
            pool = [{"url": item, "source": "token_fastapi"} for item in items]
        else:
            items, errors = _normalize_proxy_text(raw)
            if not items:
                return {"ok": False, "status": "error", "reason": errors[0] if errors else "没有有效代理", "count": 0}
            all_items = [line.strip() for line in raw.splitlines() if line.strip()]
            pool = [{"url": item, "source": "token_fastapi"} for item in items]
        try:
            config = load_runtime_config()
        except Exception:
            config = {}
        proxy_section = config.get("proxy", {}) or {}
        proxy_section["items"] = items
        proxy_section["stable_items"] = items
        proxy_section["all_items"] = all_items
        proxy_section["pool"] = pool
        proxy_section["working"] = pool
        config["proxy"] = proxy_section
        config["auto_proxy"] = bool(items)
        path = save_runtime_config(config)
        return {"ok": True, "status": "ok", "reason": f"✅ 已保存 {len(items)} 个代理到 runtime_config.toml", "count": len(items), "proxy_text": "\n".join(items), "proxies": items, "path": str(path)}
    except Exception as exc:
        return {"ok": False, "status": "error", "reason": f"保存失败: {exc}", "count": 0}


@app.post("/api/邮箱注册/proxy/detect")
def 邮箱注册_proxy_detect(req: ProxyTextRequest):
    """两阶段检测：curl 快速预筛 → Chrome CDP 实际打开注册页验证"""
    global _AVAILABLE_PROXIES
    raw = (req.proxy_text or "").strip()
    if not raw:
        return {"ok": False, "status": "error", "reason": "代理列表为空", "count": 0, "available": [], "unavailable": []}

    normalized, norm_errors = _normalize_proxy_text(raw)
    if not normalized:
        return {"ok": False, "status": "error", "reason": norm_errors[0] if norm_errors else "无有效代理", "count": 0, "available": [], "unavailable": []}

    import subprocess, json as _j, concurrent.futures
    global _PROXY_DETECT_PROGRESS

    # 检查 curl 是否可用
    try:
        subprocess.run(["curl", "--version"], capture_output=True, timeout=5)
    except FileNotFoundError:
        return {"ok": False, "status": "error", "reason": "系统未安装curl，无法进行代理检测。请先安装curl。", "count": 0, "available": [], "unavailable": []}

    # 高并发检测：curl 验证 HTTPS 连接 + 注册页内容
    _PROXY_DETECT_PROGRESS = {"running": True, "done": 0, "total": len(normalized), "available": 0, "unavailable": 0, "stage": "检测中"}

    available = []
    unavailable = []
    signup_url = "https://signup.live.com/signup"
    ip_url = "https://api.ipify.org?format=json"
    timeout = 12

    def _check_one(proxy_url):
        """
        两步检测：
        1. HTTPS 连通性（curl socks5h:// 让代理解析 DNS，模拟 Chrome 的 SOCKS5 行为）
        2. 访问注册页验证内容
        """
        # 用 socks5h:// 强制代理解析 DNS（和 Chrome 的行为更接近）
        socks = proxy_url.replace("socks5://", "socks5h://").replace("socks4://", "socks4a://")
        # 如果已经是 socks5h:// 就不重复替换
        if not socks.startswith(("socks5h://", "socks4a://")):
            socks = proxy_url  # http 代理不需要替换

        ip = ""
        # 第一步：HTTPS 连通性检测
        try:
            r = subprocess.run(
                ["curl", "-s", "--max-time", "8", "--connect-timeout", "5", "--proxy", socks, ip_url],
                capture_output=True, text=True, timeout=12
            )
            if r.returncode == 0 and r.stdout.strip():
                data = _j.loads(r.stdout)
                ip = data.get("origin", "") or data.get("ip", "")
        except Exception:
            pass
        if not ip:
            return False, "", "HTTPS连不通"

        # 第二步：访问注册页
        try:
            r = subprocess.run(
                ["curl", "-s", "--max-time", str(timeout), "--connect-timeout", "8",
                 "-L", "--max-redirs", "5",
                 "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
                 "--proxy", socks, signup_url],
                capture_output=True, text=True, timeout=timeout + 5
            )
            body = (r.stdout or "").lower()
            signup_markers = ["signup", "create account", "个人数据导出许可",
                              "隐私声明", "password", "出生日期", "microsoft", "outlook"]
            if r.returncode == 0 and any(m in body for m in signup_markers) and len(body) > 500:
                return True, ip, "可访问注册页"
            elif r.returncode == 0:
                return False, ip, f"注册页响应异常(len={len(body)})"
            else:
                return False, ip, f"HTTP错误(rc={r.returncode})"
        except Exception as e:
            return False, ip, f"注册页访问失败:{str(e)[:40]}"

    max_workers = min(50, len(normalized))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_check_one, p): p for p in normalized}
        for fut in concurrent.futures.as_completed(futures):
            proxy_url = futures[fut]
            try:
                ok, ip, reason = fut.result()
                if ok:
                    available.append({"url": proxy_url, "ip": ip, "reason": reason})
                    _PROXY_DETECT_PROGRESS["available"] += 1
                else:
                    unavailable.append({"url": proxy_url, "reason": reason})
                    _PROXY_DETECT_PROGRESS["unavailable"] += 1
            except Exception as e:
                unavailable.append({"url": proxy_url, "reason": str(e)[:50]})
                _PROXY_DETECT_PROGRESS["unavailable"] += 1
            _PROXY_DETECT_PROGRESS["done"] += 1

    _PROXY_DETECT_PROGRESS["running"] = False

    _AVAILABLE_PROXIES = [a["url"] for a in available]
    with REG_LOCK:
        REG_STATE["available_proxies"] = _AVAILABLE_PROXIES[:]

    available_urls = [a["url"] for a in available]
    return {
        "ok": bool(available),
        "status": "ok" if available else "error",
        "reason": f"✅ {len(available)}/{len(normalized)} 个代理可访问注册页" if available else f"❌ {len(normalized)} 个代理均无法访问注册页",
        "count": len(available),
        "available": available,
        "available_urls": available_urls,
        "unavailable": unavailable,
        "total": len(normalized),
        "proxy_text": "\n".join(available_urls),
    }


@app.get("/api/邮箱注册/proxy/available")
def 邮箱注册_proxy_available():
    """获取当前可用代理列表"""
    with REG_LOCK:
        proxies = REG_STATE.get("available_proxies", [])
        rotate = REG_STATE.get("proxy_rotate", False)
    return {"ok": True, "proxies": proxies, "count": len(proxies), "rotate": rotate}

@app.get("/api/邮箱注册/proxy/detect_progress")
def 邮箱注册_proxy_detect_progress():
    """获取代理检测进度"""
    return {"ok": True, **_PROXY_DETECT_PROGRESS}

@app.post("/api/邮箱注册/proxy/clear")
def 邮箱注册_proxy_clear():
    """清空可用代理列表"""
    global _AVAILABLE_PROXIES, _PROXY_ROTATE
    _AVAILABLE_PROXIES = []
    _PROXY_ROTATE = False
    with REG_LOCK:
        REG_STATE["available_proxies"] = []
        REG_STATE["proxy_rotate"] = False
    return {"ok": True, "message": "已清空可用代理列表"}


@app.post("/api/邮箱注册/proxy/rotate")
def 邮箱注册_proxy_set_rotate(req: dict = Body(None)):
    """设置代理轮询开关"""
    global _PROXY_ROTATE
    enabled = bool((req or {}).get("enabled", True))
    _PROXY_ROTATE = enabled
    with REG_LOCK:
        REG_STATE["proxy_rotate"] = enabled
    return {"ok": True, "rotate": enabled}


# ====== 本地代理管理 ======

@app.get("/api/local_proxy/status")
def local_proxy_status():
    """获取本地代理配置状态"""
    with _LOCAL_PROXY_LOCK:
        return {"ok": True, "url": _LOCAL_PROXY["url"], "enabled": _LOCAL_PROXY["enabled"]}


@app.post("/api/local_proxy/set")
def local_proxy_set(req: dict = Body(None)):
    """设置本地代理地址（自动补全协议前缀）"""
    url = _normalize_proxy_url(str((req or {}).get("url", "")).strip())
    with _LOCAL_PROXY_LOCK:
        _LOCAL_PROXY["url"] = url
    _save_local_proxy_to_file()
    return {"ok": True, "url": url}


@app.post("/api/local_proxy/enable")
def local_proxy_enable(req: dict = Body(None)):
    """启用/禁用本地代理"""
    enabled = bool((req or {}).get("enabled", True))
    with _LOCAL_PROXY_LOCK:
        _LOCAL_PROXY["enabled"] = enabled
    _save_local_proxy_to_file()
    return {"ok": True, "enabled": enabled}


@app.get("/api/local_proxy/test")
def local_proxy_test():
    """测试本地代理连通性（多URL容错 + 详细错误信息）"""
    with _LOCAL_PROXY_LOCK:
        url = _LOCAL_PROXY["url"]
    if not url:
        return {"ok": False, "reason": "未设置本地代理地址"}
    import subprocess
    socks = url.replace("socks5://", "socks5h://").replace("socks4://", "socks4a://")
    if not socks.startswith(("socks5h://", "socks4a://")):
        socks = url  # http 代理不需要替换

    # 多个测试URL容错
    test_urls = [
        "https://api.ipify.org?format=json",
        "https://ipinfo.io/json",
        "https://httpbin.org/ip",
        "http://ip-api.com/json",
    ]
    last_error = ""
    for test_url in test_urls:
        try:
            r = subprocess.run(
                ["curl", "-s", "--max-time", "15", "--connect-timeout", "8", "--proxy", socks, test_url],
                capture_output=True, text=True, timeout=20
            )
            if r.returncode == 0 and r.stdout.strip():
                try:
                    info = json.loads(r.stdout)
                    ip = info.get("ip", "") or info.get("origin", "") or info.get("ip", "")
                    country = info.get("country", "")
                    city = info.get("city", "")
                    org = info.get("org", "")
                    if ip:
                        return {"ok": True, "ip": ip, "country": country, "city": city, "org": org}
                except json.JSONDecodeError:
                    last_error = f"响应解析失败: {r.stdout[:100]}"
                    continue
            else:
                stderr_snippet = (r.stderr or "").strip()[:200]
                last_error = f"curl返回码={r.returncode}" + (f", stderr={stderr_snippet}" if stderr_snippet else "")
                continue
        except subprocess.TimeoutExpired:
            last_error = "curl超时(15秒)"
            continue
        except FileNotFoundError:
            return {"ok": False, "reason": "系统未安装curl，无法测试代理连通性"}
        except Exception as e:
            last_error = str(e)[:200]
            continue

    return {"ok": False, "reason": f"本地代理连接失败: {last_error}"}


@app.get("/api/邮箱注册/config")
def 邮箱注册_config_get():
    if load_runtime_config is None:
        return {"ok": False, "status": "error", "reason": f"邮箱注册 service_adapters 导入失败: {邮箱注册_ADAPTER_IMPORT_ERROR}", "config": {}}
    try:
        return {"ok": True, "status": "ok", "config": load_runtime_config()}
    except Exception as exc:
        return {"ok": False, "status": "error", "reason": str(exc), "config": {}}

@app.post("/api/邮箱注册/config")
def 邮箱注册_config_save(req: RuntimeConfigRequest):
    if save_runtime_config is None:
        return {"ok": False, "status": "error", "reason": f"邮箱注册 service_adapters 导入失败: {邮箱注册_ADAPTER_IMPORT_ERROR}"}
    try:
        path = save_runtime_config(req.config or {})
        return {"ok": True, "status": "ok", "path": str(path)}
    except Exception as exc:
        return {"ok": False, "status": "error", "reason": str(exc)}

@app.get("/api/stats")
def get_stats(db: Session = Depends(get_db)):
    total = db.query(Account).count()
    groups = db.query(Group).all()
    gc = {g.name: db.query(Account).filter(Account.group_name == g.name).count() for g in groups}
    batch_count = len([f for f in os.listdir(BATCH_REG_DIR) if f.endswith(".txt")]) if os.path.isdir(BATCH_REG_DIR) else 0
    return {"total_accounts": total, "total_groups": len(groups), "group_counts": gc, "batch_dir_count": batch_count}

@app.post("/api/batch_import_dir")
def batch_import_dir(group: str = "批量注册", db: Session = Depends(get_db)):
    if not os.path.isdir(BATCH_REG_DIR):
        return {"status": "error", "message": "目录不存在"}
    added = 0
    skipped = 0
    for fname in os.listdir(BATCH_REG_DIR):
        if not fname.endswith(".txt"):
            continue
        fpath = os.path.join(BATCH_REG_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read().strip()
        except Exception:
            continue
        parts = content.split("----")
        if len(parts) < 2:
            continue
        email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', parts[0])
        if not email_match:
            continue
        email = email_match.group(0)
        if db.query(Account).filter(Account.email == email).first():
            skipped += 1
            continue
        acc = Account(email=email, pwd=parts[1].strip(),
                      client_id=parts[2].strip() if len(parts) > 2 else "14d82eec-204b-4c2f-b7e8-296a70dab67e",
                      token=parts[3].strip() if len(parts) > 3 else "",
                      raw=content, group_name=group)
        db.add(acc)
        added += 1
    if added > 0:
        if not db.query(Group).filter(Group.name == group).first():
            db.add(Group(name=group))
        db.commit()
    return {"status": "ok", "added": added, "skipped": skipped}

@app.get("/debug")
def debug_info():
    return {
        "root_dir": os.path.dirname(os.path.abspath(__file__)),
        "frontend_file": os.path.join(os.path.dirname(os.path.abspath(__file__)), "integrated_frontend.html"),
        "file_exists": os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "integrated_frontend.html")),
        "batch_reg_dir": BATCH_REG_DIR,
    }

# --------------- Subscription Proxy API ---------------
try:
    from 邮箱注册.subscription_proxy import get_manager as _get_sub_proxy_manager
    from 邮箱注册.subscription_proxy import test_proxy as _test_sys_proxy
    _SUB_PROXY_AVAILABLE = True
except Exception as _sub_exc:
    _SUB_PROXY_AVAILABLE = False

def _sub_proxy():
    if not _SUB_PROXY_AVAILABLE:
        return None
    return _get_sub_proxy_manager()

class SubProxyUrlsRequest(BaseModel):
    urls: List[str] = []
    names: List[str] = []

@app.get("/api/sub_proxy/status")
def sub_proxy_status():
    mgr = _sub_proxy()
    if mgr is None:
        return {"ok": False, "error": "proxy module unavailable"}
    st = mgr.status()
    # 添加订阅列表详情
    subs = []
    for s in mgr.subscriptions:
        subs.append({"url": s["url"], "name": s["name"], "node_count": -1, "error": ""})
    st["subscriptions"] = subs
    st["total_nodes"] = st.get("node_count", 0)
    return {"ok": True, **st}

@app.post("/api/sub_proxy/add")
def sub_proxy_add(req: SubProxyUrlsRequest):
    try:
        mgr = _sub_proxy()
        if mgr is None:
            return {"ok": False, "error": "proxy module unavailable"}
        added = 0
        failed = 0
        for url in req.urls:
            ok, msg = mgr.add(url)
            if ok:
                added += 1
            else:
                failed += 1
        # 添加后自动更新 mihomo 配置
        if added > 0:
            try:
                if mgr.is_running:
                    mgr.stop()
                    import time; time.sleep(1)
                mgr.start()
            except Exception:
                pass
        return {"ok": True, "added": added, "failed": failed, "total": len(mgr.subscriptions)}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.post("/api/sub_proxy/remove")
def sub_proxy_remove(req: dict = Body(None)):
    mgr = _sub_proxy()
    if mgr is None:
        return {"ok": False, "error": "proxy module unavailable"}
    url = (req or {}).get("url", "")
    if not url:
        return {"ok": False, "error": "url required"}
    ok, msg = mgr.remove(url)
    return {"ok": ok, "message": msg}

@app.post("/api/sub_proxy/clear")
def sub_proxy_clear():
    mgr = _sub_proxy()
    if mgr is None:
        return {"ok": False, "error": "proxy module unavailable"}
    mgr.clear()
    return {"ok": True, "message": "cleared"}

@app.post("/api/sub_proxy/start")
def sub_proxy_start():
    mgr = _sub_proxy()
    if mgr is None:
        return {"ok": False, "error": "proxy module unavailable"}
    ok, msg = mgr.start()
    return {"ok": ok, "message": msg, "proxy_url": mgr.proxy_url if ok else ""}

@app.post("/api/sub_proxy/stop")
def sub_proxy_stop():
    mgr = _sub_proxy()
    if mgr is None:
        return {"ok": False, "error": "proxy module unavailable"}
    result = mgr.stop()
    if result is None:
        return {"ok": True, "message": "proxy stopped"}
    ok, msg = result
    return {"ok": ok, "message": msg}

@app.post("/api/sub_proxy/refresh")
def sub_proxy_refresh():
    mgr = _sub_proxy()
    if mgr is None:
        return {"ok": False, "error": "proxy module unavailable"}
    # 重新更新配置并重启
    ok, msg = mgr.stop()
    ok2, msg2 = mgr.start()
    return {"ok": ok2, "message": f"重启: {msg}; {msg2}"}

@app.get("/api/sub_proxy/test")
def sub_proxy_test():
    mgr = _sub_proxy()
    if mgr is None:
        return {"ok": False, "error": "proxy module unavailable"}
    result = mgr.test_proxy()
    return {"ok": result.get("ok", False), **result}

@app.get("/api/sub_proxy/nodes")
def sub_proxy_nodes():
    mgr = _sub_proxy()
    if mgr is None:
        return {"ok": False, "nodes": [], "error": "proxy module unavailable"}
    nodes = mgr.get_nodes()
    return {"ok": True, "nodes": nodes, "count": len(nodes)}

@app.post("/api/sub_proxy/rotate")
def sub_proxy_rotate():
    mgr = _sub_proxy()
    if mgr is None:
        return {"ok": False, "message": "proxy module unavailable"}
    return mgr.rotate_node()

@app.post("/api/sub_proxy/find_alive")
def sub_proxy_find_alive():
    mgr = _sub_proxy()
    if mgr is None:
        return {"ok": False, "message": "proxy module unavailable"}
    ok, msg = mgr.find_alive_node()
    return {"ok": ok, "message": msg}

@app.get("/api/sub_proxy/nodes")
def sub_proxy_nodes():
    mgr = _sub_proxy()
    if mgr is None:
        return {"ok": False, "error": "proxy module unavailable"}
    nodes = mgr.get_nodes()
    return {"ok": True, "nodes": nodes, "count": len(nodes)}

@app.post("/api/sub_proxy/switch")
def sub_proxy_switch(req: dict = Body(None)):
    mgr = _sub_proxy()
    if mgr is None:
        return {"ok": False, "message": "proxy module unavailable"}
    node_name = (req or {}).get("name", "")
    if not node_name:
        return {"ok": False, "message": "节点名称不能为空"}
    ok, msg = mgr.switch_to_node(node_name)
    return {"ok": ok, "message": msg}


def _kill_port_occupants(port: int):
    """自动杀掉占用指定端口的旧进程，等待端口释放"""
    import subprocess, socket
    killed = False
    for _ in range(3):  # 最多重试 3 轮
        try:
            out = subprocess.check_output(
                f'netstat -aon | findstr ":{port} " | findstr "LISTENING"',
                shell=True, text=True, stderr=subprocess.DEVNULL
            )
        except subprocess.CalledProcessError:
            break  # 端口没被占用
        pids = set()
        for line in out.strip().splitlines():
            parts = line.split()
            if len(parts) >= 5:
                pid = parts[-1]
                if pid != "0":
                    pids.add(pid)
        if not pids:
            break
        for pid in pids:
            try:
                subprocess.run(["taskkill", "/PID", pid, "/F"],
                               capture_output=True, timeout=5)
                print(f"[CLEANUP] 已清理端口 {port} 上的旧进程 PID={pid}")
                killed = True
            except Exception:
                pass
        time.sleep(1)
    if killed:
        # 等端口真正释放
        for _ in range(10):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(1)
                s.connect(("127.0.0.1", port))
                s.close()
                time.sleep(0.5)
            except Exception:
                break  # 端口已释放


if __name__ == "__main__":
    import uvicorn
    _kill_port_occupants(PORT)
    uvicorn.run(app, host="0.0.0.0", port=PORT)

