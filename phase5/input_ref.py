"""Canonical ``input_ref`` — spec section 6.2.1.

One exact function for all five sources; no source-specific exception. The
ratified Option-C GTFOBins form ``_gtfobins/<escaped-relative-path>#`` is
*generated* by this function rather than special-cased.

CP5.1 scope: this is a pure helper. Adapter integration is CP5.3 — nothing here
reads the filesystem, and no host-absolute spelling ever enters canonical bytes.
Platform path semantics are deliberately not used: the separator, the absolute
forms and the component rules are all defined by the specification.
"""
import re

from .canonical import nfc
from .vocabulary import SOURCE_UNIVERSE

__all__ = [
    "SOURCE_PREFIX",
    "ACQUISITION_ROOT",
    "PathInvalid",
    "FILE",
    "ROW",
    "canonical_input_ref",
    "invalid_path_ref",
    "normalized_ref_collision_groups",
]

#: Section 6.2.1 — literal acquisition root per source, relative to the verified
#: checkout root. Recorded for documentation; the host-absolute spelling of
#: ``checkout_root`` is never data and never enters canonical bytes.
ACQUISITION_ROOT = {
    "GTFOBins": "checkout_root/_gtfobins",
    "LOLBAS": "checkout_root/yml",
    "WADComs": "checkout_root/_wadcoms",
    "LOLAD": "checkout_root",
    "LOLDrivers": "checkout_root/yaml",
}

#: Section 6.2.1 — canonical source prefix. LOLAD's prefix is the empty string,
#: so its acquired file is the non-empty root-relative name ``index.html``; the
#: file itself is never treated as the root.
SOURCE_PREFIX = {
    "GTFOBins": "_gtfobins/",
    "LOLBAS": "yml/",
    "WADComs": "_wadcoms/",
    "LOLAD": "",
    "LOLDrivers": "yaml/",
}

#: A drive-letter form such as ``C:`` or ``C:/a`` is absolute and path-invalid.
_DRIVE_ABSOLUTE = re.compile(r"^[A-Za-z]:($|/)")

#: Locator for a file candidate (including a synthetic whole-document candidate).
FILE = ("FILE",)


def ROW(index):
    """Locator for a LOLAD row: 0-based index among candidate rows before truncation.

    Valid only for LOLAD; every other source has file candidates (section 6.2.2).
    """
    return ("ROW", index)


class PathInvalid(ValueError):
    """Raised for a path-invalid candidate (section 6.2.1).

    A path-invalid candidate has exactly one terminal disposition:
    ``MALFORMED_RECORD``, zero emissions, and the reserved
    :func:`invalid_path_ref` rejection reference.
    """


def _require_source(source: str) -> str:
    name = nfc(source)
    if name not in SOURCE_UNIVERSE:
        raise PathInvalid(f"unknown source {source!r}")
    return name


def canonical_input_ref(source: str, raw_name: str, locator=FILE) -> str:
    """Section 6.2.1 — the single canonical reference function.

    ``raw_name`` is the candidate expressed relative to that source's exact
    acquisition root. Supplying a host-absolute name does not authorize root
    stripping and is path-invalid.

    Raises :class:`PathInvalid` for absolute names, ``..`` components, names that
    normalize away to nothing, and unknown locators.
    """
    name = _require_source(source)
    if not isinstance(raw_name, str):
        raise PathInvalid("raw_name must be a string")

    # Step 2 — backslash to solidus, then NFC. Case is preserved, never folded.
    text = nfc(raw_name.replace("\u005c", "/"))
    if text.startswith("/") or _DRIVE_ABSOLUTE.match(text):
        raise PathInvalid(f"absolute path is not a candidate reference: {raw_name!r}")

    # Step 3 — drop empty and "." components; any ".." is invalid; something must remain.
    components = []
    for component in text.split("/"):
        if component == "" or component == ".":
            continue
        if component == "..":
            raise PathInvalid(f"'..' component is path-invalid: {raw_name!r}")
        components.append(component)
    if not components:
        raise PathInvalid(f"name normalizes to an empty path: {raw_name!r}")
    relative = nfc("/".join(components))

    # Step 4 — ordered, injective escaping over the complete path string.
    escaped = relative.replace("%", "%25").replace("#", "%23")

    # Step 5 — prefix plus locator suffix.
    canonical_path = SOURCE_PREFIX[name] + escaped
    if locator == FILE:
        return canonical_path + "#"
    if (
        isinstance(locator, tuple)
        and len(locator) == 2
        and locator[0] == "ROW"
        and isinstance(locator[1], int)
        and not isinstance(locator[1], bool)
        and locator[1] >= 0
    ):
        # Section 6.2.1/6.2.2: only LOLAD has row candidates; every other source
        # has file candidates, so ROW(n) is not a valid locator for them.
        if name != "LOLAD":
            raise PathInvalid(f"ROW locator is only valid for LOLAD, not {name}")
        return canonical_path + "#row=" + str(locator[1])
    raise PathInvalid(f"unknown locator {locator!r}")


def invalid_path_ref(source: str) -> str:
    """Section 6.2.1 reserved sentinel for a path-invalid candidate.

    Every valid path is non-empty, so this can never equal a valid reference.
    """
    return SOURCE_PREFIX[_require_source(source)] + "#invalid-path"


def normalized_ref_collision_groups(candidates):
    """Section 6.2.1 normalized-reference collision, fail closed.

    ``candidates`` is an iterable of ``(canonical_input_ref, candidate_key)``.
    Returns ``{ref: [candidate_key, ...]}`` for every group with ``N > 1``
    distinct candidates. All members of such a group are rejected with
    ``NORMALIZED_PATH_COLLISION``; none is parsed or emits; the group does not
    participate in duplicate-ID derivation. The result is a pure function of the
    candidate set and cannot be discovery-order dependent.
    """
    groups = {}
    for ref, key in candidates:
        groups.setdefault(ref, [])
        if key not in groups[ref]:
            groups[ref].append(key)
    return {ref: keys for ref, keys in groups.items() if len(keys) > 1}
