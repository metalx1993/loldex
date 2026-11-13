# D2-GTFO — explicit aliases and inherit support

Status: opt-in implementation under the user's delegated source-semantic repair
work. Profile **`publication-v2`**. D1/default observation, the CORE v6-4 artifact,
CP5.1/CP5.2 goldens and the default legacy adapter behavior remain unchanged.
This amendment must be reviewed with the other publication-v2 source changes;
it is not a retroactive claim that D1 already supported these source records.

## Evidence and problem

Verified GTFOBins commit `acd524623f9c406acedd2754ebd9c2431f3675ad` contains
478 physical candidate files. D1 rejects 20 alias-only documents for missing
`functions` and records 85 unknown-function occurrences for the newly supported
source function forms. Those diagnostics were correct under the old contract;
this amendment adds a different, explicit grammar rather than suppressing them.

Upstream authority at that commit:

- `CONTRIBUTING.md`, **Aliases**, specifies a document containing
  `alias: <gtfobin>` as an alias of another existing executable.
- `CONTRIBUTING.md`, **Functions**, defines `inherit` and its mandatory `from`
  field as the executable enabled by the activation example.
- `_layouts/gtfobin.html` resolves alias pages to their target; its inheritance
  presentation says downstream functions are **possibly** granted and links the
  target. It does not establish an unconditional union of downstream capabilities.
- `_data/functions.yml` and `linter/schema.py` explicitly define the source
  function `privilege-escalation`, absent from the previous LOLDEX mapping.

Only document bytes are consumed. Upstream Liquid, Python, shell or command
snippets are never executed or imported by LOLDEX.

## Decision 1 — aliases without invented identities

A document is an alias declaration only when its complete mapping contains the
single key `alias`, with a non-empty string value naming another file in the
**same verified acquisition bundle**. Lookups are exact and case-sensitive;
there is no filesystem/path lookup, external fetch, corpus lookup or slug.

Resolve alias chains to a canonical non-alias document with a non-empty functions
mapping. Missing targets, cycles, self-aliases, malformed target documents and
ambiguous alias-plus-functions records are candidate defects, never silent skips.
An iterative resolver handles long chains without recursive expansion.

Each valid alias file remains one physical candidate and is terminally parsed
with **zero emissions**. Its literal filename is added to the canonical target's
public `aliases` list, and the alias source-page URL is retained as a reference.
No alias entry ID is manufactured; existing target IDs, stable identity values
and commands are not renamed, substituted or rewritten. Removing an alias later
can change the target material fingerprint because aliases are material under
CORE §14; it does not delete a separate previously fabricated alias entry.

The source_data evidence for the target retains the original target and alias
source documents. The `source_data.GTFOBins.raw.documents` wrapper records exact
source filenames and parsed upstream mappings. Interpretive claims remain in
`enrichment`; the raw mappings do not acquire LOLDEX capability fields.

## Decision 2 — inherit activation, not transitive capability inference

A recognized `functions.inherit` example requires:

1. A non-empty string `from` naming an existing same-bundle executable or valid
   alias whose canonical target has a non-empty functions mapping.
2. The ordinary typed code/context structure. Specialized context code overrides
   common code exactly; a whitespace-only override is an empty-code context.
3. No target capability, command, context or privilege propagation.

For every actual activation snippet/context, keep the existing identity shape
`gtfobins/{binary}/inherit/{context}` and its corresponding GTFO natural key.
Record capability `command-execution` and phase `execution` as an explicit
**heuristic / low** interpretation of the activation snippet, with the note:

> Upstream inherit activation snippet; no downstream capability is inferred from its target.

This is not an upstream declaration of arbitrary command execution. No shell,
file-read, upload, or other downstream target capability is inferred or copied.
The original snippet is shown unchanged. `privilege_required` still comes from
the declared context mapping; the pre-existing elevated-context phase rule is
retained, with inherited phase claims remaining heuristic/low.

References include the target's source page. Raw evidence includes the activation
document and the referenced target/alias declarations used for validation.
Multiple activation examples in the same context group into one entry, retaining
their original commands. An inherit graph cycle is not recursively expanded:
these are literal activation references, not a transitive graph evaluator.

## Decision 3 — explicit privilege-escalation and caveats

The exact upstream function `privilege-escalation` maps deterministically to the
already-existing `privilege-escalation` capability/phase. This adds no taxonomy
value and does not reclassify arbitrary unknown functions.

Unknown functions/contexts retain their proper diagnostics. Empty-code contexts
retain non-suppressing EMPTY_CODE_CONTEXT diagnostics and valid siblings survive.
The publication gate still refuses any diagnostic. No warning is removed merely
to make the live corpus pass.

For publication-v2 command display, non-empty upstream context comments are
preserved alongside record comments, separated by two newline scalars. Raw
source evidence retains both values independently. This explicitly repairs lost
source caveats; the default D1 material projection is not silently changed.

## Integration contract

`phase5.adapters.gtfobins` exports:

- `prepare_documents(filename_to_parsed_mapping) -> GTFOResolution`
- `derive_document(resolution, filename, full_revision) -> GTFODerivation`
- `preflight(raw) -> {inputs_total, alias_refs, supported_function_refs, diagnostics, expected_emissions, expected_evidence}`

A derivation returns immutable tuple containers of emissions and diagnostic code
occurrences. Every emission has `id`, `material`, `enrichment`, `raw_documents`
and `upstream_identity`. Alias derivations return no emissions.

Preflight reports references only for valid aliases and explicit newly supported
function forms. It throws GTFOError with an exact candidate code for malformed
source input. A caller must require diagnostic-free preflight before exempting
any D1 finding; a reference containing both inherit and an actually unknown
function is not permission to drop that unknown-function diagnostic.

`expected_emissions` maps each normalized identity to its pure-derived material
fingerprint. `expected_evidence` independently binds the enrichment hash, the
Phase 1 raw source hash and upstream URL. These values come directly from parsed
verified documents and pure derivation, not from `normalize()` output. The
publication integrator must compare normalized public coverage/material and
evidence against these expectations before accepting the result. A public
normalizer cannot silently skip an entry, alter display fields, upgrade a low
confidence heuristic, fabricate rehashed raw evidence or change a citation URL
and then define its own fingerprint oracle.

`GTFOBinsAdapter.normalize(raw)` uses this derivation only when
`raw['profile'] == 'publication-v2'`. The input file objects are read-only views of
verified bytes. The default branch and FUNCTION_CAP mapping are unchanged.
Public `Entry` construction uses the same pure material/claim derivation and the
existing Phase 1 projection helper. No CORE state transition, migration,
publication permission, scheduler or automatic deletion is introduced here.

## Verification evidence

New isolated tests cover alias-only accounting, source evidence, unchanged IDs
and code, alias chains/cycles/missing targets, ambiguous declarations, inherit
missing/invalid targets, low-confidence interpretations, absence of downstream
capability copying, strict UTF-8, literal source mapping and D1 opt-in isolation.

On the pinned source commit above, the new preflight accounts for all 478
physical candidates, recognizes 20 aliases and 85 explicit supported-function
references, emits zero diagnostics and produces 1,898 valid public entries.
Those counts are measured evidence, **not invariants** or a completeness oracle.
The snapshot-local result is recorded in `work/gtfobins-d2-proof.json`; it does not
certify any future upstream revision or other source.
