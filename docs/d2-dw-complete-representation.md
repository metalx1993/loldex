# D2-DW — Complete LOLDrivers and WADComs publication representations

Status: implemented opt-in publication amendment under the user's authorization
to resolve the five upstream sources. This document is new authority, not a
claim that historical reviewers approved these semantics.

## Scope and frozen boundary

The default `normalize()` methods, WADComs `ATTACK_MAP`, frozen CORE v6-4,
CP5.1/CP5.2, `project_material_v1`, and default D1 `adapter_result()` remain
unchanged. In particular, the D1 retention limits still produce their exact
`SUBSET_TRUNCATED` diagnostics. D2 does not turn that suppression bit off or
pretend a truncated D1 result is healthy.

The explicit `normalize_complete()` publication profile instead represents all
the relevant records and their complete material. D1 diagnostics may be resolved
by the root D2 publication gate **only after** this full derivation succeeds and
the independent preflight accounts for every source file and expected emission.
Future malformed data and unrecognized classifications remain publication
blockers. This amendment does not itself mutate the corpus, migrate IDs, change
CORE state or authorize deletion, deployment or cron.

## Loss and evidence observed

The previously acquired verified snapshot reported 426 LOLDrivers truncation
diagnostics and 73 WADComs truncation diagnostics. These are observations of
that snapshot, not future expected counts. Driver descriptions can exceed 200
scalars, sample/command arrays can contain multiple records, and Resources can
exceed three URLs. WADComs descriptions can exceed 280 scalars and references can
exceed four URLs. Retaining only those prefixes is genuine information loss;
renaming or suppressing the diagnostic without representing the omitted data
would not resolve it.

## LOLDrivers complete derivation

- One file still produces one entry. ID is `loldrivers/` plus the required
  non-empty native `Id`, NFC canonicalized. No name fallback or uniqueness suffix
  is introduced. Duplicate IDs are rejected, never assigned a winner.
- `name` is the first Tags value when present; remaining Tags become aliases.
  An empty Tags list yields an empty projected name, not an Id/path substitute.
- Every Commands record is validated and retained. Every non-empty Command
  produces a command block with its entire Description as comment. No 200-scalar
  prefix or first-record selection remains. The complete source records also
  appear in `driver_detail.command_metadata`, including description/usecase
  records whose Command is empty.
- Capability and phase claims apply the existing keyword/default classifier to
  **each** command record. Individual claims remain `heuristic/low` with the
  contributing command index in their rationale. The projected value arrays are
  derived by the frozen projection function. The single privilege summary is
  explicitly `heuristic/low`: kernel/system in any complete command record yields
  system; otherwise admin. It is not represented as an upstream declaration.
- The existing MitreID string remains an `upstream/high` claim, independently of
  those heuristic claims. No new ATT&CK ID or inference is fabricated here.
- Every KnownVulnerableSamples record appears in `driver_detail.samples`, not
  only the first sample. All its fields are retained in the typed JSON form
  below. First-sample `sha256`, `signer` (Company), and `original_filename`
  compatibility fields remain when stated; they do not replace the full list.
- Every Resources value is retained. The source homepage fallback applies only
  when the array is absent/empty. No three-reference prefix remains.

## WADComs complete derivation

- One file still produces one entry, ID `wadcoms/` plus the source file stem,
  NFC canonicalized, without slugging.
- The entire resolved description is retained as command comment, including
  internal whitespace/newlines. All non-empty source references are retained.
  No 280-scalar or four-reference prefix remains.
- The existing explicit attack-type mapping is extended by this exact table:

| Source-native literal | Capability | Phase |
|---|---|---|
| `Discovery` | discovery | discovery |
| `Privilidge Escalation` | privilege-escalation | privilege-escalation |
| `Laterl movement` | lateral-movement | lateral-movement |
| `AS-REP Roasting` | credential-access | credential-access |
| `Kerberoasting` | kerberoast | credential-access |
| `Timeroasting` | credential-access | credential-access |

These are explicit adapter mappings of stated upstream labels, not fuzzy
matching. Source spelling remains unchanged in raw evidence and in the claim's
rationale. Resulting claims are `adapter/high`; no ATT&CK technique ID is inferred
from these labels. Multiple source labels may support separate claims for one
projected value; provenance is not flattened into entry-level confidence.

An absent/empty attack-type list retains the existing, explicitly explained
`heuristic/low` discovery default. A **stated but unknown** type never invokes
that default. All unknown occurrences are returned as `UNKNOWN_ATTACK_TYPE`
diagnostics, preserving their original values and multiplicity. The publication
gate must reject them even when other stated types have known mappings.

The strict frontmatter parser accepts only complete delimiter **lines**, with
optional leading blank lines (the verified `Rubeus-s4u.md` has this framing).
An inline `---` inside a YAML string is not a delimiter. Original file text,
including frontmatter and any Markdown body, is retained unchanged.

## Raw authority and canonical detail types

`source_data.<project>.raw` contains the original file name and full original YAML
document text. This preserves upstream scalar types, lexical values and fields
that JSON cannot natively encode. Before constructing an entry, the supplied
parsed document is checked against that original source text. No production
fallback fabricates raw text from a normalized record.

Material detail uses integer-only canonical JSON without modifying CORE:

- null, booleans, integers and strings remain their respective JSON types;
  strings and mapping keys use NFC; duplicate NFC keys fail;
- lists preserve source order and multiplicity, including duplicate samples;
- YAML floats, dates, timestamps and binary values use explicit `$yaml_type`
  wrappers with their deterministic value representation;
- a native mapping containing `$yaml_type` is itself wrapped as a mapping so it
  cannot masquerade as a tagged scalar; YAML sets use a canonical-value-sorted
  typed set wrapper; cyclic aliases fail closed.

The open structural `driver_detail` object already admits these fields. No base
schema, taxonomy, metadata-key contract or frozen material serializer changes.
The profile records complete material, so new fingerprints can legitimately
differ from D1's lossy fingerprints. Tests prove that changes after the old
description/reference/sample cutoffs now change the fingerprint. Old D1 goldens
are not rewritten to conceal that explicit profile difference.

## Publication accountability

Both adapters expose `publication_preflight(raw)` with exact input/parsed/error
accounting, complete diagnostics, `expected_emissions` (ID → material fingerprint)
and `expected_evidence` (ID → complete entry-evidence hash). The independent
preflight calls the pure `complete_entry()` functions directly, not the public
normalizer; dropping a file in a normalizer cannot reduce the expected output.

`entry_evidence_hash()` binds public structure, source data, source declarations,
claim provenance/confidence and source hashes while excluding only generated
date stamps (`last_synced` and `projected_at`). Dates for pure derivation are
explicit canonical ISO inputs. Publication must compare actual IDs/fingerprints
and evidence hashes with the preflight before declaring success. This catches
missing/extra entries and same-material changes to claim evidence.

`tests/test_complete_dw.py` covers complete retention, fingerprint sensitivity,
typed raw evidence, unknown-type handling, malformed late records, duplicate IDs,
normalizer-independent expected outputs, leading-blank frontmatter, and unchanged
D1 truncation behavior. Final live-source and integrated counts belong in the
root completion report, not normative invariants.
