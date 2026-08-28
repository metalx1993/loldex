# Phase 1 — Layered data model (`source_data` / `enrichment`)

This phase introduces a layered entry model **without changing any public
output**. It is the foundation for later phases and is designed so those can be
added without a second destructive migration.

## Architecture

```
source_data + enrichment  ->  projection.build()  ->  legacy top-level fields
```

The top-level fields (`capabilities`, `phases`, `privilege_required`,
`attack_techniques`) are **not** the source of truth — they are a projection
derived from the enrichment layer. Divergence is therefore structurally
impossible: any hand-set top-level is overwritten by `apply()`
(see `test_projection_overwrites_manual_toplevel`).

## The three layers (all additive, all optional in phase 1)

**`source_data.<project>`** — only what the upstream source states, in its own
vocabulary.
- `raw` (object, required) — the source's own payload. It is **opaque**: it is
  NOT validated against loldex taxonomies. A key inside `raw` that happens to be
  named `capabilities` is accepted as-is (`test_source_data_raw_is_opaque`).
- `upstream_url` (string, required).
- `upstream_version` (string, optional) — commit hash / release tag.
- `last_synced` (date, optional) — OUR fetch time. This is the **only** home for
  `last_synced`.
- The block's own keys must not be loldex-interpretive
  (`test_source_data_rejects_interpretive_keys`).

**`enrichment`** — what loldex maps/derives; the **sole** input to the
projection. Every value is an `enriched_value`:
```
value
provenance: { type: upstream|adapter|heuristic|manual, source?, adapter?, note? }
confidence: { level: low|medium|high|verified }
```
`provenance` (who produced it) and `confidence` (how sure) are **independent
axes**. Active fields in phase 1: `capabilities`, `phases`,
`attack_techniques` (lists) and `privilege_required` (single).
`detection` / `mitigation` / `notes` are **RESERVED** in the schema — no adapter
emits them and nothing reads them in phase 1.

**`_meta`** (serialized as `_meta`, never `meta` — `test_meta_serializes_as_underscore`).
Active contract in phase 1 is **exactly** four keys
(`test_meta_contract_is_exactly_four_keys`):
- `schema_version` — `1`
- `generated_by` — the projecting component, `loldex-projection`
- `projected_at` — when the projection was stamped
- `source_hashes` — `<project>: sha256:...`

There is deliberately **no** `_meta.last_synced` (sync time is per-source, in
`source_data.<project>.last_synced`) and **no** `_meta.model`.
`last_enriched` is RESERVED — the manual-enrichment lifecycle is not handled in
phase 1, so it is documented but never populated.

## Per-source hashing

`source_hash` = `sha256` over canonical JSON of `raw` (+ `upstream_version` when
present). It **excludes** `last_synced` and `upstream_url`, so the hash changes
if and only if upstream content changes — the basis for real change detection.
Each project is hashed independently (`test_compute_source_hashes_two_sources`).

## Projection contract

- `build(enrichment)` — pure, deterministic, idempotent; no clock, no I/O.
  Always returns all four owned keys (empty when absent).
- `apply(entry)` — mutative; assigns the **complete** projection (so a field
  removed from enrichment is cleared, not left stale —
  `test_apply_clears_removed_field`, `test_projection_full_contract_after_removal`)
  and stamps `_meta`.
- Adapters never author the four owned fields directly; they build
  `source_data` + `enrichment` and call `make_entry()`.

## Scope and guarantees

- **Pilot only:** GTFOBins is the only adapter on the layered path in phase 1.
  LOLBAS, WADComs, LOLAD, LOLDrivers remain legacy and validate unchanged.
- **No regression:** the dataset validates and `site/data.json` is
  **byte-identical** before and after. `_meta`, `source_data`, `enrichment` are
  internal and are not emitted into `data.json`, so the public site, PHP API,
  and client-side search are unaffected.
- **Not implemented:** relationships (reserved in the model, not built),
  technique pages, confidence surfacing, UI — later phases.
- **Data model only:** no exploit execution or operational capability is
  introduced.

## Files

- `adapters/base.py` — `EnrichedValue`, `LOLDEX_INTERPRETIVE_KEYS`, the three
  layer fields on `Entry`, layer validation (runs only when layers are present),
  `meta` -> `_meta` serialization.
- `adapters/projection.py` — `build()`, `apply()`, `make_entry()`,
  per-source hashing, `GENERATED_BY`.
- `adapters/gtfobins.py` — pilot; builds the layers and goes through
  `make_entry()`.
- `scripts/validate.py` — non-blocking layer checks; legacy entries pass.
- `schema/schema.yaml` — `version: 1`; documents the layered model, the
  `enriched_value` type, and the reserved fields.
- `tests/test_phase1.py` — 26 tests.

## Verification

```
python -m scripts.validate                 # 3086 entries — 0 errors
python -m scripts.build_site_data          # data.json byte-identical
python -m pytest tests/test_phase1.py -q   # 26 passed
```
