# Phase 8 — Explainable advanced search

The pure UMD module `site/search-engine.js` runs in browsers and Node. The PHP
API mirrors this grammar and evaluator using the shared fixture
`tests/test_advanced_search_vectors.json`. It searches the existing catalog;
it does not enrich upstream data, resolve identity, or invent entry confidence.

## Query contract

The precedence is **NOT, AND, OR**. Adjacent operands imply AND. Parentheses
control grouping. Uppercase unquoted AND/OR/NOT are operators; quoted versions
are ordinary literals. Double quotes preserve phrases, with only `\"` and `\\`
escapes. A colon outside quotes introduces an exact filter. Supported fields:
`platform`, `source`, `capability`, `phase`, `type`, `privilege`, `technique`,
`confidence`, `provenance`, `freshness`. For example:

```text
(platform:linux OR platform:windows) capability:file-read confidence:high
"hello world" NOT source:WADComs
NOT (capability:file-read AND confidence:high)
```

Matching folds ASCII A–Z only. Unicode stays byte-exact: É differs from é, and
NFC café differs from its decomposed spelling. This is deliberate parity across
JavaScript and PHP without optional Unicode extensions. ASCII whitespace U+0009
through U+000D and U+0020 separates tokens; nonbreaking space is literal. Other
C0 controls and DEL are rejected. Invalid UTF-8 / isolated surrogates are errors.

Free terms search individual fields: ID, name, aliases, platform, type, privilege,
technique IDs/names, capabilities, phases, source projects, command templates and
references. A phrase must occur within one field; concatenated unrelated fields
cannot satisfy a phrase. Matching is literal substring, with no regex or code
execution. Filters compare complete values. Unknown fields, missing operands,
empty values, broken quotes, invalid escapes and unmatched parentheses fail
explicitly. There is no fallback to a different query interpretation.

Bounds are 4096 UTF-8 bytes, 128 tokens, nesting depth 16 and at most 64 positive
conjunction alternatives in any scope, with at most 4096 expanded atom/NOT
occurrences across all nested scopes. This final bound also limits serialized
AST output; opaque subtree evaluations are memoized per entry in JavaScript. Pagination requires nonnegative integer
offset and integer limit 1–500. Invalid input raises `QueryError`.

## Claim scope and negation

Positive AND/OR expressions expand into bounded conjunction alternatives. Each
alternative applies its positive confidence and provenance filters to every
positive capability, phase, technique and privilege constraint. Each selected
claim facet needs an individual supporting claim satisfying **all** qualifiers;
confidence from a different claim cannot be borrowed. Positive source filters
also constrain the provenance source of these supporting claims, including
source-only queries that select a claim facet or exclusively match claim text.
A standalone source filter or source plus metadata text needs only entry source
membership; it does not invent or require a claim. If no claim
facet is selected, the confidence/provenance filters require one attributable
matching claim. Multiple conflicting confidence values cannot match one claim.

NOT is an opaque expression evaluated in its own scope. It contributes no
positive qualifiers to its containing conjunction. It is **not** rewritten with
De Morgan: an entry with capability A at low confidence and unrelated B at high
confidence matches `NOT (capability:A AND confidence:high)`. Double negation
preserves the scoped expression. An external qualifier distributes into positive
OR alternatives, but not into a NOT subtree.

Freshness is an exact classification filter. Missing state means NOT_OBSERVED.
Neither NOT_OBSERVED nor any unknown string is treated as ACTIVE or healthy.
Search does not infer age-based freshness. Registry verification and source
metadata never supply claim confidence. A free term matching only projected
claim fields must also have a matching individually qualified claim. A free
term matching name, command, reference or other metadata remains a separate
literal predicate: its metadata reason has no confidence attached. Source
qualifiers still constrain supporting claim provenance in either case.

## Ranking, explanations and facets

Results rank by the sum of the strongest matching field weight for each positive
term in the successful alternative; the highest scoring alternative wins. NOT
and an empty query score zero. Field weights are ID 100, name 90, aliases 70,
techniques 60, commands 40, capabilities 30, phases 25, privilege 15, platform,
type and source 10, references 5. Exact free-term field matches add 20. Exact
filters score 20; confidence/provenance filters score 10. Repeated metadata does
not multiply a term's weight. Equal scores sort by raw ID in deterministic
Unicode codepoint order (equivalent to UTF-8 byte order), independent of input order. This is lexical relevance, not risk,
confidence, exploitability or identity equivalence.

Reasons expose field paths and literal matched values. Claim qualifiers expose
the actual supporting claim, its provenance and confidence. Source/name/command
matches do not acquire a fabricated confidence. Facets count distinct matching
entries, not claim occurrences. Each candidate facet is evaluated as an additional
AND constraint in every positive alternative, retaining claim correlation. Thus
an unrelated high-confidence claim does not produce a high-confidence facet for
a selected low-confidence capability. Counts refer to the full result set before
pagination.

## Module API and validation

- `parse(query)` returns `{version:1, clauses}`. A clause contains `{field,value}`
  atoms or opaque `{op:'not',clauses}` expressions.
- `evaluate(entry, parsed)` returns null or `{entry,score,reasons}`.
- `search(entries,query,{offset,limit})` returns version, total, offset, limit,
  ranked results and facets (`field: [{value,count}]`). Inputs are not mutated.

Shared vectors cover precedence, implicit AND, parentheses, scoped NOT/double
NOT, qualifier distribution, sources, mixed-confidence claims, unknown freshness,
phrases, references, Unicode, invalid grammar and controls. Node checks bounds,
claim reasons, correlated facets, stable ordering, pagination and purity, plus a
search over the actual catalog. `tests/test_advanced_search.py` runs these checks
under pytest. UI integration, accessible errors and API HTTP behavior are tested
by their owners separately; module tests do not establish deployed behavior.
