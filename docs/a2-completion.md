# A2 / D2 observed acceptance — 13 November 2026

## Executed evidence

- Full Python suite: 754 passed (331.48 seconds), collected before the last
  independent additions; later focused reviews are recorded below/in final report.
- Router PHP regression: real isolated PHP runtime checks passed for 307,
  no-store, query/POST preservation, malformed state and release binding.
- Live browser: search, filters, pagination, source disclosure, technique views,
  graph rendering, 320-pixel layout and injection rendering passed on loldex.sh.
- Actual SiteGround private filesystem: rename/fsync/flock, competing processes,
  injected pre-switch failure, rollback, retained assets and ABA rejection passed.
- Isolated HTTPS fixture: visible A/B activation and rollback, old version URLs,
  query and POST preservation passed. No real contact message was submitted.
- Production root migrated with a 12-file SHA-256 inventory and private backup.
  Dynamic cache purge was explicitly authorized and Site Tools confirmed success.
  Plain root, index, data, search, API and contact POST requests now yield 307 with
  no-store to the selected immutable release.
- Initial production release is bound to commit
  `140ecb96cfc2593d568b25e6c5c471ab12ad15e8`; generation 1. Its 20 accessible
  static files match package bytes. Hosting blocks build-manifest.json with 403;
  that non-runtime manifest is verified through SSH.
- Live D2 source proof: all five verified pinned upstreams passed with zero
  diagnostics, yielding 3,336 entries. All knowledge/UI datasets built together
  successfully. This is publication health, not a CORE freshness transition.

## Defects exposed by independent attempts

Git replacement/object corruption, retained hardlinks, stale-token no-op/ABA,
unsafe archive/URL escaping, SiteGround direct static delivery and stale dynamic
cache, alias/inherit and identity collisions, data truncation, raw evidence
forgery, confidence escalation, normalizer omission, second-pass ID mutation,
long-ID storage paths, and deletion of late untracked/ignored files were tested.
The implementation now rejects these failure paths or applies the documented
explicit source-format/migration amendment. Frozen D1 tests remain unchanged.

## Scheduling boundary

No cron is enabled. GitHub's manual workflow is the full verified source-refresh
publisher; SiteGround's optional trusted pull command publishes committed site
artifacts without exporting a private SSH key to GitHub. Manual acceptance of
both operations must precede enabling their schedules. No claim of a successful
GitHub Actions run or final refreshed production activation is made until its
specific observed outcome is recorded.
