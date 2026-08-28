"""LOLAD adapter.

LOLAD (Living Off The Land Active Directory) publishes its techniques as an
HTML table on a single-page site: columns are Name, Command, Type, Reference.
There is no structured capability/privilege metadata, so we classify each
technique heuristically from its name and command — this is the "human-curated"
part flagged in the design. The heuristics are conservative and documented
below; refine the keyword tables as coverage grows.

Most LOLAD techniques are enumeration run as an ordinary domain user (that is
the whole point of "living off the land AD"), so those are the defaults.

Licence note: verify upstream LICENSE before publishing derived data.
"""

from __future__ import annotations
import pathlib
import re
import subprocess
from typing import Iterable

from .base import Adapter, Entry
from . import projection, enrich

LOLAD_REPO = "https://github.com/lolad-project/lolad-project.github.io.git"

# keyword (lowercase, matched in name+command) -> (capability, phases, priv_hint)
# Order matters: first match wins. Most specific first.
RULES = [
    ("dcsync",          ("credential-dump",   ["credential-access"], "specific-right")),
    ("kerberoast",      ("kerberoast",        ["credential-access"], "domain-user")),
    ("asrep",           ("kerberoast",        ["credential-access"], "domain-user")),
    ("as-rep",          ("kerberoast",        ["credential-access"], "domain-user")),
    ("golden ticket",   ("persistence",       ["persistence"],       "specific-right")),
    ("silver ticket",   ("persistence",       ["persistence"],       "specific-right")),
    ("shadow cred",     ("credential-access", ["credential-access"], "domain-user")),
    ("relay",           ("lateral-movement",  ["lateral-movement", "credential-access"], "none")),
    ("coerce",          ("coerce",            ["credential-access"], "domain-user")),
    ("petitpotam",      ("coerce",            ["credential-access"], "domain-user")),
    ("password",        ("credential-access", ["credential-access"], "domain-user")),
    ("credential",      ("credential-access", ["credential-access"], "domain-user")),
    ("lsass",           ("credential-dump",   ["credential-access"], "admin")),
    ("secretsdump",     ("credential-dump",   ["credential-access"], "admin")),
    ("add ",            ("persistence",       ["persistence"],       "domain-user")),
    ("create",          ("persistence",       ["persistence"],       "domain-user")),
    ("set ",            ("defense-evasion",   ["defense-evasion"],   "domain-user")),
    ("disable",         ("defense-evasion",   ["defense-evasion"],   "domain-user")),
    ("psexec",          ("lateral-movement",  ["lateral-movement"],  "admin")),
    ("wmiexec",         ("lateral-movement",  ["lateral-movement"],  "admin")),
    ("winrm",           ("lateral-movement",  ["lateral-movement"],  "domain-user")),
    ("evil-winrm",      ("lateral-movement",  ["lateral-movement"],  "domain-user")),
    # generic enumeration verbs (fallbacks)
    ("enum",            ("discovery",         ["discovery"],         "domain-user")),
    ("list",            ("discovery",         ["discovery"],         "domain-user")),
    ("get-",            ("discovery",         ["discovery"],         "domain-user")),
    ("find",            ("discovery",         ["discovery"],         "domain-user")),
    ("collect",         ("discovery",         ["discovery"],         "domain-user")),
    ("query",           ("discovery",         ["discovery"],         "domain-user")),
    ("search",          ("discovery",         ["discovery"],         "domain-user")),
]
DEFAULT = ("discovery", ["discovery"], "domain-user")


def slug(text: str) -> str:
    s = "".join(c if c.isalnum() else "-" for c in text.strip().lower())
    return re.sub(r"-+", "-", s).strip("-")


def classify(name: str, command: str):
    hay = f"{name} {command}".lower()
    for kw, res in RULES:
        if kw in hay:
            return res
    return DEFAULT


class LOLADAdapter(Adapter):
    source_name = "LOLAD"
    platform = "active-directory"
    upstream_url = "https://lolad-project.github.io"
    license = "verify upstream LICENSE"

    def __init__(self, clone_dir: pathlib.Path | None = None):
        self.clone_dir = clone_dir or pathlib.Path("/tmp/lolad_src")

    def fetch(self):
        if not (self.clone_dir / "index.html").exists():
            subprocess.run(
                ["git", "clone", "--depth", "1", LOLAD_REPO, str(self.clone_dir)],
                check=True, capture_output=True,
            )
        rev = subprocess.run(
            ["git", "-C", str(self.clone_dir), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True,
        ).stdout.strip()
        html = (self.clone_dir / "index.html").read_text(encoding="utf-8", errors="replace")
        return {"rev": rev, "html": html}

    @staticmethod
    def _rows(html: str):
        m = re.search(r"<table.*?</table>", html, re.S | re.I)
        if not m:
            return []
        rows = re.findall(r"<tr.*?</tr>", m.group(0), re.S | re.I)
        out = []
        for r in rows:
            cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", r, re.S | re.I)
            cells = [re.sub(r"<[^>]+>", " ", c) for c in cells]
            cells = [re.sub(r"\s+", " ", c).strip() for c in cells]
            if len(cells) >= 3:
                out.append(cells)
        return out

    def normalize(self, raw) -> Iterable[Entry]:
        src = self.source_stub(upstream_version=raw["rev"])
        seen_ids = set()
        for cells in self._rows(raw["html"]):
            name, command, ptype = cells[0], cells[1], (cells[2] if len(cells) > 2 else "")
            if name.lower().startswith("technique") or not command:
                continue  # header row or empty
            cap, phases, priv = classify(name, command)
            base = f"lolad/{slug(name)}"
            eid = base
            n = 1
            while eid in seen_ids:
                n += 1
                eid = f"{base}-{n}"
            seen_ids.add(eid)

            tags = ["active-directory", "lolad"]
            if ptype:
                tags.append(ptype.lower())

            tag = f"lolad@{raw['rev']}"
            note = "classified heuristically from technique name/command"
            # LOLAD publishes no capability/phase/privilege taxonomy — all three
            # are GUESSED by classify() from the name+command text -> heuristic/low.
            enrichment = enrich.assemble(
                capabilities=enrich.claims([cap], ptype="heuristic", source="LOLAD",
                                           adapter=tag, confidence="low", note=note),
                phases=enrich.claims(phases, ptype="heuristic", source="LOLAD",
                                     adapter=tag, confidence="low", note=note),
                privilege=enrich.enriched(priv, ptype="heuristic", source="LOLAD",
                                          adapter=tag, confidence="low", note=note),
            )
            source_data = {"LOLAD": enrich.source_block(
                project_raw={"name": name, "command": command, "type": ptype},
                upstream_url=self.upstream_url, upstream_version=raw["rev"],
                last_synced=src["last_synced"])}
            yield projection.make_entry(
                source_data=source_data, enrichment=enrichment,
                on=src["last_synced"],
                id=eid,
                type="technique",
                platform="active-directory",
                name=name,
                commands=[{"template": command}],
                sources=[src],
                references=[self.upstream_url],
                tags=tags,
            )
