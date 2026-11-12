# Bug bounty recon pipeline

PRD Phase 4. Deployed to the edge (single-server plan, ADR-009) by
`infra/ansible/roles/recon`, as two systemd units running on a dedicated
`recon` system user:

- **`scout.timer`** → `scout.py`, once a day. Pulls HackerOne's public program
  list ([arkadiyt/bounty-targets-data](https://github.com/arkadiyt/bounty-targets-data)),
  runs the deterministic shortlist filter (`filters.py`), and pings Telegram
  with an Approve/Reject tap for each new qualifying program. At most
  `SCOUT_MAX_PINGS` (default 10) go out per run — the first run against the
  live catalog queues ~190 candidates; pinging all of them at once would flood
  you, not inform you, so the rest drain a few at a time on later runs.
- **`approval-bridge.service`** → `approval_bridge.py`, always running. Long-polls
  Telegram for your tap. **Approve** writes `scope/<handle>.json` from that
  program's own scope data and marks it `approved`; **Reject** marks it
  `rejected`. Nothing else ever changes a program's status.

State lives in `recon.db` (SQLite, schema in `schema.sql`).

## Why the design looks like this

`docs/STATUS.md` and `PRD.md` both say "agents never pick targets" / "scope
file is required per program" — a guardrail from earlier in this project.
This pipeline keeps that true: the scout only *proposes*, and nothing is
in scope until you tap Approve. That tap is deliberately the only gate, and
it's deliberately manual — see ADR-013 (`docs/DECISIONS.md`).

**There is no automated policy check before the ping.** HackerOne program
pages (`hackerone.com/<handle>`) are a JS single-page app — a plain HTTP GET
returns a ~3.5 KB shell with no policy text, so a headless `curl`-style fetch
can't read the actual rules (and a headless browser is more weight than this
free-tier box should carry for something your own judgment does better
anyway). So the Telegram ping gives you the link and the structured scope
data, and says plainly: **reading the policy before you tap is the scope
check.** A richer automated signal is possible later via HackerOne's official
read-only MCP server (authenticated, sees real policy data) — worth adding
in Phase B, not worth faking with regexes against a page that doesn't carry
the text to begin with.

## What's NOT built yet (Phase B)

- The recon worker itself: passive (subfinder/httpx) then active (nuclei,
  non-destructive templates only) scanning, strictly intersected against the
  approved scope file, one target at a time, research-header injection,
  global rate limit, kill switch.
- Triage: dedup against existing reports via HackerOne's official MCP server,
  draft report generation.
- The second Telegram ping (a credible finding, ready for your review) and
  report submission (manual at first — see the main chat for the fuller
  design discussion).

## Local development

```
python -m unittest discover -s recon -v   # no network, no Telegram needed
```

`common.py` reads `TELEGRAM_ENV` (default `/etc/oci-homelab/telegram.env`) and
`RECON_DB` (default `/opt/oci-homelab/recon/recon.db`) from the environment —
override both for a manual dry run against the real dataset without touching
the deployed DB or sending real Telegram messages (monkeypatch
`common.send_message` for the latter, as `test_scout.py` does).

## Secrets

None required for this stage beyond the Telegram bot already used by
Alertmanager (`/etc/oci-homelab/telegram.env`, manually placed — see
`docs/RUNBOOK.md`). Ansible copies a recon-owned copy to
`/etc/oci-homelab/secrets/recon-telegram.env` (mode 0600, owner `recon`), same
pattern as `roles/monitoring`. The HackerOne API token (needed once Phase B
does dedup/triage via the official MCP server) is not wired up yet.
