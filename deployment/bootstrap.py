"""One-time legacy-root migration. Explicit reviewed inventory; no scheduling.

SiteGround may serve existing static files without Apache rewrite processing.
Move the reviewed root files to a private backup before router authority can
cover them. This initial migration is a controlled maintenance operation;
subsequent release changes use only ReleaseStore.activate.
"""
from pathlib import Path
import hashlib
import json
import os
import stat

from deployment.server import DeploymentError, _fsync_dir


def inventory(root):
    root = Path(root)
    result = {}
    for path in sorted(root.iterdir()):
        if path.name == 'releases' or path.name.startswith('a2-check-') or path.name == '.well-known':
            if path.is_symlink() or not path.is_dir():
                raise DeploymentError('unexpected reserved root path')
            continue
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise DeploymentError('unexpected root object; review inventory')
        result[path.name] = 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def bootstrap(store, expected_inventory, backup, router, rules):
    with store._lock():
        return _bootstrap_locked(store, expected_inventory, backup, router, rules)


def _bootstrap_locked(store, expected_inventory, backup, router, rules):
    """Move exact reviewed legacy files aside, retaining a byte-verified backup.

    Requires an already activated and verified release (not yet root-routed).
    Never overwrites a backup. Failure restores the initial root files. Does not
    silently refresh a changed inventory or select a release.
    """
    backup = Path(backup)
    if backup != backup.resolve() or store.public == backup or store.public in backup.parents:
        raise DeploymentError('backup must be canonical and outside public root')
    token = store.status()
    if token['release_id'] is None:
        raise DeploymentError('verified active release required before bootstrap')
    manifest = store.verify(token['release_id'])
    if manifest['commit'] != token['commit']:
        raise DeploymentError('active commit binding differs')
    if set(expected_inventory) & {'inventory.json', 'new-loldex-router.php', 'new-.htaccess'}:
        raise DeploymentError('legacy names collide with backup control files')
    if inventory(store.public) != expected_inventory or not expected_inventory:
        raise DeploymentError('legacy root changed; re-review inventory')
    if 'loldex-router.php' in expected_inventory:
        raise DeploymentError('bootstrap already present')
    backup.mkdir(mode=0o700, parents=False, exist_ok=False)
    staged = {}
    moved = []
    try:
        for name, raw in (('loldex-router.php', router), ('.htaccess', rules)):
            path = backup / ('new-' + name)
            with path.open('xb') as stream:
                stream.write(raw); stream.flush(); os.fsync(stream.fileno())
            path.chmod(0o644)
            staged[name] = path
        (backup / 'inventory.json').write_text(json.dumps(expected_inventory, sort_keys=True) + '\n')
        # Root routing is not yet atomic on this first legacy migration.
        # Move .htaccess last, then install router before the new rules.
        for name in sorted(expected_inventory, key=lambda n: n == '.htaccess'):
            os.rename(store.public / name, backup / name)
            moved.append(name)
        for name in ('loldex-router.php', '.htaccess'):
            os.rename(staged[name], store.public / name)
        _fsync_dir(store.public); _fsync_dir(backup)
        for name, digest in expected_inventory.items():
            if 'sha256:' + hashlib.sha256((backup / name).read_bytes()).hexdigest() != digest:
                raise DeploymentError('backup hash mismatch')
    except Exception:
        for name in ('loldex-router.php', '.htaccess'):
            path = store.public / name
            if path.exists() and name not in expected_inventory:
                path.unlink()
            elif path.exists() and name in moved:
                path.unlink()
        for name in reversed(moved):
            os.rename(backup / name, store.public / name)
        _fsync_dir(store.public)
        raise
    return {'backup': str(backup), 'legacy_files': len(moved), 'active': token}
