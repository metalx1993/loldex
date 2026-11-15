"""Offline correlation of supplied automatic-cycle evidence; no external actions.

VERIFIED_* means internally consistent supplied evidence, never authentication of
its origin. Retain original GitHub, scheduler, log and HTTPS captures for review.
"""
from __future__ import annotations

import argparse
import hashlib
from datetime import datetime, timezone
import json
from pathlib import Path
import re

REPOSITORY = 'metalx1993/loldex'
WORKFLOW = '.github/workflows/sync.yml'
STEPS = (
    'Checkout main', 'Set up Python', 'Install dependencies',
    'Install isolated PHP test interpreter', 'Record acquisition base',
    'Acquire five public upstream repositories',
    'Prepare complete verified D2 snapshot and all derived views',
    'Validate entries', 'Rebuild validated site and knowledge data',
    'Read-only generated-data quality gate',
    'Hard test gate', 'Stage candidate',
    'Publish only onto the unchanged acquisition base',
)
PUBLISHER_COMMAND = ('cd /home/customer/www/loldex.sh/loldex-control/tools && /bin/python3 -m deployment.pull '
                     '--repo /home/customer/www/loldex.sh/loldex-control/repository.git '
                     '--public-root /home/customer/www/loldex.sh/public_html '
                     '--control-root /home/customer/www/loldex.sh/loldex-control '
                     '>> /home/customer/www/loldex.sh/loldex-control/publisher.log 2>&1')
PUBLISHER_COMMAND_SHA256 = hashlib.sha256(PUBLISHER_COMMAND.encode()).hexdigest()
SCOPE = 'consistency_of_supplied_operational_evidence'
SECTIONS = {'run', 'job', 'candidate', 'snapshot', 'publication', 'host', 'live'}


def _object(value, keys, label):
    if not isinstance(value, dict) or set(value) != set(keys.split()):
        raise ValueError(f'{label}: exact fields required: {keys}')
    return value


def _require(ok, message):
    if not ok:
        raise ValueError(message)


def _sha(value):
    _require(isinstance(value, str) and re.fullmatch(r'[0-9a-f]{40}', value), 'invalid Git SHA')
    return value


def _positive(value):
    _require(type(value) is int and value > 0, 'positive integer required')
    return value


def _text(value):
    _require(isinstance(value, str) and bool(value.strip()), 'nonempty evidence reference required')
    return value


def _time(value):
    _require(isinstance(value, str), 'timestamp must be text')
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError('invalid timestamp') from exc
    _require(dt.tzinfo is not None and dt.utcoffset() is not None, 'timezone required')
    return dt.astimezone(timezone.utc)


def _digest(value):
    _require(isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value), 'invalid evidence SHA-256')


def _release(value):
    _require(isinstance(value, str) and re.fullmatch(r'r-[0-9a-f]{64}', value), 'invalid release ID')
    return value


def _present(evidence):
    """Reject independently known failures before incomplete captures go pending."""
    shapes = {
        'job': 'id run_id head_sha status conclusion steps',
        'candidate': 'base_sha base_tree_sha tree_sha changed',
        'snapshot': 'sha parents tree_sha',
        'publication': 'run_id job_id remote_sha log_sha256',
        'host': 'schedule execution active',
        'live': 'release_id observed_at root_redirect requests',
    }
    for name, keys in shapes.items():
        if evidence[name] is not None:
            _object(evidence[name], keys, name)
    run, job, candidate = evidence['run'], evidence['job'], evidence['candidate']
    if job is not None:
        _positive(job['id']); _positive(job['run_id']); _sha(job['head_sha'])
        _require(job['status'] in ('queued', 'in_progress', 'completed'), 'invalid job status')
        _require(job['conclusion'] == ('success' if job['status'] == 'completed' else None), 'known failed or inconsistent job')
        if run is not None and isinstance(run, dict):
            _require(job['run_id'] == run.get('id') and job['head_sha'] == run.get('head_sha'), 'job belongs to another run')
        _require(isinstance(job['steps'], list), 'steps must be a list')
        names, numbers = [], []
        for step in job['steps']:
            _object(step, 'number name status conclusion', 'step')
            _positive(step['number']); _text(step['name'])
            _require(step['status'] in ('queued', 'in_progress', 'completed'), 'invalid step status')
            _require(step['conclusion'] in ('success', 'skipped') if step['status'] == 'completed' else step['conclusion'] is None, 'known failed or inconsistent step')
            names.append(step['name']); numbers.append(step['number'])
        _require(len(names) == len(set(names)) and len(numbers) == len(set(numbers)) and numbers == sorted(numbers), 'duplicate or reordered steps')
        if job['status'] == 'completed':
            _require(all(step['status'] == 'completed' for step in job['steps']), 'completed job contains unfinished step')
            _require(tuple(name for name in names if name in STEPS) == STEPS, 'missing required completed job gate')
            for step in job['steps']:
                if step['name'] in STEPS[:-1]:
                    _require(step['conclusion'] == 'success', 'required completed gate did not succeed')
    if candidate is not None:
        for name in ('base_sha', 'base_tree_sha', 'tree_sha'):
            _sha(candidate[name])
        _require(type(candidate['changed']) is bool, 'changed must be boolean')
        _require((candidate['tree_sha'] != candidate['base_tree_sha']) == candidate['changed'], 'candidate change/tree contradiction')
        if isinstance(run, dict):
            _require(candidate['base_sha'] == run.get('head_sha'), 'candidate belongs to another run base')
        if job is not None and job['status'] == 'completed':
            publish = next(step for step in job['steps'] if step['name'] == STEPS[-1])
            _require(publish['conclusion'] == ('success' if candidate['changed'] else 'skipped'), 'publication step/change contradiction')
    snapshot = evidence['snapshot']
    if snapshot is not None:
        _sha(snapshot['sha']); _sha(snapshot['tree_sha'])
        _require(isinstance(snapshot['parents'], list), 'parents must be a list')
        for parent in snapshot['parents']:
            _sha(parent)
        if candidate is not None:
            _require(snapshot['tree_sha'] == candidate['tree_sha'], 'snapshot tree differs from candidate')
            _require(snapshot['parents'] == [candidate['base_sha']] and snapshot['sha'] != candidate['base_sha'] if candidate['changed'] else snapshot['sha'] == candidate['base_sha'], 'snapshot/base relationship differs')
    publication = evidence['publication']
    if publication is not None:
        _positive(publication['run_id']); _positive(publication['job_id'])
        _sha(publication['remote_sha']); _digest(publication['log_sha256'])
        if isinstance(run, dict):
            _require(publication['run_id'] == run.get('id'), 'publication belongs to another run')
        if job is not None:
            _require(publication['job_id'] == job['id'], 'publication belongs to another job')
        if snapshot is not None:
            _require(publication['remote_sha'] == snapshot['sha'], 'remote snapshot mismatch')
    host = evidence['host']
    if host is not None:
        schedule = _object(host['schedule'], 'id command_sha256 cron observed_at', 'schedule')
        execution = _object(host['execution'], 'job_id started_at completed_at log_sha256 commit release_id generation', 'execution')
        active = _object(host['active'], 'commit release_id generation observed_at', 'active')
        _text(schedule['id']); _digest(schedule['command_sha256'])
        _require(schedule['command_sha256'] == PUBLISHER_COMMAND_SHA256 and schedule['cron'] == '30 * * * *', 'unreviewed scheduler command/profile')
        _require(execution['job_id'] == schedule['id'], 'host execution belongs to another scheduler job')
        _digest(execution['log_sha256']); _sha(execution['commit']); _release(execution['release_id']); _positive(execution['generation'])
        _sha(active['commit']); _release(active['release_id']); _positive(active['generation'])
        _require(all(active[key] == execution[key] for key in ('commit', 'release_id', 'generation')), 'active token mismatch')
        _require(_time(schedule['observed_at']) <= _time(execution['started_at']) <= _time(execution['completed_at']) <= _time(active['observed_at']), 'host evidence chronology mismatch')
        if isinstance(run, dict) and run.get('status') == 'completed':
            _require(_time(run.get('completed_at')) <= _time(execution['started_at']), 'host predates refresh completion')
        if snapshot is not None:
            _require(execution['commit'] == snapshot['sha'], 'host published another snapshot')
    live = evidence['live']
    if live is not None:
        _release(live['release_id']); _time(live['observed_at'])
        redirect = _object(live['root_redirect'], 'url status location', 'root_redirect')
        prefix = 'https://loldex.sh/releases/' + live['release_id'] + '/'
        _require(redirect['url'] == 'https://loldex.sh/api/v1/entries?limit=1' and type(redirect['status']) is int and redirect['status'] == 307 and redirect['location'] == prefix + 'api/v1/entries?limit=1', 'invalid root release redirect')
        _require(isinstance(live['requests'], list) and bool(live['requests']), 'missing live requests')
        seen_target = False
        for request in live['requests']:
            _object(request, 'url status release_id body_sha256', 'request')
            _digest(request['body_sha256'])
            _require(isinstance(request['url'], str) and request['url'].startswith(prefix) and '/../' not in request['url'] and '%' not in request['url'] and type(request['status']) is int and request['status'] == 200 and request['release_id'] == live['release_id'], 'invalid pinned live request')
            seen_target |= request['url'] == redirect['location']
        _require(seen_target, 'redirect destination not checked')
        if host is not None:
            _require(live['release_id'] == host['active']['release_id'] and _time(host['active']['observed_at']) <= _time(live['observed_at']), 'live capture mismatches host release/time')


def verify_cycle(evidence):
    """Return a conservative result; null sections are pending, never green."""
    try:
        _object(evidence, 'version repository run job candidate snapshot publication host live', 'evidence')
        _require(type(evidence['version']) is int and evidence['version'] == 1, 'unsupported version')
        _require(evidence['repository'] == REPOSITORY, 'wrong repository')
        missing = sorted(key for key in SECTIONS if evidence[key] is None)
        _present(evidence)
        # Validate present evidence even when another required section is absent.
        run = evidence['run']
        if run is not None:
            _object(run, 'id event status conclusion head_branch head_sha workflow_path run_attempt started_at completed_at', 'run')
            _positive(run['id'])
            _require(run['event'] == 'schedule', 'manual or non-schedule execution cannot certify automatic refresh')
            _require(run['run_attempt'] == 1 and type(run['run_attempt']) is int, 'rerun is not original automatic execution')
            _require(run['head_branch'] == 'main' and run['workflow_path'] == WORKFLOW, 'wrong branch or workflow')
            _sha(run['head_sha'])
            _require(run['status'] in ('queued', 'in_progress', 'completed'), 'invalid run status')
            if run['status'] != 'completed':
                _require(run['conclusion'] is None, 'unfinished run has conclusion')
                return {'version': 1, 'scope': SCOPE, 'status': 'PENDING', 'reasons': ['scheduled run not completed']}
            _require(run['conclusion'] == 'success', 'scheduled refresh did not succeed')
            _require(_time(run['started_at']) <= _time(run['completed_at']), 'run timestamps reversed')
        if missing:
            return {'version': 1, 'scope': SCOPE, 'status': 'PENDING', 'reasons': [f'missing {key}' for key in missing]}
        job = _object(evidence['job'], 'id run_id head_sha status conclusion steps', 'job')
        _positive(job['id'])
        _require(type(job['run_id']) is int and job['run_id'] == run['id'] and job['head_sha'] == run['head_sha'], 'job does not belong to this run/base')
        _require(job['status'] == 'completed' and job['conclusion'] == 'success', 'job did not succeed')
        _require(isinstance(job['steps'], list), 'steps must be a list')
        names, numbers = [], []
        for step in job['steps']:
            _object(step, 'number name status conclusion', 'step')
            _positive(step['number']); _text(step['name'])
            _require(step['status'] == 'completed' and step['conclusion'] in ('success', 'skipped'), 'failed or unfinished step')
            names.append(step['name']); numbers.append(step['number'])
        _require(len(set(names)) == len(names) and len(set(numbers)) == len(numbers) and numbers == sorted(numbers), 'duplicate or reordered steps')
        _require(tuple(name for name in names if name in STEPS) == STEPS, 'missing or reordered required gate')
        candidate = _object(evidence['candidate'], 'base_sha base_tree_sha tree_sha changed', 'candidate')
        _require(type(candidate['changed']) is bool, 'changed must be boolean')
        _require(_sha(candidate['base_sha']) == run['head_sha'], 'acquisition base differs from tested run')
        _sha(candidate['base_tree_sha']); _sha(candidate['tree_sha'])
        for step in job['steps']:
            if step['name'] in STEPS:
                expected = 'skipped' if step['name'] == STEPS[-1] and not candidate['changed'] else 'success'
                _require(step['conclusion'] == expected, 'required gate not executed as expected')
        snapshot = _object(evidence['snapshot'], 'sha parents tree_sha', 'snapshot')
        _sha(snapshot['sha']); _sha(snapshot['tree_sha'])
        _require(isinstance(snapshot['parents'], list) and all(isinstance(p, str) and re.fullmatch(r'[0-9a-f]{40}', p) for p in snapshot['parents']), 'invalid parents')
        publication = _object(evidence['publication'], 'run_id job_id remote_sha log_sha256', 'publication')
        _digest(publication['log_sha256'])
        _require(type(publication['run_id']) is int and type(publication['job_id']) is int and publication['run_id'] == run['id'] and publication['job_id'] == job['id'], 'publication belongs to another run/job')
        _require(_sha(publication['remote_sha']) == snapshot['sha'], 'remote publication mismatch')
        _require(candidate['tree_sha'] == snapshot['tree_sha'], 'published tree was not the tested candidate')
        if candidate['changed']:
            _require(snapshot['parents'] == [candidate['base_sha']] and snapshot['sha'] != candidate['base_sha'], 'changed snapshot must directly descend from acquisition base')
            _require(candidate['tree_sha'] != candidate['base_tree_sha'], 'changed candidate has unchanged tree')
        else:
            _require(snapshot['sha'] == candidate['base_sha'] and snapshot['tree_sha'] == candidate['base_tree_sha'], 'no-change lacks unchanged commit/tree evidence')
        host = _object(evidence['host'], 'schedule execution active', 'host')
        schedule = _object(host['schedule'], 'id command_sha256 cron observed_at', 'schedule')
        _text(schedule['id']); _digest(schedule['command_sha256'])
        _require(schedule['command_sha256'] == PUBLISHER_COMMAND_SHA256, 'scheduler command differs from reviewed publisher profile')
        _require(schedule['cron'] == '30 * * * *', 'unexpected host schedule')
        execution = _object(host['execution'], 'job_id started_at completed_at log_sha256 commit release_id generation', 'execution')
        _require(execution['job_id'] == schedule['id'], 'publisher execution not linked to configured scheduler job')
        _digest(execution['log_sha256']); _positive(execution['generation']); _release(execution['release_id'])
        _require(execution['commit'] == snapshot['sha'], 'host did not publish the accepted snapshot')
        _require(_time(schedule['observed_at']) <= _time(execution['started_at']), 'schedule was not observed before execution')
        _require(_time(run['completed_at']) <= _time(execution['started_at']) <= _time(execution['completed_at']), 'host execution did not follow completed refresh')
        active = _object(host['active'], 'commit release_id generation observed_at', 'active')
        _require(type(active['generation']) is int and active['commit'] == execution['commit'] and active['release_id'] == execution['release_id'] and active['generation'] == execution['generation'], 'active token differs from publisher receipt')
        _require(_time(execution['completed_at']) <= _time(active['observed_at']), 'active observation predates execution')
        live = _object(evidence['live'], 'release_id observed_at root_redirect requests', 'live')
        _require(live['release_id'] == active['release_id'], 'HTTPS release differs from active token')
        _require(_time(active['observed_at']) <= _time(live['observed_at']), 'HTTPS observation predates active token observation')
        _require(isinstance(live['requests'], list) and bool(live['requests']), 'no HTTPS checks')
        prefix = 'https://loldex.sh/releases/' + live['release_id'] + '/'
        redirect = _object(live['root_redirect'], 'url status location', 'root_redirect')
        _require(redirect['url'] == 'https://loldex.sh/api/v1/entries?limit=1' and type(redirect['status']) is int and redirect['status'] == 307, 'root API did not redirect')
        _require(redirect['location'] == prefix + 'api/v1/entries?limit=1', 'root API redirects to another release')
        _require(any(isinstance(r, dict) and r.get('url') == redirect['location'] for r in live['requests']), 'redirect target was not checked')
        for request in live['requests']:
            _object(request, 'url status release_id body_sha256', 'request')
            _require(isinstance(request['url'], str) and request['url'].startswith(prefix) and '/../' not in request['url'] and '%' not in request['url'], 'HTTPS request is not pinned to active release')
            _require(type(request['status']) is int and request['status'] == 200 and request['release_id'] == live['release_id'], 'HTTPS check failed or belongs to another release')
            _digest(request['body_sha256'])
        return {'version': 1, 'scope': SCOPE, 'status': 'VERIFIED_CHANGED' if candidate['changed'] else 'VERIFIED_NO_CHANGE',
                'run_id': run['id'], 'commit': snapshot['sha'], 'release_id': active['release_id'],
                'limits': ['Supplied evidence consistency only; origin, signatures and truth of captures require independent operator review.',
                           'Does not prove future scheduling, CORE freshness or correctness of upstream claims.']}
    except (ValueError, TypeError, KeyError, OverflowError) as error:
        return {'version': 1, 'scope': SCOPE, 'status': 'FAIL', 'reasons': [str(error)]}


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key: ' + key)
        result[key] = value
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence', type=Path)
    args = parser.parse_args(argv)
    try:
        result = verify_cycle(json.loads(args.evidence.read_text(), object_pairs_hook=_unique))
    except (ValueError, OSError, UnicodeError) as error:
        result = {'version': 1, 'scope': SCOPE, 'status': 'FAIL', 'reasons': [str(error)]}
    print(json.dumps(result, sort_keys=True))
    return 0 if result['status'].startswith('VERIFIED_') else 2 if result['status'] == 'PENDING' else 1


if __name__ == '__main__':
    raise SystemExit(main())
