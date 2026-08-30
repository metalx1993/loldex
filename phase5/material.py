"""Material projection — spec §14, with the §3 command ordering rules.

``project_material_v1`` builds the exact omit-empty material object over which
the material fingerprint is computed. It is a pure function of the projected
entry and never consults non-material fields.
"""
from .canonical import CanonicalError, canonical_bytes, code_point_sorted, digest_over, nfc

__all__ = [
    "MATERIAL_SCALARS",
    "MATERIAL_ARRAYS",
    "MATERIAL_DETAILS",
    "canonical_command",
    "command_sort_key",
    "canonical_commands",
    "project_material_v1",
    "material_fingerprint",
]

#: §14 — scalar material fields.
MATERIAL_SCALARS = ("type", "platform", "name", "privilege_required")
#: §14 — array material fields; each sorted by §3 order and de-duplicated.
MATERIAL_ARRAYS = (
    "aliases",
    "phases",
    "capabilities",
    "attack_techniques",
    "preconditions",
    "references",
    "tags",
)
#: §14 — detail objects, included only when present, keys sorted by §3.
MATERIAL_DETAILS = ("technique_detail", "driver_detail")


def _is_empty(value) -> bool:
    """§14 omit-empty: a value in ``[], {}, "", None`` is omitted."""
    return value is None or value == [] or value == {} or value == ""


def canonical_command(command: dict) -> dict:
    """Canonicalize one projected command (§3 material/command ordering).

    ``placeholders`` is sorted by code point after NFC and de-duplicated; if the
    result is empty the field is omitted under the universal omit-empty rule, so
    ``{"template":"X","placeholders":[]}`` and ``{"template":"X"}`` become the
    same object. Only non-empty ``template``/``placeholders``/``comment`` survive.
    """
    out = {}
    template = command.get("template")
    if not _is_empty(template):
        out["template"] = nfc(template)
    placeholders = command.get("placeholders") or []
    placeholders = code_point_sorted(placeholders, dedupe=True)
    if placeholders:  # empty => omitted, never an exception to omit-empty
        out["placeholders"] = placeholders
    comment = command.get("comment")
    if not _is_empty(comment):
        out["comment"] = nfc(comment)
    return out


def command_sort_key(command: dict):
    """§3 command sort tuple, total and permutation-invariant.

    ``(template, tuple(placeholders_canonical), comment, canonical_bytes(command))``
    where an omitted ``comment`` sorts as ``""`` and omitted ``placeholders`` as
    the empty tuple. The final component is a total tie-breaker: two commands can
    only share a full sort key if their canonical bytes are identical, in which
    case they are the same command and their order is immaterial.
    """
    return (
        command.get("template", ""),
        tuple(command.get("placeholders", ())),
        command.get("comment", ""),
        canonical_bytes(command),
    )


def canonical_commands(commands) -> list:
    """Canonicalize then order a command list (§3)."""
    canonical = [canonical_command(c) for c in (commands or [])]
    canonical = [c for c in canonical if c]
    return sorted(canonical, key=command_sort_key)


def _normalized_detail(field: str, detail: dict) -> dict:
    """NFC-normalize a detail object's keys, hard-failing on a collision.

    Section 3 mandates a hard failure for duplicate NFC-normalized object keys.
    Normalizing into a fresh dict would silently drop one of two colliding keys
    before the canonical serializer could ever see them, so the check happens
    here, before the normalized object is constructed.
    """
    normalized = {}
    for raw_key in detail:
        if not isinstance(raw_key, str):
            raise CanonicalError(f"{field}: object keys must be strings")
        key = nfc(raw_key)
        if key in normalized:
            raise CanonicalError(f"{field}: duplicate NFC-normalized key: {key!r}")
        normalized[key] = detail[raw_key]
    return normalized


def project_material_v1(entry: dict) -> dict:
    """§14 — the exact material object for a projected entry.

    Excluded as non-material: ``id``, ``last_synced``, ``projected_at``,
    ``_meta.*``, ``source_data.*``, enrichment provenance, and ``sources``.
    """
    material = {}

    for key in MATERIAL_SCALARS:
        value = entry.get(key)
        if not _is_empty(value):
            material[key] = nfc(value) if isinstance(value, str) else value

    for key in MATERIAL_ARRAYS:
        values = code_point_sorted(entry.get(key) or [], dedupe=True)
        if values:
            material[key] = values

    commands = canonical_commands(entry.get("commands"))
    if commands:
        material["commands"] = commands

    opsec_in = entry.get("opsec") or {}
    opsec = {}
    for key in ("noise", "triggers"):
        value = opsec_in.get(key)
        if not _is_empty(value):
            opsec[key] = nfc(value) if isinstance(value, str) else value
    detection_refs = code_point_sorted(opsec_in.get("detection_refs") or [], dedupe=True)
    if detection_refs:
        opsec["detection_refs"] = detection_refs
    if opsec:
        material["opsec"] = opsec

    for key in MATERIAL_DETAILS:
        detail = entry.get(key)
        if not _is_empty(detail):
            material[key] = _normalized_detail(key, detail)

    return material


def material_fingerprint(entry: dict) -> str:
    """``sha256:<hex>`` over the §3 canonical bytes of the §14 material object."""
    return digest_over(canonical_bytes(project_material_v1(entry)))
