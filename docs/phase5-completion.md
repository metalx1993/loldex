# Phase 5 implementation and operational boundary

Implemented under the 13 November 2026 delegation to finish LOLDEX through
Phase 6. The historical CORE, CP5.1, CP5.2 and A1 freeze artifacts are unchanged.
D1 is recorded separately in [phase5-d1.md](phase5-d1.md); this work does not
silently rewrite the frozen specification or claim an historical approval.

## Delivered modules

- `phase5/acquisition.py`: local Git commit/tree/blob verification, immutable
  byte bundles, source-specific complete discovery. No network fetch or clone.
- `phase5/observation.py`: pure five-source derivation, raw/claim/projection
  separation, exact health accounting, normalized path and ID reject-all,
  frozen stable identity and ownership shape, complete canonical observations.
- `phase5/runtime.py`: caller builder, exact delivery artifacts, captured tokens,
  stable POSIX lock, validation, fsync/temp/rename state persistence.
- `scripts/observe.py`: explicit local cycle and exact retry CLI.
- `tests/test_phase5_cp53.py`: source and runtime failure regressions. Independent
  adversarial cases are in `tests/test_adversarial_semantics.py`.

## Local operation

Provide local upstream Git repositories already acquired by the operator. A
repository's committed objects are authoritative, not its working tree. This
command changes only the explicitly selected state/artifact files, never
`data/entries`, site data, the remote branch or the public host:

```sh
python3 -m scripts.observe \
  --source GTFOBins=/absolute/path/to/GTFOBins.github.io \
  --source LOLBAS=/absolute/path/to/LOLBAS \
  --source LOLDrivers=/absolute/path/to/LOLDrivers \
  --source LOLAD=/absolute/path/to/LOLAD \
  --source WADComs=/absolute/path/to/WADComs.github.io \
  --state work/freshness/state.json \
  --observation work/freshness/observation-1.json
```

Sources not provided are represented by exact NOT_RUN results, not successful
empty sources. A provided repository that cannot be verified is represented by
exact ACQUISITION_FAILED. Non-ok sources hold evidence; they cannot credit
qualifying absence. A valid partial run can still commit an observation and
return a report: admission APPLIED does **not** mean every source was healthy.
Inspect `results[].status/primary_reason` in the finalized observation.

Retry using the exact same `--observation` file. No source is reacquired on that
path, and a post-commit retry returns IDEMPOTENT_NO_OP with null report. To begin
the next cycle, use a new artifact only after the previous cycle committed.
Do not submit two different canonical observations against one base token.
The runtime provides one live serial local builder; it is not a distributed
reservation service. After a crash before artifact finalization, automatic
reconstruction/reacquisition is deliberately not offered. A partial artifact is
rejected, never repaired or overwritten.

The persisted genesis is seeded from the repository's current `data/entries`
inventory exactly as CORE §12 specifies. Corpus size/hash is not an invariant.
State files and delivery artifacts should be kept outside deployable site data;
no automatic publication of health internals has been introduced.

## Verification and limitations

Focused tests exercise all five adapter observations through the frozen engine,
unknown taxonomy, typed YAML, empty-code siblings, malformed candidates,
normalized path/ID collisions, source health holds, builder reuse rejection,
exact retry, stale observation rejection, duplicate JSON keys, pre-rename and
post-rename failures. Independent tests include working-tree mutation, corrupt
or missing Git objects, symlink input and projection fingerprint constants.
The final delivery report records actual test counts/results.

No live upstream synchronization, corpus regeneration, corpus migration,
publication or production smoke test is claimed. The historical ID changes
implied by the closed D1 decisions are observable in freshness state only.
`ACQUISITION_FAILED` reports deliberately do not disclose local filesystem paths.
The runtime targets POSIX platforms supporting `flock` and same-filesystem
atomic rename; browser clients do not write state.

A2 remains separate: commit-atomic deployment and any cron reactivation require
their own implementation/review. Legacy `scripts.sync` remains unchanged and
must not be mistaken for the new verified observation path. CORE does not
publish, delete, choose terminal STALE, or introduce durable Phase-9 identity.
