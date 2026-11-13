"""Independent publication-v2 identity/evidence bridge tests, all local temporary repos."""
from dataclasses import replace
from unittest.mock import patch

import pytest
import yaml

from tests.test_publication_health import repositories, commit
from adapters.lolbas import LOLBASAdapter
from deployment.source_health import prepare_verified_sync, SourceHealthError


def test_d2_bridge_binds_public_entry_identity_to_the_healthy_gate_result(repositories, tmp_path):
    original = LOLBASAdapter.normalize
    calls = 0

    def changed_after_gate(self, raw):
        nonlocal calls
        calls += 1
        for entry in original(self, raw):
            yield replace(entry, id=entry.id + '/changed-after-gate') if calls > 1 else entry

    target = tmp_path / 'candidate'
    with patch.object(LOLBASAdapter, 'normalize', changed_after_gate):
        with pytest.raises(SourceHealthError):
            prepare_verified_sync(repositories, target, profile='publication-v2')
    assert not target.exists()


def test_d2_same_triple_distinct_lolad_reference_aborts_before_staging(repositories, tmp_path):
    repo = repositories['LOLAD'][0]
    text = '<table><tr><th>Name</th><th>Command</th><th>Type</th><th>Reference</th></tr>'
    text += '<tr><td>Same</td><td>cmd</td><td>CMD</td><td>A</td></tr>'
    text += '<tr><td>Same</td><td>cmd</td><td>CMD</td><td>B</td></tr></table>'
    (repo / 'index.html').write_text(text)
    commit(repo)
    target = tmp_path / 'candidate'
    with pytest.raises(SourceHealthError) as error:
        prepare_verified_sync(repositories, target, profile='publication-v2')
    assert any(result['source'] == 'LOLAD' and result['status'] == 'failed' for result in error.value.results)
    assert not target.exists()


def test_d2_lolbas_collision_cannot_hide_malformed_detection(repositories, tmp_path):
    repo = repositories['LOLBAS'][0]
    (repo / 'yml/OSScripts/test.yml').write_text('Detection: {}\nCommands:\n- Category: Execute\n  Command: script\n')
    commit(repo)
    target = tmp_path / 'candidate'
    with pytest.raises(SourceHealthError) as error:
        prepare_verified_sync(repositories, target, profile='publication-v2')
    assert any(result['source'] == 'LOLBAS' and result['status'] == 'failed' for result in error.value.results)
    assert not target.exists()


def _refresh_fixture(tmp_path, monkeypatch, *, symlink_data=False):
    import subprocess
    import scripts.verified_refresh as refresh_module
    repo = tmp_path / 'candidate-checkout'
    repo.mkdir()
    data = tmp_path / 'external-data' if symlink_data else repo / 'data'
    (data / 'entries').mkdir(parents=True)
    (data / 'entries/old.yaml').write_text('id: old\n')
    if symlink_data:
        (repo / 'data').symlink_to(data, target_is_directory=True)
    (repo / 'site').mkdir()
    (repo / 'site/index.html').write_text('old')
    (repo / '.gitignore').write_text('data/entries/ignored.yaml\n')
    subprocess.run(['git', '-C', str(repo), 'init', '-q'], check=True, capture_output=True)
    subprocess.run(['git', '-C', str(repo), 'add', '.'], check=True, capture_output=True)
    subprocess.run(['git', '-C', str(repo), '-c', 'user.name=fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture'], check=True, capture_output=True)
    expected = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD']).decode().strip()
    prepared = tmp_path / 'prepared'
    (prepared / 'data/entries').mkdir(parents=True)
    (prepared / 'data/entries/new.yaml').write_text('id: new\n')
    (prepared / 'site').mkdir()
    (prepared / 'site/data.json').write_text('{}')
    (prepared / 'source-health.json').write_text('{}')
    monkeypatch.setattr(refresh_module, 'prepare_verified_sync', lambda *args, **kwargs: prepared)
    monkeypatch.setattr(refresh_module, 'build_all', lambda *args, **kwargs: None)
    return refresh_module, repo, prepared, expected, data


@pytest.mark.parametrize('name', ['untracked.yaml', 'ignored.yaml'])
def test_refresh_never_deletes_untracked_or_ignored_work_from_a_clean_checkout(tmp_path, monkeypatch, name):
    module, repo, prepared, expected, data = _refresh_fixture(tmp_path, monkeypatch)
    work = data / 'entries' / name
    work.write_text('user work never committed\n')
    with pytest.raises(ValueError):
        module.refresh({}, repo, prepared, expected)
    assert work.read_text() == 'user work never committed\n'


def test_refresh_cannot_delete_a_data_tree_outside_checkout_through_a_tracked_symlink(tmp_path, monkeypatch):
    module, repo, prepared, expected, data = _refresh_fixture(tmp_path, monkeypatch, symlink_data=True)
    with pytest.raises(ValueError):
        module.refresh({}, repo, prepared, expected)
    assert (data / 'entries/old.yaml').read_text() == 'id: old\n'


@pytest.mark.parametrize('defect', ['skip', 'material', 'confidence', 'raw'])
def test_independent_source_oracle_rejects_a_defective_normalizer_even_during_the_first_gate(defect):
    from tests.test_publication_identities import lolbas_raw
    from phase5.acquisition import AcquiredFile, VerifiedBundle
    from deployment.publication import publication_result
    from adapters.projection import compute_source_hashes
    raw = {**lolbas_raw(), 'profile': 'publication-v2'}
    bundle = VerifiedBundle('LOLBAS', 'a' * 40, 'b' * 40,
                            tuple(AcquiredFile(path.relative, path.text.encode()) for _, path in raw['files']))
    from deployment.source_health import _legacy_raw
    raw = _legacy_raw(bundle, profile='publication-v2')
    original = LOLBASAdapter.normalize

    def corrupt(self, source):
        entries = list(original(self, source))
        if defect == 'skip':
            return iter(entries[:1])
        if defect == 'material':
            entries[0].name += ' changed'
        elif defect == 'confidence':
            entries[0].enrichment['capabilities'][0]['confidence']['level'] = 'verified'
        else:
            entries[0].source_data['LOLBAS']['raw']['document_utf8'] += '\nforged evidence'
            entries[0].meta['source_hashes'] = compute_source_hashes(entries[0].source_data)
        return iter(entries)

    with patch.object(LOLBASAdapter, 'normalize', corrupt):
        with pytest.raises(ValueError, match='independent preflight'):
            publication_result(bundle, raw, LOLBASAdapter())
