"""Technique views are exact aggregations of the validated relationship graph."""
from __future__ import annotations

from collections import Counter, defaultdict
import copy

from knowledge.graph import CONFIDENCE, validate_graph
from knowledge.registry import validate_registry


def _aggregate(graph, registry=None):
    nodes = {n['id']: n for n in graph['nodes']}
    context = defaultdict(lambda: defaultdict(set))
    evidence = defaultdict(list)
    for edge in graph['edges']:
        if edge['type'] == 'implements':
            evidence[nodes[edge['to']]['technique_id']].append(copy.deepcopy(edge))
        else:
            context[edge['from']][edge['type']].add(nodes[edge['to']]['label'])
    techniques = []
    for tid in sorted(n['technique_id'] for n in graph['nodes'] if n['kind'] == 'technique'):
        supporting = sorted(evidence[tid], key=lambda e: e['id'])
        entry_nodes = sorted({edge['from'] for edge in supporting})
        attributes = {}
        for field, relation in [('platforms', 'belongs_to'), ('sources', 'sourced_from'),
                                ('capabilities', 'has_capability'), ('phases', 'operates_in')]:
            attributes[field] = sorted({value for eid in entry_nodes for value in context[eid][relation]})
        counts = Counter(edge['confidence']['level'] for edge in supporting)
        record = registry['techniques'].get(tid) if registry else None
        registry_fields = {key: copy.deepcopy(record[key]) if record else ([] if key == 'tactics' else None)
                           for key in ('name', 'description', 'url', 'tactics', 'revoked', 'deprecated', 'stix_id', 'modified')}
        techniques.append({'id': tid, **registry_fields, 'registry_status': 'verified' if record else 'unverified',
                           'entry_ids': sorted(nodes[eid]['entry_id'] for eid in entry_nodes),
                           **attributes, 'evidence': supporting,
                           'confidence_counts': {level: counts[level] for level in sorted(CONFIDENCE)}})
    registry_meta = {**copy.deepcopy(registry['metadata']), 'checksum': registry['checksum']} if registry else None
    return {'version': 1, 'count': len(techniques), 'registry': registry_meta, 'techniques': techniques}


def build_techniques(graph, registry=None):
    validate_graph(graph)
    if registry is not None:
        validate_registry(registry)
    return _aggregate(graph, registry)


def validate_techniques(data, graph, registry=None):
    validate_graph(graph)
    if registry is not None:
        validate_registry(registry)
    if data != _aggregate(graph, registry):
        raise ValueError('technique view diverges from supporting graph evidence')
    if type(data.get('version')) is not int or type(data.get('count')) is not int:
        raise ValueError('technique version and count must be integers')
    for technique in data['techniques']:
        if any(type(v) is not int for v in technique['confidence_counts'].values()):
            raise ValueError('confidence counts must be integers')
