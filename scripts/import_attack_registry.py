#!/usr/bin/env python3
"""Import a separately acquired and pinned official Enterprise ATT&CK STIX file offline."""
from __future__ import annotations

import argparse
from pathlib import Path
from knowledge.graph import write_json
from knowledge.registry import DEFAULT_REGISTRY, import_stix


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stix', type=Path, help='local official STIX JSON snapshot; no network requests')
    parser.add_argument('--version', required=True)
    parser.add_argument('--source-url', required=True)
    parser.add_argument('--expected-sha256', help='sha256:<64 lowercase hex> of the original STIX bytes')
    parser.add_argument('--out', type=Path, default=DEFAULT_REGISTRY)
    args = parser.parse_args(argv)
    registry = import_stix(args.stix.read_bytes(), version=args.version,
                           source_url=args.source_url, expected_sha256=args.expected_sha256)
    write_json(args.out, registry)
    print(f"Imported Enterprise ATT&CK {args.version}: {registry['metadata']['technique_count']} techniques; {registry['metadata']['source_sha256']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
