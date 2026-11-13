"""D2-DW is explicit, complete and evidence-preserving; D1 remains frozen."""
import copy
import datetime

import pytest
import yaml

from adapters.complete_data import SourceDataError, entry_evidence_hash, json_detail
from adapters.loldrivers import LOLDriversAdapter, complete_entry as driver_entry
from adapters.wadcoms import WADComsAdapter, complete_entry as wad_entry
from phase5.acquisition import AcquiredFile, VerifiedBundle
from phase5.material import material_fingerprint
from phase5.observation import adapter_result

REV = "a" * 40
DATE = "2026-11-13"


def document(source, data):
    raw = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
    return "---\n" + raw + "---\nOriginal markdown body\n" if source == "WADComs" else raw


def driver(data=None):
    return {"Id": "fixed-driver", "Tags": ["one.sys", "alias.sys"],
            "Commands": [{"Usecase": "disable defenses", "Description": "A" * 301,
                          "Command": "first", "Privileges": "Admin"},
                         {"Usecase": "kernel escalation", "Description": "B" * 401,
                          "Command": "second", "Privileges": "System"}],
            "KnownVulnerableSamples": [{"SHA256": "hash-a", "Company": "Signer A"},
                                       {"SHA256": "hash-b", "Company": "Signer B", "Filename": "b.sys"}],
            "Resources": [f"https://example.invalid/{n}" for n in range(7)],
            "MitreID": "T1068", **(data or {})}


def make_driver(data):
    return driver_entry(data, file_name="driver.yaml", revision=REV, on=DATE,
                        raw_text=document("LOLDrivers", data))


def make_wad(data):
    return wad_entry(data, file_name="Source-File.md", revision=REV, on=DATE,
                     raw_text=document("WADComs", data))


def raw_paths(tmp_path, source, documents):
    files = []
    for name, content in documents:
        path = tmp_path / name
        path.write_text(content)
        files.append(path)
    return {"rev": REV, "on": DATE, "files": files}


def test_complete_driver_keeps_every_command_sample_reference_and_description():
    data = driver()
    original = copy.deepcopy(data)
    entry = make_driver(data)
    assert data == original
    assert len(entry.commands) == 2
    assert entry.commands[0]["comment"] == "A" * 301
    assert entry.commands[1]["comment"] == "B" * 401
    assert len(entry.references) == 7
    assert len(entry.driver_detail["samples"]) == 2
    assert entry.driver_detail["samples"][1]["SHA256"] == "hash-b"
    assert entry.driver_detail["command_metadata"] == data["Commands"]
    assert entry.aliases == ["alias.sys"]
    assert entry.id == "loldrivers/fixed-driver"
    assert entry.privilege_required == "system"
    assert entry.source_data["LOLDrivers"]["raw"]["document"] == document("LOLDrivers", data)
    entry.validate()


@pytest.mark.parametrize("mutate", [
    lambda d: d["KnownVulnerableSamples"][1].update(SHA256="changed-last-sample"),
    lambda d: d["Resources"].__setitem__(6, "https://example.invalid/changed-last-reference"),
    lambda d: d["Commands"][1].update(Command="changed-second-command"),
    lambda d: d["Commands"][0].update(Description="A" * 300 + "X"),
])
def test_previously_discarded_driver_material_changes_fingerprint(mutate):
    before = driver()
    changed = copy.deepcopy(before)
    mutate(changed)
    assert material_fingerprint(make_driver(before).to_dict()) != material_fingerprint(make_driver(changed).to_dict())


def test_duplicate_sample_occurrences_and_source_order_are_retained():
    data = driver({"KnownVulnerableSamples": [{"SHA256": "same"}, {"SHA256": "same"}]})
    entry = make_driver(data)
    assert entry.driver_detail["samples"] == [{"SHA256": "same"}] * 2
    one = copy.deepcopy(data)
    one["KnownVulnerableSamples"].pop()
    assert material_fingerprint(entry.to_dict()) != material_fingerprint(make_driver(one).to_dict())


def test_yaml_non_json_types_have_explicit_material_types_and_original_raw_text():
    sample = {"Date": datetime.date(2026, 11, 13), "Value": 1.5, "Payload": b"binary"}
    data = driver({"KnownVulnerableSamples": [sample]})
    entry = make_driver(data)
    detail = entry.driver_detail["samples"][0]
    assert detail["Date"] == {"$yaml_type": "date", "value": "2026-11-13"}
    assert detail["Value"] == {"$yaml_type": "float", "value": "1.5"}
    assert detail["Payload"] == {"$yaml_type": "binary", "value": "YmluYXJ5"}
    assert "!!binary" in entry.source_data["LOLDrivers"]["raw"]["document"]
    material_fingerprint(entry.to_dict())


def test_typed_scalar_wrapper_cannot_collide_with_source_mapping():
    assert json_detail(1.5) != json_detail({"$yaml_type": "float", "value": "1.5"})
    with pytest.raises(SourceDataError):
        json_detail({"é": 1, "e\u0301": 2})


def test_driver_claim_confidence_stays_per_claim():
    entry = make_driver(driver())
    assert all(c["confidence"]["level"] == "low" and c["provenance"]["type"] == "heuristic"
               for c in entry.enrichment["capabilities"])
    assert entry.enrichment["attack_techniques"][0]["confidence"]["level"] == "high"
    assert entry.enrichment["attack_techniques"][0]["provenance"]["type"] == "upstream"


@pytest.mark.parametrize("field,value", [
    ("Commands", [{"Command": "good"}, None]),
    ("KnownVulnerableSamples", [{"SHA256": "good"}, None]),
    ("Resources", ["https://example.invalid", False]),
    ("Tags", [None]),
])
def test_malformed_late_driver_records_are_not_skipped(tmp_path, field, value):
    data = driver({field: value})
    raw = raw_paths(tmp_path, "LOLDrivers", [("one.yaml", document("LOLDrivers", data))])
    preflight = LOLDriversAdapter.publication_preflight(raw)
    assert preflight["inputs_total"] == 1
    assert preflight["parsed_ok"] == 0
    assert preflight["diagnostics"][0]["code"] == "MALFORMED_RECORD"
    with pytest.raises(SourceDataError):
        list(LOLDriversAdapter().normalize_complete(raw))


def test_d1_driver_truncation_remains_visible_while_d2_retains_full_records(tmp_path):
    data = driver()
    content = document("LOLDrivers", data)
    bundle = VerifiedBundle("LOLDrivers", REV, "b" * 40, (AcquiredFile("one.yaml", content.encode()),))
    frozen = adapter_result(bundle)
    assert frozen["status"] == "partial"
    assert any(d["code"] == "SUBSET_TRUNCATED" for d in frozen["unmapped"])
    raw = raw_paths(tmp_path, "LOLDrivers", [("one.yaml", content)])
    assert LOLDriversAdapter.publication_preflight(raw)["diagnostics"] == []


@pytest.mark.parametrize("label,capability", [
    ("Discovery", "discovery"), ("Privilidge Escalation", "privilege-escalation"),
    ("Laterl movement", "lateral-movement"), ("AS-REP Roasting", "credential-access"),
    ("Kerberoasting", "kerberoast"), ("Timeroasting", "credential-access"),
])
def test_wad_exact_new_labels_keep_raw_evidence_and_explicit_adapter_mapping(label, capability):
    data = {"command": "run", "attack_types": [label]}
    entry, unknown = make_wad(data)
    assert unknown == []
    assert entry.capabilities == [capability]
    claim = entry.enrichment["capabilities"][0]
    assert claim["confidence"]["level"] == "high"
    assert claim["provenance"]["type"] == "adapter"
    assert label in claim["provenance"]["note"]
    assert label in entry.source_data["WADComs"]["raw"]["document"]


def test_unknown_future_wad_type_never_fabricates_discovery_and_remains_diagnostic(tmp_path):
    data = {"command": "run", "attack_types": ["Future Type"]}
    entry, unknown = make_wad(data)
    assert unknown == ["Future Type"]
    assert entry.capabilities == entry.phases == []
    assert "defaulted to discovery" not in str(entry.enrichment)
    raw = raw_paths(tmp_path, "WADComs", [("One.md", document("WADComs", data))])
    preflight = WADComsAdapter.publication_preflight(raw)
    assert preflight["parsed_ok"] == 1
    assert preflight["diagnostics"] == [{"name": "One.md", "code": "UNKNOWN_ATTACK_TYPE",
                                         "value": "Future Type", "suppressing": False}]


def test_wad_missing_type_default_is_explicit_low_confidence():
    entry, unknown = make_wad({"command": "run"})
    assert unknown == []
    assert entry.capabilities == ["discovery"]
    claim = entry.enrichment["capabilities"][0]
    assert claim["provenance"]["type"] == "heuristic"
    assert claim["confidence"]["level"] == "low"
    assert "no upstream attack_types" in claim["provenance"]["note"]


def test_complete_wad_preserves_description_and_all_references(tmp_path):
    description = "start\n  " + "x" * 400 + "\nend"
    data = {"command": "run", "description": description,
            "attack_types": ["Enumeration"],
            "references": [f"https://example.invalid/{i}" for i in range(8)]}
    entry, _ = make_wad(data)
    assert entry.commands[0]["comment"] == description
    assert len(entry.references) == 8
    changed = copy.deepcopy(data)
    changed["description"] += "changed-after-280"
    assert material_fingerprint(entry.to_dict()) != material_fingerprint(make_wad(changed)[0].to_dict())
    raw = raw_paths(tmp_path, "WADComs", [("One.md", document("WADComs", data))])
    assert WADComsAdapter.publication_preflight(raw)["diagnostics"] == []
    frozen = adapter_result(VerifiedBundle("WADComs", REV, "b" * 40,
                            (AcquiredFile("One.md", document("WADComs", data).encode()),)))
    assert frozen["status"] == "partial"


def test_original_raw_document_must_match_the_derived_record():
    data = driver()
    with pytest.raises(SourceDataError, match="raw evidence"):
        driver_entry(data, file_name="one.yaml", revision=REV, on=DATE,
                     raw_text=document("LOLDrivers", driver({"Id": "other"})))


def test_preflight_accounts_for_all_files_including_malformed_document(tmp_path):
    raw = raw_paths(tmp_path, "WADComs", [("Good.md", document("WADComs", {"command": "run"})),
                                         ("Bad.md", "---\ncommand: [\n---\n")])
    result = WADComsAdapter.publication_preflight(raw)
    assert result["inputs_total"] == 2
    assert result["parsed_ok"] == 1
    assert result["rejected"] == [{"name": "Bad.md", "code": "PARSE_ERROR"}]


def test_leading_blank_lines_before_frontmatter_do_not_reject_real_wad_format(tmp_path):
    # Rubeus-s4u.md in the verified snapshot has this exact framing shape.
    raw = raw_paths(tmp_path, "WADComs", [("Rubeus-s4u.md", "\n\n" + document("WADComs", {
        "command": "run", "attack_types": ["Privilidge Escalation"], "description": "x" * 700,
    }))])
    preflight = WADComsAdapter.publication_preflight(raw)
    assert preflight["diagnostics"] == []
    assert preflight["parsed_ok"] == 1
    entry = next(WADComsAdapter().normalize_complete(raw))
    assert entry.source_data["WADComs"]["raw"]["document"].startswith("\n\n---")


def test_preflight_expected_emissions_are_independent_of_public_normalizer(tmp_path, monkeypatch):
    data = driver()
    raw = raw_paths(tmp_path, "LOLDrivers", [("one.yaml", document("LOLDrivers", data))])
    monkeypatch.setattr(LOLDriversAdapter, "normalize_complete", lambda self, raw: iter(()))
    audit = LOLDriversAdapter.publication_preflight(raw)
    assert audit["expected_emissions"] == {"loldrivers/fixed-driver": material_fingerprint(make_driver(data).to_dict())}
    independently_derived = driver_entry(data, file_name="one.yaml", revision=REV,
                                        on=DATE, raw_text=document("LOLDrivers", data))
    assert audit["expected_evidence"] == {"loldrivers/fixed-driver": entry_evidence_hash(independently_derived)}


def test_same_material_with_forged_claim_confidence_changes_evidence_hash():
    entry = make_driver(driver())
    changed = copy.deepcopy(entry)
    changed.enrichment["attack_techniques"][0]["confidence"]["level"] = "low"
    assert material_fingerprint(entry.to_dict()) == material_fingerprint(changed.to_dict())
    assert entry_evidence_hash(entry) != entry_evidence_hash(changed)


def test_duplicate_driver_ids_reject_all_preflight_emissions(tmp_path):
    data = document("LOLDrivers", driver())
    raw = raw_paths(tmp_path, "LOLDrivers", [("one.yaml", data), ("two.yaml", data)])
    audit = LOLDriversAdapter.publication_preflight(raw)
    assert audit["parsed_ok"] == 0
    assert audit["expected_emissions"] == audit["expected_evidence"] == {}
    assert [r["code"] for r in audit["rejected"]] == ["DUPLICATE_ID", "DUPLICATE_ID"]


def test_cyclic_sample_alias_is_a_shape_error_not_an_unbounded_projection():
    cyclic = {}
    cyclic["self"] = cyclic
    with pytest.raises(SourceDataError, match="cyclic"):
        json_detail(cyclic)
