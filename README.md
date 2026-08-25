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
| Windows | 1,138 | LOLBAS, LOLDrivers |
| Active Directory | 237 | WADComs, LOLAD |
| **Total** | **3,083** | |

Entry types: binaries, scripts, libraries, drivers (BYOVD), and AD techniques.
Every entry carries a command, MITRE ATT&CK mapping, required privilege,
capability, kill-chain phase, and — where available — opsec/detection notes.

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
- `.github/workflows/sync.yml` — weekly auto-sync: re-runs adapters, validates,
  rebuilds, and commits. This is what keeps the index current on its own.

## Run it locally

```bash
pip install -r requirements.txt
python -m scripts.sync              # populate data/entries from all sources
python -m scripts.validate          # validate every entry against the schema
python -m scripts.build_site_data   # build site/data.json
```

Run a single adapter: `python -m scripts.sync --only lolbas`

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
