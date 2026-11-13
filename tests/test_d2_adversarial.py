"""Independent D2 publication integrity and preparation-boundary attacks."""
from unittest.mock import patch

import pytest

from tests.test_d2_integration import _refresh_fixture
from tests.test_publication_health import repositories
from deployment.source_health import prepare_verified_sync, SourceHealthError
from adapters.loldrivers import LOLDriversAdapter
from adapters.wadcoms import WADComsAdapter


@pytest.mark.parametrize('kind', ['untracked', 'ignored', 'symlink'])
def test_refresh_rechecks_late_uncommitted_work_before_destructive_replacement(tmp_path, monkeypatch, kind):
    module, repo, prepared, expected, data = _refresh_fixture(tmp_path, monkeypatch)
    name = 'ignored.yaml' if kind == 'ignored' else 'late.yaml'
    work = data / 'entries' / name
    protected = tmp_path / 'protected.yaml'
    protected.write_text('preserve this work\n')

    def concurrent_work(*args, **kwargs):
        if kind == 'symlink':
            work.symlink_to(protected)
        else:
            work.write_text('preserve this work\n')

    monkeypatch.setattr(module, 'build_all', concurrent_work)
    with pytest.raises(ValueError):
        module.refresh({}, repo, prepared, expected)
    assert work.read_text() == 'preserve this work\n'
    assert (data / 'entries/old.yaml').exists()
    assert not (data / 'entries/new.yaml').exists()


@pytest.mark.parametrize('adapter', [LOLDriversAdapter, WADComsAdapter])
@pytest.mark.parametrize('defect', ['drop', 'material', 'confidence', 'raw'])
def test_complete_source_oracle_rejects_first_gate_normalizer_defects(repositories, tmp_path, adapter, defect):
    original = adapter.normalize_complete
    mutated = []

    def corrupt(self, raw):
        entries = list(original(self, raw))
        if defect == 'drop':
            mutated.append(defect)
            return iter(())
        entry = entries[0]
        if defect == 'material':
            entry.name += ' forged'
        elif defect == 'confidence':
            entry.enrichment['privilege_required']['confidence']['level'] = 'verified'
        else:
            source = next(iter(entry.source_data))
            entry.source_data[source]['raw']['document'] += '\n# forged evidence'
        mutated.append(defect)
        return iter(entries)

    target = tmp_path / 'output'
    with patch.object(adapter, 'normalize_complete', corrupt):
        with pytest.raises(SourceHealthError):
            prepare_verified_sync(repositories, target, profile='publication-v2')
    assert mutated == [defect]
    assert not target.exists()
