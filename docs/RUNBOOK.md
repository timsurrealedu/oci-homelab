# Runbook

## Run Ansible (control node = edge)

Ansible doesn't run on native Windows. The control node is the edge: venv `/opt/oci-homelab/ansible` (ansible-core 2.18, Python 3.13 from miniforge), checkout `~/oci-homelab/infra/ansible`.

Until the repo has a remote, push the tree from Windows:

```bash
cd infra && tar -cf - ansible | ssh -i ~/.ssh/oracle_lifeos ubuntu@100.112.185.21 'rm -rf ~/oci-homelab/infra/ansible && tar -xf - -C ~/oci-homelab/infra'
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
