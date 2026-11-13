"""Contract tests for graph derivation: adversarial provenance, identity and ordering."""
import copy
import json
import random

import pytest

from knowledge.graph import build_graph, validate_graph, edge_id, read_entries


def claim(value='T1105', *, ptype='upstream', level='high', note=None):
    provenance = {'type': ptype, 'source': 'LOLBAS', 'adapter': 'lolbas@revision'}
    if note:
        provenance['note'] = note
    return {'value': value, 'provenance': provenance, 'confidence': {'level': level}}


def entry(eid='lolbas/a', *, technique='T1105'):
    return {'id': eid, 'name': '<img src=x onerror=alert(1)>', 'platform': 'windows',
            'sources': [{'project': 'LOLBAS'}],
            'source_data': {'LOLBAS': {'raw': {'upstream': 'verbatim'}}},
            'enrichment': {'attack_techniques': [claim(technique)],
                           'capabilities': [claim('file-download', ptype='adapter')],
                           'phases': [claim('execution', ptype='heuristic', level='low', note='keyword rule')]}}


def test_distinct_claim_evidence_is_never_flattened_or_promoted():
    source = entry()
    source['enrichment']['attack_techniques'] += [claim(), claim(level='low')]
    graph = build_graph([source])
    edges = [e for e in graph['edges'] if e['type'] == 'implements']
    assert len(edges) == 2
    assert {e['confidence']['level'] for e in edges} == {'high', 'low'}
    assert {e['provenance']['type'] for e in edges} == {'upstream'}


def test_derivation_is_pure_and_order_independent():
    sources = [entry('lolbas/z'), entry('lolbas/a')]
    sources[0]['enrichment']['attack_techniques'].append(claim('T1548.003'))
    saved = copy.deepcopy(sources)
    expected = build_graph(sources)
    for seed in range(8):
        random.Random(seed).shuffle(sources)
        for source in sources:
            for values in source['enrichment'].values():
                random.Random(seed).shuffle(values)
        assert build_graph(sources) == expected
    assert saved[0]['source_data'] == next(e for e in sources if e['id'] == 'lolbas/z')['source_data']
    assert '<img' in next(n for n in expected['nodes'] if n['kind'] == 'entry')['label']


def test_no_edges_from_projected_fields_or_invented_registry():
    source = entry()
    source['attack_techniques'] = ['T9999']
    source['capabilities'] = ['reverse-shell']
    graph = build_graph([source])
    assert not any(n['id'] in {'technique:T9999', 'capability:reverse-shell'} for n in graph['nodes'])
    assert all(n['label'] == n['technique_id'] for n in graph['nodes'] if n['kind'] == 'technique')


def test_malformed_technique_claim_is_visible_without_speculative_splitting():
    graph = build_graph([entry(technique='T1542, T1068')])
    assert not any(n['kind'] == 'technique' for n in graph['nodes'])
    diagnostic, = graph['diagnostics']
    assert diagnostic['value'] == 'T1542, T1068'
    assert diagnostic['provenance']['type'] == 'upstream'
    assert diagnostic['confidence']['level'] == 'high'


@pytest.mark.parametrize('mutate', [
    lambda d: d['enrichment']['attack_techniques'][0].pop('provenance'),
    lambda d: d['enrichment']['attack_techniques'][0]['confidence'].update(level='certain'),
    lambda d: d['enrichment']['attack_techniques'][0]['provenance'].update(type='guess'),
    lambda d: d['enrichment']['attack_techniques'][0]['provenance'].update(source='UNDECLARED'),
    lambda d: d['enrichment']['attack_techniques'][0]['provenance'].pop('source'),
    lambda d: d['enrichment']['phases'][0]['provenance'].pop('note'),
    lambda d: d['enrichment'].update(capabilities=[claim('made-up', ptype='adapter')]),
    lambda d: d.update(platform='unknown'),
])
def test_malformed_evidence_fails_closed(mutate):
    source = entry()
    mutate(source)
    with pytest.raises(ValueError):
        build_graph([source])


def test_normalized_identity_collision_fails_instead_of_overwriting():
    with pytest.raises(ValueError, match='duplicate normalized entry'):
        build_graph([entry('lolbas/caf\u00e9'), entry('lolbas/cafe\u0301')])


@pytest.mark.parametrize('corruption', ['reference', 'evidence', 'id', 'duplicate', 'type', 'statistics'])
def test_validator_rejects_corrupted_public_graph(corruption):
    graph = build_graph([entry()])
    if corruption == 'reference':
        graph['edges'][0]['to'] = 'technique:T0000'
    elif corruption == 'evidence':
        graph['edges'][0]['confidence']['level'] = 'certain'
    elif corruption == 'id':
        graph['edges'][0]['id'] = 'sha256:' + '0' * 64
    elif corruption == 'duplicate':
        graph['edges'].append(copy.deepcopy(graph['edges'][0]))
    elif corruption == 'type':
        graph['edges'][0]['type'] = 'similar_to'
    else:
        graph['stats']['entries'] = True
    with pytest.raises(ValueError):
        validate_graph(graph)


def test_corrupt_corpus_input_is_not_silently_skipped(tmp_path):
    (tmp_path / 'bad.yaml').write_text('- not an entry\n')
    with pytest.raises(ValueError):
        read_entries(tmp_path)


def test_validator_rejects_unsupported_isolated_technique():
    graph = build_graph([entry()])
    graph['nodes'].append({'id': 'technique:T9999', 'kind': 'technique', 'label': 'T9999', 'technique_id': 'T9999'})
    graph['nodes'].sort(key=lambda n: n['id'])
    graph['stats']['nodes'] += 1
    graph['stats']['techniques'] += 1
    with pytest.raises(ValueError, match='isolated'):
        validate_graph(graph)


def test_validator_rejects_rehashed_platform_divergence():
    source = entry()
    graph = build_graph([source])
    for node in graph['nodes']:
        if node['kind'] == 'entry':
            node['platform'] = 'linux'
    with pytest.raises(ValueError, match='platform'):
        validate_graph(graph)


def test_validator_rejects_rehashed_evidence_from_unrelated_project():
    graph = build_graph([entry()])
    edge = next(e for e in graph['edges'] if e['type'] == 'implements')
    edge['provenance']['source'] = 'UNDECLARED'
    edge['id'] = edge_id(edge)
    graph['edges'].sort(key=lambda e: e['id'])
    with pytest.raises(ValueError, match='membership'):
        validate_graph(graph)


def test_structural_source_evidence_cannot_be_rewritten_as_upstream_behavior():
    graph = build_graph([entry()])
    edge = next(e for e in graph['edges'] if e['type'] == 'sourced_from')
    edge['provenance']['type'] = 'upstream'
    edge['id'] = edge_id(edge)
    graph['edges'].sort(key=lambda e: e['id'])
    with pytest.raises(ValueError, match='structural evidence'):
        validate_graph(graph)


def test_diagnostic_cannot_claim_an_unsupported_upstream_source():
    graph = build_graph([entry(technique='T1542, T1068')])
    graph['diagnostics'][0]['provenance']['source'] = 'UNDECLARED'
    with pytest.raises(ValueError, match='diagnostic source'):
        validate_graph(graph)
