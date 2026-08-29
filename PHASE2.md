# Phase 2 — Migrate remaining adapters to the layered model (per-claim provenance)

Phase 1 (frozen at efe2ac2) introduced the layered `source_data` / `enrichment`
model and converted the GTFOBins pilot. Phase 2 migrates the other four adapters
the same way, so **every** entry now carries source-attributed data and
enrichment with **per-claim** provenance/confidence. No public output changes.

## Contract (approved before implementation)

- **Per-enriched-value provenance (decision 1):** each claim carries its OWN
  `provenance.type` and `confidence.level`. An upstream-derived claim keeps its
  real (high) confidence even when the same entry also carries heuristic claims;
  confidences are never lowered across the board.
- **Heuristic fallbacks (decision 2):** any value introduced because upstream
  does not state it — a rule, default, or keyword guess — is
  `provenance.type: heuristic`, `confidence.level: low`, with a
  `provenance.note` explaining the rule.
- **Isolated helper (decision 3):** phase-1 `adapters/projection.py` is NOT
  modified. New helpers live in `adapters/enrich.py` (additive, separate).

## Per-adapter provenance

- **LOLBAS** (478) — `capabilities`/`phases`/`privilege` from deterministic maps
  on explicit upstream fields (Category, Privileges) → `adapter`/`high`;
  `attack_techniques` from upstream MitreID → `upstream`/`high`.
- **WADComs** (100) — `capabilities`/`phases` from the upstream `attack_types`
  map → `adapter`/`high`; when upstream states none, the `discovery` default →
  `heuristic`/`low` (note); `privilege` from an exact-token rule on `items`
  (No_Creds) → `adapter`/`high`.
- **LOLAD** (137) — no upstream taxonomy; capability/phase/privilege are guessed
  by keyword from name+command → all `heuristic`/`low` (note).
- **LOLDrivers** (661) — **mixed**: `attack_techniques` from upstream MitreID →
  `upstream`/`high`; `capabilities`/`phases` from keyword+default classify →
  `heuristic`/`low` (note); `privilege` from a keyword+default rule on the
  upstream Privileges text → `heuristic`/`low` (note). `driver_detail`
  (sha256/signer/category) is preserved as structural passthrough.

## Files

- `adapters/enrich.py` — NEW. `enriched()`, `claims()`, `assemble()`,
  `source_block()`.
- `adapters/lolbas.py`, `wadcoms.py`, `lolad.py`, `loldrivers.py` — migrated to
  `projection.make_entry()`; no direct top-level assignment.
- `tests/test_phase2.py` — NEW (13 tests).
- `data/entries/**` — the four sources regenerated in layered format.
- Unchanged: `schema/schema.yaml`, `adapters/base.py`, `adapters/projection.py`
  (phase 1 frozen).

## Guarantees (Definition of Done — all met)

- All four adapters layered; no adapter assigns projection-owned fields directly.
- Every migrated entry has `source_data` + `enrichment`; `source_data` holds
  upstream-only data (raw is opaque).
- Provenance/confidence correct claim-by-claim; heuristic fallbacks marked
  `heuristic`/`low` with a note.
- `top-level == projection(enrichment)` for every entry.
- `scripts.validate` → 3086 entries, 0 errors.
- Phase-1 tests → 26/26. Phase-2 tests → 14/14.
- `site/data.json` public output unchanged by the phase-2 migration: the
  layers (source_data/enrichment/_meta) are internal and never enter data.json.
  The projected top-level fields are byte-identical to the pre-phase-2 baseline.
  (Later upstream syncs may change data.json through normal content drift; that
  is independent of the phase-2 migration.)
- No other adapter migrated; no schema/contract change; no operational
  capability introduced.

## source_data.raw is upstream-only (audit fixes A/B)

`source_data.<project>.raw` holds upstream values verbatim, never a Loldex
normalization: WADComs raw carries the upstream file stem (`file`), not a
hyphen->space display name; LOLDrivers `raw.privileges` preserves upstream case
(no `.lower()`). Guarded by `test_raw_is_not_loldex_normalized`.

## The three former legacy orphans (resolved by upstream sync)

Three entries had a history worth recording:
`lolbas/vssadmin/tamper/0`, `loldrivers/alinubx-sys`, `loldrivers/dcrcvdrv-sys`.

At the phase-2 baseline (`efe2ac2`) they were legacy (no source_data/enrichment):
the upstream snapshot in use at that point no longer produced them, and `run()`
overwrites but does not delete files, so they persisted from an earlier import.
Phase 2 deliberately left them untouched rather than fabricate layers for
entries the adapters were not emitting — a preexisting condition, not something
phase 2 introduced.

They are no longer legacy. The scheduled sync bot re-ran the adapters against a
newer upstream revision that re-includes these three entries, so they were
regenerated in the normal layered format (source_data + enrichment + _meta),
exactly like every other entry. No manual intervention was involved. As of the
current `main`, no legacy orphan entries remain in the four migrated adapters.

Because the layers are internal and never enter `data.json`, this regeneration
did not change the public output.

## Out of scope (unchanged)

Relationship graph, cross-source deduplication/identity, technique pages, UI,
migration of any non-adapter legacy entries, and any operational/offensive
capability.

## Verification

```
python -m scripts.validate                 # 3086 entries — 0 errors
python -m scripts.build_site_data          # data.json byte-identical
python -m pytest tests/ -q                 # 40 passed (26 phase 1 + 14 phase 2)
```
