"""Pure transition engine — spec sections 5, 9, 10, 15.

``evaluate(committed_body, observation, arrival_token=None)`` is the whole of
CP5.2: a pure function from a committed state body plus one finalized canonical
observation to an admission outcome, an optional successor state and an optional
report.

It performs no I/O of any kind: no filesystem write, no network, no acquisition,
no adapter execution, no publication, no scheduler, no queue, no journal. It
never reads a clock — every value it needs comes from the observation.

CP5.1 primitives are reused, never reimplemented: canonical serialization and
digests (``phase5.canonical``), the vocabulary (``phase5.vocabulary``), the
ownership resolver (``phase5.ownership``) and the static validator
(``phase5.state``).
"""
import copy

from .canonical import (
    GENESIS_LAST_OBSERVATION_HASH,
    CanonicalError,
    canonical_bytes,
    canonicalize,
    code_point_sorted,
    digest_over,
    is_digest,
    nfc,
)
from .input_ref import (
    FILE,
    ROW,
    SOURCE_PREFIX,
    PathInvalid,
    canonical_input_ref,
    invalid_path_ref,
)
from .ownership import INVALID_PREFIX, canonical_prefix_owner, resolve_owner
from .state import StateInvalid, state_token, validate_body
from .vocabulary import (
    CORE_STATE_VERSION,
    IDENTITY_MODE,
    REPORT_VERSION,
    SOURCE_UNIVERSE,
    STALE_THRESHOLD,
    AggregateClass,
    Classification,
    IdentityMode,
    OwnerResolution,
    SourceStatus,
)

__all__ = [
    "Admission",
    "OwnerOutcome",
    "TransitionResult",
    "ObservationInvalid",
    "observation_hash",
    "evaluate",
]


class Admission:
    """Section 5.4 admission outcomes. Only APPLIED produces a report."""

    APPLIED = "APPLIED"
    IDEMPOTENT_NO_OP = "IDEMPOTENT_NO_OP"
    SAME_ID_DIFFERENT_HASH_CONFLICT = "SAME_ID_DIFFERENT_HASH_CONFLICT"
    STALE = "STALE"
    INVALID_SUCCESSOR = "INVALID_SUCCESSOR"
    PRECONDITION_MISMATCH = "PRECONDITION_MISMATCH"


class OwnerOutcome:
    """Section 9.4 per-owner outcomes."""

    PRESENT = "PRESENT"
    QUALIFYING_ABSENCE = "QUALIFYING_ABSENCE"
    HEALTH_HOLD = "HEALTH_HOLD"
    CONTINUITY_HOLD = "CONTINUITY_HOLD"
    CONFLICT = "CONFLICT"
    UNPROVABLE = "UNPROVABLE"


class ObservationInvalid(ValueError):
    """Raised for a HARD INVALID observation (sections 4, 5.3, 6.0.1).

    Validation stops before admission: no transition occurs and no report is
    produced.
    """


class TransitionResult:
    """The complete, side-effect-free outcome of one evaluation.

    ``next_body`` is ``None`` for every non-APPLIED admission, and ``report`` is
    ``None`` for every admission except APPLIED (section 5.4).
    """

    __slots__ = ("admission", "next_body", "report", "observation_hash")

    def __init__(self, admission, next_body=None, report=None, obs_hash=None):
        self.admission = admission
        self.next_body = next_body
        self.report = report
        self.observation_hash = obs_hash

    @property
    def mutated(self) -> bool:
        return self.next_body is not None

    def __repr__(self):  # pragma: no cover - diagnostic only
        return f"<TransitionResult {self.admission} mutated={self.mutated}>"


def observation_hash(observation) -> str:
    """Section 5.4 — ``sha256`` over the canonical bytes of the whole observation."""
    return digest_over(canonical_bytes(observation))


# --------------------------------------------------------------------------
# Observation validation (sections 4, 5.3, 6.0, 6.0.1, 6.1, 6.2.1, 7.2, 7.3, 8.4)
#
# Every rule below is *byte-local*: decidable from the delivered observation
# bytes alone. Nothing here acquires, parses upstream data or reaches CP5.3.
# Section 4 is explicit that "validation runs entirely before admission and
# transition", so ``evaluate`` runs this pass before any admission branch.
# --------------------------------------------------------------------------
_TOKEN_FIELDS = {
    "core_state_version",
    "last_observation_id",
    "last_observation_hash",
    "state_checksum",
}

_OBSERVATION_FIELDS = {"observation_id", "base_state", "results"}

#: Section 6.0 — the complete AdapterResult field set. No undeclared fields.
_RESULT_FIELDS = {
    "source",
    "acquired_ok",
    "resolved_revision",
    "status",
    "primary_reason",
    "inputs_total",
    "parsed_ok",
    "rejected",
    "unmapped",
    "duplicate_ids",
    "emitted_entries",
}

_EMITTED_FIELDS = {"material_fingerprint", "owner_evidence", "upstream_identity"}
_EVIDENCE_FIELDS = {"source_data_projects", "declared_sources", "id_prefix"}
_IDENTITY_FIELDS = {"kind", "value"}

#: Section 7.2 precedence: ``reason -> (rank, status)``. Rank 1 wins.
_REASON_RANK = {
    "ACQUISITION_FAILED": (1, SourceStatus.FAILED),
    "EMPTY_INPUT_SET": (2, SourceStatus.FAILED),
    "INVALID_ENCODING": (3, SourceStatus.FAILED),
    "IO_ERROR": (4, SourceStatus.FAILED),
    "PARSE_ERROR": (5, SourceStatus.FAILED),
    "EMPTY_DOCUMENT": (6, SourceStatus.FAILED),
    "NON_DICT_DOCUMENT": (7, SourceStatus.FAILED),
    "UNEXPECTED_EXCEPTION": (8, SourceStatus.FAILED),
    "NORMALIZED_PATH_COLLISION": (9, SourceStatus.FAILED),
    "DUPLICATE_ID": (10, SourceStatus.FAILED),
    "MISSING_REQUIRED_FIELD": (11, SourceStatus.PARTIAL),
    "MALFORMED_RECORD": (12, SourceStatus.PARTIAL),
    "SUPPRESSING_UNMAPPED": (13, SourceStatus.PARTIAL),
}

#: Section 7.2a — source-level, zero-candidate only; never a ``rejected`` code.
_SOURCE_LEVEL_REASONS = frozenset({"ACQUISITION_FAILED", "EMPTY_INPUT_SET"})

#: Section 7.2b — the complete candidate rejection enum.
_CANDIDATE_REJECT_ENUM = frozenset(
    set(_REASON_RANK) - _SOURCE_LEVEL_REASONS - {"SUPPRESSING_UNMAPPED"}
)

#: Section 7.3 — unmapped code to its exact ``suppressing`` bit.
_UNMAPPED_SUPPRESSING = {
    "UNKNOWN_FUNCTION": True,
    "UNKNOWN_CATEGORY": True,
    "UNKNOWN_ATTACK_TYPE": False,
    "UNKNOWN_PRIVILEGE": False,
    "UNKNOWN_CONTEXT": False,
    "SUBSET_TRUNCATED": True,
    "EMPTY_CODE_CONTEXT": False,
}

_HEX40 = frozenset("0123456789abcdef")


def _fail(message):
    raise ObservationInvalid(message)


def _exact_fields(obj, allowed, what):
    if not isinstance(obj, dict):
        _fail(f"{what} must be an object")
    if set(obj) != allowed:
        extra = sorted(set(obj) - allowed)
        missing = sorted(allowed - set(obj))
        _fail(f"{what}: undeclared fields {extra}, missing {missing}")


def _is_nonneg_int(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _decode_ref_escape(escaped, what):
    """Invert the §6.2.1 step-4 escaping (``%``→``%25`` then ``#``→``%23``).

    Because ``%`` is escaped first, every ``%`` in a conforming escaped path
    starts exactly one of ``%25`` or ``%23``; anything else is not a §6.2.1
    output.
    """
    out = []
    i = 0
    while i < len(escaped):
        ch = escaped[i]
        if ch != "%":
            out.append(ch)
            i += 1
            continue
        token = escaped[i + 1 : i + 3]
        if token == "23":
            out.append("#")
        elif token == "25":
            out.append("%")
        else:
            _fail(f"{what}: not a canonical §6.2.1 escape sequence")
        i += 3
    return "".join(out)


def _validate_input_ref(source, ref, what, *, sentinel_code=None):
    """Section 4 — every candidate reference is the §6.2.1 output or the sentinel.

    Validation is a round trip through the frozen CP5.1 constructor: decode the
    escaping, rebuild with ``canonical_input_ref`` and require byte identity.
    That rejects un-normalized paths, wrong escaping, a ``ROW`` locator on a
    non-LOLAD source and any other non-canonical spelling without duplicating a
    second normalization here (§6.2.3 forbids a second one).

    The reserved sentinel is **context-sensitive**. It denotes a path-invalid
    candidate, and §6.2.1 gives such a candidate exactly one terminal
    disposition: a ``MALFORMED_RECORD`` rejection with zero emissions (§7.2c
    step 1 repeats it). §6.2.3 adds that path-invalid candidates "use only the
    reserved sentinel and cannot emit diagnostics". So the sentinel is legal
    only in ``rejected`` and only alongside ``MALFORMED_RECORD``; it is never
    legal in ``unmapped``. ``sentinel_code`` carries the accompanying rejection
    code, and is ``None`` for ``unmapped``.
    """
    if not isinstance(ref, str):
        _fail(f"{what}: input_ref must be a string")
    if ref == invalid_path_ref(source):
        if sentinel_code is None:
            _fail(
                f"{what}: the reserved invalid-path sentinel cannot appear in "
                f"unmapped — a path-invalid candidate emits no diagnostics (§6.2.3)"
            )
        if sentinel_code != "MALFORMED_RECORD":
            _fail(
                f"{what}: the reserved invalid-path sentinel requires code "
                f"'MALFORMED_RECORD', got {sentinel_code!r} (§6.2.1, §7.2c)"
            )
        return
    prefix = SOURCE_PREFIX[source]
    if not ref.startswith(prefix):
        _fail(f"{what}: input_ref must start with the {source} source prefix")
    rest = ref[len(prefix) :]
    if rest.count("#") != 1:
        _fail(f"{what}: input_ref needs exactly one locator separator")
    escaped_path, fragment = rest.split("#")
    if fragment == "":
        locator = FILE
    elif fragment.startswith("row="):
        digits = fragment[4:]
        if not digits or not digits.isdigit() or not digits.isascii():
            _fail(f"{what}: ROW locator needs a decimal index")
        if digits != str(int(digits)):
            _fail(f"{what}: ROW index must have no leading zero")
        locator = ROW(int(digits))
    else:
        _fail(f"{what}: unknown locator fragment {fragment!r}")
    raw = _decode_ref_escape(escaped_path, what)
    try:
        rebuilt = canonical_input_ref(source, raw, locator)
    except PathInvalid as exc:
        _fail(f"{what}: not a §6.2.1 canonical reference ({exc})")
    if rebuilt != ref:
        _fail(f"{what}: input_ref is not canonical (expected {rebuilt!r}, got {ref!r})")


def _validate_identity(source, entry_id, identity):
    """Sections 6.0.1 and 9.1 — identity shape is fixed by the emitter's mode."""
    mode, kind = IDENTITY_MODE[source]
    where = f"{source}/{entry_id}"
    if mode == IdentityMode.STABLE:
        _exact_fields(identity, _IDENTITY_FIELDS, f"{where}: upstream_identity")
        if identity["kind"] != kind:
            _fail(f"{where}: STABLE identity kind must be exactly {kind!r}")
        if not isinstance(identity["value"], str) or not identity["value"]:
            _fail(f"{where}: STABLE identity value must be a non-empty string")
    elif identity is not None:
        _fail(f"{where}: a NONE-mode emitter must emit a null upstream_identity")


def _validate_emitted_entry(source, entry_id, payload):
    """Sections 6.0/6.0.1/8.2 — the exact emitted-entry shape."""
    where = f"{source}/{entry_id}"
    if not isinstance(entry_id, str) or not entry_id:
        _fail(f"{source}: emitted entry ids must be non-empty strings")
    # §8.1: an id without "/", with an empty prefix or with an unmapped prefix
    # is hard-invalid.
    if canonical_prefix_owner(entry_id) == INVALID_PREFIX:
        _fail(f"{where}: entry id has no valid §8.1 prefix owner")
    _exact_fields(payload, _EMITTED_FIELDS, f"{where}: emitted entry")

    # §6.0 cross-field: every emitted entry in every status has a valid,
    # non-null material fingerprint.
    if not is_digest(payload["material_fingerprint"]):
        _fail(f"{where}: material_fingerprint must be 'sha256:'+64 lowercase hex")

    _exact_fields(payload["owner_evidence"], _EVIDENCE_FIELDS, f"{where}: owner_evidence")
    _validate_identity(source, entry_id, payload["upstream_identity"])

    # §8.2/§8.3 evidence semantics (SU membership, canonical arrays, id_prefix)
    # are the frozen resolver's; a HARD_INVALID verdict is hard-invalid here.
    resolution, _ = resolve_owner(entry_id, payload["owner_evidence"])
    if resolution == OwnerResolution.HARD_INVALID:
        _fail(f"{where}: owner_evidence is hard-invalid under §8.3")


def _derived_primary_reason(rejected_codes, has_suppressing):
    """Section 7.2 — lowest-ranked present candidate/derived reason, or NONE."""
    present = set(rejected_codes)
    if has_suppressing:
        present.add("SUPPRESSING_UNMAPPED")
    if not present:
        return "NONE"
    return min(present, key=lambda code: _REASON_RANK[code][0])


def _validate_result(result):
    """Sections 6.0, 6.1, 7.2, 7.2a-d, 7.3 for one AdapterResult."""
    if not isinstance(result, dict):
        _fail("every result must be an object")
    source = result.get("source")
    if not isinstance(source, str) or source not in SOURCE_UNIVERSE:
        _fail(f"result source must be a SOURCE_UNIVERSE member, got {source!r}")
    _exact_fields(result, _RESULT_FIELDS, f"{source}: AdapterResult")

    status = result["status"]
    if status not in (
        SourceStatus.OK,
        SourceStatus.PARTIAL,
        SourceStatus.FAILED,
        SourceStatus.UNKNOWN,
    ):
        _fail(f"{source}: bad status {status!r}")

    reason = result["primary_reason"]
    if not isinstance(reason, str) or (
        reason not in _REASON_RANK and reason not in ("NONE", "NOT_RUN")
    ):
        _fail(f"{source}: bad primary_reason {reason!r}")

    acquired = result["acquired_ok"]
    revision = result["resolved_revision"]
    if not isinstance(acquired, bool):
        _fail(f"{source}: acquired_ok must be boolean")
    # §4/§6.0 biconditional.
    if acquired:
        if not (
            isinstance(revision, str)
            and len(revision) == 40
            and all(c in _HEX40 for c in revision)
        ):
            _fail(f"{source}: acquired_ok requires exactly 40 lowercase hex")
    elif revision is not None:
        _fail(f"{source}: not acquired requires resolved_revision null")

    for field in ("inputs_total", "parsed_ok"):
        if not _is_nonneg_int(result[field]):
            _fail(f"{source}: {field} must be a non-negative integer")

    rejected = result["rejected"]
    unmapped = result["unmapped"]
    duplicate_ids = result["duplicate_ids"]
    emitted = result["emitted_entries"]
    for field, value in (
        ("rejected", rejected),
        ("unmapped", unmapped),
        ("duplicate_ids", duplicate_ids),
    ):
        if not isinstance(value, list):
            _fail(f"{source}: {field} must be an array")
    if not isinstance(emitted, dict):
        _fail(f"{source}: emitted_entries must be an object")

    # §6.0/§7.1 count equation.
    if result["inputs_total"] != result["parsed_ok"] + len(rejected):
        _fail(f"{source}: inputs_total != parsed_ok + len(rejected)")

    # --- rejected: exact element shape, enum, canonical order (§6.0/§7.2b) ---
    for element in rejected:
        _exact_fields(element, {"input_ref", "code"}, f"{source}: rejected element")
        code = element["code"]
        if code not in _CANDIDATE_REJECT_ENUM:
            # §7.2a: source-level values MUST NOT occur in rejected[].code.
            _fail(f"{source}: {code!r} is not a CANDIDATE_REJECT_ENUM member")
        _validate_input_ref(
            source, element["input_ref"], f"{source}: rejected", sentinel_code=code
        )
    keys = [(e["input_ref"], e["code"]) for e in rejected]
    if keys != sorted(keys):
        _fail(f"{source}: rejected must be ordered by (input_ref, code)")

    # --- unmapped: exact element shape, enum, exact suppressing bit (§7.3) ---
    for element in unmapped:
        _exact_fields(
            element, {"input_ref", "code", "suppressing"}, f"{source}: unmapped element"
        )
        code = element["code"]
        if code not in _UNMAPPED_SUPPRESSING:
            _fail(f"{source}: {code!r} is not an UNMAPPED_ENUM member")
        if element["suppressing"] is not _UNMAPPED_SUPPRESSING[code]:
            _fail(
                f"{source}: {code} must carry suppressing="
                f"{_UNMAPPED_SUPPRESSING[code]} exactly (§7.3)"
            )
        _validate_input_ref(source, element["input_ref"], f"{source}: unmapped")
    keys = [(e["input_ref"], e["code"]) for e in unmapped]
    if keys != sorted(keys):
        _fail(f"{source}: unmapped must be ordered by (input_ref, code)")

    # --- duplicate_ids: NFC, code-point sorted, de-duplicated (§6.0/§7.2c) ---
    if any(not isinstance(i, str) for i in duplicate_ids):
        _fail(f"{source}: duplicate_ids must be strings")
    if [nfc(i) for i in duplicate_ids] != duplicate_ids:
        _fail(f"{source}: duplicate_ids must be NFC-normalized")
    if duplicate_ids != code_point_sorted(duplicate_ids, dedupe=True):
        _fail(f"{source}: duplicate_ids must be sorted and de-duplicated")

    # --- emitted entries (§6.0.1) --------------------------------------
    for entry_id, payload in emitted.items():
        _validate_emitted_entry(source, entry_id, payload)

    # --- NOT_RUN (§6.1) is exclusive and exactly shaped ------------------
    if (status == SourceStatus.UNKNOWN) != (reason == "NOT_RUN"):
        _fail(f"{source}: status 'unknown' and primary_reason 'NOT_RUN' are biconditional")
    if reason == "NOT_RUN":
        if (
            acquired
            or revision is not None
            or result["inputs_total"] != 0
            or result["parsed_ok"] != 0
            or rejected
            or unmapped
            or duplicate_ids
            or emitted
        ):
            _fail(f"{source}: NOT_RUN must be exactly the §6.1 shape")
        return

    # --- §7.2a source-level results are exclusive and zero-candidate -----
    if reason in _SOURCE_LEVEL_REASONS:
        if (
            result["inputs_total"] != 0
            or result["parsed_ok"] != 0
            or rejected
            or unmapped
            or duplicate_ids
            or emitted
        ):
            _fail(f"{source}: {reason} must have zero candidates, diagnostics and emissions")
        if reason == "ACQUISITION_FAILED" and (acquired or revision is not None):
            _fail(f"{source}: ACQUISITION_FAILED requires acquired_ok:false and null revision")
        if reason == "EMPTY_INPUT_SET" and not acquired:
            _fail(f"{source}: EMPTY_INPUT_SET is acquired and must carry its revision")
    else:
        # §7.2a: ACQUISITION_FAILED is the only run result other than NOT_RUN
        # with acquired_ok:false.
        if not acquired:
            _fail(f"{source}: acquired_ok:false requires NOT_RUN or ACQUISITION_FAILED")
        # An acquired source whose enumeration produced zero candidates is
        # EMPTY_INPUT_SET by §7.2a rank 2 — never an 'ok' zero-candidate result.
        if result["inputs_total"] == 0:
            _fail(f"{source}: acquired with zero candidates must be EMPTY_INPUT_SET")
        # §7.2 derivation: primary_reason is the lowest-ranked present reason.
        expected = _derived_primary_reason(
            [e["code"] for e in rejected],
            any(e["suppressing"] for e in unmapped),
        )
        if reason != expected:
            _fail(
                f"{source}: primary_reason must be the §7.2 lowest-ranked present "
                f"reason {expected!r}, got {reason!r}"
            )

    # --- status is derived from primary_reason (§7.2 biconditional) ------
    expected_status = SourceStatus.OK if reason == "NONE" else _REASON_RANK[reason][1]
    if status != expected_status:
        _fail(f"{source}: {reason} requires status {expected_status!r}, got {status!r}")

    # --- §7.2c/§7.2d emission consistency --------------------------------
    if result["parsed_ok"] == 0 and emitted:
        _fail(f"{source}: no candidate is parsed_ok, so emitted_entries must be empty")
    has_duplicate_rejection = any(e["code"] == "DUPLICATE_ID" for e in rejected)
    if has_duplicate_rejection != bool(duplicate_ids):
        _fail(f"{source}: DUPLICATE_ID rejections and duplicate_ids must accompany each other")
    colliding = set(duplicate_ids) & {nfc(i) for i in emitted}
    if colliding:
        _fail(f"{source}: a colliding id never emits ({sorted(colliding)})")


def _validate_emitter_membership(results_by_source):
    """Section 8.4 — a RESOLVED owner set must contain every emitter source.

    Copies of one id are collected across results; byte-identical evidence
    resolves once. If the resolution is AMBIGUOUS, §8.4 does not evaluate
    membership at all. If it is RESOLVED and some emitter is outside the set,
    the whole observation is hard-invalid.
    """
    emitters = {}
    evidence_by_id = {}
    for source in sorted(results_by_source):
        for entry_id, payload in results_by_source[source]["emitted_entries"].items():
            emitters.setdefault(entry_id, []).append(source)
            evidence_by_id.setdefault(entry_id, []).append(payload["owner_evidence"])

    for entry_id in sorted(emitters):
        evidences = evidence_by_id[entry_id]
        first = canonical_bytes(evidences[0])
        if any(canonical_bytes(e) != first for e in evidences[1:]):
            continue  # AMBIGUOUS: membership is not evaluated (§8.4)
        resolution, owners = resolve_owner(entry_id, evidences[0])
        if resolution == OwnerResolution.HARD_INVALID:
            _fail(f"{entry_id}: ownership is hard-invalid")
        if resolution != OwnerResolution.RESOLVED:
            continue
        outside = sorted(set(emitters[entry_id]) - set(owners))
        if outside:
            _fail(
                f"{entry_id}: emitter(s) {outside} are outside the resolved owner "
                f"set {sorted(owners)} (§8.4)"
            )


def _validate_observation(observation):
    """Sections 4/5.3 — complete byte-local validation, before any admission."""
    _exact_fields(observation, _OBSERVATION_FIELDS, "observation")

    obs_id = observation["observation_id"]
    if not _is_nonneg_int(obs_id):
        _fail("observation_id must be a non-negative integer")

    base = observation["base_state"]
    _exact_fields(base, _TOKEN_FIELDS, "base_state")
    if base["core_state_version"] != CORE_STATE_VERSION:
        _fail(f"base_state.core_state_version must be {CORE_STATE_VERSION}")
    if not _is_nonneg_int(base["last_observation_id"]):
        _fail("base_state.last_observation_id must be a non-negative integer")
    for field in ("last_observation_hash", "state_checksum"):
        if not is_digest(base[field]):
            _fail(f"base_state.{field}: bad digest grammar {base[field]!r}")
    if (
        base["last_observation_id"] == 0
        and base["last_observation_hash"] != GENESIS_LAST_OBSERVATION_HASH
    ):
        _fail("a genesis base token requires the all-zero last_observation_hash")

    results = observation["results"]
    if not isinstance(results, list):
        _fail("results must be an array")
    sources = [r.get("source") if isinstance(r, dict) else None for r in results]
    if any(s not in SOURCE_UNIVERSE for s in sources):
        _fail("every result source must be in SOURCE_UNIVERSE")
    if len(set(sources)) != len(sources):
        _fail("duplicate AdapterResult source")
    if set(sources) != set(SOURCE_UNIVERSE):
        missing = sorted(set(SOURCE_UNIVERSE) - set(sources))
        _fail(f"missing AdapterResult for {missing}")
    # Section 3 array order: ``results`` is sorted by ``source`` in the canonical
    # form. A differently ordered array is a different byte string and therefore a
    # different observation hash, so a non-canonical order is rejected here rather
    # than silently re-sorted.
    if sources != sorted(sources):
        _fail("results must be sorted by source (canonical array order)")

    for result in results:
        _validate_result(result)

    results_by_source = {r["source"]: r for r in results}
    _validate_emitter_membership(results_by_source)
    return obs_id, base, results_by_source

# --------------------------------------------------------------------------
# Ownership for one entry (section 8.4)
# --------------------------------------------------------------------------
def _entry_ownership(entry_id, results_by_source, persisted_entry):
    """Resolve the owner set for one entry (section 8.4).

    Returns ``(resolution, owners_or_None)``. Emitted copies must agree
    byte-for-byte on ``owner_evidence``; differing evidence is AMBIGUOUS.
    """
    evidences = []
    for source in sorted(results_by_source):
        emitted = results_by_source[source]["emitted_entries"]
        if entry_id in emitted:
            evidences.append(emitted[entry_id].get("owner_evidence"))

    if not evidences:
        if persisted_entry is None:
            return OwnerResolution.HARD_INVALID, None
        if persisted_entry["owner_ambiguous"]:
            return OwnerResolution.AMBIGUOUS, None
        return OwnerResolution.RESOLVED, frozenset(persisted_entry["owner_sources"])

    first = canonical_bytes(evidences[0])
    if any(canonical_bytes(e) != first for e in evidences[1:]):
        return OwnerResolution.AMBIGUOUS, None
    return resolve_owner(entry_id, evidences[0])


# --------------------------------------------------------------------------
# Per-owner outcome (sections 9.2 and 9.3)
# --------------------------------------------------------------------------
def _owner_outcome(entry_id, source, result, prior_evidence, observation_id):
    """Return ``(outcome, planned_update_or_None)`` for one owner."""
    mode, kind = IDENTITY_MODE[source]
    prior_identity = prior_evidence.get("upstream_identity") if prior_evidence else None
    present = result["status"] == SourceStatus.OK and entry_id in result["emitted_entries"]

    if not present:
        # Section 9.3 absent-entry partition.
        if result["status"] != SourceStatus.OK:
            return OwnerOutcome.HEALTH_HOLD, None
        if mode == IdentityMode.STABLE and prior_identity is not None:
            return OwnerOutcome.QUALIFYING_ABSENCE, None
        return OwnerOutcome.CONTINUITY_HOLD, None

    # Section 9.2 present-entry partition.
    payload = result["emitted_entries"][entry_id]
    observed_identity = payload.get("upstream_identity")
    observed_fp = payload.get("material_fingerprint")

    if mode == IdentityMode.NONE:
        # Row 5: prior null, observed null => PRESENT_UNKEYED.
        return OwnerOutcome.PRESENT, {
            "material_fingerprint": observed_fp,
            "last_reliable_observation_id": observation_id,
            "upstream_identity": None,
        }
    if prior_identity is None:
        # Row 1: FIRST_SIGHTING.
        return OwnerOutcome.PRESENT, {
            "material_fingerprint": observed_fp,
            "last_reliable_observation_id": observation_id,
            "upstream_identity": copy.deepcopy(observed_identity),
        }
    if prior_identity == observed_identity:
        # Row 2: PROVEN — stored identity unchanged.
        return OwnerOutcome.PRESENT, {
            "material_fingerprint": observed_fp,
            "last_reliable_observation_id": observation_id,
            "upstream_identity": copy.deepcopy(prior_identity),
        }
    # Row 3: CONFLICT — entry-level blocking HOLD, plans no update.
    return OwnerOutcome.CONFLICT, None


def _aggregate(outcomes, ambiguous):
    """Section 9.4 ordered aggregate. Computed before any evidence mutation."""
    if ambiguous:
        return AggregateClass.HOLD
    values = set(outcomes.values())
    if OwnerOutcome.CONFLICT in values or OwnerOutcome.UNPROVABLE in values:
        return AggregateClass.HOLD
    if OwnerOutcome.CONTINUITY_HOLD in values:
        return AggregateClass.HOLD
    if OwnerOutcome.PRESENT in values:
        return AggregateClass.PRESENT
    if outcomes and values == {OwnerOutcome.QUALIFYING_ABSENCE}:
        return AggregateClass.QUALIFYING_ABSENCE
    return AggregateClass.HOLD


def _empty_evidence(source):
    return {
        "source": source,
        "material_fingerprint": None,
        "last_reliable_observation_id": None,
        "upstream_identity": None,
    }


def _freshness(prior, aggregate_class):
    """Section 10 entry-level table. Returns ``(classification, initialized, streak)``."""
    if prior is None:
        if aggregate_class == AggregateClass.PRESENT:
            return Classification.ACTIVE, True, 0
        return None  # no record created (QUALIFYING_ABSENCE ignored; HOLD creates nothing)

    classification = prior["classification"]
    initialized = prior["initialized"]
    streak = prior["absence_streak"]

    if not initialized:
        if aggregate_class == AggregateClass.PRESENT:
            return Classification.ACTIVE, True, 0
        if aggregate_class == AggregateClass.QUALIFYING_ABSENCE:
            return Classification.NOT_OBSERVED, True, 1
        return classification, initialized, streak  # HOLD: unchanged

    if aggregate_class == AggregateClass.PRESENT:
        return Classification.ACTIVE, True, 0
    if aggregate_class == AggregateClass.HOLD:
        return classification, True, streak
    # QUALIFYING_ABSENCE
    if classification == Classification.ACTIVE:
        return Classification.NOT_OBSERVED, True, 1
    nxt = streak + 1
    if classification == Classification.STALE_CANDIDATE:
        return Classification.STALE_CANDIDATE, True, nxt
    return (
        Classification.STALE_CANDIDATE if nxt >= STALE_THRESHOLD else Classification.NOT_OBSERVED,
        True,
        nxt,
    )


def _changed(aggregate_class, present_owners, prior_by_source):
    """Section 15 R5-B2 — total OR over every PRESENT owner.

    ``aggregate_class != PRESENT`` short-circuits to ``False`` before any
    fingerprint comparison, keyed on the current aggregate class.
    """
    if aggregate_class != AggregateClass.PRESENT:
        return False
    for source, planned in present_owners.items():
        prior = prior_by_source.get(source)
        prior_fp = prior.get("material_fingerprint") if prior else None
        if prior_fp is not None and planned["material_fingerprint"] != prior_fp:
            return True
    return False


# --------------------------------------------------------------------------
# The transition (sections 8.5, 9.4, 10, 15)
# --------------------------------------------------------------------------
def _transition(committed_body, observation, obs_hash, results_by_source):
    observation_id = observation["observation_id"]
    prior_entries = {e["entry_id"]: e for e in committed_body["entries"]}

    emitted_ids = set()
    for result in results_by_source.values():
        emitted_ids.update(result["emitted_entries"])

    membership = sorted(set(prior_entries) | emitted_ids)

    next_entries = []
    report_rows = []

    for entry_id in membership:
        prior = prior_entries.get(entry_id)
        resolution, owners = _entry_ownership(entry_id, results_by_source, prior)

        if resolution == OwnerResolution.HARD_INVALID:
            raise ObservationInvalid(f"{entry_id}: ownership is hard-invalid")

        ambiguous = resolution == OwnerResolution.AMBIGUOUS
        if ambiguous:
            owner_set = frozenset(prior["owner_sources"]) if prior else frozenset()
        else:
            owner_set = owners

        prior_by_source = {}
        if prior:
            prior_by_source = {ev["source"]: ev for ev in prior["sources"]}

        outcomes = {}
        planned = {}
        if not ambiguous:
            for source in sorted(owner_set):
                outcome, plan = _owner_outcome(
                    entry_id,
                    source,
                    results_by_source[source],
                    prior_by_source.get(source),
                    observation_id,
                )
                outcomes[source] = outcome
                if outcome == OwnerOutcome.PRESENT:
                    planned[source] = plan

        aggregate_class = _aggregate(outcomes, ambiguous)
        changed = _changed(aggregate_class, planned, prior_by_source)

        # --- ambiguity policy (section 8.5) -------------------------------
        if ambiguous:
            if prior is None:
                entry = {
                    "entry_id": entry_id,
                    "classification": Classification.NOT_OBSERVED,
                    "initialized": True,
                    "absence_streak": 0,
                    "owner_ambiguous": True,
                    "owner_sources": [],
                    "sources": [],
                }
            else:
                entry = copy.deepcopy(prior)
                entry["owner_ambiguous"] = True
                entry["classification"] = Classification.NOT_OBSERVED
                entry["initialized"] = True
                entry["absence_streak"] = 0
            next_entries.append(entry)
            report_rows.append(
                {
                    "entry_id": entry_id,
                    "classification": entry["classification"],
                    "aggregate_class": AggregateClass.HOLD,
                    "changed": False,
                }
            )
            continue

        freshness = _freshness(prior, aggregate_class)

        if freshness is None:
            # Section 10: no record created. Section 15: report-only row is
            # normatively NOT_OBSERVED, never null.
            report_rows.append(
                {
                    "entry_id": entry_id,
                    "classification": Classification.NOT_OBSERVED,
                    "aggregate_class": aggregate_class,
                    "changed": False,
                }
            )
            continue

        classification, initialized, streak = freshness

        # --- membership reconciliation first (section 10) ------------------
        sources = []
        for source in sorted(owner_set):
            carried = prior_by_source.get(source)
            evidence = copy.deepcopy(carried) if carried else _empty_evidence(source)
            # --- then the aggregate-subordinate mutation gate (section 9.4) --
            if aggregate_class == AggregateClass.PRESENT and source in planned:
                evidence["material_fingerprint"] = planned[source]["material_fingerprint"]
                evidence["last_reliable_observation_id"] = planned[source][
                    "last_reliable_observation_id"
                ]
                evidence["upstream_identity"] = planned[source]["upstream_identity"]
            sources.append(evidence)

        next_entries.append(
            {
                "entry_id": entry_id,
                "classification": classification,
                "initialized": initialized,
                "absence_streak": streak,
                "owner_ambiguous": False,
                "owner_sources": sorted(owner_set),
                "sources": sources,
            }
        )
        report_rows.append(
            {
                "entry_id": entry_id,
                "classification": classification,
                "aggregate_class": aggregate_class,
                "changed": changed,
            }
        )

    next_entries.sort(key=lambda e: e["entry_id"])
    next_body = {
        "core_state_version": committed_body["core_state_version"],
        "entries": next_entries,
        # Section 10 generic applied-transition head assignments.
        "last_observation_hash": obs_hash,
        "last_observation_id": observation_id,
    }
    report = {
        "report_version": REPORT_VERSION,
        "observation_id": observation_id,
        "entries": sorted(report_rows, key=lambda r: r["entry_id"]),
    }
    return next_body, report


# --------------------------------------------------------------------------
# Admission (section 5.4)
# --------------------------------------------------------------------------
def evaluate(committed_body, observation, arrival_token=None):
    """Pure ``F(S, O) -> result``. No side effects, no clock, no I/O.

    ``arrival_token`` models the section 5.2 API-entry capture. When omitted it
    defaults to the committed state's own token, i.e. nothing changed between
    arrival and lock acquisition.

    The section 5.4 branch order is normative and must not be reordered: both
    same-ID branches precede the base comparison, so an exact retry after a
    successful commit returns IDEMPOTENT_NO_OP even though the observation still
    embeds its pre-commit base token (B7, sections 5.7 and 5.7.1).
    """
    # --- B1: bind semantics to canonical identity (sections 3, 4) --------
    # ``canonical_bytes`` already NFC-normalizes before hashing, so the
    # observation hash is a property of the canonical form. Every semantic
    # comparison below must therefore be made on that same canonical form, or
    # two observations with identical canonical bytes (and identical hashes)
    # could transition differently. ``canonicalize`` returns new structures and
    # never mutates its input, so the caller's objects stay untouched; a
    # duplicate NFC-normalized key is a §3 hard failure and is surfaced here as
    # a hard-invalid observation rather than escaping as a CanonicalError.
    try:
        committed_body = canonicalize(committed_body)
        observation = canonicalize(observation)
        arrival_token = None if arrival_token is None else canonicalize(arrival_token)
    except CanonicalError as exc:
        raise ObservationInvalid(f"input is not canonicalizable: {exc}") from exc

    validate_body(committed_body)
    obs_id, base, results_by_source = _validate_observation(observation)
    obs_hash = observation_hash(observation)

    committed_token = state_token(committed_body)
    arrival = committed_token if arrival_token is None else arrival_token

    def done(admission):
        return TransitionResult(admission, None, None, obs_hash)

    # --- arrival-time ---------------------------------------------------
    if obs_id == arrival["last_observation_id"]:
        return done(
            Admission.IDEMPOTENT_NO_OP
            if obs_hash == arrival["last_observation_hash"]
            else Admission.SAME_ID_DIFFERENT_HASH_CONFLICT
        )
    if obs_id < arrival["last_observation_id"]:
        return done(Admission.STALE)
    if obs_id != base["last_observation_id"] + 1:
        return done(Admission.INVALID_SUCCESSOR)
    if base != arrival:
        return done(Admission.PRECONDITION_MISMATCH)

    # --- locked ---------------------------------------------------------
    if obs_id == committed_token["last_observation_id"]:
        return done(
            Admission.IDEMPOTENT_NO_OP
            if obs_hash == committed_token["last_observation_hash"]
            else Admission.SAME_ID_DIFFERENT_HASH_CONFLICT
        )
    if obs_id < committed_token["last_observation_id"]:
        return done(Admission.STALE)
    if arrival != base or base != committed_token:
        return done(Admission.PRECONDITION_MISMATCH)

    # --- applied ---------------------------------------------------------
    next_body, report = _transition(committed_body, observation, obs_hash, results_by_source)
    try:
        validate_body(next_body)
    except StateInvalid as exc:  # pragma: no cover - guards against an engine defect
        raise StateInvalid(f"transition produced an invalid successor state: {exc}") from exc
    return TransitionResult(Admission.APPLIED, next_body, report, obs_hash)
