#!/usr/bin/env python3
"""Package a committed LOLDEX site for offline review or explicit deployment."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from deployment.package import package_commit, read_package, resolve_commit


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--commit', default='HEAD', help='commit/ref to resolve, never working-tree files')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    resolved = resolve_commit(args.repo, args.commit)
    raw = package_commit(args.repo, resolved)
    manifest, _ = read_package(raw)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(raw)
    print(f"Packaged {manifest['release_id']} from committed {resolved}: {len(raw)} bytes")
    print('Package sha256:' + hashlib.sha256(raw).hexdigest())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
