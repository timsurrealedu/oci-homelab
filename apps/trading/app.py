"""Read-only paper-trading dashboard for the freqtrade bot.

The browser never talks to freqtrade (Caddy serves the page from public/). This server logs in to freqtrade's API (http://freqtrade:8080 on freqtrade's Docker network) with
credentials from a root-only env file, fetches a few read-only endpoints, keeps only whitelisted
fields, caches the result for a minute and serves it as /api/summary. It refuses to show anything
if the bot is not in dry-run mode (live money is out of scope).
"""
import base64
import json
import os
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

FT_URL = os.environ.get("FT_URL", "http://127.0.0.1:8080").rstrip("/")
CACHE_S = 60

_cache: dict = {"at": 0.0, "body": None}
_cache_lock = threading.Lock()


class NotPaper(RuntimeError):
    pass


def ft_get(path: str):
    token = base64.b64encode(f"{os.environ['FT_USER']}:{os.environ['FT_PASS']}".encode()).decode()
    req = urllib.request.Request(f"{FT_URL}/api/v1/{path}", headers={"Authorization": f"Basic {token}"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)


def fetch_all_trades() -> list[dict]:
    trades, offset = [], 0
    while True:
        page = ft_get(f"trades?limit=500&offset={offset}")
        trades += page["trades"]
        offset += len(page["trades"])
        if not page["trades"] or offset >= page["total_trades"]:
            return trades


def round_or_none(x, n=2):
    return None if x is None else round(x, n)


def build_summary(config: dict, profit: dict, balance: dict, open_trades: list, trades: list) -> dict:
    """Pure function: freqtrade API responses in, public whitelisted summary out."""
    if config.get("dry_run") is not True:
        raise NotPaper("bot is not in dry-run mode")

    closed = sorted((t for t in trades if not t.get("is_open")), key=lambda t: t["close_timestamp"])
    # Start the curve at the wallet's real opening value so it ends exactly at the current balance
    # (freqtrade's "starting_capital" excludes its 1% reserve).
    total = balance.get("total")
    start = total - sum(t.get("profit_abs") or 0.0 for t in closed) if total is not None else balance.get("starting_capital") or 0.0
    equity, value, peak, max_dd = [], start, start, 0.0
    if closed:
        equity.append([closed[0]["open_timestamp"], round(start, 2)])
    for t in closed:
        value += t.get("profit_abs") or 0.0
        peak = max(peak, value)
        max_dd = max(max_dd, (peak - value) / peak if peak else 0.0)
        equity.append([t["close_timestamp"], round(value, 2)])

    return {
        "generated_at": int(time.time() * 1000),
        "bot": {k: config.get(k) for k in ("strategy", "timeframe", "exchange", "trading_mode",
                                           "max_open_trades", "stoploss", "state")},
        "summary": {
            "stake_currency": config.get("stake_currency"),
            "starting_capital": round(start, 2),
            "balance": round_or_none(balance.get("total")),
            "return_pct": round_or_none(balance.get("starting_capital_pct")),
            "closed_trades": profit.get("closed_trade_count"),
            "winrate_pct": round_or_none((profit.get("winrate") or 0) * 100, 1),
            "profit_factor": round_or_none(profit.get("profit_factor")),
            "max_drawdown_pct": round(max_dd * 100, 1),
            "best_pair": profit.get("best_pair"),
            "avg_duration": profit.get("avg_duration"),
            "first_trade": profit.get("first_trade_timestamp"),
            "latest_trade": profit.get("latest_trade_timestamp"),
        },
        "equity": equity,
        "open": [{"pair": t["pair"], "opened": t["open_timestamp"],
                  "profit_pct": round_or_none(t.get("profit_pct"))} for t in open_trades],
        "recent": [{"pair": t["pair"], "opened": t["open_timestamp"], "closed": t["close_timestamp"],
                    "profit_pct": round_or_none(t.get("profit_pct")), "profit_abs": round_or_none(t.get("profit_abs")),
                    "exit": t.get("exit_reason")} for t in reversed(closed[-25:])],
    }


def summary_json() -> bytes:
    with _cache_lock:  # one upstream fetch at a time; everyone else gets the cached copy
        if _cache["body"] is None or time.monotonic() - _cache["at"] > CACHE_S:
            body = build_summary(ft_get("show_config"), ft_get("profit"), ft_get("balance"),
                                 ft_get("status"), fetch_all_trades())
            _cache.update(at=time.monotonic(), body=json.dumps(body).encode())
        return _cache["body"]


class Handler(BaseHTTPRequestHandler):
    server_version = "trading"
    sys_version = ""

    def address_string(self) -> str:
        return self.headers.get("X-Forwarded-For", self.client_address[0]).split(",")[0].strip()

    def send(self, code: int, body: bytes, ctype: str, cache: str = "no-store") -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/healthz":
            return self.send(200, b"ok", "text/plain")
        if self.path != "/api/summary":
            return self.send(404, b"not found", "text/plain")
        try:
            self.send(200, summary_json(), "application/json", f"public, max-age={CACHE_S}")
        except NotPaper as e:
            self.send(503, json.dumps({"error": str(e)}).encode(), "application/json")
        except Exception as e:  # upstream down or changed; don't leak details
            self.log_error("upstream error: %r", e)
            self.send(502, b'{"error": "trading bot unavailable"}', "application/json")


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8092"))), Handler).serve_forever()
