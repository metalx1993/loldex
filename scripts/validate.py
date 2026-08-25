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
from adapters.base import (PHASES, CAPABILITIES, PRIVILEGES, PLATFORMS, TYPES)  # noqa: E402


def load_schema_taxonomy():
    s = yaml.safe_load((ROOT / "schema" / "schema.yaml").read_text())
    t = s["taxonomy"]
    return set(t["phase"]), set(t["capability"]), set(t["privilege"])


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

    print(f"validated {n} entries — {errors} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
