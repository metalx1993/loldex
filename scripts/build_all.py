"""Build all static data from one local corpus read, without upstream acquisition.

All derived datasets are validated before any destination is written. This is a
local build command; it is not the separate A2 atomic deployment mechanism.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from knowledge.graph import ROOT, build_graph, read_entries
from knowledge.registry import DEFAULT_REGISTRY, load_registry
from knowledge.techniques import build_techniques
from adapters.projection import build as project
from phase5.canonical import nfc
from phase5.state import validate_envelope
from scripts.build_experience import build_experience
from scripts.build_site_data import KEEP


def artifacts(entries, registry, state=None):
    # Preserve the legacy public API byte contract while refusing contradictory
    # identities/projections across public views. Do not silently migrate IDs.
    for entry in entries:
        if not isinstance(entry.get("id"), str) or entry["id"] != nfc(entry["id"]):
            raise ValueError("corpus entry ID must already be NFC canonical")
        for key, value in project(entry.get("enrichment", {})).items():
            if entry.get(key, [] if isinstance(value, list) else "") != value:
                raise ValueError(f"public projection drift for {entry['id']}: {key}")
    graph = build_graph(entries)
    techniques = build_techniques(graph, registry)
    catalog, evidence = build_experience(entries, state)
    legacy_entries = [{key: entry[key] for key in KEEP if key in entry} for entry in entries]
    legacy_entries.sort(key=lambda e: (e["platform"], e["name"], e["id"]))
    legacy = json.dumps({"count": len(legacy_entries), "entries": legacy_entries}, indent=0).encode("utf-8")
    payloads = {"data.json": legacy}
    for name, value in (("catalog.json", catalog), ("evidence.json", evidence), ("graph.json", graph), ("techniques.json", techniques)):
        payloads[name] = (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    return payloads


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entries", type=Path, default=ROOT / "data/entries")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--out", type=Path, default=ROOT / "site")
    parser.add_argument("--state", type=Path, help="optional validated CORE state for classification display")
    args = parser.parse_args(argv)
    entries = read_entries(args.entries)
    registry = load_registry(args.registry)
    state = validate_envelope(args.state.read_bytes()) if args.state else None
    payloads = artifacts(entries, registry, state)
    payloads["registry-license.txt"] = (ROOT / "data/registry/LICENSE-MITRE.txt").read_bytes()
    manifest = {"version": 1, "files": {name: "sha256:" + hashlib.sha256(value).hexdigest() for name, value in sorted(payloads.items())},
                "entries": len(entries), "registry_checksum": registry["checksum"]}
    payloads["build-manifest.json"] = (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode()
    args.out.mkdir(parents=True, exist_ok=True)
    for name, value in payloads.items():
        (args.out / name).write_bytes(value)
    print(f"Built {len(entries)} entries and all validated graph, technique, evidence and UI datasets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
