#!/usr/bin/env python3
"""Long-running daemon (approval-bridge.service): polls Telegram for your
Approve/Reject taps on candidate programs. This is the only place that ever
flips a program to 'approved'. On approve it writes recon/scope/<handle>.json
from that program's own in-scope data captured at discovery time; the (not yet
written -- Phase B) recon worker is meant to act only within that file.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

SCOPE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scope")


def write_scope_file(conn, handle: str) -> str:
    row = conn.execute("SELECT scope_json FROM programs WHERE handle = ?", (handle,)).fetchone()
    scope = json.loads(row["scope_json"]) if row and row["scope_json"] else {"in_scope": [], "out_of_scope": []}
    os.makedirs(SCOPE_DIR, exist_ok=True)
    path = os.path.join(SCOPE_DIR, f"{handle}.json")
    with open(path, "w") as f:
        json.dump({"handle": handle, "approved_at": time.time(), "targets": scope}, f, indent=2)
    return path


def handle_callback(conn, cb: dict) -> None:
    data = cb.get("data", "")  # "appr:<handle>" or "rej:<handle>"
    action, _, handle = data.partition(":")
    from_user = cb.get("from", {}).get("username") or cb.get("from", {}).get("id")

    if action == "appr":
        write_scope_file(conn, handle)
        conn.execute(
            "UPDATE programs SET status = 'approved', decided_at = ?, decided_by = ? WHERE handle = ?",
            (time.time(), str(from_user), handle),
        )
        reply = "✅ Approved. Scope file written."
    elif action == "rej":
        conn.execute(
            "UPDATE programs SET status = 'rejected', decided_at = ?, decided_by = ? WHERE handle = ?",
            (time.time(), str(from_user), handle),
        )
        reply = "❌ Rejected."
    else:
        reply = None

    conn.commit()
    common.answer_callback(cb["id"], reply)
    if reply:
        conn.execute(
            "INSERT INTO approvals (program_handle, action, created_at) VALUES (?, ?, ?)",
            (handle, action, time.time()),
        )
        conn.commit()


def main() -> None:
    conn = common.db()
    offset = int(common.kv_get(conn, "bridge_offset", "0"))
    while True:
        try:
            updates = common.get_updates(offset, timeout=30)
        except Exception as e:
            print(f"approval_bridge: getUpdates failed: {e}", file=sys.stderr)
            time.sleep(5)
            continue
        for u in updates:
            offset = u["update_id"] + 1
            cb = u.get("callback_query")
            if cb:
                try:
                    handle_callback(conn, cb)
                except Exception as e:
                    print(f"approval_bridge: error handling callback {cb.get('data')}: {e}", file=sys.stderr)
            common.kv_set(conn, "bridge_offset", str(offset))


if __name__ == "__main__":
    main()
