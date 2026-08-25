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
    license = "verify upstream LICENSE"

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
            if not caps:
                caps, phases = ["discovery"], ["discovery"]

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

            yield Entry(
                id=f"wadcoms/{slug(path.stem)}",
                type="technique",
                platform="active-directory",
                name=name,
                phases=phases,
                capabilities=caps,
                privilege_required=priv,
                preconditions=preconds,
                commands=[{k: v for k, v in {"template": command, "comment": desc}.items() if v}],
                sources=[src],
                references=refs[:4],
                tags=["active-directory", "wadcoms"] + [s.lower() for s in services],
            )
