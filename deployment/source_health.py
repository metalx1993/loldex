"""Fail-closed source health and a staging bridge over the same verified bytes.

This is publication preparation, not a CORE transition or identity migration.
It never fetches, updates the live corpus, or invokes Adapter.run().
"""
from __future__ import annotations

from dataclasses import dataclass
from collections import Counter
from pathlib import Path, PurePosixPath
import shutil

import yaml

from adapters.base import CAPABILITIES, PHASES, PLATFORMS, PRIVILEGES, TYPES, EnrichedValue, LOLDEX_INTERPRETIVE_KEYS
from adapters import projection
from adapters.gtfobins import GTFOBinsAdapter
from adapters.lolbas import LOLBASAdapter
from adapters.loldrivers import LOLDriversAdapter
from adapters.lolad import LOLADAdapter
from adapters.wadcoms import WADComsAdapter
from phase5.acquisition import acquire, AcquisitionFailed
from phase5.canonical import canonical_bytes, nfc
from phase5.observation import adapter_result, source_failure
from phase5.material import material_fingerprint
from phase5.vocabulary import SOURCE_UNIVERSE, PREFIX_OWNER

ADAPTERS = {"GTFOBins": GTFOBinsAdapter, "LOLBAS": LOLBASAdapter,
            "LOLDrivers": LOLDriversAdapter, "LOLAD": LOLADAdapter,
            "WADComs": WADComsAdapter}
ROOT = Path(__file__).resolve().parent.parent


class SourceHealthError(ValueError):
    def __init__(self, message, results=()):
        super().__init__(message)
        self.results = list(results)


def check_source_health(repositories, *, profile="d1"):
    if profile not in ("d1", "publication-v2"):
        raise SourceHealthError("unknown publication profile")
    """Require all five complete sources, returning immutable bundles + results.

    repositories is Source -> (local Git repository, revision). Unknown sources
    are configuration errors. Every acquisition failure is represented before
    aggregate rejection; no healthy subset can authorize publication.
    """
    if set(repositories) - SOURCE_UNIVERSE:
        raise SourceHealthError("unknown source in publication input")
    bundles, results = {}, []
    for source in sorted(SOURCE_UNIVERSE):
        if source not in repositories:
            results.append(source_failure(source, "NOT_RUN"))
            continue
        repo, revision = repositories[source]
        try:
            bundle = acquire(repo, source, revision)
        except AcquisitionFailed:
            results.append(source_failure(source))
            continue
        try:
            if profile == "publication-v2":
                from deployment.publication import publication_result
                result, _ = publication_result(bundle, _legacy_raw(bundle, profile=profile), ADAPTERS[source]())
            else:
                result = adapter_result(bundle)
        except (ValueError, TypeError, KeyError) as exc:
            result = adapter_result(bundle)
            result.update(status="failed", primary_reason="MALFORMED_RECORD", emitted_entries={})
            result["publication_error"] = str(exc)
        bundles[source] = bundle
        results.append(result)
    if any(result["status"] != "ok" for result in results):
        raise SourceHealthError("publication requires five verified healthy sources", results)
    if any(result["unmapped"] for result in results):
        raise SourceHealthError("publication requires zero source diagnostics; review warnings before publication", results)
    return bundles, results


@dataclass(frozen=True)
class MemoryPath:
    """Minimal read-only path interface needed by baseline normalize()."""
    relative: str
    content: bytes

    @property
    def name(self):
        return PurePosixPath(self.relative).name

    @property
    def stem(self):
        return PurePosixPath(self.relative).stem

    def read_text(self, encoding="utf-8", errors="strict"):
        return self.content.decode(encoding, errors)


def _legacy_raw(bundle, *, profile="d1"):
    paths = [MemoryPath(file.name, file.content) for file in bundle.files]
    if bundle.source == "LOLAD":
        return {"rev": bundle.revision, "html": paths[0].read_text(), "profile": profile}
    if bundle.source == "LOLBAS":
        return {"rev": bundle.revision, "profile": profile,
                "files": [(PurePosixPath(path.relative).parts[0], path) for path in paths]}
    return {"rev": bundle.revision, "files": paths, "profile": profile}


def _validate_public_entry(entry, source, revision):
    """Explicit checks remain effective under python -O (legacy uses assert)."""
    if not isinstance(entry.id, str) or not entry.id or not isinstance(entry.name, str):
        raise SourceHealthError("invalid public entry identity/name")
    prefix, sep, _ = entry.id.partition("/")
    if not sep or PREFIX_OWNER.get(prefix) != source:
        raise SourceHealthError("public entry prefix/source mismatch")
    if entry.platform not in PLATFORMS or entry.type not in TYPES:
        raise SourceHealthError("invalid public platform/type")
    if entry.privilege_required not in PRIVILEGES or not entry.phases:
        raise SourceHealthError("invalid public privilege/empty phases")
    if any(value not in PHASES for value in entry.phases) or any(value not in CAPABILITIES for value in entry.capabilities):
        raise SourceHealthError("invalid public taxonomy")
    if not entry.sources or {s.get("project") for s in entry.sources} != {source}:
        raise SourceHealthError("public source declaration mismatch")
    if set(entry.source_data) != {source}:
        raise SourceHealthError("public raw source mismatch")
    if any(item.get("upstream_version") != revision for item in entry.sources):
        raise SourceHealthError("public source revision does not match verified acquisition")
    if set(entry.meta) != {"schema_version", "generated_by", "projected_at", "source_hashes"} or entry.meta.get("schema_version") != 1 or entry.meta.get("generated_by") != projection.GENERATED_BY:
        raise SourceHealthError("invalid public projection metadata contract")
    if entry.meta["source_hashes"] != projection.compute_source_hashes(entry.source_data):
        raise SourceHealthError("public raw source hashes do not match source evidence")
    for block in entry.source_data.values():
        if LOLDEX_INTERPRETIVE_KEYS & set(block):
            raise SourceHealthError("interpretive fields leaked into public source evidence")
        if block.get("upstream_version") != revision:
            raise SourceHealthError("raw source revision does not match verified acquisition")
        if not isinstance(block.get("raw"), dict) or not isinstance(block.get("upstream_url"), str) or not block["upstream_url"]:
            raise SourceHealthError("invalid public source evidence")
    for payload in entry.enrichment.values():
        for claim in payload if isinstance(payload, list) else [payload]:
            if not isinstance(claim, dict) or not isinstance(claim.get("value"), str) or not claim["value"]:
                raise SourceHealthError("invalid public claim value")
            if claim.get("provenance", {}).get("type") not in EnrichedValue.PROV_TYPES or claim.get("confidence", {}).get("level") not in EnrichedValue.CONF_LEVELS:
                raise SourceHealthError("invalid public per-claim provenance/confidence")
            if claim["provenance"].get("source") != source or claim["provenance"].get("adapter") != source.lower() + "@" + revision:
                raise SourceHealthError("public claim provenance does not match verified source revision")
            if claim["provenance"]["type"] == "heuristic" and (not claim["provenance"].get("note") or claim["confidence"]["level"] != "low"):
                raise SourceHealthError("heuristic public claim needs its explanatory note and low confidence")
    for field, value in projection.build(entry.enrichment).items():
        if getattr(entry, field) != value:
            raise SourceHealthError("public fields diverge from enrichment projection")
    entry.validate()


def prepare_verified_sync(repositories, output, *, profile="d1"):
    """Prepare a NEW staging corpus. Never replace/delete an existing corpus.

    No filesystem output is created until all source health, adapter emissions,
    global public IDs, filename collisions and public entries have passed.
    The output is a candidate only: callers must run full schema/graph/site
    validation, review retained historical entries and use their publication gate.
    """
    output = Path(output)
    resolved = output.resolve()
    live = (ROOT / "data").resolve()
    if resolved == live or live in resolved.parents:
        raise SourceHealthError("staging output cannot be inside the live data tree")
    if output.exists() or output.is_symlink():
        raise SourceHealthError("staging output must not already exist")
    bundles, results = (check_source_health(repositories) if profile == "d1" else
                        check_source_health(repositories, profile=profile))
    records, ids, filenames = [], set(), set()
    results_by_source = {result["source"]: result for result in results}
    for source in sorted(SOURCE_UNIVERSE):
        try:
            adapter = ADAPTERS[source]()
            raw = _legacy_raw(bundles[source], profile=profile)
            normalize = (getattr(adapter, "normalize_complete") if profile == "publication-v2" and source in ("LOLDrivers", "WADComs") else adapter.normalize)
            entries = list(normalize(raw))
            expected = Counter(value["material_fingerprint"] for value in results_by_source[source]["emitted_entries"].values())
            actual = Counter()
            actual_ids = {}
            actual_evidence = {}
            for entry in entries:
                _validate_public_entry(entry, source, bundles[source].revision)
                fingerprint = material_fingerprint(entry.to_dict())
                actual[fingerprint] += 1
                actual_ids[entry.id] = fingerprint
                if profile == "publication-v2":
                    from adapters.complete_data import entry_evidence_hash
                    actual_evidence[entry.id] = entry_evidence_hash(entry)
                identity = nfc(entry.id)
                if profile == "publication-v2":
                    import hashlib
                    storage_name = entry.id.partition('/')[0] + '__' + hashlib.sha256(entry.id.encode('utf-8')).hexdigest()
                else:
                    storage_name = entry.id.replace("/", "__")
                filename = nfc(entry.platform + "/" + storage_name + ".yaml")
                basename = filename.split("/", 1)[1]
                if any(ord(char) < 32 or ord(char) == 127 for char in basename) or len(basename.encode("utf-8")) > 255:
                    raise SourceHealthError("public filename cannot be safely staged")
                if identity in ids or filename in filenames:
                    raise SourceHealthError("public ID or filename collision; no winner may be published")
                ids.add(identity)
                filenames.add(filename)
                records.append((filename, entry.to_dict()))
            if profile == "publication-v2":
                expected_ids = {identity: value["material_fingerprint"] for identity, value in results_by_source[source]["emitted_entries"].items()}
                expected_evidence = {identity: value["public_entry_evidence"] for identity, value in results_by_source[source]["emitted_entries"].items()}
                if actual_evidence != expected_evidence:
                    raise SourceHealthError("D2 staged source evidence differs from healthy preflight")
                if actual_ids != expected_ids:
                    raise SourceHealthError("D2 staged identities differ from healthy source emissions")
            if actual != expected:
                raise SourceHealthError("public material emissions differ from verified CORE derivation; review compatibility before publication")
        except SourceHealthError:
            raise
        except Exception as exc:
            raise SourceHealthError("verified source could not produce a valid public candidate") from exc
    if not records:
        raise SourceHealthError("empty public candidate")
    # Every operation below is against a newly and exclusively created staging
    # directory. A completion manifest is written last; partial output is removed.
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir()
    try:
        for filename, data in sorted(records):
            path = output / "data" / "entries" / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("x", encoding="utf-8") as stream:
                yaml.safe_dump(data, stream, sort_keys=False, allow_unicode=True, width=100)
        report = {"version": 1, "complete": True, "candidate_entries": len(records),
                  "identity_policy": "legacy-public-projection-no-core-id-migration" if profile == "d1" else "publication-v2-explicit-D2",
                  "publication_profile": profile,
                  "sources": results}
        (output / "source-health.json").write_bytes(canonical_bytes(report) + b"\n")
    except Exception:
        shutil.rmtree(output)
        raise
    return output
