# Phase 9 — durable, evidence-preserving tool identities

Phase 9 adds a separate versioned tool registry and derived `identities.json`; it does not change CORE/D1 identity modes, rewrite source entry IDs, merge techniques, or deduplicate evidence. `build_identities(entries, registry=None)` is pure: None yields an empty registry view. Production explicitly loads `data/identity/registry.json` through `load_identity_registry()`.

## Contract and confidence

Explicit stable entity IDs use `tool:`. Explicit claim IDs use `claim:` and survive entry disappearance. Each membership retains its own provenance, confidence and pinned raw-source witnesses. Entities distinguish possible runtime families from catalogue context (`active-directory` is a context, not an operating system).

`documents_tool` is adapter/high only when the pinned LOLBAS native YAML has an exact Name executable token and exact Full_Path matching the declared native identifier. Duplicate native keys are rejected; strings containing another executable/path as a substring are insufficient. `uses_tool` remains heuristic/low: a leading command token associates a documented operation with the tool; it proves neither PATH resolution, executable bytes/version, actual execution nor runtime OS. All initial curation is labelled curator=agent, never human/manual/verified.

The initial registry contains three meaningful cross-source groups: Microsoft Windows Certutil (LOLBAS plus LOLAD), Microsoft Windows Reg (LOLBAS, LOLAD and WADComs), and Impacket secretsdump (LOLAD and WADComs). Each declaration has explicit native/project identifiers and scope notes. Source links pin canonical upstream repositories and full review revisions; each witness hashes the exact original raw document/row string, without Unicode rewriting. Registry checksums are integrity pins, not authenticity signatures.

## Lifecycle and derived output

Membership states are active, missing, witness_changed or ambiguous. Review revision and current revision are separate: an upstream revision change alone does not deactivate unchanged document bytes. Missing entries and changed evidence retain their original claim and witnesses, but leave the active `entry_index`. Candidates are separate low-confidence leading-token suggestions and never active membership. Same display name, capability or ATT&CK technique does not establish identity. No transitive closure or confidence inheritance is computed.

`entities[].members` contains all curated states. `entry_index[entry_id]` contains only active `{entity_id,claim_id,relation}` references. `candidates`, `diagnostics`, explicit `aliases`, statistics and an overall deterministic checksum are separate. Output ordering is stable under input permutation; malformed registries, duplicate IDs, invalid confidence/provenance, conflicting documentation claims and invalid alias graphs fail closed. `validate_identities` independently rebuilds the expected view and compares canonical JSON bytes.

## Durable source-ID bookmarks

Aliases are explicit claims with adapter/high provenance, curator=agent, explanatory notes and historical evidence, not automatic name migrations. `old_entry_id` maps to all explicit `new_entry_ids`; output status is active for one target or split for several. There is no redirect, selected winner, chained alias resolution, or inherited tool membership. Current IDs take precedence in the resolver; an old entry endpoint remains missing, while the dedicated resolver explains the alias.

The initial concrete alias maps `lolbas/certutil/download/0` to D2's path-qualified `OSBinaries/Certutil.yml` Download index 0. Its historical YAML was read offline from repository commit `eaa8fa5e3eb19f28041e06362e43c2d08eee60bc`, path `data/entries/windows/lolbas__certutil__download__0.yaml`. The registry preserves original YAML, Git blob SHA1 and SHA256. Runtime verifies those bytes and parsed old ID, D1 and D2 source-identity formulae, source-file coverage, plus unchanged historical name/type/commands where present. Commit/path association is the explicit offline agent review basis, not a runtime Git Merkle inclusion proof or independent proof of historical public hosting.

The old Syncapp record names the VBS script and its command; mapping it to both EXE and VBS would invent ambiguity. No such split is seeded. Synthetic tests cover genuinely unspecified historical records with two explicitly curated compatible targets and preserve both. Alias chains, cycles, competing old-ID records, existing-current-ID conflicts and dangling targets are rejected before writing output.

## Verification

Focused tests cover input permutations, opaque source bytes, stale and missing witnesses, source revision changes, invalid provenance/confidence, contradictory typed native metadata, aliases and historical-byte tampering. An independent reviewer attacks these boundaries separately. Building the current 3336-entry snapshot from existing catalogue/evidence yields three entities, fifteen active curated memberships, seven non-active candidates and no inactive membership diagnostics; the checked registry adds one explicit historical alias.
