# Independent adversarial review — Phases 5, 3 and 4

Status: **PASS on the independently tested scope.** Final repository-wide test
totals and browser checks are recorded separately in the delivery report.

Scope: independent attempts to violate the approved CORE and the new Phase 3/4
contracts. Tests use synthetic data and local temporary Git object databases;
they do not fetch upstream, synchronize the production corpus, or deploy.

## Acquisition boundary

Verified independently in `tests/test_adversarial_semantics.py`:

- Modified, deleted and untracked working-tree files cannot change a bundle
  acquired from the same committed object.
- WADComs dotfiles, nested Markdown files and uppercase extensions are excluded
  by the stated discovery rule.
- A missing selected blob fails acquisition; it cannot become healthy absence.
- A selected symlink fails acquisition and cannot read external file bytes.

Initial result: **4 tests passed**. The expanded independent suite now has **22
passing tests** at that stage, covering the boundaries below in addition to
acquisition. The final independent suite has **23 passing tests**.

## Required semantic attack matrix

| Boundary | Adversarial input | Required outcome |
|---|---|---|
| File candidate cardinality | Multiple LOLBAS commands | One candidate for the file |
| Collision precedence | Same final ID with an additional content defect | Reject every participating file as `DUPLICATE_ID`; no sibling emission from rejected files |
| Unknown classifications | LOLBAS unmapped category | Retain parsed emission; suppress source health credit |
| Parser typing | Required YAML string resolves as boolean/integer | Reject with the specific shape error; never coerce |
| Empty code | Empty GTFO context next to a valid context | Parsed file, non-suppressing diagnostic, surviving valid emission |
| Driver identity/name | Valid Id with empty Tags | Identity retained; projected name omitted; no fabricated fallback |
| Path normalization | Two source names normalize to one reference | Reject all, preserve rejection multiplicity |
| State persistence | Failed/partial/NOT_RUN owner | No evidence mutation or qualifying absence |
| Admission | Byte-identical retry | No second state mutation and no report |
| Relationship evidence | Same value with different claim evidence | Preserve separate evidence; no confidence escalation |
| Graph authority | Injected projected fields without claims | No new enrichment-derived edge |
| Technique registry | Unknown syntactically valid ATT&CK ID | Queryable identifier, explicitly unverified; no invented name |
| Technique aggregate | Injected unrelated entry or changed totals | Validator rejects divergence from validated graph |

## Findings corrected during review

1. Python 3.9 could not import the new observation dataclass because a union
   annotation was evaluated at runtime. Deferred annotation evaluation restored
   compatibility; the actual test environment now imports and executes it.
2. A null GTFO function-record list could terminate parsed with zero emissions,
   potentially supplying false healthy absence. Explicit list typing now rejects
   malformed function values, and the implementation suite covers these cases.
3. Search confidence originally matched any claim on the entry, independent of a
   selected technique/capability. It could therefore qualify a low-confidence
   technique using an unrelated high-confidence privilege. Confidence and
   provenance now qualify each selected claim facet, and selected source restricts
   the supporting claim's source. Independently exercised mixed-source cases pass.
4. The observation's internal layered source block was missing the Phase 1
   required upstream URL. It now includes that URL without changing material
   fingerprints.
5. The UI catalog builder copied the four interpretation-owned public fields
   independently of enrichment. A drifted top-level capability could therefore
   appear without a supporting claim. The catalog now rederives those fields
   through the frozen projection function and validates optional CORE state;
   independent injected-field checks confirm that no phantom interpretation
   survives and that input corpus objects remain unchanged.
6. Final cross-view review found that a decomposed Unicode corpus ID could stay
   decomposed in the legacy API while graph/catalog normalized it. The integrated
   builder now rejects non-NFC corpus IDs before creating any output, preserving
   the existing API byte contract without silently migrating identities.
7. The integrated builder could preserve drifted interpretation-owned fields in
   the legacy API while the new UI corrected them. It now checks projection
   parity before building any artifact; contradictory API/UI interpretations
   fail closed.
8. The workflow's new build step initially left the old staging list unchanged.
   A later manual sync could therefore commit a refreshed corpus while leaving
   graph/catalog/evidence stale. Its explicit staging list now includes every
   generated view, manifest and registry notice under the unchanged A1 base
   guard. Cron remains disabled and deployment remains absent.

## Independent evidence

- Existing frozen suite: **359 passed in 262.42 seconds**, collected before new
  phase tests were added. This is baseline evidence, separate from later totals.
- Independent adversarial suite: **23 passed**. Includes collision-before-content
  precedence, no silent unknown-category skips, NFC collision multiplicity,
  empty-code sibling survival, nested-table rejection, immutable acquisition,
  corrupted-state fail-closed, pre-rename failure and byte-identical retry.
- Populated material fixtures for all five sources were independently compared
  with the existing literal mappings. Exact expected fingerprints are pinned in
  the adversarial tests, including driver Company/SHA256/OriginalFilename/opsec,
  references, command comments and LOLAD's established literal entity behavior.
- An exploratory 117-case YAML shape grid produced no unhandled exception or
  observation rejected by the frozen transition validator.
- Mutation check: in a separate process, replacing the discovery predicate with
  accept-all makes the WADComs exclusion regression fail. The mutation was killed;
  no production file was changed for this experiment.
- Independent JavaScript checks cover mixed-source evidence and confidence/origin
  correlation across multiple selected facets, plus unsafe external URL inputs.
- Final combined Phase 5 implementation and independent tests: **63 passed in
  2.46 seconds**. Broader graph/technique/registry/UI Python checks previously
  passed (115 tests before the last additional regressions were collected).
- The pinned MITRE registry extension preserves the boundary between official
  metadata and entry evidence. An independent test joins an official name to a
  low-confidence heuristic claim without upgrading its confidence or introducing
  registry tactics as entry relationships. The documented `registry_status`
  refers to identifier matching in the pinned registry, not a digital signature,
  behavior verification or entry-level confidence. The original snapshot source
  URL/hash and redistribution notice are recorded in the Phase 4 contract.
- Final integration and UI-builder targeted regressions: **13 passed** after the
  NFC identity, projection-parity and complete workflow-staging fixes. Read-only
  UI inspection confirms safe text rendering of registry descriptions, separate
  revoked/deprecated labels, and explicit separation of registry matching from
  entry-claim confidence. Final browser results are owned by the integration
  review and are not restated as independent browser tests here.

The reviewed runtime conforms within CORE's valid-input boundary. It serializes
live local cycles, replays finalized observation bytes and uses rename as the
commit point. It does **not** promise persistent reservation/arbitration across a
crash before finalization; the D1 caller limitation states this explicitly, as
required by the frozen scope. No journal, scheduler or distributed coordination
was smuggled in to make the tests pass.
