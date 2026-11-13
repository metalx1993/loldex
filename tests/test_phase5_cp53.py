"""CP5.3 semantic and runtime regression tests against CORE clauses."""
import json
from pathlib import Path
import subprocess
from unittest.mock import patch

import pytest

from phase5.acquisition import AcquiredFile, VerifiedBundle, acquire, AcquisitionFailed
from phase5.observation import adapter_result, build_observation
from phase5.genesis import genesis_body, seed_entry
from phase5.runtime import ObservationBuilder, apply_observation, read_state, cycle
from phase5.transition import evaluate
from phase5.canonical import canonical_bytes


def bundle(source, files):
    return VerifiedBundle(source, "a" * 40, "b" * 40, tuple(AcquiredFile(n, t.encode() if isinstance(t, str) else t) for n, t in files))


def test_gtfo_context_empty_is_diagnostic_not_file_rejection():
    b = bundle("GTFOBins", [("diff", "functions:\n  file-read:\n  - code: cat /x\n    contexts: {unprivileged: null}\n  - code: ''\n    contexts: {sudo: null}\n")])
    result = adapter_result(b)
    assert result["parsed_ok"] == result["inputs_total"] == 1
    assert result["status"] == "ok"
    assert result["unmapped"] == [{"input_ref": "_gtfobins/diff#", "code": "EMPTY_CODE_CONTEXT", "suppressing": False}]
    assert len(result["emitted_entries"]) == 1
    evaluate(genesis_body([]), build_observation(genesis_body([]), {"GTFOBins": b}))


def test_driver_identity_is_id_not_name_and_empty_name_is_omitted():
    one = adapter_result(bundle("LOLDrivers", [("test.yaml", "Id: fixed\nTags: []\n")]))
    assert list(one["emitted_entries"]) == ["loldrivers/fixed"]
    two = adapter_result(bundle("LOLDrivers", [("test.yaml", "Id: fixed\nTags: [driver.sys]\n")]))
    assert one["emitted_entries"]["loldrivers/fixed"]["upstream_identity"] == {"kind": "loldrivers_id", "value": "fixed"}
    assert one["emitted_entries"]["loldrivers/fixed"]["material_fingerprint"] != two["emitted_entries"]["loldrivers/fixed"]["material_fingerprint"]


def test_unknown_lolbas_category_emits_and_uses_source_index():
    b = bundle("LOLBAS", [("OSBinaries/test.yml", "Commands:\n- Category: Novel\n  Command: first\n- Category: Execute\n  Command: second\n")])
    r = adapter_result(b)
    assert r["status"] == "partial"
    assert set(r["emitted_entries"]) == {"lolbas/test/novel/0", "lolbas/test/execute/1"}
    assert r["parsed_ok"] == 1
    evaluate(genesis_body([]), build_observation(genesis_body([]), {"LOLBAS": b}))


def test_lolbas_collision_overrides_content_defect_rejects_whole_files():
    b = bundle("LOLBAS", [("OSBinaries/test.yml", "Commands:\n- Category: Execute\n  Command: good\n- Category: Download\n  Command: sibling\n"), ("OSScripts/test.yml", "Detection: bad\nCommands:\n- Category: Execute\n  Command: bad\n")])
    r = adapter_result(b)
    assert r["primary_reason"] == "DUPLICATE_ID"
    assert r["parsed_ok"] == 0 and r["emitted_entries"] == {}
    assert [x["code"] for x in r["rejected"]] == ["DUPLICATE_ID"] * 2
    assert r["duplicate_ids"] == ["lolbas/test/execute/0"]


@pytest.mark.parametrize("content,code", [("command: yes", "MALFORMED_RECORD"), ("command: 4", "MALFORMED_RECORD"), ("command: ''", "MISSING_REQUIRED_FIELD"), ("command: hi\nservices: wrong", "MALFORMED_RECORD"), (b"\xff", "INVALID_ENCODING"), ("[a]", "NON_DICT_DOCUMENT"), ("", "EMPTY_DOCUMENT")])
def test_wadcoms_typed_failures(content, code):
    r = adapter_result(bundle("WADComs", [("Test.md", content)]))
    assert r["rejected"] == [{"input_ref": "_wadcoms/Test.md#", "code": code}]
    assert not r["emitted_entries"]


def test_normalized_path_collision_retains_multiplicity():
    r = adapter_result(bundle("WADComs", [("e\u0301.md", "command: one"), ("é.md", "command: two")]))
    assert r["rejected"] == [{"input_ref": "_wadcoms/é.md#", "code": "NORMALIZED_PATH_COLLISION"}] * 2
    assert not r["emitted_entries"]


def test_lolad_identical_triples_are_not_repaired_by_suffix():
    html = "<table><tr><th>Name</th><th>Command</th><th>Type</th></tr>" + "<tr><td>Test</td><td>cmd</td><td>CMD</td></tr>" * 2 + "<tr><td>Other</td><td>cmd</td><td>CMD</td></tr></table>"
    b = bundle("LOLAD", [("index.html", html)])
    r = adapter_result(b)
    assert r["inputs_total"] == 3 and r["parsed_ok"] == 1
    assert len(r["rejected"]) == 2 and len(r["duplicate_ids"]) == 1
    assert len(r["emitted_entries"]) == 1
    evaluate(genesis_body([]), build_observation(genesis_body([]), {"LOLAD": b}))


def test_partial_source_holds_known_entry_without_false_absence():
    body = genesis_body([seed_entry("wadcoms/Test", "WADComs")])
    b = bundle("WADComs", [("Test.md", "command: hi\nreferences: [a,b,c,d,e]")])
    r = evaluate(body, build_observation(body, {"WADComs": b}))
    assert r.next_body["entries"][0]["absence_streak"] == 0
    assert r.report["entries"][0]["aggregate_class"] == "HOLD"


def test_apply_persist_exact_retry_and_no_report(tmp_path):
    base = genesis_body([])
    observation = build_observation(base, {"WADComs": bundle("WADComs", [("Test.md", "command: hi")])})
    path = tmp_path / "state.json"
    first = apply_observation(path, observation, base)
    before = path.read_bytes()
    assert first.admission == "APPLIED"
    assert read_state(path, base) == first.next_body
    second = apply_observation(path, observation, base)
    assert second.admission == "IDEMPOTENT_NO_OP" and second.report is None
    assert before == path.read_bytes()


def test_rename_failure_keeps_old_authority_and_cleans_temp(tmp_path):
    base = genesis_body([])
    observation = build_observation(base, {})
    path = tmp_path / "state.json"
    with patch("phase5.runtime.os.replace", side_effect=OSError("injected rename failure")):
        with pytest.raises(OSError):
            apply_observation(path, observation, base)
    assert not path.exists()
    assert not list(tmp_path.glob("state.json.tmp.*"))


def test_builder_cannot_reacquire_same_base():
    builder = ObservationBuilder()
    builder.build(genesis_body([]), {})
    with pytest.raises(ValueError, match="second acquisition"):
        builder.build(genesis_body([]), {})


def test_state_duplicate_json_keys_rejected(tmp_path):
    path = tmp_path / "state.json"
    path.write_text('{"body":{},"body":{},"checksum":"x"}')
    with pytest.raises(ValueError, match="duplicate"):
        read_state(path, genesis_body([]))


def test_directory_fsync_failure_is_after_commit_point(tmp_path):
    base = genesis_body([])
    obs = build_observation(base, {})
    path = tmp_path / "state.json"
    calls = 0
    import os
    fsync = os.fsync
    def inject(fd):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("directory durability failure")
        return fsync(fd)
    with patch("phase5.runtime.os.fsync", side_effect=inject):
        with pytest.raises(OSError):
            apply_observation(path, obs, base)
    assert read_state(path, base)["last_observation_id"] == 1
    retry = apply_observation(path, obs, base)
    assert retry.admission == "IDEMPOTENT_NO_OP" and retry.report is None


def test_cycle_retries_finalized_bytes_without_reacquisition(tmp_path):
    path, artifact = tmp_path / "state.json", tmp_path / "observation.json"
    repo_root = tmp_path / "empty-repository"
    repo_root.mkdir()
    with patch("phase5.runtime.acquire", return_value=bundle("WADComs", [("Test.md", "command: hi")])) as acquisition:
        first = cycle(path, {"WADComs": ("irrelevant", "HEAD")}, repo_root, artifact)
    assert first.admission == "APPLIED" and acquisition.call_count == 1
    before = artifact.read_bytes()
    with patch("phase5.runtime.acquire", side_effect=AssertionError("retry reacquired")):
        retry = cycle(path, {"WADComs": ("irrelevant", "HEAD")}, repo_root, artifact)
    assert retry.admission == "IDEMPOTENT_NO_OP"
    assert artifact.read_bytes() == before


def test_stale_artifact_does_not_overwrite_newer_state(tmp_path):
    base = genesis_body([])
    path = tmp_path / "state.json"
    obs1 = build_observation(base, {})
    first = apply_observation(path, obs1, base)
    obs2 = build_observation(first.next_body, {})
    apply_observation(path, obs2, base)
    before = path.read_bytes()
    stale = apply_observation(path, obs1, base)
    assert stale.admission == "STALE" and stale.report is None
    assert path.read_bytes() == before


@pytest.mark.parametrize("functions", ["null", "false", "[]", "{shell: null}", "{shell: false}"])
def test_malformed_gtfo_function_shapes_hold_instead_of_qualifying_absence(functions):
    b = bundle("GTFOBins", [("tool", "functions: " + functions)])
    result = adapter_result(b)
    assert result["primary_reason"] == "MALFORMED_RECORD"
    assert result["parsed_ok"] == 0


def test_lolad_unclosed_row_is_counted_and_rejected_not_silently_skipped():
    html = '<table><tr><td>Valid</td><td>cmd</td><td>CMD</td></tr><tr><td>Broken</td><td>cmd</td><td>CMD</td></table>'
    result = adapter_result(bundle("LOLAD", [("index.html", html)]))
    assert result["inputs_total"] == 2
    assert result["parsed_ok"] == 1
    assert result["primary_reason"] == "MALFORMED_RECORD"


def test_lolad_td_header_is_excluded_without_skipping_real_technique_names():
    html = '<table><tr><td>Technique/Command Name</td><td>Command</td><td>Type</td></tr><tr><td>Technique discovery</td><td>cmd</td><td>CMD</td></tr></table>'
    result = adapter_result(bundle("LOLAD", [("index.html", html)]))
    assert result["inputs_total"] == result["parsed_ok"] == 1


def test_gtfo_whitespace_context_override_does_not_resurrect_base_command():
    result = adapter_result(bundle("GTFOBins", [("tool", "functions:\n  shell:\n  - code: base\n    contexts:\n      sudo: {code: '   '}\n      unprivileged: null\n")]))
    assert list(result["emitted_entries"]) == ["gtfobins/tool/shell/unprivileged"]
    assert result["unmapped"][0]["code"] == "EMPTY_CODE_CONTEXT"


def test_all_five_verified_git_adapters_to_committed_state(tmp_path):
    repo = tmp_path / "upstream"
    repo.mkdir()
    fixtures = {
        "_gtfobins/tool": "functions:\n  shell:\n  - code: hello\n",
        "yml/OSBinaries/test.yml": "Name: Test.exe\nCommands:\n- Category: Execute\n  Command: hello\n",
        "yml/OSLibraries/.keep": "",
        "yml/OSScripts/.keep": "",
        "yml/OtherMSBinaries/.keep": "",
        "_wadcoms/Test.md": "command: hello\nattack_types: [Enumeration]\n",
        "yaml/driver.yaml": "Id: driver-id\nTags: [driver.sys]\n",
        "index.html": "<table><tr><th>Name</th><th>Command</th><th>Type</th></tr><tr><td>List users</td><td>hello</td><td>CMD</td></tr></table>",
    }
    for name, content in fixtures.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    for args in (("init", "-q"), ("add", "."), ("-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "fixture")):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
    empty = tmp_path / "genesis"
    empty.mkdir()
    from phase5.vocabulary import SOURCE_UNIVERSE
    repositories = {source: (repo, "HEAD") for source in SOURCE_UNIVERSE}
    result = cycle(tmp_path / "state.json", repositories, empty, tmp_path / "observation.json")
    assert result.admission == "APPLIED"
    observation = json.loads((tmp_path / "observation.json").read_text())
    assert all(r["status"] == "ok" for r in observation["results"])
    assert all(len(r["resolved_revision"]) == 40 for r in observation["results"])
    assert len(result.next_body["entries"]) == 5
    assert all(e["classification"] == "ACTIVE" for e in result.next_body["entries"])


@pytest.mark.parametrize("html", ["<table><table>", "<table>"])
def test_unclosed_lolad_table_is_synthetic_malformed_not_empty(html):
    result = adapter_result(bundle("LOLAD", [("index.html", html)]))
    assert result["primary_reason"] == "MALFORMED_RECORD"
    assert result["inputs_total"] == 1


@pytest.mark.parametrize("source,name,content", [
    ("LOLBAS", "OSBinaries/test.yml", "Commands: [null]"),
    ("LOLBAS", "OSBinaries/test.yml", "Commands: []\nDetection: [null]"),
    ("GTFOBins", "tool", "functions: {shell: [null]}"),
    ("LOLDrivers", "test.yaml", "Id: fixed\nCommands: [null]"),
    ("LOLDrivers", "test.yaml", "Id: fixed\nKnownVulnerableSamples: [null]"),
])
def test_null_nested_records_are_malformed_not_missing_optional_fields(source, name, content):
    result = adapter_result(bundle(source, [(name, content)]))
    assert result["primary_reason"] == "MALFORMED_RECORD"
    assert result["parsed_ok"] == 0


def test_lolbas_null_category_collision_cannot_bypass_provisional_ids():
    result = adapter_result(bundle("LOLBAS", [("OSBinaries/test.yml", "Commands: [{Category: null, Command: one}]"), ("OSScripts/test.yml", "Commands: [{Category: null, Command: two}]")]))
    assert result["primary_reason"] == "DUPLICATE_ID"
    assert result["duplicate_ids"] == ["lolbas/test//0"]
    assert result["parsed_ok"] == 0 and not result["emitted_entries"]


@pytest.mark.parametrize("source,name,content", [("LOLDrivers", "test.yaml", 'Id: "\\uD800"'), ("GTFOBins", "tool", 'functions: {"\\uD800": [{code: hi}]}')])
def test_yaml_surrogates_reject_candidate_instead_of_invalidating_whole_observation(source, name, content):
    b = bundle(source, [(name, content)])
    result = adapter_result(b)
    assert result["primary_reason"] == "MALFORMED_RECORD"
    evaluate(genesis_body([]), build_observation(genesis_body([]), {source: b}))
