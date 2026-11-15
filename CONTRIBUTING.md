# Contributing to loldex

**We don't re-catalogue what upstream projects already document — we unify,
enrich, and cross-link it.** That single line decides what belongs here.

If you want to document a brand-new binary or technique, the right home is the
upstream catalogue (GTFOBins, LOLBAS, LOLAD…). `loldex` syncs from those. What
we need is the layer *on top*.

## Where you can help

| Area | What it means |
|------|---------------|
| **Adapters** | Write an adapter for a source we don't ingest yet. Highest-value contribution — one adapter adds an entire catalogue via automated sync. Start from `adapters/_template.py`. |
| **AD curation** | Active Directory sources are prose markdown; turning them into structured entries needs someone who knows the attack paths (ACL abuse, delegation, DCSync). |
| **Enrichment** | Add `opsec` (noise, triggers, detection refs) and `attack_techniques` (ATT&CK ids) — the value-add fields upstream doesn't carry. |
| **Access** | Improve search, the API, and the CLI. |
| **Sources** | Flag a missing source that passes the inclusion test (below). |

## Writing an adapter

1. Copy `adapters/_template.py` to `adapters/<yoursource>.py`.
2. Implement `fetch()` (prefer a shallow git clone or a released data file over
   the rate-limited GitHub API) and `normalize()` (yield `Entry` objects).
3. Map upstream vocabulary into the **closed taxonomies** in
   `schema/schema.yaml`. Need a value that doesn't exist? Open a schema PR — do
   not invent free-form strings.
4. Propose source admission with pinned discovery/representation fixtures,
   licence evidence and explicit D2 preflight rules. The current five-source
   publication contract is [D2](docs/phase5-d2-publication.md); adding a source
   requires contract review, not just registration in a historical sync list.
5. Run the relevant adapter/negative tests, `python -m scripts.validate`,
   `python -m scripts.quality_report` against the matching built views, and the
   full suite before delivery. `scripts.sync` remains historical compatibility;
   it is not the current production admission procedure.

For data-quality reports and changes, use the
[review and correction procedure](docs/quality-governance.md). Record the affected
revision/claim, pinned source evidence, reproduction, actual test results and
the review decision. Do not patch public projections independently of enrichment.

## The inclusion test

A source becomes a sync source only if **all three** hold:

1. **Structured data** — machine-ingestible (YAML/JSON/regular markdown).
2. **Redistributable licence** — permissive or compatible. ShareAlike /
   NonCommercial → human reference only, not ingestion.
3. **Unit = "legitimate tool/technique abused"** — not a payload against a
   vulnerability class.

## Scope & posture

`loldex` is a **reference aggregator, not an attack platform.** We index
publicly documented, redistributable material. No new weaponization, no
non-redistributable data, no "0day dumps." PRs that push past that line will be
declined regardless of technical quality — the clean posture is what keeps the
project citable and welcome in the ecosystem.

## Attribution

Credit is the currency here. Every entry records its upstream `sources`, and
contributors are credited. When you add or enrich entries, keep provenance
intact.

## Good first issues

Look for the `good first issue` label. Typical starters: enrich a handful of
GTFOBins entries with Sigma detection refs; add ATT&CK ids to a capability
group; write a `fetch()` for a source whose data is already a single JSON file.
