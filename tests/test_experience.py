"""Semantic UI build regression tests, independent of DOM presentation."""
import copy
import json

import pytest

from scripts.build_experience import build_experience
from phase5.genesis import genesis_body, seed_entry


def example(eid="lolbas/a/execute/0"):
    return {"id": eid, "name": "A", "platform": "windows", "sources": [{"project": "LOLBAS"}],
            "enrichment": {"capabilities": [{"value": "execution", "provenance": {"type": "heuristic", "note": "fixture"}, "confidence": {"level": "low"}}]},
            "source_data": {"LOLBAS": {"raw": {"untrusted": "<script>alert(1)</script>"}}}}


def test_claims_and_raw_are_separate_and_unmodified():
    entry = example()
    original = copy.deepcopy(entry)
    catalog, evidence = build_experience([entry])
    assert entry == original
    assert catalog["entries"][0]["claims"] == entry["enrichment"]
    assert "source_data" not in catalog["entries"][0]
    assert evidence["entries"][entry["id"]] == entry["source_data"]
    assert "confidence" not in catalog["entries"][0]


def test_no_state_means_not_observed_never_fresh():
    catalog, _ = build_experience([example()])
    assert catalog["entries"][0]["freshness"] == {"classification": "NOT_OBSERVED", "initialized": False, "observation_id": None}


def test_deterministic_under_entry_order():
    entries = [example(), example("lolbas/b/execute/0")]
    assert build_experience(entries) == build_experience(list(reversed(entries)))


def test_duplicate_entry_fails_instead_of_overwriting():
    with pytest.raises(ValueError, match="duplicate"):
        build_experience([example(), example()])


def test_state_classification_not_clock_is_projected():
    base = genesis_body([seed_entry(example()["id"], "LOLBAS")])
    catalog, _ = build_experience([example()], base)
    assert catalog["entries"][0]["freshness"]["classification"] == "NOT_OBSERVED"
    assert catalog["entries"][0]["freshness"]["observation_id"] == 0


def test_projected_drift_cannot_fabricate_ui_claims():
    entry = example()
    entry.update(capabilities=["defense-evasion"], attack_techniques=["T1105"], phases=["execution"], privilege_required="system")
    catalog, _ = build_experience([entry])
    result = catalog["entries"][0]
    assert result["capabilities"] == ["execution"]
    assert result["attack_techniques"] == result["phases"] == []
    assert result["privilege_required"] == ""
    assert entry["attack_techniques"] == ["T1105"]


def test_nfc_identity_collision_cannot_split_evidence():
    with pytest.raises(ValueError, match="duplicate"):
        build_experience([example("lolbas/é/execute/0"), example("lolbas/e\u0301/execute/0")])
