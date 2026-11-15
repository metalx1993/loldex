"""Offline closure/integrity policy checks for the CPython 3.12 Linux CI lock.

The metadata comments are the reviewed official-PyPI snapshot, not a claim that
an offline test can authenticate PyPI or verify downloaded artifacts. pip's
--require-hashes step verifies the artifact bytes when CI installs them.
"""
import copy
import json
from pathlib import Path
import re

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name
import pytest

ROOT = Path(__file__).resolve().parent.parent


def lock_snapshot():
    source = (ROOT / 'requirements-ci.lock').read_text()
    assert '--only-binary=:all:' in source.splitlines()
    snapshots = {}
    for block in source.split('\n\n'):
        if '# Metadata: ' not in block:
            continue
        lines = block.splitlines()
        metadata = json.loads(next(line[len('# Metadata: '):]
                                   for line in lines if line.startswith('# Metadata: ')))
        expected_source = ('# Source: https://pypi.org/pypi/' + metadata['name'] +
                           '/' + metadata['version'] + '/json')
        assert expected_source in lines
        pin = next(line for line in lines if line and not line.startswith(('#', ' ')))
        requirement = Requirement(pin.removesuffix(' \\'))
        assert str(requirement.specifier) == '==' + metadata['version']
        assert requirement.name == metadata['name']
        assert not requirement.extras and not requirement.marker and not requirement.url
        hashes = [line.strip().removesuffix(' \\') for line in lines
                  if line.lstrip().startswith('--hash=')]
        wheels = [line for line in lines if line.startswith('# Wheel: ')]
        assert hashes and len(hashes) == len(wheels) == len(set(hashes))
        assert all(re.fullmatch(r'--hash=sha256:[0-9a-f]{64}', value) for value in hashes)
        assert all(line.endswith('.whl') for line in wheels)
        name = canonicalize_name(requirement.name)
        assert name not in snapshots
        snapshots[name] = metadata
    assert set(snapshots) == {'pyyaml', 'pytest', 'iniconfig', 'packaging', 'pluggy', 'pygments'}
    # Reject extra floating requirements or alternative-index directives outside
    # the reviewed blocks, including requirements hidden between comments.
    actual_pins = [line.split('==')[0] for line in source.splitlines()
                   if line and not line.startswith(('#', ' ', '--only-binary='))]
    assert sorted(canonicalize_name(name) for name in actual_pins) == sorted(snapshots)
    return snapshots


def assert_closure(snapshot, *, full_version='3.12.0', machine='x86_64'):
    environment = default_environment()
    environment.update(python_version='3.12', python_full_version=full_version,
                       implementation_name='cpython', implementation_version=full_version,
                       platform_python_implementation='CPython', sys_platform='linux',
                       os_name='posix', platform_system='Linux', platform_machine=machine,
                       extra='')
    for metadata in snapshot.values():
        assert full_version in SpecifierSet(metadata['requires_python'])
        for raw in metadata['requires_dist']:
            dependency = Requirement(raw)
            if dependency.marker and not dependency.marker.evaluate(environment):
                continue
            name = canonicalize_name(dependency.name)
            assert name in snapshot, 'missing CI dependency: ' + name
            assert snapshot[name]['version'] in dependency.specifier, raw


@pytest.mark.parametrize('machine,full_version', [('x86_64', '3.12.0'), ('aarch64', '3.12.9')])
def test_ci_lock_is_exact_hashed_and_dependency_complete(machine, full_version):
    snapshot = lock_snapshot()
    assert_closure(snapshot, machine=machine, full_version=full_version)
    for line in (ROOT / 'requirements.txt').read_text().splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        dependency = Requirement(line)
        name = canonicalize_name(dependency.name)
        assert name in snapshot
        assert snapshot[name]['version'] in dependency.specifier


@pytest.mark.parametrize('mutation', ['missing', 'incompatible'])
def test_closure_guard_detects_missing_or_incompatible_transitive(mutation):
    snapshot = copy.deepcopy(lock_snapshot())
    if mutation == 'missing':
        snapshot.pop('iniconfig')
    else:
        snapshot['pluggy']['version'] = '1.4.0'
    with pytest.raises(AssertionError):
        assert_closure(snapshot)
