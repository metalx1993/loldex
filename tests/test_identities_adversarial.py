"""Independent Phase9 attacks: byte witnesses, curation scope and index integrity."""
import copy
import hashlib
import json
import unicodedata

import pytest

from knowledge.identities import build_identities, seal_identity_registry, validate_identities
from tests.test_identities import entry, claim, registry, tool


def test_canonical_equivalent_raw_bytes_do_not_silently_refresh_membership():
    original = entry(raw={'document': 'Name: Alpha.exe\nFull_Path:\n- Path: C:\\Windows\\Alpha.exe\nComment: café\n', 'source_file': 'OSBinaries/Alpha.yml'})
    curated = registry([original])
    assert build_identities([original], curated)['entities'][0]['members'][0]['status'] == 'active'
    changed = copy.deepcopy(original)
    changed['source_data']['LOLBAS']['raw']['document'] = unicodedata.normalize('NFD', changed['source_data']['LOLBAS']['raw']['document'])
    assert changed['source_data']['LOLBAS']['raw']['document'] != original['source_data']['LOLBAS']['raw']['document']
    result = build_identities([changed], curated)
    member, = result['entities'][0]['members']
    assert member['status'] == 'witness_changed'
    assert member['evidence'] == curated['claims'][0]['evidence']
    assert result['entry_index'] == {}
    assert result['diagnostics'][0]['code'] == 'IDENTITY_WITNESS_CHANGED'


def test_revision_change_does_not_override_exact_witness_or_rewrite_review_basis():
    document = entry()
    curated = registry([document])
    changed = copy.deepcopy(document)
    changed['source_data']['LOLBAS']['upstream_version'] = 'f' * 40
    result = build_identities([changed], curated)
    member, = result['entities'][0]['members']
    assert member['status'] == 'active'
    assert member['review_revision'] == 'a' * 40
    assert member['current_revision'] == 'f' * 40
    assert member['evidence'] == curated['claims'][0]['evidence']


@pytest.mark.parametrize('field,value', [('confidence', {'level': 'high'}), ('provenance_type', 'manual'), ('confidence', {'level': 'verified'})])
def test_command_association_cannot_be_promoted_by_resealing_curated_registry(field, value):
    document = entry('lolad/operation', platform='active-directory', source='LOLAD', raw={'document': 'alpha.exe /go'})
    association = claim(document, relation='uses_tool', source='LOLAD')
    if field == 'provenance_type':
        association['provenance']['type'] = value
    else:
        association[field] = value
    with pytest.raises(ValueError):
        registry([document], claims=[association])


def test_active_directory_context_is_not_a_windows_runtime_measurement():
    document = entry('lolad/op', platform='active-directory', source='LOLAD', raw={'document': 'alpha.exe /go'})
    association = claim(document, relation='uses_tool', source='LOLAD')
    curated = registry([document], claims=[association])
    result = build_identities([document], curated)
    logical, = result['entities']
    assert logical['platform_scope'] == {'runtime': ['windows'], 'contexts': ['windows', 'active-directory']}
    assert logical['members'][0]['status'] == 'active'
    assert 'runtime' not in logical['members'][0]
    assert document['platform'] == 'active-directory'


def test_recomputed_output_checksum_cannot_launder_a_forged_active_index():
    original = entry()
    curated = registry([original])
    missing = build_identities([], curated)
    forged = copy.deepcopy(missing)
    forged['entry_index'][original['id']] = [{'entity_id': 'tool:alpha', 'claim_id': 'claim:alpha:one', 'relation': 'documents_tool'}]
    forged['entities'][0]['members'][0]['status'] = 'active'
    payload = {key: value for key, value in forged.items() if key != 'checksum'}
    forged['checksum'] = 'sha256:' + hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    with pytest.raises(ValueError):
        validate_identities(forged, [], curated)
    assert missing['entities'][0]['members'][0]['status'] == 'missing'
    assert missing['entities'][0]['members'][0]['evidence'] == curated['claims'][0]['evidence']


def test_command_change_cannot_keep_uses_tool_active_even_with_unchanged_witness():
    document = entry('lolad/op', platform='active-directory', source='LOLAD', raw={'document': 'alpha.exe /go'})
    curated = registry([document], claims=[claim(document, relation='uses_tool', source='LOLAD')])
    document['commands'] = [{'template': 'unrelated.exe /go'}]
    result = build_identities([document], curated)
    assert result['entities'][0]['members'][0]['status'] == 'witness_changed'
    assert not result['entry_index']


def test_same_display_material_does_not_merge_or_mutate_entries_without_curation():
    original = entry()
    other = copy.deepcopy(original)
    other['id'] = 'wadcoms/same-tool'
    other['platform'] = 'active-directory'
    snapshot = copy.deepcopy([original, other])
    first = build_identities([original, other])
    assert first['entities'] == [] and first['entry_index'] == {} and first['candidates'] == []
    assert build_identities([other, original]) == first
    first['diagnostics'].append({'code': 'injected'})
    assert build_identities([original, other])['diagnostics'] == []
    assert [original, other] == snapshot


def test_source_project_cannot_borrow_an_arbitrary_github_repository_as_witness():
    document = entry()
    membership = claim(document)
    membership['evidence'][0]['url'] = 'https://github.com/attacker/unrelated/blob/' + 'a' * 40 + '/record.yml'
    with pytest.raises(ValueError):
        registry([document], claims=[membership])


def test_explicit_document_cannot_claim_a_different_tool_with_resealed_valid_bytes():
    document = entry()
    beta = tool('tool:beta', 'beta.exe')
    beta['label'] = 'Beta'
    beta['identifiers'] = [{'namespace': 'windows-path', 'value': 'C:\\Windows\\Beta.exe'}]
    membership = claim(document, entity_id='tool:beta')
    try:
        curated = registry([document], claims=[membership], entities=[beta])
    except ValueError:
        return  # Rejecting inconsistent declarations before derivation is also fail-closed.
    result = build_identities([document], curated)
    assert not result['entry_index']
    assert result['entities'][0]['members'][0]['status'] != 'active'


def test_proxy_command_and_native_identifier_prefix_do_not_prove_documented_tool():
    document = entry(command='alpha.exe /proxy', raw={
        'name': 'Beta.exe', 'source_file': 'OSBinaries/Alpha.yml',
        'document': 'Name: Beta.exe\nFull_Path:\n- Path: C:\\Windows\\Alpha.exe.evil\nCommand: alpha.exe /proxy\n'})
    membership = claim(document)
    membership['evidence'][0]['required_literals'] = ['Name: Beta.exe', 'C:\\Windows\\Alpha.exe.evil']
    curated = registry([document], claims=[membership])
    result = build_identities([document], curated)
    assert result['entities'][0]['members'][0]['status'] != 'active'
    assert not result['entry_index']


def test_duplicate_native_names_cannot_become_high_documentation_via_yaml_last_wins():
    document = entry()
    document['source_data']['LOLBAS']['raw']['document'] = 'Name: Beta.exe\n' + document['source_data']['LOLBAS']['raw']['document']
    result = build_identities([document], registry([document]))
    assert not result['entry_index']
    assert result['entities'][0]['members'][0]['status'] == 'ambiguous'


def _alias_targets():
    from phase5.publication_identities import lolbas_entry_id
    records = []
    for folder in ['OSBinaries', 'OSScripts']:
        path = folder + '/Alpha.yml'
        current = entry(lolbas_entry_id(path, 'Execute', 0))
        current['source_data']['LOLBAS']['raw'].update(source_file=path, category='Execute', command_source_index=0)
        records.append(current)
    return records


def _historical_document(alias, text):
    raw = text.encode()
    alias['historical_evidence'].update(
        document_utf8=text, sha256='sha256:' + hashlib.sha256(raw).hexdigest(),
        blob_sha1=hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest())


def test_historical_split_keeps_all_targets_without_membership_inheritance_or_dangling_winner():
    from tests.test_identities import alias_record
    records = _alias_targets()
    alias = alias_record(targets=[record['id'] for record in records], paths=['OSBinaries/Alpha.yml', 'OSScripts/Alpha.yml'])
    curated = registry(claims=[], aliases=[alias])
    result = build_identities(records, curated)
    assert result['aliases'][0]['status'] == 'split'
    assert result['aliases'][0]['new_entry_ids'] == sorted(record['id'] for record in records)
    assert not result['entry_index']
    with pytest.raises(ValueError, match='dangling'):
        build_identities(records[:1], curated)


@pytest.mark.parametrize('defect', ['bytes', 'blob', 'sha256', 'old-id', 'duplicate-id'])
def test_historical_alias_bytes_and_old_id_are_checked_even_after_registry_reseal(defect):
    from tests.test_identities import alias_record
    records = _alias_targets()
    alias = alias_record(targets=[records[0]['id']])
    historical = alias['historical_evidence']
    if defect == 'bytes':
        historical['document_utf8'] += '# modified\n'
    elif defect == 'blob':
        historical['blob_sha1'] = 'b' * 40
    elif defect == 'sha256':
        historical['sha256'] = 'sha256:' + 'b' * 64
    elif defect == 'old-id':
        _historical_document(alias, 'id: lolbas/some-other-id\n')
    else:
        _historical_document(alias, 'id: lolbas/other\nid: ' + alias['old_entry_id'] + '\n')
    with pytest.raises(ValueError):
        registry(claims=[], aliases=[alias])


def test_native_historical_material_disambiguates_and_never_selects_a_split_winner():
    from tests.test_identities import alias_record
    records = _alias_targets()
    records[1]['type'] = 'script'
    alias = alias_record(targets=[record['id'] for record in records], paths=['OSBinaries/Alpha.yml', 'OSScripts/Alpha.yml'])
    _historical_document(alias, 'id: ' + alias['old_entry_id'] + '\ntype: binary\n')
    curated = registry(claims=[], aliases=[alias])
    with pytest.raises(ValueError, match='disambiguates'):
        build_identities(records, curated)
