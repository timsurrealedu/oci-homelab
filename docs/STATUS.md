# Status and handoff

Where the project stands, what is running, and what to do next. **Update this file at the end of every work session.** Last updated 2026-11-05.

## The goal

Turn Tim's single Oracle Cloud Always Free server (ap-batam-1) into a small, documented, $0 platform:
an internet-facing **edge** VM and a private **worker** VM, built with Terraform and Ansible, with monitoring, a deploy platform,
a bug bounty recon pipeline, a few public demos, and a portfolio-quality repo. Full goals, non-goals and phases: [`PRD.md`](../PRD.md).
Safety rules (cost $0, never terminate without a backup and Tim's yes, no admin UI on public ports, secrets never committed): the `oci-homelab` skill in `.claude/skills/`.

## Phase progress

| Phase | State | Notes |
|---|---|---|
| 0 Audit and safety net | ✅ done | Inventory in `docs/inventory-2026-11.md`. Old pm2 apps (lifeOS, noema...) decommissioned at Tim's request. Boot volume backup taken. |
| 1 IaC foundation | ✅ done except the worker | Terraform (`infra/terraform/`) imports the VCN, gateways, subnets and edge; adds NSGs. Edge shrunk in place to 1 OCPU / 6 GB. **Worker blocked on A1 capacity**, see below. |
| 2 Server baseline | ✅ done on the edge | Ansible (`infra/ansible/`, run *from the edge*). Worker gets the same baseline once it exists. Tailscale ACL drafted, not applied (Tim's step). |
| 3 Platform | 🟡 partly | Monitoring is live on the edge (Prometheus, Alertmanager to Telegram, Grafana, Uptime Kuma; tailnet-only). Not started: Coolify/Dokploy on the worker, Caddy on the edge, moving freqtrade, public status page (needs a domain). |
| 4 Recon platform | ⬜ not started | Needs a domain (interactsh NS delegation) and Tim's scope files. |
| 5 Public demos | ⬜ not started | Needs the worker, Caddy and a domain. Every demo needs Tim's yes before going public. |
| 6 Portfolio | ⬜ not started | README, architecture diagram, CI. The repo has **no remote**; creating a public GitHub repo needs Tim's yes after a secret scan. |

## Running right now

- **Edge** = instance `newLifeOS`, hostname `instance-20260702-1842`, Ubuntu 20.04, 1 OCPU / 6 GB, private `10.0.0.165`, Tailscale `100.112.185.21`.
  SSH: `ssh -i ~/.ssh/oracle_lifeos ubuntu@100.112.185.21`. Runs freqtrade (dry-run), readChinese, Syncthing (Obsidian Vault), the monitoring stack.
- **Worker launch retry**: systemd timer `worker-retry.timer` on the edge tries to launch the worker every ~5 min with the edge's instance principal
  (`infra/worker-retry/`, deployed to `/opt/oci-homelab/worker-retry/`). Batam keeps answering "Out of host capacity" (about 190 attempts by 2026-11-05).
  Gives up after 2016 attempts (7 days, around 2026-11-11). Telegram (@timsurrealbot) pings on: 🎉 launched, ⏳ once per 288 attempts (~daily), ⚠️ unexpected error, 🛑 give-up. Silence in between is normal.
- **Monitoring** URLs and alert rules: `docs/RUNBOOK.md`. All UIs are on 127.0.0.1, published only through Tailscale Serve.

## Next steps, in order

1. **When Telegram says 🎉 (worker launched)**:
   - On Windows, in `infra/terraform/`: `terraform import oci_core_instance.worker <ocid>`, then `terraform plan` must show no changes to the worker.
   - Check it booted, has NAT egress (`curl -m 6 https://ifconfig.me` from the worker), and SSH from the edge works (`ssh -i ~/.ssh/id_ed25519_ansible ubuntu@10.0.1.10`).
   - Run the Ansible baseline against `worker_hosts` (see RUNBOOK), then add `{target: 10.0.1.10:9100, name: worker}` to `monitoring_node_targets`.
   - Ask Tim to delete the IAM policy `oci-homelab-worker-launch` and dynamic group `oci-homelab-edge` (agents never change IAM).
   - Then continue Phase 3: Coolify or Dokploy on the worker (measure memory), move freqtrade to the worker, possibly move monitoring too.
2. **If the retry gives up (🛑)** or Tim changes his mind: options are to keep retrying (reset `/opt/oci-homelab/worker-retry/attempts` and re-enable the timer), try other hours, or accept one VM. Ask Tim.
3. **Work that doesn't need the worker**: Caddy on the edge (needs a domain first), CI workflow (terraform fmt/validate, ansible-lint, gitleaks), README and architecture diagram, restore drill from the boot volume backup.

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
