"""Offline importer for a pinned official MITRE ATT&CK Enterprise STIX snapshot.

Registry metadata enriches technique display only; it never creates entry claims.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import unicodedata
from urllib.parse import urlparse
from uuid import UUID

from phase5.canonical import canonical_bytes
from knowledge.graph import ATTACK_ID, ROOT

DEFAULT_REGISTRY = ROOT / 'data/registry/enterprise-attack.json'
_DIGEST = re.compile(r'sha256:[0-9a-f]{64}\Z')
_VERSION = re.compile(r'[0-9]+(?:\.[0-9]+)+\Z')


def _pairs_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON object key')
        result[key] = value
    return result


def _parse_json(raw):
    return json.loads(raw, object_pairs_hook=_pairs_object,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('invalid JSON constant')))


def _hash(value):
    return 'sha256:' + hashlib.sha256(canonical_bytes(value)).hexdigest()


def _string(value, field):
    if not isinstance(value, str) or not value or any(0xD800 <= ord(c) <= 0xDFFF for c in value):
        raise ValueError(f'{field} must be a non-empty scalar string')
    return unicodedata.normalize('NFC', value)


def _source_url(url, version):
    value = _string(url, 'source_url')
    if any(ord(c) < 33 for c in value):
        raise ValueError('registry source URL contains whitespace or controls')
    parsed = urlparse(value)
    if parsed.scheme != 'https' or parsed.hostname not in {'raw.githubusercontent.com', 'github.com'} or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('registry source must be an HTTPS URL of official MITRE attack-stix-data')
    prefix = '/mitre-attack/attack-stix-data/'
    if not re.fullmatch(re.escape(prefix) + r'[0-9a-f]{40}/enterprise-attack/enterprise-attack-' + re.escape(version) + r'\.json', parsed.path):
        raise ValueError('registry source must pin a commit and the declared Enterprise version')
    return value


def _technique_url(value, tid):
    expected = 'https://attack.mitre.org/techniques/' + tid.replace('.', '/') + '/'
    if value not in {expected, expected[:-1]}:
        raise ValueError(f'official technique URL does not match {tid}')
    return value


def _stix_id(value):
    value = _string(value, 'stix_id')
    if not value.startswith('attack-pattern--'):
        raise ValueError('invalid attack-pattern STIX identity')
    try:
        parsed = UUID(value[len('attack-pattern--'):])
    except (ValueError, AttributeError) as exc:
        raise ValueError('invalid attack-pattern STIX identity') from exc
    if str(parsed) != value[len('attack-pattern--'):]:
        raise ValueError('STIX UUID must use canonical lowercase representation')
    return value


def import_stix(raw, *, version, source_url, expected_sha256=None):
    if not isinstance(raw, bytes):
        raise ValueError('STIX input must be original file bytes')
    digest = 'sha256:' + hashlib.sha256(raw).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError('STIX source SHA-256 mismatch')
    if not isinstance(version, str) or not _VERSION.fullmatch(version):
        raise ValueError('snapshot version must be explicit, e.g. 20.1')
    source_url = _source_url(source_url, version)
    bundle = _parse_json(raw)
    if not isinstance(bundle, dict) or bundle.get('type') != 'bundle' or not isinstance(bundle.get('objects'), list):
        raise ValueError('STIX source must be a bundle with objects')
    if any(not isinstance(obj, dict) for obj in bundle['objects']):
        raise ValueError('STIX objects must be mappings')
    collections = [obj for obj in bundle['objects'] if obj.get('type') == 'x-mitre-collection']
    if len(collections) != 1:
        raise ValueError('STIX snapshot requires exactly one MITRE collection')
    collection = collections[0]
    if collection.get('name') != 'Enterprise ATT&CK':
        raise ValueError('STIX collection must be Enterprise ATT&CK')
    if collection.get('x_mitre_version') != version:
        raise ValueError('STIX collection version does not match the declared snapshot version')
    techniques, seen_stix = {}, set()
    for obj in bundle['objects']:
        if not isinstance(obj, dict):
            raise ValueError('STIX objects must be mappings')
        if obj.get('type') != 'attack-pattern':
            continue
        domains = obj.get('x_mitre_domains')
        if not isinstance(domains, list) or 'enterprise-attack' not in domains:
            raise ValueError('attack-pattern is not attributed to Enterprise ATT&CK')
        sid = _stix_id(obj.get('id'))
        if sid in seen_stix:
            raise ValueError('duplicate attack-pattern STIX object')
        seen_stix.add(sid)
        references = obj.get('external_references')
        if not isinstance(references, list):
            raise ValueError('attack-pattern requires external references')
        official = [r for r in references if isinstance(r, dict) and r.get('source_name') == 'mitre-attack']
        if len(official) != 1:
            raise ValueError('attack-pattern requires exactly one MITRE ATT&CK reference')
        reference = official[0]
        tid = _string(reference.get('external_id'), 'external_id')
        if not ATTACK_ID.fullmatch(tid) or tid in techniques:
            raise ValueError('invalid or duplicate MITRE technique identifier')
        phases = obj.get('kill_chain_phases', [])
        if not isinstance(phases, list):
            raise ValueError('kill_chain_phases must be an array')
        tactics = set()
        for phase in phases:
            if not isinstance(phase, dict):
                raise ValueError('kill_chain_phase must be an object')
            if phase.get('kill_chain_name') == 'mitre-attack':
                tactics.add(_string(phase.get('phase_name'), 'phase_name'))
        revoked = obj.get('revoked', False)
        deprecated = obj.get('x_mitre_deprecated', False)
        if type(revoked) is not bool or type(deprecated) is not bool:
            raise ValueError('revoked and deprecated must be booleans')
        techniques[tid] = {
            'id': tid, 'name': _string(obj.get('name'), 'name'),
            'description': _string(obj.get('description'), 'description'),
            'url': _technique_url(reference.get('url'), tid),
            'tactics': sorted(tactics), 'revoked': revoked, 'deprecated': deprecated,
            'stix_id': sid, 'modified': _string(obj.get('modified'), 'modified'),
            'object_version': _string(obj.get('x_mitre_version', 'unknown'), 'x_mitre_version'),
        }
    if not techniques:
        raise ValueError('registry must contain MITRE technique metadata')
    payload = {'schema_version': 1, 'metadata': {
        'domain': 'enterprise-attack', 'version': version, 'source_url': source_url,
        'source_sha256': digest, 'source_object_count': len(bundle['objects']),
        'technique_count': len(techniques),
    }, 'techniques': dict(sorted(techniques.items()))}
    # Normalize all strings before pinning the derived artifact checksum.
    payload = json.loads(canonical_bytes(payload))
    registry = {**payload, 'checksum': _hash(payload)}
    validate_registry(registry)
    return registry


def validate_registry(registry):
    if not isinstance(registry, dict) or set(registry) != {'schema_version', 'metadata', 'techniques', 'checksum'}:
        raise ValueError('invalid registry shape')
    payload = {key: registry[key] for key in ('schema_version', 'metadata', 'techniques')}
    if registry['checksum'] != _hash(payload):
        raise ValueError('registry checksum mismatch')
    if json.loads(canonical_bytes(registry)) != registry:
        raise ValueError('registry must be NFC normalized')
    if type(registry['schema_version']) is not int or registry['schema_version'] != 1:
        raise ValueError('unsupported registry schema')
    meta = registry['metadata']
    expected = {'domain', 'version', 'source_url', 'source_sha256', 'source_object_count', 'technique_count'}
    if not isinstance(meta, dict) or set(meta) != expected or meta['domain'] != 'enterprise-attack':
        raise ValueError('invalid registry metadata')
    if not isinstance(meta['version'], str) or not _VERSION.fullmatch(meta['version']):
        raise ValueError('invalid registry version')
    _source_url(meta['source_url'], meta['version'])
    if not isinstance(meta['source_sha256'], str) or not _DIGEST.fullmatch(meta['source_sha256']):
        raise ValueError('invalid source digest')
    if any(type(meta[k]) is not int or meta[k] < 1 for k in ('source_object_count', 'technique_count')):
        raise ValueError('invalid registry counts')
    techniques = registry['techniques']
    if not isinstance(techniques, dict) or len(techniques) != meta['technique_count'] or len(techniques) > meta['source_object_count']:
        raise ValueError('registry technique count mismatch')
    seen_stix = set()
    expected_fields = {'id', 'name', 'description', 'url', 'tactics', 'revoked', 'deprecated', 'stix_id', 'modified', 'object_version'}
    for tid, record in techniques.items():
        if not isinstance(tid, str) or not ATTACK_ID.fullmatch(tid) or not isinstance(record, dict) or set(record) != expected_fields or record['id'] != tid:
            raise ValueError('invalid registry technique record')
        for key in ('name', 'description', 'modified', 'object_version'):
            _string(record[key], key)
        _technique_url(record['url'], tid)
        sid = _stix_id(record['stix_id'])
        if sid in seen_stix:
            raise ValueError('duplicate registry STIX identity')
        seen_stix.add(sid)
        if type(record['revoked']) is not bool or type(record['deprecated']) is not bool:
            raise ValueError('invalid lifecycle flags')
        tactics = record['tactics']
        if not isinstance(tactics, list) or any(not isinstance(t, str) or not t for t in tactics) or tactics != sorted(set(tactics)):
            raise ValueError('invalid registry tactic metadata')


def load_registry(path=DEFAULT_REGISTRY):
    registry = _parse_json(Path(path).read_text(encoding='utf-8'))
    validate_registry(registry)
    return registry
