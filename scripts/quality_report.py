"""Read-only Phase 10 validation of the complete generated data inventory.

Print JSON to stdout; never acquire, repair, write generated views or publish.
PASS applies only to the listed local checks, not to operational acceptance.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import hashlib
import io
import json
import os
import subprocess
from pathlib import Path

import yaml

from knowledge.graph import ROOT, read_entries
from knowledge.registry import load_registry, validate_registry, _parse_json
from knowledge.identities import load_identity_registry, validate_identity_registry, _native_yaml
from phase5.state import validate_envelope
from scripts.build_all import complete_artifacts
from scripts import validate


_LOADED_SCRIPT_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _real_directory(path):
    path = Path(path).absolute()
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise ValueError(f'directory must not traverse symlinks: {path}')
    if not path.is_dir():
        raise ValueError(f'required directory missing or not a directory: {path}')
    return path


def _real_file(path):
    path = Path(path).absolute()
    _real_directory(path.parent)
    if path.is_symlink() or not path.is_file():
        raise ValueError(f'input must be a regular non-symlink file: {path}')
    return path


def _input_files(state_path=None):
    corpus = _real_directory(ROOT / 'data/entries')
    _real_directory(ROOT / 'site')
    files = []
    for directory, subdirs, names in os.walk(corpus, followlinks=False):
        for name in subdirs:
            _real_directory(Path(directory) / name)
        for name in names:
            path = _real_file(Path(directory) / name)
            if path.suffix == '.yaml':
                files.append(path)
    if not files:
        raise ValueError('corpus must contain at least one regular YAML entry')
    files += [_real_file(ROOT / name) for name in
              ('data/registry/enterprise-attack.json', 'data/identity/registry.json',
               'api/openapi-v1.json', 'data/registry/LICENSE-MITRE.txt', 'schema/schema.yaml')]
    if state_path is not None:
        files.append(_real_file(state_path))
    return sorted(files)


def _fingerprint(files):
    # Labels separate same-content files; only the combined digest is reported.
    digest = hashlib.sha256()
    labelled = [(path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT)
                 else 'external-core-state', path) for path in files]
    for label, path in sorted(labelled):
        raw = path.read_bytes()
        digest.update(label.encode('utf-8'))
        digest.update(b'\0')
        digest.update(hashlib.sha256(raw).digest())
    return digest.hexdigest()


def baseline(entries, registry, identity_registry, site, state=None):
    """Reuse canonical corpus/build validators and compare without the writer."""
    site = _real_directory(site)
    if not isinstance(entries, list) or not entries or any(not isinstance(e, dict) for e in entries):
        raise ValueError('baseline requires a nonempty list of entry objects')
    if not isinstance(registry, dict):
        raise ValueError('baseline requires the validated technique registry')
    validate_registry(registry)
    if identity_registry is not None:
        validate_identity_registry(identity_registry)
    validate.check_taxonomy()
    diagnostics = io.StringIO()
    with redirect_stdout(diagnostics):
        errors = sum(validate.check_entry(Path(f'entry-{i}.yaml'), entry)
                     for i, entry in enumerate(entries))
    if errors:
        raise ValueError(diagnostics.getvalue().strip())
    expected = complete_artifacts(entries, registry, state, identity_registry)
    issues = []
    for name, raw in sorted(expected.items()):
        target = site / name
        if target.is_symlink() or any(p.is_symlink() for p in target.parents):
            issues.append({'file': name, 'reason': 'symlink'})
        elif not target.is_file():
            issues.append({'file': name, 'reason': 'missing_or_nonregular'})
        elif target.read_bytes() != raw:
            issues.append({'file': name, 'reason': 'content_mismatch'})
    shards = site / 'evidence-records'
    if shards.is_symlink():
        issues.append({'file': 'evidence-records', 'reason': 'symlink'})
    elif shards.exists():
        if not shards.is_dir():
            issues.append({'file': 'evidence-records', 'reason': 'not_a_directory'})
        else:
            for target in sorted(shards.rglob('*')):
                name = target.relative_to(site).as_posix()
                if name not in expected:
                    issues.append({'file': name, 'reason': 'unexpected_evidence_object'})
    return {'version': 1, 'scope': 'complete_generated_data_inventory',
            'status': 'FAIL' if issues else 'PASS', 'entries': len(entries),
            'checked_files': len(expected), 'issues': issues,
            'expected_sha256': {name: hashlib.sha256(raw).hexdigest() for name, raw in sorted(expected.items())},
            'limits': ['Local filesystem check; files are not locked and concurrent ABA changes cannot be excluded.',
                       'No upstream acquisition, CORE freshness inference or operational-cycle acceptance.',
                       'Handwritten API/runtime and UI assets are outside this generated-data comparison.']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, help='same validated CORE state used for the site build, if any')
    args = parser.parse_args(argv)
    try:
        files = _input_files(args.state)
        before = _fingerprint(files)
        # Reuse the existing strict native parser only as ambiguity preflight.
        # read_entries remains the canonical corpus reader.
        for path in files:
            if path.suffix == '.yaml':
                _native_yaml(path.read_text(encoding='utf-8'))
        _parse_json((ROOT / 'api/openapi-v1.json').read_text(encoding='utf-8'))
        state = validate_envelope(args.state.read_bytes()) if args.state else None
        result = baseline(read_entries(ROOT / 'data/entries'),
                          load_registry(ROOT / 'data/registry/enterprise-attack.json'),
                          load_identity_registry(ROOT / 'data/identity/registry.json'),
                          ROOT / 'site', state)
        after_files = _input_files(args.state)
        after = _fingerprint(after_files)
        result['input_snapshot'] = {'sha256': before, 'files': len(files), 'stable_at_recheck': files == after_files and before == after}
        if not result['input_snapshot']['stable_at_recheck']:
            result['issues'].append({'reason': 'inputs_changed_during_check'})
            result['status'] = 'FAIL'
    except (ValueError, OSError, TypeError, KeyError, AttributeError, IndexError, RecursionError, yaml.YAMLError) as error:
        result = {'version': 1, 'scope': 'complete_generated_data_inventory', 'status': 'FAIL',
                  'issues': [{'reason': 'input_or_validation_error', 'detail': str(error)}]}
    try:
        status = subprocess.check_output(['git', '-C', str(ROOT), 'status', '--porcelain', '--untracked-files=normal'], text=True)
        result['checkout'] = {
            'head': subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip(),
            'tracked_changes': any(not line.startswith('??') for line in status.splitlines()),
            'untracked_changes': any(line.startswith('??') for line in status.splitlines()),
            'report_script_sha256': _LOADED_SCRIPT_SHA256}
    except (OSError, subprocess.CalledProcessError):
        result['checkout'] = {'head': None}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
