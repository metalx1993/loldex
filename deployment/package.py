"""Deterministic, integrity-checked releases built from committed Git objects."""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import re
import subprocess
import tarfile
import unicodedata
import zlib
from pathlib import Path

MAX_PACKAGE_BYTES = 128 * 1024 * 1024
MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_MEMBERS = 20_000
_SHA = re.compile(r'sha256:[0-9a-f]{64}\Z')
_COMMIT = re.compile(r'[0-9a-f]{40}\Z')
_RELEASE = re.compile(r'r-[0-9a-f]{64}\Z')
DATA_FILES = {'data.json', 'catalog.json', 'evidence.json', 'graph.json',
              'techniques.json', 'registry-license.txt'}
PRODUCTION_DATA_FILES = DATA_FILES | {'identities.json', 'openapi-v1.json'}
PRODUCTION_FILES = DATA_FILES | {
    'build-manifest.json', 'index.html', 'search.html', 'entry.html', 'technique.html',
    'techniques.html', 'experience-core.js', 'experience.js', 'experience.css',
    'api-v1.php', 'api-v1-core.php', 'request-guard.php', 'search-engine.php', 'search-engine.js',
    'api.php', 'contact.php', 'contact.html', 'contact.css', 'contact.js', '.htaccess',
    'identities.json', 'identity.html', 'identities.html', 'api.html', 'openapi-v1.json',
}
_FORBIDDEN_PARTS = {'.git', '.hg', '.svn', '.ssh', '.aws', '.codex', '__pycache__'}
_PRIVATE_NAMES = {'.htpasswd', '.ds_store', 'id_rsa', 'id_dsa', 'id_ecdsa', 'id_ed25519'}


def canonical_bytes(value):
    """Release JSON does not transform file-content bytes or normalize metadata."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'),
                      allow_nan=False).encode('utf-8')


def _sha(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def validate_path(path):
    if not isinstance(path, str) or not path or path != unicodedata.normalize('NFC', path):
        raise ValueError('release path must be a non-empty NFC string')
    if path.startswith('/') or '\\' in path or any(ord(c) < 32 or ord(c) == 127 or 0xD800 <= ord(c) <= 0xDFFF for c in path):
        raise ValueError('unsafe release path')
    parts = path.split('/')
    if any(part in {'', '.', '..'} or part != part.strip() for part in parts):
        raise ValueError('release path must be normalized relative POSIX')
    if ':' in parts[0]:
        raise ValueError('drive or scheme prefix forbidden in release path')
    lower_parts = [part.casefold() for part in parts]
    if any(part in _FORBIDDEN_PARTS or part == '.env' or part.startswith('.env.') for part in lower_parts):
        raise ValueError('repository or credential directory forbidden in release')
    base = lower_parts[-1]
    if base in _PRIVATE_NAMES or base == '.env' or base.startswith('.env.') or base.endswith(('.pem', '.key', '.p12', '.pfx')):
        raise ValueError('credential or private-key filename forbidden in release')
    if path == 'release.json':
        raise ValueError('release.json is a reserved root control filename')
    if len(path.encode('utf-8')) > 255:
        raise ValueError('release path exceeds supported USTAR length')
    return path


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON object key')
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError('non-finite JSON value forbidden')


def _parse_json(raw):
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs, parse_constant=_invalid_constant)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('release JSON must be strict UTF-8 JSON') from exc


def _validate_file_map(files):
    if not isinstance(files, dict) or not files or len(files) + 1 > MAX_MEMBERS:
        raise ValueError('release must contain a bounded non-empty file mapping')
    total = 0
    for path, raw in files.items():
        validate_path(path)
        if not isinstance(raw, bytes) or len(raw) > MAX_FILE_BYTES:
            raise ValueError('release file must be bytes within the per-file limit')
        total += len(raw)
        if total > MAX_PACKAGE_BYTES:
            raise ValueError('release exceeds total payload limit')
        segments = path.split('/')
        if any('/'.join(segments[:index]) in files for index in range(1, len(segments))):
            raise ValueError('release file conflicts with a parent directory')


def _validate_manifest(manifest):
    if not isinstance(manifest, dict) or set(manifest) != {'version', 'commit', 'files', 'release_id'}:
        raise ValueError('invalid release manifest shape')
    if type(manifest['version']) is not int or manifest['version'] != 1:
        raise ValueError('unsupported release manifest version')
    if not isinstance(manifest['commit'], str) or not _COMMIT.fullmatch(manifest['commit']):
        raise ValueError('release commit must be a full lowercase SHA-1')
    files = manifest['files']
    if not isinstance(files, dict) or not files or len(files) + 1 > MAX_MEMBERS:
        raise ValueError('invalid manifest file mapping')
    for path, digest in files.items():
        validate_path(path)
        if not isinstance(digest, str) or not _SHA.fullmatch(digest):
            raise ValueError('invalid manifest file digest')
    if not isinstance(manifest['release_id'], str) or not _RELEASE.fullmatch(manifest['release_id']):
        raise ValueError('invalid release identity')
    payload = {key: manifest[key] for key in ('version', 'commit', 'files')}
    expected = 'r-' + hashlib.sha256(canonical_bytes(payload)).hexdigest()
    if manifest['release_id'] != expected:
        raise ValueError('release identity does not match canonical manifest')


def parse_manifest(raw):
    if not isinstance(raw, bytes) or len(raw) > MAX_FILE_BYTES:
        raise ValueError('invalid release manifest bytes')
    manifest = _parse_json(raw)
    _validate_manifest(manifest)
    if canonical_bytes(manifest) != raw:
        raise ValueError('release manifest must use exact canonical JSON without a newline')
    return manifest


def verify_data_manifest(files, *, required=False):
    if 'build-manifest.json' not in files:
        if required:
            raise ValueError('production release requires build-manifest.json')
        return
    manifest = _parse_json(files['build-manifest.json'])
    if not isinstance(manifest, dict) or set(manifest) != {'version', 'files', 'entries', 'registry_checksum'}:
        raise ValueError('invalid data build manifest shape')
    if type(manifest['version']) is not int or manifest['version'] != 1 or type(manifest['entries']) is not int or manifest['entries'] < 0:
        raise ValueError('invalid data build manifest version/count')
    if not isinstance(manifest['registry_checksum'], str) or not _SHA.fullmatch(manifest['registry_checksum']):
        raise ValueError('invalid data registry checksum')
    declared = manifest['files']
    if not isinstance(declared, dict) or not DATA_FILES <= declared.keys() or 'build-manifest.json' in declared:
        raise ValueError('data build manifest must cover all public datasets')
    if any(path.startswith('evidence-records/') and path not in declared for path in files):
        raise ValueError('evidence shard missing from build inventory')
    for path, digest in declared.items():
        validate_path(path)
        if path not in files or not isinstance(digest, str) or not _SHA.fullmatch(digest) or _sha(files[path]) != digest:
            raise ValueError(f'data build manifest checksum mismatch: {path}')


def validate_payload(manifest, files):
    _validate_manifest(manifest)
    _validate_file_map(files)
    if set(manifest['files']) != set(files):
        raise ValueError('release manifest and actual files differ')
    for path, raw in files.items():
        if manifest['files'][path] != _sha(raw):
            raise ValueError(f'release file checksum mismatch: {path}')
    verify_data_manifest(files)
    from .url_closure import validate_url_closure
    validate_url_closure(files)


def build_package(files, commit):
    _validate_file_map(files)
    payload = {'version': 1, 'commit': commit,
               'files': {path: _sha(files[path]) for path in sorted(files)}}
    manifest = {**payload, 'release_id': 'r-' + hashlib.sha256(canonical_bytes(payload)).hexdigest()}
    validate_payload(manifest, files)
    archive = io.BytesIO()
    try:
        with tarfile.open(fileobj=archive, mode='w', format=tarfile.USTAR_FORMAT,
                          encoding='utf-8', errors='strict') as handle:
            members = [('release.json', canonical_bytes(manifest))]
            members += [('site/' + path, files[path]) for path in sorted(files)]
            for name, raw in members:
                info = tarfile.TarInfo(name)
                info.type = tarfile.REGTYPE
                info.size = len(raw)
                info.mode = 0o644
                info.uid = info.gid = info.mtime = 0
                info.uname = info.gname = ''
                handle.addfile(info, io.BytesIO(raw))
    except (ValueError, UnicodeError) as exc:
        raise ValueError('release path cannot be represented without TAR extensions') from exc
    tar_bytes = archive.getvalue()
    if len(tar_bytes) > MAX_PACKAGE_BYTES:
        raise ValueError('uncompressed release archive exceeds package limit')
    compressed = io.BytesIO()
    with gzip.GzipFile(fileobj=compressed, mode='wb', filename='', mtime=0, compresslevel=9) as handle:
        handle.write(tar_bytes)
    result = compressed.getvalue()
    if len(result) > MAX_PACKAGE_BYTES:
        raise ValueError('compressed release archive exceeds package limit')
    return result


def _tar_string(field):
    raw, separator, padding = field.partition(b'\0')
    if separator and any(padding):
        raise ValueError('noncanonical TAR string padding')
    try:
        return raw.decode('utf-8')
    except UnicodeError as exc:
        raise ValueError('TAR paths must be UTF-8') from exc


def read_package(raw):
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_PACKAGE_BYTES:
        raise ValueError('invalid compressed release size')
    try:
        inflater = zlib.decompressobj(16 + zlib.MAX_WBITS)
        content = inflater.decompress(raw, MAX_PACKAGE_BYTES + 1)
        if len(content) > MAX_PACKAGE_BYTES or not inflater.eof or inflater.unused_data or inflater.unconsumed_tail:
            raise ValueError('oversized, truncated or concatenated gzip release')
    except zlib.error as exc:
        raise ValueError('invalid gzip release') from exc
    if len(content) % 512:
        raise ValueError('TAR release is not block aligned')
    files, manifest_bytes, offset, member_count = {}, None, 0, 0
    while offset < len(content):
        header = content[offset:offset + 512]
        if not any(header):
            if len(content) - offset < 1024 or any(content[offset:]):
                raise ValueError('invalid TAR end markers or trailing content')
            break
        member_count += 1
        if member_count > MAX_MEMBERS:
            raise ValueError('too many TAR release members')
        if header[257:265] != b'ustar\x0000':
            raise ValueError('only plain USTAR releases are accepted; extensions forbidden')
        try:
            info = tarfile.TarInfo.frombuf(header, encoding='utf-8', errors='strict')
        except (tarfile.HeaderError, UnicodeError, ValueError) as exc:
            raise ValueError('invalid TAR member header') from exc
        name = _tar_string(header[:100])
        prefix = _tar_string(header[345:500])
        if prefix:
            name = prefix + '/' + name
        if info.name != name or info.type not in {tarfile.REGTYPE, tarfile.AREGTYPE} or info.linkname:
            raise ValueError('only regular release files are accepted')
        if info.mode != 0o644 or info.uid != 0 or info.gid != 0 or info.mtime != 0 or info.uname or info.gname or info.devmajor or info.devminor:
            raise ValueError('noncanonical or privileged TAR metadata')
        if info.size < 0 or info.size > MAX_FILE_BYTES:
            raise ValueError('release member exceeds per-file size limit')
        start, end = offset + 512, offset + 512 + info.size
        padded_end = ((end + 511) // 512) * 512
        if padded_end > len(content) or any(content[end:padded_end]):
            raise ValueError('truncated member or nonzero TAR member padding')
        value = content[start:end]
        if name == 'release.json':
            if manifest_bytes is not None:
                raise ValueError('duplicate release manifest')
            manifest_bytes = value
        elif name.startswith('site/'):
            path = validate_path(name[5:])
            if path in files:
                raise ValueError('duplicate release file')
            files[path] = value
        else:
            raise ValueError('unexpected TAR release root member')
        offset = padded_end
    else:
        raise ValueError('TAR release has no end markers')
    if manifest_bytes is None:
        raise ValueError('release manifest missing')
    manifest = parse_manifest(manifest_bytes)
    validate_payload(manifest, files)
    return manifest, files


def _git(repo, *args):
    # Do not inherit replace refs, external object stores, lazy network fetches,
    # user configuration or credentials from the invoking shell.
    try:
        result = subprocess.run(['git', '--no-replace-objects', '-C', str(repo), *args],
                                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=30, env={'PATH': '/usr/bin:/bin',
                                                'GIT_CONFIG_NOSYSTEM': '1',
                                                'GIT_CONFIG_GLOBAL': '/dev/null',
                                                'GIT_NO_LAZY_FETCH': '1',
                                                'GIT_ALLOW_PROTOCOL': '',
                                                'GIT_TERMINAL_PROMPT': '0'})
    except (subprocess.SubprocessError, OSError) as exc:
        raise ValueError('cannot read committed release Git objects') from exc
    if result.returncode:
        raise ValueError('cannot read committed release Git objects: ' + result.stderr.decode('utf-8', errors='replace').strip())
    return result.stdout


def resolve_commit(repo, revision='HEAD'):
    if not isinstance(revision, str) or not revision or revision.startswith('-'):
        raise ValueError('invalid requested release revision')
    resolved = _git(repo, 'rev-parse', '--verify', '--end-of-options', revision + '^{commit}').decode('ascii').strip()
    if not _COMMIT.fullmatch(resolved):
        raise ValueError('release requires a full SHA-1 commit identity')
    return resolved


def package_commit(repo, commit):
    """Package verified commit/tree/blob objects; neither worktree nor replace refs apply."""
    if not isinstance(commit, str) or not _COMMIT.fullmatch(commit):
        raise ValueError('package_commit requires a full lowercase commit identity')
    object_bytes, visited = 0, 0

    def obj(kind, oid):
        nonlocal object_bytes
        try:
            size = int(_git(repo, 'cat-file', '-s', oid).strip())
        except ValueError as exc:
            raise ValueError('invalid committed Git object size') from exc
        if size < 0 or size > MAX_FILE_BYTES:
            raise ValueError('committed Git object exceeds per-object size limit')
        object_bytes += size
        if object_bytes > MAX_PACKAGE_BYTES:
            raise ValueError('committed Git object reads exceed release size budget')
        value = _git(repo, 'cat-file', kind, oid)
        actual = hashlib.sha1(kind.encode('ascii') + b' ' + str(len(value)).encode('ascii') + b'\0' + value).hexdigest()
        if len(value) != size or actual != oid:
            raise ValueError('committed Git object content does not match its identity')
        return value

    def tree_records(oid):
        nonlocal visited
        raw = obj('tree', oid)
        position, names = 0, set()
        while position < len(raw):
            try:
                space = raw.index(b' ', position)
                end = raw.index(b'\0', space)
                mode = raw[position:space].decode('ascii')
                name = raw[space + 1:end].decode('utf-8', errors='strict')
                child = raw[end + 1:end + 21].hex()
                if len(child) != 40 or name in {'', '.', '..'} or '/' in name or name in names:
                    raise ValueError('invalid tree record')
            except (ValueError, UnicodeError) as exc:
                raise ValueError('malformed or ambiguous committed Git tree') from exc
            names.add(name)
            position = end + 21
            visited += 1
            if visited > MAX_MEMBERS * 4:
                raise ValueError('committed site tree exceeds traversal limit')
            yield mode, name, child

    raw_commit = obj('commit', commit)
    match = re.match(rb'tree ([0-9a-f]{40})\n', raw_commit)
    if match is None:
        raise ValueError('committed release has no root tree')
    root_tree = match[1].decode('ascii')
    site = None
    for mode, name, oid in tree_records(root_tree):
        if name == 'site':
            if mode != '40000':
                raise ValueError('committed site must be a regular Git tree')
            site = oid
    if site is None:
        raise ValueError('committed release has no site tree')
    files = {}

    def walk(tree, prefix='', depth=0):
        if depth > 64:
            raise ValueError('committed site tree nesting exceeds release limit')
        for mode, name, oid in tree_records(tree):
            relative = validate_path(prefix + name)
            if mode == '40000':
                walk(oid, relative + '/', depth + 1)
            elif mode in {'100644', '100755'}:
                if len(files) + 2 > MAX_MEMBERS:
                    raise ValueError('too many committed site files')
                if relative in files:
                    raise ValueError('duplicate committed site path')
                files[relative] = obj('blob', oid)
            else:
                raise ValueError('committed release must contain only regular site blobs')

    walk(site)
    _validate_file_map(files)
    if not PRODUCTION_FILES <= files.keys():
        raise ValueError('committed site is missing required UI or generated dataset files')
    verify_data_manifest(files, required=True)
    if not PRODUCTION_DATA_FILES <= _parse_json(files['build-manifest.json'])['files'].keys():
        raise ValueError('production build inventory must cover versioned API and identity datasets')
    return build_package(files, commit)
