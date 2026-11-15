# Cron activation — first automatic cycle in progress

Two operations have separate responsibilities and need no shared private key:

1. **GitHub verified source refresh**, enabled Monday 04:00 UTC. The `schedule` in `.github/workflows/sync.yml` defines the
   source-update schedule. All five sources must pass D2 preflight and the full
   candidate test gate before the unchanged-base, non-force Git publication.
2. **SiteGround publication**, enabled every hour at minute 30 (`30 * * * *`).
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
No email recipients or GitHub secrets were added; the authorized server jobs
were installed through Site Tools.
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

The original acceptance above predates activation. Current operational evidence
is recorded below; configuration alone does not prove a complete automatic cycle.

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


## Observed scheduler execution — 14 November 2026

The normal SiteGround job executed automatically at 16:30:21 UTC and again at
17:30:17 UTC. The first execution activated generation 12, commit
`cbcab282d304b0ba7057520bd245b25f4569018f`, release
`r-39200d452631f79d564a4fa99f7edaebd1a2a7733ec24dc67998830ea49bddd5`.
The second execution preserved that generation idempotently. HTTPS API checks
confirmed the same release and 3,336 entries. Neither execution was manually
invoked. This proves the host scheduler; it does not prove an automatic source
refresh on GitHub. The publisher result's legacy `scheduler_enabled: false`
means the publisher command does not install a scheduler; Site Tools config and
actual timed log entries establish the host schedule's state.

No GitHub `event: schedule` run was observable through 17:36 UTC. No failed test
run is inferred from an absent event. A native GitHub editor commit
`f2359201a3a9169f670d760761d66da41b042057` added a separate temporary 17:37 UTC
verification slot without removing the earlier 17:07 slot. This is a diagnostic
probe, not evidence of a known cause or a completed cycle. Only one cron line
changed; the six focused integration checks passed. SiteGround's temporary
verification job is now `47 17 14 11 *`; its log was still absent at 17:33 UTC.
All temporary entries must be removed after verification. The normal weekly
GitHub and hourly SiteGround entries remain enabled.


At 17:47:19 UTC the temporary host job also executed automatically, acquired
`f2359201a3a9169f670d760761d66da41b042057`, and activated generation 13, release
`r-e1e84862c2c02ed166e92f5499b1a65a401cadb01ec09ed9deced85885711115`.
This is a configuration-only descendant of the accepted dataset, not a new
GitHub scheduled source-refresh snapshot. The full automatic chain remains
pending a real GitHub schedule event. Removal of the temporary SiteGround job
was blocked by automatic approval review and a specific user confirmation was
requested; the normal hourly job remains enabled.


### Current operational boundary — 17:49 UTC

After the user's specific confirmation, Site Tools removed only the temporary
host job and displayed success. The single remaining job is `30 * * * *`, with
`publisher.log`. Expired GitHub diagnostic slots are removed by this report's
commit to prevent annual recurrence; the normal Monday `0 4 * * 1` stays enabled.
No `event: schedule` run was observable at 17:49 UTC, including after the native
editor probe. The cause is not established. Both normal schedules are configured,
but **full automatic source-refresh → test → GitHub snapshot → host publication
acceptance remains open**. A manual dispatch is not a substitute. Next acceptance
requires an actual successful scheduled GitHub run and subsequent automatic host
activation of its snapshot, followed by live checks. No background monitor is
installed by this work.

Live checks after the 17:47 host execution passed: eleven API resources, stable
routing, HEAD/304, cross-origin/preflight, invalid-query errors and sampled static
file equality; the dataset remains 3,336 entries. See
[cron-activation-observed.json](cron-activation-observed.json).

## Follow-up — 15 November 2026

GitHub's schedule-event runs endpoint still returned zero runs. The current
remote workflow contains only the normal weekly `0 4 * * 1` schedule: its next
configured time is Monday 16 November at 04:00 UTC (05:00 Europe/Rome), not
Sunday morning. This is an expected slot, not a guarantee of execution. The
earlier temporary probes remain historical unobserved slots.

SiteGround has automatically acquired the latest available commit
`5ac395121777e4abdf4ca662062518bff6ea31b9`: active generation 14, release
`r-45c5d35c436fa592310637a993910c4accddef880245b98fef50d435eeea0c79`.
The hourly publisher log recorded a successful idempotent execution at
07:30:18 UTC (08:30 Europe/Rome). Live API/resource, routing, HEAD/304,
CORS/preflight, invalid-query and sampled static-file checks passed again,
with 3,336 entries. No manual dispatch or publisher invocation was performed.

**The complete automatic chain remains pending a genuine scheduled GitHub
refresh and subsequent scheduled host publication of that snapshot.** No new
temporary schedule or background monitor was installed. Current evidence:
[cron-check-2026-11-15.json](cron-check-2026-11-15.json). Phase 10 planning starts
separately in [phase10-plan.md](phase10-plan.md); it does not close this gate.
