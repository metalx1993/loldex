"""Virtual genesis — spec §12.

The genesis body is never empty: the inventory is materialized deterministically
and seeded *before* the token is computed, so orchestrator and CORE derive the
identical token from the identical inventory.

Reads only ``data/entries/`` from the local working tree. No network access.
"""
import pathlib

import yaml

from .canonical import GENESIS_LAST_OBSERVATION_HASH, canonical_bytes, digest_over
from .ownership import INVALID_PREFIX, canonical_prefix_owner
from .state import state_token
from .vocabulary import CORE_STATE_VERSION, Classification

__all__ = [
    "ENTRIES_ROOT",
    "iter_inventory_paths",
    "build_genesis_inventory",
    "seed_entry",
    "genesis_body",
    "genesis_token",
    "genesis_checksum",
]

#: §12 step 1 — the single tree examined, recursively.
ENTRIES_ROOT = "data/entries"


def iter_inventory_paths(repo_root):
    """§12 steps 2-3 — accepted files in deterministic order.

    Accepted: regular files matching ``data/entries/**/*.yaml`` (POSIX,
    case-sensitive extension). Excluded: non-``.yaml`` files, directories and
    symlinks. Sorted by repository-relative POSIX path, code-point order.
    """
    root = pathlib.Path(repo_root)
    base = root / ENTRIES_ROOT
    accepted = []
    for path in base.rglob("*.yaml"):
        if path.is_symlink() or not path.is_file():
            continue
        if path.suffix != ".yaml":  # case-sensitive
            continue
        accepted.append(path)
    return sorted(accepted, key=lambda p: p.relative_to(root).as_posix())


def seed_entry(entry_id: str, owner: str) -> dict:
    """§12 step 8 — the seeded shape for one inventory entry."""
    return {
        "entry_id": entry_id,
        "classification": Classification.NOT_OBSERVED,
        "initialized": False,
        "absence_streak": 0,
        "owner_ambiguous": False,
        "owner_sources": [owner],
        "sources": [
            {
                "source": owner,
                "material_fingerprint": None,
                "last_reliable_observation_id": None,
                "upstream_identity": None,
            }
        ],
    }


def build_genesis_inventory(repo_root) -> list:
    """§12 steps 2-8 — the seeded, sorted ``entries`` array.

    A file that fails to parse, is not a mapping, or lacks a non-empty string
    ``id`` is skipped (genesis seeds *known* entries; it is not a health pass).
    An id whose prefix is not in ``PREFIX_OWNER`` is skipped. On duplicate ids
    the first in traversal order is kept.
    """
    seen = set()
    entries = []
    for path in iter_inventory_paths(repo_root):
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 - no exception aborts the build (§12 step 4)
            continue
        if not isinstance(document, dict):
            continue
        entry_id = document.get("id")
        if not isinstance(entry_id, str) or not entry_id:
            continue
        owner = canonical_prefix_owner(entry_id)
        if owner == INVALID_PREFIX:
            continue
        if entry_id in seen:  # §12 step 7 — first wins
            continue
        seen.add(entry_id)
        entries.append(seed_entry(entry_id, owner))
    entries.sort(key=lambda e: e["entry_id"])
    return entries


def genesis_body(entries) -> dict:
    """§12 step 9 — the genesis body around a seeded inventory."""
    return {
        "core_state_version": CORE_STATE_VERSION,
        "entries": list(entries),
        "last_observation_hash": GENESIS_LAST_OBSERVATION_HASH,
        "last_observation_id": 0,
    }


def genesis_checksum(entries) -> str:
    """``sha256`` over the canonical bytes of the fully-seeded genesis body."""
    return digest_over(canonical_bytes(genesis_body(entries)))


def genesis_token(entries) -> dict:
    """The genesis ``state_token``; the inventory is incorporated before it."""
    return state_token(genesis_body(entries))
