"""Persistent freshness state — model, envelope and static validator.

Spec §11 (validator), §12 (genesis constants), §13 (envelope bytes).

The validator is *static*: it decides solely from the bytes in front of it and
never infers unencoded history (e.g. "first-seen ambiguous"). It is fail-closed
and never repairs, coerces or normalizes an invalid state into a valid one.
"""
from .canonical import (
    GENESIS_LAST_OBSERVATION_HASH,
    canonical_bytes,
    code_point_sorted,
    digest_over,
    is_digest,
    nfc,
)
from .ownership import canonical_prefix_owner
from .vocabulary import (
    CORE_STATE_VERSION,
    STALE_THRESHOLD,
    SOURCE_UNIVERSE,
    Classification,
    EvidenceTuple,
    IDENTITY_MODE,
    IdentityMode,
)

__all__ = [
    "StateInvalid",
    "ENTRY_FIELDS",
    "EVIDENCE_FIELDS",
    "BODY_FIELDS",
    "classify_evidence_tuple",
    "validate_evidence",
    "validate_entry",
    "validate_body",
    "validate_envelope",
    "build_envelope",
    "serialize_state_file",
    "state_token",
]

ENTRY_FIELDS = frozenset(
    {
        "entry_id",
        "classification",
        "initialized",
        "absence_streak",
        "owner_ambiguous",
        "owner_sources",
        "sources",
    }
)
EVIDENCE_FIELDS = frozenset(
    {"source", "material_fingerprint", "last_reliable_observation_id", "upstream_identity"}
)
BODY_FIELDS = frozenset(
    {"core_state_version", "entries", "last_observation_hash", "last_observation_id"}
)


class StateInvalid(ValueError):
    """Raised when persisted state bytes violate §11. Fail-closed."""


def _require_exact_fields(obj, allowed, what):
    if not isinstance(obj, dict):
        raise StateInvalid(f"{what}: expected object, got {type(obj).__name__}")
    keys = set()
    for raw in obj:
        if not isinstance(raw, str):
            raise StateInvalid(f"{what}: non-string key")
        key = nfc(raw)
        if key in keys:
            raise StateInvalid(f"{what}: duplicate NFC-normalized key {key!r}")
        keys.add(key)
    missing = allowed - keys
    if missing:
        raise StateInvalid(f"{what}: missing required field(s) {sorted(missing)}")
    undeclared = keys - allowed
    if undeclared:
        raise StateInvalid(f"{what}: undeclared field(s) {sorted(undeclared)}")


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def classify_evidence_tuple(mode: str, kind, identity, fingerprint, reliable_id, last_observation_id):
    """§11.5 — name the legal tuple, or raise.

    ``(I, F, L)`` bits, per mode:
      STABLE: ``000`` EMPTY, ``111`` STABLE_RELIABLE, everything else REJECT.
      NONE:   ``000`` EMPTY, ``011`` UNKEYED_RELIABLE, everything else REJECT.

    ``L`` is valid only when ``1 <= L <= last_observation_id``; ``L=0`` is invalid
    because genesis creates only EMPTY and the first applied observation is 1.
    """
    i_bit = identity is not None
    f_bit = fingerprint is not None
    l_bit = reliable_id is not None

    if f_bit and not is_digest(fingerprint):
        raise StateInvalid(f"material_fingerprint: bad digest grammar {fingerprint!r}")
    if l_bit:
        if not _is_int(reliable_id):
            raise StateInvalid("last_reliable_observation_id: expected integer")
        if not (1 <= reliable_id <= last_observation_id):
            raise StateInvalid(
                f"last_reliable_observation_id {reliable_id} outside 1..{last_observation_id}"
            )
    if i_bit:
        if not isinstance(identity, dict) or set(identity) != {"kind", "value"}:
            raise StateInvalid("upstream_identity: expected exactly {kind, value}")
        if identity.get("kind") != kind:
            raise StateInvalid(
                f"upstream_identity.kind {identity.get('kind')!r} != required {kind!r}"
            )
        value = identity.get("value")
        if not isinstance(value, str) or not value:
            raise StateInvalid("upstream_identity.value: expected non-empty string")

    bits = (i_bit, f_bit, l_bit)
    if mode == IdentityMode.STABLE:
        if bits == (False, False, False):
            return EvidenceTuple.EMPTY
        if bits == (True, True, True):
            return EvidenceTuple.STABLE_RELIABLE
    else:  # NONE
        if bits == (False, False, False):
            return EvidenceTuple.EMPTY
        if bits == (False, True, True):
            return EvidenceTuple.UNKEYED_RELIABLE
    raise StateInvalid(
        f"illegal {mode} evidence tuple (I,F,L)="
        f"{''.join('1' if b else '0' for b in bits)}"
    )


def validate_evidence(evidence, last_observation_id) -> str:
    """Validate one persisted source-evidence record; return its tuple name."""
    _require_exact_fields(evidence, EVIDENCE_FIELDS, "source evidence")
    source = evidence["source"]
    if not isinstance(source, str) or nfc(source) not in SOURCE_UNIVERSE:
        raise StateInvalid(f"source {source!r} not in SOURCE_UNIVERSE")
    mode, kind = IDENTITY_MODE[nfc(source)]
    return classify_evidence_tuple(
        mode,
        kind,
        evidence["upstream_identity"],
        evidence["material_fingerprint"],
        evidence["last_reliable_observation_id"],
        last_observation_id,
    )


def validate_entry(entry, last_observation_id) -> None:
    """Validate one persisted entry against §11.3, §11.4 and §11.6."""
    _require_exact_fields(entry, ENTRY_FIELDS, "entry")

    entry_id = entry["entry_id"]
    if not isinstance(entry_id, str) or not entry_id:
        raise StateInvalid("entry_id: expected non-empty string")

    ambiguous = entry["owner_ambiguous"]
    initialized = entry["initialized"]
    classification = entry["classification"]
    streak = entry["absence_streak"]
    if not isinstance(ambiguous, bool) or not isinstance(initialized, bool):
        raise StateInvalid(f"{entry_id}: owner_ambiguous/initialized must be booleans")
    if not _is_int(streak) or streak < 0:
        raise StateInvalid(f"{entry_id}: absence_streak must be a non-negative integer")

    # §11.3 exact entry-state partition — valid iff exactly one row matches.
    rows = (
        ambiguous and initialized and classification == Classification.NOT_OBSERVED and streak == 0,
        (not ambiguous)
        and (not initialized)
        and classification == Classification.NOT_OBSERVED
        and streak == 0,
        (not ambiguous) and initialized and classification == Classification.ACTIVE and streak == 0,
        (not ambiguous)
        and initialized
        and classification == Classification.NOT_OBSERVED
        and 0 <= streak <= STALE_THRESHOLD - 1,
        (not ambiguous)
        and initialized
        and classification == Classification.STALE_CANDIDATE
        and streak >= STALE_THRESHOLD,
    )
    if sum(1 for matched in rows if matched) != 1:
        raise StateInvalid(
            f"{entry_id}: no unique §11.3 row for "
            f"(ambiguous={ambiguous}, initialized={initialized}, "
            f"classification={classification!r}, streak={streak})"
        )

    # §11.4 ownership/source membership.
    owner_sources = entry["owner_sources"]
    sources = entry["sources"]
    if not isinstance(owner_sources, list) or not isinstance(sources, list):
        raise StateInvalid(f"{entry_id}: owner_sources/sources must be arrays")
    if [nfc(o) for o in owner_sources] != code_point_sorted(owner_sources, dedupe=True):
        raise StateInvalid(f"{entry_id}: owner_sources not sorted/de-duplicated")
    if any(nfc(o) not in SOURCE_UNIVERSE for o in owner_sources):
        raise StateInvalid(f"{entry_id}: owner_sources contains a value outside SOURCE_UNIVERSE")

    source_names = [ev.get("source") if isinstance(ev, dict) else None for ev in sources]
    if any(not isinstance(s, str) for s in source_names):
        raise StateInvalid(f"{entry_id}: every source evidence needs a string source")
    if [nfc(s) for s in source_names] != code_point_sorted(source_names, dedupe=True):
        raise StateInvalid(f"{entry_id}: sources not sorted by source / de-duplicated")
    if {nfc(s) for s in source_names} != {nfc(o) for o in owner_sources}:
        raise StateInvalid(f"{entry_id}: set(sources[].source) != set(owner_sources)")

    tuples = [validate_evidence(ev, last_observation_id) for ev in sources]

    # §11.6 entry-level reachability invariants.
    if not ambiguous and not owner_sources:
        raise StateInvalid(f"{entry_id}: non-ambiguous entry needs a non-empty owner set")
    if not initialized and any(name != EvidenceTuple.EMPTY for name in tuples):
        raise StateInvalid(f"{entry_id}: initialized:false requires every tuple EMPTY")
    # (i) R7 hardening V1
    if initialized and last_observation_id < 1:
        raise StateInvalid(f"{entry_id}: initialized:true requires last_observation_id >= 1")
    # (ii) R7 hardening V2
    if streak > last_observation_id:
        raise StateInvalid(
            f"{entry_id}: absence_streak {streak} > last_observation_id {last_observation_id}"
        )
    # (iii) R7 hardening V3 — ambiguous entries are exempt (§11.6).
    if not ambiguous:
        owner = canonical_prefix_owner(entry_id)
        if owner not in {nfc(o) for o in owner_sources}:
            raise StateInvalid(
                f"{entry_id}: non-ambiguous entry omits its canonical prefix owner {owner!r}"
            )


def validate_body(body) -> None:
    """Validate a state body against §11.2 plus every entry rule."""
    _require_exact_fields(body, BODY_FIELDS, "body")
    if body["core_state_version"] != CORE_STATE_VERSION:
        raise StateInvalid(f"core_state_version must be {CORE_STATE_VERSION}")

    last_id = body["last_observation_id"]
    if not _is_int(last_id) or last_id < 0:
        raise StateInvalid("last_observation_id must be a non-negative integer")
    last_hash = body["last_observation_hash"]
    if not is_digest(last_hash):
        raise StateInvalid(f"last_observation_hash: bad digest grammar {last_hash!r}")
    if last_id == 0 and last_hash != GENESIS_LAST_OBSERVATION_HASH:
        raise StateInvalid("virtual genesis requires the all-zero last_observation_hash")

    entries = body["entries"]
    if not isinstance(entries, list):
        raise StateInvalid("entries must be an array")
    ids = [e.get("entry_id") if isinstance(e, dict) else None for e in entries]
    if any(not isinstance(i, str) for i in ids):
        raise StateInvalid("every entry needs a string entry_id")
    if len(set(nfc(i) for i in ids)) != len(ids):
        raise StateInvalid("duplicate entry_id in body")
    if [nfc(i) for i in ids] != sorted(nfc(i) for i in ids):
        raise StateInvalid("entries not sorted by entry_id")

    for entry in entries:
        validate_entry(entry, last_id)


def build_envelope(body) -> dict:
    """§11.1/§13 — ``{body, checksum}`` with the checksum over canonical body bytes."""
    return {"body": body, "checksum": digest_over(canonical_bytes(body))}


def serialize_state_file(body) -> bytes:
    """Persisted ``state.json`` bytes: canonical envelope plus exactly one newline."""
    return canonical_bytes(build_envelope(body)) + b"\n"


def validate_envelope(file_bytes: bytes) -> dict:
    """Validate persisted file bytes end to end (§11.1); return the body.

    Requires exact byte identity with ``canonical(envelope) + "\\n"``, so a
    semantically equivalent but non-canonical file is rejected.
    """
    if not isinstance(file_bytes, (bytes, bytearray)):
        raise StateInvalid("state file must be bytes")
    if not file_bytes.endswith(b"\n"):
        raise StateInvalid("state file must end with exactly one newline")
    import json as _json

    try:
        envelope = _json.loads(file_bytes.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - fail closed on any decode error
        raise StateInvalid(f"state file is not valid UTF-8 JSON: {exc}") from exc

    _require_exact_fields(envelope, {"body", "checksum"}, "envelope")
    body = envelope["body"]
    validate_body(body)

    expected = digest_over(canonical_bytes(body))
    if envelope["checksum"] != expected:
        raise StateInvalid("checksum does not match canonical body bytes")
    if file_bytes != serialize_state_file(body):
        raise StateInvalid("state file bytes are not canonical")
    return body


def state_token(body) -> dict:
    """§5/§12 — the state token derived from a body."""
    return {
        "core_state_version": body["core_state_version"],
        "last_observation_hash": body["last_observation_hash"],
        "last_observation_id": body["last_observation_id"],
        "state_checksum": digest_over(canonical_bytes(body)),
    }
