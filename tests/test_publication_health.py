"""Publication bridge failure gates; no live fetch or deployment."""
import json
from contextlib import ExitStack
from dataclasses import replace
from pathlib import Path
import subprocess
from unittest.mock import patch

import pytest

from adapters.base import Entry
from deployment.source_health import (SourceHealthError, check_source_health,
                                      prepare_verified_sync, MemoryPath)
from phase5.vocabulary import SOURCE_UNIVERSE


@pytest.fixture
def repositories(tmp_path):
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
        "index.html": "<table><tr><th>Technique/Command Name</th><th>Command</th><th>Type</th></tr><tr><td>List users</td><td>hello</td><td>CMD</td></tr></table>",
    }
    for name, content in fixtures.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    for args in (("init", "-q"), ("add", "."), ("-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "fixture")):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
    return {source: (repo, "HEAD") for source in SOURCE_UNIVERSE}


def commit(repo):
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "change"], check=True, capture_output=True)


def test_gate_requires_all_five_sources_before_output(repositories, tmp_path):
    repositories.pop("WADComs")
    output = tmp_path / "candidate"
    with pytest.raises(SourceHealthError) as failure:
        prepare_verified_sync(repositories, output)
    assert any(r["source"] == "WADComs" and r["primary_reason"] == "NOT_RUN" for r in failure.value.results)
    assert not output.exists()


@pytest.mark.parametrize("source", sorted(SOURCE_UNIVERSE))
def test_any_acquisition_failure_aborts_entire_candidate(source, repositories, tmp_path):
    repositories[source] = (tmp_path / "absent", "HEAD")
    output = tmp_path / "candidate"
    with pytest.raises(SourceHealthError) as failure:
        prepare_verified_sync(repositories, output)
    assert any(r["source"] == source and r["primary_reason"] == "ACQUISITION_FAILED" for r in failure.value.results)
    assert not output.exists()


def test_partial_source_aborts_before_any_staging_output(repositories, tmp_path):
    repo = repositories["LOLBAS"][0]
    (repo / "yml/OSBinaries/test.yml").write_text("Commands: [{Category: Novel, Command: hello}]")
    commit(repo)
    output = tmp_path / "candidate"
    with pytest.raises(SourceHealthError) as failure:
        prepare_verified_sync(repositories, output)
    lolbas = next(r for r in failure.value.results if r["source"] == "LOLBAS")
    assert lolbas["status"] == "partial"
    assert lolbas["primary_reason"] == "SUPPRESSING_UNMAPPED"
    assert not output.exists()


def test_mutated_workingtree_between_health_and_normalize_is_not_consumed(repositories, tmp_path):
    from deployment import source_health
    original = source_health.check_source_health
    def mutate_after_gate(repos):
        result = original(repos)
        repo = repositories["WADComs"][0]
        (repo / "_wadcoms/Test.md").write_text("command: ATTACKER-MUTATED\n")
        return result
    with ExitStack() as guards:
        guards.enter_context(patch("deployment.source_health.check_source_health", side_effect=mutate_after_gate))
        for cls in source_health.ADAPTERS.values():
            guards.enter_context(patch.object(cls, "fetch", side_effect=AssertionError("fetch forbidden")))
            guards.enter_context(patch.object(cls, "run", side_effect=AssertionError("run forbidden")))
        output = prepare_verified_sync(repositories, tmp_path / "candidate")
    text = (output / "data/entries/active-directory/wadcoms__test.yaml").read_text()
    assert "ATTACKER-MUTATED" not in text and "hello" in text
    report = json.loads((output / "source-health.json").read_text())
    assert report["complete"] is True and report["candidate_entries"] == 5
    assert all(r["status"] == "ok" for r in report["sources"])


def test_existing_output_is_never_removed_or_overwritten(repositories, tmp_path):
    output = tmp_path / "candidate"
    output.mkdir()
    marker = output / "keep"
    marker.write_text("existing work")
    with pytest.raises(SourceHealthError, match="already exist"):
        prepare_verified_sync(repositories, output)
    assert marker.read_text() == "existing work"


def test_global_duplicate_public_ids_abort_no_winner(repositories, tmp_path):
    from deployment import source_health
    original = source_health.ADAPTERS["WADComs"].normalize
    def twice(self, raw):
        entry = next(original(self, raw))
        yield entry
        yield entry
    output = tmp_path / "candidate"
    with patch.object(source_health.ADAPTERS["WADComs"], "normalize", twice):
        with pytest.raises(SourceHealthError, match="collision"):
            prepare_verified_sync(repositories, output)
    assert not output.exists()


def test_write_failure_removes_only_owned_new_staging(repositories, tmp_path):
    output = tmp_path / "candidate"
    keep = tmp_path / "sibling"
    keep.write_text("keep")
    with patch("deployment.source_health.yaml.safe_dump", side_effect=OSError("injected full disk")):
        with pytest.raises(OSError):
            prepare_verified_sync(repositories, output)
    assert not output.exists() and keep.read_text() == "keep"


def test_core_state_is_not_touched_by_publication_health(repositories, tmp_path):
    state = tmp_path / "state.json"
    state.write_bytes(b"unaltered authority")
    bundles, results = check_source_health(repositories)
    assert set(bundles) == SOURCE_UNIVERSE and len(results) == 5
    assert state.read_bytes() == b"unaltered authority"


def test_source_health_known_collision_refuses_publication(repositories, tmp_path):
    repo = repositories["LOLBAS"][0]
    (repo / "yml/OSScripts/test.yml").write_text("Commands: [{Category: Execute, Command: distinct-script}]")
    commit(repo)
    output = tmp_path / "candidate"
    with pytest.raises(SourceHealthError) as failure:
        prepare_verified_sync(repositories, output)
    lolbas = next(r for r in failure.value.results if r["source"] == "LOLBAS")
    assert lolbas["primary_reason"] == "DUPLICATE_ID"
    assert not output.exists()


@pytest.mark.parametrize("source,path,content", [
    ("GTFOBins", "_gtfobins/tool", "functions: false"),
    ("LOLBAS", "yml/OSBinaries/test.yml", "Commands: [{Category: Novel, Command: hi}]"),
    ("WADComs", "_wadcoms/Test.md", "command: hi\nreferences: [a,b,c,d,e]"),
    ("LOLDrivers", "yaml/driver.yaml", "Id: fixed\nTags: wrong"),
    ("LOLAD", "index.html", "<table></table><table></table>"),
])
def test_any_partial_source_aborts_candidate(source, path, content, repositories, tmp_path):
    repo = repositories[source][0]
    (repo / path).write_text(content)
    commit(repo)
    output = tmp_path / "candidate"
    with pytest.raises(SourceHealthError) as failure:
        prepare_verified_sync(repositories, output)
    bad = next(r for r in failure.value.results if r["source"] == source)
    assert bad["status"] == "partial"
    assert not output.exists()


def test_distinct_public_ids_with_same_encoded_filename_abort(repositories, tmp_path):
    from deployment import source_health
    original = source_health.ADAPTERS["WADComs"].normalize
    def collide_filenames(self, raw):
        entry = next(original(self, raw))
        yield replace(entry, id="wadcoms/a/b")
        yield replace(entry, id="wadcoms/a__b")
    output = tmp_path / "candidate"
    with patch.object(source_health.ADAPTERS["WADComs"], "normalize", collide_filenames):
        with pytest.raises(SourceHealthError, match="collision"):
            prepare_verified_sync(repositories, output)
    assert not output.exists()


def test_staging_cannot_target_live_data_tree(repositories, tmp_path):
    with patch("deployment.source_health.ROOT", tmp_path):
        with pytest.raises(SourceHealthError, match="live data"):
            prepare_verified_sync(repositories, tmp_path / "data/stage")
    assert not (tmp_path / "data/stage").exists()


def test_manual_public_field_cannot_diverge_from_enrichment(repositories, tmp_path):
    from deployment import source_health
    original = source_health.ADAPTERS["WADComs"].normalize
    def diverge(self, raw):
        entry = next(original(self, raw))
        yield replace(entry, capabilities=["shell"])
    output = tmp_path / "candidate"
    with patch.object(source_health.ADAPTERS["WADComs"], "normalize", diverge):
        with pytest.raises(SourceHealthError, match="diverge"):
            prepare_verified_sync(repositories, output)
    assert not output.exists()


def test_non_suppressing_wadcoms_warning_is_publication_only_rejection(repositories, tmp_path):
    repo = repositories["WADComs"][0]
    (repo / "_wadcoms/Test.md").write_text("command: hi\nattack_types: [Novel]")
    commit(repo)
    output = tmp_path / "candidate"
    with pytest.raises(SourceHealthError, match="zero source diagnostics") as failure:
        prepare_verified_sync(repositories, output)
    wadcoms = next(r for r in failure.value.results if r["source"] == "WADComs")
    assert wadcoms["status"] == "ok"
    assert wadcoms["unmapped"][0]["code"] == "UNKNOWN_ATTACK_TYPE"
    assert not output.exists()


def test_healthy_driver_legacy_name_fallback_cannot_change_verified_material(repositories, tmp_path):
    repo = repositories["LOLDrivers"][0]
    (repo / "yaml/driver.yaml").write_text("Id: driver-id\nTags: []")
    commit(repo)
    _, results = check_source_health(repositories)
    assert all(r["status"] == "ok" and not r["unmapped"] for r in results)
    output = tmp_path / "candidate"
    with pytest.raises(SourceHealthError, match="public material emissions differ"):
        prepare_verified_sync(repositories, output)
    assert not output.exists()


def test_silent_legacy_emission_skip_cannot_pass_healthy_gate(repositories, tmp_path):
    from deployment import source_health
    output = tmp_path / "candidate"
    with patch.object(source_health.ADAPTERS["WADComs"], "normalize", return_value=iter(())):
        with pytest.raises(SourceHealthError, match="public material emissions differ"):
            prepare_verified_sync(repositories, output)
    assert not output.exists()


def test_same_count_with_changed_display_material_cannot_pass(repositories, tmp_path):
    from deployment import source_health
    original = source_health.ADAPTERS["WADComs"].normalize
    def change_name(self, raw):
        entry = next(original(self, raw))
        yield replace(entry, name="different display content")
    output = tmp_path / "candidate"
    with patch.object(source_health.ADAPTERS["WADComs"], "normalize", change_name):
        with pytest.raises(SourceHealthError, match="public material emissions differ"):
            prepare_verified_sync(repositories, output)
    assert not output.exists()


def test_provenance_source_cannot_be_forged_without_changing_material(repositories, tmp_path):
    from deployment import source_health
    original = source_health.ADAPTERS["WADComs"].normalize
    def forge_claim(self, raw):
        entry = next(original(self, raw))
        entry.enrichment["capabilities"][0]["provenance"]["source"] = "LOLBAS"
        yield entry
    output = tmp_path / "candidate"
    with patch.object(source_health.ADAPTERS["WADComs"], "normalize", forge_claim):
        with pytest.raises(SourceHealthError, match="claim provenance"):
            prepare_verified_sync(repositories, output)
    assert not output.exists()
