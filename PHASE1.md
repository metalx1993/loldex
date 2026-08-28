# Phase 1 — Layered data model (`source_data` / `enrichment`)

This phase introduces a layered entry model **without changing any public
output**. It is the foundation for later phases (relationship graph, technique
pages, confidence, stale-data detection) and is designed so those can be added
without a second destructive migration.

## What changed

**Architecture:** `source_data + enrichment  ->  projection  ->  legacy top-level fields`

The top-level fields (`capabilities`, `phases`, `privilege_required`,
`attack_techniques`) are no longer the source of truth — they are a **projection**
derived from the enrichment layer. This removes any possibility of the two
diverging.

Every entry can now carry three additive, optional layers:

- **`source_data.<project>`** — only what the upstream source states, in its own
  vocabulary. No loldex interpretation is allowed here (enforced by validation).
- **`enrichment`** — what loldex maps/derives/adds. Every value carries its own
  `provenance` (`upstream` | `adapter` | `heuristic` | `manual`) and
  `confidence` (`low` | `medium` | `high` | `verified`), kept as separate axes.
- **`_meta`** — `schema_version`, `generated_by`, `projected_at`,
  `last_enriched`, and per-source `source_hashes` (sha256 over upstream content,
  excluding fetch metadata, so the hash changes iff the source content changes).

## Files changed

- `adapters/base.py` — adds `EnrichedValue`, `LOLDEX_INTERPRETIVE_KEYS`, the
  three layer fields on `Entry`, layer validation (runs only when layers are
  present), and the internal `meta` -> external `_meta` serialization mapping.
  Top-level validation is unchanged.
- `adapters/projection.py` — new. Pure `build()`, mutative `apply()`,
  `make_entry()`, and per-source hashing.
- `adapters/gtfobins.py` — pilot adapter. Now builds `source_data` + `enrichment`
  and goes through `make_entry()`; it no longer sets top-level fields directly.
- `scripts/validate.py` — non-blocking layer checks; legacy entries pass
  unchanged.
- `schema/schema.yaml` — bumped to `version: 1` (additive, backward compatible).
- `tests/test_phase1.py` — new test suite (23 tests).
- `data/entries/linux/*` — GTFOBins entries regenerated in the layered format.

## Scope and guarantees

- **No regression:** the existing dataset still validates (3,083 entries, 0
  errors) and `site/data.json` is **byte-identical** before and after — the
  public site, PHP API, and client-side search are unaffected.
- **Pilot only:** only GTFOBins uses the layered path in this phase. The other
  four adapters (LOLBAS, WADComs, LOLAD, LOLDrivers) remain legacy and are
  migrated in Phase 2. This is a deliberate, temporary dual path.
- **Not yet implemented:** relationships (reserved in the schema, not built).
- **Data model only:** no exploit execution or operational capability is
  introduced — this is purely data architecture.

## Verification

```
python -m scripts.validate          # 3083 entries — 0 errors
python -m scripts.build_site_data    # data.json byte-identical
python -m pytest tests/test_phase1.py -q   # 23 passed
```
