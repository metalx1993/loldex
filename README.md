# loldex

**A unified, searchable index of living-off-the-land techniques across Linux, Windows, and Active Directory.**

Live: https://loldex.sh

The security community documents living-off-the-land (LOL) techniques across a
dozen separate catalogues — each with its own format, taxonomy, and search.
loldex **unifies them into one normalized index** you can pivot across by
platform, kill-chain phase, required privilege, and capability — the query a
red teamer actually runs on an engagement.

loldex is an **aggregator, not a re-cataloguer**: it normalizes and enriches
what upstream projects already publish, and links back to every source. See
[ATTRIBUTION.md](ATTRIBUTION.md).

## What's inside

| Platform | Entries | Sources |
|----------|--------:|---------|
| Linux | 1,898 | GTFOBins |
| Windows | 1,198 | LOLBAS, LOLDrivers |
| Active Directory | 240 | WADComs, LOLAD |
| **Total** | **3,336** | |

Entry types: binaries, scripts, libraries, drivers (BYOVD), and AD techniques.
Entries expose available commands, required privilege, capabilities and phases.
ATT&CK mappings and opsec/detection notes are included where supported by the
source-attributed claims; missing mappings are never fabricated.

## How it works

```
upstream catalogues        adapters/            data/entries/
(GTFOBins, LOLBAS,   -->    normalize into  -->  one YAML file
 WADComs, LOLAD,           canonical schema      per technique
 LOLDrivers)                                          |
                                                      v
                                            scripts/build_site_data.py
                                                      |
                                                      v
                                            site/data.json  (client-side search)
                                                +  api.php   (query API)
```

- `schema/schema.yaml` — the canonical schema and closed taxonomies.
- `adapters/` — one adapter per source; each turns upstream data into entries
  that validate against the schema.
- `scripts/sync.py` — retired acquisition entry point; use verified D2 refresh.
  `scripts/validate.py` — CI gate.
  `scripts/build_site_data.py` — builds the site's search data.
- `site/` — the static site (landing, client-side search, contact) plus a
  self-contained PHP API (`api.php`) and contact handler (`contact.php`).
- `.github/workflows/sync.yml` — scheduled and manual verified D2 five-source snapshot:
  validates, rebuilds all static knowledge/UI data, tests, and commits onto an
  unchanged Git base. Scheduling is enabled; full automatic-cycle acceptance
  remains pending. The separate A2 host publisher
  installs immutable committed versions and activates them atomically. See
  [activation plan](docs/cron-activation.md). CORE observation remains separate.

## Build and preview locally

The checked-in corpus is sufficient. No upstream access is needed for a site build.

```bash
python3 -m pip install -r requirements.txt pytest==8.4.2
python3 -m scripts.validate
python3 -m scripts.build_all
python3 -m http.server 8765 --bind 127.0.0.1 --directory site
```

Open `http://127.0.0.1:8765/`. The experience includes global search, combined
claim-aware advanced queries, entry evidence, technique pages, declared tool identities
and a local relationship view. Search supports AND/OR/NOT, phrases and parentheses;
result explanations retain the individual supporting claims. Identity candidates
and historical aliases stay explicit and never merge techniques.
Technique metadata uses a pinned MITRE ATT&CK Enterprise 20.1 registry; metadata
matching never raises the confidence of entry claims. Revoked IDs remain labeled.

The architecture stays `source_data → enrichment → projection`. Each graph edge
retains the individual claim's provenance and confidence. Raw upstream evidence
is loaded separately; no similarity inference or destructive deduplication occurs.

### Verified CORE observation (Phase 5)

```bash
python3 -m scripts.observe --source GTFOBins=/path/to/local/upstream-git-repo \
  --state work/freshness/state.json --observation work/freshness/observation-1.json
```

Provide `--source` once per source. Omitted sources are NOT_RUN; invalid or
incomplete acquisitions fail closed. Only immutable verified Git objects are read.
The command writes only the explicit state/delivery artifacts, never the catalogue.
Reuse the exact observation file for a retry; a subsequent committed cycle uses a
new file. Read [the caller and persistence boundary](docs/phase5-completion.md)
before operation. CORE observes and classifies; publication remains separate.

To show validated CORE classifications in the UI:

```bash
python3 -m scripts.build_all --state work/freshness/state.json
```

Without a state, the UI says NOT_OBSERVED. Dates and historical corpus counts are
never evidence of a healthy observation. Legacy `scripts.sync` acquisition is disabled; use `scripts.verified_refresh` with explicit source repositories. The manual
publication workflow uses the explicit verified D2 snapshot profile; it is separate
from the frozen observer. See [D2 publication](docs/phase5-d2-publication.md).

### Checks and project status

```bash
python3 -m pytest -q
python3 -m scripts.quality_report  # read-only generated-view baseline, JSON stdout
node tests/test_experience.js
# Optional browser regression suite with Playwright installed, preview running:
node tests/browser-experience.cjs
node tests/browser_phase9.cjs
```

See [current roadmap](docs/ROADMAP.md), [delivery evidence](docs/DELIVERY.md),
[CORE + D1](docs/phase5-d1.md), [graph contract](docs/phase3-design.md),
[technique registry](docs/phase4-design.md), and [UI contract](docs/phase6-design.md), [API v1](docs/phase7-design.md),
[advanced search](docs/phase8-design.md), and [durable identities](docs/phase9-design.md).
Phases 7–9 are implemented and published on loldex.sh: 848 CI tests and live
API/browser/rollback checks passed. See [production acceptance](docs/phase9-delivery.md).
GitHub and SiteGround schedules are enabled; first automatic-cycle verification
is in progress. See [scheduler status](docs/cron-activation.md).
Phase 10 implements a complete generated-data quality report, an offline
operational-evidence checker, review/correction procedures and adversarial
regressions. See [delivery evidence](docs/phase10-delivery.md) and
[the Phase 10 plan](docs/phase10-plan.md). The real scheduled GitHub-to-host
acceptance remains open; tool delivery does not certify that production cycle.
Once captures are retained, correlate them offline with
`python3 -m scripts.check_operational_cycle work/automatic-cycle-evidence.json`;
the required evidence contract is in [the operations procedure](docs/operations-governance.md).
`site/build-manifest.json` pins the generated data files. Static builds validate
all derived views before writing. [A2 deployment](docs/a2-design.md) installs
immutable committed releases and switches the private active token atomically.
The live root migration is implemented; actual scheduled-cycle acceptance is tracked separately.

## API

The versioned public contract is [OpenAPI v1](api/openapi-v1.json). Same-release
`api-v1.php?resource=...` and `/api/v1/...` expose entries, original evidence,
advanced search with explanations/facets, graph, techniques, identities and
explicit historical-ID resolution. Responses identify their dataset; retained
release URLs remain bound to their own data. API production routing, CORS and
conditional requests passed live acceptance. The legacy routes remain available:

```
/api/stats
/api/search?q=certutil&os=windows&priv=user&cap=file-download&phase=&type=
/api/entries?limit=&offset=
/api/entry/<id>
```
`os` shorthands: `win` → windows, `ad` → active-directory.

## Contributing

loldex needs adapters for new sources, Active-Directory curation, and
opsec/detection enrichment — **not** re-cataloguing of what upstream already
covers. See `CONTRIBUTING.md`.

## Licence

Code: MIT (`LICENSE`). Aggregated data: redistributed under each upstream
source's licence — see [ATTRIBUTION.md](ATTRIBUTION.md).

### Security hardening

Contact/API validation, shared private abuse quotas, YAML expansion limits, browser
restrictions and reproducible CI dependencies are documented in
[security hardening and host publication steps](docs/security-hardening.md).
The SiteGround static response-header gate must be verified separately.

CI uses the hash-verified Python 3.12/Linux wheel lock `requirements-ci.lock`.
For PHP integration tests, copy `tests/php-runtime/package*.json` to
`work/php-runtime/` and run `npm ci --prefix work/php-runtime --ignore-scripts`.
