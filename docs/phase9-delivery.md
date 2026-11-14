# Phases 7–9 — production acceptance

Accepted 14 November 2026. Phases 7, 8 and 9 are implemented, tested and published
on loldex.sh. Frozen CORE/D1 decisions remain unchanged. Phase 10 remains future.
Compact evidence: [phase9-acceptance.json](phase9-acceptance.json).

## Accepted implementation and snapshot

- Implementation: `5cd24ace1c19bee94d6d49fe10e1cc52a6297d9f`.
- Verified publication commit: `d7084febab348a96d6cb00b4a63db705992170c1`.
- Release: `r-a5d8d76297a9c31a459defa109ed7098578f89ffcfc82021436eabe904150b80`.
- Final activation after rollback/restoration: generation 11; all 3,369 release
  files verified on the host, including 3,336 source-evidence shards.
- Dataset: 3,336 entries; all five D2 publication sources `ok`, zero publication
  audit diagnostics. This does not declare a CORE transition.
- Initial identity coverage: three tool entities, fifteen active associations,
  seven separate candidates, one historical Certutil alias, zero inactive
  associations. This does not establish an identity for every catalogue entry.

## Acceptance results

| Gate | Observed result |
|---|---|
| Five-source acquisition, preflight, validation and rebuild | Passed; 3,336 entries, zero validation errors |
| Full GitHub test gate | **848 passed in 701.88 seconds** |
| Unchanged acquisition base and non-force Git publication | Passed |
| Trusted host acquisition, package integrity and atomic activation | Passed |
| API v1 resources, pretty routes, strict requests and original evidence | Passed over HTTPS |
| GET/HEAD, conditional 304 and retained-release binding | Passed over HTTPS |
| CORS through stable redirect and OPTIONS preflight | Passed over HTTPS and in a real cross-origin browser request |
| Catalogue, identities, OpenAPI, scripts and sampled evidence | Exact local/HTTPS byte matches |
| Advanced search, errors, pagination and explanations | Passed in Chromium on the published release |
| Identity witnesses, candidates, alias and source evidence | Passed in Chromium on the published release |
| Checked mobile pages at 320 px | No horizontal overflow or page, console or network errors in live checks |
| Actual root rollback and restoration | Passed; both retained URLs remain accessible |
| Legacy API | Passed; 3,336 entries |
| Cron | **OFF; ready for explicit activation** |

GitHub evidence: [successful run 43608361901](https://github.com/metalx1993/loldex/actions/runs/43608361901).
Its acquisition base was the implementation commit above; successful publication
produced the recorded snapshot commit. Subsequent acceptance-document and
browser-test-only commits do not change the accepted application/data tree.

Public entry points: [API v1](https://loldex.sh/api/v1),
[search](https://loldex.sh/search.html), [identities](https://loldex.sh/identities.html).

## Adversarial findings corrected

Cross-reviews cover claim/source/confidence correlation, opaque NOT scope,
ranking from eligible claims, bounded AST expansion and per-entry cache
isolation. The worst accepted nested query over the complete catalogue, with
facets and JavaScript/PHP parity, completed in approximately 0.8 seconds in the
local PHP 8.2 interpreter after correction; this is not a hosting SLA.

API attacks covered duplicate, array and malformed parameters, path-like IDs,
corrupted/missing files, conditional requests after corruption, retained-release
metadata removal and query-string attempts to forge immutable caching. Identity
attacks covered unrelated repositories, proxy/prefix tool names, duplicate YAML
keys, altered historical bytes/digests, ambiguous splits, stale witnesses and
false provenance. Raw evidence rendering preserves large numeric literals and
displays HTML as literal text.

An earlier local integration test copied the site before generation finished;
it passed when repeated after generation. Final CI ran acquisition, build and
all 848 tests in order and passed. Production browser checks also corrected a
test-only asynchronous wait for the alias link.

## Preserved semantics and next gate

CORE observes and classifies; D2 prepares publication snapshots. API/search/UI
read their bound release and never trigger acquisition or CORE transitions.
Freshness remains NOT_OBSERVED without validated CORE state. Provenance and
confidence belong to individual claims. Candidates and stale witnesses never
become active memberships; tool association does not equate techniques. Aliases
retain all explicit targets without choosing a split winner or inheriting
membership. Agent curation stays labelled as such. Historical Git commit/path
review is an offline review basis, not a runtime Merkle inclusion proof.

CORE specification SHA256 remains
`f79aed020b36d1a217b8091319be1e7ec7cf5ac48849c8d0b765a1523f2ef3e0`.

Site Tools was inspected on 14 November: no cron jobs exist for loldex.sh. The
GitHub schedule remains commented out. No scheduled cycle is claimed observed.
Next: explicitly activate the two prepared schedules and inspect their first
scheduled results; see [cron-activation.md](cron-activation.md). Phase 10
quality/governance operations are separate future work.
