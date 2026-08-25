# loldex

**A unified index of living-off-the-land techniques across Linux, Windows, and Active Directory.**

The community documents living-off-the-land (LOTL) techniques across a dozen
separate catalogues — GTFOBins, LOLBAS, LOLDrivers, LOLAD, and more — each with
its own format, taxonomy, and search. `loldex` normalizes them into **one**
searchable index you can pivot across by platform, kill-chain phase, required
privilege, and capability.

> We don't re-catalogue what upstream projects already document. We **unify,
> enrich, and cross-link** it.

Status: **v0 — in development.**

---

## What it is (and isn't)

- **Is:** an aggregator. A canonical schema + a sync engine that pulls from the
  public LOTL catalogues + human enrichment (Active Directory curation, opsec /
  detection fields, ATT&CK mappings) + access layers (search, API, CLI).
- **Isn't:** a place to discover new techniques, and not a payload/exploit
  cookbook. The unit is always *a legitimate tool or technique being abused*.

## Quickstart

```bash
pip install -r requirements.txt

# populate the index from GTFOBins (real data, ~1700 entries)
python -m scripts.sync --only gtfobins

# validate every entry against the schema
python -m scripts.validate

# search across all domains in one query
python cli/loldex.py stats
python cli/loldex.py search tar --os linux --priv sudo
python cli/loldex.py search DCSync --platform active-directory
python cli/loldex.py search --cap file-download        # cross-domain pivot

# build the JSON the static site searches in-browser
python -m scripts.build_site_data
```

## Architecture

```
sources (public catalogues)          adapters/            data/entries/
  GTFOBins, GTFOArgs      ─┐          gtfobins.py   ─┐     linux/*.yaml
  LOLBAS, LOLDrivers      ─┼─ sync ─▶ lolbas.py     ─┼──▶  windows/*.yaml   ─┐
  LOLAD, WADComs          ─┘          lolad.py      ─┘     active-directory/ │
                                                                            │
  human enrichment (AD curation, opsec, ATT&CK) ────────────────────────────┤
                                                                            ▼
                                              scripts/build_site_data.py → site/data.json
                                                                            │
                                     access layers:  CLI · search · API ◀───┘
```

- `schema/schema.yaml` — the canonical polymorphic schema and closed taxonomies.
  The intellectual core: it holds a Linux binary, a Windows driver, and an AD
  technique in the same skeleton.
- `adapters/` — one adapter per source. `base.py` is the contract,
  `gtfobins.py` a working reference, `_template.py` a starting point.
- `data/entries/` — normalized YAML entries, one per (thing, vector).
- `cli/loldex.py` — the operator-facing search.
- `site/` — the static site (landing + client-side search over `data.json`).

## The inclusion test (what becomes a source)

A source is a **sync source** only if all three hold:

1. **Structured data** — YAML/JSON/regular markdown, ingestible by machine.
2. **Redistributable licence** — permissive or otherwise compatible. ShareAlike
   and NonCommercial are landmines; treat those as reference material for a
   human curator, not a sync source.
3. **Unit = "legitimate tool/technique abused"** — not a payload against a
   vulnerability class.

GTFOBins, LOLBAS, LOLDrivers, LOLAD pass. HackTricks and PayloadsAllTheThings
don't — they're prose knowledge bases / exploit cookbooks, and are for human
reference, not ingestion.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). The highest-value contribution is a new
**adapter**. Also wanted: Active Directory curation, opsec/detection enrichment,
and search/API/CLI improvements.

## See also

loldex stands on the shoulders of the projects it indexes. Credit for every
technique belongs to its original catalogue and authors:
[GTFOBins](https://gtfobins.github.io) ·
[LOLBAS](https://lolbas-project.github.io) ·
[LOLDrivers](https://www.loldrivers.io) ·
[LOLAD](https://lolad-project.github.io) ·
[WADComs](https://wadcoms.github.io) ·
[lolol.farm](https://lolol.farm)

## Licence

Code: MIT (see [LICENSE](LICENSE)). Indexed data remains under each upstream
source's licence, recorded per entry in its `sources` field.
