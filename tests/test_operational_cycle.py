"""Linked fixtures are synthetic consistency tests, never production evidence."""
import copy
import json

import pytest

from scripts.check_operational_cycle import STEPS, PUBLISHER_COMMAND_SHA256, main, verify_cycle

A, B, T, U = 'a' * 40, 'b' * 40, 'c' * 40, 'd' * 40
R = 'r-' + 'e' * 64
D = 'f' * 64


def valid_evidence(changed=True):
    sha, tree = (B, U) if changed else (A, T)
    return {'version': 1, 'repository': 'metalx1993/loldex',
            'run': {'id': 123, 'event': 'schedule', 'status': 'completed', 'conclusion': 'success',
                    'head_branch': 'main', 'head_sha': A, 'workflow_path': '.github/workflows/sync.yml',
                    'run_attempt': 1, 'started_at': '2026-11-16T04:00:00Z', 'completed_at': '2026-11-16T04:20:00Z'},
            'job': {'id': 456, 'run_id': 123, 'head_sha': A, 'status': 'completed', 'conclusion': 'success',
                    'steps': [{'number': i, 'name': name, 'status': 'completed',
                               'conclusion': 'skipped' if name == STEPS[-1] and not changed else 'success'}
                              for i, name in enumerate(STEPS, 1)]},
            'candidate': {'base_sha': A, 'base_tree_sha': T, 'tree_sha': tree, 'changed': changed},
            'snapshot': {'sha': sha, 'parents': [A] if changed else ['0' * 40], 'tree_sha': tree},
            'publication': {'run_id': 123, 'job_id': 456, 'remote_sha': sha, 'log_sha256': D},
            'host': {'schedule': {'id': 'host-job-1', 'command_sha256': PUBLISHER_COMMAND_SHA256, 'cron': '30 * * * *', 'observed_at': '2026-11-15T08:00:00Z'},
                     'execution': {'job_id': 'host-job-1', 'started_at': '2026-11-16T04:30:00Z', 'completed_at': '2026-11-16T04:31:00Z',
                                   'log_sha256': D, 'commit': sha, 'release_id': R, 'generation': 15},
                     'active': {'commit': sha, 'release_id': R, 'generation': 15, 'observed_at': '2026-11-16T04:31:10Z'}},
            'live': {'release_id': R, 'observed_at': '2026-11-16T04:32:00Z',
                     'root_redirect': {'url': 'https://loldex.sh/api/v1/entries?limit=1', 'status': 307,
                                       'location': 'https://loldex.sh/releases/' + R + '/api/v1/entries?limit=1'},
                     'requests': [{'url': 'https://loldex.sh/releases/' + R + '/api/v1/entries?limit=1', 'status': 200, 'release_id': R, 'body_sha256': D}]}}


@pytest.mark.parametrize('changed,expected', [(True, 'VERIFIED_CHANGED'), (False, 'VERIFIED_NO_CHANGE')])
def test_complete_linked_supplied_evidence_and_no_change_are_distinct(changed, expected):
    evidence = valid_evidence(changed)
    original = copy.deepcopy(evidence)
    assert verify_cycle(evidence)['status'] == expected
    assert evidence == original


def test_absent_schedule_is_pending_not_success():
    evidence = {key: None for key in ('run', 'job', 'candidate', 'snapshot', 'publication', 'host', 'live')}
    evidence.update(version=1, repository='metalx1993/loldex')
    assert verify_cycle(evidence)['status'] == 'PENDING'


@pytest.mark.parametrize('section,key,value', [
    ('run', 'event', 'workflow_dispatch'), ('run', 'run_attempt', 2),
    ('run', 'conclusion', 'failure'), ('run', 'head_branch', 'other'),
    ('run', 'workflow_path', '.github/workflows/other.yml'),
    ('job', 'run_id', 124), ('job', 'head_sha', B), ('job', 'conclusion', 'failure'),
    ('candidate', 'base_sha', B), ('candidate', 'tree_sha', T),
    ('snapshot', 'parents', [A, B]), ('snapshot', 'tree_sha', T),
    ('publication', 'remote_sha', A), ('publication', 'job_id', 457),
])
def test_cross_run_manual_failed_and_untested_snapshots_fail(section, key, value):
    evidence = valid_evidence()
    evidence[section][key] = value
    assert verify_cycle(evidence)['status'] == 'FAIL'


def test_missing_and_reordered_full_test_gates_fail():
    evidence = valid_evidence()
    evidence['job']['steps'] = [step for step in evidence['job']['steps'] if step['name'] != 'Hard test gate']
    assert verify_cycle(evidence)['status'] == 'FAIL'
    evidence = valid_evidence()
    evidence['job']['steps'][0], evidence['job']['steps'][1] = evidence['job']['steps'][1], evidence['job']['steps'][0]
    assert verify_cycle(evidence)['status'] == 'FAIL'


@pytest.mark.parametrize('changed', [True, False])
def test_changed_and_no_change_must_match_publish_step(changed):
    evidence = valid_evidence(changed)
    evidence['job']['steps'][-1]['conclusion'] = 'success' if not changed else 'skipped'
    assert verify_cycle(evidence)['status'] == 'FAIL'


def test_no_change_cannot_smuggle_a_new_commit():
    evidence = valid_evidence(False)
    evidence['snapshot']['sha'] = B
    assert verify_cycle(evidence)['status'] == 'FAIL'


@pytest.mark.parametrize('target,key,value', [
    ('execution', 'commit', A), ('execution', 'job_id', 'manual-command'),
    ('execution', 'started_at', '2026-11-16T04:10:00Z'),
    ('schedule', 'observed_at', '2026-11-16T04:40:00Z'),
    ('active', 'generation', 14), ('active', 'release_id', 'r-' + 'a' * 64),
])
def test_host_must_follow_this_refresh_and_match_scheduler_and_active_token(target, key, value):
    evidence = valid_evidence()
    evidence['host'][target][key] = value
    assert verify_cycle(evidence)['status'] == 'FAIL'


def test_unpinned_or_stale_https_checks_fail():
    evidence = valid_evidence()
    evidence['live']['requests'][0]['url'] = 'https://other.invalid/'
    assert verify_cycle(evidence)['status'] == 'FAIL'
    evidence = valid_evidence()
    evidence['live']['observed_at'] = '2026-11-15T04:32:00Z'
    assert verify_cycle(evidence)['status'] == 'FAIL'


def test_cli_pending_fail_and_duplicate_key_do_not_return_success(tmp_path, capsys):
    evidence = valid_evidence()
    evidence['host'] = None
    path = tmp_path / 'evidence.json'
    path.write_text(json.dumps(evidence))
    assert main([str(path)]) == 2
    assert json.loads(capsys.readouterr().out)['status'] == 'PENDING'
    path.write_text('{"version":1,"version":1}')
    assert main([str(path)]) == 1
    assert json.loads(capsys.readouterr().out)['status'] == 'FAIL'
