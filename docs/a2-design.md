# A2 — Atomic publication contract

Status: implemented for local verification; production activation is NOT approved.
SiteGround is confirmed by the operator; only Site Tools/FTP is currently available.
Historical CORE and A1 semantics remain unchanged. This is a separate publication
subsystem, not an extension of the CORE state machine.

## Decision and reason

A release is a complete, immutable snapshot built from a selected committed Git
site tree. Transfer and verify it outside the public namespace, install it under
`public_html/releases/<release_id>/`, then atomically replace one private
`loldex-control/active.json` record. The public entrypoint redirects with **307**
and **no-store** to a visible immutable version prefix. Every local asset and data
request stays within that prefix. Old releases are retained without automatic GC.
An atomic symlink alone is insufficient: a document fetched before a switch could
otherwise load assets from the new target on its next request.

Use the existing PHP host for a tiny read-only stable router. It accepts no upload,
secret, shell command, or deployment request. The publisher is a standard-library
Python/POSIX command executed through a trusted shell on the destination. No FTP
fallback asserts atomicity, and no additional HTTP administration service is added.

## Artifact and provenance

`package_commit` resolves a complete commit, disables Git replacements/transports,
and verifies commit, trees and every selected blob against their content addresses.
Uncommitted and untracked worktree bytes never enter the package. File contents
are not Unicode-normalized or otherwise transformed.

The deterministic gzip/USTAR package contains `release.json` and `site/<path>`.
Manifest v1 binds the commit and the complete file/hash map. Release ID is `r-`
plus SHA-256 of canonical `{version,commit,files}`. Manifest bytes are canonical
UTF-8 compact JSON without terminal newline. The manifest does not hash itself;
its release ID binds the rest. The existing data build manifest is also checked.

Reject unsafe paths, non-NFC names, credentials/private directories, duplicates,
undeclared or missing payload, wrong hashes, links, devices, PAX overrides, and
oversized compressed/decompressed inputs before filesystem extraction. Extraction
is explicit file creation; tar.extractall is never called. Production packaging
requires the complete current UI and data set.

A valid manifest is integrity evidence, not a signature or proof of a trusted
publisher. `build_package` is a pure fixture/low-level API and can accept caller
bytes; only `package_commit` proves their committed-object origin. Trusted SSH
transport and the explicitly chosen expected release ID remain deployment inputs.

## On-host protocol and concurrency

Control and public roots must be canonical real non-overlapping directories on
the same filesystem, with no symlink ancestors. Control must be outside webroot.
The SiteGround router expects the private control directory as a sibling named
`loldex-control`. Staging is private; fully verified releases appear under the
public release namespace only after staging completes.

`active.json` is the sole mutable authority, protected by a stable private lock
inode. Token shape is exactly `{version:1,generation,release_id,previous_release_id,
commit}`. Generation begins at zero with null release fields, is integer-only,
and increases on every switch, including rollback. There is no second mutable
symlink/previous-pointer authority to disagree with it.

Activation requires the entire expected token to equal current authority. A
stale publisher, including an ABA A→B→A case, is rejected. Same-target no-op still
requires the exact current token and intact target. The destination is verified
again before switching, including extra/missing files, hashes, symlinks and
hardlinks. Installation never overwrites a pre-existing release.

Commit point is `os.replace(temp, active.json)` after file fsync; directory fsync
follows. Failure before rename preserves old authority. A later durability error
does not revert visibility: read status and use its actual generation. Never
blindly retry with a stale expected token. Stale temp files are not authority.
Rollback is an explicit CAS to a retained verified release; it creates a new
generation, never restores an old token or chooses a target automatically.

CAS establishes order against the active publication generation. It does NOT
prove that the selected commit is the latest GitHub main. The current command is
an explicit manual immutable-commit publisher. Future automation must preserve
its separate A1 Git-base/authority checks and cannot claim implicit latestness.

## Request coherence and first migration

After version entry, relative HTML/CSS/JS/data/API/contact references stay on one
retained version. Root API requests redirect to a per-request version; clients
requiring multi-request pagination consistency must keep using the returned
version prefix. Contact POST receives 307; no test follows it to send mail.

A production static URL-closure guard rejects obvious root/absolute runtime
references and base overrides for the reviewed stack. It is not a proof of all
possible dynamic JavaScript. HTTP/browser checks on the target remain mandatory.
No remote fonts/scripts are needed by the current site.

The initial migration from unversioned legacy HTML has a different boundary:
browsers/CDNs may retain documents with old root-relative dependencies. Establish
an explicit maintenance/cache transition and test SiteGround cache exclusions
before switching the stable router. Do not claim this protocol retroactively
versions those already-loaded documents. Save legacy root configuration for
operator-controlled restoration; do not delete it as part of A2 installation.

## Source data and cron

Atomic website publication does not certify source acquisition. The new explicit
verified staging bridge consumes the same immutable bundles used for all five
CORE health results, rejects diagnostics and material divergence from the legacy
public projection, and aborts global public-ID/filename collisions. It does not
migrate canonical IDs, delete absent historical entries or grant a publication
policy to CORE. See a2-source-health.md.

The existing workflow remains manual and invokes legacy scripts.sync. No cron or
live deployment is enabled by this work. Before scheduling, integrate the verified
bridge with a reviewed retained-entry policy, then demonstrate healthy real inputs,
Git publication, same-commit release packaging, remote switch and rollback.
Known documented upstream collisions must abort rather than be silently repaired.

## Production prerequisites

All must pass before an explicit cron approval:

- SSH key access to the actual SiteGround account; pinned host identity.
- Confirm real paths, PHP handler/rewrite, Python >=3.9, POSIX flock, same-filesystem
  replacement, file and directory fsync via the destination's private probe.
- Install and verify a non-active release, with its full expected ID/hash.
- HTTP smoke tests against the release URL: UI/data/API and query/method handling.
- Controlled cache/bootstrap migration, interrupted-upload and failed-activation
  tests, successful switch, old-page/new-fetch consistency and rollback on-host.
- The verified source pipeline and retained-entry policy are integrated and pass
  real upstream input tests. Package provenance and the A1 Git-base guard agree.

Host verification is recorded below. Initial production migration and verified
source publication remain separate gates until their observed completion.
The SSH host key was accepted on first use and is pinned for subsequent
connections; it has not been independently fingerprint-verified.

## Destination evidence — 13 November 2026

Dedicated SSH access is configured. Actual host: Python 3.14.10, PHP 8.2.35,
canonical webroot `/home/customer/www/loldex.sh/public_html`. Private tests on
this filesystem passed POSIX locking, rename/fsync, two competing publishers,
pre-switch failure, rollback and ABA rejection. The PHP router passes host syntax
checks and the isolated PHP runtime regression suite.

An isolated HTTPS fixture proved 307/no-store, query preservation, POST method
preservation without sending a message, visible activation/rollback, and retained
old version URLs. It also exposed SiteGround static direct delivery: an existing
`index.html` bypassed root rewrite even while directory requests hit the router.
Removing the fixture's legacy static file eliminated that bypass. Therefore the
first migration MUST move the reviewed legacy root files into a private,
SHA-256-verified backup, leaving only the stable router and bootstrap rules at
root. `deployment.bootstrap` performs that explicit maintenance operation with
inventory comparison and restoration on failure. Subsequent publications require
only the atomic active-state switch. Initial migration is not retroactively
atomic for already cached legacy clients. Old root HTML was served without an
explicit cache lifetime; no universal cache-expiry claim is made.
