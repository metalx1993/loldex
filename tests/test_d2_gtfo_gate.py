"""Independent adversarial checks of GTFO publication-v2 integration."""
from dataclasses import replace
from unittest.mock import patch
import pytest

from adapters.gtfobins import GTFOBinsAdapter
from deployment.publication import publication_result
from deployment.source_health import _legacy_raw
from phase5.acquisition import VerifiedBundle, AcquiredFile

REV = "a" * 40


def bundle(files):
    return VerifiedBundle("GTFOBins", REV, "b" * 40,
                         tuple(AcquiredFile(name, body.encode()) for name, body in files))


def rejected(bundle_, adapter=None):
    adapter = adapter or GTFOBinsAdapter()
    try:
        result, _ = publication_result(bundle_, _legacy_raw(bundle_, profile="publication-v2"), adapter)
    except ValueError:
        return True
    return result["status"] != "ok"


def test_known_inherit_and_unknown_function_same_ref_must_still_fail():
    b = bundle([("target", "functions: {shell: [{code: literal}]}"),
                ("launcher", "functions: {inherit: [{code: activation, from: target}], invented: [{code: unsupported}]}")])
    assert rejected(b)


def test_alias_cycles_are_not_exempted_as_missing_functions():
    assert rejected(bundle([("a", "alias: b"), ("b", "alias: a")]))


def test_alias_and_function_ambiguity_is_not_exempted():
    assert rejected(bundle([("a", "alias: b\nfunctions: {shell: [{code: activation}]}"),
                           ("b", "functions: {shell: [{code: literal}]}")]))


def test_malformed_alias_target_cannot_be_used_to_clear_rejections():
    assert rejected(bundle([("a", "alias: b"), ("b", "functions: false")]))


def test_valid_explicit_alias_and_inherit_can_pass_without_transitive_claims():
    b = bundle([("alias", "alias: target"),
                ("target", "functions: {file-read: [{code: literal-read}]}"),
                ("launcher", "functions: {inherit: [{code: activation, from: target}]}")])
    result, entries = publication_result(b, _legacy_raw(b, profile="publication-v2"), GTFOBinsAdapter())
    assert result["status"] == "ok" and result["parsed_ok"] == 3
    assert len(entries) == 2
    launcher = next(entry for entry in entries if entry.name == "launcher")
    assert launcher.capabilities == ["command-execution"]
    assert launcher.enrichment["capabilities"][0]["confidence"]["level"] == "low"
    assert not any(entry.id.startswith("gtfobins/alias/") for entry in entries)


def test_silent_normalizer_skip_cannot_define_its_own_expected_emissions():
    b = bundle([("a", "functions: {shell: [{code: one}]}"),
                ("b", "functions: {shell: [{code: two}]}")])
    adapter = GTFOBinsAdapter()
    original = adapter.normalize
    with patch.object(adapter, "normalize", side_effect=lambda raw: iter(list(original(raw))[:-1])):
        assert rejected(b, adapter), "D2 trusted the normalizer's incomplete output as its expected corpus"


def test_normalizer_changed_material_cannot_define_its_own_fingerprint_oracle():
    b = bundle([("a", "functions: {shell: [{code: one}]}")])
    adapter = GTFOBinsAdapter()
    original = adapter.normalize
    def changed(raw):
        return [replace(entry, name="fabricated display material") for entry in original(raw)]
    with patch.object(adapter, "normalize", side_effect=changed):
        assert rejected(b, adapter), "D2 derived both actual and expected material from the same mutated normalizer"


def test_inherit_cannot_be_upgraded_from_heuristic_to_authoritative_claim():
    b = bundle([("target", "functions: {shell: [{code: literal}]}"),
                ("launcher", "functions: {inherit: [{code: activation, from: target}]}")])
    adapter = GTFOBinsAdapter()
    original = adapter.normalize
    def upgrade_claim(raw):
        entries = list(original(raw))
        for entry in entries:
            if entry.name == "launcher":
                claim = entry.enrichment["capabilities"][0]
                claim["provenance"]["type"] = "adapter"
                claim["confidence"]["level"] = "high"
        return entries
    with patch.object(adapter, "normalize", side_effect=upgrade_claim):
        assert rejected(b, adapter), "material equality cannot authorize changing the meaning of provenance/confidence"


def test_rehashed_fabricated_raw_evidence_does_not_count_as_verified_source():
    from adapters import projection
    b = bundle([("a", "functions: {shell: [{code: literal}]}")])
    adapter = GTFOBinsAdapter()
    original = adapter.normalize
    def forge_raw(raw):
        entries = list(original(raw))
        for entry in entries:
            entry.source_data["GTFOBins"]["raw"]["documents"]["a"]["functions"]["shell"][0]["code"] = "fabricated raw evidence"
            entry.meta["source_hashes"] = projection.compute_source_hashes(entry.source_data)
        return entries
    with patch.object(adapter, "normalize", side_effect=forge_raw):
        assert rejected(b, adapter), "self-consistent raw hashes do not prove correspondence with acquired bytes"


def test_fabricated_upstream_url_cannot_bypass_nonmaterial_exclusion():
    b = bundle([("a", "functions: {shell: [{code: literal}]}")])
    adapter = GTFOBinsAdapter()
    original = adapter.normalize
    def forge_url(raw):
        entries = list(original(raw))
        for entry in entries:
            entry.source_data["GTFOBins"]["upstream_url"] = "https://unrelated.invalid/fabricated"
        return entries
    with patch.object(adapter, "normalize", side_effect=forge_url):
        assert rejected(b, adapter), "a valid-looking URL is not proof of source attribution"


def test_single_unicode_source_filename_has_one_nfc_public_identity():
    b = bundle([("e\u0301", "functions: {shell: [{code: literal}]}")])
    result, entries = publication_result(b, _legacy_raw(b, profile="publication-v2"), GTFOBinsAdapter())
    assert result["status"] == "ok"
    assert entries[0].id == "gtfobins/é/shell/unprivileged"


def test_raw_input_revision_cannot_differ_from_verified_bundle():
    b = bundle([("a", "functions: {shell: [{code: literal}]}")])
    raw = _legacy_raw(b, profile="publication-v2")
    raw["rev"] = "c" * 40
    with pytest.raises(ValueError, match="differs from verified bundle"):
        publication_result(b, raw, GTFOBinsAdapter())


def test_raw_input_bytes_cannot_be_replaced_after_acquisition():
    from deployment.source_health import MemoryPath
    b = bundle([("a", "functions: {shell: [{code: literal}]}")])
    raw = _legacy_raw(b, profile="publication-v2")
    raw["files"] = [MemoryPath("a", b"functions: {shell: [{code: fabricated}]}")]
    with pytest.raises(ValueError, match="differs from verified bundle"):
        publication_result(b, raw, GTFOBinsAdapter())


def test_default_profile_cannot_be_silently_treated_as_publication_v2():
    b = bundle([("a", "functions: {shell: [{code: literal}]}")])
    with pytest.raises(ValueError, match="differs from verified bundle"):
        publication_result(b, _legacy_raw(b), GTFOBinsAdapter())


def test_alias_ref_exemption_cannot_override_normalized_path_collision():
    b = bundle([("e\u0301", "alias: target"), ("é", "alias: target"),
                ("target", "functions: {shell: [{code: literal}]}")])
    assert rejected(b)
