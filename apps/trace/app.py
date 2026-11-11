"""Trace your request (API; Caddy serves the page from public/): shows the path a visitor's request takes into the platform, with real timings.

Hops measured per request:
  browser -> edge      : the browser measures it (fetch timing minus the server's Server-Timing total)
  Caddy -> this app    : Caddy stamps X-Trace-Caddy-In (unix ms) when it forwards; we compare on arrival
Paths measured from the edge (fixed targets, refreshed every 30 s in the background, so visitors can't multiply the traffic):
  edge -> internet via the Internet Gateway, and edge -> worker over the private subnet.
Nothing here takes a target from the visitor.
"""
import json
import os
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

PROBE_CACHE_S = 30

# (id, label, host, port, explanation)
PROBES = [
    ("internet", "Edge to the internet", "1.1.1.1", 443,
     "Out of the public subnet through Oracle's Internet Gateway (route 0.0.0.0/0 -> IGW). TCP handshake to Cloudflare."),
    ("github", "Edge to GitHub", "github.com", 443,
     "Same path, plus a DNS lookup through the VCN resolver. Shows the distance from Batam to a big cloud region."),
    ("worker", "Edge to the private worker", "10.0.1.10", 22,
     "Across the VCN into the private subnet. nsg-worker only accepts traffic from members of nsg-edge."),
]

_probe_state: dict = {"results": [], "measured": 0}


def tcp_connect_ms(host: str, port: int, timeout: float = 1.5) -> float:
    t0 = time.perf_counter()
    with socket.create_connection((host, port), timeout=timeout):
        return round((time.perf_counter() - t0) * 1000, 1)


def run_probes(connect=tcp_connect_ms) -> list[dict]:
    out = []
    for pid, label, host, port, why in PROBES:
        try:
            out.append({"id": pid, "label": label, "target": f"{host}:{port}", "ok": True, "ms": connect(host, port), "why": why})
        except OSError as e:
            note = "no answer: the worker hasn't launched yet (Oracle has no free ARM capacity in Batam)" \
                if pid == "worker" else f"failed: {type(e).__name__}"
            out.append({"id": pid, "label": label, "target": f"{host}:{port}", "ok": False, "ms": None, "why": why, "note": note})
    return out


def refresh_probes_forever() -> None:
    """Background loop: requests read the latest results and never wait on a slow or failing probe."""
    while True:
        _probe_state.update(results=run_probes(), measured=int(time.time() * 1000))
        time.sleep(PROBE_CACHE_S)


def cached_probes() -> tuple[list[dict], int]:
    return _probe_state["results"], _probe_state["measured"]


def classify_entry(headers) -> str:
    """How the request reached the edge. Tailscale Serve adds Tailscale-User-* headers for tailnet users."""
    if headers.get("Tailscale-User-Login") or headers.get("Tailscale-Headers-Info"):
        return "tailscale"
    return "internet"


def caddy_hop_ms(caddy_in: str | None, arrived_ms: float) -> float | None:
    try:
        return max(0.0, round(arrived_ms - int(caddy_in), 1))
    except (TypeError, ValueError):
        return None


class Handler(BaseHTTPRequestHandler):
    server_version = "trace"
    sys_version = ""

    def address_string(self) -> str:
        return self.headers.get("X-Forwarded-For", self.client_address[0]).split(",")[0].strip()

    def send(self, code: int, body: bytes, ctype: str, extra: dict | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        arrived_ms = time.time() * 1000
        t0 = time.perf_counter()
        path = urlparse(self.path).path  # the page adds ?t=<now> so each trace is a fresh timing entry
        if path == "/healthz":
            return self.send(200, b"ok", "text/plain")
        if path != "/api/trace":
            return self.send(404, b"not found", "text/plain")

        probes, measured = cached_probes()
        caddy_ms = caddy_hop_ms(self.headers.get("X-Trace-Caddy-In"), arrived_ms)
        app_ms = round((time.perf_counter() - t0) * 1000, 1)
        body = {
            "entry": classify_entry(self.headers),
            "client": self.address_string() if classify_entry(self.headers) == "internet" else None,
            "caddy_to_app_ms": caddy_ms,
            "app_ms": app_ms,
            "probes": probes,
            "probes_measured_at": measured,
            "server_time": int(arrived_ms),
        }
        timing = f"app;dur={app_ms};desc=\"trace app\""
        if caddy_ms is not None:
            timing = f"proxy;dur={caddy_ms};desc=\"Caddy to app\", " + timing
        self.send(200, json.dumps(body).encode(), "application/json", {"Server-Timing": timing})


if __name__ == "__main__":
    _probe_state.update(results=run_probes(), measured=int(time.time() * 1000))
    threading.Thread(target=refresh_probes_forever, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8094"))), Handler).serve_forever()
