"""Projection builder — the single direction of truth.

    source_data + enrichment  ->  build()  ->  enriched top-level fields

CONTRACT
  build(enrichment)  PURE + idempotent. No side effects, no clock, no I/O.
                     Input MUST be already-validated enrichment (Entry.validate
                     enforces enriched_value well-formedness upstream of here).
  apply(entry)       MUTATIVE. Writes the projection onto entry's top-level
                     fields AND stamps projection metadata (projected_at,
                     source_hashes). Not pure by design — documented below.

Adapters never author capabilities/phases/privilege_required/attack_techniques.
They build source_data + enrichment and call make_entry(); top-level fields are
DERIVED, so divergence is structurally impossible.

PHASE-1 SCOPE (explicit): the projection OWNS exactly four fields —
capabilities, phases, privilege_required, attack_techniques. Structural fields
(sources, commands, references, aliases, tags, *_detail) are source-attributable
passthrough and are NOT projected. In a later phase, `sources[]` MAY become a
projection derived from source_data.<project>; deliberately out of scope now.
"""

from __future__ import annotations
import datetime as _dt
import hashlib
import json

# top-level fields the projection OWNS (derived from enrichment)
_LIST_FIELDS = ("capabilities", "phases", "attack_techniques")
_SINGLE_FIELD = "privilege_required"


def _values(enrichment: dict, field: str) -> list[str]:
    """Ordered, de-duplicated values for a list-valued enriched field.
    Assumes enrichment already validated (each item has a 'value')."""
    payload = enrichment.get(field, [])
    if isinstance(payload, dict):
        payload = [payload]
    out, seen = [], set()
    for ev in payload:
        v = ev["value"]
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def build(enrichment: dict) -> dict:
    """PURE + idempotent: validated enrichment -> owned top-level fields.

    Always returns ALL owned keys (empty when absent) so callers can assign the
    complete projection without leaving stale values behind. No clock, no
    hashing, no mutation.
    """
    proj: dict = {f: _values(enrichment, f) for f in _LIST_FIELDS}
    pr = enrichment.get(_SINGLE_FIELD)
    if pr:
        proj[_SINGLE_FIELD] = pr["value"] if isinstance(pr, dict) else pr[0]["value"]
    else:
        proj[_SINGLE_FIELD] = ""
    return proj


def _iso(on) -> str:
    """Coerce a date | ISO-string | None into an ISO date string."""
    if on is None:
        return _dt.date.today().isoformat()
    if isinstance(on, str):
        return on
    return on.isoformat()


def project_metadata(source_data: dict, *, on=None) -> dict:
    """Projection metadata (impure input: the date). Separated from build()
    so the pure projection never carries a clock. `on` accepts a date, an ISO
    string, or None (today)."""
    return {
        "projected_at": _iso(on),
        "source_hashes": compute_source_hashes(source_data),
    }


def apply(entry, *, on=None):
    """MUTATIVE. Set entry's owned top-level fields to EXACTLY the projection,
    then stamp projection metadata.

    Assigns the COMPLETE projection (including empties) so a field removed from
    enrichment is cleared from the top-level — no stale survivors. Idempotent in
    VALUES (build is pure); `projected_at` reflects the run date and is not
    value-idempotent across days (pin `on=` for byte-stable output). Legacy
    entries (no enrichment) are left untouched.
    """
    if not entry.enrichment:
        return entry
    proj = build(entry.enrichment)
    for f in _LIST_FIELDS:
        setattr(entry, f, proj.get(f, []))          # always full projection
    entry.privilege_required = proj.get(_SINGLE_FIELD, "")
    entry.meta.setdefault("schema_version", 1)
    entry.meta.update(project_metadata(entry.source_data, on=on))
    return entry


def make_entry(*, source_data: dict, enrichment: dict,
               on=None, **identity_and_structural):
    """Single sanctioned constructor for layered entries. Caller does NOT pass
    capabilities/phases/privilege_required/attack_techniques — they are derived,
    so top-level == build(enrichment) at construction time."""
    from .base import Entry            # local import avoids cycle
    proj = build(enrichment)
    entry = Entry(
        source_data=source_data, enrichment=enrichment,
        capabilities=proj["capabilities"], phases=proj["phases"],
        attack_techniques=proj["attack_techniques"],
        privilege_required=proj[_SINGLE_FIELD],
        **identity_and_structural,
    )
    entry.meta["schema_version"] = 1
    entry.meta.setdefault("model", "layered")     # tracks migrated adapters
    entry.meta.update(project_metadata(source_data, on=on))
    return entry


# --- canonical, per-source hashing (stale detection) ----------------------
def canonical_json(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def source_hash(source_block: dict) -> str:
    """sha256 over UPSTREAM CONTENT only: raw (+ upstream_version). Excludes
    last_synced (our fetch metadata) so the hash changes iff source content
    changes — the basis for real change detection."""
    content = {"raw": source_block.get("raw", {})}
    if source_block.get("upstream_version"):
        content["upstream_version"] = source_block["upstream_version"]
    return "sha256:" + hashlib.sha256(canonical_json(content).encode("utf-8")).hexdigest()


def compute_source_hashes(source_data: dict) -> dict:
    return {proj: source_hash(block) for proj, block in source_data.items()}
