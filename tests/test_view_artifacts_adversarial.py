"""Independent attacks on local generated-view ownership, not A2 publication."""
import hashlib
import json
from pathlib import Path

import pytest

from knowledge.artifacts import evidence_path, write_artifacts


def package(shards, marker=b'new'):
    files = {'catalog.json': marker, **shards}
    manifest = {'version': 1, 'entries': len(shards), 'registry_checksum': 'sha256:' + 'a' * 64,
                'files': {name: 'sha256:' + hashlib.sha256(raw).hexdigest() for name, raw in files.items()}}
    return {**files, 'build-manifest.json': (json.dumps(manifest, sort_keys=True, separators=(',', ':')) + '\n').encode()}


def test_unknown_dirty_shard_cannot_be_deleted_or_overwritten(tmp_path):
    out = tmp_path / 'site'
    unknown = out / evidence_path('user-work')
    unknown.parent.mkdir(parents=True)
    unknown.write_bytes(b'user work')
    for candidate in (package({}), package({unknown.relative_to(out).as_posix(): b'new bytes'})):
        with pytest.raises(ValueError):
            write_artifacts(out, candidate)
        assert unknown.read_bytes() == b'user work'
        assert not (out / 'catalog.json').exists()
        assert not (out / 'build-manifest.json').exists()


def test_modified_previously_owned_shard_aborts_before_any_write(tmp_path):
    out = tmp_path / 'site'
    name = evidence_path('old')
    old = package({name: b'original'}, marker=b'old catalog')
    write_artifacts(out, old)
    (out / name).write_bytes(b'changed by user')
    with pytest.raises(ValueError):
        write_artifacts(out, package({}))
    assert (out / name).read_bytes() == b'changed by user'
    assert (out / 'catalog.json').read_bytes() == old['catalog.json']
    assert (out / 'build-manifest.json').read_bytes() == old['build-manifest.json']


def test_only_exact_previous_inventory_shards_are_removed_before_completion(tmp_path, monkeypatch):
    out = tmp_path / 'site'
    stale, kept = evidence_path('stale'), evidence_path('kept')
    old = package({stale: b'retired', kept: b'kept'}, marker=b'old')
    write_artifacts(out, old)
    new = package({kept: b'kept'})
    original = Path.unlink
    removed = []

    def observe(path, *args, **kwargs):
        if path == out / stale:
            assert (out / 'build-manifest.json').read_bytes() == old['build-manifest.json']
            removed.append(path)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'unlink', observe)
    write_artifacts(out, new)
    assert removed == [out / stale]
    assert not (out / stale).exists()
    assert (out / kept).read_bytes() == b'kept'
    assert (out / 'build-manifest.json').read_bytes() == new['build-manifest.json']
    manifest = json.loads(new['build-manifest.json'])
    for name, digest in manifest['files'].items():
        assert 'sha256:' + hashlib.sha256((out / name).read_bytes()).hexdigest() == digest


@pytest.mark.parametrize('kind', ['root', 'ancestor', 'shard-directory', 'shard-file', 'catalog-file'])
def test_symlink_surfaces_never_escape_output(tmp_path, kind):
    outside = tmp_path / 'outside'
    outside.mkdir()
    protected = outside / 'protected'
    protected.write_bytes(b'protected')
    out = tmp_path / 'site'
    name = evidence_path('x')
    if kind == 'root':
        out.symlink_to(outside, target_is_directory=True)
    elif kind == 'ancestor':
        parent = tmp_path / 'linked'
        parent.symlink_to(outside, target_is_directory=True)
        out = parent / 'site'
    else:
        out.mkdir()
        if kind == 'shard-directory':
            (out / 'evidence-records').symlink_to(outside, target_is_directory=True)
        elif kind == 'shard-file':
            (out / 'evidence-records').mkdir()
            (out / name).symlink_to(protected)
        else:
            (out / 'catalog.json').symlink_to(protected)
    with pytest.raises(ValueError):
        write_artifacts(out, package({name: b'new'}))
    assert protected.read_bytes() == b'protected'
    assert not (outside / 'catalog.json').exists()


@pytest.mark.parametrize('kind', ['directory-shard', 'directory-target', 'file-parent'])
def test_nonregular_objects_fail_before_inventory_is_written(tmp_path, kind):
    out = tmp_path / 'site'
    out.mkdir()
    name = evidence_path('x')
    if kind == 'directory-shard':
        (out / name).mkdir(parents=True)
    elif kind == 'directory-target':
        (out / 'catalog.json').mkdir()
    else:
        (out / 'evidence-records').write_bytes(b'not a directory')
    with pytest.raises(ValueError):
        write_artifacts(out, package({name: b'new'}))
    assert not (out / 'build-manifest.json').exists()


def test_raw_identity_never_enters_filesystem_path():
    name = evidence_path('../../private/\x00É')
    assert name == 'evidence-records/' + hashlib.sha256('../../private/\x00É'.encode()).hexdigest() + '.json'
