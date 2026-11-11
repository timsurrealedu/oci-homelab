"""Looking glass: ping, mtr and DNS lookups from Oracle Cloud ap-batam-1, for public targets only.

Stdlib only. Runs behind Caddy, which serves the page (public/) and sets X-Forwarded-For to the real client address.
Guardrails: targets must be a hostname or IP that resolves only to global addresses (no private,
loopback, link-local, CGNAT/Tailscale or metadata ranges); tools get the resolved IP, never user
text, so no flags or DNS rebinding; fixed tool arguments; per-client rate limit; global
concurrency cap; timeouts; output size cap.
"""
import ipaddress
import json
import os
import re
import socket
import subprocess
import threading
import time
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HOSTNAME = re.compile(r"^(?=.{1,253}$)(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*\.?$")
DNS_TYPES = {"A", "AAAA", "CAA", "CNAME", "MX", "NS", "SOA", "TXT"}
RATE_PER_MIN = int(os.environ.get("LG_RATE_PER_MIN", "6"))
TIMEOUT_S = 30
MAX_OUTPUT = 20_000

_busy = threading.BoundedSemaphore(int(os.environ.get("LG_CONCURRENCY", "2")))
_hits: dict[str, deque] = defaultdict(deque)
_hits_lock = threading.Lock()


class Rejected(ValueError):
    pass


def resolve_public(target: str) -> str:
    """Return a global IP for an IP literal or hostname; reject anything that isn't public."""
    try:
        ips = [ipaddress.ip_address(target)]
    except ValueError:
        if not HOSTNAME.match(target):
            raise Rejected("enter a hostname or an IP address") from None
        try:
            infos = socket.getaddrinfo(target, None, proto=socket.IPPROTO_TCP)
        except (socket.gaierror, UnicodeError):
            raise Rejected("that name does not resolve") from None
        ips = [ipaddress.ip_address(i[4][0]) for i in infos]
    if not ips or not all(ip.is_global and not ip.is_multicast for ip in ips):
        raise Rejected("only public addresses are allowed")
    # IPv4 only: the server has no IPv6 route, and v6 forms like NAT64 (64:ff9b::/96) can wrap private v4.
    v4 = [ip for ip in ips if ip.version == 4]
    if not v4:
        raise Rejected("only IPv4 targets are supported")
    return str(v4[0])


def build_command(tool: str, target: str, rtype: str = "A") -> list[str]:
    target = target.strip()
    if tool == "dns":
        if not HOSTNAME.match(target):
            raise Rejected("enter a hostname")
        if rtype not in DNS_TYPES:
            raise Rejected(f"record type must be one of {', '.join(sorted(DNS_TYPES))}")
        # A public resolver, so names inside Oracle's VCN DNS can't be looked up.
        return ["dig", "@1.1.1.1", "+time=2", "+tries=1", "+noall", "+answer", target, rtype]
    if tool == "ping":
        return ["ping", "-c", "4", "-W", "2", resolve_public(target)]
    if tool == "mtr":
        return ["mtr", "-r", "-n", "-c", "5", resolve_public(target)]
    raise Rejected("tool must be ping, mtr or dns")


def allow(client: str) -> bool:
    now = time.monotonic()
    with _hits_lock:
        if len(_hits) > 10_000:  # honey: crude memory bound; fine at demo traffic, use a TTL cache if it grows
            _hits.clear()
        q = _hits[client]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= RATE_PER_MIN:
            return False
        q.append(now)
        return True


class Handler(BaseHTTPRequestHandler):
    server_version = "lg"
    sys_version = ""

    def client(self) -> str:
        return self.headers.get("X-Forwarded-For", self.client_address[0]).split(",")[0].strip()

    def address_string(self) -> str:  # access log shows the real client
        return self.client()

    def send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def json(self, code: int, data: dict) -> None:
        self.send(code, json.dumps(data).encode(), "application/json")

    def do_GET(self) -> None:
        url = urlparse(self.path)
        if url.path == "/healthz":
            return self.send(200, b"ok", "text/plain")
        if url.path != "/api/run":
            return self.send(404, b"not found", "text/plain")

        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        if not allow(self.client()):
            return self.json(429, {"error": f"limit is {RATE_PER_MIN} lookups per minute, try again shortly"})
        if not _busy.acquire(blocking=False):
            return self.json(503, {"error": "busy with other lookups, try again in a few seconds"})
        try:
            cmd = build_command(q.get("tool", ""), q.get("target", "")[:253], q.get("type", "A").upper())
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT_S, errors="replace")
            self.json(200, {"command": " ".join(cmd), "output": (p.stdout + p.stderr)[:MAX_OUTPUT]})
        except Rejected as e:
            self.json(400, {"error": str(e)})
        except subprocess.TimeoutExpired:
            self.json(504, {"error": "timed out"})
        finally:
            _busy.release()


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8090"))), Handler).serve_forever()
