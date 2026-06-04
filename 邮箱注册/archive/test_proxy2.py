"""Test proxy - try raw HTTP request"""
import socket

host = 'gate2.ipweb.cc'
port = 7778
user = 'B_72756_JP___90_pphKvB9y'
pwd = '2442375'

# Method 1: Try sending HTTP request directly through proxy
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(15)
s.connect((host, port))
print('TCP connected')

# Try raw HTTP proxy (no CONNECT, just direct request)
import base64
cred = base64.b64encode(f'{user}:{pwd}'.encode()).decode()
http_req = f'GET http://api.ipify.org/?format=json HTTP/1.0\r\nHost: api.ipify.org\r\nProxy-Authorization: Basic {cred}\r\n\r\n'
print('Sending HTTP request...')
s.send(http_req.encode())

try:
    resp = s.recv(4096)
    print('Response:', resp.decode()[:500])
except socket.timeout:
    print('Timeout - no response')
s.close()

# Method 2: Try sending just the SOCKS5 greeting without auth methods count
print('\n--- Method 2: Minimal SOCKS5 ---')
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(15)
s.connect((host, port))

# Try SOCKS4
import struct
s4_req = b'\x04\x01' + struct.pack('>H', 443) + socket.inet_aton('54.157.226.194') + b'\x00'  # api.ipify.org IP
s.send(s4_req)
try:
    resp = s.recv(1024)
    print('SOCKS4 response:', resp.hex(), 'len=', len(resp))
except socket.timeout:
    print('SOCKS4 timeout')
s.close()

# Method 3: Check if it responds to anything at all
print('\n--- Method 3: Just send random data ---')
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(10)
s.connect((host, port))
s.send(b'HELLO\r\n')
try:
    resp = s.recv(1024)
    print('Response:', repr(resp))
except socket.timeout:
    print('Timeout')
s.close()
