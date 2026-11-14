# LOLDEX — delivery roadmap

Updated 14 November 2026. This replaces historical progress summaries as the
implementation index; it does not replace any frozen normative CORE clause.

## Implementation status through Phase 9

| Phase | Scope | Status / contract |
|---|---|---|
| 0 | Foundations and unified catalogue | Existing implementation |
| 1 | Source data → enrichment → projection | Frozen existing contract, PHASE1.md |
| 2 | Per-claim provenance and confidence, five sources | Existing implementation, PHASE2.md |
| 2.1 | Documentation and test hygiene | Existing implementation |
| 3 | Derived relationship graph with evidence | Implemented; phase3-design.md |
| 4 | Technique views and pinned official registry | Implemented; phase4-design.md |
| 5 | Verified acquisition, observations, deterministic transitions, persistence and reports | Implemented; phase5-d1.md and phase5-completion.md; historical freezes unchanged |
| 6 | Search, facets, entry evidence, technique pages and local relationship UI | Implemented; phase6-design.md |
| 7 | Versioned public knowledge API with release-bound data and original evidence | Implemented and tested locally; phase7-design.md; production acceptance pending |
| 8 | Bounded Boolean queries, claim-correlated filters, relevance explanations and facets | Implemented and tested locally; phase8-design.md; production acceptance pending |
| 9 | Durable declared tool identities, separate candidates and explicit historical source-ID aliases | Implemented and browser-tested locally; phase9-design.md; production acceptance pending |
| 10 | Ongoing quality and governance operations | Future phase; not claimed complete |

The new work was locally implemented and independently reviewed before the
requested GitHub upload. Production deployment and historical gatekeeper
approvals are separate. Historical verification through Phase 6 is in DELIVERY.md. New Phase 7–9
release gates and current acceptance evidence are tracked in phase9-delivery.md.

## Exact boundaries

- CORE observes and classifies. It does not publish or delete catalogue entries.
- Observation uses verified local upstream Git repositories explicitly supplied
  to scripts.observe. No implicit live fetch, refresh or mutable-worktree trust.
- The current checked-in D2 publication snapshot contains 3,336 entries. D2
  path-qualified source IDs do not rewrite frozen CORE/D1 identity contracts.
  Phase 9 records explicit witnessed bookmark aliases without automatic redirects,
  transitive identity propagation or destructive deduplication.
- UI freshness is NOT_OBSERVED unless a validated CORE state is explicitly
  supplied at build time. Presence in an observation is not a clock-based guarantee.
- A2 immutable releases, host CAS and rollback are implemented and the production
  root has been migrated. See a2-design.md and a2-siteground-runbook.md.
- D2 is an explicit publication profile for current source formats, separate from
  frozen CORE/D1. See phase5-d2-publication.md. Full manual GitHub refresh and live
  publication/rollback acceptance passed: 783 tests, 3,336 entries, five healthy
  publication sources. See a2-completion.md. Cron is ready for explicit activation
  and remains disabled until requested.
- Crash recovery before an observation artifact is finalized remains the
  frozen caller responsibility, not a newly invented reservation service.

## Remaining gates

1. Complete the current Phase 7–9 full-suite/CI and production acceptance record
   in phase9-delivery.md. Local browser tests already exercise advanced query
   errors and correlated filters, pagination, three declared identities,
   separate candidates, the historical Certutil alias and sharded source evidence,
   including 320px layouts. These checks do not establish hosting behavior.
2. Preserve the accepted A2/D2 immutable-release, rollback and five-source
   publication boundaries. Prior production acceptance in a2-completion.md does
   not automatically accept this new API/search/identity release.
3. Keep cron OFF. Activation remains a final explicit user decision after the
   current release gates; see cron-activation.md.
4. Plan Phase 10 quality and governance work separately. The focused validators,
   adversarial tests and curation shipped here are not a claim that broader
   ongoing governance operations have been completed.
