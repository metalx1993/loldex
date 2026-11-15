"""Independent false-green probes; fixtures are synthetic, never live evidence."""
import hashlib

import pytest

from knowledge.registry import load_registry
from scripts.build_all import complete_artifacts
from scripts.check_operational_cycle import verify_cycle
from scripts.quality_report import baseline
from tests.test_operational_cycle import valid_evidence
from tests.test_quality_report import entry


def _replace(document, path, value):
    target = document
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value


@pytest.mark.parametrize('path,value', [
    (('host', 'schedule', 'command_sha256'), hashlib.sha256(b'echo success').hexdigest()),
    (('run', 'run_attempt'), True),
    (('job', 'steps', 9, 'conclusion'), 'skipped'),
    (('host', 'active', 'generation'), True),
    (('host', 'active', 'observed_at'), '2026-11-16T04:30:30Z'),
    (('live', 'root_redirect', 'location'), 'https://loldex.sh/releases/r-' + 'a' * 64 + '/api/v1/entries?limit=1'),
    (('live', 'requests', 0, 'release_id'), 'r-' + 'a' * 64),
    (('live', 'requests', 0, 'url'), 'https://loldex.sh/releases/r-' + 'e' * 64 + '/api/v1/search?q=test'),
    (('live', 'requests', 0, 'status'), 200.0),
])
def test_independent_operational_false_green_probes(path, value):
    evidence = valid_evidence()
    _replace(evidence, path, value)
    assert verify_cycle(evidence)['status'] == 'FAIL'


def test_no_change_does_not_excuse_skipped_test_or_altered_tree():
    evidence = valid_evidence(False)
    evidence['job']['steps'][9]['conclusion'] = 'skipped'
    assert verify_cycle(evidence)['status'] == 'FAIL'
    evidence = valid_evidence(False)
    evidence['candidate']['tree_sha'] = 'd' * 40
    evidence['snapshot']['tree_sha'] = 'd' * 40
    assert verify_cycle(evidence)['status'] == 'FAIL'


def test_known_failed_job_is_not_masked_by_missing_host_evidence():
    evidence = valid_evidence()
    evidence['host'] = None
    evidence['job']['conclusion'] = 'failure'
    assert verify_cycle(evidence)['status'] == 'FAIL'


def test_malformed_present_section_is_not_masked_by_another_absent_section():
    evidence = valid_evidence()
    evidence['host'] = None
    evidence['publication']['run_id'] = True
    assert verify_cycle(evidence)['status'] == 'FAIL'


def test_completed_job_cannot_have_unfinished_step_when_candidate_is_absent():
    evidence = valid_evidence()
    evidence['candidate'] = None
    evidence['job']['steps'][-1].update(status='in_progress', conclusion=None)
    assert verify_cycle(evidence)['status'] == 'FAIL'


@pytest.fixture
def local_views(tmp_path):
    corpus = [entry()]
    registry = load_registry()
    for name, raw in complete_artifacts(corpus, registry).items():
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    return corpus, registry, tmp_path


def test_interpretation_cannot_be_hidden_in_source_layer(local_views):
    corpus, registry, site = local_views
    corpus[0]['source_data']['LOLBAS']['capabilities'] = ['file-download']
    with pytest.raises(ValueError):
        baseline(corpus, registry, None, site)


def test_claim_cannot_borrow_another_sources_membership(local_views):
    corpus, registry, site = local_views
    corpus[0]['enrichment']['capabilities'][0]['provenance']['source'] = 'GTFOBins'
    with pytest.raises(ValueError):
        baseline(corpus, registry, None, site)


def test_duplicate_entries_are_not_destructively_deduplicated(local_views):
    corpus, registry, site = local_views
    with pytest.raises(ValueError):
        baseline(corpus + corpus, registry, None, site)


def test_site_symlink_cannot_stand_in_for_verified_directory(local_views):
    corpus, registry, site = local_views
    alias = site.parent / (site.name + '-alias')
    alias.symlink_to(site, target_is_directory=True)
    with pytest.raises(ValueError):
        baseline(corpus, registry, None, alias)
