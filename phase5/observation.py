"""Pure CP5.3 candidate accounting and five-source derivation (CORE + D1).

Only immutable acquired bytes are consumed. No working tree, clock or cached
corpus is consulted. Candidate finalization applies global reject-all rules.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import base64
from collections import Counter
from pathlib import PurePosixPath
import re

import yaml
from adapters import enrich, projection
from adapters.gtfobins import FUNCTION_CAP, CONTEXT_PRIV, CAP_PHASE
from adapters.lolbas import CATEGORY_MAP, FOLDER_MAP, LOUD, map_privilege, slug
from adapters.wadcoms import ATTACK_MAP, ITEM_PRECOND
from adapters.loldrivers import classify as classify_driver
from adapters.lolad import classify as classify_ad
from .canonical import canonicalize, nfc
from .input_ref import canonical_input_ref, invalid_path_ref, PathInvalid, ROW
from .material import material_fingerprint
from .state import state_token
from .vocabulary import SOURCE_UNIVERSE, PREFIX_OWNER

SUPPRESSING = {"UNKNOWN_FUNCTION": True, "UNKNOWN_CATEGORY": True,
               "UNKNOWN_ATTACK_TYPE": False, "UNKNOWN_PRIVILEGE": False,
               "UNKNOWN_CONTEXT": False, "SUBSET_TRUNCATED": True, "EMPTY_CODE_CONTEXT": False}
RANK = {v: i for i, v in enumerate(("ACQUISITION_FAILED", "EMPTY_INPUT_SET", "INVALID_ENCODING", "IO_ERROR", "PARSE_ERROR", "EMPTY_DOCUMENT", "NON_DICT_DOCUMENT", "UNEXPECTED_EXCEPTION", "NORMALIZED_PATH_COLLISION", "DUPLICATE_ID", "MISSING_REQUIRED_FIELD", "MALFORMED_RECORD", "SUPPRESSING_UNMAPPED"))}
PARTIAL = {"MISSING_REQUIRED_FIELD", "MALFORMED_RECORD", "SUPPRESSING_UNMAPPED"}


class Defect(ValueError):
    pass


def text(value, required=False):
    if value is None:
        if required:
            raise Defect("MISSING_REQUIRED_FIELD")
        return ""
    if not isinstance(value, str):
        raise Defect("MALFORMED_RECORD")
    try:
        value.encode("utf-8", "strict")
    except UnicodeError as exc:
        raise Defect("MALFORMED_RECORD") from exc
    return value


def array(value):
    if value is None:
        return []
    if not isinstance(value, list):
        raise Defect("MALFORMED_RECORD")
    return value


def strings(value):
    return [text(v).strip() for v in array(value)]


def mapping(value, required=False):
    if value is None:
        if required:
            raise Defect("MISSING_REQUIRED_FIELD")
        return {}
    if not isinstance(value, dict):
        raise Defect("MALFORMED_RECORD")
    return value


def record(value):
    if not isinstance(value, dict):
        raise Defect("MALFORMED_RECORD")
    return value


@dataclass
class Candidate:
    ref: str
    path: str
    data: object = None
    ids: list = field(default_factory=list)
    entries: list = field(default_factory=list)
    diagnostics: list = field(default_factory=list)
    error: str | None = None

    def diag(self, code):
        self.diagnostics.append({"input_ref": self.ref, "code": code, "suppressing": SUPPRESSING[code]})


def source_failure(source, reason="ACQUISITION_FAILED", revision=None):
    if source not in SOURCE_UNIVERSE:
        raise ValueError("unknown source")
    if reason not in ("ACQUISITION_FAILED", "EMPTY_INPUT_SET", "NOT_RUN"):
        raise ValueError("invalid source failure")
    return {"source": source, "acquired_ok": reason == "EMPTY_INPUT_SET", "resolved_revision": revision if reason == "EMPTY_INPUT_SET" else None,
            "status": "unknown" if reason == "NOT_RUN" else "failed", "primary_reason": reason,
            "inputs_total": 0, "parsed_ok": 0, "rejected": [], "unmapped": [], "duplicate_ids": [], "emitted_entries": {}}


def _parse_file(source, acquired):
    try:
        ref = canonical_input_ref(source, acquired.name)
    except PathInvalid:
        return Candidate(invalid_path_ref(source), acquired.name, error="MALFORMED_RECORD")
    c = Candidate(ref, acquired.name)
    try:
        raw = acquired.content.decode("utf-8", "strict")
        if source in ("GTFOBins", "WADComs"):
            parts = raw.split("---")
            if len(parts) >= 3 and not parts[0].strip():
                raw = parts[1]
        c.data = yaml.safe_load(raw)
        if c.data is None:
            c.error = "EMPTY_DOCUMENT"
        elif not isinstance(c.data, dict):
            c.error = "NON_DICT_DOCUMENT"
    except UnicodeError:
        c.error = "INVALID_ENCODING"
    except (yaml.YAMLError, ValueError, RecursionError):
        c.error = "PARSE_ERROR"
    return c


def _lolad_candidates(bundle):
    f = bundle.files[0]
    try:
        html = f.content.decode("utf-8", "strict")
    except UnicodeError:
        return [Candidate(canonical_input_ref("LOLAD", "index.html"), "index.html", error="INVALID_ENCODING")]
    tables = re.findall(r"<table\b[^>]*>.*?</table\s*>", html, re.S | re.I)
    table_count = len(re.findall(r"<table\b", html, re.I))
    if table_count == 0:
        return []
    if table_count > 1 or not tables:
        return [Candidate(canonical_input_ref("LOLAD", "index.html"), "index.html", error="MALFORMED_RECORD")]
    candidates = []
    starts = list(re.finditer(r"<tr\b[^>]*>", tables[0], re.I))
    for position, start in enumerate(starts):
        row = tables[0][start.start():starts[position + 1].start() if position + 1 < len(starts) else len(tables[0])]
        if re.search(r"<th\b", row, re.I):
            continue
        cells = re.findall(r"<td\b[^>]*>(.*?)</td\s*>", row, re.S | re.I)
        cells = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", v)).strip() for v in cells]
        if position == 0 and len(cells) >= 2 and cells[0].lower() in ("technique", "technique/command name", "technique/command", "technique name") and cells[1].lower() == "command":
            continue
        if not re.search(r"</tr\s*>", row, re.I):
            ref = canonical_input_ref("LOLAD", "index.html", ROW(len(candidates)))
            candidates.append(Candidate(ref, "index.html", cells, error="MALFORMED_RECORD"))
            continue
        if len(cells) >= 2 and not cells[1]:
            continue
        ref = canonical_input_ref("LOLAD", "index.html", ROW(len(candidates)))
        candidates.append(Candidate(ref, "index.html", cells))
    return candidates


def _ids(source, c):
    """Provisional occurrences even when a different content field is defective."""
    d = c.data
    path = PurePosixPath(c.path)
    if source == "LOLAD":
        if isinstance(d, list) and len(d) >= 3 and d[0] and d[1]:
            enc = lambda s: base64.urlsafe_b64encode(nfc(s).encode()).rstrip(b"=").decode()
            c.ids = ["lolad/" + "/".join(enc(s) for s in d[:3])]
        return
    if not isinstance(d, dict):
        return
    if source == "LOLDrivers":
        if isinstance(d.get("Id"), str) and d["Id"]:
            c.ids = ["loldrivers/" + d["Id"]]
    elif source == "WADComs":
        c.ids = ["wadcoms/" + path.stem]
    elif source == "LOLBAS":
        for i, cmd in enumerate(d.get("Commands") if isinstance(d.get("Commands"), list) else []):
            if isinstance(cmd, dict) and (cmd.get("Category") is None or isinstance(cmd.get("Category"), str)):
                category = cmd.get("Category") or ""
                c.ids.append(f"lolbas/{slug(path.stem)}/{slug(category)}/{i}")
    elif source == "GTFOBins":
        functions = d.get("functions")
        if isinstance(functions, dict):
            for func, records in functions.items():
                if not isinstance(func, str) or not isinstance(records, list):
                    continue
                contexts = set()
                for ce in records:
                    if not isinstance(ce, dict):
                        continue
                    ctxs = ce.get("contexts") or {"unprivileged": None}
                    if isinstance(ctxs, dict):
                        for ctx, value in ctxs.items():
                            code = value.get("code") if isinstance(value, dict) and value.get("code") else ce.get("code")
                            if isinstance(ctx, str) and isinstance(code, str) and code.strip():
                                contexts.add(ctx)
                for ctx in sorted(contexts):
                    c.ids.append(f"gtfobins/{path.name}/{func}/{ctx}")


def _base(type_, platform, name, caps, phases, priv, refs, tags, commands):
    return {"type": type_, "platform": platform, "name": name, "capabilities": caps,
            "phases": phases, "privilege_required": priv, "references": refs, "tags": tags,
            "commands": commands}


def _gtfo(c):
    d = c.data
    if "functions" not in d:
        raise Defect("MALFORMED_RECORD")
    if not isinstance(d["functions"], dict):
        raise Defect("MALFORMED_RECORD")
    functions = d["functions"]
    for func, records in functions.items():
        text(func, True)
        cap = FUNCTION_CAP.get(func)
        if cap is None:
            c.diag("UNKNOWN_FUNCTION")
        per_ctx = {}
        if not isinstance(records, list):
            raise Defect("MALFORMED_RECORD")
        for ce in records:
            ce = record(ce)
            base = text(ce.get("code")).strip()
            comment = text(ce.get("comment")).strip()
            ctxs = ce.get("contexts")
            if ctxs is None or ctxs == {}:
                ctxs = {"unprivileged": None}
            ctxs = mapping(ctxs)
            for ctx, value in ctxs.items():
                text(ctx, True)
                if value is not None and not isinstance(value, dict):
                    raise Defect("MALFORMED_RECORD")
                override = text(value.get("code")) if value else ""
                code = override.strip() if override else base
                if not code:
                    c.diag("EMPTY_CODE_CONTEXT")
                    continue
                if ctx not in CONTEXT_PRIV:
                    c.diag("UNKNOWN_CONTEXT")
                per_ctx.setdefault(ctx, []).append({k: v for k, v in {"template": code, "comment": comment}.items() if v})
        for ctx, commands in per_ctx.items():
            priv = CONTEXT_PRIV.get(ctx, "user")
            phases = list(CAP_PHASE.get(cap, []))
            if cap is not None and priv in ("sudo", "suid", "capability") and "privilege-escalation" not in phases:
                phases.append("privilege-escalation")
            eid = f"gtfobins/{PurePosixPath(c.path).name}/{func}/{ctx}"
            url = f"https://gtfobins.github.io/gtfobins/{PurePosixPath(c.path).name}/"
            entry = _base("binary", "linux", PurePosixPath(c.path).name, [cap] if cap else [], phases, priv, [url], ["linux", "unix", "gtfobins"], commands)
            c.entries.append((eid, entry, {"kind": "gtfobins_natural_key", "value": "/".join((PurePosixPath(c.path).name, func, ctx))}))


def _lolbas(c):
    d, path = c.data, PurePosixPath(c.path)
    commands = d.get("Commands")
    if commands is None:
        raise Defect("MISSING_REQUIRED_FIELD")
    commands = array(commands)
    name = text(d.get("Name")) or path.stem
    detections = array(d.get("Detection"))
    iocs, detection_refs = [], []
    for detection in detections:
        detection = record(detection)
        if detection.get("IOC"):
            iocs.append(text(detection["IOC"]))
        for key in ("Sigma", "Elastic", "Splunk"):
            if detection.get(key):
                detection_refs.append(text(detection[key]))
    type_, urlseg = FOLDER_MAP[path.parts[0]]
    page = f"https://lolbas-project.github.io/lolbas/{urlseg}/{path.stem}/"
    for index, cmd in enumerate(commands):
        cmd = record(cmd)
        category = text(cmd.get("Category")).strip()
        mapped = CATEGORY_MAP.get(category)
        if mapped is None:
            c.diag("UNKNOWN_CATEGORY")
        caps, phases = ([mapped[0]], mapped[1]) if mapped else ([], [])
        rawpriv = text(cmd.get("Privileges"))
        if rawpriv and not any(v in rawpriv.lower() for v in ("system", "admin", "user", "any", "low", "sebackup", "backup operators")):
            c.diag("UNKNOWN_PRIVILEGE")
        command, desc = text(cmd.get("Command")).strip(), text(cmd.get("Description")).strip()
        entry = _base(type_, "windows", name, caps, phases, map_privilege(rawpriv), [page], ["windows", "lolbas"], [{k: v for k, v in {"template": command, "comment": desc}.items() if v}] if command else [])
        alias = path.stem.lower()
        entry["aliases"] = [alias] if alias != slug(path.stem) else []
        entry["opsec"] = {"noise": "high" if mapped and mapped[0] in LOUD else "medium"}
        if iocs:
            entry["opsec"]["triggers"] = iocs[0]
        if detection_refs:
            entry["opsec"]["detection_refs"] = detection_refs[:6]
        mitre = text(cmd.get("MitreID")).strip()
        entry["attack_techniques"] = [mitre] if mitre else []
        eid = f"lolbas/{slug(path.stem)}/{slug(category)}/{index}"
        c.entries.append((eid, entry, None))


def _wadcoms(c):
    d, path = c.data, PurePosixPath(c.path)
    command = text(d.get("command"), True).strip()
    if not command:
        raise Defect("MISSING_REQUIRED_FIELD")
    attack_types, items, services, refs = (strings(d.get(k)) for k in ("attack_types", "items", "services", "references"))
    raw_items = [text(v) for v in array(d.get("items"))]
    caps, phases = [], []
    for attack in attack_types:
        mapped = ATTACK_MAP.get(attack)
        if mapped is None:
            c.diag("UNKNOWN_ATTACK_TYPE")
        else:
            caps.append(mapped[0]); phases.extend(mapped[1])
    if not attack_types:
        caps, phases = ["discovery"], ["discovery"]
    desc = " ".join(text(d.get("description")).strip().split())
    if len(desc) > 280 or len(refs) > 4:
        c.diag("SUBSET_TRUNCATED")
    entry = _base("technique", "active-directory", path.stem.replace("-", " "), caps, phases, "none" if "No_Creds" in raw_items else "domain-user", [r for r in refs if r][:4], ["active-directory", "wadcoms"] + [s.lower() for s in services], [{k: v for k, v in {"template": command, "comment": desc[:280]}.items() if v}])
    entry["preconditions"] = [ITEM_PRECOND.get(i, i.replace("_", " ").lower()) for i in items]
    c.entries.append(("wadcoms/" + path.stem, entry, None))


def _driver(c):
    d = c.data
    identity = d.get("Id")
    if not isinstance(identity, str) or not identity:
        raise Defect("MISSING_REQUIRED_FIELD")
    text(identity, True)
    tags = [text(v) for v in array(d.get("Tags"))]
    cmd = d.get("Commands")
    if isinstance(cmd, list):
        if len(cmd) > 1:
            c.diag("SUBSET_TRUNCATED")
        cmd = record(cmd[0]) if cmd else {}
    cmd = mapping(cmd)
    usecase, desc, command, rawpriv = (text(cmd.get(k)) for k in ("Usecase", "Description", "Command", "Privileges"))
    command = command.strip()
    caps, phases = classify_driver(usecase, desc)
    priv = "system" if any(v in rawpriv.lower() for v in ("kernel", "system")) else "admin"
    samples = array(d.get("KnownVulnerableSamples"))
    refs = [text(v) for v in array(d.get("Resources"))]
    if len(samples) > 1 or len(refs) > 3 or len(desc) > 200:
        c.diag("SUBSET_TRUNCATED")
    sample = record(samples[0]) if samples else {}
    detail = {out: text(sample.get(key)) for out, key in (("sha256", "SHA256"), ("signer", "Company"), ("original_filename", "OriginalFilename")) if sample.get(key)}
    if d.get("Category"):
        detail["category"] = text(d["Category"])
    entry = _base("driver", "windows", tags[0] if tags else "", caps, phases, priv, refs[:3] or ["https://www.loldrivers.io"], ["windows", "driver", "byovd", "loldrivers"], [{k: v for k, v in {"template": command, "comment": desc[:200]}.items() if v}] if command else [])
    entry["driver_detail"] = detail
    entry["opsec"] = {"noise": "high" if detail.get("category") == "malicious" else "medium"}
    mitre = text(d.get("MitreID")).strip()
    entry["attack_techniques"] = [mitre] if mitre else []
    c.entries.append(("loldrivers/" + identity, entry, {"kind": "loldrivers_id", "value": identity}))


def _lolad(c):
    cells = c.data
    if len(cells) < 3:
        raise Defect("MALFORMED_RECORD")
    name, command, ptype = cells[:3]
    if not name:
        raise Defect("MISSING_REQUIRED_FIELD")
    cap, phases, priv = classify_ad(name, command)
    entry = _base("technique", "active-directory", name, [cap], phases, priv, ["https://lolad-project.github.io"], ["active-directory", "lolad"] + ([ptype.lower()] if ptype else []), [{"template": command}])
    c.entries.append((c.ids[0], entry, None))


DERIVE = {"GTFOBins": _gtfo, "LOLBAS": _lolbas, "WADComs": _wadcoms, "LOLDrivers": _driver, "LOLAD": _lolad}


def _layered_projection(source, c, entry, revision):
    """Keep raw evidence, per-claim interpretation and public projection separate.

    Observation output carries only the fingerprint, but its input follows the
    same layered boundary as public entries. No projection-owned field is a
    second source of truth.
    """
    entry = dict(entry)
    tag = source.lower() + "@" + revision
    heuristic = source in ("LOLAD", "LOLDrivers")
    mapping_type = "heuristic" if heuristic else "adapter"
    confidence = "low" if heuristic else "high"
    note = "source-specific keyword/default interpretation" if heuristic else None
    if source == "WADComs" and not c.data.get("attack_types"):
        mapping_type, confidence, note = "heuristic", "low", "no upstream attack_types; defaulted to discovery"
    def claims(values, ptype=mapping_type, conf=confidence, why=note):
        return enrich.claims(values, ptype=ptype, source=source, adapter=tag,
                             confidence=conf, **({"note": why} if why else {}))
    privilege_type = "heuristic" if heuristic else "adapter"
    privilege = entry.pop("privilege_required", "")
    enrichment = enrich.assemble(
        capabilities=claims(entry.pop("capabilities", [])),
        phases=claims(entry.pop("phases", [])),
        privilege=enrich.enriched(privilege, ptype=privilege_type, source=source,
                                  adapter=tag, confidence="low" if heuristic else "high",
                                  **({"note": note} if heuristic else {})),
        attack_techniques=claims(entry.pop("attack_techniques", []), "upstream", "high", None))
    raw = c.data if isinstance(c.data, dict) else dict(zip(("name", "command", "type"), c.data[:3]))
    upstream_url = {"GTFOBins": "https://gtfobins.github.io", "LOLBAS": "https://lolbas-project.github.io", "WADComs": "https://wadcoms.github.io", "LOLDrivers": "https://www.loldrivers.io", "LOLAD": "https://lolad-project.github.io"}[source]
    entry["source_data"] = {source: {"raw": raw, "upstream_url": upstream_url, "upstream_version": revision}}
    entry["enrichment"] = enrichment
    entry.update(projection.build(enrichment))
    return entry


def adapter_result(bundle):
    """Complete result with global collision precedence and no silent skip."""
    source = bundle.source
    candidates = _lolad_candidates(bundle) if source == "LOLAD" else [_parse_file(source, f) for f in bundle.files]
    if not candidates:
        return source_failure(source, "EMPTY_INPUT_SET", bundle.revision)
    refs = Counter(c.ref for c in candidates if c.ref != invalid_path_ref(source))
    for c in candidates:
        if refs[c.ref] > 1:
            c.error = "NORMALIZED_PATH_COLLISION"
        if c.error is None:
            _ids(source, c)
            c.ids = [eid for eid in c.ids if not any(0xD800 <= ord(char) <= 0xDFFF for char in eid)]
    occurrences = Counter(nfc(eid) for c in candidates if c.error is None for eid in c.ids)
    duplicates = sorted(eid for eid, count in occurrences.items() if count > 1)
    for c in candidates:
        if any(nfc(eid) in duplicates for eid in c.ids):
            c.error = "DUPLICATE_ID"
    rejected, unmapped, emitted = [], [], {}
    parsed = 0
    for c in candidates:
        if c.error is None:
            try:
                DERIVE[source](c)
                # Fingerprinting can fail on impossible scalar/detail shapes;
                # all the candidate's siblings then fail together.
                material = [(nfc(eid), material_fingerprint(_layered_projection(source, c, entry, bundle.revision)), ident) for eid, entry, ident in c.entries]
            except Defect as exc:
                c.error = str(exc)
            except (TypeError, ValueError, KeyError, IndexError, AttributeError, RecursionError):
                c.error = "MALFORMED_RECORD"
            except Exception:
                c.error = "UNEXPECTED_EXCEPTION"
        if c.error:
            rejected.append({"input_ref": c.ref, "code": c.error})
        else:
            parsed += 1
            unmapped.extend(c.diagnostics)
            for eid, fingerprint, identity in material:
                emitted[eid] = {"material_fingerprint": fingerprint, "owner_evidence": {"source_data_projects": [source], "declared_sources": [source], "id_prefix": eid.split("/", 1)[0]}, "upstream_identity": identity}
    reasons = {r["code"] for r in rejected}
    if any(d["suppressing"] for d in unmapped):
        reasons.add("SUPPRESSING_UNMAPPED")
    primary = min(reasons, key=RANK.__getitem__) if reasons else "NONE"
    result = {"source": source, "acquired_ok": True, "resolved_revision": bundle.revision, "status": "ok" if primary == "NONE" else "partial" if primary in PARTIAL else "failed", "primary_reason": primary, "inputs_total": len(candidates), "parsed_ok": parsed,
              "rejected": sorted(rejected, key=lambda d: (d["input_ref"], d["code"])), "unmapped": sorted(unmapped, key=lambda d: (d["input_ref"], d["code"])), "duplicate_ids": duplicates, "emitted_entries": emitted}
    return canonicalize(result)


def build_observation(base_body, bundles):
    """One finalized observation from one captured base and immutable bundles.

    Mapping absent source => NOT_RUN; explicitly None => acquisition failed.
    Caller must retain these canonical bytes for retry, never rebuild same base.
    """
    unknown = set(bundles) - SOURCE_UNIVERSE
    if unknown:
        raise ValueError("unknown source")
    results = []
    for source in sorted(SOURCE_UNIVERSE):
        bundle = bundles.get(source)
        if bundle is not None and bundle.source != source:
            raise ValueError("bundle/source mismatch")
        results.append(adapter_result(bundle) if bundle is not None else source_failure(source, "ACQUISITION_FAILED" if source in bundles else "NOT_RUN"))
    return canonicalize({"observation_id": base_body["last_observation_id"] + 1, "base_state": state_token(base_body), "results": results})
