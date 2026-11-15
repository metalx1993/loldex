# Phase 10 — review, correction and operational evidence

This document defines the usable maintenance procedure for the delivered tools.
It does not amend frozen CORE/D1, change a confidence taxonomy, infer freshness,
merge source occurrences or authorize a new schedule. Continuous maintenance is
not something that a one-time acceptance can permanently finish.

## Roles and decisions

- **Reporter** supplies an affected entry/claim, source path or public resource,
  exact input revision, expected versus observed behavior and reproduction.
- **Maintainer** reproduces in an isolated fixture, identifies the affected
  source_data/enrichment/projection layer and classifies the impact.
- **Reviewer** checks the correction against original source evidence and tests,
  including negative cases; the review records unresolved limitations.
- **Operator** correlates actual GitHub, SiteGround and HTTPS evidence before
  recording operational acceptance. A maintainer may perform several roles, but
  the correction's author must not be its independent reviewer. Identify which
  role made each decision; tool output is not a reviewer.

Record each case in an issue or retained local review document with these fields:
`case_id`, `reported_at`, `reporter_role`, `affected_revision`, `affected_ids`,
`source_references`, `reproduction`, `expected`, `observed`, `impact`,
`maintainer_role`, `decision`, `decision_reason`, `fix_revision`, `tests_run`,
`reviewer_role`, `verification_evidence`, `remaining_limits`.

Decision states are **insufficient evidence**, **reproduced**, **accepted for
correction**, **rejected with reason**, **fixed awaiting verification**, and
**verified within stated scope**. These are case workflow states, not new CORE
freshness states or entry confidence levels. Do not mark verified from a proposed
patch, guessed outcome or merely green status badge. Do not copy private keys,
tokens, private server paths unrelated to this project or personal data into
public issues. Keep raw private observations outside the published site.

### Triage and correction

1. If a discrepancy compromises layer separation, provenance/confidence,
   identifier integrity, tested-tree publication or release integrity, stop the
   affected candidate/publication from being accepted. Existing valid releases
   remain available. Preserve evidence before editing anything.
2. If the failure is a missing optional mapping, unsupported source format or a
   search/UI limitation, record the exact scope. Missing optional enrichment is
   not fabricated, and source publication health is not CORE observation health.
3. Correct in the responsible layer. Preserve upstream raw evidence; an adapter
   interpretation needs its own claim provenance and confidence. A schema or
   frozen-contract change needs a separate explicit design decision, not a quiet
   expansion during a bug fix.
4. Add a reproducer that fails before the correction and passes afterward. Add
   the opposite/negative case when a permissive interpretation caused the bug.
   Re-run the affected tests and the relevant build/schema contracts. Broader
   changes require the full regression gate; do not reduce tests to save time.
5. Review actual diff, test results and remaining limits. Publish only a committed
   reviewed tree. A live change also needs A2 verification, stable root routing,
   API checks and retained rollback availability. Record exact revisions.

**Acceptable report:** at a named revision, claim `capabilities[0]` on entry X
has upstream provenance Y but no confidence; a retained fixture reproduces the
validator failure. Correct the responsible adapter and add a negative test.

**Insufficient report:** “source X looks stale” with no observation or revision;
“all records are verified” from a single successful download; identity candidate
similarity used as approval to merge occurrences. Ask for the missing evidence;
do not promote confidence, suppress errors or rewrite raw source payloads.

## Operational evidence checker

Run offline, with a retained normalized evidence file:

```sh
python3 -m scripts.check_operational_cycle work/automatic-cycle-evidence.json
```

The command reads JSON and prints JSON. Exit codes: **0** for
`VERIFIED_CHANGED` or `VERIFIED_NO_CHANGE`, **2** for `PENDING`, **1** for `FAIL`.
No network access, sync, deployment, notification, scheduler change or repair is
performed. Duplicate JSON keys, unknown fields and contradictory complete
captures are rejected. Missing/null required sections are pending, never green.
A present manual/non-schedule run, failed run or manually rerun attempt fails
before missing downstream sections can disguise it as a successful cycle.

**Trust boundary:** `VERIFIED_*` means consistency of supplied evidence only.
The tool does not authenticate capture origins, signatures, scheduler history or
whether a collector told the truth. An operator must retain and independently
review the original authenticated GitHub API/log captures, commit/tree objects,
Site Tools schedule configuration, private publisher log/status and HTTPS
responses. Hashes are references to those retained bytes, not proof of origin.
Synthetic unit-test fixtures are not production acceptance evidence. A changed
or fabricated normalized file can never replace that review.

### Version 1 evidence contract

Top-level exact keys: `version` (integer 1), `repository` (`metalx1993/loldex`),
`run`, `job`, `candidate`, `snapshot`, `publication`, `host`, `live`. The seven
sections may be null while evidence is unavailable. SHA fields are lowercase
40-hex Git object IDs; SHA-256 fields are lowercase 64-hex digests. IDs and
publication generations are positive integers (booleans are refused). Times
are ISO-8601 strings with explicit timezone.

| Section | Exact fields and required correlation |
|---|---|
| run | `id,event,status,conclusion,head_branch,head_sha,workflow_path,run_attempt,started_at,completed_at`. Must be the original attempt 1 of `schedule`, main, `.github/workflows/sync.yml`, completed successfully. Queued/in-progress valid scheduled runs remain pending. |
| job | `id,run_id,head_sha,status,conclusion,steps`. Run ID/head must match the run, and job must succeed. Each step has `number,name,status,conclusion`; names and positive numbers are unique and ordered. All workflow gate names in `STEPS` must occur in order and succeed; the publication step must instead be skipped only for the independently demonstrated no-change case. |
| candidate | `base_sha,base_tree_sha,tree_sha,changed`. Base must equal tested run head; tree comes from the candidate's staged Git tree, with a real boolean change result. Capture base/stage information from that same job, not a later local build. |
| snapshot | `sha,parents,tree_sha`. Changed snapshot must have exactly the acquisition base as its one direct parent, a different SHA and changed tree. Its tree must equal the tested candidate tree. No-change requires unchanged base SHA and tree; no new snapshot publication is claimed. Preserve the commit object's actual parent list. |
| publication | `run_id,job_id,remote_sha,log_sha256`. IDs identify the same run/job; remote SHA equals snapshot SHA; digest identifies retained log bytes. For no-change, capture the unchanged remote SHA separately after staging. |
| host.schedule | `id,command_sha256,cron,observed_at`. Site Tools job identity, `30 * * * *`, and digest of the exact reviewed command below. Configuration must have been observed before execution. A digest of an unrelated command is rejected. |
| host.execution | `job_id,started_at,completed_at,log_sha256,commit,release_id,generation`. Job identity matches the saved schedule. Preserve scheduler-origin evidence; a manually invoked publisher is not such evidence. Commit matches snapshot; times follow successful GitHub completion. Digest identifies the private log capture. |
| host.active | `commit,release_id,generation,observed_at`. Actual status token matches the publisher receipt, and was read after execution completed. |
| live | `release_id,observed_at,root_redirect,requests`. Release matches active token and capture follows the active-token observation. `root_redirect` has `url,status,location`: root API `https://loldex.sh/api/v1/entries?limit=1` must return 307 to this exact release's `/api/v1/entries?limit=1`. Each request has `url,status,release_id,body_sha256`: pinned same-release URL, 200 response, matching dataset release and retained body digest. The redirect destination itself must be checked. |

The exact host command whose UTF-8 SHA-256 is accepted is exported as
`PUBLISHER_COMMAND` / `PUBLISHER_COMMAND_SHA256` in the checker:

```sh
cd /home/customer/www/loldex.sh/loldex-control/tools && /bin/python3 -m deployment.pull --repo /home/customer/www/loldex.sh/loldex-control/repository.git --public-root /home/customer/www/loldex.sh/public_html --control-root /home/customer/www/loldex.sh/loldex-control >> /home/customer/www/loldex.sh/loldex-control/publisher.log 2>&1
```

Do not edit a captured command to match this string. A legitimate command or
workflow evolution needs reviewed profile/version changes and corresponding
negative tests. The checker conservatively requires acquisition base = run head;
a run that checked out a later main revision needs a separate explained review,
not manufactured matching metadata.

For a missing scheduled run, use this genuine pending envelope (not a fake
successful fixture):

```json
{"version":1,"repository":"metalx1993/loldex","run":null,"job":null,"candidate":null,"snapshot":null,"publication":null,"host":null,"live":null}
```

### Capture and recovery procedure

The workflow logs `acquisition_base_sha`, `acquisition_base_tree_sha`,
`candidate_tree_sha`, and `candidate_changed` in their corresponding steps.
Map these to `candidate.base_sha`, `base_tree_sha`, `tree_sha`, and `changed`.
After a successful changed push, `published_commit_sha` identifies the snapshot;
retain the GitHub commit/tree object independently. For no-change the publication
step is skipped, so observe the unchanged remote SHA separately as required above.
The quality gate prints its result/count/input fingerprint; its complete JSON is
only in RUNNER_TEMP and is not a permanently retained Actions artifact. Keep any
additional captures explicitly; do not claim unretained per-file reports exist.

1. Read the actual GitHub schedule event collection. Record run ID, event,
   attempt, workflow, branch, head and timestamps. A configured cron or manual
   `workflow_dispatch` is not automatic-cycle acceptance. An expected future
   slot is not a missed/failed job. If no run exists, keep `PENDING`; do not
   invent a failure reason or repeatedly change schedules without diagnosis.
2. Once complete, retain that run's job/steps and logs, recorded acquisition base,
   staged tree and changed/no-change result. Fetch the committed snapshot object
   and unchanged-base relationship from Git. Full tests must actually succeed;
   a previously accepted manual run does not cover this new execution.
3. Observe the existing host scheduler and private log. Link the exact job,
   publisher result, snapshot and active token. The publisher's historical
   `scheduler_enabled:false` field only means that command installs no scheduler;
   it is not Site Tools configuration evidence in either direction.
4. Capture root routing and pinned HTTPS API response from the active release,
   including the returned dataset release ID. Verify release-file hashes through
   the A2 package/host verification where required; API check alone does not
   certify all-file integrity. Correlate evidence offline, then record operator
   review and its limits separately from the tool's result.
5. If acquisition/validation/tests fail, preserve the current published snapshot
   and evidence, reproduce with a fixture and correct the cause. If main moved,
   discard the staged candidate and let a fresh cycle reacquire against the new
   base. Do not rebase or force-push a candidate produced under old code.
6. If host package verification, remote-main recheck or CAS fails, inspect actual
   status before retrying. Preserve the active valid release and diagnostics.
   A post-rename durability error may leave the new release authoritative: never
   assume that an error implies no activation happened.
7. For an authorized rollback, follow [A2 runbook](a2-siteground-runbook.md): read a
   **new** expected-token file from current status, explicitly select a retained
   approved release and invoke rollback with that token. Verify root, pinned
   APIs/static files and generation afterward. A stale token is refused; do not
   silently refresh it inside a retry. Never edit immutable release files or
   delete retained releases to make a check green.

The A2 runbook's initial scheduling warnings describe its historical preparation
stage; current configuration/acceptance is in [cron-activation.md](cron-activation.md).
Keep actual operational acceptance separate from local code/tool acceptance.
The absence of a genuine scheduled GitHub run remains an open production gate,
not a reason to claim that local Phase 10 tools have already observed that run.


## SYNTHETIC complete specimen — not production acceptance

The following is an artificial consistency fixture with repeated fake Git SHAs,
release IDs and log/body digests. Its future timestamps are invented, not an
observed scheduled execution. It demonstrates the exact version-1 envelope only.
Do not relabel it as live evidence. The independently generated tests use the
same shape in `tests/test_operational_cycle.py::valid_evidence`.

```json
{
  "version": 1,
  "repository": "metalx1993/loldex",
  "run": {
    "id": 123,
    "event": "schedule",
    "status": "completed",
    "conclusion": "success",
    "head_branch": "main",
    "head_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "workflow_path": ".github/workflows/sync.yml",
    "run_attempt": 1,
    "started_at": "2026-11-16T04:00:00Z",
    "completed_at": "2026-11-16T04:20:00Z"
  },
  "job": {
    "id": 456,
    "run_id": 123,
    "head_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "status": "completed",
    "conclusion": "success",
    "steps": [
      {
        "number": 1,
        "name": "Checkout main",
        "status": "completed",
        "conclusion": "success"
      },
      {
        "number": 2,
        "name": "Set up Python",
        "status": "completed",
        "conclusion": "success"
      },
      {
        "number": 3,
        "name": "Install dependencies",
        "status": "completed",
        "conclusion": "success"
      },
      {
        "number": 4,
        "name": "Install isolated PHP test interpreter",
        "status": "completed",
        "conclusion": "success"
      },
      {
        "number": 5,
        "name": "Record acquisition base",
        "status": "completed",
        "conclusion": "success"
      },
      {
        "number": 6,
        "name": "Acquire five public upstream repositories",
        "status": "completed",
        "conclusion": "success"
      },
      {
        "number": 7,
        "name": "Prepare complete verified D2 snapshot and all derived views",
        "status": "completed",
        "conclusion": "success"
      },
      {
        "number": 8,
        "name": "Validate entries",
        "status": "completed",
        "conclusion": "success"
      },
      {
        "number": 9,
        "name": "Rebuild validated site and knowledge data",
        "status": "completed",
        "conclusion": "success"
      },
      {
        "number": 10,
        "name": "Read-only generated-data quality gate",
        "status": "completed",
        "conclusion": "success"
      },
      {
        "number": 11,
        "name": "Hard test gate",
        "status": "completed",
        "conclusion": "success"
      },
      {
        "number": 12,
        "name": "Stage candidate",
        "status": "completed",
        "conclusion": "success"
      },
      {
        "number": 13,
        "name": "Publish only onto the unchanged acquisition base",
        "status": "completed",
        "conclusion": "success"
      }
    ]
  },
  "candidate": {
    "base_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "base_tree_sha": "cccccccccccccccccccccccccccccccccccccccc",
    "tree_sha": "dddddddddddddddddddddddddddddddddddddddd",
    "changed": true
  },
  "snapshot": {
    "sha": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "parents": [
      "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    ],
    "tree_sha": "dddddddddddddddddddddddddddddddddddddddd"
  },
  "publication": {
    "run_id": 123,
    "job_id": 456,
    "remote_sha": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "log_sha256": "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
  },
  "host": {
    "schedule": {
      "id": "host-job-1",
      "command_sha256": "cebd336b5bed53ee1a975fc762a14728c460d812b56502c9d23a0ad92b358a66",
      "cron": "30 * * * *",
      "observed_at": "2026-11-15T08:00:00Z"
    },
    "execution": {
      "job_id": "host-job-1",
      "started_at": "2026-11-16T04:30:00Z",
      "completed_at": "2026-11-16T04:31:00Z",
      "log_sha256": "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
      "commit": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "release_id": "r-eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
      "generation": 15
    },
    "active": {
      "commit": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "release_id": "r-eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
      "generation": 15,
      "observed_at": "2026-11-16T04:31:10Z"
    }
  },
  "live": {
    "release_id": "r-eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
    "observed_at": "2026-11-16T04:32:00Z",
    "root_redirect": {
      "url": "https://loldex.sh/api/v1/entries?limit=1",
      "status": 307,
      "location": "https://loldex.sh/releases/r-eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee/api/v1/entries?limit=1"
    },
    "requests": [
      {
        "url": "https://loldex.sh/releases/r-eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee/api/v1/entries?limit=1",
        "status": 200,
        "release_id": "r-eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
        "body_sha256": "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
      }
    ]
  }
}
```
