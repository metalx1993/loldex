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

## MITRE ATT&CK technique registry

Technique names, descriptions, tactics and lifecycle metadata are reproduced from
MITRE ATT&CK Enterprise 20.1, pinned to commit
`a8db2f52eb933c9c99060c123e088b3326d3a607` of
[mitre-attack/attack-stix-data](https://github.com/mitre-attack/attack-stix-data).
The original STIX file SHA-256 is
`539a843a7b53ed9749740b2123dddae3726b1a4831841c32aca740b011b910b5`.

© 2026 The MITRE Corporation. This work is reproduced and distributed with the
permission of The MITRE Corporation.

The complete license and disclaimers accompany the reduced registry in
`data/registry/LICENSE-MITRE.txt` and the static site in `site/registry-license.txt`.
Registry metadata does not endorse or verify the behavioral claims made by
aggregated entries; each claim retains its own source, provenance and confidence.
