# A2 and D2 — completed production acceptance

13 November 2026. **A2 and the five-source publication fixes are implemented,
reviewed and verified in production. Scheduling can now be enabled explicitly;
no cron was enabled by this work.**

## End-to-end result

[GitHub acceptance run 8](https://github.com/metalx1993/loldex/actions/runs/43518679145)
completed successfully: verified acquisition of all five sources, complete D2
snapshot preparation, validation of 3,336 entries with zero errors, rebuilding all
views, **783 Python tests passed in 356.15 seconds**, and unchanged-base/non-force
Git publication. Snapshot commit:
`be7ecfc7c8c3b84871b7bb9efcba51589a5644fe`, acquired and tested on base
`eaa8fa5e3eb19f28041e06362e43c2d08eee60bc`.

| Source | Published entries | Remaining diagnostics |
|---|---:|---:|
| GTFOBins | 1,898 | 0 |
| LOLBAS | 485 | 0 |
| LOLDrivers | 713 | 0 |
| LOLAD | 136 | 0 |
| WADComs | 104 | 0 |
| Total | 3,336 | 0 |

Exact upstream revisions, physical/logical accounting and independent emission/
evidence oracles are in `data/source-health.json`. The explicit D2 snapshot ledger
records 3,086 prior storage files retired from current search and 3,336 new files;
public identities are preserved inside bounded hashed storage names. Historical
bytes remain in Git history and retained host releases. LOLAD's 137 physical rows
become 136 logical entries only under the documented exact-cell coalescence,
retaining every original occurrence. No cross-source identity merge is performed.

## Real SiteGround proof

The trusted private publisher fetched the accepted GitHub commit, verified its
objects and dataset manifest, installed and activated release
`r-c569bac446139075188e3afe8b95b19b9fc13c38f4814d1cf6c3ccef81b3dea4`.
Its deterministic archive is 6,460,214 bytes, SHA-256:
`bf4d4155caa0399f550f6cd8ea473e4143372abe20ff99cf2241c615986f2b8d`.
An independently generated local package has the same release ID and bytes.

- Actual POSIX rename/fsync/flock, competing processes, injected pre-switch
  failure, retained assets and stale/ABA refusal passed on this filesystem.
- Isolated HTTPS switching and rollback passed. The initial 12-file legacy root
  was moved into a private SHA-256-inventoried backup. SiteGround's cached old
  homepage required an explicitly user-authorized purge, confirmed in Site Tools.
- Root/index/data/search/API/contact POST requests bind to one immutable version
  through 307/no-store; no real contact message was submitted.
- Twenty public static files matched package bytes. The host blocks the
  non-runtime build-manifest.json with 403; the publisher verifies it through
  authenticated filesystem access instead. PHP scripts are verified as files and
  the live API was exercised separately.
- Live API reports 3,336 entries. Live browser checks passed for search, filters,
  pagination, source evidence, technique/graph views, injection rendering and
  320-pixel layouts. A separate regression passed with a 589-character LOLAD ID,
  long URLs and provenance at 320/375/768/1440 pixels.
- The actual refreshed production release was rolled back to the previous
  complete version and restored, advancing generation to 7. HTTPS followed both
  changes correctly. Old version URLs still return the old 3,086-entry dataset;
  new version URLs return the new 3,336-entry dataset. No release was deleted.

Acceptance identifies the tested snapshot above. A later documentation-only
commit does not change any accepted site payload bytes; the private `status`
command is the authority for the currently selected commit/generation.

## Independent review and preserved contracts

Independent agents reproduced omissions, material/evidence tampering, false
confidence, raw/URL forgery, collisions, truncation, long-ID path failures,
late untracked/ignored-file deletion, URL/archive escapes, Git object relabeling,
retained hardlinks and stale concurrent publisher behavior. Relevant fixes and
regressions are committed. Additional final local full suite: 783 passed in
177.56 seconds. Router PHP checks ran in a real isolated PHP runtime and passed;
actual destination PHP syntax/API checks also passed.

The first GitHub acceptance attempt was deliberately cancelled before staging/
push: Phase 2 tests repeatedly reparsed 56.8 MB of YAML, and a raw-case test still
used the legacy driver field location. The corrected test reads original
Commands[].Privileges. The optimized test helper uses the same safe YAML parser
once per root and returns independent deep copies. Equality of all 3,336 records
and their order was independently verified; no test or assertion was removed.

Frozen CORE/D1 and its default derivation remain unchanged. CORE specification
SHA-256 remains `f79aed020b36d1a217b8091319be1e7ec7cf5ac48849c8d0b765a1523f2ef3e0`.
D2 publication health is not a retroactive successful D1 observation or CORE
freshness transition. The UI continues to show NOT_OBSERVED without a separately
validated CORE state. Initial migration does not retroactively version legacy
HTML already cached by clients. Actual mail delivery was not tested by sending
messages.

## Cron decision

**GO for explicit scheduling.** Both the GitHub full-refresh workflow and the
credential-free SiteGround pull publisher have passed their manual acceptance.
Site Tools showed no existing cron entries, and GitHub's schedule remains
commented out. The proposed two-operation schedule and exact host command are in
[cron-activation.md](cron-activation.md). No SSH private key was exported to GitHub,
no notification recipient was added, and no schedule was activated.
