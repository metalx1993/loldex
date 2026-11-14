"""Integration contracts across corpus, legacy API, graph and public experience."""
import copy
import json

import pytest

from scripts.build_all import artifacts


def corpus_entry():
    return {"id": "lolbas/test/execute/0", "name": "Test", "platform": "windows", "sources": [{"project": "LOLBAS"}],
            "source_data": {"LOLBAS": {"raw": {"Name": "Test"}}},
            "enrichment": {"capabilities": [{"value": "file-download", "provenance": {"type": "adapter", "source": "LOLBAS"}, "confidence": {"level": "high"}}]},
            "capabilities": ["file-download"]}


def test_all_views_share_identity_and_build_does_not_mutate_corpus():
    entry = corpus_entry()
    before = copy.deepcopy(entry)
    result = {k: json.loads(v) for k, v in artifacts([entry], None).items()}
    assert entry == before
    eid = entry["id"]
    assert result["data.json"]["entries"][0]["id"] == result["catalog.json"]["entries"][0]["id"] == eid
    assert result["graph.json"]["stats"]["entries"] == result["catalog.json"]["count"] == 1
    assert eid in result["evidence.json"]["entries"]
    assert result["catalog.json"]["entries"][0]["freshness"]["classification"] == "NOT_OBSERVED"


def test_invalid_claim_prevents_every_artifact_being_built():
    entry = corpus_entry()
    entry["enrichment"]["capabilities"][0]["confidence"]["level"] = "made-up"
    with pytest.raises(ValueError):
        artifacts([entry], None)


def test_all_artifacts_are_reproducible_under_entry_order():
    a, b = corpus_entry(), corpus_entry()
    b["id"] = "lolbas/z/execute/0"
    assert artifacts([a, b], None) == artifacts([b, a], None)


def test_noncanonical_corpus_identity_cannot_split_public_views():
    entry = corpus_entry()
    entry["id"] = "lolbas/cafe\u0301/execute/0"
    with pytest.raises(ValueError, match="NFC"):
        artifacts([entry], None)


def test_drift_cannot_survive_in_legacy_api_while_ui_ignores_it():
    entry = corpus_entry()
    entry["capabilities"] = ["defense-evasion"]
    with pytest.raises(ValueError, match="projection drift"):
        artifacts([entry], None)


def test_manual_sync_stages_every_generated_view_under_existing_base_guard():
    from pathlib import Path
    workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/sync.yml").read_text()
    stage = next(line for line in workflow.splitlines() if "git add data/" in line)
    for name in ["data.json", "catalog.json", "evidence.json", "graph.json", "techniques.json", "identities.json", "openapi-v1.json", "evidence-records/", "build-manifest.json", "registry-license.txt"]:
        assert "site/" + name in stage
    assert "# schedule:" in workflow
    assert workflow.index('if [ "$remote_sha" != "$BASE_SHA" ]') < workflow.index('git commit -m')
