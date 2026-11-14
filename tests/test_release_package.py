"""Release archives bind exact committed bytes and reject unsafe or ambiguous containers."""
import copy
import gzip
import hashlib
import io
import json
import subprocess
import tarfile

import pytest

from deployment.package import (build_package, read_package, parse_manifest, validate_payload,
                                validate_path, package_commit, canonical_bytes, DATA_FILES,
                                PRODUCTION_FILES, PRODUCTION_DATA_FILES, verify_data_manifest)

COMMIT = 'a' * 40


def tar_gzip(members, *, format=tarfile.USTAR_FORMAT):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w', format=format) as archive:
        for info, content in members:
            archive.addfile(info, io.BytesIO(content))
    return gzip.compress(buffer.getvalue(), mtime=0)


def member(name, content, **attrs):
    info = tarfile.TarInfo(name)
    info.mode = 0o644
    info.size = len(content)
    for key, value in attrs.items():
        setattr(info, key, value)
    return info, content


def envelope(files=None):
    files = files or {'index.html': b'<h1>LOLDEX</h1>'}
    manifest, _ = read_package(build_package(files, COMMIT))
    return manifest, files


def test_package_is_byte_deterministic_and_preserves_exact_file_contents():
    files = {'index.html': b'content', 'assets/image.bin': b'content\x00\xff', '.htaccess': b'RewriteEngine On\n', 'assets/caf\u00e9.css': b'nfc not applied: cafe\xcc\x81'}
    first = build_package(files, COMMIT)
    second = build_package(dict(reversed(list(files.items()))), COMMIT)
    assert first == second
    manifest, recovered = read_package(first)
    assert recovered == files
    assert manifest['commit'] == COMMIT
    assert manifest['files']['index.html'] == 'sha256:' + hashlib.sha256(files['index.html']).hexdigest()
    assert first[4:8] == b'\0\0\0\0'  # gzip timestamp, not build clock.


@pytest.mark.parametrize('path', ['../index.html', '/index.html', 'a/../../bad', 'a//b', './a',
                                   'a\\b', 'a\nb', 'cafe\u0301.html', '.git/config', '.GIT/config',
                                   'a/.env', '.env/secret', 'private.pem', '.ssh/id_rsa',
                                   'release.json', 'C:/index.html', 'a/../b', 'a/ b'])
def test_unsafe_release_paths_fail_before_packaging(path):
    with pytest.raises(ValueError):
        build_package({path: b'bad'}, COMMIT)


def test_manifest_requires_canonical_bytes_and_rejects_duplicate_json_keys():
    manifest, _ = envelope()
    raw = canonical_bytes(manifest)
    assert parse_manifest(raw) == manifest
    for value in (raw + b'\n', json.dumps(manifest, indent=2).encode(), raw.replace(b'"version":1', b'"version":1,"version":1')):
        with pytest.raises(ValueError):
            parse_manifest(value)


def test_rehashed_release_id_does_not_hide_file_tampering():
    manifest, files = envelope()
    with pytest.raises(ValueError, match='checksum'):
        validate_payload(manifest, {'index.html': b'changed'})
    manifest['commit'] = 'b' * 40
    with pytest.raises(ValueError, match='identity'):
        validate_payload(manifest, files)


@pytest.mark.parametrize('kind', ['traversal', 'symlink', 'hardlink', 'device', 'duplicate', 'extra_root', 'pax'])
def test_archive_member_attacks_are_rejected_without_extraction(kind):
    manifest, files = envelope()
    base = [member('release.json', canonical_bytes(manifest)), member('site/index.html', files['index.html'])]
    if kind == 'traversal':
        base.append(member('site/../evil', b'bad'))
    elif kind == 'symlink':
        base.append(member('site/link', b'', type=tarfile.SYMTYPE, linkname='/etc/passwd'))
    elif kind == 'hardlink':
        base.append(member('site/link', b'', type=tarfile.LNKTYPE, linkname='site/index.html'))
    elif kind == 'device':
        base.append(member('site/device', b'', type=tarfile.CHRTYPE, devmajor=1, devminor=1))
    elif kind == 'duplicate':
        base.append(member('site/index.html', files['index.html']))
    elif kind == 'extra_root':
        base.append(member('control.php', b'bad'))
    else:
        base.append(member('site/pax', b'bad', pax_headers={'path': '../evil'}))
    raw = tar_gzip(base, format=tarfile.PAX_FORMAT if kind == 'pax' else tarfile.USTAR_FORMAT)
    with pytest.raises(ValueError):
        read_package(raw)


def test_manifest_file_set_must_match_archive_exactly():
    manifest, _ = envelope()
    raw = tar_gzip([member('release.json', canonical_bytes(manifest)), member('site/other.html', b'x')])
    with pytest.raises(ValueError, match='files differ'):
        read_package(raw)


def test_trailing_tar_content_and_concatenated_gzip_streams_are_rejected():
    valid = build_package({'index.html': b'hi'}, COMMIT)
    with pytest.raises(ValueError):
        read_package(valid + gzip.compress(b'junk'))
    with pytest.raises(ValueError):
        read_package(gzip.compress(gzip.decompress(valid) + b'x' * 512))
    with pytest.raises(ValueError):
        read_package(valid[:-8])


def test_payload_file_cannot_also_be_a_directory():
    with pytest.raises(ValueError, match='parent directory'):
        build_package({'assets': b'file', 'assets/app.js': b'code'}, COMMIT)


def test_size_and_count_limits_are_enforced(monkeypatch):
    import deployment.package as package
    monkeypatch.setattr(package, 'MAX_FILE_BYTES', 3)
    with pytest.raises(ValueError):
        build_package({'index.html': b'four'}, COMMIT)
    monkeypatch.setattr(package, 'MAX_FILE_BYTES', 32 * 1024 * 1024)
    monkeypatch.setattr(package, 'MAX_MEMBERS', 2)
    with pytest.raises(ValueError):
        build_package({'index.html': b'x', 'app.js': b'y'}, COMMIT)
    monkeypatch.setattr(package, 'MAX_MEMBERS', 20_000)
    monkeypatch.setattr(package, 'MAX_PACKAGE_BYTES', 512)
    with pytest.raises(ValueError):
        build_package({'index.html': b'x'}, COMMIT)
    raw = gzip.compress(b'x' * 513)
    with pytest.raises(ValueError):
        read_package(raw)


def production_files():
    files = {name: b'fixture' for name in PRODUCTION_FILES if name != 'build-manifest.json'}
    build = {'version': 1, 'entries': 1, 'registry_checksum': 'sha256:' + '0' * 64,
             'files': {name: 'sha256:' + hashlib.sha256(files[name]).hexdigest() for name in sorted(PRODUCTION_DATA_FILES)}}
    files['build-manifest.json'] = canonical_bytes(build) + b'\n'
    return files


def test_build_manifest_must_cover_all_datasets_with_matching_checksums():
    files = production_files()
    verify_data_manifest(files, required=True)
    changed = dict(files)
    changed['catalog.json'] = b'changed'
    with pytest.raises(ValueError, match='checksum mismatch'):
        build_package(changed, COMMIT)
    build = json.loads(files['build-manifest.json'])
    del build['files']['graph.json']
    files['build-manifest.json'] = canonical_bytes(build)
    with pytest.raises(ValueError, match='all public datasets'):
        verify_data_manifest(files)


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args])


def test_package_commit_ignores_dirty_and_untracked_worktree_files(tmp_path):
    git(tmp_path, 'init', '-q')
    git(tmp_path, 'config', 'user.email', 'test@example.invalid')
    git(tmp_path, 'config', 'user.name', 'Test')
    for path, raw in production_files().items():
        target = tmp_path / 'site' / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    git(tmp_path, 'add', 'site')
    git(tmp_path, 'commit', '-qm', 'fixture')
    commit = git(tmp_path, 'rev-parse', 'HEAD').decode().strip()
    expected = package_commit(tmp_path, commit)
    (tmp_path / 'site/index.html').write_text('dirty content')
    (tmp_path / 'site/untracked.txt').write_text('do not package')
    actual = package_commit(tmp_path, commit)
    assert actual == expected
    manifest, files = read_package(actual)
    assert files['index.html'] == b'fixture'
    assert 'untracked.txt' not in files
    assert manifest['commit'] == commit


def test_committed_symlink_is_not_a_regular_release_blob(tmp_path):
    git(tmp_path, 'init', '-q')
    git(tmp_path, 'config', 'user.email', 'test@example.invalid')
    git(tmp_path, 'config', 'user.name', 'Test')
    (tmp_path / 'site').mkdir()
    (tmp_path / 'site/link').symlink_to('/etc/passwd')
    git(tmp_path, 'add', 'site')
    git(tmp_path, 'commit', '-qm', 'fixture')
    commit = git(tmp_path, 'rev-parse', 'HEAD').decode().strip()
    with pytest.raises(ValueError, match='regular site blobs'):
        package_commit(tmp_path, commit)


def test_git_replace_cannot_substitute_site_beneath_declared_commit(tmp_path):
    git(tmp_path, 'init', '-q')
    git(tmp_path, 'config', 'user.email', 'test@example.invalid')
    git(tmp_path, 'config', 'user.name', 'Test')
    for path, raw in production_files().items():
        target = tmp_path / 'site' / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    git(tmp_path, 'add', 'site')
    git(tmp_path, 'commit', '-qm', 'original')
    first = git(tmp_path, 'rev-parse', 'HEAD').decode().strip()
    expected = package_commit(tmp_path, first)
    (tmp_path / 'site/index.html').write_bytes(b'replacement content')
    git(tmp_path, 'add', 'site')
    git(tmp_path, 'commit', '-qm', 'replacement')
    second = git(tmp_path, 'rev-parse', 'HEAD').decode().strip()
    git(tmp_path, 'replace', first, second)
    actual = package_commit(tmp_path, first)
    manifest, files = read_package(actual)
    assert actual == expected
    assert manifest['commit'] == first
    assert files['index.html'] == b'fixture'


@pytest.mark.parametrize('omitted', ['identities.json', 'openapi-v1.json'])
def test_production_commit_rejects_versioned_dataset_omitted_from_build_inventory(tmp_path, omitted):
    files = production_files()
    inventory = json.loads(files['build-manifest.json'])
    del inventory['files'][omitted]
    files['build-manifest.json'] = canonical_bytes(inventory) + b'\n'
    git(tmp_path, 'init', '-q')
    git(tmp_path, 'config', 'user.email', 'fixture@example.invalid')
    git(tmp_path, 'config', 'user.name', 'Fixture')
    for name, raw in files.items():
        target = tmp_path / 'site' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    git(tmp_path, 'add', 'site')
    git(tmp_path, 'commit', '-qm', 'fixture missing inventory binding')
    commit = git(tmp_path, 'rev-parse', 'HEAD').decode().strip()
    with pytest.raises(ValueError, match='production build inventory'):
        package_commit(tmp_path, commit)
