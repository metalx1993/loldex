# A2 — Source health before publication

Implemented staging and D2 snapshot publication gate. Cron remains disabled
until the manual end-to-end acceptance is complete. Live source and hosting
evidence is recorded in a2-design.md and the delivery report.

## Why atomic site activation is insufficient

The former manual sync workflow invoked legacy `scripts.sync`, which fetched or
reused temporary working trees and wrote public entry YAML directly. The updated
workflow uses `scripts.verified_refresh` with the explicit publication-v2 profile. An atomic
website release prevents mixed files at the host; it does not prove upstream
completeness, source health, or that the published bytes came from the verified
acquisition object. A detached preflight check followed by a fresh legacy fetch
would reopen that gap.

## Gate and byte binding

`deployment.source_health.check_source_health(repositories)` requires a mapping
of all five exact source names to `(local Git repository, revision)` tuples.
It resolves and verifies immutable bundles using the Phase 5 acquisition module,
then derives the complete CP5.3 AdapterResult for every source. It returns
`(bundles, results)` only if **all five** have `status == ok` **and zero unmapped
diagnostics**. This stricter publication policy leaves CORE health unchanged: a
non-suppressing diagnostic can remain `ok` for observation while requiring review
before publication. Unknown source keys
are errors. Missing sources become NOT_RUN; failed acquisitions become
ACQUISITION_FAILED. Any partial/failed/unknown source rejects the whole gate;
`SourceHealthError.results` retains the canonical per-source evidence.

This checks source health only. It does not evaluate CORE freshness state,
compare newly canonical D1 IDs with historical public IDs, or infer removals.
Different ID schemes must not manufacture false absence or migration authority.

`prepare_verified_sync(repositories, output)` passes those **same bundle bytes**
to the existing public adapters' `normalize()` methods through read-only
`MemoryPath` objects. It never calls `fetch()` or `run()`, and never reads source
working-tree files after verification. For LOLAD HTML comes from the bundle; for
LOLBAS the tuple includes the verified folder and memory-backed file; the other
sources receive memory-backed files. Each source declaration records the full
verified commit revision.

The public output retains the existing adapter ID/projection policy. The new D1
canonical IDs remain within the CORE observation lane. This is an explicit
compatibility bridge, not a claim that public legacy IDs equal CORE identities.
It must not be used as a shortcut to silently migrate the corpus.

Before creating output, the bridge materializes every public emission, validates
the closed taxonomies, layers, provenance/confidence and projection equality,
and checks global NFC-normalized public ID and encoded filename uniqueness.
Source declarations, raw evidence, per-claim source/adapter revision and raw
source hashes must all agree with the verified acquisition. The four-key Phase 1
projection metadata contract is checked explicitly; heuristic claims retain their
low confidence and explanatory note.
A duplicate aborts the entire candidate: no first/last winner. The bridge also
compares the per-source **multiset of material fingerprints** from verified CORE
emissions with the public candidate material fingerprints, preserving multiplicity.
Entry IDs are excluded from CORE §14 material, so this check neither maps nor
compares the two ID schemes. Missing, extra or materially different public
emissions abort; counts are derived from the current bundle, never historical
snapshots. Unsafe filenames,
normalization exceptions, invalid output or empty public candidate also abort.
The gate is explicit Python control flow and does not rely only on assertions
that disappear under optimized Python.

## Staging output and caller responsibilities

The output must not exist and must be outside the live repository `data/` tree.
Health and normalization failures create no output. The bridge exclusively
creates a new staging directory and writes:

```text
candidate/
  data/entries/<platform>/*.yaml
  source-health.json
```

The source-health completion report is written last. An output write failure
removes only the new directory owned by this invocation, leaving existing output
and siblings intact. A process crash can leave incomplete staging: callers must
require successful process exit and the completion report, never treat directory
existence as publication authority. No existing directory is replaced.

A staged corpus is **not** a publish instruction. Before publishing, callers must:

1. Run full schema, projection, knowledge-graph and site-build validation on the
   staged entries and build all views from that same candidate.
2. Review historical entries not emitted by the candidate. CORE grants no
   automatic deletion or migration authority; blindly replacing the old corpus
   with this emission set would introduce a separate removal policy.
3. Bind the candidate and tested code to the unchanged acquisition Git base,
   preserving A1's no-rebase/non-force publication checks.
4. Use the reviewed A2 release/activation mechanism and verify the actual host.
5. Keep cron disabled until source-health and publication integration have both
   passed their independent gates. The current legacy workflow is not silently
   switched to this preparation command.

Example preparation from operator-provided local repositories:

```sh
python3 -m scripts.prepare_verified_sync \
  --source GTFOBins=/absolute/local/GTFOBins.github.io \
  --source LOLBAS=/absolute/local/LOLBAS \
  --source LOLDrivers=/absolute/local/LOLDrivers \
  --source LOLAD=/absolute/local/LOLAD \
  --source WADComs=/absolute/local/WADComs.github.io \
  --output work/candidate-1

python3 -m scripts.build_all \
  --entries work/candidate-1/data/entries \
  --out work/candidate-1/site
```

The preparation CLI performs no fetch, live corpus write, commit, push or deploy.
The full candidate still needs the checks above before any publication.

## Known reference blockers and honest readiness

The archived D1 evidence documents a LOLBAS cross-folder ID collision and an
identical LOLAD natural-identity triple. Under the approved reject-all policy,
these yield failed source results. Also, a WADComs unknown attack type is
non-suppressing (`ok`) under CORE but would trigger a legacy discovery fallback
whose explanation falsely says no types were stated. The publication-only zero-
diagnostic gate blocks that case. A driver with empty Tags can similarly be
healthy in CORE with material name omitted, while legacy normalization falls back
to Id; the material-emission parity check blocks this divergence even though no
diagnostic is present. If those upstream states are supplied, this
gate **must abort**. Healthy synthetic fixtures passing are not evidence that
current live upstream states are healthy. No live fetch was performed here.

A2 host activation also requires capabilities independently verified on the real
hosting environment. An FTP-only connection does not establish POSIX SSH,
server-side atomic activation or rollback support. A dry run or local test does
not certify the production host or authorize cron reactivation.

## Regression evidence

`tests/test_publication_health.py` covers each source failing acquisition and
being partial; missing sources; source collisions; mutation of working-tree bytes
between the gate and normalization; forbidden additional fetch; duplicate public
IDs and filename collisions; expected material-emission multiplicity and content;
legacy display-name fallback divergence; forged provenance; existing output protection; cleanup of owned staging on write failure; and
no CORE state mutation. The delivery report records the final executed counts.

## D2 update — explicit opt-in publication profile

The default gate described above remains D1. `--profile publication-v2` applies
the documented [D2 amendments](phase5-d2-publication.md), preserving every frozen
CORE/D1 behavior. Every D2 source has an independent preflight oracle, checking
exact public identity/material and claim/raw-evidence expectations before a
normalizer can authorize publication. The staging pass binds identities and full
evidence again, in addition to material multiplicity and the existing taxonomy/
projection checks. Alias-only GTFO documents have explicit accounted zero emission;
LOLAD exact duplicates retain all physical occurrences, not a first/last winner.

D2 filenames use `<source>__<sha256(public_id)>.yaml` unconditionally; the public
ID itself remains intact. This is a bounded storage encoding, not identity
deduplication. The gate still detects ID and filename collisions globally. The
new complete-snapshot retention policy is explicit in D2, with a publication
ledger and previous Git commits/immutable releases preserved.
