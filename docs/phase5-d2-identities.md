# D2 publication-v2 — LOLBAS qualification and LOLAD equivalent-row evidence

Status: explicit opt-in publication profile implemented under the user's source-remediation
authorization. This document supplements D1 for publication preparation only. It does not
edit the frozen CORE, D1 default AdapterResult, CP5.1/CP5.2, or identity modes.

## Why a separate publication decision is necessary

The verified upstream clones expose two different situations:

- LOLBAS commit `2056cb7662509dc998fc6ce79636aec4e6c0397f` contains distinct
  `OSBinaries/Syncappvpublishingserver.yml` and `OSScripts/Syncappvpublishingserver.yml`.
  Their source `Name` and commands distinguish `.exe` and `.vbs`. A stem/category/index
  identifier collapses them. Neither first nor last filesystem writer is legitimate.
- LOLAD commit `6ed6a258f6e5a4692cec07f9692ed097551e04e5` contains physical rows
  123 and 129 with identical complete four-cell content, including Reference. Their
  `Name, Command, Type` natural identity is identical; creating positional technique
  identities would fabricate a distinction and cause churn when rows move.

Default D1 continues to reject collision groups in both situations. D2 is selected
only with `raw['profile'] == 'publication-v2'` at the publication bridge. A D2 result
is not an observation accepted by the frozen CORE transition engine.

## LOLBAS: unconditional source-qualified identity

For every selected source document and upstream Commands array element:

```
entry_id = "lolbas/" + encode(source_relative_path) + "/" + encode(category.strip())
           + "/" + decimal(command_source_index)
encode(x) = BASE64URL_NO_PAD(UTF8(NFC(x)))
```

The path includes the exact selected folder and `.yml` filename, relative to `yml/`.
It is not an absolute host path. Qualification applies to **all** records, not only
when a collision happens. There is no hash, truncation, ordinal allocation by traversal,
first/last winner, or ID suffix repair. The command array index is source-native position,
not emitted count. Moving a document or reordering commands can change its ID; LOLBAS
remains identity mode NONE and this profile does not claim Phase 9 durable identity.

Full original UTF-8 source document bytes, their SHA-256, source-relative path and
command source index are retained in each entry's `source_data.LOLBAS.raw`. Raw
Name/Category/Privileges/MitreID values preserve original whitespace and absent
values remain null; display fallbacks and trimming never masquerade as upstream
values. Interpreted
capability/phase/privilege claims remain separately attributed in `enrichment`.

All IDs differ from D1 by an explicit rule. `publication_preflight` returns a complete
`identity_changes` list linking each D1 provisional ID to its source-qualified publication
ID and source locator. The previously colliding D1 ID maps to both distinct new IDs.
This report does not authorize silent migration, deletion, redirect, or identity merging.

Preflight validates every document and command before normalizing any entry. Malformed
name, detection or command shapes, unknown categories, unknown privilege text, normalized
source-path collisions, missing commands, and qualified ID collisions fail closed. A
D1 duplicate-ID rejection cannot hide another defect and make it publishable through D2.

## LOLAD: one logical entry, all equivalent source occurrences

Rows are parsed from exactly one complete table. Headers and explicitly empty-command
rows retain their existing NOT_A_RECORD meaning. All other rows require a name and at
least three cells. The equivalence key is the complete normalized cell array, including
Reference and any additional cells. Coalescence requires exact equality of that array;
comparison never ignores a differing reference or selects the richer record.

Each logical entry preserves the existing D1 natural ID:

```
"lolad/" + encode(Name) + "/" + encode(Command) + "/" + encode(Type)
```

Equal complete arrays produce one logical entry. Every physical source occurrence is
retained separately with original UTF-8 `<tr>...</tr>` bytes, their SHA-256, all source
cells and canonical physical `input_ref`. A representative locator is not an identity
and selects no behavioral winner. `source_data.LOLAD.raw.physical_rows` retains the full
list, and `physical_occurrence_count` explicitly records multiplicity. Reordering source
rows changes locators/evidence but does not change logical technique IDs.

Rows with the same natural triple but distinct remaining cells are **not** coalesced:
they remain a DUPLICATE_ID failure for the publication profile. No positional, emitted-
count, or hash suffix is introduced. Classification stays heuristic/low; repeated rows
are not independent confirmations and do not promote claim confidence.

Physical and logical cardinalities are kept in the publication audit separately from
any frozen D1 AdapterResult. At the verified snapshot: 137 physical candidates, 136
logical entries, one coalesced extra occurrence. Both original copies of the RDP row
remain available as evidence. D1 still rejects both and emits 135 siblings; D2 emits
one additional logical entry with two physical records, rather than hiding the duplicate.

## Checks

- Source-specific opt-in tests preserve legacy/default behavior and frozen D1 collisions.
- Real verified LOLBAS input: 245 selected documents, 485 unique publication entries.
- Real verified LOLAD input: 137 physical rows, 136 unique publication entries.
- Dedicated tests cover complete source evidence, conditional-winner avoidance, Unicode
  path collisions, row reorder, non-equivalent references, malformed shape hidden behind
  collisions, and unknown-category publication rejection.

These numbers describe inspected snapshots, not future acceptance invariants. Publication
still requires all five verified sources and the separate staging/release gate.

## Independent publication oracle

Preflight returns `expected_emissions` (ID to material fingerprint) without invoking
`Adapter.normalize`. It uses the pure reviewed source derivation rules, then applies
only the D2 identity and evidence decisions above. It also returns
`expected_entry_evidence_hashes`; `publication_entry_evidence_hash(entry)` binds the
entry ID, exact source evidence and every enrichment claim, excluding only fetch/build
clock metadata. This evidence hash preserves opaque upstream Unicode bytes rather than
NFC-normalizing them into apparent equality. The source bytes' own digests remain stored.

The publication bridge must compare the normalizer's output against both maps, then
bind the staged second normalization to the already-checked per-ID mappings. This
prevents a defective normalizer from defining its own expected output, silently skipping
a record, relabeling an entry, changing its material, promoting confidence, or forging
raw evidence while recalculating its local source hash.
