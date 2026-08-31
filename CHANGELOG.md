# Changelog

## Phase 5 CORE — CP5.2 Transition Engine · FROZEN

- `phase5/transition.py`: `evaluate(committed_body, observation, arrival_token)`
  returns an admission outcome, an optional successor state and an optional
  report. Pure — no I/O, no clock, no global state; every value comes from the
  observation.
- Implements the frozen design: §5.4 admission in normative branch order (both
  same-ID branches precede the base-token comparison, closing B7), complete
  byte-local §4/§6/§7/§8.4 observation validation before admission, the §9.2/§9.3
  per-owner partitions, the §9.4 ordered aggregate computed before any evidence
  tuple is touched, the §10 entry-level table with threshold 3 and generic head
  assignments, the §8.5 ambiguity policy, and the §15 report whose `changed` is a
  total OR over every PRESENT owner.
- Gate: `apply(G2, fixture_genesis) == G3` byte-exact — body 581, envelope 675,
  persisted file 676, sha256:286048e4…ce09. Production genesis unchanged at
  3,086 entries / 899,886 bytes / sha256:8d78d81b…5ca9; all CP5.1 goldens
  unchanged.
- Three independent Codex adversarial review rounds. Round 1 reported two
  blockers: canonical-equivalent Unicode observations could transition
  differently (the engine hashed a canonicalized observation but transitioned
  over the raw object), and observations the spec requires to be hard-invalid
  were admitted and advanced state. Round 2 reported one further blocker: the
  reserved invalid-path sentinel (§6.2.1) was accepted outside its sole legal
  disposition. All three shared one shape — a careful main path with a lax
  reserved or exempt branch.
- Round 3 closed every finding and additionally audited the remaining branches of
  that shape (the §8.4 AMBIGUOUS exemption, the NOT_RUN early return, the §7.2a
  source-level early returns) for the same class of bypass, finding none:
  zero blockers, zero majors, zero minors, no hidden scope expansion.
- Determinism: canonical-equivalent inputs produce byte-identical successors and
  reports across hash seed, locale and timezone.
- Tests: 159 CP5.2 · 310 CP5.1+CP5.2 · 350 repository-wide.
- Next: CP5.3 — verified acquisition and the five adapters.

## Phase 5 CORE — CP5.1 Deterministic Substrate · FROZEN

- The primitives every later checkpoint builds on: canonical JSON (§3), the
  digest and state-token grammar, the normative vocabulary (§4/§8/§9), the
  ownership resolver (§8), material projection (§14), the persistent state model
  and static validator (§11), virtual genesis (§12), and the canonical
  `input_ref` function (§6.2.1).
- Every frozen golden vector is an executable test asserting exact byte length
  and exact SHA-256: G1–G6, both placeholder vectors, the fixture genesis, and
  the production genesis reproduced from the real corpus (3,086 entries /
  899,886 canonical body bytes / sha256:8d78d81b…5ca9). The §11.5 evidence truth
  table is covered as an exhaustive cross-product.
- Independent Codex review reported three blockers — a digest grammar accepting a
  trailing newline, material projection silently collapsing NFC-duplicate detail
  keys instead of hard-failing, and `ROW(n)` accepted for non-LOLAD sources — all
  fixed and closed on re-review with zero blockers, zero majors, and no canonical
  byte changed.
- Tests: 151 CP5.1 + 40 pre-existing.
- Next: CP5.2 — the pure transition engine.

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
