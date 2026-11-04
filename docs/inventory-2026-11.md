# OCI inventory: 2026-11-04 (Phase 0)

Region `ap-batam-1`, AD `sjag:AP-BATAM-1-AD-1`, all resources in the root compartment (tenancy). Object Storage namespace `axbksq2eba46`.
Gathered with the `oci` CLI (the oci-compute/networking/monitoring/usage MCP servers fail with `'security_token_file'`; see "Tooling notes").

## Compute

| Resource | Details |
|---|---|
| Instance `newLifeOS` | `VM.Standard.A1.Flex` 2 OCPU / 8 GB, RUNNING, created 2026-07-02. Hostname `instance-20260702-1842`. Ubuntu **20.04.6 LTS** (standard support ended 2025-04). OCID `ocid1.instance.oc1.ap-batam-1.anrguljrfmise5aciaelrdequkbsutibfwmajfiibys4e5jercdsbxihfera` |
| VNIC | private `10.0.0.165`, public (ephemeral) `168.110.202.46`, subnet `public subnet-lifeos`, no NSGs, skip-source-dest-check = false. OCID `ocid1.vnic.oc1.ap-batam-1.abrguljrjvl7l6gr3mzojkvcio2pnyfgp2qn7fpnfxw65fbudvexhpkvsgjq` |
| Boot volume (attached) | `instance-20260702-1842 (Boot Volume)` 47 GB, 10 VPU. `ocid1.bootvolume.oc1.ap-batam-1.abrguljrz7gal2k2u6ecwebpn6he3agxu6qglnghwxznaf7k6vxqafjcu2ua` |
| Boot volume (**orphan**) | `lifeos-a1 (Boot Volume)` 47 GB, AVAILABLE, not attached (left from the old `lifeos-a1` instance). `ocid1.bootvolume.oc1.ap-batam-1.abrguljr4a463tox7jj373fwyz7pxr76gj4hvi6vmde2e5wznbr762vyzucq` |
| Block volumes | none |
| Boot volume backups | `newLifeOS-pre-phase1-2026-11-04` (FULL, created in Phase 0). `ocid1.bootvolumebackup.oc1.ap-batam-1.abrguljrjioioo3jinxp4fibpnpbnnatexbsbs5vz3p43ejabbnemcm27fna` |

Block storage used at audit: 94 / 200 GB. After Phase 0 (orphan deleted): **47 / 200 GB**; volume backups 2 / 5 (`newLifeOS-pre-phase1-2026-11-04`, `lifeos-a1-orphan-final-2026-11-04` OCID `ocid1.bootvolumebackup.oc1.ap-batam-1.abrguljryqoiatznnnfj6iwg37vsexfl7c5bi67e67iw4x3yqqlajri6exna`).

## Network

The VCN already has the public + private split the PRD wants, with OCI's managed NAT gateway. **Keep these CIDRs** (public 10.0.0.0/24, private 10.0.1.0/24) instead of the PRD's 10.0.1/10.0.2 numbering: renumbering would mean recreating the instance's VNIC.

| Resource | Details |
|---|---|
| VCN `lifeos` | `10.0.0.0/16`, DNS label `lifeos`. `ocid1.vcn.oc1.ap-batam-1.amaaaaaafmise5aawvttsrrvbu3tlle6go6fkfomlc4uzwevrjm46ao6q4pq` |
| Subnet `public subnet-lifeos` | `10.0.0.0/24`, public IPs allowed, RT = default, SL = Default. `ocid1.subnet.oc1.ap-batam-1.aaaaaaaayfpvg7ck4wgnut5kjnbca26miel6aumwlfssljq3tanihu6ehaza` |
| Subnet `private subnet-lifeos` | `10.0.1.0/24`, prohibit public IP, RT = private, SL = private. Empty today. `ocid1.subnet.oc1.ap-batam-1.aaaaaaaa7lvx73glpiov2y4ifexuq2wrxp7y6bryxjyiuwzvd5gyv4unsb5q` |
| Route table `default route table for lifeos` | `0.0.0.0/0 → IGW`. `ocid1.routetable.oc1.ap-batam-1.aaaaaaaar47cmwoiad4qjydy4puf5eexseiahvcff5mdaiookpzg3raoigba` |
| Route table `route table for private private subnet-lifeos` | `0.0.0.0/0 → NAT GW`, `all-hsg-services → SGW`. `ocid1.routetable.oc1.ap-batam-1.aaaaaaaanrqt4pt3ugv6knrgwtcpo4bhgzpesfu7lizsfdwv22kcbnkrxgnq` |
| Internet gateway | `Internet gateway-lifeos`, enabled. `ocid1.internetgateway.oc1.ap-batam-1.aaaaaaaafhrbkcjasyajrv2c3drhwins4wswxzycuw7filk2tb2ezntyhivq` |
| NAT gateway | `NAT gateway-lifeos`, NAT IP `168.110.215.167`, not blocked. `ocid1.natgateway.oc1.ap-batam-1.aaaaaaaauog54rdxxuqw3m6dd7w7j5nazqorjhs74f45vxvxkwqrmlkmlzta` |
| Service gateway | `Service gateway-lifeos`, All HSG services. `ocid1.servicegateway.oc1.ap-batam-1.aaaaaaaafgkbreutpmgy42hhtkfwo2cmfvhpgzkpbpfgxxuaoaz2ejmzggfq` |
| NSGs | none |
| Reserved public IPs | none (the instance's public IP is ephemeral: reserve it before anything that could detach the VNIC) |

### Security lists

`Default Security List for lifeos` (public subnet) `ocid1.securitylist.oc1.ap-batam-1.aaaaaaaaa2roegbwwzrym2rlixuzvjeajvjmy3mmlmwgmttwzttzzi6qcwca`
- IN tcp 22 from 0.0.0.0/0
- IN tcp 80 from 0.0.0.0/0
- IN icmp 3/4 from 0.0.0.0/0, icmp 3 from 10.0.0.0/16
- OUT all

`security list for private subnet-lifeos` `ocid1.securitylist.oc1.ap-batam-1.aaaaaaaagd77yne3k66ywv3altlvfaqiidsnp4rcqdbqzxxhygfwviy7lpla`
- IN tcp 22 from 10.0.0.0/16; icmp 3/4 from anywhere, icmp 3 from VCN
- OUT all

## Host (newLifeOS)

Disk 27/45 GB used. RAM ~1.15 GB used of 7.9 GB. Up since 2026-11-02 08:58.

Host firewall: iptables (netfilter-persistent) `INPUT`: ts-input → established → icmp → lo → **tcp 22 only** → REJECT. ufw inactive. `ip_forward=1`.

| Port (bind) | Process | Reachable from |
|---|---|---|
| 22 (0.0.0.0) | sshd: keys only, `PermitRootLogin without-password` | **internet** + tailnet |
| 80 (0.0.0.0) | nginx → smartStudent SPA (`~/smartStudent/frontend/dist`), `/api` → :3001 | tailnet; **internet via Tailscale Funnel :8443** |
| 3001 (0.0.0.0) | node (smartStudent API, systemd `smartstudent.service`) | tailnet |
| 7681 (0.0.0.0) | ttyd `-W` (writable, **no auth**) → `tmux new -A -s main` | tailnet |
| 7777 (0.0.0.0) | pm2 (lifeOS) | tailnet; Tailscale Serve :443 |
| 8888 (0.0.0.0) | JupyterLab (password set), root dir `/home/ubuntu` | tailnet |
| 3107 / 3108 (*) | next-server: noema / readChinese | tailnet; Tailscale Serve :8444 / :8445 |
| 8080 (127.0.0.1) | freqtrade API (Docker) | local only |
| 8384 (127.0.0.1) | Syncthing GUI | local only |
| 22000 tcp/udp, 21027 udp | Syncthing sync/discovery | blocked by iptables except via tailnet |
| 111 (0.0.0.0) | rpcbind | tailnet (unneeded) |

Tailscale Serve/Funnel on `instance-20260702-1842.tail3548c0.ts.net`:
- `:443` → 127.0.0.1:7777 (tailnet only)
- `:8443` → 127.0.0.1:80 (**Funnel on: public internet**)
- `:8444` → 127.0.0.1:3107, `:8445` → 127.0.0.1:3108 (tailnet only)

Workloads: Docker `freqtrade` (stable, dry-run); pm2 `lifeOS`, `lifeOS-editor`, `lifeOS-playground`, `noema`, `noema-worker`, `readchinese`; systemd `smartstudent`, `nginx`; Syncthing (Obsidian Vault 127 MB); ttyd; JupyterLab.
Cron: aiTrading weekly report (Sun 18:00), stewie `run.py --once` 6×/day, pegilagiMarketing render 3×/day + export-lifeos daily.
Largest dirs: `mycode` 7.0 GB, `stewie` 2.1 GB, `noema` 1.7 GB, `miniforge3` 1.1 GB, `readChinese` 870 MB, `smartStudent` 382 MB (+ a 380 MB `.backup` copy), `pegilagiMarketing` 306 MB.

Tailnet stale nodes: `desktop-pbodc5a` (150 d), `instance-20260630-1435` (126 d), `lifeos-a1` (125 d). Also long-offline: `tuf-fedora` (44 d), `xiaomi-14` (48 d), `xiaomi-pad-6` (28 d), `poco-x8-pro-max` (37 d).

## External exposure check (2026-11-04)

Raw TCP probes from the Windows box are useless: the local network accepts every TCP connect (even to `192.0.2.1`). Verified at the application level instead:
- `ssh ubuntu@168.110.202.46`: answers (key auth OK).
- `curl http://168.110.202.46:{80,3001,7681,7777,8888}`: all time out (host iptables REJECT; OCI SL also blocks all but 22/80).
- `https://instance-20260702-1842.tail3548c0.ts.net:8443/health`: **200 from the internet** (Funnel).

## Reclamation baseline (oci_computeagent, daily p95, 2026-10-28 → 11-04)

| Metric | Before reboot (10-28 → 11-02) | Since reboot (11-02 → 11-04) | Threshold |
|---|---|---|---|
| CpuUtilization p95 | 5.0–5.7% | 2.7–2.9% | 20% |
| MemoryUtilization p95 | 20.7–20.9% | 16.9–17.2% | 20% |
| Network | far below 20% of 2 Gbps | same | 20% |

All three metrics are now **under 20%**. Before the 11-02 reboot, memory was just above the line. If nothing changes, the 7-day window runs out around **2026-11-09**. Phase 1/3 must add real resident workloads (Postgres, Prometheus, Coolify) or memory reservations before then.

## Cost

Usage API, COST, by service: October 2026 = $0.00, November 2026 (to date) = $0.00. No non-zero line items.

## Changes made in Phase 0 (2026-11-04)

Backups first:
- Boot volume backup `newLifeOS-pre-phase1-2026-11-04` (FULL, AVAILABLE, 28 GB unique).
- Off-box at `C:\Users\timsurreal\Backups\oci-homelab\2026-11-04\`: `app-data.tgz` (2.4 GB, gzip-verified: lifeOS, noema, readChinese, Obsidian Vault, aiTrading, smartStudent, stewie, pegilagiMarketing, backups, Syncthing state; build dirs excluded) and `system-config.tgz` (nginx, sshd_config, iptables rules, pm2 dump, Jupyter config, crontab, Tailscale serve JSON, systemd units). `~/mycode` (7 GB) is only in the boot volume backup.

Then, per Tim's checkpoint answers:
- pm2 `lifeOS`, `lifeOS-editor` (= **ttyd** :7681), `lifeOS-playground` (= **JupyterLab** :8888), `noema`, `noema-worker` deleted; `pm2 save`. Folders stay on disk. **Do not delete `~/noema`**: `readchinese` runs on `~/noema/.node-v24.14.0`. To bring back ttyd/Jupyter: re-add from the pm2 dump in `system-config.tgz`, bound to the Tailscale IP.
- Tailscale Funnel on :8443 turned off; :8443 → nginx (smartStudent) is now tailnet-only. Serve routes :443 (lifeOS) and :8444 (noema) removed. Public relay check for the Funnel URL now times out.
- Orphan boot volume `lifeos-a1 (Boot Volume)`: backed up as `lifeos-a1-orphan-final-2026-11-04`, then deleted (Tim's yes in chat).
- `readchinese` (200 on :3108) and `smartstudent` (200 on /health) checked after the changes. RAM used dropped from ~1.15 GB to ~0.9 GB.

## Changes made in Phase 1 (2026-11-04)

- Terraform (`infra/terraform/`) now manages all 11 existing resources (imported with zero drift) plus `nsg-edge` (`ocid1.networksecuritygroup.oc1.ap-batam-1.aaaaaaaabmgu6wzxizy3nenejwjubprwfxkxgaglssqkqy6dqeusmdhi7c7a`) and `nsg-worker` (`ocid1.networksecuritygroup.oc1.ap-batam-1.aaaaaaaa6vsjfchnpxzejucc4a22a7kvroik3retf2tmstyrffviy5lnwylq`).
- `newLifeOS` (edge) resized in place to **1 OCPU / 6 GB**, `nsg-edge` attached. Public and private IPs unchanged. All services came back after the reboot.
- Public TCP 80 moved from the default security list to `nsg-edge`.
- Worker launch (1 OCPU / 6 GB, Ubuntu 24.04, `10.0.1.10`, no public IP): **Out of host capacity** on the first try. Retrying via `scripts/retry-worker.sh` (see ADR-005).
- `Projects/.stignore` now excludes `.terraform/`, `*.tfstate*`, `*.tfplan` and `*.tfvars` from Syncthing.

## Tooling notes

- `oracle.oci-{compute,networking,monitoring,usage}-mcp-server` read `security_token_file` from the profile, i.e. they expect `oci session authenticate` (browser login) rather than API-key auth. `oci-cloud` (with `OCI_MCP_AUTH_TYPE=api_key`) and the `oci` CLI work.
- `~/.ssh/oracle_lifeos` had an `Everyone:(F)` ACL, so OpenSSH refused it. Fixed with `icacls` (owner read only).
