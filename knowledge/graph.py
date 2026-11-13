"""Deterministic, evidence-preserving graph derived from layered entries."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import unicodedata

import yaml

from phase5.canonical import canonical_bytes

ROOT = Path(__file__).resolve().parent.parent
_TAXONOMY = yaml.safe_load((ROOT / 'schema/schema.yaml').read_text())['taxonomy']
PLATFORMS = {'linux', 'windows', 'active-directory', 'macos'}
PROVENANCE = {'upstream', 'adapter', 'heuristic', 'manual'}
CONFIDENCE = {'low', 'medium', 'high', 'verified'}
RELATIONS = {
    'implements': 'technique', 'has_capability': 'capability',
    'operates_in': 'phase', 'belongs_to': 'platform', 'sourced_from': 'source',
}
CLAIM_RELATIONS = {
    'attack_techniques': ('implements', 'technique'),
    'capabilities': ('has_capability', 'capability'),
    'phases': ('operates_in', 'phase'),
}
PLATFORM_NOTE = 'Entry platform metadata; not a behavioral claim.'
SOURCE_NOTES = {
    'Declared source membership from entry.sources[].project.',
    'Source payload membership from entry.source_data project key.',
}
ATTACK_ID = re.compile(r'T[0-9]{4}(?:\.[0-9]{3})?\Z')


def _text(value, label):
    if not isinstance(value, str) or not value:
        raise ValueError(f'{label} must be a non-empty string')
    result = unicodedata.normalize('NFC', value)
    if any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF for c in result):
        raise ValueError(f'{label} contains invalid control or surrogate characters')
    return result


def _normal(value):
    """Normalize using CORE's already-frozen canonical JSON primitive."""
    return json.loads(canonical_bytes(value))


def _evidence(provenance, confidence):
    if not isinstance(provenance, dict) or set(provenance) - {'type', 'source', 'adapter', 'note'}:
        raise ValueError('invalid provenance object')
    if provenance.get('type') not in PROVENANCE:
        raise ValueError('invalid provenance type')
    for key, value in provenance.items():
        _text(value, f'provenance.{key}')
    if provenance['type'] == 'upstream' and not provenance.get('source'):
        raise ValueError('upstream evidence requires a source')
    if provenance['type'] == 'heuristic' and not provenance.get('note'):
        raise ValueError('heuristic evidence requires a rationale')
    if not isinstance(confidence, dict) or set(confidence) != {'level'}:
        raise ValueError('invalid confidence object')
    if confidence['level'] not in CONFIDENCE:
        raise ValueError('invalid confidence level')
    return _normal({'provenance': provenance, 'confidence': confidence})


def edge_id(edge):
    payload = {key: edge[key] for key in ('type', 'from', 'to', 'provenance', 'confidence')}
    return 'sha256:' + hashlib.sha256(canonical_bytes(payload)).hexdigest()


def _edge(relation, origin, target, provenance, confidence):
    edge = {'type': relation, 'from': origin, 'to': target,
            **_evidence(provenance, confidence)}
    edge['id'] = edge_id(edge)
    return edge


def read_entries(directory):
    """Load regular corpus YAML files. Invalid records fail the build, never disappear."""
    entries = []
    for path in sorted(Path(directory).rglob('*.yaml')):
        if path.is_symlink() or not path.is_file():
            raise ValueError(f'corpus input must be a regular file: {path}')
        entry = yaml.safe_load(path.read_text(encoding='utf-8'))
        if not isinstance(entry, dict):
            raise ValueError(f'entry must be an object: {path}')
        entries.append(entry)
    return entries


def _node(kind, value, *, label=None, **extra):
    return {'id': kind + ':' + value, 'kind': kind, 'label': label or value, **extra}


def _stats(nodes, edges):
    return {'nodes': len(nodes), 'edges': len(edges),
            'entries': sum(n['kind'] == 'entry' for n in nodes),
            'techniques': sum(n['kind'] == 'technique' for n in nodes)}


def build_graph(entries):
    nodes, edges, diagnostics, seen = {}, {}, {}, set()

    def add_node(node):
        existing = nodes.get(node['id'])
        if existing is not None and existing != node:
            raise ValueError(f'conflicting node definition: {node["id"]}')
        nodes[node['id']] = node

    def add_edge(relation, origin, target, provenance, confidence):
        edge = _edge(relation, origin, target, provenance, confidence)
        edges[edge['id']] = edge

    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError('entry must be an object')
        eid = _text(entry.get('id'), 'entry.id')
        if eid in seen:
            raise ValueError(f'duplicate normalized entry id: {eid}')
        seen.add(eid)
        name = _text(entry.get('name'), 'entry.name')
        platform = _text(entry.get('platform'), 'entry.platform')
        if platform not in PLATFORMS:
            raise ValueError(f'unknown platform: {platform}')
        origin = 'entry:' + eid
        add_node(_node('entry', eid, label=name, entry_id=eid, platform=platform))
        add_node(_node('platform', platform))
        add_edge('belongs_to', origin, 'platform:' + platform,
                 {'type': 'adapter', 'note': PLATFORM_NOTE},
                 {'level': 'high'})
        declared = entry.get('sources', [])
        raw_sources = entry.get('source_data', {})
        if not isinstance(declared, list) or not isinstance(raw_sources, dict):
            raise ValueError('sources must be a list and source_data an object')
        source_projects = set()
        for source in declared:
            if not isinstance(source, dict):
                raise ValueError('source declaration must be an object')
            project = _text(source.get('project'), 'sources.project')
            source_projects.add(project)
            add_node(_node('source', project))
            add_edge('sourced_from', origin, 'source:' + project,
                     {'type': 'adapter', 'source': project,
                      'note': 'Declared source membership from entry.sources[].project.'},
                     {'level': 'high'})
        normalized_projects = set()
        for source, block in raw_sources.items():
            project = _text(source, 'source_data project')
            if project in normalized_projects:
                raise ValueError('duplicate normalized source_data project')
            normalized_projects.add(project)
            if not isinstance(block, dict) or not isinstance(block.get('raw'), dict):
                raise ValueError('source_data block requires an object raw payload')
            source_projects.add(project)
            add_node(_node('source', project))
            add_edge('sourced_from', origin, 'source:' + project,
                     {'type': 'adapter', 'source': project,
                      'note': 'Source payload membership from entry.source_data project key.'},
                     {'level': 'high'})
        enrichment = entry.get('enrichment', {})
        if not isinstance(enrichment, dict):
            raise ValueError('enrichment must be an object')
        for field, (relation, kind) in CLAIM_RELATIONS.items():
            claims = enrichment.get(field, [])
            if not isinstance(claims, list):
                raise ValueError(f'enrichment.{field} must be a list')
            for claim in claims:
                if not isinstance(claim, dict) or set(claim) != {'value', 'provenance', 'confidence'}:
                    raise ValueError(f'invalid {field} claim shape')
                value = _text(claim['value'], f'enrichment.{field}.value')
                evidence = _evidence(claim['provenance'], claim['confidence'])
                psource = evidence['provenance'].get('source')
                if evidence['provenance']['type'] in {'upstream', 'adapter'} and psource and psource not in source_projects:
                    raise ValueError(f'claim source {psource} has no entry source evidence')
                if kind == 'technique' and not ATTACK_ID.fullmatch(value):
                    diagnostic = {'code': 'INVALID_TECHNIQUE_ID', 'entry_id': eid,
                                  'field': field, 'value': value, **evidence}
                    diagnostics[canonical_bytes(diagnostic)] = diagnostic
                    continue
                if kind in {'capability', 'phase'} and value not in _TAXONOMY[kind]:
                    raise ValueError(f'unknown {kind}: {value}')
                extra = {'technique_id': value} if kind == 'technique' else {}
                add_node(_node(kind, value, **extra))
                add_edge(relation, origin, kind + ':' + value, **evidence)
    result = {'version': 1, 'nodes': sorted(nodes.values(), key=lambda n: n['id']),
              'edges': sorted(edges.values(), key=lambda e: e['id']),
              'diagnostics': [diagnostics[key] for key in sorted(diagnostics)],
              'stats': _stats(list(nodes.values()), list(edges.values()))}
    result = _normal(result)
    validate_graph(result)
    return result


def validate_graph(graph):
    """Reject corrupted graph data before it reaches a public view."""
    if not isinstance(graph, dict) or set(graph) != {'version', 'nodes', 'edges', 'diagnostics', 'stats'}:
        raise ValueError('invalid graph shape')
    if type(graph['version']) is not int or graph['version'] != 1:
        raise ValueError('unsupported graph version')
    if not all(isinstance(graph[k], list) for k in ('nodes', 'edges', 'diagnostics')):
        raise ValueError('nodes, edges and diagnostics must be arrays')
    if _normal(graph) != graph:
        raise ValueError('graph strings must already be NFC normalized')
    nodes = {}
    for node in graph['nodes']:
        if not isinstance(node, dict) or not {'id', 'kind', 'label'} <= node.keys():
            raise ValueError('invalid node shape')
        nid, kind = _text(node['id'], 'node.id'), node['kind']
        if kind not in {'entry', *RELATIONS.values()} or not nid.startswith(kind + ':') or not nid[len(kind) + 1:]:
            raise ValueError('invalid typed node id')
        _text(node['label'], 'node.label')
        if nid in nodes:
            raise ValueError('duplicate node id')
        if kind == 'entry':
            if set(node) != {'id', 'kind', 'label', 'entry_id', 'platform'} or nid != 'entry:' + node['entry_id'] or node['platform'] not in PLATFORMS:
                raise ValueError('invalid entry node')
        elif kind == 'technique':
            if set(node) != {'id', 'kind', 'label', 'technique_id'} or not ATTACK_ID.fullmatch(node['technique_id']) or nid != 'technique:' + node['technique_id'] or node['label'] != node['technique_id']:
                raise ValueError('invalid technique node')
        else:
            if set(node) != {'id', 'kind', 'label'} or nid != kind + ':' + node['label']:
                raise ValueError('invalid attribute node')
            if kind in {'phase', 'capability'} and node['label'] not in _TAXONOMY[kind]:
                raise ValueError('unknown taxonomy node')
            if kind == 'platform' and node['label'] not in PLATFORMS:
                raise ValueError('unknown platform node')
        nodes[nid] = node
    seen_edges = set()
    incident_nodes = set()
    platforms = {}
    source_membership = {}
    for edge in graph['edges']:
        if not isinstance(edge, dict) or set(edge) != {'id', 'type', 'from', 'to', 'provenance', 'confidence'}:
            raise ValueError('invalid edge shape')
        if edge['type'] not in RELATIONS:
            raise ValueError('unknown relation')
        if edge['from'] not in nodes or edge['to'] not in nodes or edge['from'] == edge['to']:
            raise ValueError('dangling reference or self-loop')
        if nodes[edge['from']]['kind'] != 'entry' or nodes[edge['to']]['kind'] != RELATIONS[edge['type']]:
            raise ValueError('invalid relation endpoint kinds')
        _evidence(edge['provenance'], edge['confidence'])
        if edge['id'] != edge_id(edge) or edge['id'] in seen_edges:
            raise ValueError('altered edge id or duplicate edge')
        seen_edges.add(edge['id'])
        incident_nodes.update((edge['from'], edge['to']))
        if edge['type'] == 'belongs_to':
            if edge['provenance'] != {'type': 'adapter', 'note': PLATFORM_NOTE} or edge['confidence'] != {'level': 'high'}:
                raise ValueError('platform membership requires exact structural evidence')
            if edge['from'] in platforms or nodes[edge['to']]['label'] != nodes[edge['from']]['platform']:
                raise ValueError('platform edge diverges from entry metadata')
            platforms[edge['from']] = edge['to']
        if edge['type'] == 'sourced_from':
            provenance = edge['provenance']
            if set(provenance) != {'type', 'source', 'note'} or provenance['type'] != 'adapter' or provenance['source'] != nodes[edge['to']]['label'] or provenance['note'] not in SOURCE_NOTES or edge['confidence'] != {'level': 'high'}:
                raise ValueError('source membership requires exact structural evidence')
            source_membership.setdefault(edge['from'], set()).add(nodes[edge['to']]['label'])
    if set(nodes) != incident_nodes:
        raise ValueError('unsupported isolated graph node')
    if set(platforms) != {nid for nid, node in nodes.items() if node['kind'] == 'entry'}:
        raise ValueError('entry requires exactly one matching platform edge')
    for edge in graph['edges']:
        source = edge['provenance'].get('source')
        if edge['provenance']['type'] in {'upstream', 'adapter'} and source and source not in source_membership.get(edge['from'], set()):
            raise ValueError('claim source has no entry membership evidence')
    if [n['id'] for n in graph['nodes']] != sorted(nodes):
        raise ValueError('nodes must be sorted by id')
    if [e['id'] for e in graph['edges']] != sorted(seen_edges):
        raise ValueError('edges must be sorted by id')
    diagnostic_bytes = []
    for diagnostic in graph['diagnostics']:
        if not isinstance(diagnostic, dict) or set(diagnostic) != {'code', 'entry_id', 'field', 'value', 'provenance', 'confidence'}:
            raise ValueError('invalid diagnostic shape')
        if diagnostic['code'] != 'INVALID_TECHNIQUE_ID' or diagnostic['field'] != 'attack_techniques' or 'entry:' + diagnostic['entry_id'] not in nodes:
            raise ValueError('invalid diagnostic reference')
        value = _text(diagnostic['value'], 'diagnostic.value')
        if ATTACK_ID.fullmatch(value):
            raise ValueError('valid technique marked invalid')
        _evidence(diagnostic['provenance'], diagnostic['confidence'])
        source = diagnostic['provenance'].get('source')
        if diagnostic['provenance']['type'] in {'upstream', 'adapter'} and source and source not in source_membership.get('entry:' + diagnostic['entry_id'], set()):
            raise ValueError('diagnostic source has no entry membership evidence')
        diagnostic_bytes.append(canonical_bytes(diagnostic))
    if diagnostic_bytes != sorted(set(diagnostic_bytes)):
        raise ValueError('diagnostics must be sorted and unique')
    expected_stats = _stats(graph['nodes'], graph['edges'])
    if graph['stats'] != expected_stats or any(type(v) is not int for v in graph['stats'].values()):
        raise ValueError('incorrect graph statistics')


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n', encoding='utf-8')
