"""WADComs adapter.

WADComs (_wadcoms/*.md) is a curated cheat sheet of offensive commands against
Windows/AD environments. Each markdown file carries YAML frontmatter with a
`command`, `attack_types`, `services`, `items` (what creds/access you need),
and `references`. That is structured enough to map mechanically.

We emit one entry per file, on the active-directory platform (WADComs targets
Windows/AD; the OS field is where the *tool* runs, not the target).

Mapping:
  - attack_types -> capabilities + phases
  - items        -> preconditions (No_Creds / Username / Password / Hash / ...)
  - services     -> tags (SMB, LDAP, Kerberos, WinRM, MSSQL, ...)

Licence note: verify upstream LICENSE before publishing derived data.
"""

from __future__ import annotations
import pathlib
import subprocess
from typing import Iterable

import yaml

from .base import Adapter, Entry
from . import projection, enrich

WADCOMS_REPO = "https://github.com/WADComs/WADComs.github.io.git"

# WADComs attack_type -> (capability, phases)
ATTACK_MAP = {
    "Enumeration":       ("discovery",          ["discovery"]),
    "Exploitation":      ("command-execution",  ["execution"]),
    "PrivEsc":           ("privilege-escalation", ["privilege-escalation"]),
    "Persistence":       ("persistence",        ["persistence"]),
    "Credential Access": ("credential-access",  ["credential-access"]),
    "Lateral Movement":  ("lateral-movement",   ["lateral-movement"]),
    "Defense Evasion":   ("defense-evasion",    ["defense-evasion"]),
}

# item token -> a readable precondition
ITEM_PRECOND = {
    "No_Creds": "no credentials required",
    "Username": "a valid username",
    "Password": "a valid password",
    "Hash": "an NTLM hash (pass-the-hash)",
    "Kerberos_Ticket": "a Kerberos ticket",
    "Domain_User": "domain user context",
    "Local_Admin": "local admin on the target",
}


def slug(text: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in text.strip().lower()).strip("-")


class WADComsAdapter(Adapter):
    source_name = "WADComs"
    platform = "active-directory"
    upstream_url = "https://wadcoms.github.io"
    license = "GPL-3.0"

    def __init__(self, clone_dir: pathlib.Path | None = None):
        self.clone_dir = clone_dir or pathlib.Path("/tmp/wadcoms_src")

    def fetch(self):
        if not (self.clone_dir / "_wadcoms").exists():
            subprocess.run(
                ["git", "clone", "--depth", "1", WADCOMS_REPO, str(self.clone_dir)],
                check=True, capture_output=True,
            )
        rev = subprocess.run(
            ["git", "-C", str(self.clone_dir), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True,
        ).stdout.strip()
        files = sorted((self.clone_dir / "_wadcoms").glob("*.md"))
        return {"rev": rev, "files": files}

    @staticmethod
    def _frontmatter(path: pathlib.Path) -> dict | None:
        text = path.read_text(encoding="utf-8", errors="replace")
        parts = text.split("---")
        chunk = parts[1] if len(parts) >= 3 and parts[0].strip() == "" else text
        try:
            data = yaml.safe_load(chunk)
        except yaml.YAMLError:
            return None
        return data if isinstance(data, dict) else None

    def normalize(self, raw) -> Iterable[Entry]:
        src = self.source_stub(upstream_version=raw["rev"])
        for path in raw["files"]:
            data = self._frontmatter(path)
            if not data or not data.get("command"):
                continue

            name = path.stem.replace("-", " ")
            caps, phases = [], []
            for at in (data.get("attack_types") or []):
                mapped = ATTACK_MAP.get(str(at).strip())
                if mapped and mapped[0] not in caps:
                    caps.append(mapped[0])
                    for ph in mapped[1]:
                        if ph not in phases:
                            phases.append(ph)
            caps_from_map = bool(caps)          # did upstream attack_types drive it?
            if not caps:
                caps, phases = ["discovery"], ["discovery"]   # heuristic default

            items = data.get("items") or []
            preconds = [ITEM_PRECOND.get(str(i).strip(), str(i).strip().replace("_", " ").lower())
                        for i in items]
            # privilege: No_Creds -> none; anything cred-bearing -> domain-user
            priv = "none" if any("No_Creds" == str(i) for i in items) else "domain-user"

            services = [str(s).strip() for s in (data.get("services") or [])]
            refs = [str(r).strip() for r in (data.get("references") or []) if str(r).strip()]
            command = str(data.get("command", "")).strip()
            desc_raw = str(data.get("description", "")).strip()
            desc = " ".join(desc_raw.split())[:280] or None

            tag = f"wadcoms@{raw['rev']}"
            if caps_from_map:
                # deterministic map from upstream attack_types -> adapter / high
                cap_claims = enrich.claims(caps, ptype="adapter", source="WADComs",
                                           adapter=tag, confidence="high")
                phase_claims = enrich.claims(phases, ptype="adapter", source="WADComs",
                                             adapter=tag, confidence="high")
            else:
                # upstream stated no attack_types -> defaulted to discovery
                note = "no upstream attack_types; defaulted to discovery"
                cap_claims = enrich.claims(caps, ptype="heuristic", source="WADComs",
                                           adapter=tag, confidence="low", note=note)
                phase_claims = enrich.claims(phases, ptype="heuristic", source="WADComs",
                                             adapter=tag, confidence="low", note=note)
            enrichment = enrich.assemble(
                capabilities=cap_claims,
                phases=phase_claims,
                # privilege from a deterministic rule on the explicit `items`
                # token (No_Creds) -> adapter / high.
                privilege=enrich.enriched(priv, ptype="adapter", source="WADComs",
                                          adapter=tag, confidence="high"),
            )
            source_data = {"WADComs": enrich.source_block(
                project_raw={"file": path.stem,
                             "attack_types": [str(a).strip() for a in (data.get("attack_types") or [])],
                             "items": [str(i).strip() for i in items],
                             "services": services},
                upstream_url=self.upstream_url, upstream_version=raw["rev"],
                last_synced=src["last_synced"])}
            yield projection.make_entry(
                source_data=source_data, enrichment=enrichment,
                on=src["last_synced"],
                id=f"wadcoms/{slug(path.stem)}",
                type="technique",
                platform="active-directory",
                name=name,
                preconditions=preconds,
                commands=[{k: v for k, v in {"template": command, "comment": desc}.items() if v}],
                sources=[src],
                references=refs[:4],
                tags=["active-directory", "wadcoms"] + [s.lower() for s in services],
            )

    def normalize_complete(self, raw) -> Iterable[Entry]:
        """Explicit D2 profile; complete descriptions/references and exact mappings."""
        from .complete_data import read_document, revision
        rev = revision(raw.get("rev"))
        on = raw.get("on", self.source_stub(rev)["last_synced"])
        for path in raw["files"]:
            document, raw_text = read_document(path, frontmatter=True)
            entry, _ = complete_entry(document, file_name=path.name, revision=rev,
                                      on=on, raw_text=raw_text)
            yield entry

    @staticmethod
    def publication_preflight(raw):
        return publication_preflight(raw)


# Exact upstream labels, explicitly curated under D2-DW. These do not mutate
# ATTACK_MAP used by the frozen D1 observation profile or the legacy adapter.
COMPLETE_ATTACK_MAP = {
    **ATTACK_MAP,
    "Discovery": ("discovery", ["discovery"]),
    "Privilidge Escalation": ("privilege-escalation", ["privilege-escalation"]),
    "Laterl movement": ("lateral-movement", ["lateral-movement"]),
    "AS-REP Roasting": ("credential-access", ["credential-access"]),
    "Kerberoasting": ("kerberoast", ["credential-access"]),
    "Timeroasting": ("credential-access", ["credential-access"]),
}


def complete_entry(document, *, file_name, revision, on, raw_text):
    """Return a complete Entry and every unrecognized stated attack type.

    A missing type list may retain the established heuristic discovery default.
    An unrecognized *stated* value never creates that default. The separate
    publication preflight exposes it as UNKNOWN_ATTACK_TYPE, blocking publication.
    """
    from pathlib import PurePosixPath
    from phase5.canonical import nfc
    from .complete_data import (projection_date, raw_evidence, record, revision as valid_revision,
                                string_items, text, SourceDataError)
    document = record(document)
    revision = valid_revision(revision)
    on = projection_date(on)
    template = text(document.get("command"), required=True).strip()
    if not template:
        raise SourceDataError("MISSING_REQUIRED_FIELD", "WADComs command is required")
    raw_types = string_items(document.get("attack_types"))
    raw_items = string_items(document.get("items"))
    services = [value.strip() for value in string_items(document.get("services"))]
    references = [value.strip() for value in string_items(document.get("references")) if value.strip()]
    description = text(document.get("description"))
    tag = "wadcoms@" + revision
    capabilities, phases, unknown = [], [], []
    for original_type in raw_types:
        attack_type = original_type.strip()
        mapped = COMPLETE_ATTACK_MAP.get(attack_type)
        if mapped is None:
            unknown.append(original_type)
            continue
        note = "exact D2 mapping of upstream attack_types value: " + original_type
        capabilities.extend(enrich.claims([mapped[0]], ptype="adapter", source="WADComs", adapter=tag,
                                         confidence="high", note=note))
        phases.extend(enrich.claims(mapped[1], ptype="adapter", source="WADComs", adapter=tag,
                                   confidence="high", note=note))
    if not raw_types:
        note = "no upstream attack_types; defaulted to discovery"
        capabilities = enrich.claims(["discovery"], ptype="heuristic", source="WADComs", adapter=tag,
                                      confidence="low", note=note)
        phases = enrich.claims(["discovery"], ptype="heuristic", source="WADComs", adapter=tag,
                               confidence="low", note=note)
    enrichment = enrich.assemble(
        capabilities=capabilities, phases=phases,
        privilege=enrich.enriched("none" if "No_Creds" in raw_items else "domain-user",
                                  ptype="adapter", source="WADComs", adapter=tag, confidence="high"))
    path = PurePosixPath(file_name)
    src = {"project": "WADComs", "upstream_url": WADComsAdapter.upstream_url,
           "license": WADComsAdapter.license, "upstream_version": revision, "last_synced": on}
    source_data = {"WADComs": enrich.source_block(
        project_raw=raw_evidence(document, raw_text, file_name, frontmatter=True), upstream_url=src["upstream_url"],
        upstream_version=revision, last_synced=on)}
    command = {"template": template}
    if description:
        command["comment"] = description
    entry = projection.make_entry(
        source_data=source_data, enrichment=enrichment, on=on,
        id="wadcoms/" + nfc(path.stem), type="technique", platform="active-directory",
        name=path.stem.replace("-", " "), commands=[command],
        preconditions=[ITEM_PRECOND.get(value.strip(), value.strip().replace("_", " ").lower())
                       for value in raw_items],
        sources=[src], references=references,
        tags=["active-directory", "wadcoms"] + [service.lower() for service in services])
    return entry, unknown


def publication_preflight(raw):
    from .complete_data import preflight
    return preflight(raw, complete_entry, frontmatter=True)
