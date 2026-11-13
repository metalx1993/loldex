# A2 — Independent adversarial review

Status: **local protocol review passed.** This report covers the independent
local review; subsequent actual-host acceptance is recorded separately in
[a2-completion.md](a2-completion.md).

This review operates only on temporary local Git repositories, release roots and
control directories. It performs no remote connection, upload to a live host,
service restart, contact-email submission or scheduler change. Local success is
not a transport capability proof and does not authorize cron activation.

## Invariants and executed attacks

`tests/test_a2_adversarial.py` has **35 passing independent tests** (latest run:
3.70 seconds).

| Boundary | Attack | Independently verified outcome |
|---|---|---|
| Retained versioned resources | Read A HTML/assets/data, activate B, read A URLs again | A bytes remain unchanged; B has its own asset bytes |
| Active publication CAS | Two real processes publish different releases using one token | Exactly one wins; the other receives Conflict |
| Retry precedence | Retry the current target with a stale expected token | Rejected; target equality cannot bypass CAS |
| Rollback ABA | A → B → A, then a publisher uses the original A token | Rejected because generation changed |
| Precommit failure | Inject failure in active-record replace | Old authority remains byte-identical; temporary active file removed |
| Postcommit durability failure | Fail directory fsync after active replace | New generation remains visible; old token cannot roll it back |
| Retained-release integrity | Change payload, add undeclared file, replace payload with symlink | Activation and rollback both reject; active state unchanged |
| Retained-release aliasing | Replace a matching payload with a hardlink to an external file | Verification and activation reject the shared inode even before its bytes change |
| Private control location | Spell an overlapping control root through `other/../public/control` | Reject before creating private state beneath the public document root |
| State corruption | Duplicate keys, boolean generation, noncanonical bytes | Fail closed; never reinterpret as uninitialized |
| Archive boundary | Traversal, absolute path, backslash, duplicate manifest/member, symlink, hardlink, FIFO | Rejected before a public release exists |
| Git provenance | Replace requested commit with another commit through Git replace refs | Original commit's bytes are packaged, never replacement bytes under the old label |
| Object integrity | Overwrite a loose commit/tree object at the claimed identity with different valid object bytes | Packaging rejects the mismatch |
| Source-health policy | WADComs states an unknown attack type | Publication staging aborts instead of inventing a discovery fallback |
| Acquisition-to-staging binding | Change source working-tree bytes immediately after verified acquisition | Public staging still consumes the original immutable source bytes |
| Static URL closure | Root/absolute same-origin resources, base element, HTML entities, CSS hex escape and JavaScript legacy-octal escape | Rejected rather than bypassing the versioned release URL |

The retention test proves filesystem release immutability within the protocol;
it does not substitute for an actual Apache/PHP/browser route test. A2 coherence
requires the browser to enter a visible versioned URL and all local resource/data
dependencies to remain within that release. A mutable `current` symlink alone
would not satisfy this requirement across independent browser requests.

## Defects found and corrected

1. **Commit relabeling through Git replace refs.** The initial packager honored
   local replacement objects. A real two-commit fixture produced commit B's HTML
   while labeling the release commit A. The independent regression failed before
   the fix. Packaging now disables replacement refs and re-verifies the raw
   requested commit, every traversed tree and every included blob. Independent
   loose-object corruption tests confirm that this is more than a replacement-
   ref workaround.
2. **Observation health did not guarantee equivalent public material.** The
   legacy WADComs normalizer could invent a discovery fallback from a stated but
   unknown attack type, while the closed CORE derivation deliberately emitted no
   mapped capability. Publication now requires zero diagnostics in addition to
   healthy CORE status, and compares per-source material-fingerprint multisets.
   This is a stricter publication policy, not a change to CORE's non-suppressing
   diagnostic semantics or its identity policy.
3. **Root-relative favicon in an existing document.** `contact.html` referred to
   `/favicon.svg`, which could cross generations despite a versioned document
   URL. The dependency is now relative. The remaining external Google Fonts
   stylesheet was removed, retaining system-font fallbacks. A production-package
   static URL lint now checks the reviewed HTML/CSS/JavaScript/SVG surfaces.
4. **Escaped static fetch bypass.** The initial URL lint interpreted JavaScript
   `fetch('\\57catalog.json')` as a relative literal, while non-strict JavaScript
   interprets the legacy octal escape as `/`. The independent regression failed
   before the fix. The lint now rejects legacy-octal URL escapes; CSS hex escapes
   and entity-encoded HTML roots are also covered independently.

The URL lint is explicitly scoped to the reviewed stack and supported static
surfaces. It is not a proof that arbitrary dynamic JavaScript, PHP, redirects or
future server configuration cannot construct an unversioned request. Manifest
hashes alone do not prove URL closure; production changes still require code and
browser acceptance within the documented release-contained dependency contract.
An isolated-process mutation replacing the runtime-URL guard with a no-op was
killed by three independent HTML dependency regressions. No production source
file was modified for the mutation experiment.

## Reviewed boundaries and production gates

- A2 is separate from the frozen observe/classify CORE and its state. It adds no
  CORE deletion, identity migration or scheduler semantics.
- Server CAS controls the active host generation. It does not prove the chosen
  immutable Git commit is the latest remote main; that is an external publication
  policy, and no latest-main guarantee is inferred.
- The stable PHP entrypoint uses a temporary 307 redirect, no-store caching and
  preserved query strings. This avoids changing POST into GET. Canonical token
  bytes reject duplicate-key/alternative representations. Registry/contact UI
  functionality is not exercised by sending live mail.
- Host-side activation requires a verified POSIX filesystem, stable locking,
  atomic same-filesystem rename, correct private control permissions, and an
  actual supported authenticated execution channel. Domain ownership or FTP
  access alone establishes none of these properties.
- Previously cached pre-A2 HTML with unversioned URLs needs an explicit initial
  cutover/cache policy. Versioned-path retention protects clients after entry
  into the versioned routing contract; it does not retroactively version old
  cached documents.
- No release garbage collection is introduced. Rollback verifies an explicit
  retained target under the same CAS rule; it never guesses or silently rewinds.
- The legacy manual sync remains distinct from verified candidate staging. Cron
  must remain off until source-health preparation, historical-entry disposition,
  tested code/corpus base binding and actual host publication are integrated and
  independently verified. Correctly failing synthetic/current-reference cases
  are evidence of fail-closed behavior, not evidence of production readiness.

Final integrated test totals, HTTP/browser host checks and production blockers
belong in the root delivery report; they must not be represented as tests this
independent reviewer executed on the real host.
