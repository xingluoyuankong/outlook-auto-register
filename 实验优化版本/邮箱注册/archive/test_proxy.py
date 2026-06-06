"""Test proxy connectivity"""
import socket
import struct

host = 'gate2.ipweb.cc'
port = 7778
user = 'B_72756_JP___90_pphKvB9y'
pwd = '2442375'

def test_socks5():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(15)
    print(f'TCP connecting to {host}:{port}...')
    s.connect((host, port))
    print('TCP connected')
    
    # SOCKS5 greeting: version=5, 2 methods: no-auth(0x00) + user-pass(0x02)
    s.send(b'\x05\x02\x00\x02')
    resp = s.recv(1024)
    print('Greeting response:', resp.hex(), 'len=', len(resp))
    
    if len(resp) < 2:
        print('Empty response from proxy')
        s.close()
        return False
    
    auth_method = resp[1]
    print('Selected auth method:', hex(auth_method))
    
    if auth_method == 0x00:
        print('No auth needed')
    elif auth_method == 0x02:
        print('Username/password auth required')
        auth_msg = b'\x01'
        auth_msg += bytes([len(user)]) + user.encode()
        auth_msg += bytes([len(pwd)]) + pwd.encode()
        s.send(auth_msg)
        auth_resp = s.recv(1024)
        print('Auth response:', auth_resp.hex())
        if len(auth_resp) < 2 or auth_resp[1] != 0x00:
            print('Auth FAILED')
            s.close()
            return False
        print('Auth OK')
    elif auth_method == 0xFF:
        print('No acceptable auth methods')
        s.close()
        return False
    else:
        print('Unknown auth method:', hex(auth_method))
    
    # Send CONNECT request to api.ipify.org:443
    target_host = 'api.ipify.org'
    target_port = 443
    connect_req = b'\x05\x01\x00\x03'  # VER=5, CMD=CONNECT, RSV=0, ATYP=DOMAINNAME
    connect_req += bytes([len(target_host)]) + target_host.encode()
    connect_req += struct.pack('>H', target_port)
    s.send(connect_req)
    
    connect_resp = s.recv(1024)
    print('Connect response:', connect_resp.hex(), 'len=', len(connect_resp))
    
    if len(connect_resp) >= 2:
        status = connect_resp[1]
        status_map = {0x00: 'SUCCESS', 0x01: 'GENERAL_FAILURE', 0x02: 'NOT_ALLOWED',
                      0x03: 'NET_UNREACHABLE', 0x04: 'HOST_UNREACHABLE', 0x05: 'CONN_REFUSED',
                      0x06: 'TTL_EXPIRED', 0x07: 'CMD_NOT_SUPPORTED', 0x08: 'ADDR_NOT_SUPPORTED'}
        status_name = status_map.get(status, f'UNKNOWN({hex(status)})')
        print('Status:', status_name)
        
        if status == 0x00:
            print('=== PROXY WORKS! ===')
            # Try to do an HTTP request through the tunnel
            import ssl
            context = ssl.create_default_context()
            ssock = context.wrap_socket(s, server_hostname=target_host)
            http_req = f'GET /?format=json HTTP/1.1\r\nHost: {target_host}\r\nConnection: close\r\n\r\n'
            ssock.send(http_req.encode())
            http_resp = b''
            while True:
                chunk = ssock.recv(4096)
                if not chunk:
                    break
                http_resp += chunk
            print('HTTP response:', http_resp.decode()[-200:])
            ssock.close()
            return True
    
    s.close()
    return False

# Also try plain HTTP proxy (CONNECT method)
def test_http_connect():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(15)
    print(f'\n--- HTTP CONNECT proxy test ---')
    print(f'TCP connecting to {host}:{port}...')
    s.connect((host, port))
    print('TCP connected')
    
    import base64
    cred = base64.b64encode(f'{user}:{pwd}'.encode()).decode()
    connect_req = f'CONNECT api.ipify.org:443 HTTP/1.1\r\nHost: api.ipify.org:443\r\nProxy-Authorization: Basic {cred}\r\n\r\n'
    s.send(connect_req.encode())
    
    resp = s.recv(4096)
    print('HTTP CONNECT response:', resp.decode()[:200])
    if b'200' in resp:
        print('=== HTTP CONNECT PROXY WORKS! ===')
        s.close()
        return True
    s.close()
    return False

if __name__ == '__main__':
    print('=== SOCKS5 Test ===')
    try:
        ok = test_socks5()
        if ok:
            print('\nUse socks5 protocol')
    except Exception as e:
        print(f'SOCKS5 test error: {e}')
    
    try:
        ok = test_http_connect()
        if ok:
            print('\nUse HTTP CONNECT protocol')
    except Exception as e:
        print(f'HTTP CONNECT test error: {e}')
