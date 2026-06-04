"""Test proxy with httpx + socksio"""
import httpx
import time

proxy_raw = "gate2.ipweb.cc:7778:B_72756_JP___90_pphKvB9y:2442375"
parts = proxy_raw.split(":")
host, port, user, pwd = parts[0], int(parts[1]), parts[2], parts[3]

tests = [
    ("SOCKS5", f"socks5://{user}:{pwd}@{host}:{port}"),
    ("SOCKS5H", f"socks5h://{user}:{pwd}@{host}:{port}"),
    ("HTTP", f"http://{user}:{pwd}@{host}:{port}"),
]

for name, proxy_url in tests:
    print(f"\n=== {name}: {proxy_url[:60]}... ===")
    try:
        transport = httpx.HTTPTransport(proxy=proxy_url) if name == "HTTP" else None
        if transport:
            client = httpx.Client(transport=transport, timeout=20)
        else:
            client = httpx.Client(proxy=proxy_url, timeout=20)
        
        r = client.get("http://ipinfo.io")
        print(f"  Status: {r.status_code}")
        print(f"  Body: {r.text[:300]}")
        if r.status_code == 200:
            print(f"  === PROXY WORKS! ===")
            break
    except Exception as e:
        print(f"  Error: {type(e).__name__}: {str(e)[:150]}")
    finally:
        try: client.close()
        except: pass
