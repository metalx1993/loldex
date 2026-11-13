"""Explicit D2 publication profile; frozen CORE/D1 observations stay unchanged.

This profile admits only documented source-format extensions after an exhaustive
source-specific preflight. It is never accepted as a CORE transition observation.
"""
from phase5.observation import adapter_result
from phase5.material import material_fingerprint
from phase5.canonical import nfc

PROFILE = 'publication-v2'


def publication_result(bundle, raw, adapter):
    from deployment.source_health import _legacy_raw
    if raw != _legacy_raw(bundle, profile=PROFILE):
        raise ValueError('publication raw input differs from verified bundle')
    baseline = adapter_result(bundle)
    source = bundle.source
    audit = {'physical_inputs': baseline['inputs_total'],
             'logical_inputs': baseline['inputs_total'], 'coalesced_inputs': 0,
             'diagnostics': []}
    allowed_rejections = set()
    allowed_diagnostics = set()
    if source == 'GTFOBins':
        from phase5.adapters.gtfobins import preflight
        audit.update(preflight(raw))
        allowed_rejections = {(ref, 'MALFORMED_RECORD') for ref in audit['alias_refs']}
        allowed_diagnostics = {(ref, 'UNKNOWN_FUNCTION') for ref in audit['supported_function_refs']}
    elif source in ('LOLBAS', 'LOLAD'):
        from phase5.publication_identities import publication_preflight
        audit.update(publication_preflight(source, raw))
        # Full new identities / exact-cell coalescence are checked by preflight.
        allowed_rejections = {(r['input_ref'], 'DUPLICATE_ID') for r in baseline['rejected']}
    elif source in ('LOLDrivers', 'WADComs'):
        audit.update(adapter.publication_preflight(raw))
        # Complete representation replaces precisely the documented D1 subsets.
        allowed_diagnostics = {(r['input_ref'], r['code']) for r in baseline['unmapped']
                               if r['code'] in ('SUBSET_TRUNCATED', 'UNKNOWN_ATTACK_TYPE')}
    rejected = [r for r in baseline['rejected'] if (r['input_ref'], r['code']) not in allowed_rejections]
    unmapped = [r for r in baseline['unmapped'] if (r['input_ref'], r['code']) not in allowed_diagnostics]
    unmapped.extend(audit.get('diagnostics', []))
    if rejected or unmapped:
        return {**baseline, 'publication_profile': PROFILE, 'status': 'failed',
                'rejected': rejected, 'unmapped': unmapped, 'publication_audit': audit, 'baseline_d1_status': baseline['status'], 'baseline_d1_reason': baseline['primary_reason']}, []
    normalizer = getattr(adapter, 'normalize_complete', None) if source in ('LOLDrivers', 'WADComs') else None
    entries = list((normalizer or adapter.normalize)(raw))
    ids = [nfc(entry.id) for entry in entries]
    if len(set(ids)) != len(ids):
        raise ValueError('D2 public identities collide; no winner')
    if not entries:
        raise ValueError('D2 publication source emitted nothing')
    from adapters.complete_data import entry_evidence_hash
    from phase5.canonical import canonical_bytes, digest_over
    from adapters.projection import source_hash
    actual_material = {entry.id: material_fingerprint(entry.to_dict()) for entry in entries}
    if actual_material != audit.get('expected_emissions'):
        raise ValueError('D2 public material or coverage differs from independent preflight')
    if source == 'GTFOBins':
        evidence = {entry.id: {'enrichment_hash': digest_over(canonical_bytes(entry.enrichment)),
                              'source_hash': source_hash(entry.source_data[source]),
                              'upstream_url': entry.source_data[source]['upstream_url']} for entry in entries}
        if evidence != audit.get('expected_evidence'):
            raise ValueError('D2 GTFO claims or raw evidence differ from independent preflight')
    elif source in ('LOLBAS', 'LOLAD'):
        from phase5.publication_identities import publication_entry_evidence_hash
        if {entry.id: publication_entry_evidence_hash(entry) for entry in entries} != audit.get('expected_entry_evidence_hashes'):
            raise ValueError('D2 identity claims or raw evidence differ from independent preflight')
    elif {entry.id: entry_evidence_hash(entry) for entry in entries} != audit.get('expected_evidence'):
        raise ValueError('D2 complete source evidence differs from independent preflight')
    emitted = {entry.id: {'material_fingerprint': material_fingerprint(entry.to_dict()),
                          'owner_evidence': {'source_data_projects': [source], 'declared_sources': [source],
                                             'id_prefix': entry.id.partition('/')[0]},
                          'public_entry_evidence': entry_evidence_hash(entry),
                          'upstream_identity': {'kind': 'publication_v2_source_identity', 'value': entry.id}}
               for entry in entries}
    return {**baseline, 'publication_profile': PROFILE, 'status': 'ok', 'primary_reason': 'NONE',
            'parsed_ok': baseline['inputs_total'], 'rejected': [], 'unmapped': [], 'duplicate_ids': [],
            'emitted_entries': emitted, 'publication_audit': audit,
            'baseline_d1_status': baseline['status'], 'baseline_d1_reason': baseline['primary_reason']}, entries
