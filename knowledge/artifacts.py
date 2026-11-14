"""Local generated-view writer with bounded, inventoried evidence shard ownership.

This is not the separate A2 host publication protocol. All semantic validation
must finish before calling this writer; the build manifest is replaced last.
"""
from pathlib import Path, PurePosixPath
import hashlib
import json
import os
import re
import shutil
import tempfile

SHARD = re.compile(r'evidence-records/[0-9a-f]{64}\.json\Z')


def evidence_path(identity):
    return 'evidence-records/' + hashlib.sha256(identity.encode('utf-8')).hexdigest() + '.json'


def write_artifacts(destination, payloads):
    out = Path(destination).absolute()
    for parent in (out, *out.parents):
        if parent.is_symlink():
            raise ValueError('generated output cannot traverse symlinks')
    if 'build-manifest.json' not in payloads:
        raise ValueError('generated output requires its completion manifest')
    for name, raw in payloads.items():
        p = PurePosixPath(name)
        if p.is_absolute() or any(part in ('', '.', '..') for part in name.split('/')) or '\\' in name:
            raise ValueError('unsafe generated artifact path')
        if not isinstance(raw, bytes):
            raise ValueError('generated artifacts must be bytes')
        for parent in (out/p).parents:
            if parent == out.parent:
                break
            if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
                raise ValueError('generated artifact parent is not a real directory')
        target = out / p
        if target.is_symlink() or (target.exists() and not target.is_file()):
            raise ValueError('generated artifact target is not a regular file')
    old_files = {}
    old_manifest = out/'build-manifest.json'
    if old_manifest.exists():
        old_files = json.loads(old_manifest.read_bytes()).get('files', {})
        if not isinstance(old_files, dict):
            raise ValueError('existing generated inventory is invalid')
    stale = []
    shards = out/'evidence-records'
    if shards.exists():
        if shards.is_symlink() or not shards.is_dir():
            raise ValueError('evidence shard root must be a real directory')
        for path in shards.rglob('*'):
            name = path.relative_to(out).as_posix()
            if path.is_symlink() or not path.is_file() or not SHARD.fullmatch(name):
                raise ValueError('unexpected object in generated evidence namespace')
            raw = path.read_bytes()
            digest = 'sha256:' + hashlib.sha256(raw).hexdigest()
            if name in old_files:
                if old_files[name] != digest:
                    raise ValueError('existing evidence shard was modified outside its inventory')
                if name not in payloads:
                    stale.append(path)
            elif payloads.get(name) != raw:
                raise ValueError('unowned evidence shard cannot be overwritten or deleted')
    out.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='loldex-views-', dir=out.parent))
    try:
        for name, raw in payloads.items():
            path = stage/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        out.mkdir(exist_ok=True)
        for name in sorted(set(payloads) - {'build-manifest.json'}):
            target = out/name
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(stage/name, target)
        for path in stale:
            path.unlink()
        os.replace(stage/'build-manifest.json', out/'build-manifest.json')
    finally:
        shutil.rmtree(stage)
