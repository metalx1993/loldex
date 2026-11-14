"""Independent check that the verified refresh carries API evidence shards intact."""
import hashlib
import json

from tests.test_d2_integration import _refresh_fixture


def test_refresh_copies_release_local_shards_and_their_manifest(tmp_path, monkeypatch):
    module, repo, prepared, expected, data = _refresh_fixture(tmp_path, monkeypatch)
    shard_name = 'evidence-records/' + hashlib.sha256(b'new').hexdigest() + '.json'
    raw = b'{"source":{"raw":{"original":"evidence"}}}\n'
    shard = prepared / 'site' / shard_name
    shard.parent.mkdir()
    shard.write_bytes(raw)
    payloads = {'data.json': (prepared / 'site/data.json').read_bytes(), shard_name: raw}
    manifest = {'version': 1, 'entries': 1, 'registry_checksum': 'sha256:' + 'a' * 64,
                'files': {name: 'sha256:' + hashlib.sha256(value).hexdigest()
                          for name, value in payloads.items()}}
    (prepared / 'site/build-manifest.json').write_text(json.dumps(manifest, sort_keys=True, separators=(',', ':')) + '\n')
    module.refresh({}, repo, prepared, expected)
    assert (repo / 'site' / shard_name).read_bytes() == raw
    assert json.loads((repo / 'site/build-manifest.json').read_bytes()) == manifest
