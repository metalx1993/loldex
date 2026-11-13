from unittest.mock import patch
import pytest
from deployment.package import build_package
from deployment.server import ReleaseStore, Conflict
from deployment.pull import publish_latest


def test_main_movement_aborts_before_install_or_activation(tmp_path):
    repo=tmp_path/'bare';repo.mkdir();(repo/'config').write_text('[core]\nrepositoryformatversion = 0\nfilemode = true\nbare = true\n');store=ReleaseStore(tmp_path/'public',tmp_path/'control')
    with patch('deployment.pull.network_git',side_effect=[b'',b'b'*40+b'\trefs/heads/main\n']),patch('deployment.pull.resolve_commit',return_value='a'*40),patch('deployment.pull.package_commit',return_value=build_package({'index.html':b'a'},'a'*40)),pytest.raises(Conflict):
        publish_latest(repo,store)
    assert store.status()['generation']==0 and not list(store.releases.iterdir())


def test_concurrent_activation_during_fetch_is_not_silently_retried(tmp_path):
    repo=tmp_path/'bare';repo.mkdir();(repo/'config').write_text('[core]\nrepositoryformatversion = 0\nfilemode = true\nbare = true\n');store=ReleaseStore(tmp_path/'public',tmp_path/'control')
    other=store.install(build_package({'index.html':b'b'},'b'*40))
    def network(_repo,*args):
        if args[0]=='fetch':
            store.activate(other,store.status());return b''
        return b'a'*40+b'\trefs/heads/main\n'
    with patch('deployment.pull.network_git',side_effect=network),patch('deployment.pull.resolve_commit',return_value='a'*40),patch('deployment.pull.package_commit',return_value=build_package({'index.html':b'a'},'a'*40)),pytest.raises(Conflict):
        publish_latest(repo,store)
    assert store.status()['release_id']==other


def test_valid_pull_is_idempotent_and_retains_prior_release(tmp_path):
    repo=tmp_path/'bare';repo.mkdir();(repo/'config').write_text('[core]\nrepositoryformatversion = 0\nfilemode = true\nbare = true\n');store=ReleaseStore(tmp_path/'public',tmp_path/'control')
    first=store.install(build_package({'index.html':b'b'},'b'*40));store.activate(first,store.status())
    def network(_repo,*args):return b'' if args[0]=='fetch' else b'a'*40+b'\trefs/heads/main\n'
    with patch('deployment.pull.network_git',side_effect=network),patch('deployment.pull.resolve_commit',return_value='a'*40),patch('deployment.pull.package_commit',return_value=build_package({'index.html':b'a'},'a'*40)):
        report=publish_latest(repo,store);again=publish_latest(repo,store)
    assert report['active']==again['active'] and report['active']['previous_release_id']==first
    assert store.verify(first)
