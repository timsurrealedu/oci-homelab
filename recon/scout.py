#!/usr/bin/env python3
"""Stage 1 program discovery. Run by scout.timer (systemd), once a day.

Pulls HackerOne's public program list (arkadiyt/bounty-targets-data), keeps
only structurally promising programs (filters.py), and queues each new one as
a 'candidate'. A second pass drains up to MAX_PINGS_PER_RUN of that queue to
Telegram per run (oldest-discovered first) -- the whole catalog qualifies
~190 programs today, and pinging all of them the first time this ever runs
would flood you, not inform you. Steady state (a handful of new programs a
day) drains in one run.

This script never scans anything and never decides a program is in scope by
itself: approval_bridge.py only writes a scope file, and only once you tap
Approve -- which is also the moment you actually read that program's policy
page (linked in the ping, since it can't be fetched headlessly: see
recon/README.md). That keeps "agents never pick targets" true: the agent
proposes, you still pick.
"""
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import filters

DATA_URL = "https://raw.githubusercontent.com/arkadiyt/bounty-targets-data/main/data/hackerone_data.json"
MAX_PINGS_PER_RUN = int(os.environ.get("SCOUT_MAX_PINGS", "10"))


def fetch_programs() -> list[dict]:
    req = urllib.request.Request(DATA_URL, headers={"User-Agent": "oci-homelab-recon-scout/0.1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def already_seen(conn, handle: str) -> bool:
    return conn.execute("SELECT 1 FROM programs WHERE handle = ?", (handle,)).fetchone() is not None


def scope_summary_text(broad: list[dict]) -> str:
    severities = sorted({a.get("max_severity") for a in broad if a.get("max_severity")})
    return f"{len(broad)} bounty-eligible wildcard/URL asset(s); max severity seen: {', '.join(severities) or 'n/a'}"


def record_skip(conn, program: dict, reasons: list[str]) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO programs (handle, name, url, status, discovered_at) "
        "VALUES (?, ?, ?, 'skipped', ?)",
        (program.get("handle"), program.get("name"), program.get("url"), time.time()),
    )
    conn.commit()
    print(f"scout: skip {program.get('handle')}: {', '.join(reasons)}")


def enqueue_candidate(conn, program: dict) -> None:
    conn.execute(
        "INSERT INTO programs (handle, name, url, status, response_efficiency, scope_json, discovered_at, pinged) "
        "VALUES (?, ?, ?, 'candidate', ?, ?, ?, 0)",
        (program["handle"], program["name"], program["url"], program.get("response_efficiency_percentage"),
         json.dumps(program.get("targets", {})), time.time()),
    )
    conn.commit()
    print(f"scout: queued {program['handle']}")


def send_ping(conn, row) -> None:
    handle = row["handle"]
    scope = json.loads(row["scope_json"] or "{}")
    broad = filters.broad_scope_assets({"targets": scope})
    text = (
        f"\U0001F7E2 New candidate program: <b>{row['name']}</b>\n"
        f"{row['url']}\n"
        f"Scope: {scope_summary_text(broad)}\n"
        f"Response efficiency: {row['response_efficiency'] if row['response_efficiency'] is not None else 'n/a'}%\n\n"
        f"Read the policy at the link above before approving — this tap is the "
        f"only scope/policy check this program gets. Approving writes a scope file "
        f"from the scope data above and lets the recon worker start on it."
    )
    resp = common.send_message(text, buttons=[("✅ Approve", f"appr:{handle}"), ("❌ Reject", f"rej:{handle}")])
    msg_id = resp.get("result", {}).get("message_id")
    conn.execute("UPDATE programs SET pinged = 1 WHERE handle = ?", (handle,))
    conn.execute(
        "INSERT INTO approvals (program_handle, telegram_message_id, action, created_at) VALUES (?, ?, 'pinged', ?)",
        (handle, msg_id, time.time()),
    )
    conn.commit()
    print(f"scout: pinged {handle} (message {msg_id})")


def drain_ping_queue(conn, limit: int = MAX_PINGS_PER_RUN) -> int:
    rows = conn.execute(
        "SELECT handle, name, url, response_efficiency, scope_json FROM programs "
        "WHERE status = 'candidate' AND pinged = 0 ORDER BY discovered_at ASC LIMIT ?",
        (limit,),
    ).fetchall()
    for row in rows:
        send_ping(conn, row)
    return len(rows)


def run(programs: list[dict], conn, ping_limit: int = MAX_PINGS_PER_RUN) -> tuple[int, int, int]:
    """Pure-ish core (DB + Telegram are the only side effects) so tests can drive
    it with a fixture list and a temp DB without touching the network twice."""
    checked = queued = 0
    for program in programs:
        handle = program.get("handle")
        if not handle or already_seen(conn, handle):
            continue
        ok, reasons = filters.passes_structural_filter(program)
        if not ok:
            record_skip(conn, program, reasons)
            continue
        checked += 1
        enqueue_candidate(conn, program)
        queued += 1
    pinged = drain_ping_queue(conn, ping_limit)
    return len(programs), checked, pinged


def main() -> None:
    conn = common.db()
    seen, checked, pinged = run(fetch_programs(), conn)
    backlog = conn.execute("SELECT COUNT(*) AS n FROM programs WHERE status = 'candidate' AND pinged = 0").fetchone()["n"]
    print(f"scout: {seen} programs seen, {checked} passed stage 1, {pinged} pinged, {backlog} still queued")


if __name__ == "__main__":
    main()
