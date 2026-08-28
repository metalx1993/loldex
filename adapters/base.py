"""Adapter base contract.

Every source (GTFOBins, LOLBAS, LOLAD, ...) gets one adapter. An adapter's
only job is to turn upstream data into canonical entries that validate against
schema/schema.yaml. It does NOT invent techniques — it normalizes what the
upstream project already documents.

An adapter subclasses Adapter and implements `fetch()` and `normalize()`.
`run()` ties them together and writes YAML entries to data/entries/<platform>/.
"""

from __future__ import annotations
import dataclasses
import datetime as _dt
import pathlib
from typing import Any, Iterable

# Closed taxonomies mirrored from schema.yaml. Keep in sync (a test enforces it).
PHASES = {
    "initial-access", "execution", "persistence", "privilege-escalation",
    "defense-evasion", "credential-access", "discovery", "lateral-movement",
    "collection", "command-and-control", "exfiltration", "impact",
}
CAPABILITIES = {
    "shell", "command-execution", "reverse-shell", "bind-shell", "file-read",
    "file-write", "file-download", "file-upload", "library-load",
    "privilege-escalation", "persistence", "credential-dump",
    "credential-access", "defense-evasion", "data-exfiltration", "c2",
    "decode", "encode", "discovery", "lateral-movement", "kerberoast", "coerce",
}
PRIVILEGES = {
    "none", "user", "suid", "sudo", "capability", "admin", "system",
    "domain-user", "specific-right",
}
PLATFORMS = {"linux", "windows", "macos", "active-directory"}
TYPES = {"binary", "script", "library", "driver", "technique"}


# Keys that must NEVER appear inside source_data.<project>: they represent
# loldex INTERPRETATION, which belongs in `enrichment`, not in source-attributed
# data. Enforced by Entry._validate_source_data() and scripts/validate.py.
# `relationships` is reserved here now though relationships aren't implemented yet.
LOLDEX_INTERPRETIVE_KEYS = {
    "capabilities", "phases", "attack_techniques", "privilege_required",
    "detection", "mitigation", "notes", "enrichment", "relationships",
}


@dataclasses.dataclass
class EnrichedValue:
    """One enriched claim: a value + who produced it (provenance) + how sure
    we are (confidence). provenance.type distinguishes the four cases:
      upstream  — the source states it directly
      adapter   — deterministically mapped from source vocab by an adapter
      heuristic — guessed by an adapter heuristic (needs review)
      manual    — added/verified by a human
    confidence.level is orthogonal: low | medium | high | verified.
    """
    value: str
    provenance: dict          # {type, source?, adapter?, note?}
    confidence: dict          # {level}

    PROV_TYPES = {"upstream", "adapter", "heuristic", "manual"}
    CONF_LEVELS = {"low", "medium", "high", "verified"}

    def validate(self, ctx: str = "") -> None:
        assert self.value, f"{ctx}: enriched value empty"
        pt = self.provenance.get("type")
        assert pt in self.PROV_TYPES, f"{ctx}: bad provenance.type {pt!r}"
        cl = self.confidence.get("level")
        assert cl in self.CONF_LEVELS, f"{ctx}: bad confidence.level {cl!r}"

    def as_dict(self) -> dict:
        prov = {k: v for k, v in self.provenance.items() if v not in ("", None)}
        return {"value": self.value, "provenance": prov, "confidence": self.confidence}


@dataclasses.dataclass
class Entry:
    """One normalized loldex entry. Mirrors schema.yaml `entry` (v1).

    The enriched top-level fields (capabilities/phases/privilege_required/
    attack_techniques) are a PROJECTION of `enrichment`, emitted by
    adapters.projection. They are kept at top level for API/CLI/UI back-compat
    but are NOT the source of truth.

    Internal/external name mapping: the Python field `meta` is serialized to
    the YAML key `_meta` (a leading-underscore dataclass field breaks
    asdict()/init). Enforced by test_meta_serializes_as_underscore.
    """
    id: str
    type: str
    platform: str
    name: str
    phases: list[str]
    capabilities: list[str]
    privilege_required: str
    sources: list[dict]
    aliases: list[str] = dataclasses.field(default_factory=list)
    preconditions: list[str] = dataclasses.field(default_factory=list)
    attack_techniques: list[str] = dataclasses.field(default_factory=list)
    opsec: dict = dataclasses.field(default_factory=dict)
    commands: list[dict] = dataclasses.field(default_factory=list)
    technique_detail: dict = dataclasses.field(default_factory=dict)
    driver_detail: dict = dataclasses.field(default_factory=dict)
    references: list[str] = dataclasses.field(default_factory=list)
    tags: list[str] = dataclasses.field(default_factory=list)
    # --- v1 layers (optional in phase 1; legacy entries omit them) ---
    source_data: dict = dataclasses.field(default_factory=dict)
    enrichment: dict = dataclasses.field(default_factory=dict)
    meta: dict = dataclasses.field(default_factory=dict)   # serialized as "_meta"

    def validate(self) -> None:
        assert self.type in TYPES, f"{self.id}: bad type {self.type}"
        assert self.platform in PLATFORMS, f"{self.id}: bad platform {self.platform}"
        assert self.privilege_required in PRIVILEGES, f"{self.id}: bad privilege {self.privilege_required}"
        assert self.phases, f"{self.id}: phases empty"
        for p in self.phases:
            assert p in PHASES, f"{self.id}: bad phase {p}"
        for c in self.capabilities:
            assert c in CAPABILITIES, f"{self.id}: bad capability {c}"
        assert self.sources, f"{self.id}: sources empty (provenance is mandatory)"
        # --- new-layer checks: only run when the layers are present ---
        self._validate_source_data()
        self._validate_enrichment()

    def _validate_source_data(self) -> None:
        """source_data.<project>: source-specific only, structurally sound."""
        for project, block in self.source_data.items():
            leaked = LOLDEX_INTERPRETIVE_KEYS & set(block)
            assert not leaked, (
                f"{self.id}: source_data.{project} contains loldex-interpretive "
                f"keys {sorted(leaked)} — those belong in enrichment")
            assert isinstance(block.get("raw"), dict), \
                f"{self.id}: source_data.{project}.raw must be a dict"
            assert isinstance(block.get("upstream_url"), str) and block.get("upstream_url"), \
                f"{self.id}: source_data.{project}.upstream_url required (non-empty string)"

    def _validate_enrichment(self) -> None:
        for field_name, payload in self.enrichment.items():
            items = payload if isinstance(payload, list) else [payload]
            for raw in items:
                EnrichedValue(raw.get("value", ""), raw.get("provenance", {}),
                              raw.get("confidence", {})).validate(
                    ctx=f"{self.id}.enrichment.{field_name}")

    def to_dict(self) -> dict:
        d = dataclasses.asdict(self)
        d["_meta"] = d.pop("meta", {})   # internal `meta` -> external `_meta`
        # drop empty optionals for clean YAML
        return {k: v for k, v in d.items() if v not in ([], {}, "", None)}


class Adapter:
    #: unique adapter key, e.g. "gtfobins"
    source_name: str = ""
    #: which platform folder entries land in
    platform: str = ""
    #: upstream licence string — MUST be verified per source before shipping
    license: str = "UNKNOWN — verify before use"
    upstream_url: str = ""

    def fetch(self) -> Any:
        """Return raw upstream data (from a local clone, an API, or files)."""
        raise NotImplementedError

    def normalize(self, raw: Any) -> Iterable[Entry]:
        """Yield canonical Entry objects from the raw upstream data."""
        raise NotImplementedError

    def source_stub(self, upstream_version: str = "") -> dict:
        return {
            "project": self.source_name,
            "upstream_url": self.upstream_url,
            "license": self.license,
            "upstream_version": upstream_version,
            "last_synced": _dt.date.today().isoformat(),
        }

    def run(self, out_root: pathlib.Path) -> int:
        import yaml
        raw = self.fetch()
        out_dir = out_root / self.platform
        out_dir.mkdir(parents=True, exist_ok=True)
        n = 0
        for entry in self.normalize(raw):
            entry.validate()
            fname = entry.id.replace("/", "__") + ".yaml"
            with open(out_dir / fname, "w") as f:
                yaml.safe_dump(entry.to_dict(), f, sort_keys=False, width=100)
            n += 1
        print(f"[{self.source_name}] wrote {n} entries to {out_dir}")
        return n
