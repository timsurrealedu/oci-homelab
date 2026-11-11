---
name: oci-homelab
description: Runbook for building and operating timsurreal's Oracle Cloud (OCI) Always Free homelab in ap-batam-1 - A1 Flex compute, VCN/subnets, Tailscale, Docker/Coolify/Caddy, Terraform. Use before any OCI action (inspect, launch, resize, network change, terminate), when the oci-* MCP tools or the oci CLI are involved, or when deploying services onto the Oracle servers.
---

# OCI homelab runbook

Read `PRD.md` in this project for the goals. This file holds the facts and rules for touching the account.

## Account facts (verified 2026-11-04)

- Region `ap-batam-1` (Indonesia), AD `sjag:AP-BATAM-1-AD-1`. Tenancy OCID is in `~/.oci/config` (profile `DEFAULT`, API-key auth).
- **Since 2026-11-04 Phase 1:** Terraform in `infra/terraform/` manages the VCN, gateways, route tables, security lists, subnets, NSGs (`nsg-edge`, `nsg-worker`), edge and worker. Change infra there, not via MCP/CLI writes. `newLifeOS` = edge, now **1 OCPU / 6 GB**. Worker `10.0.1.10` (create retried on capacity errors by `scripts/retry-worker.sh`).
- **Since Phase 2 (2026-11-04):** edge baseline is Ansible-managed (`infra/ansible`, run from the edge, see `docs/RUNBOOK.md`): SSH `PermitRootLogin no` + `AllowUsers ubuntu`, fail2ban, 2 GB swap, node exporter :9100, Docker log rotation + live-restore, iptables via the `firewall` role (never `iptables-restore`/`netfilter-persistent reload` live: it wipes Docker/Tailscale chains). Tailscale advertises `10.0.0.0/16` + exit node; route approval/tags wait on `infra/tailscale/policy.hujson` being applied (user step).
- **Since Phase 3 start (2026-11-04):** monitoring stack on the edge (`/opt/oci-homelab/monitoring`, Ansible role `monitoring`): Prometheus, Alertmanager → Telegram @timsurrealbot, Grafana, Uptime Kuma, all on 127.0.0.1 and published via Tailscale Serve ports 3000/3002/9090/9093. Telegram settings in `/etc/oci-homelab/telegram.env`. URLs in `docs/RUNBOOK.md`.
- **Since 2026-11-11:** edge runs **Ubuntu 24.04 LTS** (kernel 7.0 oracle, iptables nft backend); after any release upgrade re-render `rules.v4` with the `firewall` role before rebooting (RUNBOOK). Going public is prepared in code (`public_domain` / `public_sites` in `host_vars/edge.yml`, `edge_public_web` in Terraform).
- Original instance (pre-Phase 1): `newLifeOS` (hostname `instance-20260702-1842`), `VM.Standard.A1.Flex` 2 OCPU / 8 GB, Ubuntu 20.04, 45 GB boot volume (27 GB used). Private IP `10.0.0.165` in subnet `10.0.0.0/24`. Public IP `168.110.202.46`. Tailscale `100.112.185.21` (offers exit node).
- SSH from Windows: `ssh -i ~/.ssh/oracle_lifeos ubuntu@100.112.185.21`. Keep `-o BatchMode=yes` for scripted calls.
- Running now (since Phase 0): Docker `freqtrade` (dry-run, OKX), pm2 `readchinese` (no Funnel), Syncthing holding `/home/ubuntu/Obsidian Vault`, the monitoring stack, `worker-retry.timer`. The lifeOS/noema pm2 apps (and ttyd/Jupyter with them) were decommissioned. Only SSH :22 is reachable from the internet. Current state and next steps: `docs/STATUS.md`.

## Always Free limits (Oracle docs as of 2026-11)

- A1 Flex: **1,500 OCPU-hours + 9,000 GB-hours per month = 2 OCPU / 12 GB total**, one instance or split in two (1 OCPU each). The existing instance already uses the full 2 OCPU, so a second instance requires shrinking it first.
- Block storage 200 GB total incl. boot volumes (min boot ~47-50 GB), 5 volume backups. Object storage 20 GB. 2 VCNs. 10 TB egress/month.
- Re-verify on https://docs.oracle.com/en-us/iaas/Content/FreeTier/resourceref.htm before sizing; it changed in 2026.
- **Idle reclamation:** an Always Free instance is reclaimable when, over 7 days, 95th-percentile CPU < 20% AND network < 20% AND (A1) memory < 20%. Every instance must keep at least one of these above 20% (memory is the easy one). Verify with `oci-monitoring` after changes.
- Pay As You Go accounts reportedly are not reclaimed and keep the free allowance. Upgrading is the user's decision, never the agent's.

## Hard rules

1. **Cost must stay $0.** Before creating anything, confirm it is Always Free eligible (shape, size, count). After changes, check `oci-usage` for any non-zero cost. Never create paid shapes, load balancers beyond the free one, or extra block volumes over 200 GB.
2. **Never terminate an instance, delete a boot volume, VCN or subnet without (a) a verified backup and (b) the user's explicit yes in chat for that specific resource.** `ap-batam-1` often returns "Out of host capacity" for A1 launches; a terminated A1 may not come back. Prefer in-place resize (`update_instance` shape config, then reboot) over terminate-and-recreate.
3. Never touch credentials in the console, never change IAM policies, billing, account tier or budgets yourself. List those as user steps.
4. No admin UI on a public port. Admin panels (Coolify, Grafana, Portainer, ttyd, Syncthing GUI, Freqtrade API) bind to localhost or the Tailscale interface only. Public ingress: 80/443 (Caddy), plus 53/udp+tcp and whatever interactsh needs on the edge.
5. Secrets go in `.env` files that are git-ignored, or in Coolify's secret store. Never commit `~/.oci`, SSH keys, Tailscale auth keys, API tokens.
6. This folder is Syncthing-synced (see `Projects/CLAUDE.md`): don't switch git branches in place. Terraform state (`*.tfstate*`) and `.terraform/` stay out of git.

## Which tool for what

| Need | Use |
|---|---|
| List/inspect instances, images; resize; start/stop/reboot | `oci-compute` MCP |
| Inspect VCNs, subnets, security lists, NSGs | `oci-networking` MCP (read). It can create VCN/subnet but **not** route tables, gateways or rule changes, so don't build networks with it |
| Anything else in the SDK (route tables, IGW, NAT, security list rules, boot volume backups, limits) | `oci-cloud` MCP (`find_oci_api` → `describe_oci_operation` → `invoke_oci_api`) or the `oci` CLI |
| CPU/memory/network metrics, reclamation check | `oci-monitoring` MCP (namespace `oci_computeagent`, metrics `CpuUtilization`, `MemoryUtilization`, `NetworksBytesIn/Out`) |
| Cost check | `oci-usage` MCP |
| Declaring the real infrastructure | **Terraform** (`oracle/oci` provider, auth from `~/.oci/config`) in `infra/terraform/`. Import existing resources (`terraform import`) instead of recreating them |
| Configuring servers | Ansible in `infra/ansible/`. Ansible does not run on native Windows: run it from the edge server (as control node, reaching the worker over the private subnet/Tailscale) or from the Arch laptop |

## Windows quirks on this machine

- `oci` CLI was installed with `uv tool install --python 3.12 oci-cli`. Terraform via winget (new shells pick it up from PATH; otherwise look under `%LOCALAPPDATA%\Microsoft\WinGet\Links`).
- Oracle MCP servers need Python >= 3.13 (`uvx --python 3.13 ...`). `oci-cloud-mcp-server` writes a hardcoded `/tmp/audit.log` → `C:\tmp` must exist (it was created).
- Quick health check: `oci iam region list --output table` (proves the API key works).
- **oci-compute / oci-networking / oci-monitoring / oci-usage MCP servers fail with `'security_token_file'`** under API-key auth (they expect `oci session authenticate`). Use `oci-cloud` MCP or the `oci` CLI (`export SUPPRESS_LABEL_WARNING=True`, `2>/dev/null` hides SyntaxWarnings).
- Local network fakes TCP connects (any host:port "opens", even 192.0.2.1). Verify external exposure at the app level (`ssh`, `curl -m 6`) or from an online checker, never with raw port probes.
- Run remote multi-line scripts with the Bash tool: `ssh ... 'bash -s' <<'EOF' ... EOF` (PowerShell mangles quotes).
- Existing VCN `lifeos` 10.0.0.0/16 already has public `10.0.0.0/24` (IGW), private `10.0.1.0/24` (NAT GW + service GW). Keep these CIDRs. Full OCIDs in `docs/inventory-2026-11.md`.
- Off-box backups live in `C:\Users\timsurreal\Backups\oci-homelab\<date>\` (outside the Syncthing tree).

## Target network (from the PRD)

```
VCN 10.0.0.0/16 (reuse/import existing VCN; current subnet is 10.0.0.0/24)
├─ public subnet  10.0.1.0/24  → edge   (1 OCPU/6 GB, public IP)  Caddy, demos, interactsh, Tailscale subnet router, NAT for worker
└─ private subnet 10.0.2.0/24  → worker (1 OCPU/6 GB, no public IP) stewie, freqtrade, recon jobs, Postgres
Tailscale overlay: edge, worker, Windows/Arch laptops, phone. Tailscale ACLs restrict admin ports to timsurreal's devices.
```

Keep the existing subnet CIDR if renumbering would force recreating the instance's VNIC; adapt the plan rather than breaking the running box. If OCI's managed NAT gateway is unavailable on the account, route the worker's egress through the edge (iptables MASQUERADE + route table entry pointing at the edge's private IP with source/dest check disabled on its VNIC).

## Checklist before declaring a phase done

- `oci-usage`: $0. `oci-monitoring`: each instance above 20% on at least one reclamation metric over the last 24 h, or explain the plan.
- From outside the tailnet (e.g. `curl` from the Windows box with Tailscale down, or an online port checker), only intended ports answer.
- `terraform plan` shows no drift. Ansible run is idempotent (second run: `changed=0`).
- README/ARCHITECTURE docs updated with what changed.
