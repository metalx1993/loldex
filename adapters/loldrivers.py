"""LOLDrivers adapter.

LOLDrivers (magicsword-io/LOLDrivers, yaml/*.yaml) catalogues vulnerable and
malicious Windows drivers abused in Bring-Your-Own-Vulnerable-Driver (BYOVD)
attacks — typically to escalate to kernel and disable endpoint defenses.

One entry per driver file, type "driver", platform windows. Sample hashes and
signing metadata go in driver_detail for detection use.

Licence note: LOLDrivers is MIT-licensed.
"""

from __future__ import annotations
import pathlib
import subprocess
from typing import Iterable

import yaml

from .base import Adapter, Entry

LOLDRIVERS_REPO = "https://github.com/magicsword-io/LOLDrivers.git"


def slug(text: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in text.strip().lower()).strip("-")[:60]


def classify(usecase: str, desc: str):
    """Return (capabilities, phases) from the driver's stated use."""
    hay = f"{usecase} {desc}".lower()
    caps, phases = [], []
    if any(k in hay for k in ("disable", "edr", "defen", "terminat", "kill", "unhook", "bypass")):
        caps.append("defense-evasion")
        phases.append("defense-evasion")
    if any(k in hay for k in ("elevat", "privile", "kernel", "escala")):
        if "privilege-escalation" not in caps:
            caps.append("privilege-escalation")
        phases.append("privilege-escalation")
    if not caps:  # default: BYOVD enables both
        caps = ["privilege-escalation", "defense-evasion"]
        phases = ["privilege-escalation", "defense-evasion"]
    return caps, phases


class LOLDriversAdapter(Adapter):
    source_name = "LOLDrivers"
    platform = "windows"
    upstream_url = "https://www.loldrivers.io"
    license = "MIT"

    def __init__(self, clone_dir: pathlib.Path | None = None):
        self.clone_dir = clone_dir or pathlib.Path("/tmp/loldrivers_src")

    def fetch(self):
        if not (self.clone_dir / "yaml").exists():
            subprocess.run(
                ["git", "clone", "--depth", "1", LOLDRIVERS_REPO, str(self.clone_dir)],
                check=True, capture_output=True,
            )
        rev = subprocess.run(
            ["git", "-C", str(self.clone_dir), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True,
        ).stdout.strip()
        files = sorted((self.clone_dir / "yaml").glob("*.yaml"))
        return {"rev": rev, "files": files}

    def normalize(self, raw) -> Iterable[Entry]:
        src = self.source_stub(upstream_version=raw["rev"])
        seen = set()
        for path in raw["files"]:
            try:
                d = yaml.safe_load(path.read_text(encoding="utf-8", errors="replace"))
            except yaml.YAMLError:
                continue
            if not isinstance(d, dict):
                continue

            tags = d.get("Tags") or []
            name = (tags[0] if tags else d.get("Id", path.stem))
            base = f"loldrivers/{slug(name)}"
            eid = base
            n = 1
            while eid in seen:
                n += 1
                eid = f"{base}-{n}"
            seen.add(eid)

            cmd = d.get("Commands") or {}
            if isinstance(cmd, list):
                cmd = cmd[0] if cmd else {}
            usecase = str(cmd.get("Usecase", "")) if isinstance(cmd, dict) else ""
            desc = str(cmd.get("Description", "")) if isinstance(cmd, dict) else ""
            command = str(cmd.get("Command", "")).strip() if isinstance(cmd, dict) else ""
            priv_raw = str(cmd.get("Privileges", "")).lower() if isinstance(cmd, dict) else ""

            caps, phases = classify(usecase, desc)
            priv = "system" if ("kernel" in priv_raw or "system" in priv_raw) else "admin"

            attack = []
            if d.get("MitreID"):
                attack = [str(d["MitreID"]).strip()]

            # sample hashes + signing metadata for detection
            samples = d.get("KnownVulnerableSamples") or []
            first = samples[0] if samples and isinstance(samples[0], dict) else {}
            ddetail = {}
            if first.get("SHA256"):
                ddetail["sha256"] = first["SHA256"]
            if first.get("Company"):
                ddetail["signer"] = first["Company"]
            if first.get("OriginalFilename"):
                ddetail["original_filename"] = first["OriginalFilename"]
            if d.get("Category"):
                ddetail["category"] = d["Category"]

            refs = [r for r in (d.get("Resources") or []) if isinstance(r, str)]
            cmds = [{k: v for k, v in {"template": command, "comment": desc[:200] or None}.items() if v}] if command else []

            yield Entry(
                id=eid,
                type="driver",
                platform="windows",
                name=str(name),
                phases=phases,
                capabilities=caps,
                privilege_required=priv,
                attack_techniques=attack,
                driver_detail=ddetail,
                opsec={"noise": "high"} if ddetail.get("category") == "malicious" else {"noise": "medium"},
                commands=cmds,
                sources=[src],
                references=refs[:3] or [self.upstream_url],
                tags=["windows", "driver", "byovd", "loldrivers"],
            )
