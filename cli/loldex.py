#!/usr/bin/env python3
"""loldex — unified living-off-the-land index (CLI).

Loads normalized entries from data/entries/ and searches across Linux, Windows,
and Active Directory in one query. This is the operator-facing access layer.

Examples:
  loldex search tar --os linux --priv sudo
  loldex search DCSync --platform active-directory
  loldex list --cap file-download
  loldex stats
"""

from __future__ import annotations
import argparse
import pathlib
import sys

try:
    import yaml
except ImportError:
    sys.exit("pyyaml required: pip install pyyaml")

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "entries"

C_RESET = "\033[0m"; C_AMBER = "\033[38;5;214m"; C_DIM = "\033[2m"; C_BOLD = "\033[1m"
PLATFORM_COLOR = {
    "linux": "\033[38;5;79m", "windows": "\033[38;5;75m",
    "active-directory": "\033[38;5;141m", "macos": "\033[38;5;250m",
}


def load_entries() -> list[dict]:
    out = []
    for path in DATA.rglob("*.yaml"):
        try:
            d = yaml.safe_load(path.read_text())
            if isinstance(d, dict) and "id" in d:
                out.append(d)
        except yaml.YAMLError:
            pass
    return out


def matches(e: dict, args) -> bool:
    if args.query:
        q = args.query.lower()
        hay = " ".join([e.get("name", ""), e.get("id", ""), " ".join(e.get("aliases", []))]).lower()
        if q not in hay:
            return False
    if getattr(args, "os", None) and e.get("platform") != _plat(args.os):
        return False
    if getattr(args, "platform", None) and e.get("platform") != args.platform:
        return False
    if getattr(args, "priv", None) and e.get("privilege_required") != args.priv:
        return False
    if getattr(args, "cap", None) and args.cap not in e.get("capabilities", []):
        return False
    if getattr(args, "phase", None) and args.phase not in e.get("phases", []):
        return False
    return True


def _plat(os_arg: str) -> str:
    return {"ad": "active-directory", "win": "windows"}.get(os_arg, os_arg)


def render(e: dict) -> None:
    pc = PLATFORM_COLOR.get(e.get("platform", ""), "")
    print(f"{C_BOLD}{e['name']}{C_RESET}  {pc}{e['platform']}{C_RESET}  "
          f"{C_DIM}{e['id']}{C_RESET}")
    print(f"  {C_AMBER}priv{C_RESET} {e.get('privilege_required','-'):<12}"
          f"{C_AMBER}cap{C_RESET} {','.join(e.get('capabilities',[]))}  "
          f"{C_AMBER}phase{C_RESET} {','.join(e.get('phases',[]))}")
    for c in e.get("commands", [])[:2]:
        print(f"    {C_DIM}${C_RESET} {c['template'].splitlines()[0]}")
    if e.get("opsec", {}).get("noise"):
        print(f"    {C_DIM}opsec: noise={e['opsec']['noise']}{C_RESET}")
    print()


def cmd_search(args, entries):
    hits = [e for e in entries if matches(e, args)]
    for e in sorted(hits, key=lambda x: (x["platform"], x["name"]))[: args.limit]:
        render(e)
    print(f"{C_DIM}{len(hits)} result(s){' — showing '+str(args.limit) if len(hits)>args.limit else ''}{C_RESET}")


def cmd_stats(args, entries):
    from collections import Counter
    plat = Counter(e["platform"] for e in entries)
    caps = Counter(c for e in entries for c in e.get("capabilities", []))
    print(f"{C_BOLD}loldex index{C_RESET}  ({len(entries)} entries)\n")
    print(f"{C_AMBER}by platform{C_RESET}")
    for k, v in plat.most_common():
        print(f"  {k:<18} {v}")
    print(f"\n{C_AMBER}top capabilities{C_RESET}")
    for k, v in caps.most_common(8):
        print(f"  {k:<20} {v}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="loldex", description="unified living-off-the-land index")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="search entries")
    s.add_argument("query", nargs="?", help="name / alias substring")
    s.add_argument("--os", help="linux | windows(win) | macos | active-directory(ad)")
    s.add_argument("--platform", help="exact platform value")
    s.add_argument("--priv", help="none|user|suid|sudo|capability|admin|system|domain-user|specific-right")
    s.add_argument("--cap", help="capability, e.g. file-download")
    s.add_argument("--phase", help="kill-chain phase, e.g. privilege-escalation")
    s.add_argument("--limit", type=int, default=20)
    s.set_defaults(func=cmd_search)

    ls = sub.add_parser("list", help="alias of search")
    for a in ("--os", "--platform", "--priv", "--cap", "--phase"):
        ls.add_argument(a)
    ls.add_argument("query", nargs="?")
    ls.add_argument("--limit", type=int, default=50)
    ls.set_defaults(func=cmd_search)

    st = sub.add_parser("stats", help="index summary")
    st.set_defaults(func=cmd_stats)

    args = p.parse_args(argv)
    entries = load_entries()
    args.func(args, entries)


if __name__ == "__main__":
    main()
