"""Pinned ATT&CK registry metadata must never be promoted to entry evidence."""
import copy
import hashlib
import json

import pytest

from knowledge.graph import build_graph
from knowledge.registry import import_stix, validate_registry, load_registry
from knowledge.techniques import build_techniques, validate_techniques
from tests.test_graph import entry

SOURCE = 'https://raw.githubusercontent.com/mitre-attack/attack-stix-data/' + 'a' * 40 + '/enterprise-attack/enterprise-attack-20.1.json'


def stix_object(tid='T1105', *, suffix='1'):
    return {'type': 'attack-pattern', 'id': 'attack-pattern--00000000-0000-4000-8000-' + suffix.zfill(12),
            'name': 'Official name <script>', 'description': 'Official description\nwith source markup [link](https://example.test).',
            'modified': '2026-11-05T00:00:00.000Z', 'x_mitre_version': '1.2',
            'x_mitre_domains': ['enterprise-attack'],
            'external_references': [{'source_name': 'mitre-attack', 'external_id': tid,
                                     'url': 'https://attack.mitre.org/techniques/' + tid.replace('.', '/')}],
            'kill_chain_phases': [{'kill_chain_name': 'mitre-attack', 'phase_name': 'command-and-control'}]}


def source_bytes(objects=None):
    collection = {'type': 'x-mitre-collection', 'name': 'Enterprise ATT&CK', 'x_mitre_version': '20.1'}
    return json.dumps({'type': 'bundle', 'objects': [collection, *(objects or [stix_object()])]}).encode()


def registry():
    return import_stix(source_bytes(), version='20.1', source_url=SOURCE)


def test_offline_import_pins_exact_source_bytes_and_preserves_metadata():
    raw = source_bytes()
    result = import_stix(raw, version='20.1', source_url=SOURCE,
                         expected_sha256='sha256:' + hashlib.sha256(raw).hexdigest())
    validate_registry(result)
    assert result['metadata']['source_sha256'] == 'sha256:' + hashlib.sha256(raw).hexdigest()
    assert result['metadata']['version'] == '20.1'
    assert result['techniques']['T1105']['name'] == 'Official name <script>'
    assert result['techniques']['T1105']['tactics'] == ['command-and-control']
    assert result['techniques']['T1105']['revoked'] is False


def test_registry_tactics_do_not_become_entry_claims_or_graph_edges():
    graph = build_graph([entry()])
    original = copy.deepcopy(graph)
    result = build_techniques(graph, registry())
    technique = result['techniques'][0]
    assert technique['name'] == 'Official name <script>'
    assert technique['registry_status'] == 'verified'
    assert technique['tactics'] == ['command-and-control']
    assert technique['phases'] == ['execution']  # Context from entry, not registry tactics.
    assert technique['confidence_counts'] == {'high': 1, 'low': 0, 'medium': 0, 'verified': 0}
    assert graph == original
    validate_techniques(result, graph, registry())


def test_revoked_deprecated_match_remains_labeled_without_rewriting_entry_claim():
    obj = stix_object()
    obj.update(revoked=True, x_mitre_deprecated=True)
    source = import_stix(source_bytes([obj]), version='20.1', source_url=SOURCE)
    graph = build_graph([entry()])
    result = build_techniques(graph, source)
    assert result['techniques'][0]['revoked'] is True
    assert result['techniques'][0]['deprecated'] is True
    assert len(result['techniques'][0]['evidence']) == 1
    assert result['techniques'][0]['confidence_counts']['high'] == 1


def test_unknown_identifier_remains_unverified_in_a_known_registry():
    result = build_techniques(build_graph([entry(technique='T9999')]), registry())
    technique = result['techniques'][0]
    assert technique['registry_status'] == 'unverified'
    assert technique['name'] is None and technique['revoked'] is None
    assert technique['tactics'] == []


@pytest.mark.parametrize('mutate', [
    lambda r: r['techniques']['T1105'].update(name='tampered'),
    lambda r: r['metadata'].update(source_sha256='sha256:' + '0' * 64),
    lambda r: r['techniques']['T1105']['tactics'].append('execution'),
])
def test_registry_checksum_detects_metadata_tampering(mutate):
    data = registry()
    mutate(data)
    with pytest.raises(ValueError, match='checksum'):
        validate_registry(data)
    with pytest.raises(ValueError, match='checksum'):
        build_techniques(build_graph([entry()]), data)


def test_original_snapshot_hash_mismatch_is_rejected_before_import():
    with pytest.raises(ValueError, match='SHA-256 mismatch'):
        import_stix(source_bytes(), version='20.1', source_url=SOURCE, expected_sha256='sha256:' + '0' * 64)


@pytest.mark.parametrize('source', [
    SOURCE.replace('a' * 40, 'master'), SOURCE.replace('mitre-attack', 'attacker', 1),
    SOURCE.replace('https:', 'http:'), SOURCE + '?redirect=evil', SOURCE + '#fragment',
    SOURCE.replace('enterprise-attack-20.1', 'enterprise-attack-20.0'),
])
def test_source_must_pin_official_repository_commit_and_version(source):
    with pytest.raises(ValueError):
        import_stix(source_bytes(), version='20.1', source_url=source)


@pytest.mark.parametrize('mutate', [
    lambda o: o['external_references'][0].update(url='javascript:alert(1)'),
    lambda o: o['external_references'][0].update(external_id='T1105, T1003'),
    lambda o: o.update(revoked='false'),
    lambda o: o.update(x_mitre_domains=['mobile-attack']),
    lambda o: o['external_references'].append(copy.deepcopy(o['external_references'][0])),
])
def test_invalid_stix_metadata_fails_closed(mutate):
    obj = stix_object()
    mutate(obj)
    with pytest.raises(ValueError):
        import_stix(source_bytes([obj]), version='20.1', source_url=SOURCE)


def test_duplicate_external_ids_and_stix_objects_are_never_last_wins():
    for objects in ([stix_object(), stix_object(suffix='2')], [stix_object(), stix_object()]):
        with pytest.raises(ValueError, match='duplicate'):
            import_stix(source_bytes(objects), version='20.1', source_url=SOURCE)


def test_snapshot_object_order_has_no_effect_on_registry_metadata_records():
    a, b = stix_object(), stix_object('T1003', suffix='2')
    first = import_stix(source_bytes([a, b]), version='20.1', source_url=SOURCE)
    second = import_stix(source_bytes([b, a]), version='20.1', source_url=SOURCE)
    assert first['techniques'] == second['techniques']
    # Original file hashes intentionally differ: source identity is raw byte identity.
    assert first['metadata']['source_sha256'] != second['metadata']['source_sha256']


def test_registry_json_duplicate_keys_are_rejected(tmp_path):
    path = tmp_path / 'registry.json'
    path.write_text('{"schema_version":1,"schema_version":1}')
    with pytest.raises(ValueError, match='duplicate JSON'):
        load_registry(path)


@pytest.mark.parametrize('change', ['wrong_version', 'wrong_name', 'missing', 'duplicate', 'non_object'])
def test_collection_identity_and_actual_version_are_checked_against_declaration(change):
    bundle = json.loads(source_bytes())
    if change == 'wrong_version':
        bundle['objects'][0]['x_mitre_version'] = '19.1'
    elif change == 'wrong_name':
        bundle['objects'][0]['name'] = 'Mobile ATT&CK'
    elif change == 'missing':
        bundle['objects'].pop(0)
    elif change == 'duplicate':
        bundle['objects'].append(copy.deepcopy(bundle['objects'][0]))
    else:
        bundle['objects'].append('not an object')
    with pytest.raises(ValueError):
        import_stix(json.dumps(bundle).encode(), version='20.1', source_url=SOURCE)
