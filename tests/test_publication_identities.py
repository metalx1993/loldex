"""D2 is explicit: distinct LOLBAS records survive; equivalent LOLAD rows retain all evidence."""
import base64
import copy
import hashlib
from dataclasses import dataclass

import pytest

from adapters.lolbas import LOLBASAdapter
from adapters.lolad import LOLADAdapter
from phase5.acquisition import AcquiredFile, VerifiedBundle
from phase5.observation import adapter_result
from phase5.publication_identities import (lolbas_entry_id, lolad_entry_id,
    lolad_logical_rows, publication_preflight, PublicationIdentityError)


@dataclass(frozen=True)
class MemoryPath:
    relative: str
    text: str

    @property
    def name(self):
        return self.relative.split('/')[-1]

    @property
    def stem(self):
        return self.name.rsplit('.', 1)[0]

    def read_text(self, encoding='utf-8', errors='strict'):
        return self.text


def lolbas_raw():
    a = 'Name: SyncAppvPublishingServer.exe\nCommands:\n- Category: Execute\n  Command: SyncAppvPublishingServer.exe /run\n  Privileges: User\n'
    b = 'Name: Syncappvpublishingserver.vbs\nCommands:\n- Category: Execute\n  Command: Syncappvpublishingserver.vbs /run\n  Privileges: User\n'
    return {'rev': 'a' * 40, 'files': [
        ('OSBinaries', MemoryPath('OSBinaries/Syncappvpublishingserver.yml', a)),
        ('OSScripts', MemoryPath('OSScripts/Syncappvpublishingserver.yml', b))]}


def html(rows):
    return '<table><tr><th>Name</th><th>Command</th><th>Type</th><th>Reference</th></tr>' + ''.join(
        '<tr>' + ''.join('<td>' + value + '</td>' for value in row) + '</tr>' for row in rows) + '</table>'


def test_lolbas_default_legacy_is_unchanged_but_d2_distinguishes_both_records():
    raw = lolbas_raw()
    old = list(LOLBASAdapter().normalize(raw))
    assert old[0].id == old[1].id == 'lolbas/syncappvpublishingserver/execute/0'
    raw['profile'] = 'publication-v2'
    audit = publication_preflight('LOLBAS', raw)
    entries = list(LOLBASAdapter().normalize(raw))
    assert len(entries) == len({entry.id for entry in entries}) == 2
    assert {entry.type for entry in entries} == {'binary', 'script'}
    assert audit['physical_inputs'] == audit['logical_inputs'] == 2
    assert audit['emitted_entries'] == 2
    for entry in entries:
        source = entry.source_data['LOLBAS']['raw']
        assert source['document_sha256'] == 'sha256:' + hashlib.sha256(source['document_utf8'].encode()).hexdigest()
        encoded_path = entry.id.split('/')[1]
        decoded_path = base64.urlsafe_b64decode(encoded_path + '=' * (-len(encoded_path) % 4)).decode()
        assert decoded_path == source['source_file']
        assert source['command_source_index'] == 0


def test_lolbas_qualification_applies_unconditionally_and_is_order_invariant():
    raw = lolbas_raw()
    raw['profile'] = 'publication-v2'
    first = {entry.id: entry.to_dict() for entry in LOLBASAdapter().normalize(raw)}
    raw['files'].reverse()
    second = {entry.id: entry.to_dict() for entry in LOLBASAdapter().normalize(raw)}
    assert first == second
    assert lolbas_entry_id('OSBinaries/a_b.yml', 'Execute', 0) != lolbas_entry_id('OSBinaries/a-b.yml', 'Execute', 0)
    assert lolbas_entry_id('OSBinaries/A.yml', 'Execute', 0) != lolbas_entry_id('OSBinaries/a.yml', 'Execute', 0)


def test_frozen_core_d1_lolbas_collision_policy_remains_reject_all():
    raw = lolbas_raw()
    bundle = VerifiedBundle('LOLBAS', 'a' * 40, 'b' * 40,
                            tuple(AcquiredFile(path.relative, path.text.encode()) for _, path in raw['files']))
    result = adapter_result(bundle)
    assert result['primary_reason'] == 'DUPLICATE_ID'
    assert result['parsed_ok'] == 0 and result['emitted_entries'] == {}


def test_lolad_exact_rows_coalesce_explicitly_without_losing_physical_bytes():
    row = ['Enable RDP', 'reg add RDP', 'CMD', 'Reference']
    source = html([row, row, ['Other', 'different', 'CMD', 'Ref']])
    rows, audit = lolad_logical_rows(source)
    assert audit['physical_inputs'] == 3
    assert audit['logical_inputs'] == 2
    assert audit['coalesced_inputs'] == 1
    group = next(record for record in rows if record['cells'] == row)
    assert len(group['occurrences']) == 2
    assert len({e['input_ref'] for e in group['occurrences']}) == 2
    for occurrence in group['occurrences']:
        assert occurrence['row_utf8'] in source
        assert occurrence['row_sha256'] == 'sha256:' + hashlib.sha256(occurrence['row_utf8'].encode()).hexdigest()
    raw = {'rev': 'a' * 40, 'html': source, 'profile': 'publication-v2'}
    entries = list(LOLADAdapter().normalize(raw))
    entry = next(e for e in entries if e.name == 'Enable RDP')
    assert entry.source_data['LOLAD']['raw']['physical_occurrence_count'] == 2
    assert entry.source_data['LOLAD']['raw']['physical_rows'] == group['occurrences']
    assert entry.id == lolad_entry_id(row)
    assert all(c['confidence']['level'] == 'low' for c in entry.enrichment['capabilities'])


def test_lolad_same_identity_with_distinct_reference_evidence_is_not_coalesced():
    source = html([['Test', 'cmd', 'CMD', 'Reference A'], ['Test', 'cmd', 'CMD', 'Reference B']])
    with pytest.raises(PublicationIdentityError, match='non-equivalent') as error:
        lolad_logical_rows(source)
    assert error.value.code == 'DUPLICATE_ID'
    assert error.value.diagnostics[0]['code'] == 'DUPLICATE_ID'


def test_lolad_identity_does_not_depend_on_physical_row_position():
    a, b = ['A', 'cmd A', 'CMD', 'ref A'], ['B', 'cmd B', 'CMD', 'ref B']
    first, _ = lolad_logical_rows(html([a, a, b]))
    second, _ = lolad_logical_rows(html([b, a, a]))
    assert {r['entry_id'] for r in first} == {r['entry_id'] for r in second}
    assert {tuple(r['cells']): len(r['occurrences']) for r in first} == {tuple(r['cells']): len(r['occurrences']) for r in second}


def test_frozen_d1_lolad_equal_triples_still_reject_all():
    row = ['Test', 'cmd', 'CMD', 'ref']
    bundle = VerifiedBundle('LOLAD', 'a' * 40, 'b' * 40,
                            (AcquiredFile('index.html', html([row, row]).encode()),))
    result = adapter_result(bundle)
    assert result['inputs_total'] == 2 and result['parsed_ok'] == 0
    assert result['primary_reason'] == 'DUPLICATE_ID'
    assert len(result['rejected']) == 2


@pytest.mark.parametrize('source', ['<table><tr><td>broken', '<table></table>', html([['', 'cmd', 'CMD', 'ref']]),
                                    html([['One', 'cmd']]), '<table></table><table></table>'])
def test_lolad_preflight_rejects_bad_records_instead_of_silently_skipping(source):
    with pytest.raises(PublicationIdentityError):
        publication_preflight('LOLAD', {'profile': 'publication-v2', 'html': source})


def test_non_header_technique_prefix_is_not_silently_dropped_by_d2():
    raw = {'rev': 'a' * 40, 'profile': 'publication-v2',
           'html': html([['Technique X', 'cmd', 'CMD', 'ref']])}
    entries = list(LOLADAdapter().normalize(raw))
    assert len(entries) == 1 and entries[0].name == 'Technique X'


def test_lolbas_unknown_category_never_disappears_from_publication_silently():
    raw = lolbas_raw()
    path = MemoryPath('OSBinaries/a.yml', 'Commands:\n- Category: NewUnknown\n  Command: cmd\n')
    raw.update(profile='publication-v2', files=[('OSBinaries', path)])
    with pytest.raises(PublicationIdentityError) as error:
        list(LOLBASAdapter().normalize(raw))
    assert error.value.code == 'UNKNOWN_CATEGORY'
    assert error.value.diagnostics[0]['suppressing'] is True


def test_lolbas_nfc_path_collisions_fail_instead_of_choosing_a_file():
    raw = lolbas_raw()
    content = raw['files'][0][1].text
    raw.update(profile='publication-v2', files=[('OSBinaries', MemoryPath('OSBinaries/cafe\u0301.yml', content)),
                                               ('OSBinaries', MemoryPath('OSBinaries/café.yml', content))])
    with pytest.raises(PublicationIdentityError) as error:
        publication_preflight('LOLBAS', raw)
    assert error.value.code == 'NORMALIZED_PATH_COLLISION'


@pytest.mark.parametrize('field,content', [
    ('detection', 'Detection: {}\nCommands:\n- Category: Execute\n  Command: cmd\n'),
    ('command_shape', 'Commands:\n- not-a-mapping\n'),
    ('name', 'Name: 42\nCommands:\n- Category: Execute\n  Command: cmd\n'),
    ('unknown_privilege', 'Commands:\n- Category: Execute\n  Command: cmd\n  Privileges: ROOT_ONLY\n'),
])
def test_lolbas_preflight_catches_defects_hidden_behind_d1_cross_folder_collision(field, content):
    raw = lolbas_raw()
    bad_path = MemoryPath('OSScripts/Syncappvpublishingserver.yml', content)
    raw.update(profile='publication-v2', files=[raw['files'][0], ('OSScripts', bad_path)])
    with pytest.raises(PublicationIdentityError):
        publication_preflight('LOLBAS', raw)


def test_lolbas_oracle_does_not_call_the_public_normalizer(monkeypatch):
    from phase5.material import material_fingerprint
    from phase5.publication_identities import publication_entry_evidence_hash
    raw = {**lolbas_raw(), 'profile': 'publication-v2'}
    entries = list(LOLBASAdapter().normalize(raw))
    monkeypatch.setattr(LOLBASAdapter, 'normalize', lambda *_: (_ for _ in ()).throw(AssertionError('oracle must be independent')))
    audit = publication_preflight('LOLBAS', raw)
    assert audit['expected_emissions'] == {e.id: material_fingerprint(e.to_dict()) for e in entries}
    assert audit['expected_entry_evidence_hashes'] == {e.id: publication_entry_evidence_hash(e) for e in entries}
    assert len(audit['identity_changes']) == 2
    assert len({row['d1_entry_id'] for row in audit['identity_changes']}) == 1


def test_lolad_oracle_does_not_call_the_public_normalizer(monkeypatch):
    from phase5.material import material_fingerprint
    from phase5.publication_identities import publication_entry_evidence_hash
    raw = {'profile': 'publication-v2', 'rev': 'a' * 40,
           'html': html([['A', 'cmd', 'CMD', 'ref'], ['A', 'cmd', 'CMD', 'ref']])}
    entries = list(LOLADAdapter().normalize(raw))
    monkeypatch.setattr(LOLADAdapter, 'normalize', lambda *_: (_ for _ in ()).throw(AssertionError('oracle must be independent')))
    audit = publication_preflight('LOLAD', raw)
    assert audit['expected_emissions'] == {e.id: material_fingerprint(e.to_dict()) for e in entries}
    assert audit['expected_entry_evidence_hashes'] == {e.id: publication_entry_evidence_hash(e) for e in entries}


def test_evidence_hash_binds_confidence_raw_and_identity_but_excludes_build_clock():
    from phase5.publication_identities import publication_entry_evidence_hash
    entry = next(LOLBASAdapter().normalize({**lolbas_raw(), 'profile': 'publication-v2'}))
    before = publication_entry_evidence_hash(entry)
    entry.source_data['LOLBAS']['last_synced'] = '2099-01-01'
    entry.meta['projected_at'] = '2099-01-01'
    assert publication_entry_evidence_hash(entry) == before
    entry.enrichment['capabilities'][0]['confidence']['level'] = 'verified'
    assert publication_entry_evidence_hash(entry) != before


def test_evidence_hash_does_not_normalize_original_upstream_unicode_bytes():
    from phase5.publication_identities import publication_entry_evidence_hash
    entry = next(LOLBASAdapter().normalize({**lolbas_raw(), 'profile': 'publication-v2'}))
    entry.source_data['LOLBAS']['raw']['document_utf8'] = 'café'
    first = publication_entry_evidence_hash(entry)
    entry.source_data['LOLBAS']['raw']['document_utf8'] = 'cafe\u0301'
    assert publication_entry_evidence_hash(entry) != first


def test_d2_raw_source_values_are_not_display_fallbacks_or_trimmed_interpretations():
    from phase5.publication_identities import publication_entry_evidence_hash
    text = 'Commands:\n- Category: " Execute "\n  Command: cmd\n  Privileges: " User "\n  MitreID: " T1105 "\n'
    raw = {'profile': 'publication-v2', 'rev': 'a' * 40,
           'files': [('OSBinaries', MemoryPath('OSBinaries/fallback.yml', text))]}
    entry = next(LOLBASAdapter().normalize(raw))
    source = entry.source_data['LOLBAS']['raw']
    assert entry.name == 'fallback'
    assert source['name'] is None
    assert source['category'] == ' Execute '
    assert source['privileges'] == ' User '
    assert source['mitre_id'] == ' T1105 '
    assert entry.attack_techniques == ['T1105']
    audit = publication_preflight('LOLBAS', raw)
    assert audit['expected_entry_evidence_hashes'][entry.id] == publication_entry_evidence_hash(entry)
