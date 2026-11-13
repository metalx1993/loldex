# Phase 3 — Evidence-preserving relationship graph

Status: implementation contract, adopted under the user's authorization to complete Phase 3.

The graph is a reproducible **derived view**, never an upstream source, entry migration,
identity merge, or claim-confidence aggregation. Inputs are the layered corpus; outputs
are `site/graph.json`. Build time and filesystem traversal order do not enter the bytes.

Nodes: entry, technique (ATT&CK external identifier only), capability, phase, platform,
source. IDs are typed (`entry:<entry-id>`, `technique:T1105`, etc.). NFC normalization
happens before identity, comparison and hashing. Duplicate normalized entry IDs fail.

Edges: entry `implements` technique, `has_capability` capability, `operates_in` phase,
`belongs_to` platform, `sourced_from` source. Enrichment edges copy the **individual
claim's** complete provenance and confidence. A pre-existing heuristic remains heuristic;
no similarity, fuzzy, cross-source equivalence or new heuristic relation is inferred.
Structural edges have `adapter/high` evidence explicitly stating the input metadata field;
this confidence attests the metadata link, not tool behavior or the entire entry.

An edge ID hashes its relation, endpoints, provenance and confidence with the frozen
canonical JSON primitive. Exact duplicate evidence collapses; different evidence for the
same relation is retained as separate edges. Nodes and edges sort by ID. Validation rejects
missing evidence, unknown enums, malformed IDs, dangling references, wrong relation endpoint
types, self-loops, duplicates and altered edge IDs. Entry input must have valid structural
metadata. Enrichment list fields and claims must be well formed. No fallback to projected
capabilities/phases/techniques is allowed: that would erase provenance.

ATT&CK syntax is `T` + four digits, optionally dot + three digits. Syntax is not registry
verification. A malformed ATT&CK claim is reported in `diagnostics` with its original
claim evidence and is not turned into a technique node, split, or silently repaired.
No ATT&CK names or tactics are fabricated and no live MITRE dependency is introduced.
Sources are retained as their exact project names; source URLs, licenses and revisions
remain in the entry corpus and public evidence view.

Acceptance: valid graph for the full corpus; deterministic bytes under entry/claim order
permutations; evidence unchanged; no mutation of input corpus; invalid evidence and
structural corruption fail closed; malformed technique claims remain visible diagnostics.

## Verification on the checked-in corpus

- 3,086 entry nodes, 3,187 total nodes, 18,057 evidence edges, 64 technique identifiers.
- Full corpus and claim arrays shuffled with a fixed seed: graph and technique objects
  remain byte-equivalent under canonical serialization.
- One preserved quality diagnostic: `loldrivers/asmio64-sys`, original upstream claim
  `T1542, T1068`. No false node or pair of fabricated independent claims is emitted.
- Dedicated graph/technique tests exercise per-claim preservation, deduplication,
  malformed input, structural metadata evidence, rehashed corruption, orphan nodes,
  dangling references, Unicode ID collisions and unsupported aggregate injection.

Counts describe this corpus snapshot; none is a future acceptance invariant.
