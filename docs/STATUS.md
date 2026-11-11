# Status and handoff

Where the project stands, what is running, and what to do next. **Update this file at the end of every work session.** Last updated 2026-11-11.

## The goal

Turn Tim's single Oracle Cloud Always Free server (ap-batam-1) into a small, documented, $0 platform:
**since 2026-11-11 built on one server (the edge)**, with a private worker VM added automatically if Oracle frees capacity (ADR-009). Built with Terraform and Ansible, with monitoring, a deploy platform,
a bug bounty recon pipeline, a few public demos, and a portfolio-quality repo. Full goals, non-goals and phases: [`PRD.md`](../PRD.md).
Safety rules (cost $0, never terminate without a backup and Tim's yes, no admin UI on public ports, secrets never committed): the `oci-homelab` skill in `.claude/skills/`.

## Phase progress

| Phase | State | Notes |
|---|---|---|
| 0 Audit and safety net | ✅ done | Inventory in `docs/inventory-2026-11.md`. Old pm2 apps (lifeOS, noema...) decommissioned at Tim's request. Boot volume backup taken. |
| 1 IaC foundation | ✅ done | Terraform (`infra/terraform/`) imports the VCN, gateways, subnets and edge; adds NSGs. Edge shrunk in place to 1 OCPU / 6 GB. Worker declared but waiting on A1 capacity; **plan is now single-server** (ADR-009). |
| 2 Server baseline | ✅ done on the edge | Ansible (`infra/ansible/`, run *from the edge*). Worker gets the same baseline once it exists. Tailscale ACL drafted, not applied (Tim's step). |
| 3 Platform | 🟡 partly | Monitoring is live on the edge (tailnet-only). Deploy platform = Caddy + compose via Ansible (Tim's pick, 2026-11-11): role `caddy` runs Caddy 2.11.2 on :80 (host nginx stopped, config kept for rollback), serves smartStudent with identical responses, metrics scraped by Prometheus. Public 80/443 stay closed until a domain + Tim's yes; then drop `auto_https off` and open the firewall. freqtrade stays on the edge. |
| 4 Recon platform | ⬜ not started | Needs a domain (interactsh NS delegation) and Tim's scope files. |
| 5 Public demos | 🟡 started | **Looking glass** (`apps/lg`) live tailnet-only at `https://instance-20260702-1842.tail3548c0.ts.net:8446` (ping, mtr, DNS; public targets only; 6/min per client). **Trading dashboard** (`apps/trading`) live tailnet-only at `:8447` (paper results: −21.5% over 101 trades, last trade 2026-11-04; Tim to decide if a losing strategy goes public). **Request tracer** (`apps/trace`) live tailnet-only at `:8448`. All three planned demos built; going public needs a domain and Tim's yes. Stewie (video generator) not started. |
| 6 Portfolio | 🟡 partly | `README.md`, `docs/ARCHITECTURE.md` (Mermaid diagrams) and `.github/workflows/ci.yml` (terraform fmt/validate, ansible-lint, syntax check, gitleaks) done; checks pass locally/on the edge. The repo has **no remote**; creating a public GitHub repo needs Tim's yes after a secret scan. Live links and CV note wait for the demos. |

## Running right now

- **Edge** = instance `newLifeOS`, hostname `instance-20260702-1842`, Ubuntu 20.04, 1 OCPU / 6 GB, private `10.0.0.165`, Tailscale `100.112.185.21`.
  SSH: `ssh -i ~/.ssh/oracle_lifeos ubuntu@100.112.185.21`. Runs freqtrade (dry-run), readChinese, Syncthing (Obsidian Vault), the monitoring stack.
- **Worker launch retry**: systemd timer `worker-retry.timer` on the edge tries to launch the worker every ~5 min with the edge's instance principal
  (`infra/worker-retry/`, deployed to `/opt/oci-homelab/worker-retry/`). Batam keeps answering "Out of host capacity" (about 1,820 attempts by 2026-11-11).
  Gives up after 10,500 attempts (around 2026-12-10). Telegram (@timsurrealbot) pings on: 🎉 launched, ⏳ once per 2016 attempts (~weekly), ⚠️ unexpected error, 🛑 give-up. Silence in between is normal.
- **Monitoring** URLs and alert rules: `docs/RUNBOOK.md`. All UIs are on 127.0.0.1, published only through Tailscale Serve.

## Next steps, in order

Single-server plan (ADR-009): build everything on the edge; don't wait for the worker.

1. ✅ Caddy role done; Prometheus scrapes it.
2. **Domain** (Tim): unlocks Caddy TLS, `status.<domain>`, interactsh and the demos.
3. **Demos on the edge, tailnet-first**: ✅ looking glass. ✅ trading dashboard. ✅ request tracer. When the worker arrives, the tracer's worker probe turns green automatically. New apps go in `apps/<name>/` + `apps_enabled` + a Caddy site + a `caddy_tailnet_ports` entry.
4. **Recon pipeline** once scope files exist; interactsh once the domain exists.
5. Restore drill; GitHub repo (Tim's yes); Ubuntu 20.04 upgrade (Tim's yes, fresh backup).

**Whenever Telegram says 🎉 (worker launched)**:
   - On Windows, in `infra/terraform/`: `terraform import oci_core_instance.worker <ocid>`, then `terraform plan` must show no changes to the worker.
   - Check it booted, has NAT egress (`curl -m 6 https://ifconfig.me` from the worker), and SSH from the edge works (`ssh -i ~/.ssh/id_ed25519_ansible ubuntu@10.0.1.10`).
   - Run the Ansible baseline against `worker_hosts` (see RUNBOOK), then add `{target: 10.0.1.10:9100, name: worker}` to `monitoring_node_targets`.
   - Ask Tim to delete the IAM policy `oci-homelab-worker-launch` and dynamic group `oci-homelab-edge` (agents never change IAM).
   - Then move the heavy or risky workloads (recon, rendering, freqtrade) to it by changing inventory groups.

**If the retry gives up (🛑)**: the single-server plan already covers it; ask Tim whether to keep retrying.

## Waiting on Tim (user-only steps)

- Apply `infra/tailscale/policy.hujson` in the Tailscale admin console, tag the edge `tag:edge`, approve its `10.0.0.0/16` route and exit node.
- Remove stale tailnet nodes: `desktop-pbodc5a`, `instance-20260630-1435`, `lifeos-a1`.
- Create the Uptime Kuma admin account and add monitors (agents don't create accounts).
- Pick a domain (blocks Caddy, `status.<domain>`, interactsh, demos).
- Write bug bounty scope files (agents never pick targets).
- Optional: Pay As You Go upgrade (stops idle reclamation), revoke and replace the Telegram bot token (it was pasted in chat once), delete tfstate copies Syncthing may have spread before `.stignore` was updated.
- Before any **Ubuntu 20.04 to newer** upgrade on the edge: take a fresh boot volume backup and get Tim's yes.

## Gotchas that cost time before

- The `oci-*` MCP servers fail under API-key auth (`'security_token_file'`). Use the `oci` CLI (`export SUPPRESS_LABEL_WARNING=True`).
- This Windows machine's network fakes TCP connects: raw port probes always say "open". Check exposure with `ssh`/`curl` at the application level.
- Run remote scripts with the Bash tool: `ssh ... 'bash -s' <<'EOF' ... EOF`. PowerShell mangles the quoting.
- Never run `iptables-restore` or `netfilter-persistent reload` on the servers: it wipes Docker and Tailscale chains. The Ansible `firewall` role inserts rules one by one.
- `/etc/oci-homelab/*.env` files are root-only: read them with `sudo`.
- Ansible doesn't run on native Windows. Sync `infra/ansible` to the edge and run it there (RUNBOOK).
- Terraform state is local and git-ignored (`infra/terraform/terraform.tfstate` on Windows). Don't lose it; never commit it.
- Batam sometimes returns `LimitExceeded` even though the A1 quota has room. The retry script treats it as transient.
- The folder is Syncthing-synced across devices: no in-place `git checkout`/`git switch`; use `git worktree`.
- Commit only when Tim asks; never push without his yes.

## Session log

- 2026-11-04: Phases 0-2 and Phase 3 monitoring done, committed `98aa1e5`. Worker retry moved from the laptop to the edge with Telegram alerts.
- 2026-11-04: Retry stopped once on a spurious `LimitExceeded` (attempt 47). Script fixed and restarted, `e264b02`.
- 2026-11-05: Checked retry health: timer active, bot token valid, monitoring containers up, no alerts firing. Added this file.
- 2026-11-11: Tim switched to the single-server plan (ADR-009). Retry extended to ~5 weeks with weekly notes. Added CI workflow, README and ARCHITECTURE.md. Verified public port 80 is closed.
- 2026-11-11: Caddy + compose chosen. Boot volume backup `newLifeOS-pre-caddy-2026-11-11` (incremental) taken first. Caddy replaced nginx on :80; second Ansible run changed=0.
- 2026-11-11: Looking glass app (`apps/lg`) deployed via new Ansible `apps` role behind Caddy :8091, Tailscale Serve :8446. Guardrails tested (private/metadata IPs, flags, rate limit). CI runs its unit tests. Ansible sync now copies `infra/ansible` + `apps` (RUNBOOK).
- 2026-11-11: Trading dashboard (`apps/trading`) deployed: backend logs in to freqtrade with `/etc/oci-homelab/secrets/trading.env` (generated by Ansible from freqtrade's config, mode 600), serves only whitelisted fields, refuses a live bot. Caddy :8093, Serve :8447. Unit tests in CI.
- 2026-11-11: Request tracer (`apps/trace`) deployed: Caddy :8095 stamps forward time, app reports Server-Timing, browser derives network time; probes refresh in a background thread. Serve :8448. Unit tests in CI.
