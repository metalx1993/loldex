"""Adapter template — copy this to adapters/<yoursource>.py and fill it in.

The highest-value contribution to loldex is a new adapter: one file wires an
entire upstream catalogue into the index via automated sync.

Rules of the game:
  1. Do NOT invent techniques. Normalize what the upstream project documents.
  2. Map upstream vocab into the CLOSED taxonomies in schema/schema.yaml.
     Need a value that doesn't exist? That's a schema PR, not a free string.
  3. Verify the upstream LICENSE and record it per entry. If it's not
     redistributable (ShareAlike / NonCommercial), it's reference material for
     a human curator, not a sync source — don't ingest it.
  4. Every entry needs provenance (sources) — it's mandatory.

Run it with:  python -m scripts.sync --only <yoursource>
"""

from __future__ import annotations
from typing import Iterable

from .base import Adapter, Entry


class TemplateAdapter(Adapter):
    source_name = "CHANGEME"                       # e.g. "LOLDrivers"
    platform = "windows"                           # linux | windows | macos | active-directory
    upstream_url = "https://example.github.io"
    license = "UNKNOWN — verify before use"        # e.g. "GPL-3.0"

    def fetch(self):
        """Return raw upstream data.

        Prefer a shallow git clone or a released data file over the GitHub API
        (which is rate-limited). Return whatever shape normalize() expects.
        """
        raise NotImplementedError

    def normalize(self, raw) -> Iterable[Entry]:
        """Yield canonical Entry objects.

        Minimal example of the mapping you have to do:
        """
        src = self.source_stub(upstream_version="")
        for item in raw:                            # noqa: F841 (illustrative)
            yield Entry(
                id=f"{self.source_name.lower()}/{item['name']}/{item['vector']}",
                type="binary",                      # or script/library/driver/technique
                platform=self.platform,
                name=item["name"],
                phases=["execution"],               # map from upstream, must be in taxonomy
                capabilities=["command-execution"], # map from upstream, must be in taxonomy
                privilege_required="user",          # map from upstream, must be in taxonomy
                commands=[{"template": item["command"]}],
                sources=[src],
                references=[item.get("url", self.upstream_url)],
                tags=[self.platform, self.source_name.lower()],
            )
