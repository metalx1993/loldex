"""Phase-2 enrichment helpers (isolated — phase 1 stays frozen at efe2ac2).

These build the `enrichment` block with PER-CLAIM provenance/confidence, per the
phase-2 contract:
  - each enriched_value carries its OWN provenance.type and confidence.level;
  - an upstream-derived claim keeps its real (high) confidence even when the
    same adapter also emits heuristic claims — confidences are not lowered
    across the board;
  - any value introduced because upstream does NOT state it (a rule / default /
    keyword guess) is provenance.type="heuristic", confidence.level="low", with
    a provenance.note explaining the rule.

Nothing here touches adapters.projection, the v1 schema, build()/apply(), the
meaning of source_data, or data.json. It only assembles enrichment dicts that
projection.build() already knows how to consume.
"""

from __future__ import annotations


def enriched(value: str, *, ptype: str, source: str, adapter: str,
             confidence: str, note: str | None = None) -> dict:
    """One enriched_value with explicit per-claim provenance + confidence.

    ptype ∈ {upstream, adapter, heuristic, manual}
    confidence ∈ {low, medium, high, verified}
    """
    prov = {"type": ptype, "source": source, "adapter": adapter}
    if note:
        prov["note"] = note
    return {"value": value, "provenance": prov, "confidence": {"level": confidence}}


def claims(values, *, ptype: str, source: str, adapter: str,
           confidence: str, note: str | None = None) -> list[dict]:
    """A list of enriched_values sharing one provenance/confidence (deduped,
    order preserved)."""
    out, seen = [], set()
    for v in values:
        if v and v not in seen:
            seen.add(v)
            out.append(enriched(v, ptype=ptype, source=source, adapter=adapter,
                                 confidence=confidence, note=note))
    return out


def assemble(*, capabilities=None, phases=None, attack_techniques=None,
             privilege=None) -> dict:
    """Assemble an enrichment dict from already-built enriched_value lists /
    single value. Each argument is the OUTPUT of claims()/enriched(), so
    provenance is decided per claim by the caller — never here.

    Only non-empty fields are included, so a field the source can't support is
    simply absent (projection then yields the empty projection for it).
    """
    enr: dict = {}
    if capabilities:
        enr["capabilities"] = capabilities
    if phases:
        enr["phases"] = phases
    if attack_techniques:
        enr["attack_techniques"] = attack_techniques
    if privilege is not None:
        enr["privilege_required"] = privilege   # a single enriched_value dict
    return enr


def source_block(*, project_raw: dict, upstream_url: str,
                 upstream_version: str = "", last_synced: str = "") -> dict:
    """One source_data.<project> block. `project_raw` is upstream payload in the
    source's own vocabulary — NO loldex interpretation goes here."""
    block = {"raw": project_raw, "upstream_url": upstream_url}
    if upstream_version:
        block["upstream_version"] = upstream_version
    if last_synced:
        block["last_synced"] = last_synced
    return block
