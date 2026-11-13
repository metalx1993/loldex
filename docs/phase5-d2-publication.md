# D2 — Explicit publication profile and complete-snapshot policy

Implemented 13 November 2026 under the user's instruction to complete A2 and
correct all five live source failures. This is a new, opt-in publication contract,
not an edit to frozen CORE/D1. Existing CORE `adapter_result()` behavior, identity
rules, material algorithm, classifications and golden tests remain unchanged.
D2 results MUST NOT be submitted as CORE observations or used as CORE state.

## Source-format amendments

- GTFOBins: [D2-GTFO](phase5-d2-gtfobins.md), same-bundle aliases and conservative
  inherit handling, preserving per-claim provenance and confidence.
- LOLBAS/LOLAD: [D2 identities](phase5-d2-identities.md), qualified source-file
  identities and explicit exact-cell occurrence coalescence with all evidence.
- LOLDrivers/WADComs: complete content representation and exact reviewed vocabulary
  mappings; no truncation and no invented fallback for a stated unknown type.

`deployment.publication.publication_result` first runs the unchanged D1 derivation,
then source-specific exhaustive D2 preflight on the very same verified bytes.
Only the enumerated D2-resolved findings can be replaced. Every remaining error,
future unknown value, malformed document, duplicate output or diagnostic blocks
publication. D2 output entries undergo the existing closed taxonomy, per-claim
provenance, source-revision, raw-evidence and projection validation. Preparation
repeats normalization over the immutable bytes and compares the material multiset
against the preflight output. There is no second fetch or mutable-worktree read.
Default `prepare_verified_sync` remains D1; `--profile publication-v2` is explicit.

## Search snapshot and retention

A publication snapshot requires all five complete, verified, healthy source
bundles. The managed current corpus contains exactly the emitted D2 entries for
that snapshot. This is an explicit publication policy, not an inference of CORE
absence, retirement, or cross-source identity. A partial source never authorizes
partial replacement. Unknown future formats fail closed.

Historical public IDs, including legacy path slugs and entries no longer emitted,
are not mixed into the new current-search corpus. They remain preserved in the
unchanged acquisition-base Git commit and in retained immutable host releases.
No host release garbage collection is enabled. A machine-readable
`data/publication-ledger.json` records the base commit, every removed filename and
hash, every added filename and hash, and before/after hashes for changed files.
No cross-source deduplication is performed. LOLAD's narrowly defined exact-cell
coalescence records every physical occurrence; non-equivalent collisions fail.
Old bookmarked release URLs remain valid. Legacy unversioned entry IDs can stop
resolving in the current snapshot; automatic redirects would require a separately
validated identity mapping and are not invented.

`scripts.verified_refresh` operates on a clean candidate checkout under one
recorded Git base. It prepares a separate new staging corpus, validates and builds
all views first, rechecks checkout/base, then writes the candidate tree and ledger.
It does not fetch, commit, push, deploy or schedule. A failed candidate checkout
is disposable; staging directory existence alone is never completion authority.
The workflow's existing A1 unchanged-base/no-rebase/plain-push protection remains.

## Automation boundary

The manual workflow acquires fresh public Git repositories, verifies their objects,
prepares this explicit D2 snapshot, builds all views, validates and tests before
Git publication. Cron remains commented out. SiteGround deployment uses A2 and
requires its own verified release and exact expected-state token. A successful
Git-only sync is not a successful website deployment, and source health is not
CORE freshness: the UI remains NOT_OBSERVED unless a real validated CORE state is
provided. A scheduling decision must state precisely which operation is enabled.

## Real upstream acceptance

Pinned live acquisitions produced **3,336** validated staged entries with zero
remaining source diagnostics: GTFOBins 1,898; LOLBAS 485; LOLAD 136 logical entries
from 137 physical rows (one exact duplicate explicitly accounted); LOLDrivers
713; WADComs 104. Full source revisions, independent emission/evidence oracles
and physical/logical accounting are retained in the candidate health report.
These are observed D2 publication results, not retroactive claims of healthy D1
observations or CORE freshness. All five original D1 gate failures remain
reproducible under the unchanged default profile.
