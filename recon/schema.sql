-- recon pipeline state. SQLite; created on demand by common.db(). Phase A only
-- (programs/approvals/kv); scan_runs/findings/reports land in Phase B, once the
-- recon worker and report-triage steps exist (see recon/README.md).

CREATE TABLE IF NOT EXISTS programs (
    handle              TEXT PRIMARY KEY,       -- hackerone program slug
    name                TEXT,
    url                 TEXT,
    platform            TEXT NOT NULL DEFAULT 'hackerone',
    status              TEXT NOT NULL DEFAULT 'candidate',  -- candidate|approved|rejected|skipped
    response_efficiency INTEGER,
    scope_json          TEXT,                   -- targets.{in_scope,out_of_scope}, captured at discovery time
    pinged              INTEGER NOT NULL DEFAULT 0,  -- 0 = queued, not yet sent to Telegram (see MAX_PINGS_PER_RUN)
    discovered_at       REAL NOT NULL,
    decided_at          REAL,
    decided_by          TEXT                    -- telegram username/id who tapped approve/reject
);

CREATE TABLE IF NOT EXISTS approvals (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    program_handle      TEXT NOT NULL REFERENCES programs(handle),
    telegram_message_id INTEGER,
    action              TEXT NOT NULL,          -- pinged|appr|rej
    created_at          REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS kv (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
