"""Test proxy - extended protocol detection"""
import socket, time, struct, base64

host = 'gate2.ipweb.cc'
port = 7778
user = 'B_72756_JP___90_pphKvB9y'
pwd = '2442375'

# Test 1: SOCKS5 with only user/pass auth method
print("=== Test 1: SOCKS5 user/pass only ===")
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(30)
s.connect((host, port))
s.send(b'\x05\x01\x02')  # VER=5, NMETHODS=1, METHOD=0x02 (user/pass)
try:
    resp = s.recv(1024)
    if resp:
        print(f"Got {len(resp)} bytes: {resp.hex()}")
    else:
        print("Empty response (0 bytes)")
except socket.timeout:
    print("Timed out after 30s")
except ConnectionResetError as e:
    print(f"Connection reset: {e}")
s.close()

# Test 2: SOCKS5 no auth only
print("\n=== Test 2: SOCKS5 no-auth only ===")
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(30)
s.connect((host, port))
s.send(b'\x05\x01\x00')  # VER=5, NMETHODS=1, METHOD=0x00 (no auth)
try:
    resp = s.recv(1024)
    if resp:
        print(f"Got {len(resp)} bytes: {resp.hex()}")
    else:
        print("Empty response (0 bytes)")
except socket.timeout:
    print("Timed out")
except ConnectionResetError as e:
    print(f"Connection reset: {e}")
s.close()

# Test 3: Wait longer then try
print("\n=== Test 3: Wait 5s then send SOCKS5 ===")
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(30)
s.connect((host, port))
time.sleep(5)
s.send(b'\x05\x01\x02')
try:
    resp = s.recv(1024)
    if resp:
        print(f"Got {len(resp)} bytes: {resp.hex()}")
    else:
        print("Empty response")
except socket.timeout:
    print("Timed out")
except ConnectionResetError as e:
    print(f"Connection reset: {e}")
s.close()

# Test 4: HTTP CONNECT with Basic auth
print("\n=== Test 4: HTTP CONNECT ===")
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(15)
s.connect((host, port))
cred = base64.b64encode(f"{user}:{pwd}".encode()).decode()
req = f"CONNECT api.ipify.org:443 HTTP/1.1\r\nHost: api.ipify.org:443\r\nProxy-Authorization: Basic {cred}\r\n\r\n"
s.send(req.encode())
try:
    resp = s.recv(4096)
    decoded = resp.decode(errors="replace")
    print(f"Got {len(resp)} bytes: {decoded[:300]}")
except socket.timeout:
    print("Timed out")
except ConnectionResetError as e:
    print(f"Connection reset: {e}")
s.close()

# Test 5: Try raw HTTP GET
print("\n=== Test 5: HTTP GET via proxy ===")
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(15)
s.connect((host, port))
cred = base64.b64encode(f"{user}:{pwd}".encode()).decode()
req = f"GET http://api.ipify.org/?format=json HTTP/1.0\r\nHost: api.ipify.org\r\nProxy-Authorization: Basic {cred}\r\n\r\n"
s.send(req.encode())
try:
    resp = s.recv(4096)
    decoded = resp.decode(errors="replace")
    print(f"Got {len(resp)} bytes: {decoded[:300]}")
except socket.timeout:
    print("Timed out")
except ConnectionResetError as e:
    print(f"Connection reset: {e}")
s.close()

# Test 6: Check all 5 accounts quickly
print("\n=== Test 6: Quick check all accounts ===")
accounts = [
    ('B_72756_JP___90_pphKvB9y', '2442375'),
    ('B_72756_JP___90_Eip7s5t5', '2442375'),
    ('B_72756_JP___90_4h4v6mIQ', '2442375'),
    ('B_72756_JP___90_MnF804jk', '2442375'),
    ('B_72756_JP___90_Y0jDhEY5', '2442375'),
]
for u, p in accounts:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(8)
    try:
        s.connect((host, port))
        s.send(b'\x05\x01\x02')
        resp = s.recv(1024)
        if resp:
            print(f"  {u}: GOT RESPONSE ({len(resp)} bytes)!")
        else:
            print(f"  {u}: empty")
    except socket.timeout:
        print(f"  {u}: timeout")
    except Exception as e:
        print(f"  {u}: error - {type(e).__name__}")
    finally:
        s.close()
