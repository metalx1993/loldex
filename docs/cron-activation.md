# Cron activation — first automatic cycle in progress

Two operations have separate responsibilities and need no shared private key:

1. **GitHub verified source refresh**, proposed Monday 04:00 UTC. The existing
   commented `schedule` in `.github/workflows/sync.yml` is the only proposed
   source-update schedule. All five sources must pass D2 preflight and the full
   candidate test gate before the unchanged-base, non-force Git publication.
2. **SiteGround publication**, proposed every hour at minute 30 (`30 * * * *`).
   It reads committed public GitHub main using trusted installed publisher code.
   A failed refresh leaves main unchanged; a failed transfer, package check,
   main recheck or CAS leaves the active website unchanged. An already active
   commit is idempotent. This job never imports upstream adapter code or executes
   fetched application code during publication.

Exact SiteGround command (the private directory and cache already exist):

```sh
cd /home/customer/www/loldex.sh/loldex-control/tools && /bin/python3 -m deployment.pull --repo /home/customer/www/loldex.sh/loldex-control/repository.git --public-root /home/customer/www/loldex.sh/public_html --control-root /home/customer/www/loldex.sh/loldex-control >> /home/customer/www/loldex.sh/loldex-control/publisher.log 2>&1
```

Configure the host job through **Site Tools → Devs → Cron Jobs**; the SSH account
has no `crontab` executable. Do not assume a shell command installed a scheduler.
No email recipients, GitHub secrets or server schedules were added by this work.
Inspect GitHub Actions results and the private publisher log after the first
scheduled cycle. Keep all previous releases and the legacy private backup.

## Original A2/D2 acceptance — 13 November 2026

- Live A2 package verification, HTTPS activation and rollback: passed.
- Real five-source D2 candidate with zero diagnostics: passed, 3,336 entries.
- Manual GitHub full refresh and unchanged-base push: passed in run
  43518679145, with 783 tests passing.
- Trusted host pull of that refreshed commit, production rollback and final
  UI/API checks: passed. Live count 3,336; retained old count 3,086.

All acceptance gates are closed: GO for explicit activation. The full evidence
is in [a2-completion.md](a2-completion.md).

This file is an activation plan, not evidence that either schedule is enabled.

## Phase 7–9 readiness refresh — 14 November 2026

The new API/search/identity release passed 848 tests in GitHub run 43608361901,
live HTTPS and cross-origin browser checks, all-file host verification and actual
rollback/restoration. The identical host publisher command was repeated with no
change to the active generation. See [phase9-delivery.md](phase9-delivery.md).

GO for explicit activation. GitHub scheduling remains commented out; Site Tools
was inspected and has zero jobs for loldex.sh. Neither schedule was enabled. A
manual equivalent cycle passed; no actual scheduled execution is claimed.

## Authorized activation — 14 November 2026

The user explicitly requested both schedules and the first complete automatic
cycle. GitHub scheduling is enabled by this change: Monday 04:00 UTC plus a
temporary date-bound acceptance trigger at 16:07 UTC on 14 November. Remove the
temporary trigger after the complete automatic cycle is observed. The normal
weekly schedule remains. SiteGround activation is being completed in Site Tools.

Planned SiteGround jobs: the normal hourly publisher at minute 30 and a temporary
acceptance publisher at 16:47 UTC on 14 November, leaving time for the full
GitHub acquisition/build/test gate. No workflow_dispatch or manual SSH publisher
run will count as evidence of an automatic cycle. Status and evidence below will
be completed from the actual scheduler executions. SiteGround uses UTC; see
[official timezone documentation](https://www.siteground.com/kb/how_to_adjust_the_time_zone_on_the_server).

Site Tools creation confirmed: hourly job `30 * * * *`, temporary acceptance job
`47 16 14 11 *`. The temporary job writes a dedicated private
`first-automatic-cycle-20261114.log`; the regular job writes `publisher.log`.
Both invoke the reviewed trusted publisher. GitHub activation commit:
`a84c0a92ac5b49ef46f8632bf6a7c1af0b6b1d0d`. Verification is pending actual events.

The 16:07 UTC GitHub acceptance slot had no observable schedule event through
16:25 UTC. This is not recorded as a successful run or a failed test run. The
verification trigger is moved to 17:07 UTC on 14 November to give the scheduler
more lead time. The temporary SiteGround verification is being moved to
17:47 UTC; the weekly GitHub and hourly SiteGround schedules remain unchanged.
