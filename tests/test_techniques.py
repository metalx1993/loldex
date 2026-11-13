"""Technique views retain supporting evidence and reject unsupported aggregation."""
import copy
import pytest

from knowledge.graph import build_graph
from knowledge.techniques import build_techniques, validate_techniques
from tests.test_graph import entry, claim


def test_techniques_are_exact_graph_aggregations_without_fabricated_names():
    a, b = entry('lolbas/a'), entry('lolbas/b')
    b['enrichment']['attack_techniques'].append(claim(level='low'))
    b['platform'] = 'linux'
    graph = build_graph([b, a])
    result = build_techniques(graph)
    validate_techniques(result, graph)
    technique, = result['techniques']
    assert technique['id'] == 'T1105'
    assert technique['name'] is None
    assert technique['registry_status'] == 'unverified'
    assert technique['entry_ids'] == ['lolbas/a', 'lolbas/b']
    assert technique['platforms'] == ['linux', 'windows']
    assert technique['capabilities'] == ['file-download']
    assert technique['confidence_counts'] == {'high': 2, 'low': 1, 'medium': 0, 'verified': 0}
    assert len(technique['evidence']) == 3


@pytest.mark.parametrize('field,value', [
    ('entry_ids', ['lolbas/injected']), ('name', 'Fabricated technique title'),
    ('sources', ['unrelated-source']), ('confidence_counts', {'high': 99}),
    ('evidence', []), ('phases', ['invented-phase']),
])
def test_validator_rejects_unsupported_technique_view(field, value):
    graph = build_graph([entry()])
    data = build_techniques(graph)
    data['techniques'][0][field] = value
    with pytest.raises(ValueError):
        validate_techniques(data, graph)


def test_unknown_syntactic_identifier_remains_explicitly_unverified():
    graph = build_graph([entry(technique='T9999.999')])
    data = build_techniques(graph)
    assert data['techniques'][0]['id'] == 'T9999.999'
    assert data['techniques'][0]['name'] is None
    assert data['techniques'][0]['registry_status'] == 'unverified'


def test_no_technique_claim_yields_empty_view():
    source = entry()
    source['enrichment'].pop('attack_techniques')
    assert build_techniques(build_graph([source])) == {'version': 1, 'count': 0, 'registry': None, 'techniques': []}
