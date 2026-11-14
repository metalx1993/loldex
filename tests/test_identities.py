"""Adversarial Phase 9: explicit identities, stale evidence and no transitive merging."""
import copy
import hashlib
import json
import random

import pytest

from knowledge.identities import (build_identities, validate_identities, seal_identity_registry,
                                  validate_identity_registry, load_identity_registry)

REVISION = 'a' * 40


def entry(eid='lolbas/alpha', *, platform='windows', command='alpha.exe /go', raw=None, source='LOLBAS'):
    return {'id': eid, 'name': 'Ambiguous display name', 'platform': platform,
            'type': 'binary' if source == 'LOLBAS' else 'technique',
            'commands': [{'template': command}], 'capabilities': ['command-execution'],
            'attack_techniques': ['T1059'], 'sources': [{'project': source}],
            'source_data': {source: {'raw': raw or {'document': 'Name: Alpha.exe\nFull_Path:\n- Path: C:\\Windows\\Alpha.exe\n', 'source_file': 'OSBinaries/Alpha.yml'},
                                     'upstream_version': REVISION, 'upstream_url': 'https://example.invalid'}}}


def tool(eid='tool:alpha', token='alpha.exe'):
    return {'id': eid, 'kind': 'tool', 'label': 'Alpha',
            'platform_scope': {'runtime': ['windows'], 'contexts': ['windows', 'active-directory']},
            'identifiers': [{'namespace': 'windows-path', 'value': 'C:\\Windows\\Alpha.exe'}],
            'candidate_tokens': [token],
            'scope_note': 'Logical tool declaration, not executable bit identity or entry equivalence.'}


def claim(document, *, cid='claim:alpha:one', entity_id='tool:alpha', relation='documents_tool', source='LOLBAS'):
    text = document['source_data'][source]['raw']['document']
    explicit = relation == 'documents_tool'
    return {'id': cid, 'entity_id': entity_id, 'entry_id': document['id'], 'relation': relation,
            'entry_context': document['platform'],
            'provenance': {'type': 'adapter' if explicit else 'heuristic', 'source': source,
                           'curator': 'agent', 'note': 'Explicit source metadata.' if explicit else 'Command token only; runtime PATH is not proved.'},
            'confidence': {'level': 'high' if explicit else 'low'},
            'evidence': [{'source': source, 'review_revision': REVISION,
                          'url': ('https://github.com/LOLBAS-Project/LOLBAS/blob/' + REVISION + '/yml/OSBinaries/Alpha.yml') if source == 'LOLBAS' else ('https://github.com/lolad-project/lolad-project.github.io/blob/' + REVISION + '/index.html'),
                          'pointer': '/document', 'sha256': 'sha256:' + hashlib.sha256(text.encode()).hexdigest(),
                          'required_literals': ['Name: Alpha.exe', 'C:\\Windows\\Alpha.exe'] if explicit else ['alpha.exe']}]}


def registry(documents=None, claims=None, entities=None, aliases=None):
    documents = documents or [entry()]
    return seal_identity_registry({'version': 1, 'revision': 1,
                                   'entities': entities if entities is not None else [tool()],
                                   'claims': claims if claims is not None else [claim(documents[0])],
                                   'aliases': aliases or []})


def test_same_names_capabilities_or_mitre_never_create_identity_membership():
    a, b = entry(), entry('lolbas/other', command='unrelated.exe')
    data = build_identities([a, b], registry([a]))
    assert len(data['entities']) == 1
    assert list(data['entry_index']) == ['lolbas/alpha']
    assert not data['candidates']
    assert build_identities([a, b])['entities'] == []


def test_command_candidate_remains_heuristic_low_without_membership_or_confidence_laundering():
    a, b = entry(), entry('lolad/operation', source='LOLAD', platform='active-directory')
    data = build_identities([a, b], registry([a]))
    candidate, = data['candidates']
    assert candidate['entry_id'] == b['id']
    assert candidate['relation'] == 'candidate_tool'
    assert candidate['provenance']['type'] == 'heuristic'
    assert candidate['confidence']['level'] == 'low'
    assert b['id'] not in data['entry_index']
    assert len(data['entities'][0]['members']) == 1


def test_platform_ambiguous_command_candidate_is_not_an_active_identity():
    a, b = entry(), entry('gtfobins/alpha', platform='linux', source='GTFOBins')
    data = build_identities([a, b], registry([a]))
    assert data['candidates'][0]['status'] == 'ambiguous'
    assert b['id'] not in data['entry_index']


def test_stale_or_removed_claim_keeps_identity_and_claim_ids_without_auto_refresh():
    original = entry()
    source = registry([original])
    changed = copy.deepcopy(original)
    changed['source_data']['LOLBAS']['raw']['document'] += '# source changed\n'
    data = build_identities([changed], source)
    member, = data['entities'][0]['members']
    assert member['status'] == 'witness_changed'
    assert member['id'] == 'claim:alpha:one'
    assert data['entry_index'] == {}
    missing = build_identities([], source)
    assert missing['entities'][0]['id'] == 'tool:alpha'
    assert missing['entities'][0]['members'][0]['status'] == 'missing'
    assert missing['entities'][0]['members'][0]['evidence'] == source['claims'][0]['evidence']


def test_source_revision_change_alone_does_not_invalidate_exact_raw_bytes():
    source = entry()
    curated = registry([source])
    source['source_data']['LOLBAS']['upstream_version'] = 'b' * 40
    member = build_identities([source], curated)['entities'][0]['members'][0]
    assert member['status'] == 'active'
    assert member['review_revision'] == REVISION
    assert member['current_revision'] == 'b' * 40


def test_display_label_change_does_not_rename_registry_ids_or_replace_source_evidence():
    source = entry()
    curated = registry([source])
    source['name'] = 'Different display label'
    data = build_identities([source], curated)
    assert data['entities'][0]['id'] == 'tool:alpha'
    assert data['entities'][0]['members'][0]['status'] == 'active'
    assert data['entities'][0]['members'][0]['id'] == 'claim:alpha:one'


def test_uses_tool_membership_does_not_equate_tool_and_technique_or_create_transitive_groups():
    a = entry()
    shared = entry('lolad/shared', source='LOLAD', platform='active-directory',
                   command='alpha.exe /one\nbeta.exe /two',
                   raw={'document': 'alpha.exe /one\nbeta.exe /two'})
    alpha_use = claim(shared, cid='claim:alpha:operation', relation='uses_tool', source='LOLAD')
    beta_use = copy.deepcopy(alpha_use)
    beta_use.update(id='claim:beta:operation', entity_id='tool:beta')
    beta_use['evidence'][0]['required_literals'] = ['beta.exe']
    curated = registry([a], claims=[claim(a), alpha_use, beta_use], entities=[tool(), tool('tool:beta', 'beta.exe')])
    data = build_identities([a, shared], curated)
    assert len(data['entities']) == 2
    assert len(data['entry_index'][shared['id']]) == 2
    assert data['entry_index'][a['id']] == [{'entity_id': 'tool:alpha', 'claim_id': 'claim:alpha:one', 'relation': 'documents_tool'}]
    assert [m['confidence']['level'] for m in data['entities'][1]['members']] == ['low']


def test_conflicting_explicit_tool_claims_cannot_pick_a_winner():
    source = entry()
    a, b = claim(source), claim(source, cid='claim:beta:one', entity_id='tool:beta')
    with pytest.raises(ValueError, match='conflicting declared tool'):
        registry([source], claims=[a, b], entities=[tool(), tool('tool:beta', 'beta.exe')])


@pytest.mark.parametrize('mutate', [
    lambda c: c['provenance'].update(type='manual'),
    lambda c: c['confidence'].update(level='verified'),
    lambda c: c.update(entity_id='tool:missing'),
    lambda c: c['evidence'][0].update(required_literals=['Alpha.exe']),
    lambda c: c['evidence'][0].update(url='javascript:alert(1)'),
    lambda c: c['evidence'][0].update(review_revision='main'),
    lambda c: c['evidence'][0].update(sha256='made-up'),
    lambda c: c['evidence'][0].update(source='WADComs'),
])
def test_invalid_or_false_agent_provenance_is_rejected(mutate):
    source = entry()
    membership = claim(source)
    mutate(membership)
    with pytest.raises(ValueError):
        registry([source], claims=[membership])


def test_determinism_and_input_immutability_under_registry_and_entry_permutations():
    a, b = entry(), entry('lolad/operation', source='LOLAD', platform='active-directory')
    curated = registry([a])
    original_entries, original_registry = copy.deepcopy([a, b]), copy.deepcopy(curated)
    first = build_identities([a, b], curated)
    for seed in range(6):
        shuffled = copy.deepcopy([a, b])
        random.Random(seed).shuffle(shuffled)
        assert build_identities(shuffled, curated) == first
    assert original_entries == [a, b] and original_registry == curated
    validate_identities(first, [a, b], curated)
    data = copy.deepcopy(first)
    data['entities'][0]['members'][0]['confidence']['level'] = 'verified'
    with pytest.raises(ValueError):
        validate_identities(data, [a, b], curated)


def test_output_bool_cannot_impersonate_version_integer():
    data = build_identities([])
    data['version'] = True
    with pytest.raises(ValueError):
        validate_identities(data, [])


def test_registry_checksum_and_duplicate_json_keys_are_checked(tmp_path):
    curated = registry()
    curated['entities'][0]['label'] = 'Tampered'
    with pytest.raises(ValueError, match='checksum'):
        validate_identity_registry(curated)
    path = tmp_path / 'identities.json'
    path.write_text('{"version":1,"version":1}')
    with pytest.raises(ValueError, match='duplicate'):
        load_identity_registry(path)


def test_missing_revision_or_conflicting_entry_context_is_ambiguous_not_active():
    source = entry()
    curated = registry([source])
    for altered in [copy.deepcopy(source), copy.deepcopy(source)]:
        if altered['platform'] == 'windows':
            altered['platform'] = 'linux'
        data = build_identities([altered], curated)
        assert data['entities'][0]['members'][0]['status'] == 'ambiguous'
        assert not data['entry_index']
    source['source_data']['LOLBAS'].pop('upstream_version')
    assert build_identities([source], curated)['entities'][0]['members'][0]['status'] == 'ambiguous'


def alias_record(old='lolbas/alpha/execute/0', targets=None, paths=None):
    raw = ('id: ' + old + '\n').encode()
    return {'id': 'alias:alpha:d2', 'old_entry_id': old, 'new_entry_ids': targets or ['lolbas/new'],
            'source': 'LOLBAS', 'kind': 'd2_lolbas_identity_change', 'review_revision': REVISION,
            'source_files': paths or ['OSBinaries/Alpha.yml'],
            'provenance': {'type': 'adapter', 'source': 'LOLBAS', 'curator': 'agent', 'note': 'Offline explicit historical source-ID mapping.'},
            'confidence': {'level': 'high'},
            'historical_evidence': {'repository_commit': REVISION, 'repository_path': 'data/entries/windows/alpha.yaml',
                'blob_sha1': hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest(),
                'sha256': 'sha256:' + hashlib.sha256(raw).hexdigest(), 'document_utf8': raw.decode()}}


def test_source_aliases_require_exact_d2_evidence_and_do_not_inherit_missing_membership():
    from phase5.publication_identities import lolbas_entry_id
    target = lolbas_entry_id('OSBinaries/Alpha.yml', 'Execute', 0)
    current = entry(target)
    current['source_data']['LOLBAS']['raw'].update(source_file='OSBinaries/Alpha.yml', category='Execute', command_source_index=0)
    old = 'lolbas/alpha/execute/0'
    absent_claim = claim(current)
    absent_claim['entry_id'] = old
    alias = alias_record(old, [target])
    curated = registry([current], claims=[absent_claim], aliases=[alias])
    data = build_identities([current], curated)
    assert data['aliases'][0]['status'] == 'active'
    assert data['aliases'][0]['provenance']['curator'] == 'agent'
    assert data['entities'][0]['members'][0]['status'] == 'missing'
    assert not data['entry_index']
    broken = copy.deepcopy(alias)
    broken['new_entry_ids'] = ['lolbas/not-present']
    with pytest.raises(ValueError, match='dangling'):
        build_identities([current], registry([current], claims=[], aliases=[broken]))
    forged = alias_record('lolbas/not-alpha/execute/0', [target])
    with pytest.raises(ValueError, match='D2 evidence'):
        build_identities([current], registry([current], claims=[], aliases=[forged]))


def test_alias_cycles_chains_and_competing_targets_are_rejected():
    alias = alias_record('lolbas/old', ['lolbas/new'])
    chain = alias_record('lolbas/new', ['lolbas/newer'])
    chain['id'] = 'alias:alpha:two'
    with pytest.raises(ValueError, match='chains/cycles'):
        registry(claims=[], aliases=[alias, chain])
    competing = {**copy.deepcopy(alias), 'id': 'alias:alpha:two', 'new_entry_ids': ['lolbas/other']}
    with pytest.raises(ValueError, match='conflicting'):
        registry(claims=[], aliases=[alias, competing])


def test_alias_historical_bytes_and_old_id_are_required():
    alias = alias_record()
    alias['historical_evidence']['document_utf8'] += 'tampered: true\n'
    with pytest.raises(ValueError, match='digest'):
        registry(claims=[], aliases=[alias])
    alias = alias_record()
    alias['old_entry_id'] = 'lolbas/different'
    with pytest.raises(ValueError, match='old ID'):
        registry(claims=[], aliases=[alias])


def test_explicit_ambiguous_historical_alias_preserves_all_split_targets():
    from phase5.publication_identities import lolbas_entry_id
    paths = ['OSBinaries/Alpha.yml', 'OtherMSBinaries/Alpha.yml']
    currents = []
    for path in paths:
        row = entry(lolbas_entry_id(path, 'Execute', 0))
        row['source_data']['LOLBAS']['raw'].update(source_file=path, category='Execute', command_source_index=0)
        currents.append(row)
    alias = alias_record(targets=[row['id'] for row in currents], paths=paths)
    data = build_identities(currents, registry(claims=[], aliases=[alias]))
    assert data['aliases'][0]['status'] == 'split'
    assert data['aliases'][0]['new_entry_ids'] == sorted(row['id'] for row in currents)
    assert not data['entry_index']


def test_duplicate_native_name_never_becomes_high_confidence_membership():
    source = entry()
    source['source_data']['LOLBAS']['raw']['document'] = 'Name: Beta.exe\n' + source['source_data']['LOLBAS']['raw']['document']
    assert build_identities([source], registry([source]))['entities'][0]['members'][0]['status'] == 'ambiguous'
