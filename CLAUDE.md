# oci-homelab

Infrastructure for timsurreal's Oracle Cloud Always Free servers (ap-batam-1): an edge VM and a private worker VM, built with Terraform and Ansible, aiming at a $0 platform with monitoring, deploys, bug bounty recon, public demos and a portfolio repo.

**Start here:** `docs/STATUS.md`. It covers the current state, what's running, the next steps and what's waiting on timsurreal. Update it at the end of every session.

- Goals and phases: `PRD.md`. Load the `oci-homelab` skill before any OCI action: it has the account facts, the $0 / no-terminate safety rules and the tool map.
- How-to (Ansible runs, retry timer, monitoring URLs): `docs/RUNBOOK.md`. Why things are the way they are: `docs/DECISIONS.md`. Resource OCIDs: `docs/inventory-2026-11.md`.
- MCP servers (`.mcp.json`): oci-compute, oci-networking, oci-monitoring, oci-usage, oci-cloud. Auth: `~/.oci/config` profile DEFAULT. They fail under API-key auth, so prefer the `oci` CLI.
- Folder is Syncthing-synced: follow `Projects/CLAUDE.md` (no in-place branch switches; tfstate, `.terraform/`, `.env` never committed).
