#!/usr/bin/env python3
"""
hidexx API client - calls a.hidexx.com directly
Register -> claim trial -> wait -> fetch subscription
"""

import re, os, random, string, time
import urllib.request, urllib.parse, http.cookiejar

BASE_URL = "https://a.hidexx.com"

def randstr(n, charset=string.ascii_lowercase + string.digits):
    return ''.join(random.choices(charset, k=n))

def make_email():
    return f"hx{randstr(8)}@outlook.com"

def make_password():
    return f"Hx@{randstr(10, string.ascii_letters + string.digits)}"

def create_session(proxy_url=None):
    jar = http.cookiejar.CookieJar()
    if proxy_url:
        # Use PySocks for proper SOCKS5 support (avoids SSL issues with urllib)
        import socks
        import socket as _socket
        proxy_type, proxy_host, proxy_port = None, None, None
        if proxy_url.startswith("socks5h://"):
            proxy_type = socks.SOCKS5
            addr = proxy_url.replace("socks5h://", "")
        elif proxy_url.startswith("socks5://"):
            proxy_type = socks.SOCKS5
            addr = proxy_url.replace("socks5://", "")
        elif proxy_url.startswith("http://"):
            # fallback to HTTP proxy
            proxy_handler = urllib.request.ProxyHandler({
                'http': proxy_url,
                'https': proxy_url,
            })
            opener = urllib.request.build_opener(
                urllib.request.HTTPCookieProcessor(jar), proxy_handler)
            opener.addheaders = [('User-Agent', 'Mozilla/5.0')]
            return opener
        else:
            proxy_type = socks.SOCKS5
            addr = proxy_url
        host_port = addr.rsplit(":", 1)
        proxy_host = host_port[0]
        proxy_port = int(host_port[1])
        _default_socket = _socket.socket
        socks.set_default_proxy(proxy_type, proxy_host, proxy_port)
        _socket.socket = socks.socksocket
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    opener.addheaders = [('User-Agent', 'Mozilla/5.0')]
    return opener

def get_captcha(opener):
    resp = opener.open(BASE_URL + "/users/vcode")
    data = resp.read()
    import tempfile, subprocess
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
        f.write(data)
        tmp = f.name
    try:
        out = subprocess.check_output(['tesseract', tmp, 'stdout'], timeout=10, stderr=subprocess.DEVNULL)
        code = out.decode().strip().replace(' ', '')
        return code if len(code) == 4 and code.isalnum() else None
    except:
        return None
    finally:
        os.unlink(tmp)

def register(opener, email, password, max_attempts=10):
    for i in range(max_attempts):
        opener.open(BASE_URL + "/users/register")
        code = get_captcha(opener)
        if not code:
            continue
        form = urllib.parse.urlencode({'email': email, 'pass1': password, 'pass2': password, 'checkcode': code}).encode()
        resp = opener.open(urllib.request.Request(BASE_URL + "/users/register", data=form))
        url = resp.url
        if '/users/ucenter' in url:
            return True
        body = resp.read().decode('utf-8', errors='ignore')
        if '已注册' in body or '已存在' in body:
            return False
    return False

def parse_trial_params(html):
    sid_m = re.search(r"name=['\"]?sid['\"]?\s+value=['\"]?([^'\">\s]+)", html)
    cs_m = re.search(r"name=['\"]?checksum['\"]?\s+value=['\"]?([^'\">\s]+)", html)
    if sid_m and cs_m:
        return sid_m.group(1), cs_m.group(1)
    return None, None

def claim_trial(opener, line_id="1"):
    resp = opener.open(BASE_URL + "/users/ucenter")
    html = resp.read().decode('utf-8', errors='ignore')
    sid, checksum = parse_trial_params(html)
    if not sid:
        return False
    form = urllib.parse.urlencode({'sid': sid, 'checksum': checksum, 'line_id': line_id, 'quantity': '1'}).encode()
    resp = opener.open(urllib.request.Request(BASE_URL + "/orders/request_day_trial", data=form))
    final = urllib.parse.unquote(resp.url)
    body = resp.read().decode('utf-8', errors='ignore')
    return 'success' in final or '领取成功' in body or '领取成功' in final

def get_subscriptions(opener):
    resp = opener.open(BASE_URL + "/users/ucenter")
    html = resp.read().decode('utf-8', errors='ignore')
    re_link = re.compile(r"copyText\('([^']+)'\)")
    matches = re_link.findall(html)
    return [m.replace('&amp;', '&') for m in matches]

def register_and_get_subscription(log=print, proxy_url=None):
    """Full flow: register -> claim -> wait -> get subscription URL"""
    email = make_email()
    password = make_password()
    log(f"注册 hidexx 账号: {email}")

    opener = create_session(proxy_url=proxy_url)
    if not register(opener, email, password):
        log("❌ hidexx 注册失败")
        return None

    log("注册成功, 领取免费试用...")
    if not claim_trial(opener):
        log("❌ 领取试用失败")
        return None

    log("领取成功, 等待订阅生效 (15s)...")
    time.sleep(15)

    for attempt in range(3):
        subs = get_subscriptions(opener)
        if subs:
            log(f"✅ 获取到 {len(subs)} 个订阅链接")
            return subs[0]
        log(f"   订阅未就绪 (attempt {attempt+1}), 再等 10s...")
        time.sleep(10)

    log("❌ 获取订阅失败")
    return None
