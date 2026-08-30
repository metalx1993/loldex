# Changelog

## Phase 5 CORE — Design Frozen · READY FOR IMPLEMENTATION

- Design specification frozen for the CORE freshness-observation engine
  (observe → classify → persist). Reviewed to zero normative ambiguity: two
  independent implementations of the spec must produce byte-identical
  classification, persistent state, hashes, and reports from the same valid inputs.
- Independent closure review passed all gates: classification totality YES ·
  persistent-state determinism YES · idempotency/concurrency (valid-input) YES ·
  hidden scope expansion NO. Confidence 98% ±2. Zero blockers, majors,
  behavioral minors, or regressions.
- Reached through eleven adversarial review cycles: four on the full-scope
  design (which drove the scope reduction to observe-and-classify) and seven
  independent closure reviews on CORE.
- Verified against commit 00a9fe2, and confirmed byte-identical after the
  2026-08-29 upstream sync (1ae5df3): the refresh touched only the
  last_synced / projected_at clock fields, which CORE excludes from material
  projection by design — so all 3,086 IDs, the 3,086/3,086 ownership resolution,
  and the 899,886-byte genesis (sha256:8d78d81b…) are unchanged.
- Scope boundary (intentional): CORE does not publish, delete, or coordinate.
  No automatic deletion, terminal STALE, publication authority, scheduler,
  queue, or journal/recovery subsystem.
- Next: CP5.1 implementation — golden vectors become executable tests.
