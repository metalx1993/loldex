# Cron activation plan — schedules currently disabled

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

## Acceptance prerequisites

- Live A2 package verification, HTTPS activation and rollback: passed.
- Real five-source D2 candidate with zero diagnostics: passed, 3,336 entries.
- Manual GitHub full refresh and unchanged-base push: final run outcome must be
  recorded in a2-completion.md before scheduling.
- Trusted host pull of that refreshed commit and final UI/API checks: final
  outcome must be recorded before scheduling.

This file is an activation plan, not evidence that either schedule is enabled.
