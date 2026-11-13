"""D2 GTFO source semantics; default D1 remains unchanged."""
from collections import Counter
import copy
import io
from pathlib import PurePosixPath
import subprocess
import tarfile

import pytest

from adapters.gtfobins import GTFOBinsAdapter
from deployment.source_health import MemoryPath
from phase5.adapters.gtfobins import (prepare_documents, derive_document, preflight,
                                     GTFOError)
from phase5.material import material_fingerprint

REV = "a" * 40
SHELL = {"functions": {"shell": [{"code": "literal original command"}]}}


def test_alias_is_parsed_without_new_identity_and_preserves_evidence():
    docs = {"target": copy.deepcopy(SHELL), "alias": {"alias": "target"}}
    resolution = prepare_documents(docs)
    assert not resolution.errors
    assert derive_document(resolution, "alias", REV).emissions == ()
    target = derive_document(resolution, "target", REV).emissions[0]
    assert target.id == "gtfobins/target/shell/unprivileged"
    assert target.material["aliases"] == ["alias"]
    assert target.material["commands"] == [{"template": "literal original command"}]
    assert target.raw_documents == docs
    assert docs["alias"] == {"alias": "target"}


def test_alias_chains_are_explicit_and_order_independent():
    docs = {"first": {"alias": "second"}, "second": {"alias": "target"}, "target": SHELL}
    one = prepare_documents(docs)
    two = prepare_documents(dict(reversed(list(docs.items()))))
    assert one.target_for == two.target_for == {"first": "target", "second": "target"}
    assert derive_document(one, "target", REV) == derive_document(two, "target", REV)


@pytest.mark.parametrize("docs", [
    {"a": {"alias": "missing"}},
    {"a": {"alias": "b"}, "b": {"alias": "a"}},
    {"a": {"alias": "a"}},
    {"a": {"alias": "target", "functions": {}}, "target": SHELL},
    {"a": {"alias": False}, "target": SHELL},
])
def test_invalid_aliases_are_rejected_not_silently_ignored(docs):
    resolution = prepare_documents(docs)
    assert resolution.errors
    with pytest.raises(GTFOError):
        derive_document(resolution, "a", REV)


def test_inherit_snippet_is_heuristic_low_without_target_capability_expansion():
    docs = {"target": {"functions": {"file-read": [{"code": "do not copy me"}]}},
            "launcher": {"functions": {"inherit": [{"from": "target", "code": "launch target"}]}}}
    derived = derive_document(prepare_documents(docs), "launcher", REV)
    assert not derived.diagnostics
    entry = derived.emissions[0]
    assert entry.id == "gtfobins/launcher/inherit/unprivileged"
    assert entry.material["capabilities"] == ["command-execution"]
    assert entry.material["commands"] == [{"template": "launch target"}]
    assert "file-read" not in entry.material["capabilities"]
    claim = entry.enrichment["capabilities"][0]
    assert claim["provenance"]["type"] == "heuristic"
    assert claim["confidence"]["level"] == "low"
    assert "no downstream capability" in claim["provenance"]["note"]
    assert entry.enrichment["privilege_required"]["provenance"]["type"] == "adapter"
    assert set(entry.raw_documents) == {"launcher", "target"}


@pytest.mark.parametrize("from_value", [None, False, "missing"])
def test_inherit_requires_valid_same_bundle_target(from_value):
    docs = {"launcher": {"functions": {"inherit": [{"from": from_value, "code": "activation"}]}}}
    with pytest.raises(GTFOError):
        derive_document(prepare_documents(docs), "launcher", REV)


def test_empty_code_and_unknown_values_remain_diagnostics():
    docs = {"tool": {"functions": {"new-function": [{"code": ""}]}}}
    result = derive_document(prepare_documents(docs), "tool", REV)
    assert result.diagnostics == ("UNKNOWN_FUNCTION", "EMPTY_CODE_CONTEXT")
    assert result.emissions == ()


def test_explicit_upstream_privilege_escalation_maps_existing_taxonomy():
    docs = {"tool": {"functions": {"privilege-escalation": [{"code": "activation"}]}}}
    result = derive_document(prepare_documents(docs), "tool", REV)
    assert not result.diagnostics
    assert result.emissions[0].material["capabilities"] == ["privilege-escalation"]
    assert result.emissions[0].enrichment["capabilities"][0]["provenance"]["type"] == "adapter"


def test_d2_public_material_and_pure_derivation_are_identical():
    files = [MemoryPath("alias", b"alias: target"),
             MemoryPath("target", b"functions: {shell: [{code: literal}]}")]
    raw = {"rev": REV, "files": files, "profile": "publication-v2"}
    actual = list(GTFOBinsAdapter().normalize(raw))
    resolution = prepare_documents({"alias": {"alias": "target"}, "target": {"functions": {"shell": [{"code": "literal"}]}}})
    expected = derive_document(resolution, "target", REV)
    assert len(actual) == len(expected.emissions) == 1
    assert material_fingerprint(actual[0].to_dict()) == material_fingerprint(expected.emissions[0].material)
    assert actual[0].source_data["GTFOBins"]["raw"]["documents"]["alias"] == {"alias": "target"}
    actual[0].validate()


def test_default_d1_normalizer_is_not_silently_changed():
    files = [MemoryPath("alias", b"alias: target"),
             MemoryPath("target", b"functions: {shell: [{code: literal}]}")]
    actual = list(GTFOBinsAdapter().normalize({"rev": REV, "files": files}))
    assert len(actual) == 1 and actual[0].aliases == []
    assert "documents" not in actual[0].source_data["GTFOBins"]["raw"]


def test_preflight_exempts_only_valid_alias_and_known_d2_function_refs():
    raw = {"rev": REV, "files": [MemoryPath("alias", b"alias: target"),
            MemoryPath("target", b"functions: {shell: [{code: literal}]}"),
            MemoryPath("launcher", b"functions: {inherit: [{code: activation, from: target}]}")]}
    result = preflight(raw)
    assert {key: result[key] for key in ("inputs_total", "alias_refs", "supported_function_refs", "diagnostics")} == {"inputs_total": 3, "alias_refs": ["_gtfobins/alias#"],
        "supported_function_refs": ["_gtfobins/launcher#"], "diagnostics": []}
    assert set(result["expected_emissions"]) == {"gtfobins/target/shell/unprivileged", "gtfobins/launcher/inherit/unprivileged"}
    assert set(result["expected_evidence"]) == set(result["expected_emissions"])


def test_preflight_encoding_is_strict_not_legacy_replacement():
    with pytest.raises(GTFOError, match="INVALID_ENCODING"):
        preflight({"rev": REV, "files": [MemoryPath("target", b"functions: {shell: [{code: '\xff'}]}")]})


def test_long_alias_chain_does_not_recurse_or_rewrite_target_identity():
    docs = {f"alias{i}": {"alias": f"alias{i+1}"} for i in range(1200)}
    docs["alias1200"] = {"alias": "target"}
    docs["target"] = SHELL
    resolution = prepare_documents(docs)
    assert not resolution.errors
    assert resolution.target_for["alias0"] == "target"
    entry = derive_document(resolution, "target", REV).emissions[0]
    assert entry.id == "gtfobins/target/shell/unprivileged"
    assert len(entry.material["aliases"]) == 1201


def test_context_caveat_is_retained_without_replacing_raw_claims():
    docs = {"tool": {"functions": {"shell": [{"code": "base", "comment": "general caveat", "contexts": {"sudo": {"code": "specialized", "comment": "context caveat"}}}]}}}
    entry = derive_document(prepare_documents(docs), "tool", REV).emissions[0]
    assert entry.material["commands"] == [{"template": "specialized", "comment": "general caveat\n\ncontext caveat"}]
    assert entry.raw_documents == docs


def test_supported_and_unknown_function_in_same_file_does_not_exempt_unknown():
    raw = {"rev": REV, "files": [MemoryPath("target", b"functions: {shell: [{code: literal}]}"), MemoryPath("launcher", b"functions: {inherit: [{code: activation, from: target}], invented: [{code: unsupported}]}")]}
    result = preflight(raw)
    assert result["supported_function_refs"] == ["_gtfobins/launcher#"]
    assert result["diagnostics"] == [{"input_ref": "_gtfobins/launcher#", "code": "UNKNOWN_FUNCTION"}]
    with pytest.raises(GTFOError, match="diagnostic-free"):
        list(GTFOBinsAdapter().normalize({**raw, "profile": "publication-v2"}))


def test_yaml_document_parser_does_not_split_literal_fences_inside_command():
    body = b"---\nfunctions:\n  shell:\n  - code: |-\n      echo '---'\n      retain this second line\n...\n"
    raw = {"rev": REV, "files": [MemoryPath("tool", body)], "profile": "publication-v2"}
    result = list(GTFOBinsAdapter().normalize(raw))
    assert result[0].commands[0]["template"] == "echo '---'\nretain this second line"
