"""Independent adversarial checks for the Phase 5/3/4 semantic boundaries.

Fixtures are local and deliberately hostile. No upstream network or corpus writes.
"""
import copy
import subprocess

import pytest


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True
    ).stdout.decode().strip()


def committed_repo(tmp_path, files):
    repo = tmp_path / "upstream"
    repo.mkdir()
    git(repo, "init", "-q")
    for name, content in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
        "commit", "-qm", "fixture")
    return repo


def test_verified_acquisition_ignores_mutated_deleted_and_untracked_worktree(tmp_path):
    from phase5.acquisition import acquire
    repo = committed_repo(tmp_path, {
        "_wadcoms/one.md": "original one", "_wadcoms/two.md": "original two",
    })
    before = acquire(repo, "WADComs")
    (repo / "_wadcoms/one.md").write_text("malicious replacement")
    (repo / "_wadcoms/two.md").unlink()
    (repo / "_wadcoms/untracked.md").write_text("phantom candidate")
    after = acquire(repo, "WADComs")
    assert after == before
    assert {f.name: f.content for f in after.files} == {
        "one.md": b"original one", "two.md": b"original two",
    }


def test_discovery_distinguishes_wadcoms_markdown_from_dotfiles_and_nested_files(tmp_path):
    from phase5.acquisition import acquire
    repo = committed_repo(tmp_path, {
        "_wadcoms/one.md": "included", "_wadcoms/.dir-locals.el": "excluded",
        "_wadcoms/nested/two.md": "excluded", "_wadcoms/UPPER.MD": "excluded",
    })
    assert [f.name for f in acquire(repo, "WADComs").files] == ["one.md"]


def test_acquisition_missing_blob_fails_instead_of_qualifying_as_absence(tmp_path):
    from phase5.acquisition import AcquisitionFailed, acquire
    repo = committed_repo(tmp_path, {"_wadcoms/one.md": "one"})
    oid = git(repo, "rev-parse", "HEAD:_wadcoms/one.md")
    (repo / ".git/objects" / oid[:2] / oid[2:]).unlink()
    with pytest.raises(AcquisitionFailed):
        acquire(repo, "WADComs")


def test_selected_symlink_fails_closed_instead_of_following_external_bytes(tmp_path):
    from phase5.acquisition import AcquisitionFailed, acquire
    repo = committed_repo(tmp_path, {"_wadcoms/one.md": "one"})
    (repo / "_wadcoms/link.md").symlink_to("../../outside")
    git(repo, "add", ".")
    git(repo, "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
        "commit", "-qm", "hostile symlink")
    with pytest.raises(AcquisitionFailed):
        acquire(repo, "WADComs")


def bundle(source, files):
    from phase5.acquisition import AcquiredFile, VerifiedBundle
    return VerifiedBundle(source, "a" * 40, "b" * 40,
                          tuple(AcquiredFile(name, value.encode()) for name, value in files))


def test_collision_precedes_content_defect_and_removes_all_file_siblings():
    from phase5.observation import adapter_result
    command = "Commands:\n- Category: Execute\n  Command: run\n- Category: Download\n  Command: fetch\n"
    result = adapter_result(bundle("LOLBAS", [
        ("OSBinaries/same.yml", command),
        ("OSScripts/same.yml", command + "Detection: [malformed]\n"),
    ]))
    assert result["inputs_total"] == 2
    assert result["parsed_ok"] == 0
    assert [r["code"] for r in result["rejected"]] == ["DUPLICATE_ID"] * 2
    assert result["emitted_entries"] == {}
    assert len(result["duplicate_ids"]) == 2


def test_unknown_lolbas_category_emits_but_suppresses_health_without_reindexing():
    from phase5.observation import adapter_result
    result = adapter_result(bundle("LOLBAS", [("OSBinaries/one.yml",
        "Commands:\n- Category: Unknown\n  Command: first\n- Category: Execute\n  Command: second\n")]))
    assert result["inputs_total"] == result["parsed_ok"] == 1
    assert result["status"] == "partial"
    assert sorted(result["emitted_entries"]) == ["lolbas/one/execute/1", "lolbas/one/unknown/0"]
    assert result["unmapped"] == [{"input_ref": "yml/OSBinaries/one.yml#",
                                   "code": "UNKNOWN_CATEGORY", "suppressing": True}]


def test_yaml_boolean_is_not_coerced_into_required_command():
    from phase5.observation import adapter_result
    result = adapter_result(bundle("WADComs", [("one.md", "command: yes\n")]))
    assert result["parsed_ok"] == 0
    assert result["rejected"] == [{"input_ref": "_wadcoms/one.md#", "code": "MALFORMED_RECORD"}]
    assert result["emitted_entries"] == {}


def test_nfc_path_collision_rejects_every_candidate_with_multiplicity():
    from phase5.observation import adapter_result
    result = adapter_result(bundle("WADComs", [
        ("caf\u00e9.md", "command: valid\n"), ("cafe\u0301.md", "command: valid\n"),
    ]))
    assert result["parsed_ok"] == 0
    assert result["inputs_total"] == 2
    assert len(result["rejected"]) == 2
    assert result["rejected"][0] == result["rejected"][1]
    assert result["rejected"][0]["code"] == "NORMALIZED_PATH_COLLISION"


def test_empty_gtfo_context_does_not_hide_valid_sibling():
    from phase5.observation import adapter_result
    result = adapter_result(bundle("GTFOBins", [("one", """functions:
  shell:
  - code: ''
  - code: run
""")]))
    assert result["status"] == "ok"
    assert result["inputs_total"] == result["parsed_ok"] == 1
    assert result["rejected"] == []
    assert result["unmapped"] == [{"input_ref": "_gtfobins/one#",
                                   "code": "EMPTY_CODE_CONTEXT", "suppressing": False}]
    assert list(result["emitted_entries"]) == ["gtfobins/one/shell/unprivileged"]


def test_nested_lolad_tables_cannot_look_like_one_healthy_table():
    from phase5.observation import adapter_result
    html = "<table><table><tr><td>One</td><td>run</td><td>CMD</td></tr></table></table>"
    result = adapter_result(bundle("LOLAD", [("index.html", html)]))
    assert result["inputs_total"] == 1
    assert result["parsed_ok"] == 0
    assert result["rejected"] == [{"input_ref": "index.html#", "code": "MALFORMED_RECORD"}]
    assert result["emitted_entries"] == {}


@pytest.mark.parametrize("source,name,content,expected", [
    ("GTFOBins", "one", "functions:\n  shell:\n  - code: run\n    comment: hello\n    contexts:\n      sudo: null\n",
     "b2668acb0e42e05de8a02ba34b256839a09543a77fcd430d90bf3ca81d4eb8a7"),
    ("LOLBAS", "OSBinaries/one.yml", "Name: One.exe\nCommands:\n- Category: Execute\n  Command: run\n  Description: desc\n  MitreID: T1105\n  Privileges: User\nDetection:\n- IOC: noisy\n  Sigma: https://example.invalid\n",
     "b2e4032ce5fac2b6c007a44ed14f946ab539a4e93a50279e86f613aaf13ab28a"),
    ("WADComs", "one.md", "command: run\nattack_types: [Exploitation]\nitems: [No_Creds]\nservices: [HTTP]\nreferences: [https://example.invalid]\ndescription: example\n",
     "87027d84ba7dcd5dc92baad2d3e8c24a19318851c28d260f09713d17b6d810eb"),
    ("LOLDrivers", "one.yaml", "Id: abc\nTags: [one.sys]\nCommands:\n  Usecase: privilege escalation\n  Description: desc\n  Command: run\n  Privileges: kernel\nKnownVulnerableSamples:\n- SHA256: hash\n  Company: company\n  OriginalFilename: original\nCategory: malicious\nMitreID: T1105\nResources: [https://example.invalid]\n",
     "b858f06848e45c1bf40b2adef35e501f55d4356f3280572ebc8b3f254bc240d8"),
    ("LOLAD", "index.html", '<table><tr><th>Technique</th><th>Command</th><th>Type</th></tr><tr><td>One</td><td>run &quot;hi&quot;</td><td>CMD</td></tr></table>',
     "1e23ab88d19f363e11838383c75f7d6cd765f368234a99d164184eb63acc3e12"),
])
def test_populated_projection_matches_independently_checked_closed_mapping(source, name, content, expected):
    """Expected hashes were independently cross-checked against frozen legacy maps.

    D1 changes IDs, but not these approved material fields. Includes command
    comments, tags, privilege, opsec, samples and references, plus literal HTML
    entities (the established LOLAD extractor does not unescape them).
    """
    from phase5.observation import adapter_result
    result = adapter_result(bundle(source, [(name, content)]))
    assert result["status"] == "ok"
    assert len(result["emitted_entries"]) == 1
    assert next(iter(result["emitted_entries"].values()))["material_fingerprint"] == "sha256:" + expected


def claim(value, level="high", ptype="upstream", **extra):
    provenance = {"type": ptype, "source": "LOLBAS", **extra}
    return {"value": value, "provenance": provenance, "confidence": {"level": level}}


def entry(eid="lolbas/one/execute/0", **enrichment):
    return {"id": eid, "name": "One", "platform": "windows", "type": "binary",
            "sources": [{"project": "LOLBAS", "upstream_url": "https://example.invalid"}],
            "source_data": {"LOLBAS": {"raw": {}}}, "enrichment": enrichment}


def test_graph_preserves_disagreeing_claim_evidence_and_ignores_projected_injection():
    from knowledge.graph import build_graph
    from knowledge.techniques import build_techniques
    high, low = claim("T1105"), claim("T1105", "low", "heuristic", note="keyword guess")
    document = entry(attack_techniques=[high, copy.deepcopy(high), low])
    document["capabilities"] = ["credential-dump"]
    original = copy.deepcopy(document)
    graph = build_graph([document])
    edges = [e for e in graph["edges"] if e["type"] == "implements"]
    assert len(edges) == 2
    assert {e["confidence"]["level"] for e in edges} == {"high", "low"}
    assert not any(e["type"] == "has_capability" for e in graph["edges"])
    assert document == original
    technique = build_techniques(graph)["techniques"][0]
    assert technique["confidence_counts"] == {"low": 1, "medium": 0, "high": 1, "verified": 0}


def test_technique_identifier_is_not_fabricated_registry_knowledge():
    from knowledge.graph import build_graph
    from knowledge.techniques import build_techniques
    graph = build_graph([entry(attack_techniques=[claim("T9999"), claim("T1105, T1003")])])
    data = build_techniques(graph)
    assert len(data["techniques"]) == 1
    technique = data["techniques"][0]
    assert technique["id"] == "T9999"
    assert technique["name"] is None
    assert technique["registry_status"] == "unverified"
    assert len(graph["diagnostics"]) == 1
    assert graph["diagnostics"][0]["value"] == "T1105, T1003"


def test_graph_and_techniques_are_permutation_invariant():
    from phase5.canonical import canonical_bytes
    from knowledge.graph import build_graph
    from knowledge.techniques import build_techniques
    first = entry(attack_techniques=[claim("T1105"), claim("T1003")])
    second = entry("lolbas/two/execute/0", capabilities=[claim("file-download", ptype="adapter")])
    a = build_graph([first, second])
    first["enrichment"]["attack_techniques"].reverse()
    b = build_graph([second, first])
    assert canonical_bytes(a) == canonical_bytes(b)
    assert canonical_bytes(build_techniques(a)) == canonical_bytes(build_techniques(b))


def test_technique_validator_rejects_unsupported_entry_and_confidence_totals():
    from knowledge.graph import build_graph
    from knowledge.techniques import build_techniques, validate_techniques
    graph = build_graph([entry(attack_techniques=[claim("T1105")])])
    for field, value in (("entry_ids", ["lolbas/phantom"]),
                         ("confidence_counts", {"low": 0, "medium": 0, "high": 9, "verified": 0})):
        data = build_techniques(graph)
        data["techniques"][0][field] = value
        with pytest.raises(ValueError):
            validate_techniques(data, graph)


def test_persisted_acquisition_failure_holds_evidence_and_exact_retry_is_byte_noop(tmp_path):
    from phase5.genesis import genesis_body, seed_entry
    from phase5.observation import build_observation
    from phase5.runtime import apply_observation, read_state
    eid = "gtfobins/one/shell/unprivileged"
    genesis = genesis_body([seed_entry(eid, "GTFOBins")])
    healthy = bundle("GTFOBins", [("one", "functions:\n  shell:\n  - code: run\n")])
    path = tmp_path / "state.json"
    first = apply_observation(path, build_observation(genesis, {"GTFOBins": healthy}), genesis)
    assert first.admission == "APPLIED"
    previous = read_state(path, genesis)
    evidence = copy.deepcopy(previous["entries"][0]["sources"])
    failure = build_observation(previous, {"GTFOBins": None})
    held = apply_observation(path, failure, genesis)
    assert held.admission == "APPLIED"
    assert held.next_body["entries"][0]["sources"] == evidence
    assert held.next_body["entries"][0]["absence_streak"] == 0
    bytes_after = path.read_bytes()
    retry = apply_observation(path, failure, genesis)
    assert retry.admission == "IDEMPOTENT_NO_OP"
    assert retry.report is None
    assert path.read_bytes() == bytes_after


def test_rename_failure_keeps_committed_state_and_discards_partial_successor(tmp_path, monkeypatch):
    from phase5.genesis import genesis_body
    from phase5.observation import build_observation
    from phase5.runtime import apply_observation
    import phase5.runtime as runtime
    genesis = genesis_body([])
    path = tmp_path / "state.json"
    from phase5.state import serialize_state_file
    path.write_bytes(serialize_state_file(genesis))
    before = path.read_bytes()
    def fail_replace(*args):
        raise OSError("simulated rename failure")
    monkeypatch.setattr(runtime.os, "replace", fail_replace)
    with pytest.raises(OSError):
        apply_observation(path, build_observation(genesis, {}), genesis)
    assert path.read_bytes() == before
    assert not list(tmp_path.glob("state.json.tmp.*"))


def test_corrupted_persisted_state_is_never_repaired_or_overwritten(tmp_path):
    from phase5.genesis import genesis_body
    from phase5.observation import build_observation
    from phase5.runtime import apply_observation
    genesis = genesis_body([])
    path = tmp_path / "state.json"
    path.write_bytes(b'{"body":{},"checksum":"forged"}\n')
    before = path.read_bytes()
    with pytest.raises(ValueError):
        apply_observation(path, build_observation(genesis, {}), genesis)
    assert path.read_bytes() == before


def test_official_registry_name_does_not_upgrade_low_entry_evidence_or_create_tactic_edges():
    from knowledge.graph import build_graph
    from knowledge.registry import load_registry
    from knowledge.techniques import build_techniques
    registry = load_registry()
    tid = next(iter(registry["techniques"]))
    graph = build_graph([entry(attack_techniques=[claim(tid, "low", "heuristic", note="unconfirmed interpretation")])])
    before = copy.deepcopy(graph)
    data = build_techniques(graph, registry)
    technique = data["techniques"][0]
    assert technique["name"] == registry["techniques"][tid]["name"]
    assert technique["registry_status"] == "verified"
    assert technique["confidence_counts"] == {"low": 1, "medium": 0, "high": 0, "verified": 0}
    assert technique["phases"] == []
    assert not any(edge["type"] == "operates_in" for edge in graph["edges"])
    assert graph == before
