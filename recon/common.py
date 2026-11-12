"""Shared helpers for the recon pipeline: config, SQLite, Telegram. Stdlib only
(same rule as apps/trading, apps/trace: no pip deps to keep the image/host footprint tiny).
"""
import json
import os
import sqlite3
import urllib.parse
import urllib.request

DB_PATH = os.environ.get("RECON_DB", "/opt/oci-homelab/recon/recon.db")
SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    with open(SCHEMA_PATH) as f:
        conn.executescript(f.read())
    return conn


def kv_get(conn: sqlite3.Connection, key: str, default=None):
    row = conn.execute("SELECT value FROM kv WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def kv_set(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO kv (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()


def _env_file(path: str) -> dict:
    out = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def telegram_env() -> dict:
    # Ansible writes a recon-owned copy of the shared secret to
    # /etc/oci-homelab/secrets/recon-telegram.env (see roles/recon). Local/manual
    # runs can point TELEGRAM_ENV at the shared /etc/oci-homelab/telegram.env instead.
    return _env_file(os.environ.get("TELEGRAM_ENV", "/etc/oci-homelab/telegram.env"))


def _tg_call(method: str, payload: dict) -> dict:
    token = telegram_env()["TELEGRAM_BOT_TOKEN"]
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def send_message(text: str, buttons: list[tuple[str, str]] | None = None, chat_id: str | None = None) -> dict:
    """buttons: [(label, callback_data), ...], each rendered as its own row."""
    chat_id = chat_id or telegram_env()["TELEGRAM_CHAT_ID"]
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    if buttons:
        payload["reply_markup"] = {"inline_keyboard": [[{"text": label, "callback_data": cb}] for label, cb in buttons]}
    return _tg_call("sendMessage", payload)


def answer_callback(callback_query_id: str, text: str | None = None) -> dict:
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    return _tg_call("answerCallbackQuery", payload)


def get_updates(offset: int, timeout: int = 30) -> list:
    token = telegram_env()["TELEGRAM_BOT_TOKEN"]
    qs = urllib.parse.urlencode({
        "offset": offset,
        "timeout": timeout,
        "allowed_updates": json.dumps(["callback_query"]),
    })
    url = f"https://api.telegram.org/bot{token}/getUpdates?{qs}"
    with urllib.request.urlopen(url, timeout=timeout + 10) as r:
        return json.load(r)["result"]
