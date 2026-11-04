# oci-homelab

Infrastructure for Tim's Oracle Cloud Always Free servers (ap-batam-1).

- Goals and phases: `PRD.md`. Load the `oci-homelab` skill before any OCI action: it has the account facts, the $0 / no-terminate safety rules and the tool map.
- MCP servers (`.mcp.json`): oci-compute, oci-networking, oci-monitoring, oci-usage, oci-cloud. Auth: `~/.oci/config` profile DEFAULT.
- Folder is Syncthing-synced: follow `Projects/CLAUDE.md` (no in-place branch switches; tfstate, `.terraform/`, `.env` never committed).
