# Phase 5 — D1: verified acquisition and adapter derivation

Status: implementation decision under the user's 13 November 2026 delegation to
complete Phase 5 through Phase 6. Independent adversarial review is required
before freezing this amendment. This is a new amendment; the frozen CORE v6-4
SHA-256 `f79aed020b36d1a217b8091319be1e7ec7cf5ac48849c8d0b765a1523f2ef3e0`
is unchanged. Historical evidence is not a count invariant or a normative
fallback. No claim is made that this text was approved in the historical reviews.

## Context and authority

The archived `Fases/Fase5/D1/B2-FINAL-CLOSURE-AUDIT.md` closes ID, projected
material, stable identity, owner evidence, revision, diagnostics and serialization
but leaves the admission predicate for candidate files implementation-defined.
`B2B-FINAL-CHECK.md` closes material derivation: suppressing diagnostics suppress
health credit, not parsed emission; unknown values have empty mapped values;
missing driver display name is omitted by material projection. Earlier BLOCKED
records are historical intermediate findings, not reasons to undo those closures.

The following discovery decision closes that last B2 primitive. It deliberately
preserves the historical source-specific scope, not accidental filesystem output.

## 1. Verified acquisition object (B1)

An acquisition is one resolved full 40-lowercase-hex Git SHA-1 **commit**, its
referenced tree, and the bytes of all selected regular blobs. Resolve the supplied
revision once before enumeration; requested branch names and abbreviated hashes
never enter AdapterResult. The working tree, ignored/untracked files, sparse
checkout, index and previous clones' worktree contents have no authority.

Read tree objects recursively from the object database and verify each tree and
selected blob using Git's `type + space + decimal length + NUL + content` SHA-1.
Verify the commit likewise. Git replacement objects are disabled. The decoded
paths are UTF-8 and the selected bytes remain immutable in memory through
candidate discovery and derivation. Equivalent inputs have the same source,
commit/tree identity and ordered `(relative path, bytes)` selected tuples; host
paths, filesystem metadata and requested revision spelling are excluded.

Missing/unreadable/corrupt objects, missing required roots, selected non-regular
objects (symlinks/gitlinks), invalid tree names/encoding, unsupported object format,
or resource-limit exhaustion yield exactly `ACQUISITION_FAILED`. No observation
from a partially read object is accepted as complete. The complete tree is the
completeness oracle; counts from historical corpus snapshots are never used.
An upstream commit that itself intentionally omits data is a real upstream state,
not detectable local truncation. A shallow repository is sufficient if every
object needed for this state exists. Acquisition does not fetch automatically.

Current defensive limits are 32 MiB per object, 128 MiB selected content, 20,000
selected files, 200,000 traversed tree records and depth 64. Exceeding one fails
the acquisition, never silently truncates it.

## 2. Authoritative file discovery (last B2 primitive)

All names are POSIX, case-sensitive; no case folding, extension inference,
recursive glob or host-specific path matching occurs.

| Source | Required root(s) in verified tree | Selected candidates |
|---|---|---|
| GTFOBins | `_gtfobins/` | Every immediate regular file, regardless extension, including dotfiles. No nested files. |
| LOLBAS | `yml/` and all four folders below | Immediate regular `*.yml` in `OSBinaries`, `OSLibraries`, `OSScripts`, `OtherMSBinaries`. |
| WADComs | `_wadcoms/` | Immediate regular `*.md` only. |
| LOLDrivers | `yaml/` | Immediate regular `*.yaml` only. |
| LOLAD | root `index.html` blob | The single named document; candidate rows follow CORE §7.4/§7.5. |

`HonorableMentions` and any other LOLBAS folders are excluded by the predicate,
not rejected as malformed candidates. WADComs `.dir-locals.el` is excluded because
it is not Markdown. Nested files and directories are excluded. A selected name
whose mode is not regular fails acquisition rather than silently disappear.
A missing root is not a proven empty input. A verified existing root whose
predicate selects no files produces `EMPTY_INPUT_SET`. LOLAD absent `index.html`
is `ACQUISITION_FAILED`; zero tables/zero candidate rows is `EMPTY_INPUT_SET`;
multiple table start tags, including nested or unclosed tables, or one table
start without a closing table, produce one synthetic
`MALFORMED_RECORD` candidate. Header rows are those containing `<th>`; explicitly
empty-command rows are NOT_A_RECORD. Extraction preserves the legacy tag-strip
and whitespace-collapse grammar on the first three cells; cells after the third
are ignored. This deterministic grammar is a scoped HTML-table adapter, not a
browser DOM implementation.

Paths are sorted only for reproducibility. `canonical_input_ref` and normalized
reference collision rejection remain frozen CORE §6.2.1. Candidate cardinality
remains one per file for GTFOBins/LOLBAS/WADComs/LOLDrivers, one per LOLAD row;
commands inside a file do not become candidates.

## 3. Closed entry-ID functions and stable identity

| Source | Canonical entry ID | Stable upstream identity |
|---|---|---|
| GTFOBins | `gtfobins/{path.name}/{function}/{context}` verbatim, NFC canonicalization | kind `gtfobins_natural_key`, value `{path.name}/{function}/{context}` |
| LOLBAS | `lolbas/{slug(path.stem)}/{slug(category)}/{command_source_index}` | null (NONE) |
| WADComs | `wadcoms/{path.stem}` verbatim, NFC, **no slug** | null (NONE) |
| LOLDrivers | `loldrivers/{Id}` verbatim, NFC, **no suffix/name fallback** | kind `loldrivers_id`, value `Id` |
| LOLAD | `lolad/{encode(Name)}/{encode(Command)}/{encode(Type)}` | null (NONE) |

`encode(x) = BASE64URL_NO_PAD(UTF8(NFC(x)))`, applied unconditionally to all three
components. Equal triples remain equal IDs and therefore collide; no ordinal,
position, hash, emitted-count suffix or collision-repair identity is introduced.
LOLBAS `command_source_index` is the zero-based upstream Commands array index,
including unknown-category commands; it is not the count of emitted entries.
`slug` is LOLBAS-specific: strip outer whitespace, lowercase, replace each
non-`isalnum` scalar with `-`, strip outer `-`; no repeat collapse or truncation.

The known LOLBAS cross-folder collision remains subject to CORE reject-all. The
historical winner produced by filesystem overwriting is not ratified. Identity
changes versus the historical corpus do not authorize corpus migration, deletion
or publication. Those remain separate actions.

## 4. Projection and diagnostics (B2-B/C/D)

The pure mapping constants/functions are the existing baseline definitions at
`f244936`: GTFOBins FUNCTION_CAP/CONTEXT_PRIV/CAP_PHASE, LOLBAS CATEGORY_MAP,
FOLDER_MAP, LOUD, map_privilege, WADComs ATTACK_MAP/ITEM_PRECOND, LOLDrivers
classify, LOLAD ordered classify. Their literal transcription is archived in
`B2B-PROJECTION-TRANSCRIPTION.md`, corrected by `B2B-FINAL-CHECK.md` (WADComs
`type = technique`). CP5.3 imports these unchanged helpers and supplies explicit
shape/diagnostic handling instead of calling legacy normalize/run.

Fields not claimed remain empty/absent, then CORE `project_material_v1` applies
omit-empty, NFC, canonical ordering and de-duplication. `description` remains
non-material except where it contributes the command comment. Driver `name`
comes only from `Tags[0]`; empty Tags yields omitted name, never Id/path fallback.
An unknown GTFOBins function or LOLBAS category emits its parsed entries with
empty mapped capability/phase lists plus the required suppressing diagnostic.
An unknown WADComs attack type contributes no mapped value and a non-suppressing
diagnostic. The historical discovery default applies only when no attack types
are stated, not when stated types are all unrecognized.

`declared_sources` comes from the adapter's declared source; the separate
`source_data_projects` comes from verified byte contribution. A single-source
candidate has the same singleton in both for distinct reasons. Neither set is
copied to infer mixed-source provenance. `id_prefix` is the exact ID substring.
`resolved_revision` is always the complete verified commit.

YAML parsing uses the safe 1.1 schema; required scalar values are type checked,
not string-coerced. Candidate processing is one terminal disposition: invalid
path, normalized-ref reject-all, provisional-ID reject-all, then content defects
in CORE precedence. Collisions erase all sibling emissions from every member,
even when a member also has malformed content. Diagnostics are retained only for
terminally parsed candidates, with multiplicity and frozen suppression bits.
Only finalized health/status determines whether the pure engine credits evidence.

## 5. Caller and persistence boundary

`ObservationBuilder` rejects a second build for a base token within its lifetime;
observation ID is derived from the captured token. The local cycle holds one
stable state lock through capture/acquisition/build/apply. Finalized canonical
observation bytes are written once to an explicit delivery artifact, never
mutated. Retry uses that exact file and does not reacquire. Only an applied
transition persists a new state; all other admissions return no report.

Persist with a temp file on the same filesystem, file fsync, atomic rename
(commit point), then directory fsync. Lock the stable sibling lock inode, not the
replaceable state inode. A post-rename durability error does not undo committed
visibility. Stale temp files are never authority.

Caller valid-input precondition remains CORE §2: do not construct a second
observation with a different artifact path for the same base token. Across a
process crash before finalized bytes exist, there is no automatic reconstruction
or reacquisition guarantee: the caller must decide how to restore valid input.
This intentionally does not introduce a persistent reservation service, queue or
recovery journal. Distributed arbitration and automatic crash resumption remain
outside CORE; the CLI does not claim them.

## 6. Acceptance evidence and scope

Tests cover each source, typed YAML failures, exact suppression, context sibling
survival, source-index IDs, duplicate/path rejection multiplicity, malformed
content behind collision membership, same-base builder rejection, exact retry,
state corruption and rename failures. Independent tests additionally mutate the
working tree, remove selected Git objects, introduce symlinks and nested tables.
Frozen CP5.1/CP5.2 goldens must remain unchanged. Test execution counts belong in
the delivery report, not this normative contract.

CORE still observes and classifies. No corpus deletion, migration, publication,
cron, deploy, terminal STALE or Phase-9 durable cross-source identity is added.


## Appendix A — Literal mapping tables retained from the closed derivation

The following tables are transcribed here to keep the mapping contract readable
without the external audit archive. The baseline helper imports implement these
literal values; future helper changes must be checked against this amendment.

## D.1 GTFOBins — `FUNCTION_CAP` (`gtfobins.py:30-47`)

| chiave upstream | capability |
|---|---|
| `shell` | `shell` |
| `command` | `command-execution` |
| `reverse-shell` · `non-interactive-reverse-shell` | `reverse-shell` |
| `bind-shell` · `non-interactive-bind-shell` | `bind-shell` |
| `file-read` | `file-read` |
| `file-write` | `file-write` |
| `download` | `file-download` |
| `upload` | `file-upload` |
| `library-load` | `library-load` |
| `sudo` · `suid` · `capabilities` · `limited-suid` | `privilege-escalation` |

## D.2 GTFOBins — `CONTEXT_PRIV` (`:49-56`)

| contesto | privilegio |
|---|---|
| `sudo` | `sudo` |
| `suid` · `limited-suid` | `suid` |
| `capabilities` | `capability` |
| `unprivileged` | `user` |

Default documentato (`gtfobins.py:144`, citato da §7.5:686): *"defaults to `user`"*.

## D.3 GTFOBins — `CAP_PHASE` (`:58-70`)

| capability | phases |
|---|---|
| `shell` · `command-execution` | `["execution"]` |
| `reverse-shell` · `bind-shell` | `["execution","command-and-control"]` |
| `file-read` | `["collection"]` |
| `file-write` | `["persistence"]` |
| `file-download` | `["command-and-control"]` |
| `file-upload` | `["exfiltration"]` |
| `library-load` | `["execution","persistence"]` |
| `privilege-escalation` | `["privilege-escalation"]` |

## D.4 LOLBAS — `CATEGORY_MAP` (`lolbas.py:31-47`), 15 voci

| Category | capability | phases |
|---|---|---|
| `Execute` | `command-execution` | `["execution"]` |
| `Download` | `file-download` | `["command-and-control"]` |
| `Upload` | `file-upload` | `["exfiltration"]` |
| `AWL Bypass` | `defense-evasion` | `["defense-evasion","execution"]` |
| `ADS` | `defense-evasion` | `["defense-evasion"]` |
| `Dump` | `credential-dump` | `["credential-access"]` |
| `Copy` | `file-write` | `["collection"]` |
| `UAC Bypass` | `privilege-escalation` | `["privilege-escalation","defense-evasion"]` |
| `Compile` | `command-execution` | `["execution"]` |
| `Tamper` | `defense-evasion` | `["defense-evasion"]` |
| `Credentials` | `credential-access` | `["credential-access"]` |
| `Reconnaissance` | `command-execution` | `["discovery"]` |
| `Decode` | `decode` | `["defense-evasion"]` |
| `Encode` | `encode` | `["defense-evasion"]` |
| `Conceal` | `defense-evasion` | `["defense-evasion"]` |

## D.5 LOLBAS — `FOLDER_MAP` (`:49-55`) e `LOUD` (`:58`)

| cartella | type | segmento URL |
|---|---|---|
| `OSBinaries` | `binary` | `Binaries` |
| `OtherMSBinaries` | `binary` | `OtherMSBinaries` |
| `OSScripts` | `script` | `Scripts` |
| `OSLibraries` | `library` | `Libraries` |

Commento verbatim: *"HonorableMentions intentionally skipped: not clean LOLBins upstream."*

`LOUD = {"file-download", "credential-dump", "command-execution", "file-upload"}` — euristica
`opsec`.

## D.6 LOLBAS — `map_privilege()` (`:61-73`) — **precedenza ordinata, primo match vince**

```
s := (raw or "").strip().lower()
1. "system"        ∈ s  -> "system"
2. "dns admin"     ∈ s  -> "specific-right"
3. "sebackup" ∈ s OR "backup operators" ∈ s -> "specific-right"
4. "admin"         ∈ s  -> "admin"
5. altrimenti           -> "user"
```

## D.7 WADComs — `ATTACK_MAP` (`wadcoms.py:31-39`) e `ITEM_PRECOND` (`:42-50`)

| attack_type | capability | phases |
|---|---|---|
| `Enumeration` | `discovery` | `["discovery"]` |
| `Exploitation` | `command-execution` | `["execution"]` |
| `PrivEsc` | `privilege-escalation` | `["privilege-escalation"]` |
| `Persistence` | `persistence` | `["persistence"]` |
| `Credential Access` | `credential-access` | `["credential-access"]` |
| `Lateral Movement` | `lateral-movement` | `["lateral-movement"]` |
| `Defense Evasion` | `defense-evasion` | `["defense-evasion"]` |

| token `items` | precondizione |
|---|---|
| `No_Creds` | `no credentials required` |
| `Username` | `a valid username` |
| `Password` | `a valid password` |
| `Hash` | `an NTLM hash (pass-the-hash)` |
| `Kerberos_Ticket` | `a Kerberos ticket` |
| `Domain_User` | `domain user context` |
| `Local_Admin` | `local admin on the target` |

Privilegio (`:115`): `"none"` se un item è esattamente `No_Creds`, altrimenti `"domain-user"`.

## D.8 LOLDrivers — `classify()` (`loldrivers.py:30-45`) — **cumulativa, non first-match**

```
hay := lower(usecase + " " + desc)
ramo 1: se hay contiene uno di {disable, edr, defen, terminat, kill, unhook, bypass}
        -> caps += "defense-evasion";        phases += "defense-evasion"
ramo 2: se hay contiene uno di {elevat, privile, kernel, escala}
        -> caps += "privilege-escalation" (se assente); phases += "privilege-escalation"
default: se caps vuoto -> caps   = ["privilege-escalation","defense-evasion"]
                          phases = ["privilege-escalation","defense-evasion"]
```

**Entrambi i rami possono attivarsi**: l'ordine risultante è ramo 1 poi ramo 2. Privilegio
(`:99`): `"system"` se `kernel` o `system` ∈ `lower(Privileges)`, altrimenti `"admin"`.

## D.9 LOLAD — `RULES` (`lolad.py:29-59`) — **lista ordinata, primo match vince**

Commento verbatim: *"Order matters: first match wins. Most specific first."*
`hay := lower(name + " " + command)`.

| # | keyword | capability | phases | priv |
|---|---|---|---|---|
| 1 | `dcsync` | `credential-dump` | `["credential-access"]` | `specific-right` |
| 2 | `kerberoast` | `kerberoast` | `["credential-access"]` | `domain-user` |
| 3 | `asrep` | `kerberoast` | `["credential-access"]` | `domain-user` |
| 4 | `as-rep` | `kerberoast` | `["credential-access"]` | `domain-user` |
| 5 | `golden ticket` | `persistence` | `["persistence"]` | `specific-right` |
| 6 | `silver ticket` | `persistence` | `["persistence"]` | `specific-right` |
| 7 | `shadow cred` | `credential-access` | `["credential-access"]` | `domain-user` |
| 8 | `relay` | `lateral-movement` | `["lateral-movement","credential-access"]` | `none` |
| 9 | `coerce` | `coerce` | `["credential-access"]` | `domain-user` |
| 10 | `petitpotam` | `coerce` | `["credential-access"]` | `domain-user` |
| 11 | `password` | `credential-access` | `["credential-access"]` | `domain-user` |
| 12 | `credential` | `credential-access` | `["credential-access"]` | `domain-user` |
| 13 | `lsass` | `credential-dump` | `["credential-access"]` | `admin` |
| 14 | `secretsdump` | `credential-dump` | `["credential-access"]` | `admin` |
| 15 | `add ` *(con spazio finale)* | `persistence` | `["persistence"]` | `domain-user` |
| 16 | `create` | `persistence` | `["persistence"]` | `domain-user` |
| 17 | `set ` *(con spazio finale)* | `defense-evasion` | `["defense-evasion"]` | `domain-user` |
| 18 | `disable` | `defense-evasion` | `["defense-evasion"]` | `domain-user` |
| 19 | `psexec` | `lateral-movement` | `["lateral-movement"]` | `admin` |
| 20 | `wmiexec` | `lateral-movement` | `["lateral-movement"]` | `admin` |
| 21 | `winrm` | `lateral-movement` | `["lateral-movement"]` | `domain-user` |
| 22 | `evil-winrm` | `lateral-movement` | `["lateral-movement"]` | `domain-user` |
| 23 | `enum` | `discovery` | `["discovery"]` | `domain-user` |
| 24 | `list` | `discovery` | `["discovery"]` | `domain-user` |
| 25 | `get-` | `discovery` | `["discovery"]` | `domain-user` |
| 26 | `find` | `discovery` | `["discovery"]` | `domain-user` |
| 27 | `collect` | `discovery` | `["discovery"]` | `domain-user` |
| 28 | `query` | `discovery` | `["discovery"]` | `domain-user` |
| 29 | `search` | `discovery` | `["discovery"]` | `domain-user` |
| — | **`DEFAULT`** | `discovery` | `["discovery"]` | `domain-user` |

> ⚠ **La riga 22 `evil-winrm` è irraggiungibile**: la riga 21 `winrm` è sottostringa di
> `evil-winrm` e la precede. Deterministico, quindi ratificabile, ma la voce è morta.

## Appendix B — Structural material fields

These rules accompany Appendix A and the exact ID functions in §3. All strings
are type checked before string operations; no resolved YAML scalar is coerced.
Optional missing/null strings become empty; optional missing/null arrays become
empty. Required fields and source-specific overrides follow CORE §7.5. Empty
values are omitted only by material projection, not fabricated from unrelated
fields. For GTFOBins, missing/null/non-map functions and non-list function bodies
are source-specific MALFORMED_RECORD; this explicit source rule takes precedence
over the generic missing-null default.

- **GTFOBins:** type binary, platform linux, name `path.name`, references
  `[https://gtfobins.github.io/gtfobins/{path.name}/]`, tags linux/unix/gtfobins.
  Each function's code-record list groups commands by context. A missing or empty
  context map defaults to unprivileged. Context values are null or maps. Code is
  stripped record code, overridden when the raw context-code string is non-empty
  (a whitespace-only override therefore becomes an empty-code context); comment is
  stripped record comment. A context with no code produces exactly one
  EMPTY_CODE_CONTEXT occurrence and no command. Same function/context records
  combine into one entry, not duplicate ID occurrences. Known capability phases
  gain privilege-escalation when privilege is sudo/suid/capability. Unknown
  function has no mapped capability/phases (no fabricated execution default).
- **LOLBAS:** type and reference URL segment come from FOLDER_MAP, platform
  windows; name is Name or path.stem; alias is path.stem.lower iff different from
  slug(path.stem). Reference is
  `https://lolbas-project.github.io/lolbas/{urlseg}/{path.stem}/`; tags windows,
  lolbas. Per Commands element: stripped Command and Description become template
  and comment when Command non-empty; MitreID becomes the upstream ATT&CK claim
  when non-empty. opsec.noise is high for a mapped capability in LOUD, otherwise
  medium; triggers is the first non-empty Detection.IOC; detection_refs collects
  non-empty Sigma/Elastic/Splunk in that order per Detection element, first six.
  Missing Commands is MISSING_REQUIRED_FIELD; non-list Commands, non-map command
  or Detection elements and invalid string fields reject the entire file.
  Unknown privilege strings map with the existing ordered map_privilege default
  and record UNKNOWN_PRIVILEGE. Recognized tokens are system/admin/user/any/low/
  sebackup/backup operators (substring, case-insensitive).
- **WADComs:** type technique, platform active-directory; name is path.stem with
  hyphens replaced by spaces. Required command is stripped and non-empty. Comment
  is description with whitespace collapsed then first 280 scalars. references
  are non-empty stripped source references, first four. Items map using
  ITEM_PRECOND, otherwise replace underscores by spaces and lowercase; No_Creds
  exact untrimmed upstream token sets privilege none, otherwise domain-user. Tags are
  active-directory/wadcoms plus lowercased services. Unstated attack_types defaults
  to discovery heuristically; stated unrecognized types contribute no map value.
  Overlong description or more than four references records SUBSET_TRUNCATED.
- **LOLDrivers:** type driver, platform windows; required non-empty string Id is
  identity, Tags[0] alone is material name. Commands is a mapping or list; retain
  first list item (or empty map), with SUBSET_TRUNCATED when length exceeds one.
  Usecase/Description feed cumulative classify; Privileges containing kernel or
  system yields system, otherwise admin. Non-empty stripped Command produces a
  command with first 200 Description scalars as comment; longer description
  records SUBSET_TRUNCATED. KnownVulnerableSamples retains its first map;
  SHA256/Company/OriginalFilename become driver_detail sha256/signer/
  original_filename; top-level Category becomes detail category. Multiple samples
  record SUBSET_TRUNCATED. Resources retains first three strings, otherwise
  references defaults to https://www.loldrivers.io; excess records
  SUBSET_TRUNCATED. Top-level MitreID is an upstream ATT&CK claim. Tags are
  windows/driver/byovd/loldrivers; opsec.noise high iff category equals malicious,
  otherwise medium. Non-list Tags, invalid Commands/sample/resource shapes reject
  the file; no display-name fallback to Id/path is permitted.
- **LOLAD:** type technique, platform active-directory; first three normalized
  cells are Name, Command, Type. First-match classify supplies one capability,
  phase list and privilege as heuristic/low claims. Name is material name; Command
  is template; references is [https://lolad-project.github.io]; tags are
  active-directory/lolad plus lowercase Type when non-empty. Extra cells are
  ignored. Fewer than three cells rejects MALFORMED_RECORD, empty Name rejects
  MISSING_REQUIRED_FIELD; empty Command is NOT_A_RECORD before candidate count.

Per-claim upstream ATT&CK values retain upstream/high provenance; deterministic
maps retain adapter/high; heuristic defaults/classification retain heuristic/low
and an explanatory note. No entry-wide confidence replaces these claims.
