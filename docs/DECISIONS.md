# Decisions

Short ADRs. Newest last.

## ADR-001: Keep the existing VCN and CIDRs (2026-11-04)

**Context.** The PRD sketched public `10.0.1.0/24` and private `10.0.2.0/24`. The console wizard had already built VCN `lifeos` (`10.0.0.0/16`) with public `10.0.0.0/24` and private `10.0.1.0/24`, and the edge's VNIC lives in `10.0.0.0/24`.
**Decision.** Keep the wizard's layout and import it. Edge stays at `10.0.0.165`, worker gets `10.0.1.10`.
**Why.** Renumbering means recreating the edge VNIC (or the instance). That risks the public IP and, in `ap-batam-1`, the A1 capacity itself.

## ADR-002: OCI NAT gateway for worker egress (2026-11-04)

**Context.** The worker has no public IP. Options were the managed NAT gateway, or the edge as NAT (iptables MASQUERADE, skip source/dest check, route `0.0.0.0/0` to `10.0.0.165`).
**Decision.** Use the existing managed NAT gateway (`168.110.215.167`) plus the service gateway for Oracle services.
**Why.** It already exists, costs $0, and doesn't make the edge a single point of failure for worker updates. The edge-as-NAT pattern stays documented in the skill as the fallback.

## ADR-003: Security lists for the baseline, NSGs per role (2026-11-04)

**Decision.** Subnet security lists carry only what every host needs (SSH, path-MTU ICMP). Service ports live in NSGs: `nsg-edge` (public HTTP now; 443/53 when Caddy and interactsh land) and `nsg-worker` (22/80/443/9100 **only from `nsg-edge`**).
**Why.** Rules follow the role rather than the subnet. Using the NSG as the source means the worker trusts the edge itself, not "anything in 10.0.0.0/24".

## ADR-004: Terraform state stays local for now (2026-11-04)

**Decision.** Local `terraform.tfstate` in `infra/terraform/`, git-ignored and excluded from Syncthing by `.stignore` rules (check those before running plan/apply from a second device).
**Why.** Only one machine (Windows) runs Terraform. Revisit when the Arch laptop or CI needs `plan`: move to OCI Object Storage via the S3-compatible backend (free 20 GB).

## ADR-005: Shrink in place, guard instances against replacement (2026-11-04)

**Decision.** `newLifeOS` was resized 2 OCPU / 8 GB → 1 OCPU / 6 GB in place (reboot, 2m48s) to free half the A1 budget for the worker. Both instances carry `prevent_destroy`, and `ignore_changes` covers launch-time fields (image, metadata, VNIC tags) so drift there can never plan a replacement.
**Worker capacity.** The first launch returned `500 Out of host capacity`. `infra/terraform/scripts/retry-worker.sh` retries every 10 minutes and applies only a saved plan whose sole change is creating `oci_core_instance.worker`. Until the worker exists, everything runs on the edge.

## ADR-006: Retry the worker launch from the edge, not the laptop (2026-11-04)

**Context.** The laptop loop stops whenever the lid closes.
**Decision.** `infra/worker-retry/` runs on the edge as `worker-retry.timer` (every 5 min, root, files in `/opt/oci-homelab/worker-retry/`). It calls `oci compute instance launch` with the same parameters as `oci_core_instance.worker`, authenticated by **instance principal**: dynamic group `oci-homelab-edge` (rule: the edge's instance OCID) plus policy `oci-homelab-worker-launch`, which grants read on instance-family and launch-only (`request.operation = 'LaunchInstance'`) rights on instance, volume and virtual-network families. Telegram (@timsurrealbot, `/etc/oci-homelab/telegram.env`, mode 600) pings on success, on any non-capacity error, daily while it is still trying, and on give-up after 7 days. The timer disables itself on any final outcome.
**Why.** No personal API key on an internet-facing host, and a compromised edge can't stop, change or delete anything through this policy. The private IP `10.0.1.10` and the 2-OCPU quota make a duplicate worker impossible.
**After launch.** `terraform import oci_core_instance.worker <ocid>` on the Terraform machine (config already matches; launch-time fields are in `ignore_changes`). Then Tim deletes the policy and the dynamic group (IAM is user-only).

## ADR-007: Host firewall = Oracle's iptables-persistent, managed rule by rule (2026-11-04)

**Context.** OCI Ubuntu images ship `/etc/iptables/rules.v4` with an `InstanceServices` chain guarding the metadata, iSCSI, DNS and NTP endpoints on 169.254.0.0/16. Oracle warns against removing it. ufw would replace that file's role. A full `iptables-restore` would also flush the chains Docker and Tailscale add at runtime.
**Decision.** Keep `iptables-persistent`. The Ansible `firewall` role (a) inserts each allowed rule live with the `iptables` module (idempotent `-C` check, never a flush) and (b) templates `rules.v4` for boot with Oracle's chain byte-for-byte. Per-host allowed ports live in `inventory/host_vars/*.yml` and mirror the NSGs. ufw stays installed but inactive.
**Trade-off.** Rules removed from the vars aren't deleted live (marked `honey:` in the role); a reboot or a manual `iptables -D` cleans them up.

## ADR-008: Monitoring on the edge for now, compose + Tailscale Serve (2026-11-04)

**Context.** The target design puts monitoring on the worker, but the worker is waiting on capacity, and the edge's memory was under the 20% reclamation line with ~5 days left.
**Decision.** Run Prometheus, Alertmanager, Grafana and Uptime Kuma on the edge as one compose project (Ansible role `monitoring`, host group `monitoring_hosts`). Host networking with every listener on `127.0.0.1`. The UIs are published only through **Tailscale Serve** (`https://instance-20260702-1842.tail3548c0.ts.net:{3000,3002,9090,9093}`, tailnet-only, real TLS). Alerts go to Telegram via Alertmanager's native receiver, with the bot token in a root-owned secrets file (`bot_token_file`), never in the repo.
**Why.** Real workloads the platform needs anyway (not a memory balloon). Serve avoids binding Docker to the tailnet IP, which fails if tailscaled starts after Docker at boot. Moving to the worker later means changing the `monitoring_hosts` group and adding `10.0.0.165:9100` as a scrape target.

## ADR-009: Build on one server; keep the worker as a bonus (2026-11-11)

**Context.** A week of launch attempts (about 1,800) all hit "Out of host capacity" in ap-batam-1. Waiting blocks every later phase.
**Decision.** Tim's call: the platform is built on the edge alone. Everything the PRD put on the worker (deploy platform, freqtrade, recon jobs, demo backends) runs on the edge for now. The retry timer keeps going (limit raised to 10,500 attempts, about 5 weeks from 2026-11-04; the ⏳ note is now weekly). The edge stays at 1 OCPU / 6 GB so the worker still fits the free quota if a launch succeeds.
**If the worker arrives.** Import it (ADR-006), run the Ansible baseline, then move the heavy or risky workloads (recon, stewie rendering, freqtrade) to it by changing inventory groups. Services are written host-agnostic (compose + Ansible roles keyed by groups) so this is a move, not a rewrite.
**Trade-off.** One box means public traffic and private workloads share a kernel; the NSG, host firewall and localhost/Tailscale-only admin binds carry more of the weight.
