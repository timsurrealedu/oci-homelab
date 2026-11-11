# Runbook

## Run Ansible (control node = edge)

Ansible doesn't run on native Windows. The control node is the edge: venv `/opt/oci-homelab/ansible` (ansible-core 2.18, Python 3.13 from miniforge), checkout `~/oci-homelab/infra/ansible`.

Until the repo has a remote, push the tree from Windows:

```bash
tar -cf - infra/ansible apps | ssh -i ~/.ssh/oracle_lifeos ubuntu@100.112.185.21 'rm -rf ~/oci-homelab/infra/ansible ~/oci-homelab/apps && tar -xf - -C ~/oci-homelab'
```

On the edge:

```bash
cd ~/oci-homelab/infra/ansible
/opt/oci-homelab/ansible/bin/ansible-playbook site.yml --limit edge --check --diff   # dry run
/opt/oci-homelab/ansible/bin/ansible-playbook site.yml --limit edge                  # apply
/opt/oci-homelab/ansible/bin/ansible-playbook site.yml --limit edge                  # must report changed=0
```

The worker is reached at `10.0.1.10` with `~/.ssh/id_ed25519_ansible` (its public half is baked in by Terraform/cloud-init).

## Worker launch retry

See ADR-006. Status: `systemctl status worker-retry.timer`, log: `journalctl -u worker-retry.service`, attempts: `/opt/oci-homelab/worker-retry/attempts`. Telegram test: `sudo /opt/oci-homelab/worker-retry/notify-telegram.sh "test"`.

Errors: "Out of host capacity", TooManyRequests and InternalError retry silently. LimitExceeded also retries (Oracle returned it once with the quota half free, 2026-11-04) and stops after 12 in a row. Any other error stops the timer with a ⚠️ message. To resume after fixing: `sudo systemctl enable --now worker-retry.timer`.

## Backups

- Boot volume backups (2 of 5 free used): `newLifeOS-pre-phase1-2026-11-04`, `lifeos-a1-orphan-final-2026-11-04`.
- Off-box app data: `C:\Users\timsurreal\Backups\oci-homelab\<date>\` (`app-data.tgz`, `system-config.tgz`).
- Restore drill: not yet done (Phase 6 acceptance item).

## Monitoring (edge, tailnet-only)

| UI | URL |
|---|---|
| Grafana | https://instance-20260702-1842.tail3548c0.ts.net:3000 (user `admin`, password: `sudo cat /etc/oci-homelab/secrets/grafana_admin_password` on the edge) |
| Uptime Kuma | https://instance-20260702-1842.tail3548c0.ts.net:3002 |
| Prometheus | https://instance-20260702-1842.tail3548c0.ts.net:9090 |
| Alertmanager | https://instance-20260702-1842.tail3548c0.ts.net:9093 |

- Stack lives in `/opt/oci-homelab/monitoring` (`docker compose ps`, `docker compose logs <svc>`). Change it only via the Ansible role.
- Dashboards: "OCI Always Free reclamation" (7-day p95 memory/CPU against the 20% line) and "Node Exporter Full".
- Alerts (Telegram): `InstanceDown`, `ReclamationRisk` (3-day p95 memory and CPU < 20%), `DiskAlmostFull` (> 85%), `MemoryPressure` (> 90%).
- Test the alert path: POST a synthetic alert to `127.0.0.1:9093/api/v2/alerts` (see the Phase 3 notes) and check `alertmanager_notifications_total{integration="telegram"}`.
- Adding the worker: append `{target: 10.0.1.10:9100, name: worker}` to `monitoring_node_targets`.

## Going public (when a domain exists)

Everything is prepared in code; nothing is public until these steps run. Each site needs timsurreal's yes first.

1. DNS: point `lg.`, `trading.`, `trace.`, `status.<domain>` (A records) at the edge's public IP `168.110.202.46`. DNS-only (no Cloudflare proxy) unless `trusted_proxies` is added to Caddy.
2. `infra/terraform`: set `edge_public_web = true` in `terraform.tfvars`, `terraform plan` (expect one new rule: 443 on `nsg-edge`), then apply.
3. `infra/ansible/inventory/host_vars/edge.yml`: set `public_domain: <domain>` and `public_sites: [lg, ...]` (only the approved ones). The firewall opens 80/443 automatically when both are set.
4. Sync and run `site.yml`. Caddy gets Let's Encrypt certificates on first request. Check `https://<site>.<domain>` from outside the tailnet.
5. `status`: create the Uptime Kuma status page with slug `homelab` (or set `caddy_public_status_slug`). Only the status page paths are proxied; the admin UI is never public.

Tailnet addresses keep working unchanged. To go back: empty `public_sites`, re-run Ansible, `edge_public_web = false`.

## Restore drill (verified 2026-11-11)

Restore a boot volume backup into a temporary volume, attach it **read-only** to the edge, mount with `-o ro,noload`, compare, detach, delete:

```bash
oci bv boot-volume create --boot-volume-backup-id <backup> --availability-domain sjag:AP-BATAM-1-AD-1 --display-name restore-drill-<date>-TEMP --wait-for-state AVAILABLE
oci compute volume-attachment attach --instance-id <edge> --type paravirtualized --volume-id <restored> --is-read-only true --wait-for-state ATTACHED
# on the edge: mount -o ro,noload /dev/sdb1 /mnt/restore-drill ; compare ; umount
oci compute volume-attachment detach --volume-attachment-id <id> --force --wait-for-state SUCCEEDED
oci bv boot-volume delete --boot-volume-id <restored> --force --wait-for-state TERMINATED
```

Never reboot the edge while the restored disk is attached: both disks carry the label `cloudimg-rootfs`. SQLite databases in WAL mode (freqtrade) must be copied together with their `-wal`/`-shm` files to check them.

## Ubuntu release upgrades (done 20.04 -> 22.04 -> 24.04 on 2026-11-11)

Procedure: fresh boot volume backup (wait for AVAILABLE) -> `apt dist-upgrade` -> `systemd-run ... do-release-upgrade -f DistUpgradeViewNonInteractive` (survives SSH drops) -> **before rebooting**, re-run the `firewall` role -> reboot -> verify -> re-point third-party repos.

Pitfalls seen:
- The upgrade rewrites `/etc/iptables/rules.v4`: empty on 20.04 -> 22.04 (iptables switches to the nft backend), a dump of live Docker/Tailscale chains on 22.04 -> 24.04. Always re-render it with the `firewall` role before the reboot.
- Until the reboot, the old kernel can't load `nft_compat`, so the `iptables` module fails; writing `rules.v4` still works.
- Third-party repos are disabled: re-point `tailscale.list` to the new codename. NodeSource (`nodistro`) is codename-independent.
- smartStudent's Prisma engine is per-OpenSSL: after 22.04 (OpenSSL 3) run `npx prisma generate` in `~/smartStudent/backend` and restart `smartstudent`.
