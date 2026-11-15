# Quality review and correction procedure

Phase 10 delivers tools and repeatable procedures. Ongoing review is an
operational responsibility; a passing report does not certify every claim or
complete the independently tracked first scheduled production cycle.

## Roles and decision record

The reporter supplies a reproducible case. A triager records the affected layer,
scope and impact. An implementer proposes the smallest correction. A reviewer
checks the evidence, contract and tests independently of the author. A maintainer
records acceptance or rejection and controls merge/publication. These are roles,
not claims that particular people have already reviewed or accepted a change.

Each issue/PR retains this record, including rejected and deferred cases:

```
Record ID / issue URL:
Affected LOLDEX revision and entry / claim / API resource:
Upstream repository + immutable commit + path (if applicable):
Observed behavior and reproduction:
Expected behavior + governing contract:
Layer: source_data / enrichment / projection / identity / runtime / operations
Impact and affected scope:
Triage: reproduced / needs-evidence / duplicate / deferred / rejected
Reason and responsible reviewer role:
Proposed correction / migration and compatibility consequences:
Regression tests + actual results:
Decision: accepted / rejected / deferred; reason; reviewer; date:
Delivered commit and, separately, verified release (if published):
```

An empty decision is unresolved. Assignment is not approval. A green CI result
does not supply the human evidence decision. Reports must retain the evidence
boundary: local checks, supplied offline records and actual host observations
are different facts.

## Triage and repair

1. Pin the affected revision and reproduce without editing the original input.
   Preserve raw evidence and distinguish an upstream change from an adapter bug.
2. Locate the error. Upstream factual errors should be reported upstream; do not
   silently rewrite `source_data.raw`. Adapter interpretations are corrected in
   their producing rule and retain claim-level provenance/confidence. Derived
   public fields must be rebuilt from enrichment, never patched independently.
3. Treat an invalid publication or contradictory data as a release blocker.
   Optional missing metadata is descriptive coverage, not invented evidence or
   a reason to increase confidence. Retain incomplete/unknown states explicitly.
4. Changes to closed taxonomies, frozen CORE/D1, source admission, API compatibility
   or durable identity declarations need an explicit contract review before code.
   Identity candidates remain separate until witnessed human declarations; no
   destructive deduplication, transitive matching or automatic alias redirects.
5. Add a regression that failed for the reported problem. Validate the entry,
   all generated artifacts and the affected consumers, then run the full suite
   before delivery. Reproduction fixtures must contain public/synthetic data,
   never private credentials or executable fetched upstream code.
6. Record the review decision, delivered commit and actual test results. Publish
   only through A2 after its existing checks; record live verification separately.
   Recovery uses [operations-governance.md](operations-governance.md) and the
   existing [A2 runbook](a2-siteground-runbook.md), preserving prior releases.

## Sufficient and insufficient examples

**Sufficient for reproduction, not automatic approval:** a pinned LOLDEX commit,
entry ID and exact capability claim, the pinned upstream file showing a contrary
value, the adapter rule responsible, a minimal fixture and a test demonstrating
projection drift. A reviewer can decide whether to correct upstream evidence,
the interpretation or its projection and record that decision.

**Insufficient:** “the website looks old” plus a screenshot or date; this cannot
establish a verified CORE observation or missing source entry. Request immutable
source evidence and an affected revision. A healthy D2 acquisition never promotes
`NOT_OBSERVED` or assigns confidence to an entire entry.

**Insufficient identity request:** similar filenames or commands across sources.
Keep as a candidate, preserve original occurrences and require explicit witnessed
membership evidence under [phase9-design.md](phase9-design.md).

## Source onboarding and evolution

Apply CONTRIBUTING's inclusion test before admission. Record licence evidence,
candidate discovery/representation rules and pinned fixture repositories. Current
five-source publication uses the explicit verified D2 profile, preflight and
unchanged-base guard; `scripts.sync` is historical compatibility, not the current
admission or production procedure. Do not add a source by editing a cron command.

Upstream format/taxonomy changes must fail closed until fixtures and the adapter
are reviewed. Preserve source-qualified IDs; migration requires witnessed aliases
and compatibility tests. Upstream absence does not authorize destructive deletion
or rewrite the frozen CORE transition rules.

## Review cadence and limits

For every change, apply the relevant contract and regression checks. For each
observed publication, retain source/run/commit/release linkage and failure
diagnostics. Review deferred issues when new source evidence or a new contract
decision arrives; do not invent deadlines or historical progress percentages.
These procedures install no scheduler, alerts, notifications or automatic repair.
