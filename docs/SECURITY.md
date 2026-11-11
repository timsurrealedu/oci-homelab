# Security review

## 2026-11-11: demos, Caddy and the edge host

Scope: the three demos (`apps/lg`, `apps/trading`, `apps/trace`), Caddy, the host firewall and services on the edge, the CI workflow. Method: code review plus live probes from the edge, following the `bug-hunter` approach and the `web2-vuln-classes` checklist (SSRF and its IP-encoding bypasses, rate-limit bypass, header/CRLF injection, path traversal, DOM XSS, CORS, error disclosure, cloud and infra exposure, CI/CD).

### Findings and fixes

| # | Severity | Finding | Fix |
|---|---|---|---|
| 1 | Low | Looking glass accepted `64:ff9b::7f00:1` (NAT64 prefix wrapping 127.0.0.1): Python marks it global. Not exploitable here (no IPv6 route), but a filter gap. | Targets must resolve to IPv4 only; tests cover NAT64, 6to4, IPv4-mapped, decimal and hex forms. |
| 2 | Medium | Trading backend ran with host networking, so a compromise of it could reach every localhost service (Caddy admin API, Prometheus, Alertmanager, Syncthing GUI). | Bridge network joined to freqtrade's network; reaches only `http://freqtrade:8080`. Verified: Caddy admin refuses connections from it. |
| 3 | Low | Demo sites sent no security headers; pages used inline scripts and styles, which rules out a strict CSP. | Pages moved to static files served by Caddy (`apps/*/public`, shared `apps/_ui`); strict CSP (`default-src 'self'`, `frame-ancestors 'none'`, no inline), `nosniff`, Referrer-Policy, Permissions-Policy, COOP/CORP; `Server` header removed. |
| 4 | Info | `rpcbind` listened on 0.0.0.0:111 (blocked by the host firewall, but an unneeded service). | Stopped and masked by the Ansible `base` role. |

### Checked and fine

- SSRF payloads: `127.1`, `2130706433`, `0177.0.0.1`, `0x7f.0.0.1`, `::ffff:127.0.0.1`, `[::1]`, `*.nip.io`, `localtest.me`, metadata IP and names, full-width dots: all rejected. Tools receive the resolved IP, never user text, so no flag injection or DNS rebinding.
- Rate limit can't be bypassed with a spoofed `X-Forwarded-For`: Caddy replaces it.
- No CRLF/header injection through query parameters; no CORS headers, so no reflected origins.
- Path traversal (`..%2f`, `%2e%2e`, `--path-as-is`) returns 404; app source and Dockerfiles aren't reachable.
- Only GET is implemented; errors don't leak versions (`sys_version` blanked).
- DOM: all dynamic text goes through `textContent`/`createTextNode`; no `innerHTML`.
- Containers: read-only filesystems, all capabilities dropped (looking glass keeps only `NET_RAW`), `no-new-privileges`, memory and PID limits; trading and trace run as `nobody`.
- Host firewall: INPUT ends in REJECT; only SSH is public; containers can reach only SSH on the host.
- CI: `pull_request` (not `pull_request_target`), read-only token, no secrets.

### Accepted / follow-ups

- Prometheus and Alertmanager UIs have no login; they're tailnet-only. Applying the Tailscale ACL (`infra/tailscale/policy.hujson`, timsurreal's step) limits who on the tailnet reaches them.
- smartStudent's backend (`0.0.0.0:3001`) and readChinese (`*:3108`) bind all interfaces; the host firewall blocks them. Binding them to 127.0.0.1 is a change in those apps.
- GitHub Actions are pinned by tag, not commit SHA. Pin by SHA before accepting outside contributions.
- When demos go public: strip `Tailscale-User-*` request headers on public sites (only cosmetic for the tracer today), and add `trusted_proxies` if Cloudflare proxying is turned on.

### 2026-11-11 update

- Ubuntu 20.04 (past standard support) upgraded in place to 24.04 LTS (ADR-011). During the upgrade the firewall's boot file was replaced; caught before reboot and re-rendered (see RUNBOOK). Public exposure verified after each reboot: only SSH answers.
- Public mode strips `Tailscale-User-*` / `Tailscale-Headers-Info` request headers on public sites, and the public status site proxies only Uptime Kuma's status-page paths.
- Nothing listens on port 80 until a public site exists (smartStudent moved to `127.0.0.1:8097`).

### Publishing the repo (2026-11-11)

- Full history scanned with gitleaks before the first push; CI rescans every push.
- Personal email addresses removed from all history (commit author and the Tailscale policy). Before applying `infra/tailscale/policy.hujson`, replace `you@example.com` with the real login.
- Deliberately left in: OCIDs, the edge's public IP and the tailnet hostname. OCIDs are identifiers, not credentials (API calls still need the private key); the IP answers only key-based SSH; tailnet hostnames already appear in certificate transparency logs because Tailscale Serve uses public certificates.
