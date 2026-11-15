"""Shared generation and taxonomy gates stay effective under optimization."""
import hashlib
import json
import subprocess
import sys

from scripts.build_all import complete_artifacts, ROOT
from tests.test_build_all import corpus_entry
from tests.test_registry import registry


def test_complete_inventory_manifest_binds_all_generated_files():
    result = complete_artifacts([corpus_entry()], registry())
    manifest = json.loads(result['build-manifest.json'])
    assert manifest['entries'] == 1
    assert set(manifest['files']) == set(result) - {'build-manifest.json'}
    for name, digest in manifest['files'].items():
        assert digest == 'sha256:' + hashlib.sha256(result[name]).hexdigest()
    assert result['registry-license.txt'] == (ROOT / 'data/registry/LICENSE-MITRE.txt').read_bytes()
    assert json.loads(result['openapi-v1.json']) == json.loads((ROOT / 'api/openapi-v1.json').read_bytes())


def test_taxonomy_drift_fails_even_when_python_assertions_are_disabled():
    code = "from scripts import validate; validate.load_schema_taxonomy=lambda: (set(),set(),set()); validate.check_taxonomy()"
    result = subprocess.run([sys.executable, '-O', '-c', code], cwd=ROOT,
                            text=True, capture_output=True, timeout=20)
    assert result.returncode != 0
    assert 'taxonomy drift' in result.stderr
