"""Canonical JSON contract — spec §3.

One bytes->bytes serializer. Every hashed or persisted Phase 5 CORE structure
goes through :func:`canonical_bytes`.

Normative rules implemented here:
  * UTF-8; every string (keys and values) NFC-normalized before sorting,
    comparison and hashing.
  * String order = lexicographic over Unicode scalar values (code points).
    Python compares ``str`` by code point, so ``sorted``/``sort_keys`` are
    conforming; UTF-16 code-unit order is not and is never used.
  * Object keys sorted by that order; duplicate NFC-normalized key => hard fail.
  * Escaping: the seven short escapes for ``" \\ \\n \\r \\t \\b \\f``; every other
    control character U+0000-U+001F as ``\\u00xx`` with lowercase hex; no other
    character escaped (non-ASCII emitted literally as UTF-8).
  * Integers only (``allow_nan=False``); booleans/null literal; nullable fields
    written explicitly as ``null``, never omitted.
  * Separators ``(",",":")``; ``ensure_ascii=False``.
  * Hash grammar: ``sha256:`` + exactly 64 lowercase hex.
  * Terminal newline belongs to the persisted ``state.json`` file only; hashed
    byte-strings carry none.
"""
import hashlib
import json
import re
import unicodedata

__all__ = [
    "CanonicalError",
    "nfc",
    "canonicalize",
    "canonical_bytes",
    "digest_over",
    "is_digest",
    "require_digest",
    "code_point_sorted",
    "DIGEST_RE",
    "GENESIS_LAST_OBSERVATION_HASH",
]

#: Matched with ``fullmatch``: ``re`` treats ``$`` as also matching before a
#: final newline, which would admit a digest with a trailing LF.
DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}")
GENESIS_LAST_OBSERVATION_HASH = "sha256:" + "0" * 64


class CanonicalError(ValueError):
    """Raised when a value cannot be canonicalized under §3.

    Canonicalization is fail-closed: it never repairs, coerces or drops input.
    """


def nfc(text: str) -> str:
    """NFC-normalize a string (§3)."""
    return unicodedata.normalize("NFC", text)


def code_point_sorted(values, *, dedupe: bool = False) -> list:
    """Sort strings by Unicode code point after NFC, optionally de-duplicating.

    Used for every list-valued field whose order is part of canonical bytes.
    """
    normalized = [nfc(v) for v in values]
    if dedupe:
        normalized = list(dict.fromkeys(normalized))
    return sorted(normalized)


def canonicalize(value):
    """Recursively NFC-normalize and validate a value for §3 serialization.

    Rejects floats (integers only), non-string keys, and duplicate keys that
    collide after NFC normalization. Returns a new structure; the input is not
    mutated.
    """
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):  # bool already handled above
        return value
    if isinstance(value, float):
        raise CanonicalError("floats are not permitted in canonical JSON (integers only)")
    if isinstance(value, str):
        return nfc(value)
    if isinstance(value, (list, tuple)):
        return [canonicalize(item) for item in value]
    if isinstance(value, dict):
        out = {}
        for raw_key, raw_val in value.items():
            if not isinstance(raw_key, str):
                raise CanonicalError(f"object keys must be strings, got {type(raw_key).__name__}")
            key = nfc(raw_key)
            if key in out:
                raise CanonicalError(f"duplicate NFC-normalized key: {key!r}")
            out[key] = canonicalize(raw_val)
        return out
    raise CanonicalError(f"unsupported type in canonical JSON: {type(value).__name__}")


def canonical_bytes(value) -> bytes:
    """Serialize ``value`` to the single normative canonical byte string (§3)."""
    return json.dumps(
        canonicalize(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def digest_over(data: bytes) -> str:
    """``sha256:<64 lowercase hex>`` over exactly the given bytes (§3)."""
    if not isinstance(data, (bytes, bytearray)):
        raise CanonicalError("digest_over expects bytes; canonicalize first")
    return "sha256:" + hashlib.sha256(data).hexdigest()


def is_digest(text) -> bool:
    """True iff ``text`` matches the §3 hash grammar exactly."""
    return isinstance(text, str) and DIGEST_RE.fullmatch(text) is not None


def require_digest(text, field: str) -> str:
    """Return ``text`` if it matches the hash grammar, else fail closed."""
    if not is_digest(text):
        raise CanonicalError(f"{field}: expected 'sha256:<64 lowercase hex>', got {text!r}")
    return text
