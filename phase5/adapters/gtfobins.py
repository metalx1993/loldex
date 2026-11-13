"""Opt-in publication-v2 GTFOBins alias/inherit support (D2-GTFO).

No upstream code is imported/executed. D1 remains the default profile.
"""
from __future__ import annotations
from dataclasses import dataclass
from collections import defaultdict
import copy
import yaml

from adapters import enrich, projection
from adapters.gtfobins import FUNCTION_CAP, CONTEXT_PRIV, CAP_PHASE
from phase5.canonical import canonical_bytes, digest_over, nfc
from phase5.material import material_fingerprint

PROFILE = "publication-v2"
D2_FUNCTION_CAP = {**FUNCTION_CAP, "privilege-escalation": "privilege-escalation"}


class GTFOError(ValueError):
    """Exception text is a CORE candidate rejection code."""


def _string(value, required=False):
    if value is None:
        if required:
            raise GTFOError("MISSING_REQUIRED_FIELD")
        return ""
    if not isinstance(value, str):
        raise GTFOError("MALFORMED_RECORD")
    try:
        value.encode("utf-8", "strict")
    except UnicodeError as exc:
        raise GTFOError("MALFORMED_RECORD") from exc
    if required and not value:
        raise GTFOError("MISSING_REQUIRED_FIELD")
    return value


@dataclass(frozen=True)
class GTFOResolution:
    documents: dict
    target_for: dict
    aliases_for: dict
    errors: dict


@dataclass(frozen=True)
class GTFOEmission:
    id: str
    material: dict
    enrichment: dict
    raw_documents: dict
    upstream_identity: dict


@dataclass(frozen=True)
class GTFODerivation:
    emissions: tuple
    diagnostics: tuple


def prepare_documents(documents):
    """Pure exact-filename alias lookup. No ID or command rewriting."""
    documents = copy.deepcopy(dict(documents))
    target_for, errors = {}, {}
    def target(name, stack):
        chain, seen = [], set()
        current = name
        while current not in target_for:
            if current in seen:
                raise GTFOError("MALFORMED_RECORD")
            seen.add(current)
            data = documents.get(current)
            if not isinstance(data, dict):
                raise GTFOError("MALFORMED_RECORD")
            if "alias" not in data:
                if not isinstance(data.get("functions"), dict) or not data["functions"]:
                    raise GTFOError("MALFORMED_RECORD")
                resolved = current
                break
            if set(data) != {"alias"}:
                raise GTFOError("MALFORMED_RECORD")
            alias = _string(data["alias"], True)
            if alias not in documents:
                raise GTFOError("MALFORMED_RECORD")
            chain.append(current)
            current = alias
        else:
            resolved = target_for[current]
        for alias in chain:
            target_for[alias] = resolved
        return resolved
    for name, data in documents.items():
        if isinstance(data, dict) and "alias" in data:
            try:
                target(name, ())
            except GTFOError as exc:
                errors[name] = str(exc)
    aliases_for = defaultdict(list)
    for alias, canonical in target_for.items():
        if alias not in errors:
            aliases_for[canonical].append(alias)
    return GTFOResolution(documents, dict(target_for),
        {key: tuple(sorted(value)) for key, value in aliases_for.items()}, errors)


def _evidence(resolution, name):
    names = {name, *resolution.aliases_for.get(name, ())}
    return {key: copy.deepcopy(resolution.documents[key]) for key in sorted(names)}


def derive_document(resolution, name, revision):
    """Pure material/claims; aliases parsed with zero emissions.

    Inherit emits its activation snippet as heuristic-low execution. No target
    capability union, command substitution or transitive expansion is made.
    """
    if name in resolution.errors:
        raise GTFOError(resolution.errors[name])
    if name in resolution.target_for:
        return GTFODerivation((), ())
    data = resolution.documents.get(name)
    if not isinstance(data, dict) or not isinstance(data.get("functions"), dict) or not data["functions"]:
        raise GTFOError("MALFORMED_RECORD")
    emissions, diagnostics = [], []
    tag = "gtfobins@" + revision
    for function, records in data["functions"].items():
        _string(function, True)
        if not isinstance(records, list) or not records:
            raise GTFOError("MALFORMED_RECORD")
        inherited = function == "inherit"
        cap = "command-execution" if inherited else D2_FUNCTION_CAP.get(function)
        if cap is None:
            diagnostics.append("UNKNOWN_FUNCTION")
        grouped = {}
        for record in records:
            if not isinstance(record, dict):
                raise GTFOError("MALFORMED_RECORD")
            from_name = None
            if inherited:
                from_name = _string(record.get("from"), True)
                canonical_from = resolution.target_for.get(from_name, from_name)
                if from_name in resolution.errors or canonical_from not in resolution.documents:
                    raise GTFOError("MALFORMED_RECORD")
                target_doc = resolution.documents[canonical_from]
                if not isinstance(target_doc, dict) or not isinstance(target_doc.get("functions"), dict) or not target_doc["functions"]:
                    raise GTFOError("MALFORMED_RECORD")
            code = _string(record.get("code")).strip()
            comment = _string(record.get("comment")).strip()
            contexts = record.get("contexts")
            if contexts is None:
                contexts = {"unprivileged": None}
            if not isinstance(contexts, dict) or not contexts:
                raise GTFOError("MALFORMED_RECORD")
            for context, value in contexts.items():
                _string(context, True)
                if value is not None and not isinstance(value, dict):
                    raise GTFOError("MALFORMED_RECORD")
                override = _string(value.get("code")) if value else ""
                actual_code = override.strip() if override else code
                if not actual_code:
                    diagnostics.append("EMPTY_CODE_CONTEXT")
                    continue
                if context not in CONTEXT_PRIV:
                    diagnostics.append("UNKNOWN_CONTEXT")
                context_comment = _string(value.get("comment")).strip() if value else ""
                comments = [item for item in (comment, context_comment) if item]
                command = {"template": actual_code}
                if comments:
                    command["comment"] = "\n\n".join(comments)
                group = grouped.setdefault(context, {"commands": [], "targets": set()})
                group["commands"].append(command)
                if from_name:
                    group["targets"].add(from_name)
        for context, group in grouped.items():
            priv = CONTEXT_PRIV.get(context, "user")
            phases = ["execution"] if inherited else list(CAP_PHASE.get(cap, []))
            if cap is not None and priv in ("sudo", "suid", "capability") and "privilege-escalation" not in phases:
                phases.append("privilege-escalation")
            note = "Upstream inherit activation snippet; no downstream capability is inferred from its target."
            ptype, confidence = ("heuristic", "low") if inherited else ("adapter", "high")
            def claims(values):
                return enrich.claims(values, ptype=ptype, source="GTFOBins", adapter=tag,
                    confidence=confidence, **({"note": note} if inherited else {}))
            enrichment = enrich.assemble(
                capabilities=claims([cap] if cap else []), phases=claims(phases),
                privilege=enrich.enriched(priv, ptype="adapter", source="GTFOBins", adapter=tag, confidence="high"))
            page = f"https://gtfobins.github.io/gtfobins/{name}/"
            aliases = resolution.aliases_for.get(name, ())
            references = [page] + [f"https://gtfobins.github.io/gtfobins/{alias}/" for alias in aliases]
            evidence = _evidence(resolution, name)
            for target in sorted(group["targets"]):
                references.append(f"https://gtfobins.github.io/gtfobins/{target}/")
                evidence.update(_evidence(resolution, resolution.target_for.get(target, target)))
            material = {"type": "binary", "platform": "linux", "name": name,
                "commands": group["commands"], "references": references,
                "aliases": list(aliases), "tags": ["linux", "unix", "gtfobins"]}
            material.update(projection.build(enrichment))
            emissions.append(GTFOEmission(
                id=nfc(f"gtfobins/{name}/{function}/{context}"), material=material,
                enrichment=enrichment, raw_documents=evidence,
                upstream_identity={"kind": "gtfobins_natural_key", "value": nfc(f"{name}/{function}/{context}")}))
    return GTFODerivation(tuple(emissions), tuple(diagnostics))


def parsed_documents(raw, adapter):
    documents = {}
    for path in raw["files"]:
        try:
            body = path.read_text(encoding="utf-8", errors="strict")
            # Current upstream files are one YAML document delimited by
            # --- / ... . Splitting on literal --- would corrupt code blocks.
            document = yaml.safe_load(body)
        except UnicodeError as exc:
            raise GTFOError("INVALID_ENCODING") from exc
        except yaml.YAMLError as exc:
            raise GTFOError("PARSE_ERROR") from exc
        except OSError as exc:
            raise GTFOError("IO_ERROR") from exc
        if document is None:
            raise GTFOError("EMPTY_DOCUMENT")
        if not isinstance(document, dict):
            raise GTFOError("NON_DICT_DOCUMENT")
        if path.name in documents:
            raise GTFOError("NORMALIZED_PATH_COLLISION")
        documents[path.name] = document
    return documents


def preflight(raw):
    """Strict D2 publication preflight; resolves only explicit source declarations.

    Return physical candidate count, alias refs exempted from D1 missing-functions
    rejections, explicitly supported function refs, and occurrence diagnostics.
    No shape error is converted to a warning. Unknown values retain diagnostics.
    """
    from adapters.gtfobins import GTFOBinsAdapter
    from phase5.input_ref import canonical_input_ref
    documents = parsed_documents(raw, GTFOBinsAdapter)
    resolution = prepare_documents(documents)
    alias_refs, function_refs, diagnostics = [], [], []
    expected_emissions, expected_evidence = {}, {}
    for name in sorted(documents):
        derived = derive_document(resolution, name, raw["rev"])
        ref = canonical_input_ref("GTFOBins", name)
        if name in resolution.target_for:
            alias_refs.append(ref)
        functions = documents[name].get("functions", {})
        if "inherit" in functions or "privilege-escalation" in functions:
            function_refs.append(ref)
        for code in derived.diagnostics:
            diagnostics.append({"input_ref": ref, "code": code})
        for emission in derived.emissions:
            identity = nfc(emission.id)
            if identity in expected_emissions:
                raise GTFOError("DUPLICATE_ID")
            expected_emissions[identity] = material_fingerprint(emission.material)
            expected_evidence[identity] = {
                "enrichment_hash": digest_over(canonical_bytes(emission.enrichment)),
                "source_hash": projection.source_hash({"raw": {"documents": emission.raw_documents}, "upstream_version": raw["rev"]}),
                "upstream_url": emission.material["references"][0]}
    return {"inputs_total": len(documents), "alias_refs": alias_refs,
            "supported_function_refs": function_refs, "diagnostics": diagnostics,
            "expected_emissions": expected_emissions, "expected_evidence": expected_evidence}


def public_entries(raw, adapter):
    """Public bridge sharing exactly the same pure D2 material derivation."""
    documents = parsed_documents(raw, adapter)
    resolution = prepare_documents(documents)
    src = adapter.source_stub(upstream_version=raw["rev"])
    for name in sorted(documents):
        derived = derive_document(resolution, name, raw["rev"])
        if derived.diagnostics:
            raise GTFOError("publication-v2 requires diagnostic-free GTFOBins")
        for emission in derived.emissions:
            structural = {key: value for key, value in emission.material.items()
                if key not in ("capabilities", "phases", "privilege_required", "attack_techniques")}
            source_data = {"GTFOBins": {
                "raw": {"documents": emission.raw_documents},
                "upstream_url": structural["references"][0],
                "upstream_version": raw["rev"], "last_synced": src["last_synced"]}}
            yield projection.make_entry(source_data=source_data, enrichment=emission.enrichment,
                on=src["last_synced"], id=emission.id, sources=[src], **structural)
