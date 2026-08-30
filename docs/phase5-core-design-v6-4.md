# LOLDEX — Phase 5 CORE Design **v6-4**
## Freshness observation & classification — normative, self-contained, implementation-ready

> Single normative specification for Phase 5 CORE. An implementer can delete v3,
> v4, v5, the remediation spec, and every review and build the CORE from **this
> document alone**. Prior documents are referenced only in the disposition/history
> section, never to define behavior.
>
> v6-4 is a **normative closure-repair revision of v6-2**, not a redesign. It
> integrates the Codex Round-6 review as the authoritative repair list while
> preserving the ratified Round-5 Gate Contract, every Round-6 finding already
> CLOSED, and the Codex
> **R5-B5 Option-C arbitration** (empty-code context ⇒ one non-suppressing
> `EMPTY_CODE_CONTEXT` diagnostic, valid siblings always survive) which
> **supersedes** the v5 empty-code→MALFORMED_RECORD rule. The concurrency, ownership,
> continuity, freshness, acquisition, and persistence **architecture** is unchanged; the
> local normative branches identified by Round 6 are repaired. Scope is
> unchanged and reduced: no queue, scheduler, journal, recovery system,
> publication authority, snapshots, actions, evolution, or Phase-9 durable
> identity is introduced. Every newly repaired Round-6 finding is **FIX INTEGRATED
> — PENDING INDEPENDENT CLOSURE REVIEW**; this document does not self-close it.
>
> **Verified against `00a9fe2cc758af529eea1ae018687b79a9cb2bf4`** (`git rev-parse
> HEAD` confirmed in this worktree; ownership resolver run
> over all 3,086 entries; every golden recomputed and cross-checked; helper names
> and line numbers checked against the real tree). Specification-only: no code, no sync, no
> commit, no push.
>
> **Round-7 independent review & B7:** a fresh Codex session (`01a0513f-860c-7731-970d-a01d605d40eb`, no memory) passed **classification totality YES** and **persistent-state determinism YES**, closed all six Round-6 blockers and five majors, reproduced every golden, and found one new blocker B7 (exact-retry admission had two outcomes). v6-4 closes B7 by a local admission-precedence clause (§2/§5.4/§5.7 mechanically identical ordering; same-ID/hash precedes base check), states the generic §10 head assignments, and integrates three category-A static validator hardenings (§11.6). No golden changed; no other closed semantics touched.
>
> **Accounting:** Round-6 already-CLOSED findings retain that disposition. Every
> newly repaired finding below is `FIX INTEGRATED — PENDING INDEPENDENT CLOSURE
> REVIEW`; nothing newly repaired is self-marked CLOSED.
>
> **Round-5 Gate Contract & Option-C arbitration:** the boundary was ratified by Codex
> session `01a04e1b-7ae6-7741-af3b-22d6f8872191`; the R5-B5 Option-C semantics were
> arbitrated in the same session. v6-4 carries the ratified boundary text (§2), incorporates
> the genesis inventory before token computation with a fully-specified extraction algorithm
> (§12), and integrates Option C (§7.4.1). Round-6's CLOSED labels for R5-B2, R5-B3,
> candidate cardinality, and production genesis are preserved; every newly repaired finding
> uses the pending-independent-review label. R5-B5 remains Option C ratified. No newly
> repaired finding is self-marked CLOSED.

---

## 1. Scope / Non-goals

**In scope:** `verified acquisition → adapter observation → diagnostics → source
health → minimal persistent freshness state → freshness classification/reporting`.

**Out of scope (removed, not "closed"):** accepted artifact; publication governance
or atomicity; manual actions; action snapshots; recovery journal; disaster
recovery; transactional multi-kind HEAD DB; schema/policy/registry evolution;
migration; automatic deletion; automatic terminal STALE; durable cross-source
identity (Phase 9). **CORE observes and classifies; it does not decide what to
publish or delete.**

## 2. Valid-input domain & orchestrator contract (normative)

CORE is a deterministic state machine over **valid** inputs. The boundary of that
validity is itself normative, not an operational note. The following text is the
binding boundary ratified in the Round-5 Gate Contract.

**Observation uniqueness precondition.** Let `T` be a canonical committed
`base_state` token. For each `T`, the orchestrator MUST construct and submit at most
one distinct canonical observation byte string `O`. It MAY deliver `O` any number of
times, concurrently or sequentially; every such delivery is an exact retry. The
orchestrator MUST NOT reacquire, reconstruct, rebase, or submit a different canonical
observation `O2 != O` while still claiming `T`. A different observation for the next
transition MUST be constructed from a newly committed base-state token.

**Observation identity.** Two deliveries are the same observation **if and only if**
their complete canonical observation bytes are byte-identical. Equality of
`observation_id` alone is insufficient. Different canonical bytes imply different
observation hashes and therefore distinct observations.

**Successor binding.** Every observation MUST contain its complete `base_state` token,
and `observation_id` MUST equal `base_state.last_observation_id + 1`. The base token
participates in canonical observation bytes and the observation hash. The token is
immutable after the acquisition cycle begins.

**Caller conformance.** Observation construction MUST be a pure function of the
committed base token and the verified acquisition bundle. A conforming orchestrator
MUST have one logical observation-construction path per base token. Concurrent delivery
workers may receive only the already-finalized byte-identical observation; they may not
independently reacquire or reconstruct it.

**Detectable violation (admission precedence is total and matches §5.4 exactly).** The
same-ID branches are evaluated **first**, before any base/locked-token comparison:
1. If a submitted observation reuses the committed `observation_id` (i.e.
   `observation_id == locked_current.last_observation_id`) **with the same committed hash**,
   CORE MUST return `IDEMPOTENT_NO_OP`, perform no mutation, and produce no report — this is
   the expressly valid byte-identical retry, and it takes precedence even though the
   observation still embeds its pre-commit base token (which necessarily differs from the
   now-advanced locked token).
2. If it reuses the committed `observation_id` **with a different hash**, CORE MUST return
   `SAME_ID_DIFFERENT_HASH_CONFLICT`, perform no mutation, and produce no report.
3. **Only after the same-ID branches have been excluded** does the base rule apply: if the
   embedded base token does not equal the request's API-entry token or the locked
   current-state token, CORE MUST return `PRECONDITION_MISMATCH`, perform no mutation, and
   produce no report.
This precedence is **mechanically identical** to the ordered admission algorithm in §5.4:
the `observation_id == C.last_observation_id` test (steps 1–2 here) is evaluated before the
`B != state_token(C)` test (step 3 here). There is **no** unconditional locked-base-mismatch
requirement that can precede the same-ID/same-hash retry detection; a byte-identical exact
retry of an already-committed observation is always `IDEMPOTENT_NO_OP`, never
`PRECONDITION_MISMATCH`.

**Undetectable violation.** CORE is **not required** to detect two different,
not-yet-committed observations that concurrently claim the same current base token. Such
a pair violates the input-validity precondition and is **outside the CORE valid-input
domain**. Nondeterministic behavior caused **solely** by that violation is **not** an
internal CORE determinism defect. (This is the exact limit of the boundary:
first-lock-wins is not the semantics, and CORE does not arbitrate conflicting same-base
candidates — doing so would require a scheduler/queue/reservation journal, out of scope.)

**No implicit repair.** CORE MUST NOT queue, order, merge, choose between, or
automatically rebase distinct observations claiming one base token.

**Binding caller invariants** (normative architecture the orchestrator MUST satisfy —
not "should normally"): one observation-builder invocation per base token;
`observation_id` **derived** from `base.last_observation_id + 1`, never independently
assigned; finalized canonical bytes are immutable; concurrent delivery workers receive
only those finalized identical bytes; a second acquisition/build attempt for the same
token is rejected at the caller boundary; a rebase requires reading a newly committed
token and produces a new observation. Conformance is demonstrated by these caller
invariants and conformance tests, not provable from a single request without adding an
authority/reservation mechanism (which CORE does not have).

**Scope-honest statement of effect.** A submission that CORE *can* detect as
out-of-contract (§5 detectable cases) is rejected fail-closed (no mutation, no report).
A submission that CORE *cannot* detect — two distinct not-yet-committed observations on
the same base token — is an out-of-domain caller violation; CORE does not promise
deterministic arbitration for it, and any nondeterminism arising **solely** from that
violation is not a CORE defect. CORE never produces a divergent committed state from
**in-domain** input.

## 3. Canonical JSON contract (one bytes→bytes function)

Every hashed or persisted structure (observation, AdapterResult, emitted-entry,
material projection, state body, state envelope, report) uses exactly this:
- **Encoding** UTF-8. **Unicode:** NFC-normalize every string (keys and values)
  before sorting, comparison, and hashing.
- **String order** = lexicographic over **Unicode scalar values (code points)**,
  never UTF-16 code units.
- **Object keys** sorted by that order; **duplicate NFC-normalized key ⇒ hard fail.**
- **Escaping — one form per character, no alternatives:** the seven short escapes
  `\" \\ \n \r \t \b \f` for those characters; every **other** control character
  U+0000–U+001F ⇒ `\u00XX` with **lowercase** hex; **no other character is
  escaped** (all non-ASCII emitted literally as UTF-8, e.g. `é` stays `é`, never
  `\u00e9`). This is a unique bytes→bytes serializer.
- **Numbers** integers only, `allow_nan=false`; **booleans/null** literal; nullable
  fields written explicitly as `null`, never omitted.
- **Separators** `(",",":")`; `ensure_ascii=false`.
- **Array order (explicit sort tuples):** `results` sorted by `source`; `rejected`
  and `unmapped` sorted by `(input_ref, code)` with **multiplicity preserved**;
  **`duplicate_ids` normalized as
  sorted-by-code-point-after-NFC and de-duplicated (R5-B3)**; `emitted_entries` is an
  **object keyed by entry id** (order = key order); state `entries` sorted by `entry_id`;
  each entry's `sources` sorted by `source`; `owner_sources`, `source_data_projects`,
  `declared_sources` sorted **and de-duplicated**. **Every list-valued field that is part
  of canonical bytes has a stated total order; no field relies on insertion/detection order.**
- **Hash grammar** every digest is `sha256:` + exactly 64 lowercase hex.
- **Terminal newline** exactly one `\n` on the persisted `state.json` file only;
  hashed byte-strings (observation_hash input, body-for-checksum) carry **none**.

**Material/command array ordering (self-contained; §14 uses it) — total (R5-B4):**
First, **the `placeholders` array inside every projected command is canonicalized:
sorted by code-point order after NFC and de-duplicated; if the result is empty, the field
is omitted** under the universal omit-empty rule (§14). Non-empty emitted bytes carry the
sorted array, so commands whose placeholders are permutations of each other
(`["A","B"]` vs `["B","A"]`) become **byte-identical** objects, and
`{"template":"X","placeholders":[]}` and `{"template":"X"}` both become
`{"template":"X"}`.
Then commands sort by the tuple `(template, tuple(placeholders_canonical), comment,
canonical_bytes(command))` where an **omitted `comment` sorts as the empty string `""`**
and **omitted `placeholders` sorts as the empty tuple**, and the **final component
`canonical_bytes(command)` is a total tie-breaker** so no two commands can share a sort key
(if the first three components tie, the full canonical bytes decide; two commands with
identical canonical bytes are identical and their order is immaterial). This makes command
ordering **total and permutation-invariant**: the A/B placeholder permutation yields one
canonical result and one fingerprint. In the emitted object **all** empty optional material
values are omitted, including an empty `placeholders` array; a non-empty `placeholders`
array is emitted only in canonical sorted/de-duplicated form.
Every material array (`aliases, phases, capabilities, attack_techniques, preconditions,
references, tags`, and `opsec.detection_refs`) is sorted by code-point order after NFC **and
de-duplicated**; detail objects (`technique_detail, driver_detail`) have keys sorted by
code-point order.

## 4. SOURCE_UNIVERSE + observation validation (before any transition)

`SOURCE_UNIVERSE = {GTFOBins, LOLAD, LOLBAS, LOLDrivers, WADComs}`. An observation is
**HARD INVALID (fail closed, no mutation, no report)** unless all hold:
- `results` contains **exactly one** AdapterResult per SOURCE_UNIVERSE source — no
  duplicates, none missing, none unknown. Duplicate/missing/unknown source ⇒ invalid.
- A source not run appears **exactly** as the NOT_RUN shape (§6.1).
- counts are non-negative integers; `inputs_total == parsed_ok + len(rejected)` per result.
- `acquired_ok == true ⇒ resolved_revision` is exactly 40 lowercase hex;
  `acquired_ok == false ⇒ resolved_revision == null` (biconditional).
- every result satisfies the exact NOT_RUN/source-level/candidate-level status and emission
  matrix (§6.0, §6.1, §7.2); in particular source-level failure has zero candidates and
  emissions, while candidate-derived non-ok status retains every parsed sibling emission.
- every `unmapped[].suppressing` equals the §7.3 table.
- every emitted entry in every status has a valid material fingerprint and the exact
  identity shape (§6.0.1): STABLE emitters have non-null correct-kind identities and NONE
  emitters have null; `keys(emitted_entries)` has no duplicate NFC-normalized id.
- every candidate reference is the §6.2.1 output (or its reserved invalid-path sentinel),
  every collision group has the reject-all §7.2c disposition, and rejected/unmapped
  multiplicity has not been collapsed.
- `observation_id` is a non-negative integer; the `base_state` object (§5) is present
  and well-formed.
- **emitter membership (§8.4):** if an emitted entry resolves to a RESOLVED owner set,
  its emitter source MUST be in that set, else HARD INVALID.

Validation runs entirely **before** admission and transition.

## 5. Admission — snapshot-bound, deterministic across lock handoffs

Closes the concurrent-admission divergence: admission is a function of a **frozen**
committed-state token, not of lock-acquisition order.

**5.1 State token.**
```
state_token(envelope) = { core_state_version, last_observation_id,
                          last_observation_hash, state_checksum = envelope.checksum }
```
Equality is exact field equality after canonical validation; `state_checksum` binds
the whole body.

**5.2 Two immutable captures.**
- **Cycle-start capture** (orchestrator, before acquisition/adapters): atomically
  read committed `state.json` (or derive virtual genesis §12), validate fully, freeze
  its `state_token` as `observation.base_state`, set `observation_id =
  base.last_observation_id + 1`. The token MUST NOT be refreshed while building or
  retrying that observation.
- **API-entry capture** (CORE, before waiting on `flock`): read+validate the currently
  committed state, store its token as `arrival_token`, canonicalize+hash the
  submitted observation. The atomic rename (§13) guarantees this read sees a complete
  old or complete new state.

**5.3 `base_state` is part of the observation** and therefore of `observation_hash`:
```
observation = { observation_id:int, base_state:{core_state_version,last_observation_id,
                last_observation_hash,state_checksum}, results:[AdapterResult,...] }
```
Successor invariant: `observation_id == base_state.last_observation_id + 1`; violation
⇒ `INVALID_SUCCESSOR`, hard-invalid, no mutation, no report.

**5.4 Admission algorithm.**
```
validate schema + canonical fields (§3,§4)
obs_hash := sha256(canonical(observation))
A := arrival_token ; B := observation.base_state
# arrival-time
if observation_id == A.last_observation_id:
    return obs_hash==A.last_observation_hash ? IDEMPOTENT_NO_OP : SAME_ID_DIFFERENT_HASH_CONFLICT   (no mutation)
if observation_id <  A.last_observation_id:  return STALE                         (no mutation)
if observation_id != B.last_observation_id+1: return INVALID_SUCCESSOR            (no mutation)
if B != A:                                    return PRECONDITION_MISMATCH         (no mutation)
acquire whole-operation exclusive lock; read+validate committed state C
if observation_id == C.last_observation_id:
    return obs_hash==C.last_observation_hash ? IDEMPOTENT_NO_OP : SAME_ID_DIFFERENT_HASH_CONFLICT
if observation_id <  C.last_observation_id:   return STALE
if arrival_token != B or B != state_token(C): return PRECONDITION_MISMATCH
# equalities now imply observation_id == C.last_observation_id + 1
apply exactly one transition (§8,§9,§10); commit via temp/fsync/rename (§13); return applied report
```
`INVALID_SUCCESSOR`/`PRECONDITION_MISMATCH`/`STALE` are **permanent** rejections,
never reinterpreted against a later state.

**Admission result/report totality:** only the one `APPLIED` path constructs and returns the
§15 report. `IDEMPOTENT_NO_OP` returns `report:null` (it neither recomputes nor replays the
prior report). Every hard-invalid or rejected outcome, including
`SAME_ID_DIFFERENT_HASH_CONFLICT`, `STALE`, `INVALID_SUCCESSOR`, and
`PRECONDITION_MISMATCH`, also returns `report:null`. Thus an exact retry cannot choose
between a cached report and no report.

**5.5 Retry vs rebase.** *Same observation* = byte-identical canonical object (same id,
base, hash). *Exact retry after pre-commit crash* = still admissible (base still
equals current). *Exact retry after successful rename* = `IDEMPOTENT_NO_OP`. *Exact
retry after rejection* = same permanent rejection. *Rebase* (changing `base_state`,
even keeping the numeric id or AdapterResults) = a **new** observation with a new hash,
not a retry. Ordering exact retries cannot change state: each is the one commit, a
no-op, or the same permanent rejection.

**5.6 Concurrent 10/11 (proof, both interleavings).** Initial committed token `T9`,
`E=NOT_OBSERVED/1`; both requests enter under `T9` ⇒ both get `arrival=base=T9`. A
conforming object built from `T9` must have id 10; an object labeled 11 with `base=T9`
fails `11 != 9+1`.
- Order A (11 then 10): 11 rejected `INVALID_SUCCESSOR`; 10 applies ⇒ `NOT_OBSERVED/2, L=10`.
- Order B (10 then waiting 11): 10 applies, commits `L=10`; 11 has immutable `base=T9`,
  still fails the successor rule (and `B != state_token(C)`) ⇒ rejected ⇒ `NOT_OBSERVED/2, L=10`.
Both interleavings reach the **identical** committed state. To apply 11 the caller must
build a **new** observation on the committed `T10`; that is an additional submission,
not a retry from the concurrent set.

**5.7 Concurrent byte-identical delivery + exact-retry precedence (B7).** Two byte-identical
deliveries of the same valid observation `O` (same id, base, hash): one worker acquires the
lock first, applies the transition, commits (advancing the locked token). The waiting worker
then acquires the lock, reads committed state `C`, and evaluates §5.4: `observation_id ==
C.last_observation_id` is now true and `obs_hash == C.last_observation_hash` is true, so it
returns `IDEMPOTENT_NO_OP` at that branch — **before** the base comparison — even though `O`
still embeds its pre-commit base token `B != state_token(C)`. The same-ID/same-hash branch
has precedence (§2, §5.4); the embedded stale base does **not** turn the committed retry into
`PRECONDITION_MISMATCH`. Result: exactly one commit plus one idempotent no-op, deterministic
regardless of interleaving.

**5.7.1 B7 regression vector (printed G2/G3).** Fixture genesis token `T0`; apply printed
G2 ⇒ committed G3 with token `T1` (`last_observation_id=1`, `last_observation_hash=`G2 hash).
Now deliver the **exact same 1,705-byte G2** again. G2 embeds base `T0`; committed current is
`T1`, so `T0 != T1`. The unique conforming result:
- §5.4 arrival/locked branch: `observation_id(=1) == C.last_observation_id(=1)` **and**
  `obs_hash == C.last_observation_hash` ⇒ `IDEMPOTENT_NO_OP`.
- `report:null`; **no** state mutation; persisted bytes remain **exactly** G3 (581-byte body,
  checksum `sha256:286048e4…`).
`PRECONDITION_MISMATCH` is **non-conforming** here: the stale embedded base `T0` is reached
only after the same-ID branch, which already returned NO_OP. This is the sole legal admission
outcome, matching §2's precedence.

## 6. AdapterResult schema + NOT_RUN shape

```
AdapterResult = { source, acquired_ok, resolved_revision, status, primary_reason,
  inputs_total, parsed_ok, rejected:[{input_ref,code}], unmapped:[{input_ref,code,suppressing}],
  duplicate_ids:[id], emitted_entries:{ id: {material_fingerprint, owner_evidence, upstream_identity} } }
```
Ids are **derived**: `emitted_ids := sorted(keys(emitted_entries))` (no separate list that can disagree).

**6.0 Exact AdapterResult schema (Major 5 — every field pinned).** All fields required, no
undeclared fields, key order canonical (§3):
- `source`: string, exactly one `SU` member. `acquired_ok`: boolean.
- `resolved_revision`: string of exactly 40 lowercase hex **iff** `acquired_ok==true`, else
  `null` (biconditional §4).
- `status`: string ∈ `{"ok","partial","failed","unknown"}`. `primary_reason`: string, one of
  the §7.2 source-level, candidate-level, or derived diagnostic reasons, or `"NONE"` or
  `"NOT_RUN"`. `status`↔`primary_reason` is the biconditional in §7.2.
- `inputs_total`,`parsed_ok`: integers ≥0, `inputs_total == parsed_ok + len(rejected)`.
- `rejected`: array of `{input_ref:string(§6.2.1), code:string(one
  `CANDIDATE_REJECT_ENUM`, §7.2b)}`, ordered by `(input_ref,code)` with
  **multiplicity preserved**. One array element represents one candidate's one terminal
  rejection; byte-identical elements from distinct candidates are retained, never
  de-duplicated.
- `unmapped`: array of `{input_ref:string, code:string(one UNMAPPED_ENUM, §7.3),
  suppressing:boolean(exact §7.3 bit)}`, ordered by `(input_ref,code)` **preserving
  multiplicity** (NOT de-duplicated — §7.4.1).
- `duplicate_ids`: array of entry-id strings, NFC, sorted code-point, **de-duplicated** (§3).
- `emitted_entries`: object keyed by entry-id string; each value is an **emitted entry**
  (§6.0.1). Empty object allowed. Keys unique by construction.
- **Cross-field:** every emitted entry in every status has a valid non-null
  `material_fingerprint`; a rejected candidate emits nothing; `emitted_entries` is exactly
  the union of emissions from terminally parsed candidates after the reject-all collision
  rules (§7.2c); and `source` of every emitter ∈ the resolved owner set (§8.4).

**6.0.1 Emitted entry / owner_evidence / upstream_identity (exact).**
- **emitted entry** = `{material_fingerprint:string("sha256:"+64 lowercase hex, never null
  for an ok source), owner_evidence:{…}, upstream_identity:{…}|null}`. No other fields.
- **owner_evidence** = `{source_data_projects:[SU…], declared_sources:[SU…],
  id_prefix:string}`. Both arrays: only exact SU members, sorted, **de-duplicated**, may be
  empty. `id_prefix`: the raw prefix substring (before first `/`) of the entry id, case
  preserved; used for diagnostics only, never compared to a canonical source name.
- **upstream_identity** = `null` **iff** the emitter's `IDENTITY_MODE` (§9.1) is `NONE`.
  Every entry emitted by a `STABLE` source — regardless of the result's aggregate health
  status — MUST instead carry `{kind:string, value:string}` where `kind` equals that source's declared kind exactly
  (`"gtfobins_natural_key"` for GTFOBins, `"loldrivers_id"` for LOLDrivers) and `value` is a
  **non-empty** string. No other shape; a non-null identity from a NONE source ⇒ HARD INVALID
  (§9.1), as does a null identity from a STABLE source.
- **Non-ok emission semantics (pinned, no remaining choice):** `ok`, `partial`, and a
  **candidate-failure-derived** `failed` result emit **exactly** the entries from their
  terminally parsed candidates. A rejected candidate contributes zero emissions; a
  reject-all path/ID collision group contributes zero emissions for every member; every
  parsed non-colliding sibling survives. A **source-level** `ACQUISITION_FAILED` or
  `EMPTY_INPUT_SET` result has zero candidates and MUST emit `{}`. An empty-code context
  does not remove its file's valid sibling emissions (§7.4.1 Option C). Status never
  independently erases or restores emissions; §7.2d gives the exhaustive status/category
  matrix.

**6.1 NOT_RUN shape (exact; `status:"unknown" iff primary_reason:"NOT_RUN"`):**
```
{ source:<SU member>, acquired_ok:false, resolved_revision:null, status:"unknown",
  primary_reason:"NOT_RUN", inputs_total:0, parsed_ok:0, rejected:[], unmapped:[],
  duplicate_ids:[], emitted_entries:{} }
```
No cached/previous/predicted/shortened revision may appear anywhere (biconditional §4).

**6.2 Seven precise definitions (self-contained; no "deterministic/canonical/stable" left undefined):**
1. **`input_ref` grammar (single exact function — Major 4).**
   Let `checkout_root` be the verified acquisition bundle's repository root. Its host-absolute
   spelling is never data and never enters canonical bytes. Each source has exactly this
   literal acquisition root and canonical source prefix:

   | source | acquisition root | source prefix |
   |---|---|---|
   | GTFOBins | `checkout_root/_gtfobins` | `_gtfobins/` |
   | LOLBAS | `checkout_root/yml` | `yml/` |
   | WADComs | `checkout_root/_wadcoms` | `_wadcoms/` |
   | LOLAD | `checkout_root` | the empty string `""` |
   | LOLDrivers | `checkout_root/yaml` | `yaml/` |

   LOLAD's acquired file is therefore the non-empty root-relative name `index.html`; the
   file itself is never treated as the root. `canonical_input_ref(source, raw_name, locator)`
   is the following exact function, with no source-specific exception:

   1. Acquisition first expresses the candidate file as the Unicode string `raw_name`
      relative to the table's exact acquisition root. Supplying a host-absolute name to this
      function does not authorize root stripping and is path-invalid.
   2. Replace every U+005C REVERSE SOLIDUS (`\`) with U+002F SOLIDUS (`/`), then NFC-normalize
      the whole string. Case is preserved exactly and never folded. Before removing segments,
      a string beginning `/` or matching ASCII `^[A-Za-z]:($|/)` is absolute and path-invalid.
   3. Split on `/`; discard empty components produced by repeated or trailing separators and
      discard every component exactly `.`. If any component is exactly `..`, or if no component
      remains, the name is path-invalid. Otherwise join the remaining components with one `/`
      and NFC-normalize once more. Thus `a//./b/` becomes `a/b`; `.` and the empty string are
      invalid; `a/../b`, `/a`, `C:/a`, and `C:` are invalid.
   4. Escape the normalized relative path by these **ordered** replacements over the complete
      path string: first `%` → `%25`, then `#` → `%23` (uppercase hex). No other character is
      percent-escaped or decoded; `/` remains the segment separator and all other Unicode
      scalars remain literal subject to §3 JSON escaping. This is injective over normalized
      paths: literal `a#b` becomes `a%23b`, while literal `a%23b` becomes `a%2523b`.
   5. Form `canonical_path := SOURCE_PREFIX[source] + escaped_relative_path`. For a file
      candidate (including a synthetic whole-document candidate), `locator` is `FILE` and the
      result is `canonical_path + "#"`. For a LOLAD row, `locator` is `ROW(n)`, where `n` is
      the non-negative 0-based index among candidate rows before truncation, and the result is
      `canonical_path + "#row=" + decimal(n)` with no leading zero except `0`. Any other
      locator is path-invalid.

   A path-invalid candidate has exactly one terminal disposition:
   `MALFORMED_RECORD`, zero emissions, and the reserved rejection reference
   `invalid_path_ref(source) := SOURCE_PREFIX[source] + "#invalid-path"`. Because every valid
   path is non-empty, this sentinel cannot equal a valid record reference. Distinct invalid
   candidates produce repeated rejection elements; §3/§6.0 preserve that multiplicity.

   **Normalized-reference collision (fail closed).** Before parsing or emitting, group all
   structurally valid candidates by their complete `canonical_input_ref`. If a group contains
   `N>1` distinct candidates, all `N` are rejected with
   `NORMALIZED_PATH_COLLISION`; none is parsed or emits; all `N` byte-identical rejection
   elements remain in `rejected`; and the group does not participate in duplicate-ID
   derivation. Non-colliding siblings continue. This rule covers distinct filesystem names
   collapsed by separator/`.` normalization or NFC and cannot be discovery-order dependent.
   LOLAD rows have distinct `ROW(n)` locators, so normal rows of `index.html` do not collide.

   The ratified Option-C form is generated by this general function: for GTFOBins
   `raw_name=<canonical relative path>` and `locator=FILE` yield exactly
   `_gtfobins/<escaped-canonical-relative-path>#`. There is no root-stripping exception and
   no host path in the result. Source-level failures (§7.2a) have no candidate and therefore
   no `input_ref` at all.
2. **Candidate-unit enumeration (self-contained; consistent with Option C §7.4.1).** GTFOBins:
   the candidate unit is the **file**; if `_frontmatter()` returns a dict, each
   `(binary,function,context)` triple that reaches emission is **not** a separate candidate —
   the file is the single candidate. A within-file **empty-code context** adds one
   non-suppressing `EMPTY_CODE_CONTEXT` diagnostic (§7.4.1), the file stays `parsed_ok`, and
   **valid siblings survive**. A within-file genuinely malformed function/context (e.g.
   `functions` not a map) makes the **file** `MALFORMED_RECORD` (rejected, zero emissions).
   LOLBAS: the file is the candidate; a malformed `Commands`/`Detection` item rejects the
   whole file as `MALFORMED_RECORD` with zero emissions, while only the exact unknown-value
   cases in §7.3/§7.5 add diagnostics. Neither condition creates a new candidate. (One candidate per file for all
   file-per-entry adapters; lolad rows are per-row candidates.)
3. **Path normalization in diagnostics.** Every candidate rejection and diagnostic uses the
   one §6.2.1 function; no second diagnostic normalization exists. Parsed-candidate
   diagnostics use that candidate's record reference. Path-invalid candidates use only the
   reserved sentinel and cannot emit diagnostics. Source-level failures have no diagnostic
   or rejection row.
4. **`canonical input order` before every truncation.** When a rule retains "the first N"
   (SUBSET_TRUNCATED), "first" is defined over the **source's own emission order for that
   record as produced by the adapter reading the upstream file top-to-bottom** — i.e. the
   list/document order in the upstream YAML/HTML, index 0 first. Truncation keeps the
   lowest indices; the retained items are then canonically **sorted** only when placed in
   `project_material_v1` (§14). Truncation order and material sort order are distinct and
   both defined.
5. **Virtual-genesis body/bytes/checksum/token:** §12 (printed in full).
6. **Material-array ordering:** §3 + §14, fully defined here, inherited from no other doc.
7. **Malformed YAML scalar shapes (parser-independent).** To make health independent of
   YAML 1.1-vs-1.2 resolution, CORE mandates a **fixed schema**: parse with the YAML 1.1
   `safe` schema (PyYAML `yaml.safe_load` behavior), then apply **type checks on the
   resolved value**, never on the raw text. Where a **string** is required and the resolved
   value is a non-string scalar (bool, int, float, timestamp, or any tagged scalar) ⇒
   `MALFORMED_RECORD` (**never coerced**, so `yes`/`no`/`on`/dates cannot silently become
   strings and cannot differ across parsers); where a **list** is required and a scalar/map
   appears ⇒ `MALFORMED_RECORD`; where a **mapping** is required and a scalar/list appears ⇒
   `MALFORMED_RECORD` (or `NON_DICT_DOCUMENT` at document root); a null where a required
   field is expected ⇒ `MISSING_REQUIRED_FIELD`. A YAML alias/anchor resolves to its target
   value before typing. The one required cross-language rule: **a non-string resolved scalar
   in a required-string position is `MALFORMED_RECORD` regardless of parser**; implementations
   MUST NOT apply `str(value)` coercion. Because the schema and the resolved-type checks are
   fixed, YAML 1.1 vs 1.2 boolean/number resolution differences cannot change any health
   outcome.

## 7. Health — totality, precedence, suppression (no silent skip)

**7.1 No-silent-skip invariant.** Every acquired candidate unit terminates in exactly one
of `parsed_ok` or `rejected:<one CANDIDATE_REJECT_ENUM>` (§7.2b). A parsed unit may add zero or more
`unmapped` diagnostics (§7.3), including one non-suppressing `EMPTY_CODE_CONTEXT` per
empty-code context (§7.4.1) — an empty-code context is **tracked as a diagnostic on a parsed
file, never silently dropped and never a rejection**. A candidate reaching **no** explicit
adapter rule ⇒ `rejected += MALFORMED_RECORD`. An uncaught exception ⇒ `rejected +=
UNEXPECTED_EXCEPTION` only when no specific defect applies. `inputs_total == parsed_ok +
len(rejected)` is mandatory, and `rejected` preserves one element per rejected candidate
even when several elements have identical canonical bytes. A source-level failure has zero
acquired candidates and uses §7.2a instead of inventing a candidate.

**7.2 Primary-reason precedence (rank, first present wins):**
`1 ACQUISITION_FAILED·failed | 2 EMPTY_INPUT_SET·failed | 3 INVALID_ENCODING·failed |
4 IO_ERROR·failed | 5 PARSE_ERROR·failed | 6 EMPTY_DOCUMENT·failed | 7 NON_DICT_DOCUMENT·failed |
8 UNEXPECTED_EXCEPTION·failed | 9 NORMALIZED_PATH_COLLISION·failed |
10 DUPLICATE_ID·failed | 11 MISSING_REQUIRED_FIELD·partial |
12 MALFORMED_RECORD·partial | 13 SUPPRESSING_UNMAPPED·partial | NOT_RUN(exclusive)·unknown |
none·NONE/ok`. Algorithm: if NOT_RUN, require the exact shape; else `primary_reason :=
lowest-ranked present **terminal/source/derived** reason (or NONE)`, `status :=
STATUS_OF[primary_reason]`. A source-level reason, when present, is exclusive and therefore
wins without manufacturing a rejection. Otherwise the present reasons are the codes in
`rejected` plus `SUPPRESSING_UNMAPPED` iff a parsed candidate has ≥1 suppressing diagnostic.
Non-suppressing unmapped diagnostics add **no** reason flag.
Freshness: `status==ok ⇒ evaluate presence+continuity`; `status!=ok ⇒ owner outcome
HEALTH_HOLD, no evidence mutation`.

**7.2a SOURCE_FAILURE_ENUM (complete; zero-candidate only).** These values may be
`primary_reason` but MUST NOT occur in `rejected[].code`:

- `ACQUISITION_FAILED` · rank 1 · failed: the verified checkout/revision could not be
  acquired as one usable bundle. Exact result shape (for source `S`) is
  `{source:S, acquired_ok:false, resolved_revision:null, status:"failed",
  primary_reason:"ACQUISITION_FAILED", inputs_total:0, parsed_ok:0, rejected:[],
  unmapped:[], duplicate_ids:[], emitted_entries:{}}`.
- `EMPTY_INPUT_SET` · rank 2 · failed: acquisition succeeded and the source's authoritative
  candidate enumeration (§7.4) produced zero candidate or synthetic units. Exact shape is
  `{source:S, acquired_ok:true, resolved_revision:R, status:"failed",
  primary_reason:"EMPTY_INPUT_SET", inputs_total:0, parsed_ok:0, rejected:[], unmapped:[],
  duplicate_ids:[], emitted_entries:{}}`, where `R` is exactly 40 lowercase hex.

Both shapes have zero candidates, zero diagnostics, zero duplicate IDs, and zero emissions.
`ACQUISITION_FAILED` is the only run result other than NOT_RUN with `acquired_ok:false`;
`EMPTY_INPUT_SET` is acquired successfully and therefore carries its revision. Source-level
failure is exclusive: it cannot coexist with candidate accounting or candidate-level reasons.

**7.2b CANDIDATE_REJECT_ENUM (complete, normative — Major 1).**
`rejected[].code` MUST be exactly one of these; unknown ⇒ HARD INVALID (§4). Every member
is candidate-level, contributes one element to `len(rejected)`, and its candidate emits zero:

- `INVALID_ENCODING` · rank 3 · failed: bytes not decodable under the declared encoding.
- `IO_ERROR` · rank 4 · failed: read failure on an enumerated candidate.
- `PARSE_ERROR` · rank 5 · failed: YAML/HTML parse raised.
- `EMPTY_DOCUMENT` · rank 6 · failed: parsed document is empty/None.
- `NON_DICT_DOCUMENT` · rank 7 · failed: document root is not the required mapping.
- `UNEXPECTED_EXCEPTION` · rank 8 · failed: uncaught exception with no mapped specific defect.
- `NORMALIZED_PATH_COLLISION` · rank 9 · failed: §6.2.1 reject-all canonical-ref group.
- `DUPLICATE_ID` · rank 10 · failed: §7.2c reject-all derived-entry-ID group.
- `MISSING_REQUIRED_FIELD` · rank 11 · partial: required field absent/null.
- `MALFORMED_RECORD` · rank 12 · partial: parsed record violates a shape/path/locator rule
  with no more specific code; catch-all for a candidate reaching no explicit adapter rule.

Empty-code contexts are not rejected. `SUPPRESSING_UNMAPPED` (rank 13, partial) is not a
candidate code; it is derived iff a parsed candidate carries a suppressing diagnostic.

**7.2c One global collision and terminal-disposition algorithm.** For each source, construct
its complete candidate multiset using §7.4; distinct candidates are never collapsed. Apply
the same policy to every adapter. Same-ID emissions from different sources are not a
candidate collision and remain governed by multi-emitter ownership (§8.4). Then, within
each source, proceed in this exact order:

1. A structurally path-invalid candidate rejects once as `MALFORMED_RECORD` with the
   §6.2.1 sentinel.
2. Among remaining candidates, apply §6.2.1 normalized-ref grouping. Every member of each
   `N>1` group rejects once as `NORMALIZED_PATH_COLLISION`.
3. Provisionally derive every syntactically valid entry-ID occurrence from each remaining
   candidate, without yet emitting. Group occurrences by NFC-normalized ID. An ID collides
   if its group contains occurrences from `N>1` distinct candidates **or more than one
   occurrence from one candidate**. Every candidate participating in any colliding-ID group
   rejects exactly once as `DUPLICATE_ID`; no participating candidate is parsed_ok and none
   of any participating candidate's sibling entries emit, even if it also has another
   content defect. Add every colliding ID exactly once to `duplicate_ids`. Overlapping
   groups reject the union of their candidate members once each. Two-candidate,
   three-candidate, and within-one-file duplicate-emission groups use this same rule.
4. For each still-undisposed candidate, determine all applicable specific defects and select
   exactly one by this precedence:
   `INVALID_ENCODING > IO_ERROR > PARSE_ERROR > EMPTY_DOCUMENT > NON_DICT_DOCUMENT >
   MISSING_REQUIRED_FIELD > MALFORMED_RECORD > UNEXPECTED_EXCEPTION`. A predicate that
   cannot be evaluated because an earlier structural/read/parse failure prevented its inputs
   is not applicable. `UNEXPECTED_EXCEPTION` is last and applies only when no mapped defect
   does. If no rejection condition applies, the candidate is `parsed_ok`.

Thus every candidate has exactly one terminal disposition. Collision membership outranks
candidate-local content defects, so all members of a collision group have the mandated one
collision code. `duplicate_ids` is NFC/code-point-sorted/de-duplicated metadata; it never
de-duplicates `rejected` or `unmapped`. Discovery order selects no winner.

This is the one collision policy for **AdapterResult candidate processing across all five
adapters**. §12's already-ratified production-genesis inventory scan is not an adapter
observation or candidate health pass; its explicit sorted-path seed de-duplication remains a
separate closed genesis rule and does not select an observation emission winner.

**7.2d Failed/partial emissions and status matrix (Major 5).** This table is exhaustive:

| category | acquired/count shape | emissions | status/reason |
|---|---|---|---|
| NOT_RUN | exact §6.1 | `{}` | `unknown/NOT_RUN` |
| source acquisition failure | exact §7.2a; zero candidates | `{}` | `failed/ACQUISITION_FAILED` |
| acquired empty input | exact §7.2a; zero candidates | `{}` | `failed/EMPTY_INPUT_SET` |
| acquired candidates | `acquired_ok:true`, revision set, count equation | exactly all and only terminally parsed candidate emissions | §7.2 precedence |

For the last row, a candidate-level failed reason may coexist with non-empty
`emitted_entries` **iff** a different non-colliding candidate is terminally parsed and emits;
all such sibling emissions MUST be retained. `partial` uses the same survival rule. A
collision member or any other rejected candidate never emits. `status` is derived only after
all terminal dispositions and diagnostics are fixed and cannot be used to erase valid sibling
emissions. Because freshness defines PRESENT only for `status:"ok"` (§9.1), every emitted ID
in a non-ok result is report membership but supplies `HEALTH_HOLD`, not PRESENT.

**7.3 UNMAPPED_ENUM — unmapped codes & suppression bits (complete, exact; mismatch ⇒ hard
invalid).** `unmapped[].code` MUST be exactly one of the following with exactly the stated
`suppressing` bit; **no other value is valid**:
`UNKNOWN_FUNCTION:true · UNKNOWN_CATEGORY:true · UNKNOWN_ATTACK_TYPE:false ·
UNKNOWN_PRIVILEGE:false · UNKNOWN_CONTEXT:false · SUBSET_TRUNCATED:true ·
EMPTY_CODE_CONTEXT:false`. A suppressing diagnostic (`:true`) raises `SUPPRESSING_UNMAPPED`
(partial). A non-suppressing diagnostic (`:false`, incl. `EMPTY_CODE_CONTEXT`) adds **no**
reason flag and never forces HOLD. `unmapped` diagnostics are ordered by `(input_ref, code)`
**preserving multiplicity** (count-preserving, not a set) — see §7.4.1 for `EMPTY_CODE_CONTEXT`
multiplicity.

**7.4 Candidate-unit convention (subordinate to the adapter-specific cardinality in
§6.2.2).** Candidate cardinality is **defined per adapter in §6.2.2 and is authoritative**;
this section does not redefine it. For all **file-per-entry** adapters (GTFOBins, LOLBAS,
WADComs, LOLDrivers) the candidate unit is **the file — one candidate per file** — and the
enumeration of nested functions/contexts/commands/items does **NOT** create new candidate
units. An exact §7.3 unmapped condition adds its diagnostic to a parsed file; an exact
candidate defect in §7.2b/§7.5 rejects the whole file with zero emissions. There is no
diagnostic-versus-rejection choice. For **LOLAD** the candidate unit is the **row** (per-row). Concretely:
syntactically unreadable file ⇒ one rejected synthetic file unit; file whose structure
prevents record enumeration ⇒ one rejected synthetic file unit; a readable file-per-entry
file is exactly **one** candidate regardless of how many nested functions/contexts it
contains; LOLAD header & explicitly empty-command rows are `NOT_A_RECORD`, excluded before
`inputs_total`. Source tree present with no candidate/synthetic units ⇒ `EMPTY_INPUT_SET`.
(This is the exact source-level zero-candidate shape in §7.2a and creates no rejection.)
(Option C for GTFOBins empty-code contexts, §7.4.1, is consistent with this: an empty-code
context is an internal non-suppressing diagnostic on the one parsed **file** candidate, not a
separate candidate, and valid siblings survive.)

**7.4.1 Partial-candidate emission survival — Option C, ratified by Codex (R5-B5).**
This rule **supersedes and replaces** any earlier (v5) rule that mapped a GTFOBins
empty-code context to `MALFORMED_RECORD / partial / HOLD`. There is **no** normative path
in v6-4 under which an empty-code context is treated as a suppressing `MALFORMED_RECORD` or
produces a `rejected` record. The candidate unit remains the **file**.

Ratified Option-C semantics for a GTFOBins **empty-code context** (a function/context whose
resolved `code` is empty, i.e. the historical `if not code: continue`):
- It emits **one non-suppressing `EMPTY_CODE_CONTEXT` diagnostic** into `unmapped`
  (`EMPTY_CODE_CONTEXT` is an `UNMAPPED_ENUM` member with `suppressing:false`, §7.3; it is
  **not** a `CANDIDATE_REJECT_ENUM` member, §7.2b).
- It produces **no** `rejected` record.
- **Valid sibling emissions from the same file always survive.** No emission from a valid
  sibling context is discarded because another context in that file has empty code.
- **Candidate accounting for that file:** `inputs_total += 1`, `parsed_ok += 1`,
  `rejected += 0` — **even when every context in the file has empty code** (the file parsed;
  it simply produced diagnostics and possibly zero emissions).
- **If `EMPTY_CODE_CONTEXT` is the only diagnostic condition present in the whole source:**
  `primary_reason := "NONE"`, `status := "ok"`. This condition **alone does not force
  freshness HOLD** — a source that is otherwise clean and emits its siblings stays ok, and
  its present entries classify normally.
- **One diagnostic is preserved for every empty-code context.** These diagnostics are **NOT
  de-duplicated**, including when several share an identical `(input_ref, code)`; multiplicity
  is preserved. They are canonically ordered by `(input_ref, code)` **while preserving
  multiplicity** (a stable count-preserving sort, not a set). *(Cross-fix note: this
  non-dedup rule is specific to `EMPTY_CODE_CONTEXT`/`unmapped` diagnostics; it does NOT
  apply to `duplicate_ids`, which per §3 IS de-duplicated.)*
- **Ratified `input_ref` form for this diagnostic:** call
  `canonical_input_ref(GTFOBins, raw_name, FILE)` from §6.2.1. Its result is exactly
  `"_gtfobins/" + escaped_canonical_relative_path + "#"`, including the ratified literal
  prefix and trailing `#`; normalization and ordered `%`/`#` escaping are supplied only by
  the general function. This is not an exception or a second grammar.

These bullets govern a GTFOBins file whose terminal disposition is parsed. Empty code itself
never changes that disposition. If the whole file candidate is independently rejected by a
higher-priority normalized-ref/duplicate-ID collision or a genuine file-level defect, the
candidate-level rule controls: it contributes no diagnostics or emissions. This does not map
empty code to a rejection; the context-local condition does not override the global
one-terminal-disposition rule (§7.2c).

**Rejected-candidate rule (non-empty-code cases).** For candidate-level rejections that
*are* `CANDIDATE_REJECT_ENUM` (a genuinely malformed/unreadable file, §7.2), the file is one rejected
synthetic unit and contributes **zero** emissions — a rejected file candidate emits nothing.
Empty-code is explicitly **not** such a case; it is a parsed file with a non-suppressing
diagnostic. (LOLAD is per-row, not per-file, so a malformed row rejects only that row.)

**7.5 Per-adapter total rules (verified at `00a9fe2`):**
- **GTFOBins:** YAML error ⇒ PARSE_ERROR; empty doc ⇒ EMPTY_DOCUMENT; non-dict ⇒
  NON_DICT_DOCUMENT; missing/non-map `functions` ⇒ MALFORMED_RECORD; unknown function ⇒
  UNKNOWN_FUNCTION(supp); **unknown context ⇒ UNKNOWN_CONTEXT(non-supp), record emitted,
  defaults to `user`** (gtfobins.py:144); **empty code (`if not code: continue`,
  gtfobins.py:138) ⇒ one non-suppressing `EMPTY_CODE_CONTEXT` diagnostic per §7.4.1
  (Option C); the file stays parsed (`inputs_total+=1, parsed_ok+=1, rejected+=0`), valid
  siblings survive, and this condition alone keeps `primary_reason:NONE, status:ok`.** This
  **supersedes the v5 rule** that mapped empty-code to `MALFORMED_RECORD/partial/HOLD`; that
  mapping is removed and no longer normative. Helper is `_frontmatter()` (gtfobins.py:96).
- **LOLBAS:** YAML error/non-dict ⇒ PARSE_ERROR/NON_DICT_DOCUMENT; dict without `Commands`
  ⇒ MISSING_REQUIRED_FIELD; unknown category ⇒ UNKNOWN_CATEGORY(supp); unknown privilege ⇒
  UNKNOWN_PRIVILEGE(non-supp, defaults); malformed Detection/scalar ⇒ MALFORMED_RECORD.
- **WADComs:** YAML/encoding failure ⇒ PARSE_ERROR/INVALID_ENCODING; non-dict ⇒
  NON_DICT_DOCUMENT; frontmatter without `command` ⇒ MISSING_REQUIRED_FIELD; malformed
  `attack_types`(wadcoms.py:100)/`items`(111)/**`services`(117)**/`references`(118) ⇒
  MALFORMED_RECORD (**services now explicitly covered**); unknown attack_type ⇒
  UNKNOWN_ATTACK_TYPE(non-supp); description >280 scalars or >4 references ⇒
  SUBSET_TRUNCATED(supp), retain first 280 scalars / first 4 references.
- **LOLAD:** physical `index.html` absent ⇒ ACQUISITION_FAILED; count tables first; zero
  tables ⇒ EMPTY_INPUT_SET (no rejected row); >1 table ⇒ one synthetic MALFORMED_RECORD,
  partial, no entries; exactly one table: header row excluded; empty-command row
  NOT_A_RECORD; <3 cells ⇒ MALFORMED_RECORD; empty name/non-string ⇒ MISSING_REQUIRED_FIELD;
  cells after third ignored; duplicate id after suffixing ⇒ failed.
- **LOLDrivers:** YAML/non-dict ⇒ PARSE_ERROR/NON_DICT_DOCUMENT; missing/non-string/empty
  `Id` ⇒ MISSING_REQUIRED_FIELD (**path-stem fallback forbidden**); Tags non-list ⇒
  MALFORMED_RECORD; Commands non-map/list ⇒ MALFORMED_RECORD, list len>1 ⇒ retain first +
  SUBSET_TRUNCATED; Samples list>1 ⇒ first + SUBSET_TRUNCATED; Resources list>3 ⇒ first 3 +
  SUBSET_TRUNCATED; description >200 scalars ⇒ first 200 + SUBSET_TRUNCATED; duplicate id ⇒ failed.

## 8. Ownership — PREFIX_OWNER, total resolver, one ambiguity policy

**8.1 PREFIX_OWNER (exact; case-sensitive, no folding/aliasing/locale):**
`{"gtfobins":"GTFOBins","lolad":"LOLAD","lolbas":"LOLBAS","loldrivers":"LOLDrivers","wadcoms":"WADComs"}`.
`canonical_prefix_owner(entry_id)`: `raw := substring before first "/"`; if `raw` not
exactly a key ⇒ `INVALID_PREFIX`; else `PREFIX_OWNER[raw]`. An id without `/`, empty prefix,
or unmapped prefix is hard-invalid.

**8.2 owner_evidence shape:** `{ source_data_projects:[SU...], declared_sources:[SU...],
id_prefix:<raw prefix string> }`; both arrays required, may be empty, sorted+deduped, only
exact SU members. `id_prefix` retained for diagnostics; **never compared directly to a
canonical source name.**

**8.3 Total resolver (prefix is a membership constraint, not a competing singleton):**
```
resolve_owner(entry_id, ev):
  P := canonical_prefix_owner(entry_id); if INVALID_PREFIX: return HARD_INVALID
  require ev.id_prefix == raw prefix(entry_id); require all projects/declared ∈ SU; require arrays canonical
  SD := set(source_data_projects); DS := set(declared_sources)
  if SD≠∅ and DS≠∅ and SD≠DS: return AMBIGUOUS
  explicit := SD if SD≠∅ else (DS if DS≠∅ else {P})
  if P ∉ explicit: return AMBIGUOUS
  return RESOLVED(explicit)
```
Verified: all **3,086** current entries return RESOLVED (0 AMBIGUOUS, 0 INVALID) — the v4
defect (0 resolved) is eliminated. `declared_sources={GTFOBins,WADComs}` with prefix
GTFOBins is **not** ambiguous (prefix is membership, satisfied).

**8.4 Multiple emitters for one id:** collect all emitted copies across results; normalize
each `owner_evidence`; if all byte-identical ⇒ resolve that one; if they differ ⇒
`AMBIGUOUS`. Per-emitter `material_fingerprint`/`upstream_identity` stay source-local and may
differ. If RESOLVED, **every emitter source MUST be in the resolved set**, else the whole
observation is hard-invalid; if AMBIGUOUS, emitter membership is not evaluated.

**8.5 One AMBIGUOUS policy (never hard-invalidates; always the conservative transition):**
existing persisted id becomes ambiguous ⇒ `owner_ambiguous:=true, classification:=NOT_OBSERVED,
initialized:=true, absence_streak:=0, owner_sources:=UNCHANGED, sources:=UNCHANGED`. **New**
ambiguous id ⇒ `owner_ambiguous:=true, NOT_OBSERVED, initialized:=true, streak:=0,
owner_sources:=[], sources:=[], aggregate_class:=HOLD, changed:=false`; the entry **is
persisted** and appears in the report. Later resolution: `owner_ambiguous:=false`,
`owner_sources:=resolved set`, delete lost-owner evidence, create null evidence for gained
owners, evaluate health+continuity, run the normal transition from `NOT_OBSERVED/0`.

## 9. Continuity — identity mode, present/absent separated, complete truth table

**9.1 IDENTITY_MODE (static):** `GTFOBins:STABLE("gtfobins_natural_key"),
LOLDrivers:STABLE("loldrivers_id"), LOLAD:NONE, LOLBAS:NONE, WADComs:NONE`. For NONE,
emitted `upstream_identity` MUST be null; for STABLE(kind), every emitted entry MUST carry
a non-null identity of exactly that kind and with a non-empty value (§6.0.1). In particular,
`STABLE + status:ok + emitted + upstream_identity:null` is a HARD INVALID observation:
validation stops before admission, no transition occurs, and no report is produced.
`present(O,E) := O.status==ok AND E ∈ O.emitted_entries`; a non-ok result retains every
parsed sibling emission required by §7.2d but supplies only HEALTH_HOLD and no evidence mutation.

**9.2 Present-entry partition (disjoint, exhaustive):**
| # | prior id | observed id | mode | class | contribution | last_reliable | stored identity |
|---|---|---|---|---|---|---|---|
| 1 | null | non-null | STABLE, correct kind | FIRST_SIGHTING | PRESENT | set to current id | set to observed |
| 2 | non-null | same | STABLE same kind/value | PROVEN | PRESENT | set to current id | unchanged |
| 3 | non-null | different | STABLE | CONFLICT | entry-level blocking HOLD | unchanged | unchanged |
| 5 | null | null | NONE | PRESENT_UNKEYED | PRESENT | set to current id | remains null |

Those four rows exhaust the admitted domain because §6.0.1 rejects STABLE/null observed
identity, and §11.5 rejects a persisted NONE/non-null identity. Any tuple outside the table
is therefore invalid schema/state, not an executable continuity alternative. In particular,
the former STABLE/null PRESENT→UNPROVABLE rows are removed. The `last_reliable` and stored
identity columns describe **planned** PRESENT-owner updates; no evidence is written until
the aggregate-class gate in §9.4. For planned PRESENT, the planned fingerprint is the
observed fingerprint. CONFLICT plans no update.

`UNPROVABLE` remains a reserved blocking owner-outcome label, but no observation/state pair
admitted by v6-4 produces it. If it is encountered internally, it is handled identically to
CONFLICT by §9.4 (aggregate HOLD and total evidence freeze) and MUST NOT be used to admit a
STABLE/null observation or unreachable state.

**9.3 Absent-entry partition (not the present table with a synthetic null):**
| owner result | mode | prior id | outcome | evidence |
|---|---|---|---|---|
| not-ok (failed/partial/unknown) | any | any | HEALTH_HOLD | none |
| ok & absent | STABLE | non-null | QUALIFYING_ABSENCE | none |
| ok & absent | STABLE | null | CONTINUITY_HOLD | none |
| ok & absent | NONE | null | CONTINUITY_HOLD | none |
LOLBAS/LOLAD/WADComs absence **always** HOLDs; a stable owner counts absence only after a
stable identity was previously recorded.

**9.4 Owner outcome ∈ {PRESENT, QUALIFYING_ABSENCE, HEALTH_HOLD, CONTINUITY_HOLD,
CONFLICT, UNPROVABLE}. Aggregate and evidence mutation (one ordered algorithm):**
```
if ownership AMBIGUOUS:                              ambiguity transition; aggregate_class=HOLD
elif any owner CONFLICT or UNPROVABLE:               HOLD
elif any owner CONTINUITY_HOLD:                      HOLD
elif any owner PRESENT:                              PRESENT
elif owner set non-empty and all QUALIFYING_ABSENCE: QUALIFYING_ABSENCE
else:                                               HOLD
```
The aggregate is computed completely **before** mutating any evidence tuple. Then exactly:

- `aggregate_class != PRESENT`: for every persisted carried owner, freeze all three evidence
  fields byte-for-byte (`material_fingerprint`, `upstream_identity`, and
  `last_reliable_observation_id`). No planned PRESENT update is applied. A gained owner from
  deterministic ownership reconciliation (§8.5/§10) remains the all-null genesis tuple and a
  lost owner is removed; these membership operations are not evidence-value mutation.
- `aggregate_class == PRESENT`: apply the §9.2 planned update to **every** PRESENT owner;
  freeze every non-PRESENT owner's three fields. There is no selected owner that drives
  PRESENT.

Thus CONFLICT/UNPROVABLE + PRESENT, PRESENT + CONTINUITY_HOLD, every unhealthy aggregate-HOLD
path, ambiguity, and QUALIFYING_ABSENCE all freeze carried evidence. PRESENT + failed/NOT_RUN
owner remains aggregate PRESENT when no blocking outcome exists, so only its PRESENT owners
update. In the Round-6 replay (GTFOBins P1→P2 PRESENT plus LOLDrivers CONTINUITY_HOLD), the
aggregate is HOLD, GTFOBins remains P1 with its prior identity/reliable ID, and `changed=false`.

## 10. Freshness transition (entry-level; total) + per-source evidence membership

**Generic applied-transition head assignments (normative).** When admission (§5.4) reaches
the `APPLIED` path, the committed successor state's head fields are assigned **once,
generically**, for every applied transition regardless of per-entry outcome:
`last_observation_id := observation.observation_id` and `last_observation_hash := obs_hash`
(the canonical `sha256` of the whole observation, §5.4). These are the same assignments
constrained by G3 and required by exact-retry semantics (§5.5/§5.7); stating them here does
not change any golden bytes (G3 already carries `last_observation_id=1` and
`last_observation_hash=`G2 hash). Per-entry freshness follows the table below; the head
assignment is independent of it.

Applied once per entry, from the §9.4 `aggregate_class`, `s`=streak, threshold **3**:

| state | init | class | →state | init' | streak' |
|---|---|---|---|---|---|
| (new id) | — | PRESENT | ACTIVE | true | 0 |
| (new id) | — | QUALIFYING_ABSENCE | ignored (unknown id can't be absent) | — | — |
| (new id) | — | HOLD | no record created (except AMBIGUOUS new id ⇒ §8.5 case A) | — | — |
| any | false | PRESENT | ACTIVE | true | 0 |
| any | false | QUALIFYING_ABSENCE | NOT_OBSERVED | true | 1 |
| any | false | HOLD | unchanged | false | unch |
| ACTIVE | true | PRESENT | ACTIVE | true | 0 |
| ACTIVE | true | QUALIFYING_ABSENCE | NOT_OBSERVED | true | 1 |
| ACTIVE | true | HOLD | ACTIVE | true | unch |
| NOT_OBSERVED | true | PRESENT | ACTIVE | true | 0 |
| NOT_OBSERVED | true | QUALIFYING_ABSENCE | (s+1>=3?STALE_CANDIDATE:NOT_OBSERVED) | true | s+1 |
| NOT_OBSERVED | true | HOLD | NOT_OBSERVED | true | unch |
| STALE_CANDIDATE | true | PRESENT | ACTIVE | true | 0 |
| STALE_CANDIDATE | true | QUALIFYING_ABSENCE | STALE_CANDIDATE | true | s+1 |
| STALE_CANDIDATE | true | HOLD | STALE_CANDIDATE | true | unch |

In this table, `unchanged`/`unch` refers to the freshness triple
`(classification,initialized,absence_streak)`. It does not cancel deterministic ownership
membership reconciliation described below; that reconciliation can add EMPTY gained-owner
tuples or remove lost owners while aggregate HOLD freezes every carried evidence value.

**Per-source evidence membership:** invariant `set(sources[].source) == set(owner_sources)`;
when §8 ownership resolution changes a resolved owner set, reconcile membership first:
owner gained ⇒ create nested `{material_fingerprint:null,last_reliable_observation_id:null,
upstream_identity:null}`; owner lost ⇒ delete; carried owner ⇒ retain its tuple. Then apply
the aggregate-subordinate mutation gate in §9.4. Consequently `aggregate_class!=PRESENT`
never changes any carried owner's fingerprint, identity, or reliable observation ID;
`aggregate_class==PRESENT` updates every PRESENT owner and no other owner.

## 11. State validator — static partition (byte-derivable, no history inference)

**Transition invariants** (what the transition may assert, e.g. "this ambiguous id is
first-seen") are distinct from **static validation invariants** (what `state.json` bytes
alone must satisfy). The static validator never infers unencoded history.

**11.1 Envelope:** exactly `{body,checksum}`; file bytes == `canonical(envelope)+"\n"`;
`checksum == sha256(canonical(body))`; NFC-unique keys; all required fields present, no
undeclared fields; entries/sources/owner arrays already canonical.
**11.2 Body:** `core_state_version==2`; `last_observation_id` integer ≥0;
`last_observation_hash` matches sha256 grammar; `entry_id` unique. Virtual genesis:
`last_observation_id==0`, `last_observation_hash==GENESIS_LAST_OBSERVATION_HASH` (§12).
**11.3 Exact entry-state partition (an entry is valid iff exactly one row matches):**
| case | owner_ambiguous | initialized | classification | absence_streak |
|---|---|---|---|---|
| A ambiguous | true | true | NOT_OBSERVED | 0 |
| B genesis survivor | false | false | NOT_OBSERVED | 0 |
| C active | false | true | ACTIVE | 0 |
| D observed <threshold | false | true | NOT_OBSERVED | 0..2 |
| E stale candidate | false | true | STALE_CANDIDATE | ≥3 |

No other combination is valid ⇒ `owner_ambiguous==true ⇒ initialized==true`; the
`owner_ambiguous:true, initialized:false` object is **rejected**. There is no persisted
"new" state: a resolved-HOLD new id creates no entry; an ambiguous new id uses case A.
**11.4 Ownership/source:** `owner_sources` sorted, dup-free, ⊆ SU; `sources` sorted by
source, dup-free, each ∈ SU; `set(sources[].source)==set(owner_sources)`. An
`owner_sources` value outside SU ⇒ invalid (no mandatory AdapterResult could exist for it).
**11.5 Persisted source-evidence truth table (complete; Major 2).** Let `I` be
`upstream_identity`, `F` be `material_fingerprint`, and `L` be
`last_reliable_observation_id`. Let `D` be a valid material digest and let `n` be an integer
with `1 <= n <= body.last_observation_id`. A source-evidence record is legal **iff** exactly
one row for its static identity mode matches:

| mode | `I` | `F` | `L` | tuple name / reachable origin |
|---|---|---|---|---|
| STABLE(kind) | `null` | `null` | `null` | `EMPTY`; genesis or gained owner not yet reliably PRESENT |
| STABLE(kind) | `{kind:<exact kind>,value:<non-empty string>}` | `D` | `n` | `STABLE_RELIABLE`; one atomic PRESENT update, then possible freezes |
| NONE | `null` | `null` | `null` | `EMPTY`; genesis or gained owner not yet reliably PRESENT |
| NONE | `null` | `D` | `n` | `UNKEYED_RELIABLE`; one atomic PRESENT update, then possible freezes |

For an exhaustive null/non-null cross-product, `0` means null and `1` means a valid
non-null value of the required type/shape (including in-range `L`):

| `(I,F,L)` bits | STABLE | NONE |
|---|---|---|
| `000` | ALLOW (`EMPTY`) | ALLOW (`EMPTY`) |
| `001` | REJECT | REJECT |
| `010` | REJECT | REJECT |
| `011` | REJECT | ALLOW (`UNKEYED_RELIABLE`) |
| `100` | REJECT | REJECT |
| `101` | REJECT | REJECT |
| `110` | REJECT | REJECT |
| `111` | ALLOW (`STABLE_RELIABLE`) | REJECT |

Every other tuple is invalid and the state is rejected even when its checksum matches. In
particular, all of these are invalid: STABLE non-null identity with null fingerprint or null
reliable ID; any non-null fingerprint with null reliable ID; a STABLE non-null fingerprint
with null identity; any non-null identity for NONE; and every partially initialized mixture.
`L=0` is invalid because genesis creates only `EMPTY` and the first applied observation is 1.
The three evidence fields are therefore initialized atomically by PRESENT and frozen
atomically (as values) by every non-PRESENT aggregate (§9.4).

**11.6 Entry-level reachability invariants (complete from present bytes).** In addition to
the exact §11.3 state row, §11.4 membership, and one legal §11.5 tuple per source, require:

- a non-ambiguous entry has a non-empty owner set; an ambiguous entry may have empty or
  non-empty owner/source arrays, but those arrays must still be mutually equal and every
  retained tuple must satisfy §11.5;
- `initialized:false` implies every source tuple is `EMPTY`;
- **(R7 static hardening, category A — byte-derivable, cannot reject a reachable state):**
  (i) `initialized:true` implies `last_observation_id >= 1` — an initialized entry required at
  least one applied transition, and every applied transition sets `last_observation_id :=
  observation_id >= 1` (§10, §5.4); genesis (§12) produces only `initialized:false` at
  `last_observation_id:0`, so `last_observation_id==0` with any `initialized:true` (incl.
  `ACTIVE`) is unreachable and rejected. (ii) `absence_streak <= last_observation_id` — the
  streak increments only on a QUALIFYING_ABSENCE transition, each of which advances
  `last_observation_id` by at least 1, so a streak exceeding `last_observation_id` is
  unreachable and rejected. (iii) for a **non-ambiguous** entry, `canonical_prefix_owner(entry_id)`
  (recomputed from the id bytes, §8.1) MUST be a member of `owner_sources` — every RESOLVED
  owner set contains the prefix owner (§8.3: `if P ∉ explicit: return AMBIGUOUS`), so a
  non-ambiguous `gtfobins/…` whose stored owner set omits GTFOBins is unreachable and
  rejected. This does not touch ambiguous entries (case A owner arrays may be empty and are
  not prefix-checked). All three are pure functions of the current state bytes and reject only
  states no genesis/transition/reconciliation/ambiguity path can produce.
- no additional classification-to-evidence-history inference is legal for an initialized
  entry. ACTIVE, NOT_OBSERVED (any permitted streak), and STALE_CANDIDATE may each contain
  any mixture of mode-legal §11.5 tuples after deterministic owner-set reconciliation:
  lost owners are deleted, gained owners start EMPTY, and an aggregate HOLD freezes those
  gained tuples without changing the stored classification/streak (§9.4/§10). A non-ok
  emitted result can drive exactly this reachable ownership change while contributing
  HEALTH_HOLD. Requiring ACTIVE to contain a reliable tuple, or stale/positive-streak states
  to contain only STABLE_RELIABLE tuples, would therefore infer obsolete history and reject a
  valid transition output.

**Ratified static-vs-historical distinction preserved:** the validator never infers
"first-seen ambiguous" or prior owner composition from current arrays. Case A with empty arrays is valid, and case A
with non-empty arrays of legal tuples is also valid; current bytes do not encode which
history produced it. An existing entry becoming ambiguous freezes its arrays (§8.5), while a
new ambiguous entry creates empty arrays; both transition outputs satisfy the same static
rules.

**Normative allowed/rejected examples.** With `last_observation_id>=5`, STABLE
`(null,null,null)` and `(correct non-null identity,D,5)` are allowed; NONE
`(null,null,null)` and `(null,D,5)` are allowed. STABLE `(identity,null,null)`,
`(identity,D,null)`, `(null,D,null)`, `(null,D,5)`, and `(identity,null,5)` are rejected.
NONE `(identity,D,5)`, `(null,D,null)`, and `(null,null,5)` are rejected. At body observation
0 only the two `EMPTY` rows are allowed. These examples are exhaustive instances of the
table, not additional rules.

## 12. Virtual genesis — inventory incorporated before token (complete, printed)

`GENESIS_LAST_OBSERVATION_HASH = "sha256:" + 64 zeroes`.

**Genesis inventory incorporation (normative, before token computation).** When
`state.json` is absent, the genesis body is **not** empty: the `genesis_inventory` is
materialized deterministically and **every** inventory entry is seeded into the body as
`classification:NOT_OBSERVED, initialized:false, absence_streak:0`, with `owner_sources`
from the §8 resolver and one nested source-evidence per owner
(`material_fingerprint:null, last_reliable_observation_id:null, upstream_identity:null`).
The body is canonicalized (§3, entries sorted by `entry_id`) and **its checksum is
computed over that fully-seeded body** — this is the `state_checksum` in the genesis
`state_token`. Both orchestrator and CORE derive the identical token from the identical
inventory. `last_observation_id:0`, `last_observation_hash:` sixty-four zeroes.

**Production `genesis_inventory` extraction (complete, mechanical — Major 3).** The
inventory is built by this exact algorithm, from the repository at HEAD:
1. **Roots examined:** the single tree `data/entries/` recursively.
2. **Accepted files:** every regular file matching glob `data/entries/**/*.yaml` (POSIX,
   case-sensitive extension `.yaml`). **Excluded:** any non-`.yaml` file, directories,
   symlinks; no other tree is read.
3. **Deterministic traversal:** collect all accepted paths and process them **sorted by
   repository-relative POSIX path, code-point order** (the traversal order does not affect
   output because entries are re-sorted in step 8, but it is pinned for reproducibility).
4. **Parse:** load each file with the fixed YAML safe schema (§6.2.7). A file that fails to
   parse, is not a mapping, or lacks a non-empty string `id` is **skipped from the inventory**
   (genesis is a seed of *known* entries, not a health pass; malformed seeds simply do not
   seed — they will be observed normally on the first cycle). No exception aborts the build.
5. **ID derivation:** `entry_id := d["id"]` verbatim (already the canonical
   `<prefix>/<path>` id used throughout the corpus). No transformation.
6. **Ownership:** `owner := canonical_prefix_owner(entry_id)` (§8.1). An id whose prefix is
   not in `PREFIX_OWNER` is skipped from the inventory (cannot be owned).
7. **Duplicate ID:** if two accepted files derive the same `entry_id`, the **first in the
   step-3 order is kept and the rest skipped** (deterministic; the corpus has none at
   `00a9fe2`, so this branch is not exercised by the golden but is defined).
8. **Ordering & shape:** each surviving entry becomes
   `{entry_id, classification:"NOT_OBSERVED", initialized:false, absence_streak:0,
   owner_sources:[owner], owner_ambiguous:false, sources:[{source:owner,
   material_fingerprint:null, last_reliable_observation_id:null, upstream_identity:null}]}`;
   the `entries` array is **sorted by `entry_id`** (code-point, §3).
9. **Token computation:** the genesis body is `{core_state_version:2, entries:[…],
   last_observation_hash:<64 zeroes>, last_observation_id:0}`; canonicalize (§3); the
   `state_checksum` is `sha256` of those canonical bytes; that is the genesis `state_token`.
   The inventory is thus incorporated **before** token computation.

**Real corpus.** Running the algorithm above on the real repository at build time. Verified
at `00a9fe2` with this exact algorithm: **3,086 seeded entries**, canonical genesis body
**899,886 bytes**, genesis checksum
`sha256:8d78d81b92d5fbaea2972fca158b4a15424301d5ed7e111c601bf0f060415ca9`. This is the
production genesis; it is corpus-dependent by construction and regenerates whenever the
corpus changes. (The newly-explicit algorithm reproduces the previously-pinned bytes exactly;
no golden changed.)

**Normative golden fixture (1 seeded entry).** Because the 3,086-entry body is too large
to print and pin, the golden vectors below use a **normative genesis fixture** whose
`genesis_inventory` contains exactly one entry — the same GTFOBins entry used by G1/G2/G3
— seeded by the identical algorithm. This is **not** an "empty inventory" assumption
(that would be non-normative); it is the same incorporation rule applied to a
one-entry inventory, so the fixture is byte-reproducible and demonstrates the seeding.
Fixture genesis body, canonical:
```
{"core_state_version":2,"entries":[{"absence_streak":0,"classification":"NOT_OBSERVED","entry_id":"gtfobins/diff/file-read/unprivileged","initialized":false,"owner_ambiguous":false,"owner_sources":["GTFOBins"],"sources":[{"last_reliable_observation_id":null,"material_fingerprint":null,"source":"GTFOBins","upstream_identity":null}]}],"last_observation_hash":"sha256:0000000000000000000000000000000000000000000000000000000000000000","last_observation_id":0}
```
len = 457 bytes; fixture genesis checksum = `sha256:a836d0b4779c6f1ca293acb0fcae9617d594e2753328ebb6d5a9c01214b70d40`.
Fixture genesis `state_token` (complete, non-abbreviated) =
```
{"core_state_version":2,"last_observation_hash":"sha256:0000000000000000000000000000000000000000000000000000000000000000","last_observation_id":0,"state_checksum":"sha256:a836d0b4779c6f1ca293acb0fcae9617d594e2753328ebb6d5a9c01214b70d40"}
```
Complete fixture genesis **envelope** (persisted file bytes incl. terminal newline, 552 bytes):
```
{"body":{"core_state_version":2,"entries":[{"absence_streak":0,"classification":"NOT_OBSERVED","entry_id":"gtfobins/diff/file-read/unprivileged","initialized":false,"owner_ambiguous":false,"owner_sources":["GTFOBins"],"sources":[{"last_reliable_observation_id":null,"material_fingerprint":null,"source":"GTFOBins","upstream_identity":null}]}],"last_observation_hash":"sha256:0000000000000000000000000000000000000000000000000000000000000000","last_observation_id":0},"checksum":"sha256:a836d0b4779c6f1ca293acb0fcae9617d594e2753328ebb6d5a9c01214b70d40"}
```
(the persisted file appends exactly one `\n` after the closing brace).

## 13. Crash-safe single-file write (exact commit point; no journal)

```
lock -> read+validate -> validate observation -> admission (§5) -> transition (§10) ->
canonical serialize -> write temp (state.json.tmp.<pid>.<obs_id>, same fs) -> fsync(temp) ->
rename(temp,state.json)  [COMMIT POINT] -> fsync(parent dir) -> unlock
```
Commit point = `rename` returns success. Before rename ⇒ old state authority; rename fails ⇒
old state authority, temp discarded, fail closed; **rename succeeds ⇒ new `state.json` is the
committed authority read at restart, even if the later `fsync(parent dir)` fails** (that fsync
is durability, not the visibility boundary). lock-acquire failure ⇒ no mutation. Stale
`state.json.tmp.*` ⇒ ignored/removed, never authority. Hung live holder ⇒ no progress, no
divergence (liveness out of scope). No journal.

## 14. Material fingerprint (self-contained)

`project_material_v1(entry)` = exact JSON object, **omit-empty** (a value in
`[],{},"",None` is omitted), built from the projected entry: scalars `type,platform,name,
privilege_required`; arrays `aliases,phases,capabilities,attack_techniques,preconditions,
references,tags` each sorted by §3 order; `commands` sorted by §3 command tuple, each item
keeping only non-empty keys among `template,placeholders,comment`; `placeholders:[]` is
always omitted and is never an exception to omit-empty; `opsec` sub-keys
`noise,triggers` if non-empty and `detection_refs` sorted; `technique_detail`/`driver_detail`
included only if present, keys sorted. Excluded (non-material): `id,last_synced,projected_at,
_meta.*,source_data.*,enrichment provenance`, and `sources`. digest = `sha256:<hex>` over §3
canonical bytes. `technique_detail` is schema-capable but emitted by no adapter (0 entries).

Omit-empty is applied after NFC normalization and array sort/de-duplication. Therefore the
two projected inputs `{"commands":[{"template":"X","placeholders":[]}]}` and
`{"commands":[{"template":"X"}]}` both serialize exactly as
`{"commands":[{"template":"X"}]}` (31 bytes) and both have material fingerprint
`sha256:6ca27dacaf3439158765ea9c63b78acf011947c321c69956b9617029aeadff0d`.

## 15. Report (membership + exact changed)

`report = {report_version:1, observation_id:int, entries:[{entry_id,classification,
aggregate_class,changed}]}`, canonical §3, sorted by entry_id. **Membership = prior persisted
ids ∪ ids emitted this step.** Every persisted entry is evaluated every step (each gets a
class incl. HOLD), so failed/NOT_RUN owner entries are included; there is no inclusion choice.
This object exists only for an APPLIED transition; every other admission result returns the
exact `report:null` outcome in §5.4.

**R5-B1 — report row `classification` is total (one normative value per case):** the row's
`classification` field is defined for **every** membership case, including the report-only
case that creates no persistent record:
- **persisted entry** (prior id, or new id that transitions to a persisted state): `classification`
  = the entry's `classification` **in the post-transition state** (ACTIVE / NOT_OBSERVED /
  STALE_CANDIDATE).
- **report-only new id** (a newly emitted id whose aggregate class is HOLD, so §10 creates
  **no** persistent record): `classification := "NOT_OBSERVED"` **normatively**. A valid
  in-domain example is a newly emitted resolved ID owned by `{GTFOBins,LOLDrivers}`:
  GTFOBins is ok+present with a valid non-null stable identity, while LOLDrivers is ok+absent
  and its newly created prior evidence is `EMPTY`; GTFOBins contributes PRESENT,
  LOLDrivers contributes CONTINUITY_HOLD, and the aggregate is HOLD. This is
  the single legal value; `null` is **not** permitted. Rationale: a report-only id has been
  seen but not established, which is exactly what NOT_OBSERVED denotes; fixing it to a constant
  removes the §10-vs-§15 gap. §10 and §15 are mutually consistent: §10 persists nothing for
  this case, and §15 emits `{classification:"NOT_OBSERVED", aggregate_class:"HOLD",
  changed:false}`.

**R5-B2 — `changed` is one total rule with explicit precedence (aggregate class checked
first), total over the whole PRESENT-owner set:**
```
changed(entry, step):
  if aggregate_class(entry) != PRESENT:          return false      # HOLD/QUALIFYING_ABSENCE/ambiguity ⇒ false, unconditionally
  # aggregate_class == PRESENT (entry transitions to ACTIVE this step):
  return EXISTS an ok+present owner P such that
         P.prior_stored_fingerprint != null AND
         P.new_fingerprint != P.prior_stored_fingerprint
  # i.e. changed = OR over every PRESENT owner of (prior non-null AND fingerprint differs)
```
`changed` is a **total function of the entire set of PRESENT owners** — it never selects a
single "owner that drove PRESENT" (that selection was the R5-B2-followup ambiguity). It is
`true` iff **at least one** PRESENT owner has a non-null prior stored fingerprint that
differs from its new fingerprint; otherwise `false`. **Precedence is explicit and total:**
`aggregate_class != PRESENT ⇒ changed=false` is checked **before** any fingerprint
comparison, keyed on the **current aggregate class**, not the stored classification.
Consequences (all verified): first sighting / newly gained owner (prior null) contribute a
`false` term and cannot by themselves make `changed` true; multi-owner PRESENT where one
owner changes (A: P1→P1, B: Q1→Q2) yields `changed=true` in **every** conforming
implementation because the rule ORs over all owners rather than picking one; multi-owner
where none changes yields `false`; the mixed-owner CONTINUITY_HOLD / CONFLICT cases have
`aggregate_class != PRESENT` so the guard fires and returns `false` regardless of any P1→P2
on a present owner (evidence is frozen anyway). The former "is ACTIVE this step" and "the
ok+present owner that drove PRESENT" wordings are both replaced to remove the ambiguity.

## 16. Golden vectors (printed in full; recomputed; verified apply(G2,genesis)==G3)

### 16.0 Independent v6-2 → v6-3 golden comparison

| artifact | v6-2 | independently recomputed v6-3 |
|---|---|---|
| production genesis body | 3,086 entries; 899,886 bytes; `sha256:8d78d81b92d5fbaea2972fca158b4a15424301d5ed7e111c601bf0f060415ca9` | **unchanged; reproduced** |
| fixture genesis body | 457 bytes; `sha256:a836d0b4779c6f1ca293acb0fcae9617d594e2753328ebb6d5a9c01214b70d40` | **unchanged; reproduced** |
| fixture envelope | 551 canonical bytes + newline = 552 persisted bytes | **unchanged; reproduced** |
| G1 | 552 bytes; `sha256:8e4efac566970088763bfd9f7447b7fdfecc55d61764cfd422f814582ddfccae` | **unchanged; reproduced** |
| G2 | 1,705 bytes; `sha256:8b687db6f7882e233e2df28f5c55af20300278c5fddb566140f907b9f4a56f42` | **unchanged; reproduced** |
| G3 body | 581 bytes; `sha256:286048e4d67b0049ae052c7dd5c3fe1c9a95e1c8f63a4625bf21f649f2dece09` | **unchanged; reproduced** |
| G3 envelope | 675 canonical bytes + newline = 676 persisted bytes | **unchanged; reproduced** |
| G4 | 53 bytes; `sha256:3bdb5a7c1cf3696c2cd87d587db94501eca7704645be8a8d76a8e98df7be2887` | **unchanged; reproduced** |
| G5 | 39 bytes; `sha256:f021b2e37f5fc90a9701ef630f9bb68a6c9e4586e5070594bd2251a09afbd19b` | **unchanged; reproduced** |
| G6 | 49 bytes; `sha256:09bf118eab6255fbb474263f0491e19ec4234e504dfb91aae3175adb73caacc3` | **unchanged; reproduced** |
| `apply(G2, fixture genesis)` | exactly G3 | **unchanged; mechanically verified** |

No old→new hash mapping is required because no value changed. The repaired branches are not
exercised by these goldens: they contain no STABLE/null emission, aggregate HOLD with a
planned PRESENT update, input diagnostic/ref, normalized-path or duplicate-ID collision,
empty placeholder array, zero-candidate/source failure, non-ok sibling emission, or partial
persisted evidence tuple. Production/fixture genesis uses only the still-allowed `EMPTY`
evidence tuple; G2 uses a valid non-null STABLE identity; G3 uses a complete
`STABLE_RELIABLE` tuple. G1 has no placeholder field, and G4–G6 exercise unchanged canonical
JSON/ordering branches. The standalone fixture token display was reordered canonically in
v6-3, but its field values and every hashed embedding were already identical.

**G1 — material projection** of `gtfobins/diff/file-read/unprivileged` (552 bytes; rerun, **unchanged**):
`sha256:8e4efac566970088763bfd9f7447b7fdfecc55d61764cfd422f814582ddfccae`.

**G2 — observation** (base_state=genesis token; GTFOBins ok+present; 4 NOT_RUN). Complete
canonical single-line bytes:
```
{"base_state":{"core_state_version":2,"last_observation_hash":"sha256:0000000000000000000000000000000000000000000000000000000000000000","last_observation_id":0,"state_checksum":"sha256:a836d0b4779c6f1ca293acb0fcae9617d594e2753328ebb6d5a9c01214b70d40"},"observation_id":1,"results":[{"acquired_ok":true,"duplicate_ids":[],"emitted_entries":{"gtfobins/diff/file-read/unprivileged":{"material_fingerprint":"sha256:8e4efac566970088763bfd9f7447b7fdfecc55d61764cfd422f814582ddfccae","owner_evidence":{"declared_sources":["GTFOBins"],"id_prefix":"gtfobins","source_data_projects":["GTFOBins"]},"upstream_identity":{"kind":"gtfobins_natural_key","value":"diff/file-read/unprivileged"}}},"inputs_total":1,"parsed_ok":1,"primary_reason":"NONE","rejected":[],"resolved_revision":"acd5246000000000000000000000000000000000","source":"GTFOBins","status":"ok","unmapped":[]},{"acquired_ok":false,"duplicate_ids":[],"emitted_entries":{},"inputs_total":0,"parsed_ok":0,"primary_reason":"NOT_RUN","rejected":[],"resolved_revision":null,"source":"LOLAD","status":"unknown","unmapped":[]},{"acquired_ok":false,"duplicate_ids":[],"emitted_entries":{},"inputs_total":0,"parsed_ok":0,"primary_reason":"NOT_RUN","rejected":[],"resolved_revision":null,"source":"LOLBAS","status":"unknown","unmapped":[]},{"acquired_ok":false,"duplicate_ids":[],"emitted_entries":{},"inputs_total":0,"parsed_ok":0,"primary_reason":"NOT_RUN","rejected":[],"resolved_revision":null,"source":"LOLDrivers","status":"unknown","unmapped":[]},{"acquired_ok":false,"duplicate_ids":[],"emitted_entries":{},"inputs_total":0,"parsed_ok":0,"primary_reason":"NOT_RUN","rejected":[],"resolved_revision":null,"source":"WADComs","status":"unknown","unmapped":[]}]}
```
G2 length = 1705 bytes; G2 hash = `sha256:8b687db6f7882e233e2df28f5c55af20300278c5fddb566140f907b9f4a56f42`.

**G3 — state body** = `apply(G2, virtual genesis)`. Complete canonical single-line bytes:
```
{"core_state_version":2,"entries":[{"absence_streak":0,"classification":"ACTIVE","entry_id":"gtfobins/diff/file-read/unprivileged","initialized":true,"owner_ambiguous":false,"owner_sources":["GTFOBins"],"sources":[{"last_reliable_observation_id":1,"material_fingerprint":"sha256:8e4efac566970088763bfd9f7447b7fdfecc55d61764cfd422f814582ddfccae","source":"GTFOBins","upstream_identity":{"kind":"gtfobins_natural_key","value":"diff/file-read/unprivileged"}}]}],"last_observation_hash":"sha256:8b687db6f7882e233e2df28f5c55af20300278c5fddb566140f907b9f4a56f42","last_observation_id":1}
```
G3 length = 581 bytes; G3 body checksum = `sha256:286048e4d67b0049ae052c7dd5c3fe1c9a95e1c8f63a4625bf21f649f2dece09`.
Full state envelope + terminal newline (len 676 bytes):
```
{"body":{"core_state_version":2,"entries":[{"absence_streak":0,"classification":"ACTIVE","entry_id":"gtfobins/diff/file-read/unprivileged","initialized":true,"owner_ambiguous":false,"owner_sources":["GTFOBins"],"sources":[{"last_reliable_observation_id":1,"material_fingerprint":"sha256:8e4efac566970088763bfd9f7447b7fdfecc55d61764cfd422f814582ddfccae","source":"GTFOBins","upstream_identity":{"kind":"gtfobins_natural_key","value":"diff/file-read/unprivileged"}}]}],"last_observation_hash":"sha256:8b687db6f7882e233e2df28f5c55af20300278c5fddb566140f907b9f4a56f42","last_observation_id":1},"checksum":"sha256:286048e4d67b0049ae052c7dd5c3fe1c9a95e1c8f63a4625bf21f649f2dece09"}
```
**Verified mechanically: applying G2 to the fixture genesis produces exactly the G3 body
above.** The seeded entry transitions from the genesis `NOT_OBSERVED/initialized:false/0`
(§12 fixture) to `ACTIVE/initialized:true/0` on GTFOBins FIRST_SIGHTING PRESENT;
last_observation_id=1, last_observation_hash=G2. G2 and G3 changed vs v4
because `base_state` was added and `source_data_project`→`source_data_projects`.

**G4 — Unicode order:** canonical array `["gtfobins/aaa","gtfobins/\uf000zzz","gtfobins/\U0001f600aaa"]` (emitted with non-ASCII literal, so the U+F000 and U+1F600 characters appear as UTF-8 bytes) by code point (aaa < U+F000 < U+1F600); a UTF-16 code-unit sort misorders U+1F600 and is non-conforming. **Canonical length = 53 bytes; digest = `sha256:3bdb5a7c1cf3696c2cd87d587db94501eca7704645be8a8d76a8e98df7be2887`.**
**G5 — escaping** (rerun, **unchanged**): `{"input_ref":"a\nb\tc\"d\\e\u001ffég"}` ⇒
`sha256:f021b2e37f5fc90a9701ef630f9bb68a6c9e4586e5070594bd2251a09afbd19b` (LF⇒\n, TAB⇒\t,
quote⇒\", backslash⇒\\, US⇒\u001f, é literal).
**G6 — command ordering** (rerun, **unchanged**): `[{"template":"X"},{"comment":"a","template":"X"}]`
⇒ `sha256:09bf118eab6255fbb474263f0491e19ec4234e504dfb91aae3175adb73caacc3` (missing-comment first).

## 16.1 Round-5 regression vectors (one conforming output each)

- **R5-B1 (report-only new resolved-HOLD id):** previously-unseen `gtfobins/new/file-read/unprivileged`,
  resolved owners `{GTFOBins,LOLDrivers}`; GTFOBins ok+present with
  `upstream_identity:{"kind":"gtfobins_natural_key","value":"new/file-read/unprivileged"}`;
  LOLDrivers ok+absent with newly initialized `EMPTY` evidence ⇒ PRESENT + CONTINUITY_HOLD ⇒
  aggregate HOLD ⇒ no persistent record. The **only** conforming report row:
  `{"aggregate_class":"HOLD","changed":false,"classification":"NOT_OBSERVED","entry_id":"gtfobins/new/file-read/unprivileged"}`.
  `classification:null` is non-conforming (§15 fixes it to NOT_OBSERVED).
- **R5-B2 (`changed` under aggregate HOLD, and multi-owner PRESENT):** (i) prior ACTIVE entry
  owned by {GTFOBins,LOLDrivers}; GTFOBins ok+present identity stable fp P1→P2; LOLDrivers
  ok+absent null prior identity ⇒ CONTINUITY_HOLD ⇒ aggregate HOLD ⇒ **all carried evidence
  remains byte-identical, including GTFOBins P1 and prior reliable ID**. Only conforming
  value: `changed=false` (aggregate-class guard fires first). (ii) **Multi-owner PRESENT
  discordant** — entry owned by A and B, both PRESENT, A: P1→P1, B: Q1→Q2, aggregate PRESENT.
  Because `changed` ORs over **all** PRESENT owners (no arbitrary "owner that drove PRESENT"),
  the only conforming value is `changed=true` (B's change is detected regardless of A). (iii)
  Multi-owner PRESENT where **no** owner changes ⇒ `changed=false`; where **>1** changes ⇒
  `changed=true`. First-sighting / newly-gained (prior null) never alone make it true.
- **R5-B3 (`duplicate_ids` permutation invariance):** detection orders `["gtfobins/z","gtfobins/a"]`
  and `["gtfobins/a","gtfobins/z"]` both normalize to `["gtfobins/a","gtfobins/z"]`
  (sorted+dedup). One observation-hash contribution regardless of detection order.
- **R5-B4 (command placeholder permutation):** `{"template":"X","placeholders":["A","B"]}` and
  `{"template":"X","placeholders":["B","A"]}` both canonicalize to
  `{"placeholders":["A","B"],"template":"X"}` (placeholders sorted+dedup **in the emitted
  object**), producing **one** material representation and therefore one fingerprint
  `sha256:9b85e1a0276222ae7e4eb1f135a3da2f786f5dbe7c7c4d15bd277d6f06ea4552` for that command.
- **R5-B5 (Option C — empty-code sibling survival):** a GTFOBins file with one valid context
  emitting entry E and one empty-code context. The **only** conforming result: E is **retained**
  in `emitted_entries`; one non-suppressing diagnostic
  `{"code":"EMPTY_CODE_CONTEXT","input_ref":"_gtfobins/<rel>#","suppressing":false}` in
  `unmapped`; file accounting `inputs_total+=1, parsed_ok+=1, rejected+=0`; `primary_reason`
  stays `NONE`, `status` stays `ok` if this is the only condition; no HOLD forced by it.
  **All-empty variant:** a file where *every* context is empty still counts `inputs_total+=1,
  parsed_ok+=1, rejected+=0`, emits zero entries, and carries **one diagnostic per empty
  context, not de-duplicated**, ordered by `(input_ref,code)` preserving multiplicity.

## 16.2 Round-6 closure-repair regression vectors (normative)

Each vector has one legal outcome; any different status, count, emission set, report row,
evidence tuple, reference, material fingerprint, or persistent byte sequence is
non-conforming.

1. **STABLE PRESENT/null identity is invalid.** From any valid base, an otherwise-ok
   GTFOBins result emits E with `upstream_identity:null`. §6.0.1 validation fails before
   admission: no observation commit, no transition, no report, and the base bytes remain
   unchanged. The former UNPROVABLE/HOLD execution is forbidden.
2. **Valid new resolved HOLD / R5-B1.** New E resolves to
   `{GTFOBins,LOLDrivers}`. GTFOBins ok+present supplies a valid non-null natural key and
   fingerprint; LOLDrivers ok+absent starts `EMPTY`. Outcomes are PRESENT and
   CONTINUITY_HOLD, aggregate HOLD. E is not persisted and appears exactly once as
   `{entry_id:E,classification:"NOT_OBSERVED",aggregate_class:"HOLD",changed:false}`.
3. **PRESENT + CONTINUITY_HOLD freezes all evidence.** Prior ACTIVE E has GTFOBins tuple
   `(I_g,P1,L1)` and LOLDrivers `EMPTY`. GTFOBins ok+present supplies `(I_g,P2,current)`;
   LOLDrivers ok+absent contributes CONTINUITY_HOLD. Aggregate HOLD discards the planned
   GTFOBins update: post-state tuples remain `(I_g,P1,L1)` and `EMPTY`, classification remains
   ACTIVE/0, and report `changed:false`. Apart from the mandatory global last-observation
   ID/hash fields, the entry bytes are identical to the base; consequently canonicalizing
   that single specified body yields exactly one checksum.
4. **GTFOBins general reference.** `canonical_input_ref(GTFOBins,"foo/bar.md",FILE)` is
   exactly `_gtfobins/foo/bar.md#`. Option-C diagnostics use that output; `foo/bar.md#`
   (stripped prefix) is non-conforming.
5. **Injective `%`/`#` escaping.** With LOLBAS, raw `a#b.yml` yields
   `yml/a%23b.yml#`; raw `a%23b.yml` yields `yml/a%2523b.yml#`. The outputs differ and no
   percent-decoding is permitted.
6. **NFC-normalized path collision.** Two distinct GTFOBins candidates named composed
   `é.md` and decomposed `e`+U+0301+`.md` both normalize to `_gtfobins/é.md#`. Both reject:
   `inputs_total:2`, `parsed_ok:0`, `rejected` contains **two retained copies** of
   `{input_ref:"_gtfobins/é.md#",code:"NORMALIZED_PATH_COLLISION"}`,
   `duplicate_ids:[]`, `emitted_entries:{}`, `primary_reason:"NORMALIZED_PATH_COLLISION"`,
   `status:"failed"`. No diagnostic or candidate is silently collapsed.
7. **Empty-placeholder convergence.** The two material inputs
   `{"commands":[{"template":"X","placeholders":[]}]}` and
   `{"commands":[{"template":"X"}]}` both become the 31-byte canonical object
   `{"commands":[{"template":"X"}]}` and fingerprint
   `sha256:6ca27dacaf3439158765ea9c63b78acf011947c321c69956b9617029aeadff0d`.
8. **EMPTY_INPUT_SET zero-candidate accounting.** For acquired source S and 40-hex R, the
   exact semantic fields are `acquired_ok:true,resolved_revision:R,inputs_total:0,
   parsed_ok:0,rejected:[],unmapped:[],duplicate_ids:[],emitted_entries:{},
   primary_reason:"EMPTY_INPUT_SET",status:"failed"`. No rejection row is legal.
9. **ACQUISITION_FAILED zero-candidate accounting.** The exact semantic fields are
   `acquired_ok:false,resolved_revision:null,inputs_total:0,parsed_ok:0,rejected:[],
   unmapped:[],duplicate_ids:[],emitted_entries:{},primary_reason:"ACQUISITION_FAILED",
   status:"failed"`. No rejection, diagnostic, duplicate ID, or emission is legal.
10. **Two-candidate duplicate-ID collision.** Distinct LOLBAS candidates with refs
    `yml/A/a.yml#` and `yml/B/b.yml#` both derive `lolbas/e`. Both reject as DUPLICATE_ID:
    `inputs_total:2`, `parsed_ok:0`, the two independently retained rejection rows in ref
    order, `duplicate_ids:["lolbas/e"]`, `emitted_entries:{}`,
    `primary_reason:"DUPLICATE_ID"`, `status:"failed"`. Keeping either candidate is forbidden.
11. **Three-candidate duplicate-ID collision.** Add `yml/C/c.yml#`, also deriving
    `lolbas/e`. The unique outcome is `inputs_total:3`, `parsed_ok:0`, three independently
    retained DUPLICATE_ID rejection rows in ref order, the same one-element
    `duplicate_ids:["lolbas/e"]`, and zero group emissions. No first/last/median winner exists.
12. **Persisted evidence tuples.** For STABLE the allowed set is exactly `EMPTY` and
    `STABLE_RELIABLE`; for NONE it is exactly `EMPTY` and `UNKEYED_RELIABLE`, with `L` in
    `1..body.last_observation_id`. Every rejected partial combination listed in §11.5 is
    rejected. At observation 0 only EMPTY is allowed. The entry-level combinations in §11.6
    are applied after this tuple check; ambiguity never licenses an illegal tuple.
13. **Failed-source emissions.** An acquired two-candidate source has candidate A parsed and
    emitting E and candidate B rejected `PARSE_ERROR`. The unique result has
    `inputs_total:2`, `parsed_ok:1`, B's one rejection, E retained in `emitted_entries`,
    `primary_reason:"PARSE_ERROR"`, `status:"failed"`; E supplies HEALTH_HOLD and report
    membership, not PRESENT. Replacing emissions with `{}` is forbidden. By contrast, the
    source-level ACQUISITION_FAILED and EMPTY_INPUT_SET vectors 8–9 require `{}`. If A were a
    member of a duplicate/path collision group it would not be parsed and would not emit;
    a separate parsed non-colliding sibling still survives.

## 17. Internal checks executed (before handoff)

All run against `00a9fe2` / recomputed golden:
- **snapshot-bound 10/11, both interleavings** ⇒ identical committed `NOT_OBSERVED/2, L=10`; 11 permanently `INVALID_SUCCESSOR`. PASS.
- **identical same-successor delivery** ⇒ same bytes ⇒ same hash ⇒ exactly-one commit + no-op. PASS.
- **report outcome by admission result** ⇒ APPLIED returns §15; exact retry/no-op and every
  rejected/hard-invalid outcome return `report:null`; no cached-report branch. PASS.
- **distinct-hash same-base** ⇒ non-conforming input (orchestrator contract §2), not first-lock-wins. PASS.
- **ownership cross-product** incl. multi-owner/multi-emitter ⇒ resolver total; **3,086/3,086 RESOLVED** on real data, 0 AMBIGUOUS/INVALID. PASS.
- **identity schema × continuity** ⇒ STABLE/null emission rejected before transition; admitted STABLE PRESENT has a non-null identity; NONE/null PRESENT_UNKEYED remains executable. PASS.
- **GTFO empty-code (Option C)** ⇒ one non-suppressing `EMPTY_CODE_CONTEXT` diagnostic, file parsed_ok, valid siblings survive, no HOLD forced. PASS.
- **GTFO all-empty-contexts** ⇒ `inputs_total+=1, parsed_ok+=1, rejected+=0`, N non-deduped diagnostics. PASS.
- **WADComs malformed services** ⇒ MALFORMED_RECORD ⇒ partial/HOLD (unchanged). PASS.
- **health precedence and disposition** ⇒ source-level reasons have exact zero-candidate shapes; every actual candidate is parsed or has one terminal code; status rank is deterministic. PASS.
- **state validator tuple cross-product** ⇒ only the four §11.5 rows survive; all partial STABLE/NONE evidence tuples and `L=0` reject; entry-level reachability and ambiguity-history distinction both hold. PASS.
- **new resolved-HOLD id** ⇒ valid two-owner PRESENT+CONTINUITY_HOLD input; report-only `classification:NOT_OBSERVED`; no persistent record. PASS.
- **aggregate-HOLD evidence** ⇒ P1→P2 plan discarded under CONTINUITY_HOLD; identity/fingerprint/reliable ID freeze; `changed=false`. CONFLICT, reserved UNPROVABLE, health HOLD, ambiguity, and qualifying absence use the same gate. PASS.
- **`changed` multi-owner PRESENT** ⇒ total OR over all PRESENT owners: none-change⇒false, one-change (A:P1→P1,B:Q1→Q2)⇒true, >1-change⇒true, first-sighting/newly-gained-null alone⇒false. No arbitrary owner selection. PASS.
- **candidate cardinality** ⇒ file-per-entry = one candidate per file (nested functions/contexts create none); LOLAD per-row; §7.4 subordinate to §6.2.2, no alternative reading. PASS.
- **canonical input refs** ⇒ five exact roots/prefixes; LOLAD `index.html` non-empty; absolute/`.`/`..`/empty handling unique; `%` then `#` escaping injective; Option C generated by the same function. PASS.
- **normalized path collision** ⇒ reject all, repeated rejection rows retained, count equation preserved. PASS.
- **duplicate-ID collisions** ⇒ two and three candidates all reject, no winner/emission, one deduplicated `duplicate_ids` element, rejected multiplicity retained. PASS.
- **failed-result emissions** ⇒ parsed non-colliding siblings retained for candidate-derived failed/partial; source-level failed shapes emit none. PASS.
- **duplicate_ids permutation** ⇒ NFC/code-point sorted+dedup, one hash; no leakage into rejected/unmapped multiplicity. PASS.
- **command placeholders** ⇒ non-empty arrays sorted/deduped; empty omitted; present-empty and omitted converge to fingerprint `6ca27dac…`. PASS.
- **production genesis extraction** ⇒ explicit algorithm reproduces 3,086 / 899,886 / `8d78d81b…`. PASS.
- **G1/G5/G6 rerun** ⇒ unchanged. **G4 pinned** (53 bytes, `3bdb5a7c…`). **G2/G3 recomputed**; **apply(G2, fixture genesis) == G3** mechanically verified. PASS.

### 17.1 Fresh self-adversarial closure pass

For every Round-6 counterexample, two hypothetical implementations were replayed from the
same valid S and valid O. The alternate branch is now either hard-invalid before transition
or contradicted by one ordered function. The required interaction attacks produced:

| attack | unique result preventing `X != Y` |
|---|---|
| identity schema × continuity | STABLE/null never enters §9; valid STABLE PRESENT has one non-null identity branch |
| identity schema × B1 reporting | B1 uses valid GTFOBins PRESENT plus LOLDrivers CONTINUITY_HOLD; one NOT_OBSERVED report-only row |
| aggregate HOLD × evidence mutation | aggregate gate runs first; every carried three-field tuple freezes unless aggregate PRESENT |
| input_ref × Option C | `_gtfobins/...#` is produced by the general prefix/root/locator function |
| input_ref × NFC | normalization occurs at one fixed stage before escaping; case remains exact |
| input_ref × escaping | ordered `%→%25`, then `#→%23`; `a#b != a%23b` |
| normalized collision × count equation | reject-all N, retain N rejection elements; `inputs_total=parsed_ok+N` |
| placeholders × fingerprint | sort/dedup then universal omit-empty; the two inputs hash to `6ca27dac…` |
| source failure × candidate accounting | source failures have exact zero-candidate shapes and no rejection |
| duplicate collision × rejected multiplicity | reject-all N and retain N rows; `duplicate_ids` alone deduplicates the ID |
| duplicate collision × emissions | every collision member emits zero; every parsed non-colliding sibling survives |
| failed status × sibling emissions | candidate-derived failure retains all parsed siblings; source-level failure emits `{}` |
| evidence validator × ambiguity freeze | every retained tuple must match §11.5; ambiguous current bytes never infer first-seen history |
| duplicate_ids dedup × diagnostic multiplicity | only duplicate_ids deduplicates; rejected/unmapped preserve multiplicity |

Additional attacks on path-invalid sentinel collisions, LOLAD's `index.html`, two/three-way
ID groups, source-level precedence, PRESENT plus failed owners, ownership membership changes,
and initialized/classification/evidence cross-products found one local validator interaction:
an ownership change under HOLD can add an EMPTY tuple while retaining ACTIVE/NOT_OBSERVED/
STALE classification. §11.6 was repaired to accept every mode-legal tuple mixture for an
initialized entry instead of inferring obsolete owner history. After that repair, no second
conforming output remained.
Ownership reconciliation is ordered before the aggregate evidence-value gate: lost/gained
membership is unique, carried tuple values still freeze under non-PRESENT. No additional
local contradiction was found after that ordering was made explicit.

## 18. Disposition (Round-6 accounting)

| Finding | Label | Mechanism |
|---|---|---|
| R4-B1 concurrent admission | **REMEDIATION INTEGRATED — PENDING CODEX VERIFICATION** | §2 orchestrator contract + §5 snapshot-bound admission |
| R4-B2 ownership ladder | **REMEDIATION INTEGRATED — PENDING** | §8 PREFIX_OWNER membership; 3086/3086 resolved |
| R4-B3 NOT_RUN revision | **REMEDIATION INTEGRATED — PENDING** | §4/§6.1 biconditional; NOT_RUN shape |
| R4-B4 continuity null/null | **REMEDIATION INTEGRATED — PENDING** | §9 IDENTITY_MODE; present/absent split |
| R4-B5 health omissions | **REMEDIATION INTEGRATED — PENDING** | §7 no-silent-skip; empty-code + services covered |
| R4-B6 validator contradiction | **REMEDIATION INTEGRATED — PENDING** | §11 5-row static partition |
| R4 majors 1–4 | **REMEDIATION INTEGRATED — PENDING** | §15 report; §2 self-containment; §7.2 precedence restated; §8 multi-owner |
| **R5-B1 report-only classification** | **FIX INTEGRATED — PENDING INDEPENDENT CLOSURE REVIEW** | §9.1/§15/§16.2 valid two-owner HOLD replaces invalid STABLE/null example |
| **R5-B2 `changed`** | **CLOSED — CODEX ROUND 6; PRESERVED** | §15 total OR across every PRESENT owner, aggregate guard first |
| **R5-B3 duplicate_ids ordering** | **CLOSED — CODEX ROUND 6; PRESERVED** | §3 NFC/code-point sort + dedup; separate from multiplicity arrays |
| **R5-B4 command placeholder tie** | **FIX INTEGRATED — PENDING INDEPENDENT CLOSURE REVIEW** | §3/§14 empty placeholders omitted; non-empty sorted/deduped |
| **R5-B5 Option C** | **OPTION C RATIFIED; INPUT_REF FIX INTEGRATED — PENDING INDEPENDENT CLOSURE REVIEW** | §6.2.1 general function generates ratified `_gtfobins/...#`; §7.4.1 semantics preserved |
| **R6-B1 STABLE null identity** | **FIX INTEGRATED — PENDING INDEPENDENT CLOSURE REVIEW** | §6.0.1/§9.1/§9.2/§15 one schema; null STABLE emission hard-invalid |
| **R6-B2 aggregate-HOLD evidence** | **FIX INTEGRATED — PENDING INDEPENDENT CLOSURE REVIEW** | §9.4 aggregate-first total tuple freeze; §10 subordinate membership/update |
| **R6-B3 canonical input_ref** | **FIX INTEGRATED — PENDING INDEPENDENT CLOSURE REVIEW** | §6.2.1 exact roots/prefixes/path/locator/escaping/collision function |
| **R6-B4 empty placeholders** | **FIX INTEGRATED — PENDING INDEPENDENT CLOSURE REVIEW** | §3/§14 universal omit-empty and fingerprint vector |
| **R6-B5 source failures/accounting** | **FIX INTEGRATED — PENDING INDEPENDENT CLOSURE REVIEW** | §7.2a source enum and two exact zero-candidate shapes |
| **R6-B6 duplicate disposition** | **FIX INTEGRATED — PENDING INDEPENDENT CLOSURE REVIEW** | §7.2c reject-all N; no winner; retained rejection multiplicity |
| **R7-B7 exact-retry admission precedence** | **FIX INTEGRATED — PENDING INDEPENDENT CLOSURE REVIEW** | §2/§5.4/§5.7 same-ID/hash branch precedes base check; exact retry ⇒ IDEMPOTENT_NO_OP |
| **Round-6 Major 1 rejection operations** | **FIX INTEGRATED — PENDING INDEPENDENT CLOSURE REVIEW** | §7.2a–d enums, precedence, terminal disposition, status matrix |
| **Round-6 Major 2 validator reachability** | **FIX INTEGRATED — PENDING INDEPENDENT CLOSURE REVIEW** | §11.5 four-row tuple table + §11.6 entry constraints |
| **Round-6 Major 3 production genesis** | **CLOSED — CODEX ROUND 6; PRESERVED** | §12 unchanged; golden reproduced |
| **Round-6 Major 4 input_ref** | **FIX INTEGRATED — PENDING INDEPENDENT CLOSURE REVIEW** | closed by R6-B3 mechanism |
| **Round-6 Major 5 failed emissions/schema** | **FIX INTEGRATED — PENDING INDEPENDENT CLOSURE REVIEW** | §6.0.1/§7.2d category-dependent exact emissions |
| **Candidate cardinality** | **CLOSED — CODEX ROUND 6; PRESERVED** | file-per-entry vs LOLAD row rule unchanged |
| R1 B3 (ambiguity) | **NOT CLOSED** | pending Codex re-test of §8.5/§11 |
| R1 M1 (identity) | **NOT CLOSED** | pending Codex re-test of §9; durable identity DEFERRED (Phase 9) |
| R2 NB1 (concurrency) | **NOT CLOSED** | pending Codex re-test of §5 |
| R2 NB5 (continuity) | **NOT CLOSED** | pending Codex re-test of §9 |
| R1 B2,B4,B6,B7,M2,M5; R2 NB2,NB6,maj1,2,3,5; R3-B2A,B2B,B3,maj3,4 | CLOSED — CODEX VERIFIED (prior rounds) | carried; not re-opened |
| publication/actions/journal/recovery/evolution | REMOVED BY SCOPE | not CORE |
| durable cross-source identity | DEFERRED | Phase 9 |

## 19. Prior closure mapping retained in v6-3

| Finding | § | Mechanism removing the counterexample |
|---|---|---|
| R4-B1 | §2,§5 | admission = f(frozen base token); 10/11 identical in both orders; distinct-hash same-base is non-conforming input |
| R4-B2 | §8 | PREFIX_OWNER map + prefix-as-membership; 3086/3086 resolved (was 0) |
| R4-B3 | §4,§6.1 | acquired_ok ⟺ 40-hex; NOT_RUN ⇒ resolved_revision:null |
| R4-B4 | §6.0.1,§9 | IDENTITY_MODE static; NONE/null gives PRESENT_UNKEYED; STABLE/null emission invalid; present/absent separate |
| R4-B5 | §7 | no-silent-skip fallback; empty-code + services mapped |
| R4-B6 | §11 | 5-row static partition ⇒ owner_ambiguous⇒initialized:true |
| R4 maj-1 | §15 | membership = prior ∪ emitted; nonpersisted HOLD report row |
| R4 maj-2 | whole doc | self-contained; behavior defined without normative cross-references to prior documents |
| R4 maj-3 | §7.2 | primary-reason precedence restated in the health section |
| R4 maj-4 | §8 | source_data_projects array; multi-owner usable |

## 19.1 Round-5 R5-B1…B5 + Major 1…5 → normative fix → regression vector

| Finding | § | Normative fix | Regression vector (one conforming output) |
|---|---|---|---|
| R5-B1 | §9,§15 | valid two-owner new HOLD id ⇒ `classification:"NOT_OBSERVED"` (null forbidden); STABLE/null example removed | §16.1 B1 / §16.2.2 — `{classification:NOT_OBSERVED, aggregate_class:HOLD, changed:false}` sole legal row |
| R5-B2 | §15 | `changed`: `aggregate_class!=PRESENT ⇒ false` checked first; keyed on current aggregate not stored class | §16.1 B2 — mixed-owner P1→P2 + CONTINUITY_HOLD ⇒ `changed=false` only |
| R5-B3 | §3 | `duplicate_ids` sorted-code-point-after-NFC + de-duplicated, in canonical bytes | §16.1 B3 — z,a and a,z both ⇒ `["gtfobins/a","gtfobins/z"]` |
| R5-B4 | §3,§14 | non-empty placeholders sorted+deduped; empty placeholders omitted; sort tuple ends with canonical_bytes tie-breaker | §16.1 B4 plus §16.2.7 — permutations ⇒ `9b85e1a0…`; empty/omitted ⇒ `6ca27dac…` |
| R5-B5 | §7.4.1 | Option C: empty-code ⇒ one non-suppressing EMPTY_CODE_CONTEXT; siblings survive; file parsed_ok; supersedes v5 rule | §16.1 B5 — E retained + diagnostic; all-empty ⇒ parsed_ok, N non-deduped diagnostics |

## 19.2 Round-5 Major 1…5 → normative fix

| Major | § | Fix |
|---|---|---|
| 1 rejection operations | §7.2a–d, §7.3 | separate source/candidate enums, one terminal disposition, reject-all collisions, primary rank, exact emission matrix |
| 2 validator reachability | §11.5, §11.6 | four legal evidence tuples total + entry-level reachability; static-vs-historical distinction preserved |
| 3 genesis extraction | §12 | exact roots/globs/traversal/id-derivation/dup/malformed/order/token; reproduces 3086/899886/`8d78d81b…` |
| 4 input_ref grammar | §6.2.1 | five exact roots/prefixes; one path/locator function; ordered `%` then `#` escaping; reject-all normalized collisions; B5 form generated normally |
| 5 exact schemas | §6.0, §6.0.1, §7.2d | exact AdapterResult and nested shapes; STABLE identity required; category-dependent failed/partial emissions pinned |

## 19.3 R5-B5 arbitration integration — v5 rules removed/replaced

| v5 rule | v6-3 disposition |
|---|---|
| §7.5 "empty code ⇒ within-file malformed unit ⇒ MALFORMED_RECORD diagnostic ⇒ source partial/HOLD" | **REMOVED** — replaced by §7.4.1 Option C (non-suppressing EMPTY_CODE_CONTEXT, parsed_ok, no HOLD) |
| §7.4.1 v5.1 "atomic candidate policy: rejected file discards siblings" (empty-code path) | **REPLACED** — empty-code is no longer a rejection; siblings always survive; discard applies only to genuine candidate rejections/collision members |
| EMPTY_CODE_CONTEXT enum | **ADDED** to UNMAPPED_ENUM (`:false`); NOT a CANDIDATE_REJECT_ENUM member |
| empty-code accounting | **PINNED** `inputs_total+=1, parsed_ok+=1, rejected+=0`, even all-empty |
| diagnostic multiplicity | **PINNED** not de-duplicated, ordered `(input_ref,code)` preserving count |

---

## 19.4 Explicit v6-3 policy choices

The repair selected exactly these branches and removed their alternatives:

1. STABLE emissions always carry non-null correct-kind identity; null is hard-invalid.
2. Evidence-value mutation is subordinate to aggregate PRESENT; every other aggregate
   freezes every carried three-field tuple.
3. Canonical refs retain fixed source prefixes; LOLAD roots at the checkout and names
   `index.html`; path-invalid candidates use one reserved sentinel; normalized-ref groups
   reject all; `%` is escaped before `#`.
4. Every empty optional material value, including `placeholders:[]`, is omitted.
5. ACQUISITION_FAILED and EMPTY_INPUT_SET are source-level zero-candidate reasons; all other
   rejects are candidate-level.
6. Every normalized-ref and same-ID collision group rejects all members; no candidate wins;
   rejection multiplicity is retained while `duplicate_ids` alone deduplicates IDs.
7. Collision membership precedes candidate-local defect selection; otherwise the exact
   §7.2c defect order gives every candidate one terminal disposition. An independently
   rejected GTFOBins file does not retain provisional Option-C diagnostics/emissions, while
   empty code itself never rejects the file.
8. Candidate-derived failed/partial status retains parsed non-colliding siblings;
   source-level failed status has zero emissions.
9. Persisted source evidence has only four legal mode-specific tuples; partial tuples reject.
10. Ownership membership reconciliation occurs before the aggregate evidence-value gate;
    gained/lost membership is deterministic, carried values freeze under non-PRESENT, and
    the validator does not infer obsolete prior owners from classification.
11. Only APPLIED returns a report; retries and every rejection return exact `report:null`.

These are local specification selections. They require **no architectural redesign, no
queue/scheduler/arbitration mechanism, no journal/recovery subsystem, no publication
authority, no Phase-9 identity, and no other Phase-5 CORE scope expansion**.

---

**Standard:** two independent implementers reading **v6-4 alone** produce the same freshness
classification, the same persistent state bytes, the same observation hash, the same material
fingerprint, and the same report, from the same reliable observations — no
publication/journal/action/recovery/evolution guarantee. Golden G1–G6 (+ genesis, fixture,
R5 vectors) pin material projection, observation, state, Unicode order, escaping, command
ordering, and every Round-5 fix; `apply(G2, fixture genesis) == G3` is mechanically verified.

*Escalation note: no rule reintroduced journal, transactional DB, publication authority,
actions, recovery, evolution, or Phase-9 durable identity. §5 admission is a precondition on a
frozen integer token; §2 forbids arbitrating conflicting same-base hashes precisely to avoid a
scheduler/queue. Where the remediation did not fully determine a detail, §6.2 defines it
explicitly rather than inventing silent semantics.*

*Interpretive choices carried from v6-2:* (a) **§6.2.2 candidate unit** —
one candidate per file for file-per-entry adapters and per-row for LOLAD, with
within-file malformations as diagnostics not extra candidates. (b) **§6.2.4 canonical input
order** — defined as upstream document/list order (index 0 first) for truncation, distinct
from material sort order. (c) **§12 genesis inventory** — the genesis body incorporates the full inventory *before*
token computation (Gate-Contract-aligned): the real corpus seeds 3,086 entries (body
899,886 bytes, checksum `sha256:8d78d81b…`), and the printed golden uses a normative
one-entry fixture built by the identical seeding algorithm (not an empty-inventory
assumption). G2/G3 are computed on that fixture and change whenever the fixture or corpus
changes. v6-4's new selections are exhaustively listed in §19.4.

*End of Phase 5 CORE v6-4. No code implemented, no adapter/runtime modified, no sync, no commit,
no push.*
