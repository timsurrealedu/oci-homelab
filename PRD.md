# PRD: oci-homelab: timsurreal's Oracle Cloud platform

## Kickoff prompt (paste this to start the agent)

> You are setting up my Oracle Cloud Always Free server end to end. Work in `Projects/Tools/oci-homelab`. First read `PRD.md` (this file) fully and load the `oci-homelab` skill; it has the account facts, hard safety rules and which tool to use for what. You have the `oci-compute`, `oci-networking`, `oci-monitoring`, `oci-usage` and `oci-cloud` MCP servers, the `oci` CLI, Terraform, and SSH to the current server over Tailscale. Do as much as possible yourself, phase by phase, in the order below. Stop and ask me only at the **🛑 checkpoints** and for the **user-only steps**. At the end of each phase, report what changed and what you verified, and update the docs. Start with Phase 0.

---

## 1. Background

timsurreal (BINUS CS student; CTF/security, bots, game dev) has an OCI Always Free A1 server that is mostly idle. He no longer uses lifeOS or Noema (Google ecosystem + Slate replaced them). He wants the server to be:

1. **Functional**: things he actually uses.
2. **CV-worthy**: demonstrates cloud, networking (subnets, routing, NAT, Tailscale), IaC and security skills, with live URLs recruiters can click.
3. **Fun and public**: demos the general public can use.
4. **Eventually income-producing**, starting with bug bounties.

Idle is also a risk: Oracle reclaims Always Free instances that stay under 20% CPU, network and memory for 7 days. Current box: CPU ~2%, RAM ~17%.

## 2. Goals

| # | Goal | Success looks like |
|---|---|---|
| G1 | Infrastructure as code | Whole OCI setup in Terraform; servers configured by Ansible; rebuildable from the repo |
| G2 | Real network design | Public + private subnet, edge/worker split, NAT, security lists/NSGs, Tailscale overlay with ACLs, documented with a diagram |
| G3 | Deploy platform | Push to GitHub → service redeploys (Coolify or Dokploy); Caddy auto-HTTPS on subdomains |
| G4 | Observability | Uptime Kuma + Grafana/Prometheus (or Netdata); Telegram alerts; reclamation metrics visible |
| G5 | Bug bounty recon platform | Self-hosted interactsh OOB server + scheduled recon diffing with Telegram alerts |
| G6 | Fun public demos | "Trace your request" page, network looking glass, stewie public generator, paper-trading dashboard |
| G7 | Portfolio output | Public README with architecture diagram, write-up, and a status page; listed on timsurreal's portfolio |
| G8 | $0 and safe | Usage stays $0; no admin surfaces on the internet; secrets never committed |

## 3. Non-goals

- Running local LLMs on the box (2 OCPU is too weak); use API providers.
- Bulk storage, Nextcloud, media servers.
- Public deployment of **shopee-bot** (runs in timsurreal's logged-in Shopee session; against Shopee ToS) or **beelingua_bot** (automates BINUS coursework; reputational/academic risk). They are not in scope for public demos or the CV.
- Live-money trading. aiTrading stays **dry-run**. No selling signals/copy-trading (OJK licensing).
- Game servers, crypto mining, VPN resale (against Oracle terms / not useful).

## 4. Current state (verified 2026-11-04)

- Region `ap-batam-1`. One instance `newLifeOS`: A1 Flex **2 OCPU / 8 GB**, Ubuntu, 45 GB boot, private `10.0.0.165` in `10.0.0.0/24`, public `168.110.202.46`, Tailscale `100.112.185.21`.
- Services on it: Docker `freqtrade` (aiTrading dry-run; reports into `/home/ubuntu/Obsidian Vault/Trading/` on Sundays), pm2 `lifeOS`, `lifeOS-editor`, `lifeOS-playground`, `noema`, `noema-worker`, `readchinese`, Syncthing.
- Listening publicly on the host: 22, 80, 3001, 7681 (ttyd web terminal), 7777, 8888. Whether the OCI security list exposes them is unknown → Phase 0 audit.
- Tailnet has stale offline nodes: `instance-20260630-1435`, `lifeos-a1`, `desktop-pbodc5a` (old). Removing them is a user-only step in the Tailscale admin console.
- Local tooling on Windows: `oci` CLI 3.96, Terraform, uv/uvx, Node 24, gh, Tailscale. No Ansible (run it from the edge server or the Arch laptop).
- Related projects: `Projects/Automation/aiTrading` (Freqtrade + `deploy.md`), `Projects/Automation/stewie` (CPU-only short-video factory, built for this box), `Projects/Security/sentinel` (secret scanner, usable in this repo's CI), `Projects/Apps/portfolio`, `Projects/Apps/readChinese`.

## 5. Target architecture

```
                 Internet
                    │  DNS: <domain> (Cloudflare DNS, proxy off for oast/NS records)
                    ▼
OCI VCN 10.0.0.0/16 ─────────────────────────────────────────────
│ Public subnet 10.0.1.0/24 (route → Internet Gateway)
│   edge  (A1 1 OCPU / 6 GB, public IP)
│     Caddy :80/:443  → trace.<d>, lg.<d>, stewie.<d>, trading.<d>, status.<d>
│     interactsh-server (oast.<d>, :53 + HTTP via Caddy or dedicated ports)
│     Tailscale (subnet router for 10.0.0.0/16), NAT for worker if needed
│     Ansible control node
│ Private subnet 10.0.2.0/24 (route → NAT gateway, or edge as NAT)
│   worker (A1 1 OCPU / 6 GB, NO public IP)
│     Coolify/Dokploy apps: stewie, freqtrade + dashboard, recon jobs,
│     looking-glass backend, Postgres, Prometheus/Grafana, Uptime Kuma
──────────────────────────────────────────────────────────────────
Tailscale overlay: edge, worker, Windows (tuf), Arch laptop, phone
  ACLs: admin ports only from timsurreal's devices; Arch/Windows laptop can act as
  an optional GPU render node for stewie via Tailscale.
```

Adapt CIDRs to what exists: if the current `10.0.0.0/24` subnet can't be fit into this plan without recreating the instance's VNIC, keep it as the public subnet and add the private subnet alongside. Don't break the running box for tidy numbers.

### Getting from 1 instance to 2 (important)

The existing instance already uses the full 2 OCPU free budget. Path:

1. Back up: boot volume backup + `tar` of app data (lifeOS/Noema data, Obsidian Vault, freqtrade `user_data`, readchinese) copied off-box (to the Windows/Arch laptop over Tailscale).
2. Resize `newLifeOS` in place to **1 OCPU / 6 GB** (it becomes `edge`; keeps its public IP). Do **not** terminate and recreate: Oracle A1 capacity is often unavailable.
3. Launch `worker` 1 OCPU / 6 GB in the private subnet via Terraform. If launch fails with "Out of host capacity", retry on a schedule (e.g. every 10 min for a few hours) and meanwhile run everything on the edge.
4. `terraform import` the existing VCN, subnet, IGW, route tables, security lists and instance so Terraform manages them.

## 6. Phases

Each phase ends with: what changed, how it was verified, docs updated. Checkpoints marked 🛑 need timsurreal's explicit yes in chat.

### Phase 0: Access, audit, safety net
- Verify OCI API access (`oci iam region list`), MCP tools respond, SSH works.
- Inventory via MCP: instances, VCNs, subnets, security lists, route tables, gateways, boot volumes, backups, limits. Write it to `docs/inventory-2026-11.md`.
- Security audit: which ports the security list/NSG opens to 0.0.0.0/0 vs what's listening (ttyd on 7681 is the big one). **Close anything that's not SSH/80/443 immediately** if it is open to the internet. That's a safe, reversible tightening, so do it and report.
- Back up data off-box and create a boot volume backup (free: 5 backups).
- Pull 7-day reclamation metrics from `oci-monitoring`; record baseline.
- 🛑 Ask timsurreal: decommission lifeOS, lifeOS-editor, lifeOS-playground, noema, noema-worker? Keep or drop readchinese? Keep the Syncthing Obsidian Vault on the server or move it?

### Phase 1: Repo + IaC foundation
- Create the repo layout (§8). `git init`, `.gitignore` (tfstate, .terraform, .env, keys).
- Terraform: provider config from `~/.oci/config`; import existing resources; add the private subnet, route table, NAT path, security lists/NSGs (least privilege), and the worker instance with cloud-init that installs Tailscale. Keep state local (git-ignored) or in OCI Object Storage (free 20 GB) via the S3-compatible backend.
- 🛑 Before the resize/reboot of the existing instance, and before any `terraform apply` that would destroy/replace a resource, show the plan and wait for yes.

### Phase 2: Server baseline (Ansible)
- Roles: users/SSH hardening (keys only, no root login), unattended-upgrades, ufw/nftables consistent with security lists, fail2ban, Docker, Tailscale (edge as subnet router; tags `tag:edge`/`tag:worker`), time sync, swap file, node exporter.
- Idempotent: second run `changed=0`.
- Draft a Tailscale ACL policy file in the repo (`infra/tailscale/policy.hujson`). Applying it is a user-only step unless timsurreal provides an API token.

### Phase 3: Platform
- Coolify (or Dokploy if Coolify is too heavy for 6 GB; decide by measuring) on the worker, managed over Tailscale only. Caddy on the edge as the single public entry, reverse-proxying over the private subnet.
- Monitoring: Uptime Kuma (public status page at `status.<d>`), Prometheus + Grafana or Netdata (Tailscale-only), Telegram alert bot (timsurreal supplies the bot token as a user-only step).
- Move freqtrade to the worker (keep dry-run; keep the Sunday report working; its local API stays private).
- Confirm both instances sit above 20% on at least one reclamation metric; if not, set container memory reservations/caching sensibly (real workloads, not a busy-loop).

### Phase 4: Bug bounty recon platform (G5)
- Self-hosted **interactsh-server** on `oast.<d>` (NS delegation for the subdomain, ports 53/udp+tcp, HTTP/HTTPS). Resolve the port-80/443 conflict with Caddy (e.g. Caddy routes `*.oast.<d>` to interactsh's HTTP listener, or interactsh gets a dedicated IP-less setup); document the choice.
- Recon pipeline on the worker: per-program config listing **in-scope** domains only → subfinder → dnsx → httpx (tech/title/status) → store results (SQLite/Postgres) → diff vs previous run → Telegram alert on new hosts/changes. Scheduled (cron/systemd timers). Optional nuclei with conservative templates and rate limits.
- Guardrails: scope file is required per program; global rate limit; no brute-force/fuzzing by default; logs of what was scanned. Oracle's AUP dislikes aggressive scanning, so keep it gentle.
- Small web view (Tailscale-only) of recent findings.

### Phase 5: Fun public demos (G6)
1. **trace.<d>: "Trace your request"**: the visitor's request passes Caddy (edge, public subnet) → service on the worker (private subnet) → optionally through Tailscale to a home node. Each hop appends timing/hop headers; the page animates the path with real latencies and explains subnets/NAT/overlay. This is the networking showpiece.
2. **lg.<d>: network looking glass**: ping, traceroute/mtr, DNS lookup, from the Oracle server. Strict input validation (hostnames/IPs only, no flags), per-IP rate limits, no port scanning, no private-range targets. Also a Telegram/Discord bot front end (`/trace example.com`).
3. **stewie.<d>: public video generator**: visitors submit a topic, it's queued, rendered on the worker (or the home GPU node via Tailscale when online), shown in a gallery. Moderate topics (LLM filter + blocklist), cap jobs/day. Use **original characters/style**, not Family Guy IP, before going public.
4. **trading.<d>: paper-trading dashboard**: read-only public page (equity curve, open/closed trades, weekly reports) from freqtrade's API via a small backend; never expose the freqtrade API itself. Label clearly: paper money, not advice.
- 🛑 Before making any demo public, show timsurreal the URL and get a yes.

### Phase 6: Portfolio output (G7)
- `README.md`: what it is, live links, architecture diagram (Mermaid/SVG), stack, the edge/worker + subnet + Tailscale design, security choices, cost ($0).
- `docs/ARCHITECTURE.md`, `docs/RUNBOOK.md` (rebuild from scratch, restore from backup, rotate keys), `docs/DECISIONS.md` (short ADRs: Coolify vs Dokploy, NAT approach, interactsh routing).
- CI (GitHub Actions): `terraform fmt -check` + `validate`, `ansible-lint`, sentinel/gitleaks secret scan.
- Suggested CV bullet drafted in the README's companion note.
- 🛑 Creating the GitHub repo **public** and pushing is publishing: ask first, after a secret scan passes.

## 7. User-only steps (timsurreal does these; the agent prompts at the right moment)

1. **OCI API key (needed before Phase 0):** a key pair is already generated at `~/.oci/oci_api_key.pem` (+ `_public.pem`). In the OCI Console → Profile → My profile → API keys → Add API key → *Paste a public key* → paste `~/.oci/oci_api_key_public.pem`. Then copy your **User OCID** into `~/.oci/config` (replace `REPLACE_ME`). Fingerprint should match `9d:a7:41:5a:...`.
2. **Domain:** pick one (cheap domain on Cloudflare/Porkbun, or a free subdomain as a stopgap; interactsh needs NS delegation, so a real domain is strongly preferred) and point DNS at Cloudflare. Give the agent a Cloudflare API token scoped to that zone's DNS only, if you want it to manage records.
3. **Tailscale:** remove stale nodes; create a tagged auth key for the worker (or approve the device); apply the ACL policy (or give a scoped API token).
4. **Telegram bot token** for alerts (BotFather).
5. **Optional:** upgrade to Pay As You Go (stops idle reclamation; set a budget alert of $1 first).
6. **Bug bounty programs:** choose programs and write their scope files (the agent won't pick targets).

## 8. Repo layout

```
oci-homelab/
├─ PRD.md  README.md  CLAUDE.md  .mcp.json
├─ .claude/skills/oci-homelab/SKILL.md
├─ infra/
│  ├─ terraform/        # network, instances, imports, outputs
│  ├─ ansible/          # inventory, roles: base, docker, tailscale, caddy, monitoring
│  └─ tailscale/policy.hujson
├─ services/
│  ├─ caddy/  interactsh/  recon/  looking-glass/  trace/  trading-dashboard/
│  └─ (stewie and aiTrading stay in their own project folders; deploy configs here)
└─ docs/ ARCHITECTURE.md  RUNBOOK.md  DECISIONS.md  inventory-2026-11.md
```

## 9. Acceptance criteria (definition of done)

- [ ] `terraform plan` clean; all OCI resources declared or imported.
- [ ] Two instances (edge public, worker private) or a documented reason it's still one (capacity), with the plan to retry.
- [ ] Only 22 (ideally Tailscale-only), 80, 443, 53 + interactsh ports reachable from the internet; verified externally.
- [ ] Usage report shows $0; both instances above the reclamation threshold on at least one metric.
- [ ] interactsh answers DNS/HTTP for `oast.<d>`; recon pipeline ran on at least one real in-scope program and sent a Telegram diff.
- [ ] At least `trace.<d>` and `status.<d>` live publicly; looking glass, stewie and trading dashboard live or tracked as next steps.
- [ ] Freqtrade still running dry-run and weekly report still delivered.
- [ ] README with diagram + runbook; backups documented and one restore tested.
- [ ] No secrets in git (scan passes).
