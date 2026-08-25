#!/usr/bin/env python3
"""Sync orchestrator — runs registered adapters into data/entries/.

  python -m scripts.sync              # run every adapter
  python -m scripts.sync --only gtfobins
"""

from __future__ import annotations
import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from adapters.gtfobins import GTFOBinsAdapter  # noqa: E402
from adapters.lolbas import LOLBASAdapter  # noqa: E402
from adapters.wadcoms import WADComsAdapter  # noqa: E402
from adapters.lolad import LOLADAdapter  # noqa: E402

# Register adapters here as they are added.
ADAPTERS = {
    "gtfobins": GTFOBinsAdapter,
    "lolbas": LOLBASAdapter,
    "wadcoms": WADComsAdapter,
    "lolad": LOLADAdapter,
    # "loldrivers": LOLDriversAdapter,
}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--only", help="run a single adapter by key")
    args = p.parse_args()

    out = ROOT / "data" / "entries"
    keys = [args.only] if args.only else list(ADAPTERS)
    total = 0
    for key in keys:
        cls = ADAPTERS.get(key)
        if not cls:
            sys.exit(f"unknown adapter: {key} (have: {', '.join(ADAPTERS)})")
        total += cls().run(out)
    print(f"done — {total} entries across {len(keys)} adapter(s)")


if __name__ == "__main__":
    main()
