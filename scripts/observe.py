"""Observe verified local upstream repositories; never publish or mutate corpus.

python -m scripts.observe --source GTFOBins=/path/to/repo --state work/state.json \
    --observation work/observation-1.json
Use the same --observation file for an exact retry. Next cycle uses a new file.
"""
import argparse
from pathlib import Path
import sys

from phase5.canonical import canonical_bytes
from phase5.runtime import cycle
from phase5.vocabulary import SOURCE_UNIVERSE


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", action="append", default=[], metavar="SOURCE=REPOSITORY", help="case-sensitive source name; omitted sources are NOT_RUN")
    parser.add_argument("--revision", default="HEAD", help="local Git revision, resolved once per repository")
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--observation", type=Path, required=True, help="write-once canonical observation; reuse this exact file to retry")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parent.parent, help="repository containing data/entries genesis inventory")
    args = parser.parse_args(argv)
    repositories = {}
    for value in args.source:
        source, sep, repo = value.partition("=")
        if not sep or source not in SOURCE_UNIVERSE or not repo or source in repositories:
            parser.error("--source requires a unique SOURCE=REPOSITORY from " + ", ".join(sorted(SOURCE_UNIVERSE)))
        repositories[source] = (repo, args.revision)
    if not repositories and not args.observation.exists():
        parser.error("provide at least one source, or an existing observation to retry")
    if args.state.resolve() == args.observation.resolve():
        parser.error("state and observation paths must differ")
    try:
        result = cycle(args.state, repositories, args.repo_root, args.observation)
    except (ValueError, OSError) as exc:
        print(f"observation failed: {exc}", file=sys.stderr)
        return 1
    print(canonical_bytes({"admission": result.admission, "report": result.report}).decode())
    return 0 if result.admission in ("APPLIED", "IDEMPOTENT_NO_OP") else 1


if __name__ == "__main__":
    raise SystemExit(main())
