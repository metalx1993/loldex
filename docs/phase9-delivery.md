# Phases 7–9 — delivery and acceptance gates

Status: local implementation and focused checks completed; current production
acceptance pending. This record is completed by the release operator after the
remaining gates actually run. It does not replace frozen CORE approvals or the
previous A2/D2 production acceptance record.

## Observed local checks

- Phase 9 identity unit and independent adversarial checks: 37 passed at the
  focused checkpoint. Later final aggregate test results must be recorded below.
- Actual Chromium integration passed against the generated local site using
  tests/browser_phase9.cjs: valid and invalid advanced queries, correlated filters,
  30-to-60 pagination, three declared identities, per-membership witness expansion,
  separate candidates, historical Certutil alias, an actual source evidence shard
  response, no page errors, and no horizontal overflow on checked 320px pages.
- This browser checkpoint used the current 3,336-entry snapshot. It proves local
  behavior for the exercised pages; it does not prove public routing or hosting.

## Gates awaiting final operator evidence

| Gate | Current result |
|---|---|
| Final complete Python/JavaScript/PHP suites and generated-data validation | Pending final operator record |
| Final CI run bound to the exact delivery commit | Pending |
| Committed immutable release package and content manifest verification | Pending |
| Production activation and retained-release binding | Pending |
| Public API routing, CORS, GET/HEAD/OPTIONS and conditional response checks | Pending |
| Production advanced search, identity/alias and evidence-page smoke checks | Pending |
| Rollback/restore acceptance for this exact release, if required by release operator | Pending |
| Cron activation | OFF — requires final explicit user activation |

## Semantic boundaries

CORE observes and classifies; D2 separately prepares publication snapshots.
API/search/UI read a single bound release and never trigger upstream acquisition
or CORE transitions. Identity membership is a per-claim association, not technique
equivalence. Candidate suggestions and stale witnesses never become active
membership. Explicit aliases explain old IDs without automatic redirects,
selected split winners or confidence inheritance. Agent curation is labelled as
agent curation. Historical Git commit/path review is documented as an offline
review basis, not independent proof of historical public hosting.

Phase 10 remains future work.
