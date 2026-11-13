"""Build the provenance-aware UI dataset without altering the legacy public API.

Optional validated CORE state supplies observations, never clock-derived freshness.
Raw source evidence is separate and loaded only on an entry's evidence disclosure.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import yaml

from scripts.build_site_data import KEEP
from adapters.projection import build as project
from phase5.canonical import nfc
from phase5.state import validate_body, validate_envelope

ROOT = Path(__file__).resolve().parents[1]


def build_experience(entries, state=None):
    if state is not None:
        validate_body(state)
    observed = {e["entry_id"]: e for e in (state or {}).get("entries", [])}
    catalog, evidence, seen = [], {}, set()
    for entry in sorted(entries, key=lambda e: e["id"]):
        eid = nfc(entry["id"])
        if eid in seen:
            raise ValueError(f"duplicate entry id: {eid}")
        seen.add(eid)
        row = {k: copy.deepcopy(entry[k]) for k in KEEP if k in entry}
        row["id"] = eid
        # Public interpretation is always rederived from claims, never copied
        # from possibly drifted top-level projections. Raw source evidence stays raw.
        row.update(project(entry.get("enrichment", {})))
        row["sources"] = copy.deepcopy(entry.get("sources", []))
        row["claims"] = copy.deepcopy(entry.get("enrichment", {}))
        record = observed.get(eid)
        row["freshness"] = {
            "classification": record["classification"] if record else "NOT_OBSERVED",
            "initialized": record["initialized"] if record else False,
            "observation_id": state["last_observation_id"] if record else None,
        }
        catalog.append(row)
        evidence[eid] = copy.deepcopy(entry.get("source_data", {}))
    return {"version": 1, "count": len(catalog), "entries": catalog}, {"version": 1, "entries": evidence}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entries", type=Path, default=ROOT / "data/entries")
    parser.add_argument("--out", type=Path, default=ROOT / "site")
    parser.add_argument("--state", type=Path, help="validated CORE envelope; omitted means not observed")
    args = parser.parse_args()
    entries = []
    for path in sorted(args.entries.rglob("*.yaml")):
        if path.is_symlink() or not path.is_file():
            continue
        entry = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            raise ValueError(f"invalid catalog entry: {path}")
        entries.append(entry)
    state = validate_envelope(args.state.read_bytes()) if args.state else None
    # validate_envelope returns the body, not the transport envelope.
    catalog, evidence = build_experience(entries, state)
    args.out.mkdir(parents=True, exist_ok=True)
    for name, payload in (("catalog.json", catalog), ("evidence.json", evidence)):
        (args.out / name).write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Built experience for {catalog['count']} entries")


if __name__ == "__main__":
    main()
