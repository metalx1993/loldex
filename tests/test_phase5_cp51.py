"""Phase 5 CORE — CP5.1 tests.

Scope: the deterministic substrate only — canonical JSON (section 3), digest and
token grammar, vocabulary (sections 4/8/9), material projection (section 14), the
static state validator (section 11) and virtual genesis (section 12).

The frozen specification ``docs/phase5-core-design-v6-4.md`` is the oracle.
Golden assertions are on exact bytes AND exact digests, never on "equivalent
JSON". No network access. No transition engine (that is CP5.2).
"""
import itertools
import pathlib
import random
import sys

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from phase5 import genesis as gen  # noqa: E402
from phase5.canonical import (  # noqa: E402
    GENESIS_LAST_OBSERVATION_HASH,
    CanonicalError,
    canonical_bytes,
    code_point_sorted,
    digest_over,
    is_digest,
    require_digest,
)
from phase5.material import (  # noqa: E402
    canonical_command,
    canonical_commands,
    material_fingerprint,
    project_material_v1,
)
from phase5.input_ref import (  # noqa: E402
    FILE,
    ROW,
    SOURCE_PREFIX,
    PathInvalid,
    canonical_input_ref,
    invalid_path_ref,
    normalized_ref_collision_groups,
)
from phase5.ownership import INVALID_PREFIX, canonical_prefix_owner, resolve_owner  # noqa: E402
from phase5.state import (  # noqa: E402
    StateInvalid,
    build_envelope,
    classify_evidence_tuple,
    serialize_state_file,
    state_token,
    validate_body,
    validate_entry,
    validate_envelope,
)
from phase5.vocabulary import (  # noqa: E402
    CORE_STATE_VERSION,
    IDENTITY_MODE,
    PREFIX_OWNER,
    SOURCE_UNIVERSE,
    Classification,
    EvidenceTuple,
    IdentityMode,
    OwnerResolution,
)
from tests import phase5_goldens as G  # noqa: E402

SPEC = ROOT / "docs" / "phase5-core-design-v6-4.md"
G1_ENTRY = ROOT / "data" / "entries" / "linux" / "gtfobins__diff__file-read__unprivileged.yaml"

G1_DIGEST = "sha256:8e4efac566970088763bfd9f7447b7fdfecc55d61764cfd422f814582ddfccae"
G2_DIGEST = "sha256:8b687db6f7882e233e2df28f5c55af20300278c5fddb566140f907b9f4a56f42"
G3_DIGEST = "sha256:286048e4d67b0049ae052c7dd5c3fe1c9a95e1c8f63a4625bf21f649f2dece09"
G4_DIGEST = "sha256:3bdb5a7c1cf3696c2cd87d587db94501eca7704645be8a8d76a8e98df7be2887"
G5_DIGEST = "sha256:f021b2e37f5fc90a9701ef630f9bb68a6c9e4586e5070594bd2251a09afbd19b"
G6_DIGEST = "sha256:09bf118eab6255fbb474263f0491e19ec4234e504dfb91aae3175adb73caacc3"
PLACEHOLDER_EMPTY_DIGEST = "sha256:6ca27dacaf3439158765ea9c63b78acf011947c321c69956b9617029aeadff0d"
PLACEHOLDER_NONEMPTY_DIGEST = "sha256:9b85e1a0276222ae7e4eb1f135a3da2f786f5dbe7c7c4d15bd277d6f06ea4552"
FIXTURE_GENESIS_DIGEST = "sha256:a836d0b4779c6f1ca293acb0fcae9617d594e2753328ebb6d5a9c01214b70d40"
PRODUCTION_GENESIS_DIGEST = "sha256:8d78d81b92d5fbaea2972fca158b4a15424301d5ed7e111c601bf0f060415ca9"
PRODUCTION_GENESIS_ENTRIES = 3086
PRODUCTION_GENESIS_BYTES = 899886

PUA = ""
EMOJI = "\U0001f600"


# --------------------------------------------------------------------------
# Canonical JSON (section 3)
# --------------------------------------------------------------------------
def test_separators_and_key_order_are_canonical():
    assert canonical_bytes({"b": 1, "a": 2}) == b'{"a":2,"b":1}'


def test_key_order_is_code_point_not_utf16():
    # U+F000 sorts before U+1F600 by code point; a UTF-16 code-unit sort would
    # place the surrogate-pair character first and is non-conforming.
    out = canonical_bytes(["aaa", PUA + "zzz", EMOJI + "aaa"]).decode()
    assert out.index("aaa") < out.index(PUA) < out.index(EMOJI)


def test_non_ascii_emitted_literally():
    assert canonical_bytes({"k": "é"}) == '{"k":"é"}'.encode("utf-8")


def test_short_escapes_and_lowercase_unicode_escape():
    value = "a" + chr(10) + chr(9) + chr(34) + chr(92) + chr(31)
    out = canonical_bytes({"k": value}).decode()
    assert "\\n" in out and "\\t" in out and '\\"' in out and "\\\\" in out
    assert "\\u001f" in out
    assert "\\u001F" not in out


def test_nfc_normalization_before_hashing():
    composed = "é"
    decomposed = "é"
    assert canonical_bytes({"k": composed}) == canonical_bytes({"k": decomposed})


def test_duplicate_nfc_key_hard_fails():
    with pytest.raises(CanonicalError):
        canonical_bytes({"é": 1, "é": 2})


def test_floats_rejected_integers_only():
    with pytest.raises(CanonicalError):
        canonical_bytes({"n": 1.5})


def test_null_written_explicitly_never_omitted():
    assert canonical_bytes({"a": None}) == b'{"a":null}'


def test_insertion_order_does_not_affect_bytes():
    keys = ["k%d" % i for i in range(24)]
    reference = canonical_bytes({k: i for i, k in enumerate(keys)})
    rng = random.Random(20260830)
    for _ in range(40):
        shuffled = keys[:]
        rng.shuffle(shuffled)
        assert canonical_bytes({k: keys.index(k) for k in shuffled}) == reference


def test_code_point_sorted_dedupes():
    assert code_point_sorted(["b", "a", "b"], dedupe=True) == ["a", "b"]


# --------------------------------------------------------------------------
# Digest / token grammar (section 3)
# --------------------------------------------------------------------------
def test_digest_grammar():
    assert is_digest("sha256:" + "0" * 64)
    assert not is_digest("sha256:" + "0" * 63)
    assert not is_digest("sha256:" + "A" * 64)
    assert not is_digest("sha1:" + "0" * 40)
    assert not is_digest(None)


def test_require_digest_fails_closed():
    with pytest.raises(CanonicalError):
        require_digest("nope", "material_fingerprint")


def test_digest_over_requires_bytes_not_structures():
    with pytest.raises(CanonicalError):
        digest_over({"a": 1})


def test_genesis_hash_constant():
    assert GENESIS_LAST_OBSERVATION_HASH == "sha256:" + "0" * 64


# --------------------------------------------------------------------------
# Vocabulary (sections 4, 8.1, 9.1)
# --------------------------------------------------------------------------
def test_source_universe_and_prefix_owner_exact():
    assert SOURCE_UNIVERSE == {"GTFOBins", "LOLAD", "LOLBAS", "LOLDrivers", "WADComs"}
    assert set(PREFIX_OWNER.values()) == set(SOURCE_UNIVERSE)
    assert set(IDENTITY_MODE) == set(SOURCE_UNIVERSE)


def test_identity_modes_exact():
    assert IDENTITY_MODE["GTFOBins"] == (IdentityMode.STABLE, "gtfobins_natural_key")
    assert IDENTITY_MODE["LOLDrivers"] == (IdentityMode.STABLE, "loldrivers_id")
    for source in ("LOLAD", "LOLBAS", "WADComs"):
        assert IDENTITY_MODE[source] == (IdentityMode.NONE, None)


# --------------------------------------------------------------------------
# Ownership (section 8)
# --------------------------------------------------------------------------
def test_canonical_prefix_owner_is_case_sensitive_and_total():
    assert canonical_prefix_owner("gtfobins/x") == "GTFOBins"
    assert canonical_prefix_owner("GTFOBINS/x") == INVALID_PREFIX
    assert canonical_prefix_owner("noslash") == INVALID_PREFIX
    assert canonical_prefix_owner("/x") == INVALID_PREFIX
    assert canonical_prefix_owner("unknown/x") == INVALID_PREFIX


def _evidence(projects, declared, prefix="gtfobins"):
    return {
        "source_data_projects": list(projects),
        "declared_sources": list(declared),
        "id_prefix": prefix,
    }


def test_resolver_prefix_is_membership_not_singleton():
    outcome, owners = resolve_owner("gtfobins/x", _evidence([], ["GTFOBins", "WADComs"]))
    assert outcome == OwnerResolution.RESOLVED
    assert owners == frozenset({"GTFOBins", "WADComs"})


def test_resolver_ambiguous_when_channels_disagree():
    outcome, _ = resolve_owner("gtfobins/x", _evidence(["GTFOBins"], ["WADComs"]))
    assert outcome == OwnerResolution.AMBIGUOUS


def test_resolver_ambiguous_when_prefix_owner_absent():
    outcome, _ = resolve_owner("gtfobins/x", _evidence(["WADComs"], []))
    assert outcome == OwnerResolution.AMBIGUOUS


def test_resolver_defaults_to_prefix_owner_when_no_explicit_evidence():
    outcome, owners = resolve_owner("gtfobins/x", _evidence([], []))
    assert outcome == OwnerResolution.RESOLVED and owners == frozenset({"GTFOBins"})


def test_resolver_hard_invalid_on_bad_prefix_or_mismatch():
    assert resolve_owner("bogus/x", _evidence([], [], "bogus"))[0] == OwnerResolution.HARD_INVALID
    assert resolve_owner("gtfobins/x", _evidence([], [], "lolbas"))[0] == OwnerResolution.HARD_INVALID


def test_resolver_rejects_non_canonical_arrays():
    outcome, _ = resolve_owner("gtfobins/x", _evidence([], ["WADComs", "GTFOBins"]))
    assert outcome == OwnerResolution.HARD_INVALID


# --------------------------------------------------------------------------
# Material projection (section 14) and command ordering (section 3)
# --------------------------------------------------------------------------
def test_empty_placeholders_converge_with_omitted():
    assert canonical_command({"template": "X", "placeholders": []}) == {"template": "X"}
    assert canonical_command({"template": "X"}) == {"template": "X"}


def test_placeholder_permutations_are_byte_identical():
    a = canonical_command({"template": "X", "placeholders": ["A", "B"]})
    b = canonical_command({"template": "X", "placeholders": ["B", "A"]})
    assert canonical_bytes(a) == canonical_bytes(b)


def test_placeholders_deduped():
    assert canonical_command({"template": "X", "placeholders": ["A", "A"]})["placeholders"] == ["A"]


def test_command_ordering_is_total_and_permutation_invariant():
    left = canonical_commands([{"template": "X"}, {"template": "X", "comment": "a"}])
    right = canonical_commands([{"template": "X", "comment": "a"}, {"template": "X"}])
    assert left == right
    assert left[0] == {"template": "X"}


def test_material_excludes_non_material_fields():
    material = project_material_v1(
        {
            "id": "gtfobins/x",
            "name": "n",
            "last_synced": "2026-08-30",
            "projected_at": "2026-08-30",
            "_meta": {"a": 1},
            "source_data": {"GTFOBins": {"raw": {}}},
            "sources": [{"project": "GTFOBins"}],
        }
    )
    assert material == {"name": "n"}


def test_material_omit_empty_applies_to_every_shape():
    assert project_material_v1({"name": "", "aliases": [], "opsec": {}, "tags": None}) == {}


# --------------------------------------------------------------------------
# Golden vectors (section 16) — exact bytes AND exact digests
# --------------------------------------------------------------------------
def test_golden_G1_material_projection_of_real_entry():
    entry = yaml.safe_load(G1_ENTRY.read_text(encoding="utf-8"))
    blob = canonical_bytes(project_material_v1(entry))
    assert len(blob) == 552
    assert digest_over(blob) == G1_DIGEST
    assert material_fingerprint(entry) == G1_DIGEST


def test_golden_G2_observation_bytes_are_canonical():
    import json

    blob = G.G2_OBSERVATION.encode("utf-8")
    assert len(blob) == 1705
    assert digest_over(blob) == G2_DIGEST
    assert canonical_bytes(json.loads(G.G2_OBSERVATION)) == blob


def test_golden_G3_body_bytes_are_canonical():
    import json

    blob = G.G3_BODY.encode("utf-8")
    assert len(blob) == 581
    assert digest_over(blob) == G3_DIGEST
    assert canonical_bytes(json.loads(G.G3_BODY)) == blob


def test_golden_G3_envelope_and_persisted_bytes():
    import json

    body = json.loads(G.G3_BODY)
    envelope_bytes = canonical_bytes(build_envelope(body))
    assert envelope_bytes == G.G3_ENVELOPE.encode("utf-8")
    assert len(envelope_bytes) == 675
    assert len(serialize_state_file(body)) == 676
    assert serialize_state_file(body).endswith(b"}\n")


def test_golden_G3_body_passes_the_static_validator():
    import json

    validate_envelope(serialize_state_file(json.loads(G.G3_BODY)))


def test_golden_G4_unicode_ordering():
    blob = canonical_bytes(["gtfobins/aaa", "gtfobins/" + PUA + "zzz", "gtfobins/" + EMOJI + "aaa"])
    assert len(blob) == 53
    assert digest_over(blob) == G4_DIGEST


def test_golden_G5_escaping():
    value = ("a" + chr(10) + "b" + chr(9) + "c" + chr(34) + "d" + chr(92)
             + "e" + chr(31) + "fég")
    blob = canonical_bytes({"input_ref": value})
    assert len(blob) == 39
    assert digest_over(blob) == G5_DIGEST


def test_golden_G6_command_ordering():
    ordered = canonical_commands([{"comment": "a", "template": "X"}, {"template": "X"}])
    blob = canonical_bytes(ordered)
    assert len(blob) == 49
    assert digest_over(blob) == G6_DIGEST


def test_golden_placeholder_material_vectors():
    empty = canonical_bytes(
        project_material_v1({"commands": [{"template": "X", "placeholders": []}]})
    )
    assert len(empty) == 31
    assert digest_over(empty) == PLACEHOLDER_EMPTY_DIGEST
    omitted = canonical_bytes(project_material_v1({"commands": [{"template": "X"}]}))
    assert omitted == empty

    for placeholders in (["A", "B"], ["B", "A"]):
        blob = canonical_bytes(canonical_command({"template": "X", "placeholders": placeholders}))
        assert len(blob) == 41
        assert digest_over(blob) == PLACEHOLDER_NONEMPTY_DIGEST


# --------------------------------------------------------------------------
# Virtual genesis (section 12)
# --------------------------------------------------------------------------
def test_golden_fixture_genesis_body_token_and_envelope():
    entries = [gen.seed_entry("gtfobins/diff/file-read/unprivileged", "GTFOBins")]
    body = gen.genesis_body(entries)
    blob = canonical_bytes(body)
    assert blob == G.FIXTURE_GENESIS_BODY.encode("utf-8")
    assert len(blob) == 457
    assert gen.genesis_checksum(entries) == FIXTURE_GENESIS_DIGEST

    assert canonical_bytes(gen.genesis_token(entries)) == G.FIXTURE_GENESIS_TOKEN.encode("utf-8")
    assert canonical_bytes(build_envelope(body)) == G.FIXTURE_GENESIS_ENVELOPE.encode("utf-8")
    assert len(serialize_state_file(body)) == 552


def test_fixture_genesis_validates():
    entries = [gen.seed_entry("gtfobins/diff/file-read/unprivileged", "GTFOBins")]
    validate_envelope(serialize_state_file(gen.genesis_body(entries)))


def test_production_genesis_reproduces_frozen_oracle():
    entries = gen.build_genesis_inventory(ROOT)
    assert len(entries) == PRODUCTION_GENESIS_ENTRIES
    blob = canonical_bytes(gen.genesis_body(entries))
    assert len(blob) == PRODUCTION_GENESIS_BYTES
    assert digest_over(blob) == PRODUCTION_GENESIS_DIGEST


def test_production_genesis_ownership_is_fully_resolved():
    entries = gen.build_genesis_inventory(ROOT)
    assert all(canonical_prefix_owner(e["entry_id"]) in e["owner_sources"] for e in entries)
    assert len({e["entry_id"] for e in entries}) == len(entries)


def test_production_genesis_is_deterministic_across_runs():
    first = canonical_bytes(gen.genesis_body(gen.build_genesis_inventory(ROOT)))
    second = canonical_bytes(gen.genesis_body(gen.build_genesis_inventory(ROOT)))
    assert first == second


# --------------------------------------------------------------------------
# Evidence truth table (section 11.5) — exhaustive cross-product
# --------------------------------------------------------------------------
STABLE_KIND = "gtfobins_natural_key"
VALID_IDENTITY = {"kind": STABLE_KIND, "value": "diff/file-read/unprivileged"}
VALID_DIGEST = "sha256:" + "a" * 64

ALLOWED = {
    (IdentityMode.STABLE, (False, False, False)): EvidenceTuple.EMPTY,
    (IdentityMode.STABLE, (True, True, True)): EvidenceTuple.STABLE_RELIABLE,
    (IdentityMode.NONE, (False, False, False)): EvidenceTuple.EMPTY,
    (IdentityMode.NONE, (False, True, True)): EvidenceTuple.UNKEYED_RELIABLE,
}


@pytest.mark.parametrize("mode", [IdentityMode.STABLE, IdentityMode.NONE])
@pytest.mark.parametrize("bits", list(itertools.product([False, True], repeat=3)))
def test_evidence_truth_table_exhaustive(mode, bits):
    i_bit, f_bit, l_bit = bits
    kind = STABLE_KIND if mode == IdentityMode.STABLE else None
    identity = None
    if i_bit:
        identity = VALID_IDENTITY if mode == IdentityMode.STABLE else {"kind": "x", "value": "y"}
    args = (mode, kind, identity, VALID_DIGEST if f_bit else None, 5 if l_bit else None, 9)
    expected = ALLOWED.get((mode, bits))
    if expected is None:
        with pytest.raises(StateInvalid):
            classify_evidence_tuple(*args)
    else:
        assert classify_evidence_tuple(*args) == expected


def test_reliable_id_zero_is_invalid():
    with pytest.raises(StateInvalid):
        classify_evidence_tuple(IdentityMode.NONE, None, None, VALID_DIGEST, 0, 9)


def test_reliable_id_beyond_head_is_invalid():
    with pytest.raises(StateInvalid):
        classify_evidence_tuple(IdentityMode.NONE, None, None, VALID_DIGEST, 10, 9)


def test_stable_identity_kind_must_match_exactly():
    with pytest.raises(StateInvalid):
        classify_evidence_tuple(
            IdentityMode.STABLE, STABLE_KIND,
            {"kind": "loldrivers_id", "value": "x"}, VALID_DIGEST, 5, 9,
        )


def test_stable_identity_value_must_be_non_empty():
    with pytest.raises(StateInvalid):
        classify_evidence_tuple(
            IdentityMode.STABLE, STABLE_KIND,
            {"kind": STABLE_KIND, "value": ""}, VALID_DIGEST, 5, 9,
        )


def test_malformed_fingerprint_rejected_not_repaired():
    with pytest.raises(StateInvalid):
        classify_evidence_tuple(IdentityMode.NONE, None, None, "sha256:zz", 5, 9)


# --------------------------------------------------------------------------
# Entry partition (11.3) and reachability invariants (11.6)
# --------------------------------------------------------------------------
def _entry(**overrides):
    entry = {
        "entry_id": "gtfobins/x",
        "classification": Classification.ACTIVE,
        "initialized": True,
        "absence_streak": 0,
        "owner_ambiguous": False,
        "owner_sources": ["GTFOBins"],
        "sources": [
            {
                "source": "GTFOBins",
                "material_fingerprint": VALID_DIGEST,
                "last_reliable_observation_id": 1,
                "upstream_identity": VALID_IDENTITY,
            }
        ],
    }
    entry.update(overrides)
    return entry


def _empty_evidence(source="GTFOBins"):
    return {
        "source": source,
        "material_fingerprint": None,
        "last_reliable_observation_id": None,
        "upstream_identity": None,
    }


def test_partition_row_C_active_valid():
    validate_entry(_entry(), 5)


def test_partition_row_A_ambiguous_with_empty_arrays_valid():
    validate_entry(
        _entry(classification=Classification.NOT_OBSERVED, owner_ambiguous=True,
               owner_sources=[], sources=[]),
        5,
    )


def test_partition_rejects_ambiguous_uninitialized():
    with pytest.raises(StateInvalid):
        validate_entry(
            _entry(classification=Classification.NOT_OBSERVED, owner_ambiguous=True,
                   initialized=False, owner_sources=[], sources=[]),
            5,
        )


def test_partition_rejects_active_with_positive_streak():
    with pytest.raises(StateInvalid):
        validate_entry(_entry(absence_streak=1), 5)


def test_partition_rejects_stale_candidate_below_threshold():
    with pytest.raises(StateInvalid):
        validate_entry(
            _entry(classification=Classification.STALE_CANDIDATE, absence_streak=2), 5
        )


def test_partition_accepts_stale_candidate_at_threshold():
    validate_entry(
        _entry(classification=Classification.STALE_CANDIDATE, absence_streak=3,
               sources=[_empty_evidence()]),
        5,
    )


def test_hardening_V1_initialized_requires_observation_id_at_least_one():
    with pytest.raises(StateInvalid):
        validate_entry(_entry(), 0)


def test_hardening_V2_streak_cannot_exceed_last_observation_id():
    entry = _entry(classification=Classification.STALE_CANDIDATE, absence_streak=4,
                   sources=[_empty_evidence()])
    validate_entry(entry, 4)
    with pytest.raises(StateInvalid):
        validate_entry(entry, 3)


def test_hardening_V3_non_ambiguous_must_contain_prefix_owner():
    with pytest.raises(StateInvalid):
        validate_entry(
            _entry(owner_sources=["WADComs"],
                   sources=[{"source": "WADComs", "material_fingerprint": VALID_DIGEST,
                             "last_reliable_observation_id": 1, "upstream_identity": None}]),
            5,
        )


def test_hardening_V3_exempts_ambiguous_entries():
    validate_entry(
        _entry(classification=Classification.NOT_OBSERVED, owner_ambiguous=True,
               owner_sources=[], sources=[]),
        5,
    )


def test_uninitialized_requires_every_tuple_empty():
    with pytest.raises(StateInvalid):
        validate_entry(
            _entry(classification=Classification.NOT_OBSERVED, initialized=False), 5
        )


def test_mixed_legal_tuples_allowed_no_history_inference():
    # section 11.6: ACTIVE may hold any mixture of mode-legal tuples after
    # owner reconciliation; requiring a reliable tuple would infer history.
    validate_entry(
        _entry(owner_sources=["GTFOBins", "WADComs"],
               sources=[
                   {"source": "GTFOBins", "material_fingerprint": VALID_DIGEST,
                    "last_reliable_observation_id": 1, "upstream_identity": VALID_IDENTITY},
                   _empty_evidence("WADComs"),
               ]),
        5,
    )


def test_owner_and_source_sets_must_match():
    with pytest.raises(StateInvalid):
        validate_entry(_entry(owner_sources=["GTFOBins", "WADComs"]), 5)


def test_owner_sources_must_be_sorted_and_deduped():
    entry = _entry(
        owner_sources=["WADComs", "GTFOBins"],
        sources=[
            {"source": "GTFOBins", "material_fingerprint": VALID_DIGEST,
             "last_reliable_observation_id": 1, "upstream_identity": VALID_IDENTITY},
            _empty_evidence("WADComs"),
        ],
    )
    with pytest.raises(StateInvalid):
        validate_entry(entry, 5)


def test_owner_outside_source_universe_rejected():
    with pytest.raises(StateInvalid):
        validate_entry(
            _entry(owner_sources=["NotASource"], sources=[_empty_evidence("NotASource")]), 5
        )


def test_undeclared_entry_field_rejected():
    entry = _entry()
    entry["extra"] = 1
    with pytest.raises(StateInvalid):
        validate_entry(entry, 5)


def test_missing_entry_field_rejected():
    entry = _entry()
    del entry["absence_streak"]
    with pytest.raises(StateInvalid):
        validate_entry(entry, 5)


# --------------------------------------------------------------------------
# Body / envelope validation (11.1, 11.2)
# --------------------------------------------------------------------------
def _body(**overrides):
    body = {
        "core_state_version": CORE_STATE_VERSION,
        "entries": [],
        "last_observation_hash": GENESIS_LAST_OBSERVATION_HASH,
        "last_observation_id": 0,
    }
    body.update(overrides)
    return body


def test_body_version_must_be_two():
    with pytest.raises(StateInvalid):
        validate_body(_body(core_state_version=1))


def test_genesis_requires_all_zero_hash():
    with pytest.raises(StateInvalid):
        validate_body(_body(last_observation_hash="sha256:" + "1" * 64))


def test_entries_must_be_sorted_by_entry_id():
    import copy

    a = gen.seed_entry("gtfobins/a", "GTFOBins")
    b = gen.seed_entry("gtfobins/b", "GTFOBins")
    validate_body(_body(entries=[copy.deepcopy(a), copy.deepcopy(b)]))
    with pytest.raises(StateInvalid):
        validate_body(_body(entries=[copy.deepcopy(b), copy.deepcopy(a)]))


def test_duplicate_entry_id_rejected():
    import copy

    a = gen.seed_entry("gtfobins/a", "GTFOBins")
    with pytest.raises(StateInvalid):
        validate_body(_body(entries=[copy.deepcopy(a), copy.deepcopy(a)]))


def test_envelope_checksum_mismatch_rejected():
    envelope = build_envelope(_body())
    envelope["checksum"] = "sha256:" + "b" * 64
    with pytest.raises(StateInvalid):
        validate_envelope(canonical_bytes(envelope) + b"\n")


def test_envelope_requires_terminal_newline():
    with pytest.raises(StateInvalid):
        validate_envelope(canonical_bytes(build_envelope(_body())))


def test_non_canonical_but_equivalent_file_rejected():
    import json

    pretty = (json.dumps(build_envelope(_body()), sort_keys=True, indent=2) + "\n").encode("utf-8")
    with pytest.raises(StateInvalid):
        validate_envelope(pretty)


def test_state_token_shape_and_checksum():
    body = _body()
    token = state_token(body)
    assert set(token) == {
        "core_state_version", "last_observation_hash", "last_observation_id", "state_checksum",
    }
    assert token["state_checksum"] == digest_over(canonical_bytes(body))


# --------------------------------------------------------------------------
# Golden literals match the frozen specification document
# --------------------------------------------------------------------------
@pytest.mark.skipif(not SPEC.exists(), reason="frozen spec not present in this tree")
@pytest.mark.parametrize(
    "literal",
    [
        G.G2_OBSERVATION,
        G.G3_BODY,
        G.G3_ENVELOPE,
        G.FIXTURE_GENESIS_BODY,
        G.FIXTURE_GENESIS_ENVELOPE,
        G.FIXTURE_GENESIS_TOKEN,
    ],
)
def test_golden_literals_appear_verbatim_in_frozen_spec(literal):
    assert literal in SPEC.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# Canonical input_ref (section 6.2.1) — pure helper; adapter wiring is CP5.3
# --------------------------------------------------------------------------
def test_source_prefixes_are_exact():
    assert SOURCE_PREFIX == {
        "GTFOBins": "_gtfobins/",
        "LOLBAS": "yml/",
        "WADComs": "_wadcoms/",
        "LOLAD": "",
        "LOLDrivers": "yaml/",
    }
    assert set(SOURCE_PREFIX) == set(SOURCE_UNIVERSE)


def test_option_c_form_is_generated_by_the_general_function():
    # The ratified GTFOBins form is produced normally, not special-cased.
    assert canonical_input_ref("GTFOBins", "diff.md", FILE) == "_gtfobins/diff.md#"
    assert canonical_input_ref("GTFOBins", "sub/dir/diff.md", FILE) == "_gtfobins/sub/dir/diff.md#"


def test_lolad_prefix_is_empty_and_file_is_not_the_root():
    assert canonical_input_ref("LOLAD", "index.html", ROW(0)) == "index.html#row=0"
    assert canonical_input_ref("LOLAD", "index.html", ROW(12)) == "index.html#row=12"
    assert canonical_input_ref("LOLAD", "index.html", FILE) == "index.html#"


def test_row_index_has_no_leading_zero_except_zero():
    assert canonical_input_ref("LOLAD", "index.html", ROW(0)).endswith("#row=0")
    assert canonical_input_ref("LOLAD", "index.html", ROW(7)).endswith("#row=7")
    assert canonical_input_ref("LOLAD", "index.html", ROW(10)).endswith("#row=10")


def test_rows_of_one_file_do_not_collide():
    refs = [canonical_input_ref("LOLAD", "index.html", ROW(n)) for n in range(4)]
    assert len(set(refs)) == 4


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("a//./b/", "_gtfobins/a/b#"),
        ("./a/b", "_gtfobins/a/b#"),
        ("a/./b", "_gtfobins/a/b#"),
        ("a///b", "_gtfobins/a/b#"),
        ("a/b/", "_gtfobins/a/b#"),
    ],
)
def test_separator_and_dot_normalization(raw, expected):
    assert canonical_input_ref("GTFOBins", raw, FILE) == expected


def test_backslash_is_converted_to_solidus():
    assert canonical_input_ref("GTFOBins", "a" + chr(92) + "b", FILE) == "_gtfobins/a/b#"


@pytest.mark.parametrize(
    "raw", ["/a", "C:/a", "C:", "c:", "Z:/x", "//server/share", chr(92) + "a"]
)
def test_absolute_names_are_path_invalid(raw):
    with pytest.raises(PathInvalid):
        canonical_input_ref("GTFOBins", raw, FILE)


@pytest.mark.parametrize("raw", ["a/../b", "..", "../a", "a/..", "a/b/../../c"])
def test_parent_components_are_path_invalid(raw):
    with pytest.raises(PathInvalid):
        canonical_input_ref("GTFOBins", raw, FILE)


@pytest.mark.parametrize("raw", ["", ".", "./", "//", "./././"])
def test_names_that_normalize_to_nothing_are_path_invalid(raw):
    with pytest.raises(PathInvalid):
        canonical_input_ref("GTFOBins", raw, FILE)


def test_case_is_preserved_never_folded():
    assert canonical_input_ref("GTFOBins", "AbC/DeF.md", FILE) == "_gtfobins/AbC/DeF.md#"


def test_nfc_normalization_applied_to_the_name():
    composed = "caf\u00e9.md"
    decomposed = "cafe\u0301.md"
    assert canonical_input_ref("GTFOBins", composed, FILE) == canonical_input_ref(
        "GTFOBins", decomposed, FILE
    )


def test_escaping_order_is_injective():
    # % first, then #, both uppercase hex; literal a#b and literal a%23b must differ.
    assert canonical_input_ref("LOLBAS", "a#b", FILE) == "yml/a%23b#"
    assert canonical_input_ref("LOLBAS", "a%23b", FILE) == "yml/a%2523b#"
    assert canonical_input_ref("LOLBAS", "a#b", FILE) != canonical_input_ref(
        "LOLBAS", "a%23b", FILE
    )
    assert canonical_input_ref("LOLBAS", "a%b", FILE) == "yml/a%25b#"


def test_no_other_character_is_escaped_or_decoded():
    # Spaces, plus signs and non-ASCII stay literal; only % and # are escaped.
    assert canonical_input_ref("LOLBAS", "a b+c\u00e9.yml", FILE) == "yml/a b+c\u00e9.yml#"


def test_separator_is_not_escaped():
    assert canonical_input_ref("LOLBAS", "a/b/c.yml", FILE) == "yml/a/b/c.yml#"


def test_unknown_locator_is_path_invalid():
    for locator in (None, "FILE", ("ROW", -1), ("ROW", True), ("ROW", "1"), ("COLUMN", 1)):
        with pytest.raises(PathInvalid):
            canonical_input_ref("GTFOBins", "a.md", locator)


def test_unknown_source_is_path_invalid():
    with pytest.raises(PathInvalid):
        canonical_input_ref("NotASource", "a.md", FILE)


def test_invalid_path_sentinel_shape_and_disjointness():
    for source in SOURCE_UNIVERSE:
        sentinel = invalid_path_ref(source)
        assert sentinel == SOURCE_PREFIX[source] + "#invalid-path"
    # Every valid path is non-empty, so the sentinel cannot equal a valid ref.
    assert invalid_path_ref("GTFOBins") != canonical_input_ref("GTFOBins", "a.md", FILE)


def test_normalized_ref_collision_group_detected():
    # Two distinct filesystem names collapsed by separator/'.' normalization.
    a = canonical_input_ref("GTFOBins", "a/b.md", FILE)
    b = canonical_input_ref("GTFOBins", "a//./b.md", FILE)
    assert a == b
    groups = normalized_ref_collision_groups([(a, "a/b.md"), (b, "a//./b.md")])
    assert groups == {a: ["a/b.md", "a//./b.md"]}


def test_nfc_collision_is_detected():
    composed = canonical_input_ref("GTFOBins", "caf\u00e9.md", FILE)
    decomposed = canonical_input_ref("GTFOBins", "cafe\u0301.md", FILE)
    groups = normalized_ref_collision_groups(
        [(composed, "caf\u00e9.md"), (decomposed, "cafe\u0301.md")]
    )
    assert list(groups) == [composed]
    assert len(groups[composed]) == 2


def test_non_colliding_siblings_are_not_grouped():
    refs = [
        (canonical_input_ref("GTFOBins", "a.md", FILE), "a.md"),
        (canonical_input_ref("GTFOBins", "b.md", FILE), "b.md"),
    ]
    assert normalized_ref_collision_groups(refs) == {}


def test_collision_grouping_is_order_independent():
    a = canonical_input_ref("GTFOBins", "a/b.md", FILE)
    forward = normalized_ref_collision_groups([(a, "x"), (a, "y")])
    reverse = normalized_ref_collision_groups([(a, "y"), (a, "x")])
    assert set(forward) == set(reverse)
    assert sorted(forward[a]) == sorted(reverse[a]) == ["x", "y"]


def test_input_ref_is_json_safe_under_canonical_bytes():
    ref = canonical_input_ref("GTFOBins", "a#b.md", FILE)
    assert canonical_bytes({"input_ref": ref}) == ('{"input_ref":"%s"}' % ref).encode("utf-8")


# --------------------------------------------------------------------------
# G3 byte accounting — body vs envelope vs persisted file
# --------------------------------------------------------------------------
def test_G3_byte_accounting_is_explicit():
    """The three G3 sizes are distinct artefacts, not rounding of one number.

    body      581 = canonical bytes of the state body (hashed; no newline)
    envelope  675 = canonical bytes of {body, checksum} (no newline)
    file      676 = envelope + exactly one terminal newline
    """
    import json

    body = json.loads(G.G3_BODY)
    body_bytes = canonical_bytes(body)
    envelope_bytes = canonical_bytes(build_envelope(body))
    file_bytes = serialize_state_file(body)

    assert len(body_bytes) == 581
    assert len(envelope_bytes) == 675
    assert len(file_bytes) == 676

    # The single extra byte is exactly the terminal newline, and nothing else.
    assert file_bytes == envelope_bytes + b"\n"
    assert len(file_bytes) - len(envelope_bytes) == 1
    assert file_bytes[-1:] == b"\n"
    assert file_bytes.count(b"\n") == 1

    # The hashed body carries no newline; the checksum is over body bytes only.
    assert not body_bytes.endswith(b"\n")
    assert digest_over(body_bytes) == G3_DIGEST
    assert json.loads(envelope_bytes.decode())["checksum"] == G3_DIGEST


def test_fixture_genesis_byte_accounting_is_explicit():
    entries = [gen.seed_entry("gtfobins/diff/file-read/unprivileged", "GTFOBins")]
    body = gen.genesis_body(entries)
    body_bytes = canonical_bytes(body)
    envelope_bytes = canonical_bytes(build_envelope(body))
    file_bytes = serialize_state_file(body)

    assert len(body_bytes) == 457
    assert len(envelope_bytes) == 551
    assert len(file_bytes) == 552
    assert file_bytes == envelope_bytes + b"\n"
    assert file_bytes.count(b"\n") == 1


# --------------------------------------------------------------------------
# Codex CP5.1 review — regression cases for the three reported blockers
# --------------------------------------------------------------------------
def test_blocker1_digest_grammar_rejects_trailing_newline():
    """B1: ``$`` also matches before a final newline; full-string match required."""
    assert not is_digest("sha256:" + "a" * 64 + "\n")
    assert not is_digest("sha256:" + "a" * 64 + "\r\n")
    assert not is_digest("sha256:" + "a" * 64 + " ")
    assert not is_digest("\nsha256:" + "a" * 64)
    assert is_digest("sha256:" + "a" * 64)
    with pytest.raises(CanonicalError):
        require_digest("sha256:" + "a" * 64 + "\n", "material_fingerprint")


def test_blocker1_state_rejects_digest_with_trailing_newline():
    """A correctly checksummed envelope must still be rejected for a bad digest."""
    body = _body(last_observation_hash=GENESIS_LAST_OBSERVATION_HASH + "\n")
    with pytest.raises(StateInvalid):
        validate_body(body)
    with pytest.raises(StateInvalid):
        validate_envelope(canonical_bytes(build_envelope(body)) + b"\n")


def test_blocker1_evidence_rejects_fingerprint_with_trailing_newline():
    with pytest.raises(StateInvalid):
        classify_evidence_tuple(
            IdentityMode.NONE, None, None, "sha256:" + "a" * 64 + "\n", 5, 9
        )


def test_blocker2_nfc_duplicate_detail_keys_hard_fail():
    """B2: normalizing into a fresh dict silently dropped one colliding key."""
    colliding = {"technique_detail": {"é": 1, "é": 2}}
    with pytest.raises(CanonicalError):
        project_material_v1(colliding)
    with pytest.raises(CanonicalError):
        material_fingerprint(colliding)


def test_blocker2_colliding_detail_does_not_collapse_onto_a_distinct_entry():
    """The collision must not silently produce the same digest as a distinct object."""
    single = {"technique_detail": {"é": 2}}
    assert material_fingerprint(single)  # the non-colliding object still projects
    with pytest.raises(CanonicalError):
        material_fingerprint({"technique_detail": {"é": 1, "é": 2}})


def test_blocker2_driver_detail_is_covered_too():
    with pytest.raises(CanonicalError):
        project_material_v1({"driver_detail": {"é": 1, "é": 2}})


def test_blocker2_non_colliding_detail_keys_still_normalize():
    material = project_material_v1({"driver_detail": {"é": 1, "b": 2}})
    assert material["driver_detail"] == {"é": 1, "b": 2}


@pytest.mark.parametrize("source", ["GTFOBins", "LOLBAS", "WADComs", "LOLDrivers"])
def test_blocker3_row_locator_rejected_for_non_lolad_sources(source):
    """B3: only LOLAD has row candidates; every other source has file candidates."""
    with pytest.raises(PathInvalid):
        canonical_input_ref(source, "x.md", ROW(0))
    with pytest.raises(PathInvalid):
        canonical_input_ref(source, "x.md", ROW(7))


def test_blocker3_lolad_row_still_accepted():
    assert canonical_input_ref("LOLAD", "index.html", ROW(0)) == "index.html#row=0"
    assert canonical_input_ref("LOLAD", "index.html", ROW(3)) == "index.html#row=3"


def test_blocker3_file_locator_still_accepted_everywhere():
    for source in SOURCE_UNIVERSE:
        assert canonical_input_ref(source, "x.md", FILE).endswith("#")
