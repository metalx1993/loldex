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
from . import projection, enrich

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

            tag = f"loldrivers@{raw['rev']}"
            cap_note = ("classified heuristically from driver usecase/description "
                        "(keyword rules; defaults to privilege-escalation+defense-evasion)")
            priv_note = "keyword rule on upstream Privileges (kernel/system -> system; default admin)"
            # MITRE id is stated by upstream -> upstream/high; caps/phases and
            # privilege are keyword/default guesses -> heuristic/low. Per-claim
            # provenance keeps the upstream MITRE claim at high confidence even
            # though the same entry also carries heuristic claims.
            enrichment = enrich.assemble(
                capabilities=enrich.claims(caps, ptype="heuristic", source="LOLDrivers",
                                           adapter=tag, confidence="low", note=cap_note),
                phases=enrich.claims(phases, ptype="heuristic", source="LOLDrivers",
                                     adapter=tag, confidence="low", note=cap_note),
                privilege=enrich.enriched(priv, ptype="heuristic", source="LOLDrivers",
                                          adapter=tag, confidence="low", note=priv_note),
                attack_techniques=enrich.claims(attack, ptype="upstream", source="LOLDrivers",
                                                adapter=tag, confidence="high"),
            )
            source_data = {"LOLDrivers": enrich.source_block(
                project_raw={"id": str(d.get("Id", "")), "category": d.get("Category", ""),
                             "usecase": usecase,
                             "privileges": str(cmd.get("Privileges", "")) if isinstance(cmd, dict) else "",
                             "mitre_id": str(d["MitreID"]).strip() if d.get("MitreID") else ""},
                upstream_url=self.upstream_url, upstream_version=raw["rev"],
                last_synced=src["last_synced"])}
            yield projection.make_entry(
                source_data=source_data, enrichment=enrichment,
                on=src["last_synced"],
                id=eid,
                type="driver",
                platform="windows",
                name=str(name),
                driver_detail=ddetail,
                opsec={"noise": "high"} if ddetail.get("category") == "malicious" else {"noise": "medium"},
                commands=cmds,
                sources=[src],
                references=refs[:3] or [self.upstream_url],
                tags=["windows", "driver", "byovd", "loldrivers"],
            )

    def normalize_complete(self, raw) -> Iterable[Entry]:
        """Explicit D2 profile: no retained subset or first-record truncation."""
        from .complete_data import read_document, revision
        rev = revision(raw.get("rev"))
        on = raw.get("on", self.source_stub(rev)["last_synced"])
        for path in raw["files"]:
            document, raw_text = read_document(path)
            yield complete_entry(document, file_name=path.name, revision=rev,
                                 on=on, raw_text=raw_text)

    @staticmethod
    def publication_preflight(raw):
        return publication_preflight(raw)


def complete_entry(document, *, file_name, revision, on, raw_text):
    """D2-DW complete driver representation. Pure for explicit source/date inputs.

    All command records and sample metadata participate in material projection.
    Source-order sample/command-detail arrays preserve multiplicity. The raw
    source text remains authoritative evidence, including its YAML scalar types.
    """
    from .complete_data import (array, json_detail, projection_date, raw_evidence, record,
                                revision as valid_revision, string_items, text,
                                SourceDataError)
    from phase5.canonical import nfc
    document = record(document)
    revision = valid_revision(revision)
    on = projection_date(on)
    identity = document.get("Id")
    if not isinstance(identity, str) or not identity:
        raise SourceDataError("MISSING_REQUIRED_FIELD", "driver Id is required")
    identity = text(identity, required=True)
    tags = string_items(document.get("Tags"))
    raw_commands = document.get("Commands")
    if raw_commands is None:
        command_records = []
    elif isinstance(raw_commands, dict):
        command_records = [raw_commands] if raw_commands else []
    elif isinstance(raw_commands, list):
        command_records = [record(command) for command in raw_commands]
    else:
        raise SourceDataError("MALFORMED_RECORD", "driver Commands must be mapping or list")
    sample_records = [record(sample) for sample in array(document.get("KnownVulnerableSamples"))]
    resources = string_items(document.get("Resources"))
    category = text(document.get("Category"))
    capabilities, phases, commands = [], [], []
    privileges = []
    tag = "loldrivers@" + revision
    for index, command in enumerate(command_records or [{}]):
        usecase, description, template, privilege = (
            text(command.get(field)) for field in ("Usecase", "Description", "Command", "Privileges"))
        caps, command_phases = classify(usecase, description)
        note = f"keyword/default classification from complete Commands[{index}] usecase/description"
        capabilities.extend(enrich.claims(caps, ptype="heuristic", source="LOLDrivers",
                                         adapter=tag, confidence="low", note=note))
        phases.extend(enrich.claims(command_phases, ptype="heuristic", source="LOLDrivers",
                                   adapter=tag, confidence="low", note=note))
        privileges.append(privilege)
        if template.strip():
            block = {"template": template.strip()}
            if description:
                block["comment"] = description
            commands.append(block)
    privilege = "system" if any("kernel" in value.lower() or "system" in value.lower()
                                for value in privileges) else "admin"
    attack = text(document.get("MitreID")).strip()
    enrichment = enrich.assemble(
        capabilities=capabilities, phases=phases,
        privilege=enrich.enriched(privilege, ptype="heuristic", source="LOLDrivers",
                                  adapter=tag, confidence="low",
                                  note="complete command set: kernel/system privilege in any record -> system; otherwise admin"),
        attack_techniques=enrich.claims([attack] if attack else [], ptype="upstream", source="LOLDrivers",
                                        adapter=tag, confidence="high"))
    detail = {}
    if sample_records:
        detail["samples"] = [json_detail(sample) for sample in sample_records]
        for output, source_key in (("sha256", "SHA256"), ("signer", "Company"),
                                   ("original_filename", "OriginalFilename")):
            value = text(sample_records[0].get(source_key))
            if value:
                detail[output] = value
    if command_records:
        detail["command_metadata"] = [json_detail(command) for command in command_records]
    if category:
        detail["category"] = category
    src = {"project": "LOLDrivers", "upstream_url": LOLDriversAdapter.upstream_url,
           "license": LOLDriversAdapter.license, "upstream_version": revision, "last_synced": on}
    source_data = {"LOLDrivers": enrich.source_block(
        project_raw=raw_evidence(document, raw_text, file_name), upstream_url=src["upstream_url"],
        upstream_version=revision, last_synced=on)}
    return projection.make_entry(
        source_data=source_data, enrichment=enrichment, on=on,
        id="loldrivers/" + nfc(identity), type="driver", platform="windows", name=tags[0] if tags else "",
        aliases=tags[1:], driver_detail=detail,
        opsec={"noise": "high" if category == "malicious" else "medium"}, commands=commands,
        sources=[src], references=resources or [src["upstream_url"]],
        tags=["windows", "driver", "byovd", "loldrivers"])


def publication_preflight(raw):
    from .complete_data import preflight
    def derive(document, **kwargs):
        return complete_entry(document, **kwargs), []
    return preflight(raw, derive)
