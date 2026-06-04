"""Deep proxy analysis - capture any response"""
import socket, time, select

proxy_raw = "gate2.ipweb.cc:7778:B_72756_JP___90_pphKvB9y:2442375"
parts = proxy_raw.split(":")
host, port, user, pwd = parts[0], int(parts[1]), parts[2], parts[3]

# Test 1: Connect and wait for server to speak first
print("=== Test 1: Wait for server banner ===")
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(15)
s.connect((host, port))
print("TCP connected, waiting for server to send data...")
ready = select.select([s], [], [], 10)
if ready[0]:
    data = s.recv(4096)
    if data:
        print(f"Server banner ({len(data)} bytes): {data.hex()}")
        print(f"Text: {data.decode(errors='replace')}")
    else:
        print("Server sent empty data (closed connection)")
else:
    print("No data from server in 10s")
s.close()

# Test 2: Send SOCKS5 with all methods
print("\n=== Test 2: SOCKS5 all methods ===")
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(15)
s.connect((host, port))
greeting = b'\x05\x03\x00\x01\x02'  # VER=5, NMETHODS=3, methods: no-auth, GSSAPI, user-pass
print(f"Sending: {greeting.hex()}")
s.send(greeting)
ready = select.select([s], [], [], 10)
if ready[0]:
    data = s.recv(4096)
    if data:
        print(f"Response ({len(data)} bytes): {data.hex()}")
        print(f"Text: {data.decode(errors='replace')}")
    else:
        print("Empty (closed)")
else:
    print("No response in 10s")
s.close()

# Test 3: Send SOCKS4 connect
print("\n=== Test 3: SOCKS4 ===")
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(15)
s.connect((host, port))
import struct
# SOCKS4 CONNECT to 1.1.1.1:80
socks4_req = b'\x04\x01\x00\x50' + socket.inet_aton('1.1.1.1') + user.encode() + b'\x00'
print(f"Sending SOCKS4: {socks4_req.hex()}")
s.send(socks4_req)
ready = select.select([s], [], [], 10)
if ready[0]:
    data = s.recv(4096)
    if data:
        print(f"Response ({len(data)} bytes): {data.hex()}")
    else:
        print("Empty (closed)")
else:
    print("No response in 10s")
s.close()

# Test 4: HTTP CONNECT with exact curl format
print("\n=== Test 4: HTTP CONNECT (exact curl format) ===")
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(15)
s.connect((host, port))
import base64
cred = base64.b64encode(f"{user}:{pwd}".encode()).decode()
http_req = f"CONNECT ipinfo.io:443 HTTP/1.1\r\nHost: ipinfo.io:443\r\nProxy-Authorization: Basic {cred}\r\nUser-Agent: curl/8.19.0\r\nProxy-Connection: Keep-Alive\r\n\r\n"
print(f"Sending HTTP CONNECT...")
s.send(http_req.encode())
ready = select.select([s], [], [], 10)
if ready[0]:
    data = s.recv(4096)
    if data:
        print(f"Response ({len(data)} bytes):")
        print(data.decode(errors='replace')[:500])
    else:
        print("Empty (closed)")
else:
    print("No response in 10s")
s.close()

# Test 5: Plain HTTP GET (not CONNECT)
print("\n=== Test 5: HTTP GET (plain proxy) ===")
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(15)
s.connect((host, port))
cred = base64.b64encode(f"{user}:{pwd}".encode()).decode()
http_req = f"GET http://ipinfo.io/ HTTP/1.0\r\nHost: ipinfo.io\r\nProxy-Authorization: Basic {cred}\r\nUser-Agent: curl/8.19.0\r\n\r\n"
print(f"Sending HTTP GET...")
s.send(http_req.encode())
ready = select.select([s], [], [], 15)
if ready[0]:
    data = s.recv(4096)
    if data:
        print(f"Response ({len(data)} bytes):")
        print(data.decode(errors='replace')[:500])
    else:
        print("Empty (closed)")
else:
    print("No response in 15s")
s.close()

# Test 6: No auth at all
print("\n=== Test 6: HTTP GET no auth ===")
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(15)
s.connect((host, port))
http_req = f"GET http://ipinfo.io/ HTTP/1.0\r\nHost: ipinfo.io\r\n\r\n"
s.send(http_req.encode())
ready = select.select([s], [], [], 15)
if ready[0]:
    data = s.recv(4096)
    if data:
        print(f"Response ({len(data)} bytes):")
        print(data.decode(errors='replace')[:500])
    else:
        print("Empty (closed)")
else:
    print("No response in 15s")
s.close()

# Test 7: Try connecting to a different resolved IP
print("\n=== Test 7: Try alternate DNS resolution ===")
import socket as sock_mod
for ip in ["172.237.82.251", "172.237.71.95", "104.64.193.33"]:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(10)
    try:
        s.connect((ip, port))
        print(f"  Connected to {ip}, waiting 3s...")
        time.sleep(1)
        # Send a simple hello
        s.send(b"hello\r\n")
        ready = select.select([s], [], [], 5)
        if ready[0]:
            data = s.recv(4096)
            if data:
                print(f"    Got {len(data)} bytes: {data[:100]}")
            else:
                print(f"    Connection closed")
        else:
            print(f"    No response")
    except Exception as e:
        print(f"  {ip}: {e}")
    finally:
        s.close()
