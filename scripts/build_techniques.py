#!/usr/bin/env python3
"""Build technique views from the validated local relationship graph."""
from __future__ import annotations

import argparse
import json
from knowledge.graph import ROOT, write_json
from knowledge.techniques import build_techniques
from knowledge.registry import DEFAULT_REGISTRY, load_registry


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--graph', default=str(ROOT / 'site/graph.json'))
    parser.add_argument('--registry', default=str(DEFAULT_REGISTRY), help='pinned offline registry JSON')
    parser.add_argument('--without-registry', action='store_true', help='explicit identifier-only build')
    parser.add_argument('--out', default=str(ROOT / 'site/techniques.json'))
    args = parser.parse_args(argv)
    with open(args.graph, encoding='utf-8') as handle:
        data = build_techniques(json.load(handle), None if args.without_registry else load_registry(args.registry))
    write_json(args.out, data)
    verified = sum(t['registry_status'] == 'verified' for t in data['techniques'])
    print(f"technique views: {data['count']} identifiers; {verified} match pinned registry")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
