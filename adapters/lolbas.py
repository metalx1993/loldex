"""LOLBAS adapter.

Maps LOLBAS (yml/*/*.yml) into canonical entries. LOLBAS models each
living-off-the-land binary/script/library as one YAML file containing multiple
`Commands`, each with its own Category, Privileges, and MitreID. We emit one
canonical entry per command, mirroring how the GTFOBins adapter emits one entry
per (binary, function, context) — so a query like `--cap credential-dump` or
`--priv admin` filters correctly.

Mapping axes:
  - Command.Category    -> capability + default kill-chain phase(s)
  - Command.Privileges  -> privilege_required
  - folder (OSBinaries / OSScripts / OSLibraries / OtherMSBinaries) -> type

Licence note: LOLBAS content is redistributed under its upstream licence —
verify LICENSE in the upstream repo before publishing derived data.
"""

from __future__ import annotations
import pathlib
import subprocess
from typing import Iterable

import yaml

from .base import Adapter, Entry
from . import projection, enrich

LOLBAS_REPO = "https://github.com/LOLBAS-Project/LOLBAS.git"

# LOLBAS Category -> (our capability, default kill-chain phases)
CATEGORY_MAP = {
    "Execute":        ("command-execution", ["execution"]),
    "Download":       ("file-download",     ["command-and-control"]),
    "Upload":         ("file-upload",       ["exfiltration"]),
    "AWL Bypass":     ("defense-evasion",   ["defense-evasion", "execution"]),
    "ADS":            ("defense-evasion",   ["defense-evasion"]),
    "Dump":           ("credential-dump",   ["credential-access"]),
    "Copy":           ("file-write",        ["collection"]),
    "UAC Bypass":     ("privilege-escalation", ["privilege-escalation", "defense-evasion"]),
    "Compile":        ("command-execution", ["execution"]),
    "Tamper":         ("defense-evasion",   ["defense-evasion"]),
    "Credentials":    ("credential-access", ["credential-access"]),
    "Reconnaissance": ("command-execution", ["discovery"]),
    "Decode":         ("decode",            ["defense-evasion"]),
    "Encode":         ("encode",            ["defense-evasion"]),
    "Conceal":        ("defense-evasion",   ["defense-evasion"]),
}

# folder -> (entry type, URL segment on lolbas-project.github.io)
FOLDER_MAP = {
    "OSBinaries":      ("binary",  "Binaries"),
    "OtherMSBinaries": ("binary",  "OtherMSBinaries"),
    "OSScripts":       ("script",  "Scripts"),
    "OSLibraries":     ("library", "Libraries"),
    # HonorableMentions intentionally skipped: not clean LOLBins upstream.
}

# noise heuristic: which capabilities are typically loud on an EDR
LOUD = {"file-download", "credential-dump", "command-execution", "file-upload"}


def map_privilege(raw: str) -> str:
    """Normalize a free-text LOLBAS Privileges string to our closed set."""
    s = (raw or "").strip().lower()
    if "system" in s:
        return "system"
    if "dns admin" in s:
        return "specific-right"
    if "sebackup" in s or "backup operators" in s:
        return "specific-right"
    if "admin" in s:               # administrator / local admin / local administrator
        return "admin"
    # user / any / low privileges / unknown -> user
    return "user"


def slug(text: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in text.strip().lower()).strip("-")


class LOLBASAdapter(Adapter):
    source_name = "LOLBAS"
    platform = "windows"
    upstream_url = "https://lolbas-project.github.io"
    license = "GPL-3.0"

    def __init__(self, clone_dir: pathlib.Path | None = None):
        self.clone_dir = clone_dir or pathlib.Path("/tmp/lolbas_src")

    def fetch(self):
        if not (self.clone_dir / "yml").exists():
            subprocess.run(
                ["git", "clone", "--depth", "1", LOLBAS_REPO, str(self.clone_dir)],
                check=True, capture_output=True,
            )
        rev = subprocess.run(
            ["git", "-C", str(self.clone_dir), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True,
        ).stdout.strip()
        files = []
        for folder in FOLDER_MAP:
            files += [(folder, p) for p in sorted((self.clone_dir / "yml" / folder).glob("*.yml"))]
        return {"rev": rev, "files": files}

    @staticmethod
    def _detection(data: dict) -> dict:
        """Build an opsec dict from LOLBAS Detection + IOC blocks."""
        iocs, refs = [], []
        for d in (data.get("Detection") or []):
            if not isinstance(d, dict):
                continue
            if d.get("IOC"):
                iocs.append(d["IOC"])
            for key in ("Sigma", "Elastic", "Splunk"):
                if d.get(key):
                    refs.append(d[key])
        return {"iocs": iocs, "refs": refs[:6]}

    def normalize(self, raw) -> Iterable[Entry]:
        src = self.source_stub(upstream_version=raw["rev"])
        for folder, path in raw["files"]:
            etype, urlseg = FOLDER_MAP[folder]
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8", errors="replace"))
            except yaml.YAMLError:
                continue
            if not isinstance(data, dict) or not data.get("Commands"):
                continue

            name = data.get("Name") or path.stem            # e.g. Certutil.exe
            stem = slug(path.stem)                            # e.g. certutil
            alias = path.stem.lower()
            page = f"{self.upstream_url}/lolbas/{urlseg}/{path.stem}/"
            det = self._detection(data)

            seen = 0
            for cmd in data["Commands"]:
                if not isinstance(cmd, dict):
                    continue
                category = (cmd.get("Category") or "").strip()
                mapped = CATEGORY_MAP.get(category)
                if not mapped:
                    continue
                cap, phases = mapped
                priv = map_privilege(cmd.get("Privileges", ""))
                phases = list(phases)
                if priv in ("admin", "system") and "privilege-escalation" not in phases \
                        and cap == "privilege-escalation":
                    pass  # already covered

                opsec = {"noise": "high" if cap in LOUD else "medium"}
                if det["iocs"]:
                    opsec["triggers"] = det["iocs"][0]
                if det["refs"]:
                    opsec["detection_refs"] = det["refs"]

                attack = []
                mitre = cmd.get("MitreID")
                if mitre:
                    attack = [str(mitre).strip()]

                command = (cmd.get("Command") or "").strip()
                desc = (cmd.get("Description") or "").strip() or None
                cmd_block = [{"template": command, "comment": desc}] if command else []

                tag = f"lolbas@{raw['rev']}"
                # cap/phase/priv: deterministic maps from explicit upstream
                # fields (Category, Privileges) -> adapter / high.
                enrichment = enrich.assemble(
                    capabilities=enrich.claims([cap], ptype="adapter", source="LOLBAS",
                                               adapter=tag, confidence="high"),
                    phases=enrich.claims(phases, ptype="adapter", source="LOLBAS",
                                         adapter=tag, confidence="high"),
                    privilege=enrich.enriched(priv, ptype="adapter", source="LOLBAS",
                                              adapter=tag, confidence="high"),
                    # attack_techniques: taken straight from upstream MitreID
                    # -> upstream / high (not the adapter's interpretation).
                    attack_techniques=enrich.claims(attack, ptype="upstream", source="LOLBAS",
                                                    adapter=tag, confidence="high"),
                )
                source_data = {"LOLBAS": enrich.source_block(
                    project_raw={"name": name, "category": category,
                                 "privileges": (cmd.get("Privileges") or "").strip(),
                                 "mitre_id": str(mitre).strip() if mitre else ""},
                    upstream_url=page, upstream_version=raw["rev"],
                    last_synced=src["last_synced"])}
                yield projection.make_entry(
                    source_data=source_data, enrichment=enrichment,
                    on=src["last_synced"],
                    id=f"lolbas/{stem}/{slug(category)}/{seen}",
                    type=etype,
                    platform="windows",
                    name=name,
                    aliases=[alias] if alias != stem else [],
                    opsec=opsec,
                    commands=[{k: v for k, v in c.items() if v} for c in cmd_block],
                    sources=[src],
                    references=[page],
                    tags=["windows", "lolbas"],
                )
                seen += 1
