"""
Local HTTP CONNECT proxy relay.
Listens on 127.0.0.1:PORT, forwards to upstream proxy with auth.
Chrome connects to localhost (no auth needed), this relay handles upstream auth.
"""
import socket
import threading
import sys
import base64
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("proxy_relay")

UPSTREAM_HOST = "gate2.ipweb.cc"
UPSTREAM_PORT = 7778
UPSTREAM_USER = "B_72756_JP___90_pphKvB9y"
UPSTREAM_PASS = "2442375"
LOCAL_PORT = 17890


def handle_client(client_sock):
    """Handle one CONNECT request."""
    try:
        # Read the CONNECT request
        request = b""
        while b"\r\n\r\n" not in request:
            chunk = client_sock.recv(4096)
            if not chunk:
                return
            request += chunk

        first_line = request.split(b"\r\n")[0].decode("utf-8", errors="replace")
        logger.info("Request: %s", first_line[:80])

        if not first_line.upper().startswith("CONNECT"):
            # HTTP request (not CONNECT) — forward directly
            _relay_http(client_sock, request)
            return

        # CONNECT method — parse target
        parts = first_line.split()
        if len(parts) < 2:
            client_sock.close()
            return
        target = parts[1]  # host:port
        host, _, port = target.rpartition(":")
        port = int(port) if port else 443

        # Connect to upstream proxy
        upstream = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        upstream.settimeout(15)
        try:
            upstream.connect((UPSTREAM_HOST, UPSTREAM_PORT))
        except Exception as e:
            logger.error("Upstream connect failed: %s", e)
            client_sock.sendall(b"HTTP/502 Connection failed\r\n\r\n")
            client_sock.close()
            return

        # Send CONNECT to upstream with auth
        auth = base64.b64encode(f"{UPSTREAM_USER}:{UPSTREAM_PASS}".encode()).decode()
        connect_req = (
            f"CONNECT {target} HTTP/1.1\r\n"
            f"Host: {target}\r\n"
            f"Proxy-Authorization: Basic {auth}\r\n"
            f"\r\n"
        )
        upstream.sendall(connect_req.encode())

        # Read upstream response
        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = upstream.recv(4096)
            if not chunk:
                break
            resp += chunk

        resp_line = resp.split(b"\r\n")[0].decode("utf-8", errors="replace")
        logger.info("Upstream: %s", resp_line[:80])

        if b"200" in resp.split(b"\r\n")[0]:
            # Success — tell client the tunnel is established
            client_sock.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            # Bidirectional relay
            _relay(client_sock, upstream)
        else:
            # Failed — forward the error
            client_sock.sendall(resp)
            client_sock.close()
            upstream.close()

    except Exception as e:
        logger.error("Handler error: %s", e)
        try:
            client_sock.close()
        except Exception:
            pass


def _relay_http(client_sock, initial_request):
    """Relay a plain HTTP request through the upstream proxy."""
    upstream = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    upstream.settimeout(15)
    try:
        upstream.connect((UPSTREAM_HOST, UPSTREAM_PORT))
        auth = base64.b64encode(f"{UPSTREAM_USER}:{UPSTREAM_PASS}".encode()).decode()
        # Add proxy auth header
        modified = initial_request.replace(b"\r\n", f"\r\nProxy-Authorization: Basic {auth}\r\n".encode(), 1)
        upstream.sendall(modified)
        while True:
            data = upstream.recv(8192)
            if not data:
                break
            client_sock.sendall(data)
    except Exception:
        pass
    finally:
        try:
            client_sock.close()
        except Exception:
            pass
        try:
            upstream.close()
        except Exception:
            pass


def _relay(sock1, sock2):
    """Bidirectional relay between two sockets."""
    def _forward(src, dst):
        try:
            while True:
                data = src.recv(65536)
                if not data:
                    break
                dst.sendall(data)
        except Exception:
            pass
        try:
            src.close()
        except Exception:
            pass
        try:
            dst.close()
        except Exception:
            pass

    t1 = threading.Thread(target=_forward, args=(sock1, sock2), daemon=True)
    t2 = threading.Thread(target=_forward, args=(sock2, sock1), daemon=True)
    t1.start()
    t2.start()
    t1.join()
    t2.join()


def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", LOCAL_PORT))
    server.listen(20)
    logger.info("Proxy relay listening on 127.0.0.1:%d -> %s:%d", LOCAL_PORT, UPSTREAM_HOST, UPSTREAM_PORT)
    try:
        while True:
            client, addr = server.accept()
            threading.Thread(target=handle_client, args=(client,), daemon=True).start()
    except KeyboardInterrupt:
        logger.info("Shutting down")
    finally:
        server.close()


if __name__ == "__main__":
    main()
