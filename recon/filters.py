"""Stage 1: a cheap, deterministic shortlist filter over HackerOne's public program
list (arkadiyt/bounty-targets-data, data/hackerone_data.json). No network, no policy
text -- just the kind of thing that saves you looking at obviously-not-worth-it
programs by hand.

This is a shortlist step, not a scan-authorization step. Everything that passes
still gets pinged to Telegram for you to read the actual policy and tap Approve
(scout.py) before a scope file exists or anything is scanned -- see recon/README.md
for why that tap, not this filter, is what satisfies "agents never pick targets".
"""

DEFAULT_CONFIG = {
    "min_response_efficiency": 50,   # percent; skip programs with a poor track record of responding
    "require_bounties": True,        # skip VDP-only (no-pay) programs
    "min_broad_scope_assets": 1,     # at least this many wildcard/URL assets eligible for bounty
}


def broad_scope_assets(program: dict) -> list[dict]:
    """In-scope WILDCARD/URL assets that actually pay a bounty -- the kind of
    scope a recon pipeline can usefully point subfinder/httpx/nuclei at, as
    opposed to a single SOURCE_CODE or APPLE_STORE_APP_ID entry."""
    return [
        a for a in program.get("targets", {}).get("in_scope", [])
        if a.get("asset_type") in ("WILDCARD", "URL") and a.get("eligible_for_bounty")
    ]


def passes_structural_filter(program: dict, config: dict = DEFAULT_CONFIG) -> tuple[bool, list[str]]:
    """Pure function: one hackerone_data.json entry in, (passes, reasons) out.
    `reasons` is always populated when passes is False, for the skip log."""
    reasons = []

    if program.get("submission_state") != "open":
        reasons.append("not accepting submissions")

    if config.get("require_bounties", True) and not program.get("offers_bounties"):
        reasons.append("no bounties offered (VDP-only)")

    eff = program.get("response_efficiency_percentage")
    min_eff = config.get("min_response_efficiency", 0)
    if eff is not None and eff < min_eff:
        reasons.append(f"low response efficiency ({eff}% < {min_eff}%)")

    broad = broad_scope_assets(program)
    min_broad = config.get("min_broad_scope_assets", 1)
    if len(broad) < min_broad:
        reasons.append("no broad (wildcard/URL) bounty-eligible scope")

    return (not reasons), reasons
