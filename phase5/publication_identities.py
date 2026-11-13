"""D2 opt-in publication identities for LOLBAS and explicit LOLAD row equivalence.

These functions do not change CORE's D1 observation or transition contracts.
Publication normalizers invoke them only for the explicit publication-v2 profile.
"""
from __future__ import annotations

import base64
from collections import Counter
import copy
import hashlib
import json
import re

import yaml

from .canonical import canonical_bytes, nfc
from .input_ref import canonical_input_ref, ROW

PROFILE = 'publication-v2'
LOLBAS_FOLDERS = {'OSBinaries', 'OSLibraries', 'OSScripts', 'OtherMSBinaries'}


class PublicationIdentityError(ValueError):
    def __init__(self, code, message, *, diagnostics=()):
        super().__init__(message)
        self.code = code
        self.diagnostics = list(diagnostics)


def _encode(value):
    if not isinstance(value, str):
        raise PublicationIdentityError('MALFORMED_RECORD', 'identity component must be a string')
    try:
        return base64.urlsafe_b64encode(nfc(value).encode('utf-8')).rstrip(b'=').decode('ascii')
    except UnicodeError as exc:
        raise PublicationIdentityError('MALFORMED_RECORD', 'identity contains an invalid Unicode scalar') from exc


def lolbas_entry_id(path, category, command_source_index):
    if not isinstance(path, str) or '\\' in path or any(ord(c) < 32 for c in path):
        raise PublicationIdentityError('MALFORMED_RECORD', 'invalid LOLBAS source-relative path')
    parts = path.split('/')
    if len(parts) != 2 or parts[0] not in LOLBAS_FOLDERS or not parts[1].endswith('.yml') or parts[1] in {'.', '..'}:
        raise PublicationIdentityError('MALFORMED_RECORD', 'LOLBAS identity requires a selected source file path')
    if type(command_source_index) is not int or command_source_index < 0 or not isinstance(category, str):
        raise PublicationIdentityError('MALFORMED_RECORD', 'invalid LOLBAS command source index/category')
    return 'lolbas/' + _encode(path) + '/' + _encode(category.strip()) + '/' + str(command_source_index)


def lolad_entry_id(cells):
    if not isinstance(cells, (list, tuple)) or len(cells) < 3:
        raise PublicationIdentityError('MALFORMED_RECORD', 'LOLAD identity requires three source cells')
    return 'lolad/' + '/'.join(_encode(value) for value in cells[:3])


def _row_cells(row):
    cells = re.findall(r'<td\b[^>]*>(.*?)</td\s*>', row, re.S | re.I)
    return [re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', value)).strip() for value in cells]


def lolad_logical_rows(html):
    """Group only exactly equal complete normalized cell arrays, preserving raw rows.

    A group's canonical locator is its lexicographically first physical input_ref;
    this locator is not its identity and selects no behavioral winner. Every member
    contributes its full original UTF-8 row and locator to source evidence.
    """
    if not isinstance(html, str):
        raise PublicationIdentityError('INVALID_ENCODING', 'LOLAD HTML must be decoded UTF-8')
    try:
        html.encode('utf-8', 'strict')
    except UnicodeError as exc:
        raise PublicationIdentityError('INVALID_ENCODING', 'LOLAD HTML contains invalid Unicode') from exc
    table_count = len(re.findall(r'<table\b', html, re.I))
    tables = re.findall(r'<table\b[^>]*>.*?</table\s*>', html, re.S | re.I)
    if table_count != 1 or len(tables) != 1:
        code = 'EMPTY_INPUT_SET' if table_count == 0 else 'MALFORMED_RECORD'
        raise PublicationIdentityError(code, 'LOLAD publication requires exactly one complete table')
    table = tables[0]
    starts = list(re.finditer(r'<tr\b[^>]*>', table, re.I))
    groups, physical = {}, 0
    all_occurrences = []
    for position, start in enumerate(starts):
        row_slice = table[start.start():starts[position + 1].start() if position + 1 < len(starts) else len(table)]
        if re.search(r'<th\b', row_slice, re.I):
            continue
        closing = re.search(r'</tr\s*>', row_slice, re.I)
        if closing is None:
            raise PublicationIdentityError('MALFORMED_RECORD', 'LOLAD row is not closed')
        # Retain exactly the physical row bytes, not the following table markup.
        row = row_slice[:closing.end()]
        cells = _row_cells(row)
        if position == 0 and len(cells) >= 2 and cells[0].lower() in {'technique', 'technique/command name', 'technique/command', 'technique name'} and cells[1].lower() == 'command':
            continue
        if len(cells) >= 2 and not cells[1]:
            continue
        ref = canonical_input_ref('LOLAD', 'index.html', ROW(physical))
        physical += 1
        if len(cells) < 3:
            raise PublicationIdentityError('MALFORMED_RECORD', 'LOLAD row requires at least three cells')
        if not cells[0]:
            raise PublicationIdentityError('MISSING_REQUIRED_FIELD', 'LOLAD row has no name')
        normalized = [nfc(value) for value in cells]
        key = canonical_bytes(normalized)
        row_bytes = row.encode('utf-8')
        occurrence = {'input_ref': ref, 'row_utf8': row,
                      'row_sha256': 'sha256:' + hashlib.sha256(row_bytes).hexdigest(),
                      'cells': cells}
        all_occurrences.append(copy.deepcopy(occurrence))
        if key not in groups:
            groups[key] = {'cells': normalized, 'occurrences': [], 'entry_id': lolad_entry_id(normalized)}
        groups[key]['occurrences'].append(occurrence)
    rows = sorted(groups.values(), key=lambda row: row['entry_id'])
    identities = Counter(row['entry_id'] for row in rows)
    collisions = [eid for eid, count in identities.items() if count > 1]
    if collisions:
        diagnostics = [{'code': 'DUPLICATE_ID', 'entry_id': eid} for eid in sorted(collisions)]
        raise PublicationIdentityError('DUPLICATE_ID', 'non-equivalent LOLAD source rows share one identity', diagnostics=diagnostics)
    for row in rows:
        row['occurrences'].sort(key=lambda occurrence: occurrence['input_ref'])
    if not rows:
        raise PublicationIdentityError('EMPTY_INPUT_SET', 'LOLAD publication has no logical records')
    return rows, {'physical_inputs': physical, 'logical_inputs': len(rows),
                  'coalesced_inputs': physical - len(rows), 'diagnostics': [],
                  'source_occurrences': sorted(all_occurrences, key=lambda item: item['input_ref'])}


def lolbas_path(folder, path):
    return str(folder) + '/' + path.name


def publication_entry_evidence_hash(entry):
    """Bind source evidence and per-claim meaning without build clock fields."""
    data = entry.to_dict() if hasattr(entry, 'to_dict') else entry
    source_data = {project: {key: copy.deepcopy(value) for key, value in block.items() if key != 'last_synced'}
                   for project, block in data['source_data'].items()}
    payload = {'id': data['id'], 'source_data': source_data,
               'enrichment': copy.deepcopy(data['enrichment'])}
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def _expected_entry(source, candidate, material, revision, eid, raw, upstream_url):
    from .observation import _layered_projection
    entry = _layered_projection(source, candidate, material, revision)
    entry['id'] = eid
    entry['source_data'][source]['raw'] = copy.deepcopy(raw)
    entry['source_data'][source]['upstream_url'] = upstream_url
    if source == 'LOLAD':
        # This is the reviewed public-adapter rationale, not a new confidence rule.
        for values in entry['enrichment'].values():
            for claim in values if isinstance(values, list) else [values]:
                if claim['provenance']['type'] == 'heuristic':
                    claim['provenance']['note'] = 'classified heuristically from technique name/command'
    return entry


def _raw_lolbas(relative, raw_text, data, command, index):
    return {'name': data.get('Name'),
            'category': command.get('Category'),
            'privileges': command.get('Privileges'),
            'mitre_id': command.get('MitreID'),
            'source_file': relative, 'command_source_index': index,
            'document_utf8': raw_text,
            'document_sha256': 'sha256:' + hashlib.sha256(raw_text.encode('utf-8')).hexdigest()}


def _raw_lolad(row):
    cells, occurrences = row['cells'], row['occurrences']
    return {'name': cells[0], 'command': cells[1], 'type': cells[2],
            'reference': cells[3] if len(cells) > 3 else '',
            'physical_rows': copy.deepcopy(occurrences),
            'physical_occurrence_count': len(occurrences)}


def _lolbas_preflight(raw):
    # Delayed import avoids an adapter -> helper -> adapter import cycle.
    from adapters.lolbas import CATEGORY_MAP, FOLDER_MAP, slug
    from .observation import Candidate, _lolbas
    from .material import material_fingerprint
    revision = raw.get('rev')
    if not isinstance(revision, str) or not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise PublicationIdentityError('MALFORMED_RECORD', 'publication requires a full verified source revision')
    files = raw.get('files')
    if not isinstance(files, list) or not files:
        raise PublicationIdentityError('EMPTY_INPUT_SET', 'LOLBAS publication requires selected documents')
    ids, paths, occurrences, changes = set(), set(), [], []
    expected, evidence_hashes = {}, {}
    for folder, path in files:
        relative = lolbas_path(folder, path)
        lolbas_entry_id(relative, '', 0)  # Validate discovery path even for a zero-command document.
        if nfc(relative) in paths:
            raise PublicationIdentityError('NORMALIZED_PATH_COLLISION', 'LOLBAS source paths collide after NFC')
        paths.add(nfc(relative))
        try:
            raw_text = path.read_text(encoding='utf-8', errors='strict')
            data = yaml.safe_load(raw_text)
        except UnicodeError as exc:
            raise PublicationIdentityError('INVALID_ENCODING', 'LOLBAS document is not UTF-8') from exc
        except yaml.YAMLError as exc:
            raise PublicationIdentityError('PARSE_ERROR', 'LOLBAS document cannot be parsed') from exc
        if not isinstance(data, dict):
            raise PublicationIdentityError('NON_DICT_DOCUMENT', 'LOLBAS source document must be a mapping')
        commands = data.get('Commands')
        if not isinstance(commands, list):
            raise PublicationIdentityError('MISSING_REQUIRED_FIELD', 'LOLBAS document requires a Commands array')
        if data.get('Name') is not None and not isinstance(data['Name'], str):
            raise PublicationIdentityError('MALFORMED_RECORD', 'LOLBAS Name must be a string')
        detections = data.get('Detection')
        if detections is None:
            detections = []
        if not isinstance(detections, list) or any(not isinstance(item, dict) for item in detections):
            raise PublicationIdentityError('MALFORMED_RECORD', 'LOLBAS Detection must be an array of mappings')
        for detection in detections:
            if any(detection.get(key) is not None and not isinstance(detection[key], str) for key in ('IOC', 'Sigma', 'Elastic', 'Splunk')):
                raise PublicationIdentityError('MALFORMED_RECORD', 'LOLBAS detection fields must be source strings')
        for index, command in enumerate(commands):
            if not isinstance(command, dict):
                raise PublicationIdentityError('MALFORMED_RECORD', 'LOLBAS Commands element must be a mapping')
            if any(command.get(key) is not None and not isinstance(command[key], str) for key in ('Category', 'Command', 'Privileges', 'MitreID', 'Description')):
                raise PublicationIdentityError('MALFORMED_RECORD', 'LOLBAS command fields must be source strings')
            category = (command.get('Category') or '').strip()
            if category not in CATEGORY_MAP:
                raise PublicationIdentityError('UNKNOWN_CATEGORY', 'LOLBAS publication requires a mapped category', diagnostics=[{'input_ref': canonical_input_ref('LOLBAS', relative), 'code': 'UNKNOWN_CATEGORY', 'suppressing': True}])
            privilege = command.get('Privileges') or ''
            if privilege and not any(value in privilege.lower() for value in ('system', 'admin', 'user', 'any', 'low', 'sebackup', 'backup operators')):
                raise PublicationIdentityError('UNKNOWN_PRIVILEGE', 'LOLBAS privilege text has no approved mapping', diagnostics=[{'input_ref': canonical_input_ref('LOLBAS', relative), 'code': 'UNKNOWN_PRIVILEGE', 'suppressing': False}])
            if not (command.get('Command') or '').strip():
                raise PublicationIdentityError('MISSING_REQUIRED_FIELD', 'LOLBAS command must not be empty')
            eid = lolbas_entry_id(relative, category, index)
            if eid in ids:
                raise PublicationIdentityError('DUPLICATE_ID', 'LOLBAS qualified identities collide')
            ids.add(eid)
            changes.append({'d1_entry_id': f'lolbas/{slug(path.stem)}/{slug(category)}/{index}',
                            'publication_entry_id': eid, 'source_file': relative,
                            'command_source_index': index})
        candidate = Candidate(canonical_input_ref('LOLBAS', relative), relative, data)
        _lolbas(candidate)
        if len(candidate.entries) != len(commands):
            raise PublicationIdentityError('MALFORMED_RECORD', 'LOLBAS pure derivation omitted a source command')
        for index, (_old_id, material, _identity) in enumerate(candidate.entries):
            category = (commands[index].get('Category') or '').strip()
            eid = lolbas_entry_id(relative, category, index)
            expected[eid] = material_fingerprint(material)
            upstream_url = 'https://lolbas-project.github.io/lolbas/' + FOLDER_MAP[folder][1] + '/' + path.stem + '/'
            complete = _expected_entry('LOLBAS', candidate, material, revision, eid,
                                       _raw_lolbas(relative, raw_text, data, commands[index], index), upstream_url)
            evidence_hashes[eid] = publication_entry_evidence_hash(complete)
        occurrences.append({'input_ref': canonical_input_ref('LOLBAS', relative),
                            'source_file': relative,
                            'document_sha256': 'sha256:' + hashlib.sha256(raw_text.encode('utf-8')).hexdigest(),
                            'command_count': len(commands)})
    return {'physical_inputs': len(files), 'logical_inputs': len(files),
            'coalesced_inputs': 0, 'emitted_entries': len(ids),
            'diagnostics': [], 'source_occurrences': sorted(occurrences, key=lambda value: value['input_ref']),
            'identity_changes': sorted(changes, key=lambda value: value['publication_entry_id']),
            'expected_emissions': dict(sorted(expected.items())),
            'expected_entry_evidence_hashes': dict(sorted(evidence_hashes.items()))}


def publication_preflight(source, raw):
    if raw.get('profile') != PROFILE:
        raise PublicationIdentityError('MALFORMED_RECORD', 'explicit publication-v2 profile is required')
    if source == 'LOLBAS':
        return _lolbas_preflight(raw)
    if source == 'LOLAD':
        from .observation import Candidate, _lolad
        from .material import material_fingerprint
        revision = raw.get('rev')
        rows, audit = lolad_logical_rows(raw.get('html'))
        if not isinstance(revision, str) or not re.fullmatch(r'[0-9a-f]{40}', revision):
            raise PublicationIdentityError('MALFORMED_RECORD', 'publication requires a full verified source revision')
        expected, evidence_hashes = {}, {}
        for row in rows:
            eid = row['entry_id']
            candidate = Candidate(row['occurrences'][0]['input_ref'], 'index.html', row['cells'], ids=[eid])
            _lolad(candidate)
            if len(candidate.entries) != 1:
                raise PublicationIdentityError('MALFORMED_RECORD', 'LOLAD pure derivation omitted a logical row')
            material = candidate.entries[0][1]
            expected[eid] = material_fingerprint(material)
            complete = _expected_entry('LOLAD', candidate, material, revision, eid, _raw_lolad(row),
                                       'https://lolad-project.github.io')
            evidence_hashes[eid] = publication_entry_evidence_hash(complete)
        return {**audit, 'expected_emissions': dict(sorted(expected.items())),
                'expected_entry_evidence_hashes': dict(sorted(evidence_hashes.items()))}
    raise ValueError('identity publication preflight supports only LOLBAS and LOLAD')
