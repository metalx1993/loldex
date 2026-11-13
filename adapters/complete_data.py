"""D2 complete-source helpers; frozen v1 adapters and projection stay unchanged.

Raw evidence is the original YAML text, so YAML types/lexical values are never
silently converted by a JSON serializer. Material detail uses explicit wrappers
for YAML scalar types outside CORE's integer-only canonical JSON domain.
"""
from __future__ import annotations

import base64
from collections import Counter
import copy
import datetime
import re

import yaml

from phase5.canonical import canonical_bytes, digest_over, nfc
from phase5.material import material_fingerprint


class SourceDataError(ValueError):
    def __init__(self, code, message="invalid source data"):
        super().__init__(message)
        self.code = code


def text(value, *, required=False):
    if value is None:
        if required:
            raise SourceDataError("MISSING_REQUIRED_FIELD")
        return ""
    if not isinstance(value, str):
        raise SourceDataError("MALFORMED_RECORD", "source string cannot be coerced")
    try:
        value.encode("utf-8", "strict")
    except UnicodeError as exc:
        raise SourceDataError("MALFORMED_RECORD", "source string has invalid Unicode") from exc
    if required and not value:
        raise SourceDataError("MISSING_REQUIRED_FIELD")
    return value


def array(value):
    if value is None:
        return []
    if not isinstance(value, list):
        raise SourceDataError("MALFORMED_RECORD", "source field must be an array")
    return value


def record(value):
    if not isinstance(value, dict):
        raise SourceDataError("MALFORMED_RECORD", "source record must be a mapping")
    return value


def string_items(value):
    items = array(value)
    if any(not isinstance(item, str) for item in items):
        raise SourceDataError("MALFORMED_RECORD", "source list items must be strings")
    return [text(item) for item in items]


def revision(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{40}", value):
        raise SourceDataError("MALFORMED_RECORD", "complete source profile needs a full verified commit")
    return value


def projection_date(value):
    if not isinstance(value, str):
        raise SourceDataError("MALFORMED_RECORD", "explicit projection date is required")
    try:
        parsed = datetime.date.fromisoformat(value)
    except ValueError as exc:
        raise SourceDataError("MALFORMED_RECORD", "projection date must be ISO YYYY-MM-DD") from exc
    if parsed.isoformat() != value:
        raise SourceDataError("MALFORMED_RECORD", "projection date must be canonical ISO")
    return value


def parse_document(raw_text, *, frontmatter=False):
    raw_text = text(raw_text)
    chunk = raw_text
    if frontmatter:
        lines = raw_text.splitlines(keepends=True)
        first = next((i for i, line in enumerate(lines) if line.strip()), None)
        if first is not None and lines[first].strip() == "---":
            end = next((i for i in range(first + 1, len(lines)) if lines[i].strip() == "---"), None)
            if end is None:
                raise SourceDataError("PARSE_ERROR", "unterminated YAML frontmatter")
            chunk = "".join(lines[first + 1:end])
    try:
        document = yaml.safe_load(chunk)
    except (yaml.YAMLError, ValueError, RecursionError) as exc:
        raise SourceDataError("PARSE_ERROR") from exc
    if document is None:
        raise SourceDataError("EMPTY_DOCUMENT")
    if not isinstance(document, dict):
        raise SourceDataError("NON_DICT_DOCUMENT")
    return document


def read_document(path, *, frontmatter=False):
    try:
        raw = path.read_text(encoding="utf-8", errors="strict")
    except UnicodeError as exc:
        raise SourceDataError("INVALID_ENCODING") from exc
    except OSError as exc:
        raise SourceDataError("IO_ERROR") from exc
    return parse_document(raw, frontmatter=frontmatter), raw


def json_detail(value, _active=None):
    """Deterministic complete YAML-safe value represented by canonical JSON.

    Lists preserve source order and multiplicity. NFC dictionary keys sort in
    CORE canonical bytes; NFC key collisions fail. Tagged scalar wrappers are
    unambiguous because source mappings containing the reserved tag key are
    themselves wrapped as mappings. Original YAML remains the raw authority.
    """
    active = set() if _active is None else _active
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, str):
        return nfc(text(value))
    if isinstance(value, float):
        return {"$yaml_type": "float", "value": repr(value)}
    if isinstance(value, datetime.datetime):
        return {"$yaml_type": "timestamp", "value": value.isoformat()}
    if isinstance(value, datetime.date):
        return {"$yaml_type": "date", "value": value.isoformat()}
    if isinstance(value, bytes):
        return {"$yaml_type": "binary", "value": base64.b64encode(value).decode("ascii")}
    if not isinstance(value, (dict, list, set)):
        raise SourceDataError("MALFORMED_RECORD", "unsupported source detail type")
    identity = id(value)
    if identity in active:
        raise SourceDataError("MALFORMED_RECORD", "cyclic source alias")
    active.add(identity)
    try:
        if isinstance(value, list):
            return [json_detail(item, active) for item in value]
        if isinstance(value, set):
            items = [json_detail(item, active) for item in value]
            return {"$yaml_type": "set", "value": sorted(items, key=canonical_bytes)}
        result = {}
        for key, item in value.items():
            key = nfc(text(key, required=True))
            if key in result:
                raise SourceDataError("MALFORMED_RECORD", "duplicate NFC source detail key")
            result[key] = json_detail(item, active)
        if "$yaml_type" in result:
            return {"$yaml_type": "mapping", "entries": [[key, result[key]] for key in sorted(result)]}
        return result
    finally:
        active.remove(identity)


def raw_evidence(document, raw_text, file_name, *, frontmatter=False):
    if raw_text is None:
        raise SourceDataError("MALFORMED_RECORD", "original source text is required")
    parsed = parse_document(raw_text, frontmatter=frontmatter)
    if canonical_bytes(json_detail(parsed)) != canonical_bytes(json_detail(document)):
        raise SourceDataError("MALFORMED_RECORD", "parsed record does not match its raw evidence")
    return {"file": text(file_name, required=True), "document": text(raw_text)}


def entry_evidence_hash(entry):
    """Bind interpretation/provenance/raw evidence, excluding only date stamps.

    Independent pure preflight derives this before the public normalizer runs.
    Comparing it detects same-material emissions with altered claim confidence,
    missing raw evidence or changed source metadata. Clock stamps are not proof.
    """
    value = copy.deepcopy(entry.to_dict() if hasattr(entry, "to_dict") else entry)
    for block in value.get("source_data", {}).values():
        block.pop("last_synced", None)
    for source in value.get("sources", []):
        source.pop("last_synced", None)
    value.get("_meta", {}).pop("projected_at", None)
    return digest_over(canonical_bytes(value))


def preflight(raw, derive, *, frontmatter=False):
    """Account for every source file, without suppressing unknown values/errors.

    ``derive`` returns (Entry, unknown-attack-type strings). Actual public
    normalization repeats this same pure derivation over the immutable bytes.
    """
    rev = revision(raw.get("rev"))
    rejected, unmapped, entries = [], [], []
    files = list(raw.get("files", []))
    for path in files:
        name = path.name
        try:
            document, raw_text = read_document(path, frontmatter=frontmatter)
            entry, unknown = derive(document, file_name=name, revision=rev,
                                    on="1970-01-01", raw_text=raw_text)
            entries.append((name, nfc(entry.id), material_fingerprint(entry.to_dict()),
                            entry_evidence_hash(entry)))
            unmapped.extend({"name": name, "code": "UNKNOWN_ATTACK_TYPE", "value": value,
                             "suppressing": False} for value in unknown)
        except SourceDataError as exc:
            rejected.append({"name": name, "code": exc.code})
        except (ValueError, TypeError, KeyError, RecursionError) as exc:
            rejected.append({"name": name, "code": "MALFORMED_RECORD"})
    counts = Counter(row[1] for row in entries)
    duplicates = {identity for identity, count in counts.items() if count > 1}
    rejected.extend({"name": name, "code": "DUPLICATE_ID"}
                    for name, identity, _, _ in entries if identity in duplicates)
    entries = [row for row in entries if row[1] not in duplicates]
    retained_names = {row[0] for row in entries}
    unmapped = [row for row in unmapped if row["name"] in retained_names]
    return {"inputs_total": len(files), "parsed_ok": len(entries), "emitted": len(entries),
            "rejected": rejected, "unmapped": unmapped,
            "expected_emissions": {identity: fingerprint for _, identity, fingerprint, _ in sorted(entries)},
            "expected_evidence": {identity: fingerprint for _, identity, _, fingerprint in sorted(entries)},
            "diagnostics": sorted(rejected + unmapped,
                                  key=lambda row: (row["name"], row["code"], row.get("value", "")))}
