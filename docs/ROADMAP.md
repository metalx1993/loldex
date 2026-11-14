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
| 7 | Versioned public knowledge API with release-bound data and original evidence | Implemented, tested and published; phase7-design.md; phase9-delivery.md |
| 8 | Bounded Boolean queries, claim-correlated filters, relevance explanations and facets | Implemented, tested and published; phase8-design.md; phase9-delivery.md |
| 9 | Durable declared tool identities, separate candidates and explicit historical source-ID aliases | Implemented, tested and published; phase9-design.md; phase9-delivery.md |
| 10 | Ongoing quality and governance operations | Future phase; not claimed complete |

Phases 7–9 passed independent adversarial reviews, 848 CI tests, live API/browser
checks and actual rollback/restoration on 14 November. See phase9-delivery.md.
Historical verification through Phase 6 remains in DELIVERY.md. Production
acceptance does not rewrite historical gatekeeper approvals.

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
  frozen CORE/D1. See phase5-d2-publication.md. Initial A2/D2 manual GitHub refresh and live
  publication/rollback acceptance passed: 783 tests, 3,336 entries, five healthy
  publication sources. See a2-completion.md. Both schedules were explicitly
  activated on 14 November; full automatic-cycle acceptance remains pending.
- Crash recovery before an observation artifact is finalized remains the
  frozen caller responsibility, not a newly invented reservation service.

## Next steps

1. Phases 7–9 production acceptance is complete; see phase9-delivery.md.
2. GitHub and SiteGround schedules are enabled. Verify the first complete
   automatic cycle; see cron-activation.md.
3. Preserve CORE/D1, D2, immutable releases, per-claim evidence and retained
   rollback versions as the project evolves.
4. Phase 10 remains future quality/governance work; it is not silently completed
   by the validators and adversarial tests delivered here.
