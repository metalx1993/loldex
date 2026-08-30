"""Phase 5 CORE — CP5.2 tests: the pure transition engine.

Scope: admission precedence (section 5.4, including the frozen B7 closure),
per-owner continuity (9.2/9.3), the aggregate and evidence-mutation gate (9.4),
the entry-level freshness table (10), and the report including ``changed`` (15).

The frozen specification ``docs/phase5-core-design-v6-4.md`` is the oracle.
The engine is pure: every test asserts canonical bytes or exact objects, never
"equivalent JSON", and no test touches the filesystem or a clock.
"""
import copy
import json
import pathlib
import random
import sys
import unicodedata

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from phase5 import genesis as gen  # noqa: E402
from phase5.canonical import canonical_bytes, digest_over  # noqa: E402
from phase5.input_ref import FILE, ROW, canonical_input_ref, invalid_path_ref  # noqa: E402
from phase5.state import (  # noqa: E402
    build_envelope,
    serialize_state_file,
    state_token,
    validate_body,
)
from phase5.transition import (  # noqa: E402
    Admission,
    ObservationInvalid,
    TransitionResult,
    evaluate,
    observation_hash,
)
from phase5.vocabulary import (  # noqa: E402
    SOURCE_UNIVERSE,
    AggregateClass,
    Classification,
    SourceStatus,
)
from tests import phase5_goldens as G  # noqa: E402

G2_DIGEST = "sha256:8b687db6f7882e233e2df28f5c55af20300278c5fddb566140f907b9f4a56f42"
G3_DIGEST = "sha256:286048e4d67b0049ae052c7dd5c3fe1c9a95e1c8f63a4625bf21f649f2dece09"
FP_A = "sha256:" + "a" * 64
FP_B = "sha256:" + "b" * 64
REV = "c" * 40
ENTRY = "gtfobins/diff/file-read/unprivileged"
GTFO_ID = {"kind": "gtfobins_natural_key", "value": "diff/file-read/unprivileged"}
DRV_ID = {"kind": "loldrivers_id", "value": "abc-123"}


# --------------------------------------------------------------------------
# Builders — construct only schema-valid observations and states
# --------------------------------------------------------------------------
def not_run(source):
    """Section 6.1 NOT_RUN shape."""
    return {
        "source": source,
        "acquired_ok": False,
        "resolved_revision": None,
        "inputs_total": 0,
        "parsed_ok": 0,
        "rejected": [],
        "unmapped": [],
        "duplicate_ids": [],
        "emitted_entries": {},
        "status": SourceStatus.UNKNOWN,
        "primary_reason": "NOT_RUN",
    }


#: Section 7.2b candidate code used to build each non-ok health shape, chosen so
#: that ``status == STATUS_OF[primary_reason]`` holds exactly (section 7.2).
_REJECT_CODE_FOR_STATUS = {
    SourceStatus.FAILED: "PARSE_ERROR",       # rank 5 · failed
    SourceStatus.PARTIAL: "MALFORMED_RECORD",  # rank 12 · partial
}


def candidate_ref(source, name="record.yml"):
    """A §6.2.1 canonical file reference for ``source`` built by the frozen helper."""
    return canonical_input_ref(source, name, FILE)


def result(source, status=SourceStatus.OK, emitted=None, revision=REV):
    """An acquired result in the frozen valid-input domain.

    Every shape this returns satisfies §6.0/§7.2 exactly:

    * an ``ok`` result has at least one candidate (an acquired source with zero
      candidates is ``EMPTY_INPUT_SET`` by §7.2a rank 2, never ``ok``), and a
      parsed candidate is free to emit nothing — that is how a healthy source is
      *absent* for an entry;
    * a non-ok result carries a real §7.2b rejection whose code derives exactly
      the requested status, keeps the ``inputs_total == parsed_ok + len(rejected)``
      equation, and retains every parsed sibling emission (§7.2d).
    """
    emitted = emitted or {}
    if status == SourceStatus.OK:
        parsed = max(1, len(emitted))
        rejected = []
        reason = "NONE"
    else:
        code = _REJECT_CODE_FOR_STATUS[status]
        parsed = len(emitted)
        rejected = [{"input_ref": candidate_ref(source), "code": code}]
        reason = code
    return {
        "source": source,
        "acquired_ok": True,
        "resolved_revision": revision,
        "inputs_total": parsed + len(rejected),
        "parsed_ok": parsed,
        "rejected": rejected,
        "unmapped": [],
        "duplicate_ids": [],
        "emitted_entries": emitted,
        "status": status,
        "primary_reason": reason,
    }


def empty_input(source, revision=REV):
    """Section 7.2a — the exact acquired zero-candidate shape."""
    return {
        "source": source,
        "acquired_ok": True,
        "resolved_revision": revision,
        "inputs_total": 0,
        "parsed_ok": 0,
        "rejected": [],
        "unmapped": [],
        "duplicate_ids": [],
        "emitted_entries": {},
        "status": SourceStatus.FAILED,
        "primary_reason": "EMPTY_INPUT_SET",
    }


def acquisition_failed(source):
    """Section 7.2a — the exact unacquired source-level failure shape."""
    return {
        "source": source,
        "acquired_ok": False,
        "resolved_revision": None,
        "inputs_total": 0,
        "parsed_ok": 0,
        "rejected": [],
        "unmapped": [],
        "duplicate_ids": [],
        "emitted_entries": {},
        "status": SourceStatus.FAILED,
        "primary_reason": "ACQUISITION_FAILED",
    }


def emitted(entry_id, owners, fingerprint=FP_A, identity=GTFO_ID, prefix="gtfobins"):
    return {
        entry_id: {
            "material_fingerprint": fingerprint,
            "owner_evidence": {
                "declared_sources": sorted(owners),
                "id_prefix": prefix,
                "source_data_projects": sorted(owners),
            },
            "upstream_identity": identity,
        }
    }


def observation(base_token, obs_id, results):
    """Assemble a complete observation: exactly one result per SOURCE_UNIVERSE."""
    by_source = {r["source"]: r for r in results}
    full = [by_source.get(s, not_run(s)) for s in sorted(SOURCE_UNIVERSE)]
    return {"observation_id": obs_id, "base_state": base_token, "results": full}


def entry(entry_id=ENTRY, classification=Classification.ACTIVE, initialized=True,
          streak=0, owners=("GTFOBins",), sources=None, ambiguous=False):
    if sources is None:
        sources = [{"source": o, "material_fingerprint": FP_A,
                    "last_reliable_observation_id": 1, "upstream_identity": GTFO_ID}
                   for o in sorted(owners)]
    return {
        "entry_id": entry_id,
        "classification": classification,
        "initialized": initialized,
        "absence_streak": streak,
        "owner_ambiguous": ambiguous,
        "owner_sources": sorted(owners),
        "sources": sources,
    }


def empty_evidence(source):
    return {"source": source, "material_fingerprint": None,
            "last_reliable_observation_id": None, "upstream_identity": None}


def body(entries, obs_id=5, obs_hash=None):
    return {
        "core_state_version": 2,
        "entries": sorted(entries, key=lambda e: e["entry_id"]),
        "last_observation_hash": obs_hash or ("sha256:" + "d" * 64),
        "last_observation_id": obs_id,
    }


def step(state, results, obs_id=None):
    """Run one admitted transition against ``state`` and return the result."""
    token = state_token(state)
    obs = observation(token, (obs_id or state["last_observation_id"] + 1), results)
    return evaluate(state, obs)


def only_row(res):
    assert len(res.report["entries"]) == 1
    return res.report["entries"][0]


def only_entry(res):
    assert len(res.next_body["entries"]) == 1
    return res.next_body["entries"][0]


# --------------------------------------------------------------------------
# The golden transition — the CP5.2 gate
# --------------------------------------------------------------------------
def fixture_genesis():
    return gen.genesis_body([gen.seed_entry(ENTRY, "GTFOBins")])


def test_golden_apply_G2_to_fixture_genesis_equals_G3():
    res = evaluate(fixture_genesis(), json.loads(G.G2_OBSERVATION))
    assert res.admission == Admission.APPLIED
    assert res.observation_hash == G2_DIGEST

    blob = canonical_bytes(res.next_body)
    assert blob == G.G3_BODY.encode("utf-8")
    assert len(blob) == 581
    assert digest_over(blob) == G3_DIGEST

    envelope = canonical_bytes(build_envelope(res.next_body))
    assert envelope == G.G3_ENVELOPE.encode("utf-8")
    assert len(envelope) == 675
    assert len(serialize_state_file(res.next_body)) == 676


def test_golden_transition_head_and_entry_state():
    res = evaluate(fixture_genesis(), json.loads(G.G2_OBSERVATION))
    assert res.next_body["last_observation_id"] == 1
    assert res.next_body["last_observation_hash"] == G2_DIGEST
    got = only_entry(res)
    assert got["classification"] == Classification.ACTIVE
    assert got["initialized"] is True
    assert got["absence_streak"] == 0
    assert got["sources"][0]["last_reliable_observation_id"] == 1
    assert got["sources"][0]["upstream_identity"] == GTFO_ID


def test_golden_transition_report():
    res = evaluate(fixture_genesis(), json.loads(G.G2_OBSERVATION))
    assert res.report == {
        "report_version": 1,
        "observation_id": 1,
        "entries": [{"entry_id": ENTRY, "classification": "ACTIVE",
                     "aggregate_class": "PRESENT", "changed": False}],
    }


# --------------------------------------------------------------------------
# Admission precedence — B7 (sections 5.4, 5.7, 5.7.1)
# --------------------------------------------------------------------------
def committed_after_G2():
    return evaluate(fixture_genesis(), json.loads(G.G2_OBSERVATION)).next_body


def test_B7_A_exact_retry_is_idempotent_no_op():
    committed = committed_after_G2()
    res = evaluate(committed, json.loads(G.G2_OBSERVATION))
    assert res.admission == Admission.IDEMPOTENT_NO_OP
    assert res.report is None
    assert res.next_body is None


def test_B7_C_stale_embedded_base_does_not_beat_the_same_id_branch():
    """The retry still embeds pre-commit base T0 while the head is T1."""
    committed = committed_after_G2()
    obs = json.loads(G.G2_OBSERVATION)
    assert obs["base_state"] != state_token(committed)      # the mismatch is real
    assert evaluate(committed, obs).admission == Admission.IDEMPOTENT_NO_OP


def test_B7_retry_leaves_persisted_bytes_exactly_G3():
    committed = committed_after_G2()
    before = canonical_bytes(committed)
    evaluate(committed, json.loads(G.G2_OBSERVATION))
    assert canonical_bytes(committed) == before == G.G3_BODY.encode("utf-8")


def test_B7_B_same_id_different_hash_conflicts():
    committed = committed_after_G2()
    obs = json.loads(G.G2_OBSERVATION)
    gtfo = next(r for r in obs["results"] if r["source"] == "GTFOBins")
    gtfo["resolved_revision"] = "b" * 40                     # real byte change
    assert observation_hash(obs) != G2_DIGEST
    res = evaluate(committed, obs)
    assert res.admission == Admission.SAME_ID_DIFFERENT_HASH_CONFLICT
    assert res.report is None and res.next_body is None


def test_B7_D_stale_embedded_base_does_not_beat_the_conflict_branch():
    committed = committed_after_G2()
    obs = json.loads(G.G2_OBSERVATION)
    next(r for r in obs["results"] if r["source"] == "GTFOBins")["resolved_revision"] = "b" * 40
    assert obs["base_state"] != state_token(committed)
    assert evaluate(committed, obs).admission == Admission.SAME_ID_DIFFERENT_HASH_CONFLICT


def test_admission_invalid_successor():
    committed = committed_after_G2()
    obs = json.loads(G.G2_OBSERVATION)
    obs["observation_id"] = 2                                 # base still says 0
    assert evaluate(committed, obs).admission == Admission.INVALID_SUCCESSOR


def test_admission_precondition_mismatch():
    """Correct successor arithmetic, wrong base token."""
    state = body([entry()], obs_id=5)
    wrong = dict(state_token(state))
    wrong["state_checksum"] = "sha256:" + "9" * 64
    obs = observation(wrong, 6, [result("GTFOBins", emitted=emitted(ENTRY, ["GTFOBins"]))])
    assert evaluate(state, obs).admission == Admission.PRECONDITION_MISMATCH


def test_admission_stale():
    committed = committed_after_G2()
    obs = observation(state_token(committed), 0, [])
    assert evaluate(committed, obs).admission == Admission.STALE


def test_admission_valid_successor_applies():
    committed = committed_after_G2()
    obs = observation(state_token(committed), 2,
                      [result("GTFOBins", emitted=emitted(ENTRY, ["GTFOBins"]))])
    res = evaluate(committed, obs)
    assert res.admission == Admission.APPLIED
    assert res.next_body["last_observation_id"] == 2
    assert res.next_body["last_observation_hash"] == observation_hash(obs)


@pytest.mark.parametrize(
    "admission_case",
    ["retry", "conflict", "invalid_successor", "stale", "precondition"],
)
def test_every_non_applied_admission_returns_null_report_and_no_mutation(admission_case):
    committed = committed_after_G2()
    obs = json.loads(G.G2_OBSERVATION)
    if admission_case == "conflict":
        next(r for r in obs["results"] if r["source"] == "GTFOBins")["resolved_revision"] = "b" * 40
    elif admission_case == "invalid_successor":
        obs["observation_id"] = 2
    elif admission_case == "stale":
        obs = observation(state_token(committed), 0, [])
    elif admission_case == "precondition":
        wrong = dict(state_token(committed))
        wrong["state_checksum"] = "sha256:" + "9" * 64
        obs = observation(wrong, 2, [])
    before = canonical_bytes(committed)
    res = evaluate(committed, obs)
    assert res.admission != Admission.APPLIED
    assert res.report is None
    assert res.next_body is None
    assert canonical_bytes(committed) == before


# --------------------------------------------------------------------------
# Freshness matrix (sections 9.4 and 10)
# --------------------------------------------------------------------------
def test_present_from_active_stays_active_streak_zero():
    state = body([entry(classification=Classification.ACTIVE, streak=0)])
    res = step(state, [result("GTFOBins", emitted=emitted(ENTRY, ["GTFOBins"]))])
    got = only_entry(res)
    assert (got["classification"], got["absence_streak"]) == (Classification.ACTIVE, 0)
    assert only_row(res)["aggregate_class"] == AggregateClass.PRESENT


def test_present_from_positive_streak_resets_it():
    state = body([entry(classification=Classification.NOT_OBSERVED, streak=2)])
    res = step(state, [result("GTFOBins", emitted=emitted(ENTRY, ["GTFOBins"]))])
    got = only_entry(res)
    assert (got["classification"], got["absence_streak"]) == (Classification.ACTIVE, 0)


def test_present_from_stale_candidate_reappears():
    state = body([entry(classification=Classification.STALE_CANDIDATE, streak=4)])
    res = step(state, [result("GTFOBins", emitted=emitted(ENTRY, ["GTFOBins"]))])
    got = only_entry(res)
    assert (got["classification"], got["absence_streak"]) == (Classification.ACTIVE, 0)


def test_first_qualifying_absence_from_active():
    state = body([entry(classification=Classification.ACTIVE, streak=0)])
    res = step(state, [result("GTFOBins")])                    # ok but not emitted
    got = only_entry(res)
    assert (got["classification"], got["absence_streak"]) == (Classification.NOT_OBSERVED, 1)
    assert only_row(res)["aggregate_class"] == AggregateClass.QUALIFYING_ABSENCE


def test_second_qualifying_absence():
    state = body([entry(classification=Classification.NOT_OBSERVED, streak=1)])
    got = only_entry(step(state, [result("GTFOBins")]))
    assert (got["classification"], got["absence_streak"]) == (Classification.NOT_OBSERVED, 2)


def test_third_qualifying_absence_reaches_stale_candidate():
    state = body([entry(classification=Classification.NOT_OBSERVED, streak=2)])
    got = only_entry(step(state, [result("GTFOBins")]))
    assert (got["classification"], got["absence_streak"]) == (Classification.STALE_CANDIDATE, 3)


def test_further_qualifying_absence_after_threshold():
    state = body([entry(classification=Classification.STALE_CANDIDATE, streak=3)])
    got = only_entry(step(state, [result("GTFOBins")]))
    assert (got["classification"], got["absence_streak"]) == (Classification.STALE_CANDIDATE, 4)


@pytest.mark.parametrize(
    "classification,streak",
    [
        (Classification.ACTIVE, 0),
        (Classification.NOT_OBSERVED, 2),
        (Classification.STALE_CANDIDATE, 3),
    ],
)
def test_hold_freezes_disposition_and_streak(classification, streak):
    state = body([entry(classification=classification, streak=streak)])
    res = step(state, [result("GTFOBins", status=SourceStatus.FAILED)])
    got = only_entry(res)
    assert (got["classification"], got["absence_streak"]) == (classification, streak)
    assert only_row(res)["aggregate_class"] == AggregateClass.HOLD


def test_not_run_owner_holds_and_never_counts_absence():
    state = body([entry(classification=Classification.ACTIVE, streak=0)])
    res = step(state, [])                                       # every source NOT_RUN
    got = only_entry(res)
    assert (got["classification"], got["absence_streak"]) == (Classification.ACTIVE, 0)
    assert only_row(res)["aggregate_class"] == AggregateClass.HOLD


def test_one_present_owner_among_absent_owners_yields_present():
    state = body([entry(owners=("GTFOBins", "LOLDrivers"),
                        sources=[{"source": "GTFOBins", "material_fingerprint": FP_A,
                                  "last_reliable_observation_id": 1,
                                  "upstream_identity": GTFO_ID},
                                 {"source": "LOLDrivers", "material_fingerprint": FP_A,
                                  "last_reliable_observation_id": 1,
                                  "upstream_identity": DRV_ID}])])
    res = step(state, [
        result("GTFOBins", emitted=emitted(ENTRY, ["GTFOBins", "LOLDrivers"])),
        result("LOLDrivers"),                                   # ok + absent, prior identity
    ])
    assert only_row(res)["aggregate_class"] == AggregateClass.PRESENT
    assert only_entry(res)["classification"] == Classification.ACTIVE


def test_all_healthy_owners_absent_yields_qualifying_absence():
    state = body([entry(owners=("GTFOBins", "LOLDrivers"),
                        sources=[{"source": "GTFOBins", "material_fingerprint": FP_A,
                                  "last_reliable_observation_id": 1,
                                  "upstream_identity": GTFO_ID},
                                 {"source": "LOLDrivers", "material_fingerprint": FP_A,
                                  "last_reliable_observation_id": 1,
                                  "upstream_identity": DRV_ID}])])
    res = step(state, [result("GTFOBins"), result("LOLDrivers")])
    assert only_row(res)["aggregate_class"] == AggregateClass.QUALIFYING_ABSENCE


def test_one_unhealthy_owner_blocks_qualifying_absence():
    state = body([entry(owners=("GTFOBins", "LOLDrivers"),
                        sources=[{"source": "GTFOBins", "material_fingerprint": FP_A,
                                  "last_reliable_observation_id": 1,
                                  "upstream_identity": GTFO_ID},
                                 {"source": "LOLDrivers", "material_fingerprint": FP_A,
                                  "last_reliable_observation_id": 1,
                                  "upstream_identity": DRV_ID}])])
    res = step(state, [result("GTFOBins"), result("LOLDrivers", status=SourceStatus.PARTIAL)])
    assert only_row(res)["aggregate_class"] == AggregateClass.HOLD
    assert only_entry(res)["absence_streak"] == 0


def test_continuity_hold_when_stable_owner_has_no_prior_identity():
    """Section 9.3: ok+absent STABLE with null prior identity => CONTINUITY_HOLD."""
    state = body([entry(classification=Classification.NOT_OBSERVED, initialized=False, streak=0,
                        sources=[empty_evidence("GTFOBins")])])
    res = step(state, [result("GTFOBins")])
    assert only_row(res)["aggregate_class"] == AggregateClass.HOLD
    assert only_entry(res)["absence_streak"] == 0


def test_none_mode_absence_always_holds():
    """LOLBAS/LOLAD/WADComs absence never qualifies (section 9.3)."""
    state = body([entry(entry_id="lolbas/x", owners=("LOLBAS",),
                        sources=[{"source": "LOLBAS", "material_fingerprint": FP_A,
                                  "last_reliable_observation_id": 1,
                                  "upstream_identity": None}])])
    res = step(state, [result("LOLBAS")])
    assert only_row(res)["aggregate_class"] == AggregateClass.HOLD


def test_conflicting_identity_blocks_with_hold():
    """Section 9.2 row 3: prior non-null, observed different => CONFLICT."""
    state = body([entry()])
    other = {"kind": "gtfobins_natural_key", "value": "other/function/ctx"}
    res = step(state, [result("GTFOBins", emitted=emitted(ENTRY, ["GTFOBins"], identity=other))])
    assert only_row(res)["aggregate_class"] == AggregateClass.HOLD
    got = only_entry(res)
    assert got["sources"][0]["upstream_identity"] == GTFO_ID       # frozen
    assert got["sources"][0]["material_fingerprint"] == FP_A


# --------------------------------------------------------------------------
# Evidence mutation gate (section 9.4)
# --------------------------------------------------------------------------
def test_present_updates_every_present_owner():
    state = body([entry(sources=[{"source": "GTFOBins", "material_fingerprint": FP_A,
                                  "last_reliable_observation_id": 1,
                                  "upstream_identity": GTFO_ID}])], obs_id=5)
    res = step(state, [result("GTFOBins", emitted=emitted(ENTRY, ["GTFOBins"], fingerprint=FP_B))])
    evidence = only_entry(res)["sources"][0]
    assert evidence["material_fingerprint"] == FP_B
    assert evidence["last_reliable_observation_id"] == 6


def test_non_present_aggregate_freezes_every_carried_field():
    """Round-6 replay: GTFOBins P1->P2 PRESENT + LOLDrivers CONTINUITY_HOLD => HOLD."""
    state = body([entry(owners=("GTFOBins", "LOLDrivers"),
                        sources=[{"source": "GTFOBins", "material_fingerprint": FP_A,
                                  "last_reliable_observation_id": 1,
                                  "upstream_identity": GTFO_ID},
                                 empty_evidence("LOLDrivers")])])
    res = step(state, [
        result("GTFOBins", emitted=emitted(ENTRY, ["GTFOBins", "LOLDrivers"], fingerprint=FP_B)),
        result("LOLDrivers"),                                   # ok+absent, prior identity null
    ])
    row = only_row(res)
    assert row["aggregate_class"] == AggregateClass.HOLD
    assert row["changed"] is False
    by_source = {e["source"]: e for e in only_entry(res)["sources"]}
    assert by_source["GTFOBins"]["material_fingerprint"] == FP_A      # frozen at P1
    assert by_source["GTFOBins"]["last_reliable_observation_id"] == 1
    assert by_source["LOLDrivers"] == empty_evidence("LOLDrivers")


def test_empty_evidence_is_preserved_under_hold():
    state = body([entry(classification=Classification.NOT_OBSERVED, initialized=False,
                        sources=[empty_evidence("GTFOBins")])])
    res = step(state, [result("GTFOBins", status=SourceStatus.FAILED)])
    assert only_entry(res)["sources"][0] == empty_evidence("GTFOBins")


def test_mixed_legal_tuples_are_preserved():
    state = body([entry(owners=("GTFOBins", "WADComs"),
                        sources=[{"source": "GTFOBins", "material_fingerprint": FP_A,
                                  "last_reliable_observation_id": 1,
                                  "upstream_identity": GTFO_ID},
                                 empty_evidence("WADComs")])])
    res = step(state, [result("GTFOBins", status=SourceStatus.FAILED)])
    by_source = {e["source"]: e for e in only_entry(res)["sources"]}
    assert by_source["GTFOBins"]["material_fingerprint"] == FP_A
    assert by_source["WADComs"] == empty_evidence("WADComs")


def test_gained_owner_starts_empty_and_lost_owner_is_removed():
    state = body([entry(owners=("GTFOBins", "WADComs"),
                        sources=[{"source": "GTFOBins", "material_fingerprint": FP_A,
                                  "last_reliable_observation_id": 1,
                                  "upstream_identity": GTFO_ID},
                                 empty_evidence("WADComs")])])
    res = step(state, [result("GTFOBins",
                              emitted=emitted(ENTRY, ["GTFOBins", "LOLDrivers"]))])
    got = only_entry(res)
    assert got["owner_sources"] == ["GTFOBins", "LOLDrivers"]
    by_source = {e["source"]: e for e in got["sources"]}
    assert set(by_source) == {"GTFOBins", "LOLDrivers"}
    assert by_source["LOLDrivers"] == empty_evidence("LOLDrivers")     # gained => EMPTY


# --------------------------------------------------------------------------
# Ambiguity (section 8.5)
# --------------------------------------------------------------------------
def test_existing_entry_becoming_ambiguous_freezes_arrays():
    state = body([entry(classification=Classification.STALE_CANDIDATE, streak=4)])
    conflicting = emitted(ENTRY, ["GTFOBins"])
    conflicting[ENTRY]["owner_evidence"] = {
        "declared_sources": ["WADComs"], "id_prefix": "gtfobins",
        "source_data_projects": ["GTFOBins"],
    }
    res = step(state, [result("GTFOBins", emitted=conflicting)])
    got = only_entry(res)
    assert got["owner_ambiguous"] is True
    assert got["classification"] == Classification.NOT_OBSERVED
    assert got["absence_streak"] == 0
    assert got["owner_sources"] == ["GTFOBins"]                  # UNCHANGED
    assert only_row(res)["aggregate_class"] == AggregateClass.HOLD


def test_new_ambiguous_id_is_persisted_with_empty_arrays():
    state = body([], obs_id=5)
    conflicting = emitted("gtfobins/new", ["GTFOBins"])
    conflicting["gtfobins/new"]["owner_evidence"] = {
        "declared_sources": ["WADComs"], "id_prefix": "gtfobins",
        "source_data_projects": ["GTFOBins"],
    }
    res = step(state, [result("GTFOBins", emitted=conflicting)])
    got = only_entry(res)
    assert got["owner_ambiguous"] is True
    assert got["owner_sources"] == [] and got["sources"] == []
    assert (got["classification"], got["initialized"], got["absence_streak"]) == (
        Classification.NOT_OBSERVED, True, 0)
    assert only_row(res) == {"entry_id": "gtfobins/new",
                             "classification": "NOT_OBSERVED",
                             "aggregate_class": "HOLD", "changed": False}


def test_ambiguity_resolution_returns_to_normal_transition():
    state = body([entry(ambiguous=True, classification=Classification.NOT_OBSERVED,
                        streak=0, owners=("GTFOBins",),
                        sources=[empty_evidence("GTFOBins")])])
    res = step(state, [result("GTFOBins", emitted=emitted(ENTRY, ["GTFOBins"]))])
    got = only_entry(res)
    assert got["owner_ambiguous"] is False
    assert got["classification"] == Classification.ACTIVE
    assert got["sources"][0]["material_fingerprint"] == FP_A


# --------------------------------------------------------------------------
# Report and ``changed`` (section 15)
# --------------------------------------------------------------------------
def test_changed_false_when_prior_fingerprint_is_null():
    """First sighting contributes a false term and cannot make changed true."""
    state = body([entry(classification=Classification.NOT_OBSERVED, initialized=False,
                        sources=[empty_evidence("GTFOBins")])])
    res = step(state, [result("GTFOBins", emitted=emitted(ENTRY, ["GTFOBins"]))])
    assert only_row(res)["changed"] is False


def test_changed_true_when_a_present_owner_fingerprint_differs():
    state = body([entry()])
    res = step(state, [result("GTFOBins", emitted=emitted(ENTRY, ["GTFOBins"], fingerprint=FP_B))])
    assert only_row(res)["changed"] is True


def test_changed_false_when_fingerprint_is_identical():
    state = body([entry()])
    res = step(state, [result("GTFOBins", emitted=emitted(ENTRY, ["GTFOBins"], fingerprint=FP_A))])
    assert only_row(res)["changed"] is False


def test_changed_is_an_or_over_all_present_owners():
    """One owner unchanged, one changed => true; the rule never picks one owner."""
    state = body([entry(owners=("GTFOBins", "LOLDrivers"),
                        sources=[{"source": "GTFOBins", "material_fingerprint": FP_A,
                                  "last_reliable_observation_id": 1,
                                  "upstream_identity": GTFO_ID},
                                 {"source": "LOLDrivers", "material_fingerprint": FP_A,
                                  "last_reliable_observation_id": 1,
                                  "upstream_identity": DRV_ID}])])
    both = ["GTFOBins", "LOLDrivers"]
    res = step(state, [
        result("GTFOBins", emitted=emitted(ENTRY, both, fingerprint=FP_A)),
        result("LOLDrivers", emitted=emitted(ENTRY, both, fingerprint=FP_B, identity=DRV_ID)),
    ])
    assert only_row(res)["aggregate_class"] == AggregateClass.PRESENT
    assert only_row(res)["changed"] is True


def test_changed_false_for_every_non_present_aggregate():
    state = body([entry()])
    for results in ([result("GTFOBins", status=SourceStatus.FAILED)], [result("GTFOBins")]):
        res = step(state, results)
        assert only_row(res)["aggregate_class"] != AggregateClass.PRESENT
        assert only_row(res)["changed"] is False


def test_head_advances_even_when_no_entry_changed():
    """Admitted observation != entry materially changed."""
    state = body([entry()], obs_id=5)
    res = step(state, [result("GTFOBins", emitted=emitted(ENTRY, ["GTFOBins"], fingerprint=FP_A))])
    assert res.next_body["last_observation_id"] == 6
    assert only_row(res)["changed"] is False
    assert only_entry(res) == state["entries"][0] | {
        "sources": [{"source": "GTFOBins", "material_fingerprint": FP_A,
                     "last_reliable_observation_id": 6, "upstream_identity": GTFO_ID}]}


def test_head_advances_when_every_entry_holds():
    state = body([entry()], obs_id=5)
    res = step(state, [result("GTFOBins", status=SourceStatus.FAILED)])
    assert res.next_body["last_observation_id"] == 6
    assert only_entry(res)["absence_streak"] == 0


def test_report_membership_is_prior_ids_union_emitted_ids():
    state = body([entry(entry_id="gtfobins/a"), entry(entry_id="gtfobins/b")])
    res = step(state, [result("GTFOBins", emitted=emitted("gtfobins/c", ["GTFOBins"]))])
    ids = [r["entry_id"] for r in res.report["entries"]]
    assert ids == ["gtfobins/a", "gtfobins/b", "gtfobins/c"]


def test_report_only_hold_id_creates_no_record_and_reports_not_observed():
    """Section 15 R5-B1: report-only new id is normatively NOT_OBSERVED, never null."""
    state = body([], obs_id=5)
    both = ["GTFOBins", "LOLDrivers"]
    res = step(state, [
        result("GTFOBins", emitted=emitted("gtfobins/new", both)),
        result("LOLDrivers"),                                   # ok+absent, prior EMPTY
    ])
    assert res.next_body["entries"] == []                       # no persistent record
    assert res.report["entries"] == [{"entry_id": "gtfobins/new",
                                      "classification": "NOT_OBSERVED",
                                      "aggregate_class": "HOLD", "changed": False}]


def test_report_is_sorted_and_canonical():
    state = body([entry(entry_id="gtfobins/b"), entry(entry_id="gtfobins/a")])
    res = step(state, [result("GTFOBins")])
    ids = [r["entry_id"] for r in res.report["entries"]]
    assert ids == sorted(ids)
    canonical_bytes(res.report)                                 # must serialize cleanly


# --------------------------------------------------------------------------
# Validator closure (section 15 of the mandate)
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "results",
    [
        [result("GTFOBins", emitted=emitted(ENTRY, ["GTFOBins"]))],
        [result("GTFOBins")],
        [result("GTFOBins", status=SourceStatus.FAILED)],
        [],
    ],
)
def test_successor_state_always_passes_the_frozen_static_validator(results):
    state = body([entry()])
    validate_body(state)                                        # input is valid
    res = step(state, results)
    validate_body(res.next_body)                                # output is valid
    serialize_state_file(res.next_body)


def test_streak_progression_stays_validator_legal_to_threshold_and_beyond():
    state = body([entry(classification=Classification.ACTIVE, streak=0)], obs_id=5)
    for _ in range(5):
        res = step(state, [result("GTFOBins")])
        validate_body(res.next_body)
        state = res.next_body
    assert state["entries"][0]["classification"] == Classification.STALE_CANDIDATE
    assert state["entries"][0]["absence_streak"] == 5


# --------------------------------------------------------------------------
# Purity, determinism and absence of hidden mutation
# --------------------------------------------------------------------------
def test_evaluate_does_not_mutate_its_inputs():
    state = body([entry()])
    obs = observation(state_token(state), 6,
                      [result("GTFOBins", emitted=emitted(ENTRY, ["GTFOBins"], fingerprint=FP_B))])
    state_before = canonical_bytes(state)
    obs_before = canonical_bytes(obs)
    evaluate(state, obs)
    assert canonical_bytes(state) == state_before
    assert canonical_bytes(obs) == obs_before


def test_successor_does_not_alias_the_input_state():
    state = body([entry()])
    res = step(state, [result("GTFOBins", emitted=emitted(ENTRY, ["GTFOBins"], fingerprint=FP_B))])
    res.next_body["entries"][0]["absence_streak"] = 99
    assert state["entries"][0]["absence_streak"] == 0


def test_non_canonical_result_order_is_rejected_not_silently_sorted():
    """Section 3: ``results`` is sorted by ``source`` in the canonical form.

    A reordered array is a different byte string and therefore a different
    observation hash, so the engine rejects it instead of re-sorting it — which
    would let two different byte strings admit as the same observation.
    """
    state = body([entry()])
    obs = observation(state_token(state), 6,
                      [result("GTFOBins", emitted=emitted(ENTRY, ["GTFOBins"]))])
    obs["results"].reverse()
    with pytest.raises(ObservationInvalid):
        evaluate(state, obs)


def test_canonically_built_observations_are_always_byte_stable():
    """Building the same logical observation repeatedly yields identical bytes."""
    state = body([entry()])
    token = state_token(state)
    results = [result("GTFOBins", emitted=emitted(ENTRY, ["GTFOBins"], fingerprint=FP_B))]
    reference = None
    for _ in range(8):
        obs = observation(token, 6, results)
        res = evaluate(state, obs)
        current = (res.admission, canonical_bytes(res.next_body), canonical_bytes(res.report))
        reference = reference or current
        assert current == reference


def test_repeated_evaluation_is_byte_identical():
    state = body([entry()])
    obs = observation(state_token(state), 6,
                      [result("GTFOBins", emitted=emitted(ENTRY, ["GTFOBins"], fingerprint=FP_B))])
    first = evaluate(state, obs)
    second = evaluate(state, obs)
    assert canonical_bytes(first.next_body) == canonical_bytes(second.next_body)
    assert canonical_bytes(first.report) == canonical_bytes(second.report)
    assert first.observation_hash == second.observation_hash


def test_dict_insertion_order_does_not_change_the_result():
    state = body([entry()])
    obs = observation(state_token(state), 6,
                      [result("GTFOBins", emitted=emitted(ENTRY, ["GTFOBins"], fingerprint=FP_B))])
    reference = canonical_bytes(evaluate(state, obs).next_body)

    def reorder(value, rng):
        if isinstance(value, dict):
            items = list(value.items())
            rng.shuffle(items)
            return {k: reorder(v, rng) for k, v in items}
        if isinstance(value, list):
            return [reorder(v, rng) for v in value]
        return value

    rng = random.Random(7)
    for _ in range(10):
        shuffled_state = reorder(copy.deepcopy(state), rng)
        shuffled_obs = reorder(copy.deepcopy(obs), rng)
        assert canonical_bytes(evaluate(shuffled_state, shuffled_obs).next_body) == reference


# --------------------------------------------------------------------------
# Hard-invalid observations (sections 4, 5.3, 6.0.1)
# --------------------------------------------------------------------------
def test_stable_owner_emitting_null_identity_is_hard_invalid():
    state = body([entry()])
    bad = emitted(ENTRY, ["GTFOBins"], identity=None)
    obs = observation(state_token(state), 6, [result("GTFOBins", emitted=bad)])
    with pytest.raises(ObservationInvalid):
        evaluate(state, obs)


def test_none_owner_emitting_an_identity_is_hard_invalid():
    state = body([entry(entry_id="lolbas/x", owners=("LOLBAS",),
                        sources=[empty_evidence("LOLBAS")],
                        classification=Classification.NOT_OBSERVED, initialized=False)])
    bad = emitted("lolbas/x", ["LOLBAS"], identity=GTFO_ID, prefix="lolbas")
    obs = observation(state_token(state), 6, [result("LOLBAS", emitted=bad)])
    with pytest.raises(ObservationInvalid):
        evaluate(state, obs)


def test_missing_source_result_is_hard_invalid():
    state = body([entry()])
    obs = {"observation_id": 6, "base_state": state_token(state),
           "results": [result("GTFOBins")]}
    with pytest.raises(ObservationInvalid):
        evaluate(state, obs)


def test_duplicate_source_result_is_hard_invalid():
    state = body([entry()])
    obs = observation(state_token(state), 6, [result("GTFOBins")])
    obs["results"].append(result("GTFOBins"))
    with pytest.raises(ObservationInvalid):
        evaluate(state, obs)


def test_acquired_ok_revision_biconditional_is_enforced():
    state = body([entry()])
    bad = result("GTFOBins")
    bad["resolved_revision"] = None
    obs = observation(state_token(state), 6, [bad])
    with pytest.raises(ObservationInvalid):
        evaluate(state, obs)

    bad2 = not_run("GTFOBins")
    bad2["resolved_revision"] = REV
    obs2 = observation(state_token(state), 6, [bad2])
    with pytest.raises(ObservationInvalid):
        evaluate(state, obs2)


def test_count_equation_is_enforced():
    state = body([entry()])
    bad = result("GTFOBins")
    bad["inputs_total"] = 3
    obs = observation(state_token(state), 6, [bad])
    with pytest.raises(ObservationInvalid):
        evaluate(state, obs)


# ==========================================================================
# Codex Round-1 B1 — canonical observation implies canonical transition
#
# ``canonical_bytes`` NFC-normalizes before hashing (section 3), so observation
# identity is a property of the canonical form. Every semantic comparison the
# engine makes must therefore be made on that same form: two observations with
# identical canonical bytes must produce byte-identical successors.
# ==========================================================================
#: Genuinely distinct Python strings that share one canonical form.
NFC_E = "é"            # LATIN SMALL LETTER E WITH ACUTE
DEC_E = "é"           # e + COMBINING ACUTE ACCENT
NFC_CAFE = "caf" + NFC_E
DEC_CAFE = "caf" + DEC_E


def test_the_two_unicode_spellings_really_are_distinct_strings():
    """Guard: a copy-paste slip here would make every B1 test vacuous."""
    assert NFC_CAFE != DEC_CAFE
    assert len(NFC_CAFE) == 4 and len(DEC_CAFE) == 5
    assert unicodedata.normalize("NFC", DEC_CAFE) == NFC_CAFE


def stable_identity(value):
    return {"kind": "gtfobins_natural_key", "value": value}


def cafe_state(stored_value):
    """ACTIVE GTFOBins entry whose stored identity is ``stored_value``."""
    return body(
        [entry(sources=[{"source": "GTFOBins", "material_fingerprint": FP_A,
                         "last_reliable_observation_id": 1,
                         "upstream_identity": stable_identity(stored_value)}])],
        obs_id=5,
    )


def cafe_observation(state, observed_value):
    return observation(
        state_token(state), 6,
        [result("GTFOBins",
                emitted=emitted(ENTRY, ["GTFOBins"], fingerprint=FP_B,
                                identity=stable_identity(observed_value)))],
    )


def test_B1_canonical_equivalent_identities_are_one_observation():
    """Same canonical bytes and hash — the precondition for the whole property."""
    state = cafe_state(NFC_CAFE)
    o_nfc = cafe_observation(state, NFC_CAFE)
    o_dec = cafe_observation(state, DEC_CAFE)
    assert o_nfc != o_dec                                   # distinct in memory
    assert canonical_bytes(o_nfc) == canonical_bytes(o_dec)  # one canonical form
    assert observation_hash(o_nfc) == observation_hash(o_dec)


@pytest.mark.parametrize("stored", [NFC_CAFE, DEC_CAFE])
def test_B1_canonical_equivalent_observations_transition_identically(stored):
    """The Codex reproducer, run against both spellings of the *stored* identity."""
    state = cafe_state(stored)
    a = evaluate(copy.deepcopy(state), cafe_observation(state, NFC_CAFE))
    b = evaluate(copy.deepcopy(state), cafe_observation(state, DEC_CAFE))

    assert a.admission == b.admission == Admission.APPLIED
    assert a.observation_hash == b.observation_hash
    assert a.report == b.report
    assert a.next_body == b.next_body
    assert canonical_bytes(a.next_body) == canonical_bytes(b.next_body)
    assert canonical_bytes(a.report) == canonical_bytes(b.report)


def test_B1_the_pre_fix_divergence_is_gone_end_to_end():
    """Pre-fix, the decomposed spelling produced CONFLICT/HOLD and frozen evidence."""
    state = cafe_state(NFC_CAFE)
    for observed in (NFC_CAFE, DEC_CAFE):
        res = evaluate(copy.deepcopy(state), cafe_observation(state, observed))
        row = only_row(res)
        assert row["classification"] == Classification.ACTIVE
        assert row["aggregate_class"] == AggregateClass.PRESENT
        assert row["changed"] is True
        evidence = only_entry(res)["sources"][0]
        assert evidence["material_fingerprint"] == FP_B          # evidence updated
        assert evidence["last_reliable_observation_id"] == 6
        assert evidence["upstream_identity"] == stable_identity(NFC_CAFE)


def test_B1_second_probe_entry_id_is_also_canonically_compared():
    """An independent semantically-compared string field: the entry id itself."""
    nfc_id = "gtfobins/caf" + NFC_E + "/file-read"
    dec_id = "gtfobins/caf" + DEC_E + "/file-read"
    assert nfc_id != dec_id
    state = body([entry(entry_id=nfc_id)], obs_id=5)
    obs = observation(
        state_token(state), 6,
        [result("GTFOBins", emitted=emitted(dec_id, ["GTFOBins"], fingerprint=FP_B))],
    )
    res = evaluate(copy.deepcopy(state), obs)
    # The decomposed emission updates the existing entry; it never creates a
    # second, canonically identical record.
    assert res.admission == Admission.APPLIED
    assert [e["entry_id"] for e in res.next_body["entries"]] == [nfc_id]
    assert only_entry(res)["sources"][0]["material_fingerprint"] == FP_B
    assert only_row(res)["changed"] is True


def test_B1_evaluation_does_not_mutate_caller_owned_inputs():
    """Canonicalization builds frozen copies; the caller's objects are untouched."""
    state = cafe_state(NFC_CAFE)
    obs = cafe_observation(state, DEC_CAFE)
    token = copy.deepcopy(state_token(state))
    state_before = copy.deepcopy(state)
    obs_before = copy.deepcopy(obs)
    token_before = copy.deepcopy(token)

    res = evaluate(state, obs, arrival_token=token)
    assert res.admission == Admission.APPLIED
    assert state == state_before
    assert obs == obs_before
    assert token == token_before
    # The decomposed spelling survives in the caller's object verbatim.
    identity = obs["results"][0]["emitted_entries"][ENTRY]["upstream_identity"]
    assert identity["value"] == DEC_CAFE


def test_B1_rejected_observation_mutates_nothing_either():
    state = cafe_state(NFC_CAFE)
    obs = cafe_observation(state, DEC_CAFE)
    del obs["results"][0]["unmapped"]                       # hard-invalid
    state_before = copy.deepcopy(state)
    obs_before = copy.deepcopy(obs)
    with pytest.raises(ObservationInvalid):
        evaluate(state, obs)
    assert state == state_before and obs == obs_before


def test_B1_duplicate_nfc_emitted_keys_are_hard_invalid():
    """Section 4: ``keys(emitted_entries)`` has no duplicate NFC-normalized id."""
    state = body([entry()])
    bad = {}
    bad.update(emitted("gtfobins/caf" + NFC_E, ["GTFOBins"]))
    bad.update(emitted("gtfobins/caf" + DEC_E, ["GTFOBins"], fingerprint=FP_B))
    assert len(bad) == 2                                    # distinct dict keys
    obs = observation(state_token(state), 6, [result("GTFOBins", emitted=bad)])
    with pytest.raises(ObservationInvalid):
        evaluate(state, obs)


# ==========================================================================
# Codex Round-1 B2 — byte-local hard-invalid observations never reach admission
#
# Every case below is forbidden by the frozen spec and must be rejected before
# any admission branch, state mutation, head advance or report (section 4:
# "Validation runs entirely before admission and transition").
# ==========================================================================
def valid_state():
    return body([entry()], obs_id=5)


def mutated(mutate, source="GTFOBins", emitted_entries=None):
    """Build a valid observation, then apply ``mutate`` to its ``source`` result."""
    state = valid_state()
    base = result(source, emitted=emitted_entries) if emitted_entries else result(source)
    obs = observation(state_token(state), 6, [base])
    target = next(r for r in obs["results"] if r["source"] == source)
    mutate(obs, target)
    return state, obs


def assert_hard_invalid(state, obs):
    """No admission, no successor, no report — and no mutation of the inputs."""
    before = canonical_bytes(state)
    with pytest.raises(ObservationInvalid):
        evaluate(state, obs)
    assert canonical_bytes(state) == before


# --- B2 Case A: undeclared / missing AdapterResult fields ------------------
def test_B2_A_undeclared_adapter_result_field_is_hard_invalid():
    state, obs = mutated(lambda o, r: r.update({"undeclared_field": True}))
    assert_hard_invalid(state, obs)


def test_B2_A_golden_G2_plus_one_undeclared_field_is_hard_invalid():
    """The exact Codex reproducer: frozen G2 with one extra AdapterResult field."""
    obs = json.loads(G.G2_OBSERVATION)
    next(r for r in obs["results"] if r["source"] == "GTFOBins")["extra"] = 1
    assert_hard_invalid(fixture_genesis(), obs)


def test_B2_missing_required_adapter_result_field_is_hard_invalid():
    state, obs = mutated(lambda o, r: r.pop("duplicate_ids"))
    assert_hard_invalid(state, obs)


def test_B2_undeclared_top_level_observation_field_is_hard_invalid():
    state = valid_state()
    obs = observation(state_token(state), 6, [result("GTFOBins")])
    obs["extra"] = 1
    assert_hard_invalid(state, obs)


# --- B2 Case B: status / primary_reason inconsistency ----------------------
def test_B2_B_status_ok_with_a_candidate_reason_is_hard_invalid():
    """The exact Codex reproducer: ``status:"ok"`` + ``primary_reason:"PARSE_ERROR"``."""
    state, obs = mutated(lambda o, r: r.update({"primary_reason": "PARSE_ERROR"}))
    assert_hard_invalid(state, obs)


def test_B2_reason_not_derived_from_the_present_reasons_is_hard_invalid():
    """Section 7.2: primary_reason is the lowest-ranked *present* reason."""
    def mutate(o, r):
        r["status"] = SourceStatus.FAILED
        r["primary_reason"] = "IO_ERROR"                    # rank 4, not present
        r["rejected"] = [{"input_ref": candidate_ref("GTFOBins"), "code": "PARSE_ERROR"}]
        r["inputs_total"] = r["parsed_ok"] + 1
    state, obs = mutated(mutate)
    assert_hard_invalid(state, obs)


def test_B2_status_not_derived_from_the_reason_is_hard_invalid():
    def mutate(o, r):
        r["status"] = SourceStatus.PARTIAL                  # PARSE_ERROR is failed
        r["primary_reason"] = "PARSE_ERROR"
        r["rejected"] = [{"input_ref": candidate_ref("GTFOBins"), "code": "PARSE_ERROR"}]
        r["inputs_total"] = r["parsed_ok"] + 1
    state, obs = mutated(mutate)
    assert_hard_invalid(state, obs)


@pytest.mark.parametrize("status,reason", [
    (SourceStatus.UNKNOWN, "NONE"),          # unknown iff NOT_RUN
    (SourceStatus.OK, "NOT_RUN"),
])
def test_B2_not_run_biconditional_is_enforced(status, reason):
    state, obs = mutated(lambda o, r: r.update({"status": status, "primary_reason": reason}))
    assert_hard_invalid(state, obs)


def test_B2_not_run_shape_must_be_exact():
    state = valid_state()
    bad = not_run("GTFOBins")
    bad["inputs_total"] = 1                                 # §6.1 pins this to 0
    obs = observation(state_token(state), 6, [bad])
    assert_hard_invalid(state, obs)


def test_B2_invalid_status_and_reason_vocabulary_are_hard_invalid():
    state, obs = mutated(lambda o, r: r.update({"status": "OK"}))       # case-sensitive
    assert_hard_invalid(state, obs)
    state, obs = mutated(lambda o, r: r.update({"primary_reason": "WHATEVER"}))
    assert_hard_invalid(state, obs)


# --- B2 Case C: material fingerprint syntax --------------------------------
def test_B2_C_invalid_fingerprint_behind_a_hold_is_hard_invalid():
    """Validation is not bypassed because the transition would freeze the evidence."""
    bad = emitted(ENTRY, ["GTFOBins"], fingerprint="sha256:not-hex")
    state, obs = mutated(
        lambda o, r: r.update({
            "status": SourceStatus.FAILED,
            "primary_reason": "PARSE_ERROR",
            "rejected": [{"input_ref": candidate_ref("GTFOBins"), "code": "PARSE_ERROR"}],
            "inputs_total": r["parsed_ok"] + 1,
        }),
        emitted_entries=bad,
    )
    assert_hard_invalid(state, obs)


@pytest.mark.parametrize("fingerprint", [
    "sha256:" + "a" * 63,                    # too short
    "sha256:" + "A" * 64,                    # uppercase hex
    "sha256:" + "a" * 64 + "\n",             # trailing newline
    "sha1:" + "a" * 64,                      # wrong algorithm
    None,                                    # never null
])
def test_B2_invalid_material_fingerprints_are_hard_invalid(fingerprint):
    state, obs = mutated(
        lambda o, r: None,
        emitted_entries=emitted(ENTRY, ["GTFOBins"], fingerprint=fingerprint),
    )
    assert_hard_invalid(state, obs)


def test_B2_emitted_entry_field_set_must_be_exact():
    bad = emitted(ENTRY, ["GTFOBins"])
    bad[ENTRY]["extra"] = 1
    state, obs = mutated(lambda o, r: None, emitted_entries=bad)
    assert_hard_invalid(state, obs)


def test_B2_owner_evidence_field_set_must_be_exact():
    bad = emitted(ENTRY, ["GTFOBins"])
    bad[ENTRY]["owner_evidence"]["extra"] = 1
    state, obs = mutated(lambda o, r: None, emitted_entries=bad)
    assert_hard_invalid(state, obs)


def test_B2_identity_field_set_must_be_exact():
    bad = emitted(ENTRY, ["GTFOBins"], identity={"kind": "gtfobins_natural_key",
                                                 "value": "x", "extra": 1})
    state, obs = mutated(lambda o, r: None, emitted_entries=bad)
    assert_hard_invalid(state, obs)


@pytest.mark.parametrize("identity", [
    {"kind": "loldrivers_id", "value": "x"},          # wrong kind for GTFOBins
    {"kind": "gtfobins_natural_key", "value": ""},    # empty value
])
def test_B2_stable_identity_shape_is_enforced(identity):
    state, obs = mutated(lambda o, r: None,
                         emitted_entries=emitted(ENTRY, ["GTFOBins"], identity=identity))
    assert_hard_invalid(state, obs)


def test_B2_entry_id_without_a_valid_prefix_owner_is_hard_invalid():
    state, obs = mutated(
        lambda o, r: None,
        emitted_entries=emitted("nosuchproject/x", ["GTFOBins"], prefix="nosuchproject"),
    )
    assert_hard_invalid(state, obs)


# --- B2 Case D: emitter membership (section 8.4) ---------------------------
def test_B2_D_emitter_outside_the_resolved_owner_set_is_hard_invalid():
    """The exact Codex reproducer: WADComs emits a GTFOBins-owned id."""
    state = valid_state()
    wad = result("WADComs",
                 emitted=emitted("gtfobins/other", ["GTFOBins"], identity=None))
    obs = observation(state_token(state), 6,
                      [result("GTFOBins", emitted=emitted(ENTRY, ["GTFOBins"])), wad])
    assert_hard_invalid(state, obs)


def test_B2_D_co_emitter_outside_the_resolved_owner_set_is_hard_invalid():
    state = valid_state()
    shared = emitted(ENTRY, ["GTFOBins"])
    wad_copy = copy.deepcopy(shared)
    wad_copy[ENTRY]["upstream_identity"] = None             # WADComs is NONE mode
    obs = observation(state_token(state), 6,
                      [result("GTFOBins", emitted=shared), result("WADComs", emitted=wad_copy)])
    assert_hard_invalid(state, obs)


# --- B2: source cardinality, revision, counts, ordering --------------------
def test_B2_unknown_source_is_hard_invalid():
    state = valid_state()
    obs = observation(state_token(state), 6, [result("GTFOBins")])
    obs["results"][0]["source"] = "NotASource"
    assert_hard_invalid(state, obs)


@pytest.mark.parametrize("revision", ["c" * 39, "C" * 40, "g" * 40, "c" * 41])
def test_B2_invalid_resolved_revision_is_hard_invalid(revision):
    state, obs = mutated(lambda o, r: r.update({"resolved_revision": revision}))
    assert_hard_invalid(state, obs)


@pytest.mark.parametrize("field,value", [
    ("inputs_total", -1), ("parsed_ok", -1),
    ("inputs_total", 1.0), ("parsed_ok", True),
])
def test_B2_invalid_counts_are_hard_invalid(field, value):
    state, obs = mutated(lambda o, r: r.update({field: value}))
    assert_hard_invalid(state, obs)


def test_B2_acquired_with_zero_candidates_must_be_empty_input_set():
    """Section 7.2a rank 2 — the exact shape the old test builder violated."""
    def mutate(o, r):
        r["inputs_total"] = 0
        r["parsed_ok"] = 0
        r["emitted_entries"] = {}
    state, obs = mutated(mutate)
    assert_hard_invalid(state, obs)


def test_B2_unacquired_run_result_must_be_acquisition_failed():
    def mutate(o, r):
        r["acquired_ok"] = False
        r["resolved_revision"] = None
    state, obs = mutated(mutate)
    assert_hard_invalid(state, obs)


def test_B2_results_must_be_in_canonical_source_order():
    state = valid_state()
    obs = observation(state_token(state), 6, [result("GTFOBins")])
    obs["results"][0], obs["results"][1] = obs["results"][1], obs["results"][0]
    assert_hard_invalid(state, obs)


def test_B2_rejected_must_be_ordered_by_input_ref_then_code():
    def mutate(o, r):
        r["status"] = SourceStatus.FAILED
        r["primary_reason"] = "PARSE_ERROR"
        r["rejected"] = [
            {"input_ref": candidate_ref("GTFOBins", "b.md"), "code": "PARSE_ERROR"},
            {"input_ref": candidate_ref("GTFOBins", "a.md"), "code": "PARSE_ERROR"},
        ]
        r["inputs_total"] = r["parsed_ok"] + 2
    state, obs = mutated(mutate)
    assert_hard_invalid(state, obs)


def test_B2_duplicate_ids_must_be_sorted_and_de_duplicated():
    def mutate(o, r):
        r["status"] = SourceStatus.FAILED
        r["primary_reason"] = "DUPLICATE_ID"
        r["rejected"] = [{"input_ref": candidate_ref("GTFOBins"), "code": "DUPLICATE_ID"}]
        r["inputs_total"] = r["parsed_ok"] + 1
        r["duplicate_ids"] = ["gtfobins/b", "gtfobins/a"]
    state, obs = mutated(mutate)
    assert_hard_invalid(state, obs)


def test_B2_duplicate_ids_and_duplicate_id_rejections_imply_each_other():
    def only_ids(o, r):
        r["duplicate_ids"] = ["gtfobins/a"]                 # no DUPLICATE_ID rejection
    state, obs = mutated(only_ids)
    assert_hard_invalid(state, obs)

    def only_rejection(o, r):
        r["status"] = SourceStatus.FAILED
        r["primary_reason"] = "DUPLICATE_ID"
        r["rejected"] = [{"input_ref": candidate_ref("GTFOBins"), "code": "DUPLICATE_ID"}]
        r["inputs_total"] = r["parsed_ok"] + 1              # duplicate_ids stays []
    state, obs = mutated(only_rejection)
    assert_hard_invalid(state, obs)


def test_B2_a_colliding_id_never_emits():
    def mutate(o, r):
        r["status"] = SourceStatus.FAILED
        r["primary_reason"] = "DUPLICATE_ID"
        r["rejected"] = [{"input_ref": candidate_ref("GTFOBins"), "code": "DUPLICATE_ID"}]
        r["inputs_total"] = r["parsed_ok"] + 1
        r["duplicate_ids"] = [ENTRY]
    state, obs = mutated(mutate, emitted_entries=emitted(ENTRY, ["GTFOBins"]))
    assert_hard_invalid(state, obs)


def test_B2_zero_parsed_candidates_cannot_emit():
    def mutate(o, r):
        r["status"] = SourceStatus.FAILED
        r["primary_reason"] = "PARSE_ERROR"
        r["parsed_ok"] = 0
        r["rejected"] = [{"input_ref": candidate_ref("GTFOBins"), "code": "PARSE_ERROR"}]
        r["inputs_total"] = 1
    state, obs = mutated(mutate, emitted_entries=emitted(ENTRY, ["GTFOBins"]))
    assert_hard_invalid(state, obs)


# --- B2: candidate reject / unmapped enums and references ------------------
@pytest.mark.parametrize("code", ["ACQUISITION_FAILED", "EMPTY_INPUT_SET",
                                  "SUPPRESSING_UNMAPPED", "NOT_A_CODE"])
def test_B2_rejected_code_must_be_a_candidate_reject_enum_member(code):
    """Section 7.2a: source-level values MUST NOT occur in ``rejected[].code``."""
    def mutate(o, r):
        r["status"] = SourceStatus.FAILED
        r["primary_reason"] = "PARSE_ERROR"
        r["rejected"] = [{"input_ref": candidate_ref("GTFOBins"), "code": code}]
        r["inputs_total"] = r["parsed_ok"] + 1
    state, obs = mutated(mutate)
    assert_hard_invalid(state, obs)


def test_B2_rejected_element_field_set_must_be_exact():
    def mutate(o, r):
        r["status"] = SourceStatus.FAILED
        r["primary_reason"] = "PARSE_ERROR"
        r["rejected"] = [{"input_ref": candidate_ref("GTFOBins"),
                          "code": "PARSE_ERROR", "extra": 1}]
        r["inputs_total"] = r["parsed_ok"] + 1
    state, obs = mutated(mutate)
    assert_hard_invalid(state, obs)


@pytest.mark.parametrize("ref", [
    "_gtfobins/a/../b#",                    # not normalized
    "_gtfobins/a//b#",                      # not normalized
    "_gtfobins/a#b#",                       # unescaped '#'
    "yml/a.yml#",                           # wrong source prefix
    "_gtfobins/a.md",                       # missing locator
    "_gtfobins/a.md#row=0",                 # ROW is LOLAD-only (§6.2.1)
    "_gtfobins/a.md#row=00",                # leading zero
    "_gtfobins/a%2Zb#",                     # bad escape
])
def test_B2_non_canonical_input_refs_are_hard_invalid(ref):
    def mutate(o, r):
        r["status"] = SourceStatus.FAILED
        r["primary_reason"] = "PARSE_ERROR"
        r["rejected"] = [{"input_ref": ref, "code": "PARSE_ERROR"}]
        r["inputs_total"] = r["parsed_ok"] + 1
    state, obs = mutated(mutate)
    assert_hard_invalid(state, obs)


def test_B2_unmapped_code_must_carry_its_exact_suppressing_bit():
    def mutate(o, r):
        r["unmapped"] = [{"input_ref": candidate_ref("GTFOBins"),
                          "code": "EMPTY_CODE_CONTEXT", "suppressing": True}]
    state, obs = mutated(mutate)
    assert_hard_invalid(state, obs)


def test_B2_unknown_unmapped_code_is_hard_invalid():
    def mutate(o, r):
        r["unmapped"] = [{"input_ref": candidate_ref("GTFOBins"),
                          "code": "UNKNOWN_WHATEVER", "suppressing": False}]
    state, obs = mutated(mutate)
    assert_hard_invalid(state, obs)


def test_B2_suppressing_diagnostic_must_derive_suppressing_unmapped():
    """A suppressing bit raises SUPPRESSING_UNMAPPED (partial), not ``ok``."""
    def mutate(o, r):
        r["unmapped"] = [{"input_ref": candidate_ref("GTFOBins"),
                          "code": "UNKNOWN_FUNCTION", "suppressing": True}]
        # status/reason deliberately left at ok/NONE
    state, obs = mutated(mutate)
    assert_hard_invalid(state, obs)


# --- B2: base_state well-formedness (section 5.3) --------------------------
def test_B2_base_state_must_be_a_complete_well_formed_token():
    state = valid_state()
    obs = observation(state_token(state), 6, [result("GTFOBins")])
    obs["base_state"]["state_checksum"] = "not-a-digest"
    assert_hard_invalid(state, obs)


def test_B2_genesis_base_token_requires_the_all_zero_hash():
    state = valid_state()
    token = dict(state_token(state))
    token["last_observation_id"] = 0
    token["last_observation_hash"] = "sha256:" + "e" * 64
    obs = observation(token, 1, [result("GTFOBins")])
    assert_hard_invalid(state, obs)


# ==========================================================================
# Valid boundary controls — validation must not be over-strict
# ==========================================================================
def test_control_empty_input_set_shape_is_valid_and_holds():
    state = valid_state()
    obs = observation(state_token(state), 6, [empty_input("GTFOBins")])
    res = evaluate(state, obs)
    assert res.admission == Admission.APPLIED
    assert only_row(res)["aggregate_class"] == AggregateClass.HOLD
    assert only_row(res)["changed"] is False


def test_control_acquisition_failed_shape_is_valid_and_holds():
    state = valid_state()
    obs = observation(state_token(state), 6, [acquisition_failed("GTFOBins")])
    res = evaluate(state, obs)
    assert res.admission == Admission.APPLIED
    assert only_row(res)["aggregate_class"] == AggregateClass.HOLD
    # Section 9.4: an unhealthy aggregate freezes every carried evidence field.
    assert only_entry(res)["sources"][0]["material_fingerprint"] == FP_A
    assert only_entry(res)["sources"][0]["last_reliable_observation_id"] == 1


def test_control_candidate_failure_retains_parsed_sibling_emissions():
    """Section 7.2d — a failed result may still carry a sibling's emissions."""
    state = valid_state()
    bad = result("GTFOBins", status=SourceStatus.FAILED,
                 emitted=emitted(ENTRY, ["GTFOBins"], fingerprint=FP_B))
    assert bad["parsed_ok"] == 1 and len(bad["rejected"]) == 1
    assert bad["inputs_total"] == 2
    obs = observation(state_token(state), 6, [bad])
    res = evaluate(state, obs)
    assert res.admission == Admission.APPLIED
    # status != ok, so the emission supplies HEALTH_HOLD, never PRESENT (§9.1).
    assert only_row(res)["aggregate_class"] == AggregateClass.HOLD
    assert only_entry(res)["sources"][0]["material_fingerprint"] == FP_A


def test_control_non_suppressing_diagnostic_keeps_the_result_ok():
    state = valid_state()
    healthy = result("GTFOBins", emitted=emitted(ENTRY, ["GTFOBins"], fingerprint=FP_B))
    healthy["unmapped"] = [{"input_ref": candidate_ref("GTFOBins"),
                            "code": "EMPTY_CODE_CONTEXT", "suppressing": False}]
    res = evaluate(state, observation(state_token(state), 6, [healthy]))
    assert res.admission == Admission.APPLIED
    assert only_row(res)["aggregate_class"] == AggregateClass.PRESENT


def test_control_suppressing_diagnostic_derives_partial():
    state = valid_state()
    partial = result("GTFOBins", emitted=emitted(ENTRY, ["GTFOBins"]))
    partial["unmapped"] = [{"input_ref": candidate_ref("GTFOBins"),
                            "code": "UNKNOWN_FUNCTION", "suppressing": True}]
    partial["status"] = SourceStatus.PARTIAL
    partial["primary_reason"] = "SUPPRESSING_UNMAPPED"
    res = evaluate(state, observation(state_token(state), 6, [partial]))
    assert res.admission == Admission.APPLIED
    assert only_row(res)["aggregate_class"] == AggregateClass.HOLD


def test_control_valid_lolad_row_reference_is_accepted():
    state = body([entry(entry_id="lolad/x", owners=("LOLAD",),
                        sources=[empty_evidence("LOLAD")],
                        classification=Classification.NOT_OBSERVED, initialized=False)])
    lolad = result("LOLAD", status=SourceStatus.PARTIAL)
    lolad["rejected"] = [{"input_ref": canonical_input_ref("LOLAD", "index.html", ROW(0)),
                          "code": "MALFORMED_RECORD"}]
    assert lolad["rejected"][0]["input_ref"] == "index.html#row=0"
    res = evaluate(state, observation(state_token(state), 6, [lolad]))
    assert res.admission == Admission.APPLIED


def test_control_multi_owner_emitted_entry_is_valid():
    both = ["GTFOBins", "LOLDrivers"]
    state = body([entry(owners=tuple(both), sources=[
        {"source": "GTFOBins", "material_fingerprint": FP_A,
         "last_reliable_observation_id": 1, "upstream_identity": GTFO_ID},
        {"source": "LOLDrivers", "material_fingerprint": FP_A,
         "last_reliable_observation_id": 1, "upstream_identity": DRV_ID}])])
    obs = observation(state_token(state), 6, [
        result("GTFOBins", emitted=emitted(ENTRY, both, fingerprint=FP_B)),
        result("LOLDrivers", emitted=emitted(ENTRY, both, fingerprint=FP_B,
                                             identity=DRV_ID)),
    ])
    res = evaluate(state, obs)
    assert res.admission == Admission.APPLIED
    assert only_row(res)["aggregate_class"] == AggregateClass.PRESENT


def test_control_frozen_G2_is_still_admitted_unchanged():
    """The strongest over-strictness control: the printed golden observation."""
    res = evaluate(fixture_genesis(), json.loads(G.G2_OBSERVATION))
    assert res.admission == Admission.APPLIED
    assert canonical_bytes(res.next_body) == G.G3_BODY.encode("utf-8")


# ==========================================================================
# Determinism of the canonical binding
# ==========================================================================
def test_B1_canonical_equivalence_is_insertion_order_independent():
    state = cafe_state(NFC_CAFE)
    obs = cafe_observation(state, DEC_CAFE)
    shuffled = json.loads(json.dumps(obs))
    entries = list(shuffled["results"][0]["emitted_entries"][ENTRY].items())
    random.Random(7).shuffle(entries)
    shuffled["results"][0]["emitted_entries"][ENTRY] = dict(entries)
    a = evaluate(copy.deepcopy(state), obs)
    b = evaluate(copy.deepcopy(state), shuffled)
    assert canonical_bytes(a.next_body) == canonical_bytes(b.next_body)
    assert a.observation_hash == b.observation_hash


# ==========================================================================
# Codex Round-2 blocker — the reserved invalid-path sentinel is context-sensitive
#
# §6.2.1 gives a path-invalid candidate exactly one terminal disposition: a
# MALFORMED_RECORD rejection with zero emissions (§7.2c step 1 repeats it), and
# §6.2.3 adds that such a candidate "cannot emit diagnostics". So the sentinel is
# legal only in ``rejected`` and only with MALFORMED_RECORD, never in ``unmapped``.
# ==========================================================================
def sentinel(source="GTFOBins"):
    return invalid_path_ref(source)


def test_sentinel_is_the_reserved_reference_shape():
    """Guard: the sentinel must not collide with any valid record reference."""
    assert sentinel() == "_gtfobins/#invalid-path"
    assert sentinel("LOLAD") == "#invalid-path"


def test_R2_sentinel_in_rejected_with_a_non_malformed_code_is_hard_invalid():
    def mutate(o, r):
        r["status"] = SourceStatus.FAILED
        r["primary_reason"] = "PARSE_ERROR"
        r["rejected"] = [{"input_ref": sentinel(), "code": "PARSE_ERROR"}]
        r["inputs_total"] = r["parsed_ok"] + 1
    state, obs = mutated(mutate)
    with pytest.raises(ObservationInvalid, match="MALFORMED_RECORD"):
        evaluate(state, obs)


@pytest.mark.parametrize("code", ["PARSE_ERROR", "IO_ERROR", "DUPLICATE_ID",
                                  "MISSING_REQUIRED_FIELD", "NORMALIZED_PATH_COLLISION"])
def test_R2_sentinel_requires_malformed_record_for_every_other_code(code):
    def mutate(o, r):
        r["status"] = SourceStatus.FAILED if code != "MISSING_REQUIRED_FIELD" else SourceStatus.PARTIAL
        r["primary_reason"] = code
        r["rejected"] = [{"input_ref": sentinel(), "code": code}]
        r["inputs_total"] = r["parsed_ok"] + 1
        if code == "DUPLICATE_ID":
            r["duplicate_ids"] = ["gtfobins/a"]
    state, obs = mutated(mutate)
    assert_hard_invalid(state, obs)


def test_R2_sentinel_in_unmapped_is_hard_invalid():
    """A path-invalid candidate emits no diagnostics at all (§6.2.3)."""
    def mutate(o, r):
        r["unmapped"] = [{"input_ref": sentinel(), "code": "EMPTY_CODE_CONTEXT",
                          "suppressing": False}]
    state, obs = mutated(mutate)
    with pytest.raises(ObservationInvalid, match="cannot appear in unmapped"):
        evaluate(state, obs)


def test_R2_sentinel_in_unmapped_is_hard_invalid_for_every_diagnostic_code():
    for code, bit in (("UNKNOWN_FUNCTION", True), ("SUBSET_TRUNCATED", True),
                      ("UNKNOWN_CONTEXT", False), ("EMPTY_CODE_CONTEXT", False)):
        def mutate(o, r, code=code, bit=bit):
            r["unmapped"] = [{"input_ref": sentinel(), "code": code, "suppressing": bit}]
            if bit:
                r["status"] = SourceStatus.PARTIAL
                r["primary_reason"] = "SUPPRESSING_UNMAPPED"
        state, obs = mutated(mutate)
        assert_hard_invalid(state, obs)


def test_R2_control_sentinel_with_malformed_record_stays_valid():
    """The one legal use of the sentinel must keep working."""
    def mutate(o, r):
        r["status"] = SourceStatus.PARTIAL
        r["primary_reason"] = "MALFORMED_RECORD"
        r["rejected"] = [{"input_ref": sentinel(), "code": "MALFORMED_RECORD"}]
        r["inputs_total"] = r["parsed_ok"] + 1
    state, obs = mutated(mutate)
    res = evaluate(state, obs)
    assert res.admission == Admission.APPLIED
    assert only_row(res)["aggregate_class"] == AggregateClass.HOLD


def test_R2_control_repeated_sentinel_rejections_preserve_multiplicity():
    """§6.2.1: distinct invalid candidates produce repeated rejection elements."""
    def mutate(o, r):
        r["status"] = SourceStatus.PARTIAL
        r["primary_reason"] = "MALFORMED_RECORD"
        r["rejected"] = [{"input_ref": sentinel(), "code": "MALFORMED_RECORD"},
                         {"input_ref": sentinel(), "code": "MALFORMED_RECORD"}]
        r["inputs_total"] = r["parsed_ok"] + 2
    state, obs = mutated(mutate)
    assert evaluate(state, obs).admission == Admission.APPLIED


def test_R2_control_sentinel_is_per_source():
    """Each source has its own sentinel; another source's is not canonical here."""
    def mutate(o, r):
        r["status"] = SourceStatus.PARTIAL
        r["primary_reason"] = "MALFORMED_RECORD"
        r["rejected"] = [{"input_ref": sentinel("LOLBAS"), "code": "MALFORMED_RECORD"}]
        r["inputs_total"] = r["parsed_ok"] + 1
    state, obs = mutated(mutate)
    assert_hard_invalid(state, obs)
