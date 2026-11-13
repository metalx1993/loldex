"""Prepare a new publication candidate from verified local upstream objects.

No live fetch, corpus update, commit, push or deployment is performed.
"""
import argparse
from pathlib import Path
import sys

from deployment.source_health import prepare_verified_sync, SourceHealthError
from phase5.canonical import canonical_bytes
from phase5.vocabulary import SOURCE_UNIVERSE


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", action="append", required=True, metavar="SOURCE=REPOSITORY")
    parser.add_argument("--revision", default="HEAD")
    parser.add_argument("--profile", choices=("d1", "publication-v2"), default="d1")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    repositories = {}
    for item in args.source:
        source, sep, repo = item.partition("=")
        if not sep or source not in SOURCE_UNIVERSE or not repo or source in repositories:
            parser.error("--source must be unique SOURCE=REPOSITORY")
        repositories[source] = (repo, args.revision)
    try:
        result = prepare_verified_sync(repositories, args.output, profile=args.profile)
    except (SourceHealthError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        if isinstance(exc, SourceHealthError) and exc.results:
            print(canonical_bytes({"sources": exc.results}).decode(), file=sys.stderr)
        return 1
    print(f"prepared verified candidate: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
