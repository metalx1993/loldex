#!/usr/bin/env python3
"""Build a deterministic relationship graph from per-claim evidence."""
from __future__ import annotations

import argparse
from knowledge.graph import ROOT, build_graph, read_entries, write_json


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=str, default=str(ROOT / 'data/entries'))
    parser.add_argument('--out', type=str, default=str(ROOT / 'site/graph.json'))
    args = parser.parse_args(argv)
    graph = build_graph(read_entries(args.data))
    write_json(args.out, graph)
    print(f"graph: {graph['stats']['nodes']} nodes, {graph['stats']['edges']} evidence edges; {len(graph['diagnostics'])} diagnostics")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
