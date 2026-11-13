"""Run A2 host-side operations via an authenticated shell on the destination.

No FTP fallback, automatic remote connection, scheduler or destructive cleanup.
An expected token is an explicit JSON file captured with `status` on this host.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from deployment.server import ReleaseStore, canonical, strict_json


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--public-root", type=Path, required=True)
    p.add_argument("--control-root", type=Path, required=True)
    commands = p.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    commands.add_parser("probe")
    install = commands.add_parser("install")
    install.add_argument("archive", type=Path)
    for name in ("verify", "activate", "rollback"):
        sub = commands.add_parser(name)
        sub.add_argument("release_id")
        if name != "verify":
            sub.add_argument("--expected-token", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        store = ReleaseStore(args.public_root, args.control_root)
        if args.command in ("status", "probe"):
            result = getattr(store, args.command)()
        elif args.command == "install":
            result = {"release_id": store.install(args.archive.read_bytes())}
        elif args.command == "verify":
            result = store.verify(args.release_id)
        else:
            expected = strict_json(args.expected_token.read_bytes())
            result = getattr(store, args.command)(args.release_id, expected)
        print(canonical(result).decode())
        return 0
    except (ValueError, OSError) as exc:
        print(f"deployment failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
