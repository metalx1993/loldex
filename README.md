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
| Linux | 1,708 | GTFOBins |
| Windows | 1,141 | LOLBAS, LOLDrivers |
| Active Directory | 237 | WADComs, LOLAD |
| **Total** | **3,086** | |

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
- `scripts/sync.py` — runs every adapter. `scripts/validate.py` — CI gate.
  `scripts/build_site_data.py` — builds the site's search data.
- `site/` — the static site (landing, client-side search, contact) plus a
  self-contained PHP API (`api.php`) and contact handler (`contact.php`).
- `.github/workflows/sync.yml` — manual dispatch only: the legacy corpus sync
  validates, rebuilds all static knowledge/UI data, tests, and commits onto an
  unchanged Git base. Cron is disabled and automated deployment is removed; A2
  remains deferred. This is distinct from the verified CORE observation path.

## Build and preview locally

The checked-in corpus is sufficient. No upstream access is needed for a site build.

```bash
python3 -m pip install -r requirements.txt pytest
python3 -m scripts.validate
python3 -m scripts.build_all
python3 -m http.server 8765 --bind 127.0.0.1 --directory site
```

Open `http://127.0.0.1:8765/`. The experience includes global search, combined
claim-aware filters, entry evidence, technique pages and a local relationship view.
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
never evidence of a healthy observation. Legacy `scripts.sync` remains a historical compatibility path. The manual
publication workflow uses the explicit verified D2 snapshot profile; it is separate
from the frozen observer. See [D2 publication](docs/phase5-d2-publication.md).

### Checks and project status

```bash
python3 -m pytest -q
node tests/test_experience.js
# Optional browser regression suite with Playwright installed, preview running:
node tests/browser-experience.cjs
```

See [current roadmap](docs/ROADMAP.md), [delivery evidence](docs/DELIVERY.md),
[CORE + D1](docs/phase5-d1.md), [graph contract](docs/phase3-design.md),
[technique registry](docs/phase4-design.md), and [UI contract](docs/phase6-design.md).
`site/build-manifest.json` pins the generated data files. Static builds validate
all derived views before writing. [A2 deployment](docs/a2-design.md) installs
immutable committed releases and switches the private active token atomically.
The live root migration is implemented; scheduling remains an explicit gate.

## API

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
