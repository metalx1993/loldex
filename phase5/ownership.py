"""Ownership — spec §8.

``canonical_prefix_owner`` (§8.1) and the total resolver (§8.3). Both are pure
functions of their inputs; neither repairs malformed evidence.
"""
from .canonical import code_point_sorted, nfc
from .vocabulary import PREFIX_OWNER, SOURCE_UNIVERSE, OwnerResolution

__all__ = ["INVALID_PREFIX", "raw_prefix", "canonical_prefix_owner", "resolve_owner"]

#: §8.1 sentinel — an id without ``/``, with an empty prefix, or with an
#: unmapped prefix is hard-invalid.
INVALID_PREFIX = "INVALID_PREFIX"


def raw_prefix(entry_id: str) -> str:
    """Substring before the first ``/``; ``""`` when there is no ``/`` (§8.1)."""
    text = nfc(entry_id)
    head, sep, _ = text.partition("/")
    return head if sep else ""


def canonical_prefix_owner(entry_id: str) -> str:
    """§8.1 — map an entry id's raw prefix to its canonical owner.

    Returns :data:`INVALID_PREFIX` when the prefix is absent, empty, or not
    exactly a ``PREFIX_OWNER`` key. Case-sensitive; no folding.
    """
    raw = raw_prefix(entry_id)
    if not raw or raw not in PREFIX_OWNER:
        return INVALID_PREFIX
    return PREFIX_OWNER[raw]


def resolve_owner(entry_id: str, evidence: dict):
    """§8.3 total resolver.

    ``evidence`` is the §8.2 shape
    ``{source_data_projects: [...], declared_sources: [...], id_prefix: str}``.

    Returns ``(OwnerResolution.RESOLVED, frozenset(owners))`` or
    ``(OwnerResolution.AMBIGUOUS, None)`` or
    ``(OwnerResolution.HARD_INVALID, None)``.

    The prefix owner is a *membership constraint*, never a competing singleton.
    """
    owner = canonical_prefix_owner(entry_id)
    if owner == INVALID_PREFIX:
        return OwnerResolution.HARD_INVALID, None

    if not isinstance(evidence, dict):
        return OwnerResolution.HARD_INVALID, None
    for key in ("source_data_projects", "declared_sources", "id_prefix"):
        if key not in evidence:
            return OwnerResolution.HARD_INVALID, None

    if nfc(str(evidence["id_prefix"])) != raw_prefix(entry_id):
        return OwnerResolution.HARD_INVALID, None

    projects = evidence["source_data_projects"]
    declared = evidence["declared_sources"]
    for array in (projects, declared):
        if not isinstance(array, list):
            return OwnerResolution.HARD_INVALID, None
        if any(not isinstance(v, str) or nfc(v) not in SOURCE_UNIVERSE for v in array):
            return OwnerResolution.HARD_INVALID, None
        # §8.2: arrays must already be canonical (sorted + de-duplicated).
        if [nfc(v) for v in array] != code_point_sorted(array, dedupe=True):
            return OwnerResolution.HARD_INVALID, None

    sd = {nfc(v) for v in projects}
    ds = {nfc(v) for v in declared}

    if sd and ds and sd != ds:
        return OwnerResolution.AMBIGUOUS, None

    explicit = sd if sd else (ds if ds else {owner})
    if owner not in explicit:
        return OwnerResolution.AMBIGUOUS, None
    return OwnerResolution.RESOLVED, frozenset(explicit)
