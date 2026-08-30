"""Normative vocabulary — spec §4, §8.1, §9.1, §10, §11.3, §15.

Serialized values are the exact strings from the frozen specification. No
aliases: one normative value has exactly one serialized spelling.
"""
__all__ = [
    "SOURCE_UNIVERSE",
    "PREFIX_OWNER",
    "IDENTITY_MODE",
    "IdentityMode",
    "Classification",
    "AggregateClass",
    "SourceStatus",
    "OwnerResolution",
    "EvidenceTuple",
    "CORE_STATE_VERSION",
    "REPORT_VERSION",
    "STALE_THRESHOLD",
]

#: §4 — the five sources; every observation carries exactly one result per member.
SOURCE_UNIVERSE = frozenset({"GTFOBins", "LOLAD", "LOLBAS", "LOLDrivers", "WADComs"})

#: §8.1 — exact, case-sensitive; no folding, aliasing or locale.
PREFIX_OWNER = {
    "gtfobins": "GTFOBins",
    "lolad": "LOLAD",
    "lolbas": "LOLBAS",
    "loldrivers": "LOLDrivers",
    "wadcoms": "WADComs",
}


class IdentityMode:
    """§9.1 — static per-source identity mode."""

    STABLE = "STABLE"
    NONE = "NONE"


#: §9.1 — STABLE sources carry a non-null identity of exactly the stated kind;
#: NONE sources MUST emit ``upstream_identity: null``.
IDENTITY_MODE = {
    "GTFOBins": (IdentityMode.STABLE, "gtfobins_natural_key"),
    "LOLDrivers": (IdentityMode.STABLE, "loldrivers_id"),
    "LOLAD": (IdentityMode.NONE, None),
    "LOLBAS": (IdentityMode.NONE, None),
    "WADComs": (IdentityMode.NONE, None),
}


class Classification:
    """§11.3 — persisted freshness classification. No terminal STALE in CORE."""

    ACTIVE = "ACTIVE"
    NOT_OBSERVED = "NOT_OBSERVED"
    STALE_CANDIDATE = "STALE_CANDIDATE"


class AggregateClass:
    """§10 — per-step aggregate outcome (not persisted as classification)."""

    PRESENT = "PRESENT"
    QUALIFYING_ABSENCE = "QUALIFYING_ABSENCE"
    HOLD = "HOLD"


class SourceStatus:
    """§6/§7 — per-source health status."""

    OK = "ok"
    PARTIAL = "partial"
    FAILED = "failed"
    UNKNOWN = "unknown"


class OwnerResolution:
    """§8.3 — total resolver outcomes."""

    RESOLVED = "RESOLVED"
    AMBIGUOUS = "AMBIGUOUS"
    HARD_INVALID = "HARD_INVALID"


class EvidenceTuple:
    """§11.5 — the four legal persisted source-evidence tuple names."""

    EMPTY = "EMPTY"
    STABLE_RELIABLE = "STABLE_RELIABLE"
    UNKEYED_RELIABLE = "UNKEYED_RELIABLE"


CORE_STATE_VERSION = 2
REPORT_VERSION = 1
#: §10 — qualifying absences required before STALE_CANDIDATE.
STALE_THRESHOLD = 3
