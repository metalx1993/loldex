"""Local adversarial tests of credential-free host pull. No network or SSH."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import os
import subprocess

import pytest

from deployment.package import build_package
from deployment.pull import network_git, publish_latest, PUBLIC_REPOSITORY
from deployment.server import ReleaseStore, Conflict

COMMIT = 'a' * 40


def bare(path):
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(['git', 'init', '--bare', '-q', str(path)], check=True, capture_output=True)
    path.chmod(0o700)
    return path.resolve()


def mocked_publish(repo, store):
    package = build_package({'index.html': b'valid fixture'}, COMMIT)
    def network(_repo, *args):
        return b'' if args[0] == 'fetch' else COMMIT.encode() + b'\trefs/heads/main\n'
    with patch('deployment.pull.network_git', side_effect=network), patch('deployment.pull.resolve_commit', return_value=COMMIT), patch('deployment.pull.package_commit', return_value=package):
        return publish_latest(repo, store)


def test_public_url_cannot_be_redirected_by_local_git_instead_of(tmp_path):
    repo = bare(tmp_path / 'repo.git')
    subprocess.run(['git', '-C', str(repo), 'config', '--local',
                    'url.https://unrelated.invalid/.insteadOf', 'https://github.com/'],
                   check=True, capture_output=True)
    # --get-url expands configuration only: no connection is attempted.
    try:
        actual = network_git(repo, 'ls-remote', '--get-url', PUBLIC_REPOSITORY).decode().strip()
    except ValueError:
        return  # rejecting the unsafe cache before use is also correct
    assert actual == PUBLIC_REPOSITORY, 'local Git config bypassed the pinned repository URL'


def test_network_git_cannot_inherit_credential_askpass_program(tmp_path, monkeypatch):
    repo = bare(tmp_path / 'repo.git')
    monkeypatch.setenv('SSH_ASKPASS', '/untrusted/credential-collector')
    monkeypatch.setenv('GIT_ASKPASS', '/untrusted/credential-collector')
    with patch('deployment.pull.subprocess.run', return_value=SimpleNamespace(stdout=b'')) as execute:
        network_git(repo, 'ls-remote', PUBLIC_REPOSITORY, 'refs/heads/main')
    env = execute.call_args.kwargs['env']
    assert env.get('SSH_ASKPASS') in (None, '', '/bin/false', '/usr/bin/false')
    assert env.get('GIT_ASKPASS') in (None, '', '/bin/false', '/usr/bin/false')


def test_network_git_uses_trusted_executable_path(tmp_path, monkeypatch):
    repo = bare(tmp_path / 'repo.git')
    monkeypatch.setenv('PATH', '/untrusted/bin:/usr/bin:/bin')
    with patch('deployment.pull.subprocess.run', return_value=SimpleNamespace(stdout=b'')) as execute:
        network_git(repo, 'ls-remote', PUBLIC_REPOSITORY, 'refs/heads/main')
    env = execute.call_args.kwargs['env']
    executable = execute.call_args.args[0][0]
    assert executable.startswith('/') or env.get('PATH') in ('/usr/bin:/bin', '/bin:/usr/bin')


def test_nonbare_cache_is_rejected_before_network_or_store_mutation(tmp_path):
    repo = tmp_path / 'not-bare'
    repo.mkdir()
    store = ReleaseStore(tmp_path / 'public', tmp_path / 'control')
    with pytest.raises(ValueError):
        mocked_publish(repo, store)
    assert store.status()['generation'] == 0


@pytest.mark.parametrize('relationship', ['same-control', 'ancestor-public-and-control'])
def test_git_cache_cannot_overlap_publication_roots(tmp_path, relationship):
    if relationship == 'ancestor-public-and-control':
        repo = bare(tmp_path / 'host')
        store = ReleaseStore(repo / 'public', repo / 'control')
    else:
        store = ReleaseStore(tmp_path / 'public', tmp_path / 'control')
        repo = bare(store.control if relationship == 'same-control' else store.control / 'cache.git')
    with pytest.raises(ValueError):
        mocked_publish(repo, store)
    assert store.status()['generation'] == 0


def test_mismatched_remote_ref_name_is_not_accepted_as_main(tmp_path):
    repo = bare(tmp_path / 'repo.git')
    store = ReleaseStore(tmp_path / 'public', tmp_path / 'control')
    package = build_package({'index.html': b'valid fixture'}, COMMIT)
    replies = [b'', COMMIT.encode() + b'\trefs/heads/not-main\n']
    with patch('deployment.pull.network_git', side_effect=replies), patch('deployment.pull.resolve_commit', return_value=COMMIT), patch('deployment.pull.package_commit', return_value=package):
        with pytest.raises(Conflict):
            publish_latest(repo, store)
    assert store.status()['generation'] == 0


def test_private_bare_cache_inside_control_is_an_explicit_supported_layout(tmp_path):
    store = ReleaseStore(tmp_path / 'public', tmp_path / 'control')
    repo = bare(store.control / 'cache.git')
    report = mocked_publish(repo, store)
    assert report['commit'] == COMMIT
    assert store.status()['generation'] == 1
