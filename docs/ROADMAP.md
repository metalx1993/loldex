# LOLDEX — delivery roadmap

Updated 13 November 2026. This replaces historical progress summaries as the
implementation index; it does not replace any frozen normative CORE clause.

## Delivered locally through Phase 6

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

The new work was locally implemented and independently reviewed before the
requested GitHub upload. Production deployment and historical gatekeeper
approvals are separate. Final verification is in DELIVERY.md.

## Exact boundaries

- CORE observes and classifies. It does not publish or delete catalogue entries.
- Observation uses verified local upstream Git repositories explicitly supplied
  to scripts.observe. No implicit live fetch, refresh or mutable-worktree trust.
- The checked-in corpus remains unchanged. Historical D1 identity changes are
  not silently migrated into public entry IDs.
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

## After this delivery

1. Review the changes and preview before deciding the production publication strategy.
2. A2/D2 production acceptance is complete. Enable the prepared schedules only
   on explicit request; see cron-activation.md.
3. Phase 7: stable, versioned public knowledge API (basic legacy APIs already exist).
4. Phase 8: advanced and explainable search.
5. Phase 9: durable cross-source identity/clusters without destructive deduplication.
6. Phase 10: broader ongoing quality and governance operations.

Those future phases are not required to claim this delivery through Phase 6 and
are not silently marked complete by the presence of today's graph or tests.
