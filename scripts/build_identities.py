"""Build the explicit, non-destructive Phase 9 identity view from local evidence."""
from __future__ import annotations
import argparse
from pathlib import Path
from knowledge.graph import ROOT, read_entries, write_json
from knowledge.identities import DEFAULT_IDENTITY_REGISTRY, build_identities, load_identity_registry


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--entries', type=Path, default=ROOT/'data/entries')
    parser.add_argument('--registry', type=Path, default=DEFAULT_IDENTITY_REGISTRY)
    parser.add_argument('--out', type=Path, default=ROOT/'site/identities.json')
    args = parser.parse_args(argv)
    payload = build_identities(read_entries(args.entries), load_identity_registry(args.registry))
    write_json(args.out, payload)
    print(f"Identity view: {payload['stats']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
