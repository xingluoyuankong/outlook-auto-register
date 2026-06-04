"""Deep proxy debug - raw protocol analysis"""
import socket, time, struct

host = 'gate2.ipweb.cc'
port = 7778
user = 'B_72756_JP___90_pphKvB9y'
pwd = '2442375'

# Resolve DNS first
print(f"Resolving {host}...")
ips = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
resolved_ips = list(set([ip[4][0] for ip in ips]))
print(f"Resolved to: {resolved_ips}")

for ip in resolved_ips[:3]:
    print(f"\n{'='*50}")
    print(f"Testing IP: {ip}:{port}")
    
    # SOCKS5 with username/password auth
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(15)
    try:
        s.connect((ip, port))
        print(f"  TCP connected")
        
        # Send SOCKS5 greeting with ONLY user/pass method (0x02)
        greeting = b'\x05\x01\x02'
        print(f"  Sending: {greeting.hex()} (SOCKS5, 1 method: user/pass)")
        s.send(greeting)
        
        # Read with a loop (some proxies are slow)
        resp = b''
        start = time.time()
        while time.time() - start < 10:
            try:
                chunk = s.recv(1024)
                if chunk:
                    resp += chunk
                    print(f"  Received {len(chunk)} bytes after {time.time()-start:.1f}s: {chunk.hex()}")
                    break
                else:
                    print(f"  Connection closed by server after {time.time()-start:.1f}s")
                    break
            except socket.timeout:
                print(f"  Timeout waiting for response ({time.time()-start:.1f}s)")
                break
            except ConnectionResetError:
                print(f"  Connection reset after {time.time()-start:.1f}s")
                break
        
        if resp:
            if resp[0] == 0x05 and resp[1] == 0x02:
                print("  Server wants user/pass auth")
                auth = b'\x01'
                auth += bytes([len(user)]) + user.encode()
                auth += bytes([len(pwd)]) + pwd.encode()
                print(f"  Sending auth (user={user}, pwd={pwd})")
                s.send(auth)
                
                auth_resp = b''
                try:
                    auth_resp = s.recv(1024)
                    print(f"  Auth response: {auth_resp.hex()}")
                    if len(auth_resp) >= 2 and auth_resp[1] == 0x00:
                        print("  AUTH SUCCESS!")
                        # Try CONNECT
                        req = b'\x05\x01\x00\x03'
                        req += bytes([len(b'api.ipify.org')]) + b'api.ipify.org'
                        req += struct.pack('>H', 80)
                        s.send(req)
                        conn_resp = s.recv(1024)
                        print(f"  CONNECT response: {conn_resp.hex()}")
                        if len(conn_resp) >= 2 and conn_resp[1] == 0x00:
                            print("  CONNECT SUCCESS! Sending HTTP request...")
                            s.send(b'GET /?format=json HTTP/1.0\r\nHost: api.ipify.org\r\n\r\n')
                            http_resp = s.recv(4096)
                            print(f"  HTTP response: {http_resp.decode(errors='replace')[:300]}")
                    else:
                        print(f"  AUTH FAILED")
                except Exception as e:
                    print(f"  Auth error: {e}")
            elif resp[0] == 0x05 and resp[1] == 0x00:
                print("  Server accepted no-auth!")
            else:
                print(f"  Unexpected response: ver={hex(resp[0])} method={hex(resp[1])}")
        else:
            print("  No response at all")
    except Exception as e:
        print(f"  Error: {type(e).__name__}: {e}")
    finally:
        s.close()

# Also test: what if we need to wait longer?
print(f"\n{'='*50}")
print("Long wait test (20s timeout)...")
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(25)
try:
    s.connect((resolved_ips[0], port))
    print("Connected, sending SOCKS5 greeting...")
    s.send(b'\x05\x01\x02')
    print("Waiting up to 20s...")
    try:
        resp = s.recv(1024)
        if resp:
            print(f"Got response: {resp.hex()}")
        else:
            print("Empty (connection closed)")
    except socket.timeout:
        print("Timed out after 25s")
except Exception as e:
    print(f"Error: {e}")
finally:
    s.close()
