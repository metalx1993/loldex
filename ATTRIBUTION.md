# Attribution & data licences

loldex is an **aggregator**. It does not originate technique data — it
normalizes and unifies data published by upstream community catalogues. All
credit for the underlying research belongs to those projects and their
contributors.

## Sources and their licences

| Source | Covers | Upstream | Licence |
|--------|--------|----------|---------|
| GTFOBins | Linux binaries | https://gtfobins.github.io | GPL-3.0 |
| LOLBAS | Windows binaries/scripts/libraries | https://lolbas-project.github.io | GPL-3.0 |
| WADComs | Windows/AD offensive commands | https://wadcoms.github.io | GPL-3.0 |
| LOLDrivers | Vulnerable/malicious drivers (BYOVD) | https://www.loldrivers.io | MIT |
| LOLAD | Active Directory techniques | https://lolad-project.github.io | see upstream |

## What this means

- The **loldex code** (adapters, scripts, schema, site) is released under the
  MIT licence — see `LICENSE`.
- The **aggregated data** in `data/` and `site/data.json` is derived from the
  sources above and is redistributed **under their respective licences**.
  Because GTFOBins, LOLBAS, and WADComs are GPL-3.0 (a copyleft licence), the
  derived dataset carries the same obligations: keep this attribution, keep the
  licence notices, and redistribute derived data under compatible terms.
- loldex does not claim ownership of upstream content and links back to each
  source on every entry.

If you maintain one of these projects and want a change to how loldex
attributes or redistributes your data, open an issue.
