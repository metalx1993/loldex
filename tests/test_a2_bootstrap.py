from pathlib import Path
from unittest.mock import patch
import pytest
from deployment.bootstrap import bootstrap, inventory
from deployment.package import build_package
from deployment.server import ReleaseStore, DeploymentError


def fixture(tmp_path):
    store=ReleaseStore(tmp_path/'public',tmp_path/'control')
    (store.public/'index.html').write_bytes(b'legacy')
    (store.public/'.htaccess').write_bytes(b'legacy rules')
    rid=store.install(build_package({'index.html':b'new'},'a'*40))
    store.activate(rid,store.status())
    return store


def test_bootstrap_removes_static_bypass_and_preserves_exact_legacy(tmp_path):
    store=fixture(tmp_path); before=inventory(store.public)
    report=bootstrap(store,before,tmp_path/'backup',b'router',b'new rules')
    assert report['legacy_files']==2
    assert not (store.public/'index.html').exists()
    assert (tmp_path/'backup/index.html').read_bytes()==b'legacy'
    assert (store.public/'.htaccess').read_bytes()==b'new rules'
    assert store.verify(store.status()['release_id'])


def test_changed_inventory_or_existing_backup_refused(tmp_path):
    store=fixture(tmp_path);before=inventory(store.public)
    (store.public/'index.html').write_bytes(b'changed')
    with pytest.raises(DeploymentError):bootstrap(store,before,tmp_path/'backup',b'router',b'rules')
    assert not (tmp_path/'backup').exists()
    (tmp_path/'backup').mkdir()
    with pytest.raises(FileExistsError):bootstrap(store,inventory(store.public),tmp_path/'backup',b'router',b'rules')
    assert (store.public/'index.html').read_bytes()==b'changed'


def test_mid_migration_failure_restores_old_root(tmp_path):
    store=fixture(tmp_path);before=inventory(store.public)
    import os
    real=os.rename
    def fail(src,dst):
        if Path(src).name=='new-.htaccess':raise OSError('injected')
        return real(src,dst)
    with patch('deployment.bootstrap.os.rename',side_effect=fail),pytest.raises(OSError):
        bootstrap(store,before,tmp_path/'backup',b'router',b'rules')
    assert inventory(store.public)==before
    assert not (store.public/'loldex-router.php').exists()


def test_inconsistent_active_binding_blocks_before_root_move(tmp_path):
    store=fixture(tmp_path);before=inventory(store.public)
    token=store.status();token['commit']='b'*40
    from deployment.server import canonical
    store.active.write_bytes(canonical(token))
    with pytest.raises(DeploymentError):bootstrap(store,before,tmp_path/'backup',b'router',b'rules')
    assert inventory(store.public)==before and not (tmp_path/'backup').exists()


@pytest.mark.parametrize('name',['inventory.json','new-loldex-router.php','new-.htaccess'])
def test_reserved_backup_names_block_before_root_move(tmp_path,name):
    store=fixture(tmp_path);(store.public/name).write_bytes(b'legacy collision')
    before=inventory(store.public)
    with pytest.raises(DeploymentError):bootstrap(store,before,tmp_path/'backup',b'router',b'rules')
    assert inventory(store.public)==before and not (tmp_path/'backup').exists()
