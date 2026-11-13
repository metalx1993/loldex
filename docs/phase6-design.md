# Phase 6 — Search and evidence experience

Status: implementation contract under the user's delegated completion mandate.

## Context and decision

Keep the static HTML/CSS/JavaScript stack. Preserve `data.json` and existing API
contracts; build a separate deterministic `catalog.json` and lazy `evidence.json`.
The UI presents the layered model and per-claim provenance without assigning an
invented entry-level confidence. No new runtime framework or third-party assets.

## Acceptance

- Search names, aliases, commands, IDs, techniques, capabilities and phases.
- Combine platform/source/privilege/capability/phase/technique/confidence/freshness
  facets; confidence and origin qualify each selected claim facet, never a rating
  for the whole entry. When a source is selected, qualifying evidence must name
  that exact provenance source. With no claim facet, at least one claim must match.
- Query state has shareable URLs; all matches reachable through pagination.
- Technique and entry views link to source evidence and graph relationships.
- A local relationship view shows real graph edges with provenance and confidence;
  shared relationships do not claim cross-source equivalence or causality.
- Freshness defaults to NOT_OBSERVED. ACTIVE means present in a reliable CORE
  observation, not a promise of freshness today. No clock-based fabricated status.
- Upstream text is rendered as text. External links permit only HTTP(S).
- Combined builds reject non-NFC corpus IDs and projection drift before writing,
  so the preserved legacy API cannot contradict the graph or experience views.
- Keyboard navigation, visible focus, native disclosures, responsive layout,
  accessible labels and explicit loading/error/empty states.

## Consequences

Static hosting remains sufficient. Raw evidence is loaded only on demand. ATT&CK
names and descriptions come from the pinned Phase 4 registry; unmatched IDs stay
unverified. Revoked/deprecated metadata stays visible. No automatic publication,
cron, AI inference or destructive deduplication.
