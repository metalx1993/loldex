# LOLDEX — delivery through Phase 6

13 November 2026 · local implementation and verification.

## Result

Implemented the requested sequence: Phase 5 CORE completion → Phase 3 graph →
Phase 4 technique intelligence views → Phase 6 search/evidence experience.
The user delegated the remaining design choices; new contracts record those
choices explicitly. Historical CORE/CP5.1/CP5.2/A1 freezes were not rewritten.
Verification was completed locally before the requested GitHub upload. Production
deployment is separate and has not been performed.

## Delivered behavior

- **Phase 5:** source-specific D1 discovery; immutable commit/tree/blob verified
  acquisition from explicitly provided local Git repositories; five pure
  observational adapters; exact health diagnostics and reject-all collision
  semantics; frozen transition integration; validated POSIX state persistence
  and byte-identical delivery-artifact retries. A real synthetic Git repository
  exercises all five sources through persistent ACTIVE state in the tests.
- **Phase 3:** deterministic derived graph; evidence/confidence on each edge;
  no projected-field fallback or destructive cross-source identity inference.
- **Phase 4:** aggregations with preserved supporting evidence and pinned official
  Enterprise ATT&CK 20.1 metadata, source hash, offline importer and license.
  Revoked IDs remain labeled and unknown identifiers never get invented names.
- **Phase 6:** responsive global search (including commands/technique names),
  combinable facets, correlated claim-confidence/origin filtering, paginated
  results, entry/source evidence, technique pages and navigable local graph.
  Raw evidence and official descriptions render safely as text.
- **Integration:** offline build_all validates the graph, registry and public
  projection parity before any output, rejects noncanonical IDs, and produces
  a manifest for all generated data. Manual sync stages all generated views
  under the unchanged A1 publication-base guard; cron and deploy stay disabled.

Observed checked-in dataset: 3,086 entries; 3,187 graph nodes; 18,057 evidence
edges; 64 technique identifiers, all matching the pinned registry. These are
snapshot observations, not future invariants. One malformed upstream technique
claim (`T1542, T1068`, `loldrivers/asmio64-sys`) is retained as a diagnostic;
it is not silently split into two independent claims. T1562 and T1562.001 are
marked revoked in the pinned registry and are shown with that lifecycle state.

## Verification

- Final repository-wide suite: **496 passed in 242.64 seconds**, exit 0.
  This run includes the final cross-view identity/projection and workflow-staging
  regressions, all frozen tests and all new phase tests.

- Independent adversarial suite: 23 passing cases; reviewer report in
  [adversarial-review.md](adversarial-review.md). A discovery-predicate mutation
  was killed by its exclusion regression.
- JavaScript pure search/URL regressions passed, including confidence leakage,
  source/claim correlation and unsafe protocol rejection.
- Browser flows passed: homepage, search, combined filters, reset, pagination,
  entry commands/evidence, technique names/pages, revoked marker, unknown/empty
  results, malicious text rendering and all main views at 320px width.
- Browser checks passed for accessible control names, heading presence and
  reduced-motion mode. Measured token contrast: body 16.51:1, muted text on
  surface 8.14:1, accent 12.85:1, control boundary 4.50:1. This is scoped testing,
  not a claim of a full assistive-technology or WCAG certification audit.
- Corpus validation: 3,086 entries, zero errors. Repeated offline builds produced
  identical data hashes. Generated file digests match build-manifest.json.
- CORE spec SHA-256 remains
  `f79aed020b36d1a217b8091319be1e7ec7cf5ac48849c8d0b765a1523f2ef3e0`.
  Diff is empty on frozen production modules, legacy adapters, existing corpus
  and legacy site/data.json. Whitespace/error checks pass.

## Reproduce

```sh
python3 -m pytest -q
node tests/test_experience.js
python3 -m scripts.validate
python3 -m scripts.build_all
python3 -m http.server 8765 --bind 127.0.0.1 --directory site
# In a second terminal, with Playwright available:
node tests/browser-experience.cjs
node tests/browser-accessibility.cjs
```

Browser tests use LOLDEX_TEST_URL when set, defaulting to the local preview.
They submit no contact forms or external messages. Screenshots are written to
ignored work/. Production code uses only existing PyYAML and standard libraries;
no front-end framework, CDN script or new production dependency was added.

## What this does not claim

- No live upstream refresh, production deployment or production
  smoke test occurred. Real upstream Git object stores can be supplied explicitly
  via scripts.observe; test fixtures demonstrate the complete local path.
- CORE does not publish/delete or migrate historical IDs. Existing corpus and API
  bytes stay unchanged. Default UI classification is NOT_OBSERVED unless validated
  state is supplied explicitly with build_all --state.
- CORE valid-input caller restrictions remain: one distinct observation per base
  token. Cross-process crash recovery before finalized bytes exist is not a new
  reservation/journal service. Exact retries reuse the same canonical artifact.
- A2 atomic deployment and any cron reactivation remain separate. Phases 7–10
  remain future roadmap work; the existing basic API is not a completed Phase 7.

## Review map

Start with docs/ROADMAP.md, phase5-d1.md, phase5-completion.md,
phase3-design.md, phase4-design.md and phase6-design.md. Independent findings
and their corrections are recorded separately in adversarial-review.md.
