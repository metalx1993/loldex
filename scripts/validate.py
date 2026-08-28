#!/usr/bin/env python3
"""Validate every entry against the schema taxonomies. CI gate.

  python -m scripts.validate
Exits non-zero on the first invalid entry.
"""

from __future__ import annotations
import pathlib
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from adapters.base import (PHASES, CAPABILITIES, PRIVILEGES, PLATFORMS, TYPES,  # noqa: E402
                           LOLDEX_INTERPRETIVE_KEYS, EnrichedValue)


def load_schema_taxonomy():
    s = yaml.safe_load((ROOT / "schema" / "schema.yaml").read_text())
    t = s["taxonomy"]
    return set(t["phase"]), set(t["capability"]), set(t["privilege"])


def check_layers(path, d) -> int:
    """Validate the v1 layers IF present. Legacy entries (no layers) skip this
    and return 0 errors. Mirrors adapters.base.Entry layer validation."""
    errors = 0
    for proj, block in (d.get("source_data") or {}).items():
        leaked = LOLDEX_INTERPRETIVE_KEYS & set(block)
        if leaked:
            print(f"FAIL {path.name}: source_data.{proj} interpretive keys {sorted(leaked)}"); errors += 1
        if not isinstance(block.get("raw"), dict):
            print(f"FAIL {path.name}: source_data.{proj}.raw must be dict"); errors += 1
        if not (isinstance(block.get("upstream_url"), str) and block.get("upstream_url")):
            print(f"FAIL {path.name}: source_data.{proj}.upstream_url required"); errors += 1
    for field, payload in (d.get("enrichment") or {}).items():
        items = payload if isinstance(payload, list) else [payload]
        for it in items:
            if it.get("provenance", {}).get("type") not in EnrichedValue.PROV_TYPES:
                print(f"FAIL {path.name}: enrichment.{field} bad provenance.type"); errors += 1
            if it.get("confidence", {}).get("level") not in EnrichedValue.CONF_LEVELS:
                print(f"FAIL {path.name}: enrichment.{field} bad confidence.level"); errors += 1
    meta = d.get("_meta")
    if meta is not None and meta.get("schema_version") != 1:
        print(f"FAIL {path.name}: _meta.schema_version must be 1"); errors += 1
    return errors


def main():
    # 1. code taxonomies must match schema.yaml
    sp, sc, spr = load_schema_taxonomy()
    assert sp == PHASES, "phase taxonomy drift between schema.yaml and adapters/base.py"
    assert sc == CAPABILITIES, "capability taxonomy drift"
    assert spr == PRIVILEGES, "privilege taxonomy drift"

    # 2. every entry validates
    n = errors = 0
    for path in (ROOT / "data" / "entries").rglob("*.yaml"):
        d = yaml.safe_load(path.read_text())
        n += 1
        for field, allowed in (("platform", PLATFORMS), ("type", TYPES),
                               ("privilege_required", PRIVILEGES)):
            if d.get(field) not in allowed:
                print(f"FAIL {path.name}: {field}={d.get(field)!r}"); errors += 1
        for p in d.get("phases", []):
            if p not in PHASES:
                print(f"FAIL {path.name}: phase {p!r}"); errors += 1
        for c in d.get("capabilities", []):
            if c not in CAPABILITIES:
                print(f"FAIL {path.name}: capability {c!r}"); errors += 1
        if not d.get("sources"):
            print(f"FAIL {path.name}: missing sources"); errors += 1
        errors += check_layers(path, d)

    print(f"validated {n} entries — {errors} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
