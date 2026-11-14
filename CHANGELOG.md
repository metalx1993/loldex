# Changelog

## Phases 7–9 — production delivery · 2026-11-14

- Added a versioned knowledge API, OpenAPI contract, dataset/release binding,
  bounded pagination, strict request validation, conditional responses and exact
  original evidence shards. Legacy endpoints remain separate.
- Added matching JavaScript/PHP advanced query engines with bounded Boolean
  grammar, claim-correlated qualifiers, facets and relevance explanations.
  Entry-level metadata never borrows another claim's confidence.
- Added a versioned durable tool registry: three real cross-source declarations,
  per-membership raw evidence/provenance/confidence, separate low-confidence
  candidates, retained stale/missing associations and an explicit historical
  Certutil source-ID alias. No technique merge or transitive identity inference.
- Added local PHP/JavaScript, adversarial and actual Chromium integration checks,
  including advanced search errors, pagination, identity witnesses, historical
  alias UI, sharded evidence and mobile 320px layouts. Full CI: 848 tests passed.
  Live API, cross-origin browser, mobile and real rollback/restore passed; see
  docs/phase9-delivery.md.
- Preserved frozen CORE/D1 and the separate D2 publication profile. The current
  publication snapshot contains 3,336 entries; the historical Phase 6 record
  below describes its original delivery rather than today's deployment state.
- Cron remains OFF pending explicit final user activation. Phase 10 remains future.

## Local delivery through Phase 6 — 2026-11-13

- Added D1 discovery and verified immutable Git acquisition, five observational
  adapters, full canonical observations, pure-engine integration and POSIX
  crash-safe state persistence. Exact retry consumes finalized observation bytes.
  Frozen CORE/CP5.1/CP5.2 production modules and the existing corpus are unchanged.
- Added a deterministic derived relationship graph retaining provenance and
  confidence per edge, with strict integrity validation and visible diagnostics.
- Added technique aggregation and a pinned MITRE ATT&CK Enterprise 20.1 registry
  with source hash, offline importer, attribution and revoked/deprecated metadata.
  Registry matches do not verify or promote entry claims.
- Added responsive search, correlated claim-confidence/origin filters, source
  evidence, entry/technique pages and accessible local relationship navigation.
  UI projection is rederived from claims; absent observations stay NOT_OBSERVED.
- Added validated offline build_all and a generated-data manifest. The manually
  dispatched workflow rebuilds the new datasets; cron and deploy remain disabled.
- Independent adversarial tests target acquisition truncation, typed parsing,
  collision precedence, health holds, retry/persistence failures, provenance loss,
  registry confusion and confidence leakage. Final counts: docs/DELIVERY.md.
- Local implementation only: no upstream corpus refresh, production deployment,
  ID migration or historical freeze rewrite. A2 and Phases 7–10 remain separate.

## Phase 5 CORE — CP5.1 Corrective Amendment A1 · FROZEN

- Corrects the boundary between frozen golden evidence and the mutable production
  corpus, and hardens the sync workflow that boundary depends on. Two opposite
  defects from one mistake: the production genesis was pinned to a historical
  snapshot the spec declares mobile, while golden G1 — printed and pinned by §16 —
  read its input from a corpus file the sync rewrites.
- Production-genesis values (3,086 entries / 899,886 bytes / sha256:8d78d81b…) are
  now recorded as evidence verified at 00a9fe2, not asserted: §12 states the
  production genesis "is corpus-dependent by construction and regenerates whenever
  the corpus changes". G1's input is an inline frozen fixture reproducing exactly
  552 bytes and sha256:8e4efac5…, keeping the non-material fields so the §14
  exclusions stay exercised.
- Genesis tests now assert independent properties — validate_body on the live
  corpus, determinism, full ownership resolution, and §12 extraction-contract cases
  on synthetic fixtures — verified by mutation testing rather than by a snapshot.
- Sync workflow: the candidate corpus is built, validated, tested and published
  under one Git base. The base is captured before acquisition and re-checked
  against origin/main immediately before publication; a mismatch exits having
  created no commit. No rebase, no force push — a race landing after the check is
  rejected as non-fast-forward. Actions pinned to immutable commit SHAs,
  least-privilege permissions, cron disabled.
- Deployment removed rather than repaired: the FTP action was not commit-atomic
  and carried a vulnerable basic-ftp. Deferred to amendment A2 — Atomic
  Deployment; no executable deployment path remains.
- Four adversarial review rounds. Blockers found and closed: an "advisory" drift
  test that was in fact a blocking gate reintroducing the corpus pin; a stale
  candidate publishable after a clean rebase; a non-atomic deployment. Then a local
  commit created before the base check, and an out-of-scope concurrency mechanism.
  Final accreditation ran the two-concurrent-publisher race on real Git
  repositories: the loser is rejected non-fast-forward and never overwrites the
  winner, with no lock or queue. Zero blockers, majors and minors.
- Tests: 160 CP5.1 · 159 CP5.2. No phase5/* production module changed; CP5.2
  byte-identical to its freeze.
- Next: CP5.3 — verified acquisition and the five adapters.

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

## 2026-11-13 — A2 and explicit D2 publication profile

- Add deterministic committed-object release packages, complete-file hash
  verification, retained versioned URLs, exact-state activation CAS and rollback.
- Migrate the SiteGround root through a reviewed private legacy backup; verify
  HTTPS routing after explicitly authorized dynamic-cache purge.
- Add opt-in D2 publication adapters for GTFO aliases/inherit, qualified LOLBAS
  identities, evidence-preserving exact LOLAD occurrence coalescence, full driver
  sample/command representation and complete WADComs text/references/vocabulary.
- Preserve frozen CORE/D1 behavior. Independent source oracles bind public IDs,
  material, raw evidence and claim provenance/confidence before staging.
- Replace the manual legacy sync path with a verified five-source snapshot,
  explicit historical-retention ledger and unchanged A1 Git-base protection.
- Add a credential-free trusted host pull publisher; no scheduler enabled.
