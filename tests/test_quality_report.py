"""Negative evidence must not become a green Phase 10 report."""
import copy

import pytest

from scripts.build_all import complete_artifacts
from tests.test_registry import registry as load_registry
from scripts.quality_report import baseline
from scripts import quality_report


def entry():
    return {"id": "lolbas/test/execute/0", "name": "Test", "platform": "windows",
            "type": "binary", "privilege_required": "user", "phases": ["execution"],
            "sources": [{"project": "LOLBAS"}], "source_data": {"LOLBAS": {"raw": {"Name": "Test"}, "upstream_url": "https://example.test/Test"}},
            "enrichment": {"capabilities": [{"value": "file-download",
                "provenance": {"type": "adapter", "source": "LOLBAS"},
                "confidence": {"level": "high"}}],
                "phases": [{"value": "execution", "provenance": {"type": "adapter", "source": "LOLBAS"}, "confidence": {"level": "high"}}],
                "privilege_required": {"value": "user", "provenance": {"type": "adapter", "source": "LOLBAS"}, "confidence": {"level": "high"}}}, "capabilities": ["file-download"]}


@pytest.fixture
def corpus(tmp_path):
    entries = [entry()]
    payloads = complete_artifacts(entries, load_registry())
    for name, raw in payloads.items():
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    return entries, tmp_path


def test_matching_views_are_reproducible_and_read_only(corpus):
    entries, site = corpus
    original = copy.deepcopy(entries)
    before = {p.relative_to(site): p.read_bytes() for p in site.rglob('*') if p.is_file()}
    a = baseline(entries, load_registry(), None, site)
    assert a == baseline(entries, load_registry(), None, site)
    assert a['status'] == 'PASS' and a['entries'] == 1
    assert entries == original
    assert before == {p.relative_to(site): p.read_bytes() for p in site.rglob('*') if p.is_file()}


@pytest.mark.parametrize('damage', ['missing', 'altered', 'symlink', 'extra'])
def test_incomplete_tampered_or_unowned_output_fails_without_repair(corpus, damage):
    entries, site = corpus
    target = site / 'catalog.json'
    if damage == 'missing':
        target.unlink()
    elif damage == 'altered':
        target.write_bytes(b'{}')
    elif damage == 'symlink':
        target.unlink()
        target.symlink_to(site / 'data.json')
    else:
        (site / 'evidence-records' / 'unowned.json').write_bytes(b'{}')
    result = baseline(entries, load_registry(), None, site)
    assert result['status'] == 'FAIL' and result['issues']
    if damage == 'missing':
        assert not target.exists()
    elif damage == 'altered':
        assert target.read_bytes() == b'{}'
    elif damage == 'symlink':
        assert target.is_symlink()
    else:
        assert (site / 'evidence-records' / 'unowned.json').exists()


@pytest.mark.parametrize('damage', ['confidence', 'provenance', 'projection'])
def test_invalid_claim_or_projection_cannot_produce_positive_report(corpus, damage):
    entries, site = corpus
    claim = entries[0]['enrichment']['capabilities'][0]
    if damage == 'projection':
        entries[0]['capabilities'] = ['defense-evasion']
    else:
        del claim[damage]
    with pytest.raises(ValueError):
        baseline(entries, load_registry(), None, site)


def test_cli_validation_error_is_machine_readable_and_nonzero(monkeypatch, capsys):
    import json

    def invalid(_path):
        raise ValueError('invalid corpus fixture')

    monkeypatch.setattr(quality_report, '_input_files', lambda _state=None: [])
    monkeypatch.setattr(quality_report, 'read_entries', invalid)
    assert quality_report.main([]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result['status'] == 'FAIL'
    assert result['issues'][0]['reason'] == 'input_or_validation_error'


@pytest.mark.parametrize('name', ['openapi-v1.json', 'registry-license.txt', 'build-manifest.json'])
def test_additional_generated_artifacts_are_not_outside_the_gate(corpus, name):
    entries, site = corpus
    target = site / name
    target.write_bytes(b'forged or stale output')
    result = baseline(entries, load_registry(), None, site)
    assert result['status'] == 'FAIL'
    assert {'file': name, 'reason': 'content_mismatch'} in result['issues']
    assert target.read_bytes() == b'forged or stale output'


@pytest.mark.parametrize('entries', [[], None, {}, [None]])
def test_empty_or_malformed_entry_collection_cannot_pass(tmp_path, entries):
    with pytest.raises(ValueError, match='nonempty list'):
        baseline(entries, load_registry(), None, tmp_path)


@pytest.mark.parametrize('damage', ['type', 'privilege_required', 'upstream_url', 'source_data_leak'])
def test_full_entry_contract_is_checked_even_if_views_could_match(corpus, damage):
    entries, site = corpus
    if damage == 'upstream_url':
        del entries[0]['source_data']['LOLBAS']['upstream_url']
    elif damage == 'source_data_leak':
        entries[0]['source_data']['LOLBAS']['capabilities'] = ['shell']
    else:
        entries[0][damage] = 'invalid'
    with pytest.raises(ValueError):
        baseline(entries, load_registry(), None, site)


def test_missing_site_root_is_an_error_not_an_empty_pass(tmp_path):
    with pytest.raises(ValueError, match='required directory'):
        baseline([entry()], load_registry(), None, tmp_path / 'missing')


def test_site_root_symlink_is_rejected_before_reading(corpus, tmp_path):
    entries, site = corpus
    link = site.parent / (site.name + '-link')
    link.symlink_to(site, target_is_directory=True)
    with pytest.raises(ValueError, match='symlinks'):
        baseline(entries, load_registry(), None, link)


def test_expected_fifo_is_not_opened(corpus):
    import os
    entries, site = corpus
    target = site / 'catalog.json'
    target.unlink()
    os.mkfifo(target)
    result = baseline(entries, load_registry(), None, site)
    assert {'file': 'catalog.json', 'reason': 'missing_or_nonregular'} in result['issues']


@pytest.mark.parametrize('damage', ['missing', 'empty', 'symlink', 'malformed_yaml', 'duplicate_yaml', 'duplicate_api', 'duplicate_schema'])
def test_cli_bad_corpus_input_emits_json_failure_without_writes(tmp_path, monkeypatch, capsys, damage):
    import json
    import shutil
    corpus = tmp_path / 'data/entries'
    (tmp_path / 'site').mkdir()
    if damage != 'missing':
        corpus.mkdir(parents=True)
    for name in ('data/registry/enterprise-attack.json', 'data/identity/registry.json',
                 'api/openapi-v1.json', 'data/registry/LICENSE-MITRE.txt', 'schema/schema.yaml'):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(quality_report.ROOT / name, target)
    if damage == 'malformed_yaml':
        (corpus / 'entry.yaml').write_text('name: [unterminated')
    elif damage == 'duplicate_yaml':
        (corpus / 'entry.yaml').write_text('name: first\nname: second\n')
    elif damage == 'symlink':
        (corpus / 'entry.yaml').symlink_to(tmp_path / 'data/identity/registry.json')
    elif damage in {'duplicate_api', 'duplicate_schema'}:
        import yaml
        (corpus / 'entry.yaml').write_text(yaml.safe_dump(entry()))
        if damage == 'duplicate_api':
            (tmp_path / 'api/openapi-v1.json').write_text('{"openapi":"3.0.0","openapi":"3.1.0"}')
        else:
            (tmp_path / 'schema/schema.yaml').write_text('taxonomy: {}\ntaxonomy: {}\n')
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file() and not p.is_symlink()}
    monkeypatch.setattr(quality_report, 'ROOT', tmp_path)
    assert quality_report.main([]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result['status'] == 'FAIL'
    assert result['issues'][0]['reason'] == 'input_or_validation_error'
    assert before == {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file() and not p.is_symlink()}


def test_input_change_during_check_cannot_leave_a_positive_report(corpus, monkeypatch, capsys, tmp_path):
    import json
    entries, site = corpus
    witness = tmp_path / 'witness.txt'
    witness.write_text('before')
    original_baseline = quality_report.baseline

    def changing_baseline(*args, **kwargs):
        result = original_baseline(entries, load_registry(), None, site)
        assert result['status'] == 'PASS'
        witness.write_text('after')
        return result

    monkeypatch.setattr(quality_report, '_input_files', lambda _state=None: [witness])
    monkeypatch.setattr(quality_report, 'read_entries', lambda _path: entries)
    monkeypatch.setattr(quality_report, 'baseline', changing_baseline)
    assert quality_report.main([]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result['status'] == 'FAIL'
    assert result['input_snapshot']['stable_at_recheck'] is False
    assert {'reason': 'inputs_changed_during_check'} in result['issues']


def test_input_digest_is_portable_across_checkout_paths(tmp_path, monkeypatch):
    digests = []
    for name in ('checkout-one', 'checkout-two'):
        root = tmp_path / name
        path = root / 'data/entries/a.yaml'
        path.parent.mkdir(parents=True)
        path.write_bytes(b'id: fixed\n')
        monkeypatch.setattr(quality_report, 'ROOT', root)
        digests.append(quality_report._fingerprint([path]))
    assert digests[0] == digests[1]
