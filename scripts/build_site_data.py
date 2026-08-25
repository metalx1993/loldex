#!/usr/bin/env python3
"""Build site/data.json from data/entries/ for client-side search.

The static site loads this single JSON and searches it in-browser — no server,
no live DB. Run in CI after every sync.
"""

from __future__ import annotations
import json
import pathlib
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "entries"
OUT = ROOT / "site" / "data.json"

KEEP = ("id", "type", "platform", "name", "aliases", "phases", "capabilities",
        "privilege_required", "attack_techniques", "commands", "opsec",
        "references", "tags")


def main():
    entries = []
    for path in DATA.rglob("*.yaml"):
        d = yaml.safe_load(path.read_text())
        if isinstance(d, dict) and "id" in d:
            entries.append({k: d[k] for k in KEEP if k in d})
    entries.sort(key=lambda e: (e["platform"], e["name"], e["id"]))
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"count": len(entries), "entries": entries}, indent=0))
    print(f"wrote {OUT} ({len(entries)} entries, {OUT.stat().st_size//1024} KB)")


if __name__ == "__main__":
    sys.exit(main())
