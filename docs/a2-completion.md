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

## Production A2 closure

The trusted pull publisher was executed manually on the actual SiteGround host.
It fetched verified public GitHub main commit
`b46fa27b549efad827f1bd6153f722c4a028fb6c` and activated release
`r-e1c8ce1c0332ea6236dc2e4564dbce609dabfde09ffa71461e643f669fc791ab`.
Actual root HTTPS was checked after rollback to the preceding complete release
and after restoring this release. Generation advanced to 4; both version URLs
remained readable and root redirects remained 307/no-store. This closes the
production A2 switch/rollback gate, separately from refreshed-source publication.

The last focused suites passed: 123 source/integration tests and 11 pull-publisher
checks. A GitHub manual full-refresh acceptance run was requested successfully:
https://github.com/metalx1993/loldex/actions/runs/43513579159 . Its final outcome
must be recorded before scheduling readiness is declared.

The first GitHub refresh run was deliberately cancelled before staging/push:
full-corpus Phase 2 tests repeatedly reparsed 56.8 MB of YAML and one raw-case
regression still used the legacy driver field location. No candidate was committed.
The test locator now reads original Commands[].Privileges. The test corpus loader
uses the same safe YAML parser once per root and returns deep independent copies.
An independent equality scan verified all 3,336 records and their order against
the old implementation: cold read 45.389 s, 15 subsequent prefix queries 1.712 s.
No assertions, source checks or test cases were removed.

Also corrected a real 320-pixel layout overflow from long D2 identifiers and
source URLs using two targeted wrapping rules. Browser checks passed on the full
candidate, including the 589-character LOLAD ID at 320/375/768/1440 pixels.
