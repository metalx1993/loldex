# Phase 4 — Technique intelligence views and pinned ATT&CK registry

Status: implemented under the user's authorization to complete Phase 4.

## Data and evidence boundaries

`site/techniques.json` aggregates the validated Phase 3 graph and joins display metadata
from the checked-in `data/registry/enterprise-attack.json` registry. It never changes entries
or infers new entry relations. Each technique keeps associated entry IDs, entry platforms,
declared/source-data sources, entry capabilities/phases, and exact supporting `implements`
edges. `confidence_counts` counts **evidence edges**, not tool confidence, verified
techniques, or independent confirmations.

Capabilities and `phases` are contextual attributes of associated entries, **not MITRE
technique properties**. The separate `tactics` field is official registry metadata.
Registry tactic membership is never copied into entry enrichment or graph edges.

## Versioned official metadata

The registry derives from the official MITRE Enterprise ATT&CK **20.1** STIX snapshot:

- Repository commit: `a8db2f52eb933c9c99060c123e088b3326d3a607`.
- [Pinned official source](https://raw.githubusercontent.com/mitre-attack/attack-stix-data/a8db2f52eb933c9c99060c123e088b3326d3a607/enterprise-attack/enterprise-attack-20.1.json).
- Original input: 55,277,605 bytes.
- Original SHA-256: `539a843a7b53ed9749740b2123dddae3726b1a4831841c32aca740b011b910b5`.
- 867 attack-pattern records, including retained revoked/deprecated records.
- License and required designation: `data/registry/LICENSE-MITRE.txt`, also copied
  to `site/registry-license.txt` beside the distributed technique metadata.

The offline importer requires an official repository HTTPS URL pinned to a full Git
commit and the declared snapshot version. It also requires exactly one
`x-mitre-collection`, with name `Enterprise ATT&CK` and `x_mitre_version` equal
to the declared version; a matching URL alone cannot relabel a different collection.
It validates the original input hash when
`--expected-sha256` is supplied, unique STIX/external IDs, Enterprise domain, lifecycle
booleans, and technique URLs corresponding to external IDs. No network requests occur
in the importer or site build. Original descriptions and tactic names are preserved
as data, including Markdown; the browser must render them safely as text.

The reduced registry stores official name, description, URL, tactics, STIX ID,
modification timestamp, object version, revoked/deprecated flags, snapshot version,
source URL and original-file SHA-256. A checksum over the canonical reduced payload
is checked every time the registry is loaded or consumed. This detects accidental or
unacknowledged local changes; it is not a digital signature or independent proof of
MITRE authorship. Original-file digest identity and official source provenance remain
explicit.

## Interpretation and API

`registry_status:"verified"` means **the identifier matches this pinned registry**.
It does not mean that LOLDEX independently verified the behavior, that MITRE endorses
the entry, or that an entry's claim has `confidence:verified`. Existing claim evidence
and confidence remain unchanged. Revoked/deprecated records remain visible and are
labeled; they are not silently remapped or removed. Unknown syntactically valid IDs
remain `registry_status:"unverified"` with null display/lifecycle metadata and no
invented names or tactics.

`build_techniques(graph, registry=None)` and `validate_techniques(data, graph, registry=None)`
are pure functions. The CLI loads the checked-in registry by default. An identifier-only
build requires explicit `--without-registry`; no silent fallback hides a missing or
corrupted default registry. Output top-level `registry` contains the source/version/hash
metadata and reduced checksum; per-technique fields include `name`, `description`, `url`,
`tactics`, `revoked`, `deprecated`, `stix_id`, and `modified` separately from evidence.

Output is deterministic, sorted by technique ID and entry ID, with no build timestamps.
The validator recomputes aggregation and metadata joins and rejects any divergence,
including unsupported entries, evidence, confidence totals, names, lifecycle or tactics.

## Reproduction and tests

```sh
python -m scripts.import_attack_registry work/stix.json --version 20.1 \
  --source-url https://raw.githubusercontent.com/mitre-attack/attack-stix-data/a8db2f52eb933c9c99060c123e088b3326d3a607/enterprise-attack/enterprise-attack-20.1.json \
  --expected-sha256 sha256:539a843a7b53ed9749740b2123dddae3726b1a4831841c32aca740b011b910b5
python -m scripts.build_graph
python -m scripts.build_techniques
```

All 64 syntactically valid technique identifiers observed in the checked-in LOLDEX
corpus match the registry. Snapshot counts describe evidence, never future invariants.
Tests cover modified registry bytes, wrong snapshot hashes, duplicate JSON keys,
external/STIX identity collisions, malicious URLs, branch refs instead of pinned commits,
wrong domain/version, revoked/deprecated labeling, unknown IDs, no confidence escalation,
and strict separation between registry tactics and entry phases.
