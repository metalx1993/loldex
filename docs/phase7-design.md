# Phase 7 — Public API v1

Status: implemented and production-accepted on 14 November 2026; see phase9-delivery.md. The API never changes CORE state or acquires upstream data.

## Contract

`api-v1.php?resource=...` and the same-release `/api/v1/...` routes expose root metadata, entries, entry, evidence, search, graph, techniques, technique, identities, identity and resolve. OpenAPI source: `api/openapi-v1.json`; its relative `./api/v1` server preserves the retained release. Legacy `api.php` remains separate.

Success envelopes contain `api_version: "1"`, `dataset`, and resource-specific `data`. Lists add bounded pagination; search adds facets and its parsed query. Dataset metadata identifies the exact build-manifest bytes, registry checksum, entry count and, for retained releases, release ID and code commit. Errors use the same versioned envelope with `data: null` and a stable error code, without filesystem paths.

GET and HEAD share validation and representation ETags. HEAD omits the body and retains the GET content length. OPTIONS returns 204. Public CORS permits GET, HEAD, OPTIONS and the If-None-Match and Content-Type headers, exposing ETag and X-LOLDEX-Dataset. Other methods return 405.

Parameters must be unique scalar UTF-8 values; percent escapes, controls, unsupported fields, array syntax and duplicate decoded names are rejected. Pagination uses canonical decimal integers: limit 1–200 (default 50), offset 0–10,000,000. Entry IDs are exact opaque strings in query parameters, never file paths. List order is stable by ID except search, which sorts by descending score and then ID.

## Integrity and isolation

Only files beside the executing API are read. Every request validates canonical build-manifest structure. Retained releases additionally require canonical release.json, its content-derived release ID, matching directory name, and its binding to build-manifest.json. Missing retained release metadata cannot silently become a development context.

Only datasets consumed by a route are loaded and checked against manifest hashes. These checks occur before conditional 304 responses. The ETag hashes the complete serialized envelope, including release metadata, preventing two code releases with identical data from sharing an incorrect validator. Immutable caching applies only to the path prefix of the actual bound retained release; query text cannot manufacture this policy. Mutable development URLs revalidate.

Evidence is read from `evidence-records/<sha256(UTF-8 entry ID)>.json` after verifying catalog membership. The shard contains exactly the original source_data object. Its verified original JSON is embedded directly, preserving empty objects versus arrays and numeric literals beyond PHP's integer range. There is no fallback to the large legacy evidence.json, another release, or the current activation.

## Search and claim semantics

`site/search-engine.php` mirrors `site/search-engine.js`. Operators are NOT, AND (including adjacency), OR, with parentheses and quoted literals. Limits are 4096 UTF-8 bytes, 128 tokens, depth 16, 64 positive alternatives and 4096 expanded atom occurrences including opaque NOT subtrees. The latter also bounds serialized query AST size and repeated recursive evaluation. Only ASCII A–Z are folded; Unicode code points remain exact. No regex evaluation, Unicode normalization dependency or upstream command execution is involved.

Positive confidence, provenance and source qualifiers constrain each positive claim facet to its own individually supporting claim. Free literals that exclusively match claim fields follow the same constraint; name, command and reference metadata matches remain independent predicates. Ranking uses eligible supporting reasons after qualification. NOT is an opaque recursively evaluated subtree with its own evidence scope; it never supplies qualifiers to the outer conjunction. Facet counts apply an additional filter under these same rules. Search responses preserve claim records and claim paths instead of assigning one confidence to an entry.

## Identities and compatibility

Identity lists use explicit active curated entry_index memberships. Candidates and stale witnesses remain separately labelled, and tool co-membership does not establish technique equivalence. Resolve first checks the exact current entry ID, then explicit historical aliases. A split returns all declared targets and the full historical evidence record; the API does not redirect, choose a winner, rewrite IDs, or silently deduplicate entries.

## Verification

`tests/test_api_v1.cjs` runs real PHP 8.3 through the existing isolated PHP runtime and compares the complete AST, ranked results, reasons and facets against the JS engine for 41 valid shared vectors, including future multi-source and no-claim entries; 17 invalid vectors must reject. HTTP cases cover retained-release binding, raw evidence fidelity, strict parameters, GET/HEAD/OPTIONS, CORS and conditional ETags. The independent `tests/test_api_v1_adversarial.cjs` attacks corruption, missing shards, retained-context downgrade, cache-context injection, malformed requests and release-bound conditional responses. The project test wrapper makes these checks part of the test gate.

Runtime tests establish local behavior. Apache routing, public CORS through the stable redirect, hosting runtime limits and retained production URLs are recorded in phase9-delivery.md as separate production acceptance evidence.

The real-corpus runner `tests/test_api_v1_corpus.cjs` additionally exercises PHP 8.2 against the built corpus, all resource families, original evidence shards and actual historical aliases, comparing complete ranked results/reasons/facets for representative queries. On the verified 3336-entry build, the runtime reported a 256M memory limit; this is the configured limit, not a measured hosting peak. Nested opaque NOT evaluation memoizes identical scopes within an entry; the bounded worst-case regression runs 50 evaluations below three seconds. Deployment performance remains a separate hosting observation.

Final nested-query hardening: PHP precomputes private opaque-scope memo keys in its search runtime and reuses per-entry NOT results across facet evaluations. These keys never enter the public parsed AST. The maximal accepted nested regression is also exercised through the complete 3336-entry API search, including facets, full JS parity and a local ten-second upper gate; the observed PHP 8.2 run completed in 814 ms. Timing is a local runtime observation, not a hosting service guarantee.
