"""Phase 9: versioned logical tool identities with evidence-preserving membership.

Entry/technique records are never merged. Suggested matches and inactive curation
never become identity membership, and no transitive closure is computed.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import re
import unicodedata

import yaml
from urllib.parse import urlsplit, unquote

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IDENTITY_REGISTRY = ROOT / 'data/identity/registry.json'
PROJECT_REPOS = {'GTFOBins': 'GTFOBins/GTFOBins.github.io', 'LOLBAS': 'LOLBAS-Project/LOLBAS',
                 'LOLDrivers': 'magicsword-io/LOLDrivers', 'LOLAD': 'lolad-project/lolad-project.github.io',
                 'WADComs': 'WADComs/WADComs.github.io'}
PROJECTS = set(PROJECT_REPOS)
CONTEXTS = {'linux', 'windows', 'macos', 'active-directory'}
RUNTIMES = {'linux', 'windows', 'macos'}
_HEX = re.compile(r'sha256:[0-9a-f]{64}\Z')
_REV = re.compile(r'[0-9a-f]{40}\Z')
_ENTITY = re.compile(r'tool:[a-z0-9][a-z0-9-]{1,100}\Z')
_CLAIM = re.compile(r'claim:[a-z0-9][a-z0-9:-]{1,180}\Z')
_ALIAS = re.compile(r'alias:[a-z0-9][a-z0-9:-]{1,180}\Z')


class _StrictLoader(yaml.SafeLoader):
    pass


def _yaml_mapping(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ValueError('duplicate native YAML key')
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _yaml_mapping)


def _native_yaml(text):
    return yaml.load(text, Loader=_StrictLoader)


def _historical(alias):
    witness = alias['historical_evidence']
    required = {'repository_commit', 'repository_path', 'blob_sha1', 'document_utf8', 'sha256'}
    if not isinstance(witness, dict) or set(witness) != required:
        raise ValueError('alias requires historical public YAML evidence')
    for key in ('repository_commit', 'blob_sha1'):
        if not isinstance(witness[key], str) or not _REV.fullmatch(witness[key]):
            raise ValueError('historical Git object must use full SHA1')
    path = witness['repository_path']
    if not isinstance(path, str) or not path.startswith('data/entries/') or not path.endswith('.yaml') or any(part in {'', '.', '..'} for part in path.split('/')) or '\\' in path:
        raise ValueError('invalid historical public entry path')
    raw = _string(witness['document_utf8'], 'historical YAML', nfc=False).encode('utf-8')
    if witness['sha256'] != 'sha256:' + hashlib.sha256(raw).hexdigest() or witness['blob_sha1'] != hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest():
        raise ValueError('historical YAML digest mismatch')
    try:
        old = _native_yaml(raw.decode('utf-8'))
    except (yaml.YAMLError, ValueError, TypeError) as exc:
        raise ValueError('invalid historical YAML') from exc
    if not isinstance(old, dict) or old.get('id') != alias['old_entry_id']:
        raise ValueError('historical public entry does not establish the old ID')
    return old


def _bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def _digest(value):
    return 'sha256:' + hashlib.sha256(_bytes(value)).hexdigest()


def _string(value, field, *, nfc=True):
    if not isinstance(value, str) or not value or any(0xD800 <= ord(c) <= 0xDFFF for c in value):
        raise ValueError(f'{field} must be a non-empty scalar string')
    if nfc and unicodedata.normalize('NFC', value) != value:
        raise ValueError(f'{field} must already be NFC')
    return value


def _entry_id(value):
    value = _string(value, 'entry_id')
    if '/' not in value or value.split('/', 1)[0] not in {'gtfobins', 'lolbas', 'loldrivers', 'lolad', 'wadcoms'}:
        raise ValueError('identity claim must reference a source entry, not an entity/technique node')
    return value


def _unique_strings(values, field, allowed=None):
    if not isinstance(values, list) or not values or any(not isinstance(v, str) for v in values) or len(set(values)) != len(values):
        raise ValueError(f'{field} must be a non-empty unique string array')
    for value in values:
        _string(value, field)
    if allowed is not None and not set(values) <= allowed:
        raise ValueError(f'invalid {field}')


def _provenance(provenance, confidence, relation):
    if not isinstance(provenance, dict) or set(provenance) != {'type', 'source', 'curator', 'note'}:
        raise ValueError('identity provenance requires type, source, curator and explanatory note')
    if provenance['source'] not in PROJECTS or provenance['curator'] not in {'agent', 'human'}:
        raise ValueError('invalid identity source/curator')
    _string(provenance['note'], 'provenance.note')
    if not isinstance(confidence, dict) or set(confidence) != {'level'}:
        raise ValueError('invalid identity confidence')
    if relation == 'documents_tool':
        if provenance['type'] != 'adapter' or confidence['level'] != 'high':
            raise ValueError('explicit document membership requires adapter/high evidence')
    elif relation in {'uses_tool', 'candidate_tool'}:
        if provenance['type'] != 'heuristic' or confidence['level'] != 'low':
            raise ValueError('command-token association remains heuristic/low')
    else:
        raise ValueError('unknown identity relation')
    # Agent curation is never relabeled as a human review or a verified fact.
    if provenance['curator'] == 'agent' and (provenance['type'] == 'manual' or confidence['level'] == 'verified'):
        raise ValueError('agent curation cannot claim human/verified provenance')


def _witness(witness):
    expected = {'source', 'review_revision', 'url', 'pointer', 'sha256', 'required_literals'}
    if not isinstance(witness, dict) or set(witness) != expected:
        raise ValueError('invalid identity witness shape')
    if witness['source'] not in PROJECTS or not isinstance(witness['review_revision'], str) or not _REV.fullmatch(witness['review_revision']):
        raise ValueError('identity witness must pin a full source review revision')
    url = urlsplit(_string(witness['url'], 'witness.url'))
    prefix = '/' + PROJECT_REPOS[witness['source']] + '/blob/' + witness['review_revision'] + '/'
    if url.scheme != 'https' or url.hostname != 'github.com' or url.username or url.password or url.query or not url.path.startswith(prefix):
        raise ValueError('identity witness must link to its canonical source repository and pinned revision')
    try:
        relative = unquote(url.path[len(prefix):], encoding='utf-8', errors='strict')
    except UnicodeError as exc:
        raise ValueError('invalid identity witness URL encoding') from exc
    if any(part in {'', '.', '..'} for part in relative.split('/')) or '\\' in relative or any(ord(c) < 32 for c in relative):
        raise ValueError('identity witness URL requires an exact relative source path')
    if not isinstance(witness['pointer'], str) or not witness['pointer'].startswith('/'):
        raise ValueError('witness pointer must address a raw source string')
    if not isinstance(witness['sha256'], str) or not _HEX.fullmatch(witness['sha256']):
        raise ValueError('identity witness requires a source-byte digest')
    literals = witness['required_literals']
    if not isinstance(literals, list) or not literals:
        raise ValueError('identity witness requires explicit source evidence literals')
    for literal in literals:
        _string(literal, 'witness literal', nfc=False)


def seal_identity_registry(payload):
    """Produce an integrity pin after explicit curation, not an authenticity signature."""
    payload = copy.deepcopy(payload)
    payload.pop('checksum', None)
    registry = {**payload, 'checksum': _digest(payload)}
    validate_identity_registry(registry)
    return registry


def validate_identity_registry(registry):
    if not isinstance(registry, dict) or set(registry) != {'version', 'revision', 'entities', 'claims', 'aliases', 'checksum'}:
        raise ValueError('invalid identity registry shape')
    if type(registry['version']) is not int or registry['version'] != 1 or type(registry['revision']) is not int or registry['revision'] < 1:
        raise ValueError('unsupported identity registry version/revision')
    payload = {key: value for key, value in registry.items() if key != 'checksum'}
    if registry['checksum'] != _digest(payload):
        raise ValueError('identity registry checksum mismatch')
    if any(not isinstance(registry[key], list) for key in ('entities', 'claims', 'aliases')):
        raise ValueError('identity registry sections must be arrays')
    entity_ids, claim_ids, alias_ids = set(), set(), set()
    for entity in registry['entities']:
        required = {'id', 'kind', 'label', 'platform_scope', 'identifiers', 'candidate_tokens', 'scope_note'}
        if not isinstance(entity, dict) or set(entity) != required or not isinstance(entity['id'], str) or not _ENTITY.fullmatch(entity['id']) or entity['id'] in entity_ids or entity['kind'] != 'tool':
            raise ValueError('invalid or duplicate explicit tool identity')
        entity_ids.add(entity['id'])
        _string(entity['label'], 'entity.label')
        _string(entity['scope_note'], 'entity.scope_note')
        scope = entity['platform_scope']
        if not isinstance(scope, dict) or set(scope) != {'runtime', 'contexts'}:
            raise ValueError('runtime scope and entry context must be separate')
        _unique_strings(scope['runtime'], 'runtime platforms', RUNTIMES)
        _unique_strings(scope['contexts'], 'entry contexts', CONTEXTS)
        _unique_strings(entity['candidate_tokens'], 'candidate tokens')
        if any(token != token.lower() or '/' in token or '\\' in token or re.search(r'\s', token) for token in entity['candidate_tokens']):
            raise ValueError('candidate tokens must be explicit lowercase executable tokens')
        if not isinstance(entity['identifiers'], list) or not entity['identifiers']:
            raise ValueError('logical tools need explicit external/native identifiers')
        for identifier in entity['identifiers']:
            if not isinstance(identifier, dict) or set(identifier) != {'namespace', 'value'}:
                raise ValueError('invalid external tool identifier')
            _string(identifier['namespace'], 'identifier.namespace')
            _string(identifier['value'], 'identifier.value')
    documented = {}
    for claim in registry['claims']:
        expected = {'id', 'entity_id', 'entry_id', 'relation', 'entry_context', 'provenance', 'confidence', 'evidence'}
        if not isinstance(claim, dict) or set(claim) != expected or not isinstance(claim['id'], str) or not _CLAIM.fullmatch(claim['id']) or claim['id'] in claim_ids:
            raise ValueError('invalid or duplicate explicit identity claim id')
        claim_ids.add(claim['id'])
        if claim['entity_id'] not in entity_ids or claim['entry_context'] not in CONTEXTS:
            raise ValueError('identity claim has an unknown entity or context')
        _entry_id(claim['entry_id'])
        _provenance(claim['provenance'], claim['confidence'], claim['relation'])
        if not isinstance(claim['evidence'], list) or not claim['evidence']:
            raise ValueError('identity membership requires witnesses')
        for witness in claim['evidence']:
            _witness(witness)
            if witness['source'] != claim['provenance']['source']:
                raise ValueError('witness source differs from membership provenance')
        if len({witness['review_revision'] for witness in claim['evidence']}) != 1:
            raise ValueError('each membership claim requires one explicit source review basis')
        if claim['relation'] == 'documents_tool':
            # A display name alone is never adequate explicit tool documentation.
            literals = [literal for witness in claim['evidence'] for literal in witness['required_literals']]
            if len(literals) < 2 or not any(re.search(r'[A-Za-z]:\\', literal) or 'https://' in literal for literal in literals):
                raise ValueError('tool documentation needs path/project evidence beyond a display name')
            key = claim['entry_id']
            if key in documented and documented[key] != claim['entity_id']:
                raise ValueError('conflicting declared tool identities cannot select a winner')
            documented[key] = claim['entity_id']
    old_ids, targets = set(), set()
    for alias in registry['aliases']:
        required = {'id', 'old_entry_id', 'new_entry_ids', 'source', 'kind', 'review_revision', 'source_files', 'provenance', 'confidence', 'historical_evidence'}
        if not isinstance(alias, dict) or set(alias) != required or not isinstance(alias['id'], str) or not _ALIAS.fullmatch(alias['id']) or alias['id'] in alias_ids:
            raise ValueError('invalid alias registry record')
        alias_ids.add(alias['id'])
        _entry_id(alias['old_entry_id'])
        _unique_strings(alias['new_entry_ids'], 'alias targets')
        for target in alias['new_entry_ids']:
            _entry_id(target)
        if alias['old_entry_id'] in old_ids or alias['old_entry_id'] in alias['new_entry_ids']:
            raise ValueError('conflicting or cyclic source aliases')
        if alias['source'] != 'LOLBAS' or alias['kind'] != 'd2_lolbas_identity_change' or not isinstance(alias['review_revision'], str) or not _REV.fullmatch(alias['review_revision']):
            raise ValueError('only explicitly evidenced D2 LOLBAS source-ID aliases are supported')
        _unique_strings(alias['source_files'], 'alias source files')
        _provenance(alias['provenance'], alias['confidence'], 'documents_tool')
        if alias['provenance']['source'] != alias['source']:
            raise ValueError('alias provenance source mismatch')
        _historical(alias)
        old_ids.add(alias['old_entry_id'])
        targets.update(alias['new_entry_ids'])
    if old_ids & targets:
        raise ValueError('alias chains/cycles are not resolved transitively')


def _json_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate identity registry JSON key')
        result[key] = value
    return result


def load_identity_registry(path=DEFAULT_IDENTITY_REGISTRY):
    registry = json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=_json_pairs)
    validate_identity_registry(registry)
    return registry


def _pointer(raw, pointer):
    value = raw
    for token in pointer.split('/')[1:]:
        if re.search(r'~(?![01])', token):
            raise KeyError('invalid raw evidence pointer')
        token = token.replace('~1', '/').replace('~0', '~')
        if isinstance(value, list):
            if not re.fullmatch(r'0|[1-9][0-9]{0,8}', token):
                raise KeyError('invalid evidence array index')
            value = value[int(token)]
        elif isinstance(value, dict):
            value = value[token]
        else:
            raise KeyError('evidence pointer addresses a scalar')
    return value


def _command_tokens(entry):
    tokens = set()
    for command in entry.get('commands', []):
        if not isinstance(command, dict) or not isinstance(command.get('template'), str):
            continue
        for line in command['template'].splitlines():
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            parts = re.findall(r'"[^"\n]*"|\'[^\'\n]*\'|[^\s]+', line)
            if not parts:
                continue
            token = parts[0].strip('"\'').replace('\\', '/').rsplit('/', 1)[-1].lower()
            if token in {'python', 'python2', 'python3', 'python.exe', 'python2.exe', 'python3.exe'} and len(parts) > 1:
                token = parts[1].strip('"\'').replace('\\', '/').rsplit('/', 1)[-1].lower()
            tokens.add(token)
    return tokens


def _source_path(source, raw):
    if source == 'LOLAD':
        return 'index.html'
    if source == 'LOLBAS':
        path = raw.get('source_file')
        return 'yml/' + path if isinstance(path, str) else None
    key = raw.get('file')
    if not isinstance(key, str):
        return None
    return {'GTFOBins': '_gtfobins/', 'WADComs': '_wadcoms/', 'LOLDrivers': 'yaml/'}[source] + key


def _documented_tool_matches(source, raw, entity):
    # High-confidence documentation is a typed native-metadata rule, never a
    # substring search through a reference or a command that invokes a proxy.
    if source != 'LOLBAS':
        return False
    text = raw.get('document_utf8', raw.get('document'))
    if not isinstance(text, str):
        return False
    try:
        document = _native_yaml(text)
    except (yaml.YAMLError, ValueError, TypeError):
        return False
    if not isinstance(document, dict) or not isinstance(document.get('Name'), str):
        return False
    name = document['Name']
    if name.casefold() not in entity['candidate_tokens']:
        return False
    if raw.get('name') is not None and raw['name'] != name:
        return False
    paths = document.get('Full_Path')
    if not isinstance(paths, list):
        return False
    paths = [item['Path'].casefold() for item in paths if isinstance(item, dict) and isinstance(item.get('Path'), str)]
    identifiers = [identifier['value'].casefold() for identifier in entity['identifiers']
                   if identifier['namespace'] in {'windows-full-path', 'windows-path'}]
    return bool(set(paths) & set(identifiers))


def _member(claim, entity, entry):
    output = copy.deepcopy(claim)
    output.pop('entry_context')
    output['review_revision'] = claim['evidence'][0]['review_revision']
    source = claim['provenance']['source']
    output['current_revision'] = entry.get('source_data', {}).get(source, {}).get('upstream_version') if entry else None
    status = 'active'
    if entry is None:
        status = 'missing'
    elif not isinstance(output['current_revision'], str) or not _REV.fullmatch(output['current_revision']):
        status = 'ambiguous'
    elif entry.get('platform') != claim['entry_context'] or entry.get('platform') not in entity['platform_scope']['contexts']:
        status = 'ambiguous'
    else:
        source_raw = entry['source_data'][source].get('raw', {})
        native_path = _source_path(source, source_raw)
        checked_text = []
        for witness in claim['evidence']:
            if native_path is None or unquote(urlsplit(witness['url']).path.split('/blob/' + witness['review_revision'] + '/', 1)[1]) != native_path:
                status = 'ambiguous'
                break
            try:
                text = _pointer(entry['source_data'][source]['raw'], witness['pointer'])
            except (KeyError, IndexError, TypeError):
                status = 'witness_changed'
                break
            if not isinstance(text, str) or 'sha256:' + hashlib.sha256(text.encode('utf-8')).hexdigest() != witness['sha256'] or any(literal not in text for literal in witness['required_literals']):
                status = 'witness_changed'
                break
            checked_text.append(text)
        if status == 'active' and claim['relation'] == 'documents_tool':
            if not _documented_tool_matches(source, source_raw, entity):
                status = 'ambiguous'
        if status == 'active' and claim['relation'] == 'uses_tool' and not _command_tokens(entry) & set(entity['candidate_tokens']):
            status = 'witness_changed'
    output['status'] = status
    return output


def _aliases(records, entries):
    if not records:
        return []
    from phase5.publication_identities import lolbas_entry_id
    from adapters.lolbas import slug
    result = []
    for record in sorted(records, key=lambda alias: alias['id']):
        if record['old_entry_id'] in entries:
            raise ValueError('source alias conflicts with an existing current entry')
        old_document = _historical(record)
        source_files = set()
        for target in record['new_entry_ids']:
            if target not in entries:
                raise ValueError('source alias target is dangling')
            raw = entries[target].get('source_data', {}).get('LOLBAS', {}).get('raw', {})
            path, category, index = raw.get('source_file'), raw.get('category'), raw.get('command_source_index')
            if not isinstance(path, str) or not isinstance(category, str) or type(index) is not int:
                raise ValueError('alias target lacks D2 source identity evidence')
            old = 'lolbas/' + slug(Path(path).stem) + '/' + slug(category.strip()) + '/' + str(index)
            if old != record['old_entry_id'] or lolbas_entry_id(path, category, index) != target:
                raise ValueError('source-ID alias is not established by D2 evidence')
            current = entries[target]
            for field in ('name', 'type', 'commands'):
                if field in old_document and old_document[field] != current.get(field):
                    raise ValueError('historical public evidence disambiguates a different target')
            source_files.add(path)
        if source_files != set(record['source_files']):
            raise ValueError('alias source-file evidence differs from the targets')
        result.append({**copy.deepcopy(record), 'status': 'split' if len(record['new_entry_ids']) > 1 else 'active',
                       'new_entry_ids': sorted(record['new_entry_ids']),
                       'note': 'Direct evidenced source-ID mapping only; membership is never inherited or redirected.'})
    return result


def build_identities(entries, registry=None):
    """Pure identity view; None means no curation, never an implicit filesystem read."""
    if registry is not None:
        validate_identity_registry(registry)
    indexed = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError('identity inputs must be entry objects')
        eid = _entry_id(entry.get('id'))
        if eid in indexed:
            raise ValueError('duplicate identity input entry ID')
        if entry.get('platform') not in CONTEXTS or not isinstance(entry.get('source_data', {}), dict):
            raise ValueError('invalid identity entry context/source_data')
        indexed[eid] = entry
    entities, candidates, diagnostics, entry_index = [], [], [], {}
    claims_by_entity = {}
    if registry:
        for claim in registry['claims']:
            claims_by_entity.setdefault(claim['entity_id'], []).append(claim)
        for declaration in sorted(registry['entities'], key=lambda entity: entity['id']):
            entity = {key: copy.deepcopy(value) for key, value in declaration.items() if key != 'candidate_tokens'}
            members = []
            curated_entries = set()
            for claim in sorted(claims_by_entity.get(entity['id'], []), key=lambda item: item['id']):
                member = _member(claim, declaration, indexed.get(claim['entry_id']))
                members.append(member)
                curated_entries.add(claim['entry_id'])
                if member['status'] == 'active':
                    entry_index.setdefault(member['entry_id'], []).append({'entity_id': entity['id'], 'claim_id': member['id'], 'relation': member['relation']})
                else:
                    diagnostics.append({'code': 'IDENTITY_' + member['status'].upper(), 'entity_id': entity['id'], 'claim_id': member['id'], 'entry_id': member['entry_id']})
            entity['members'] = members
            entities.append(entity)
            for eid, entry in sorted(indexed.items()):
                if eid in curated_entries:
                    continue
                matched = sorted(_command_tokens(entry) & set(declaration['candidate_tokens']))
                if not matched:
                    continue
                source_projects = sorted(set(entry.get('source_data', {})) & PROJECTS)
                candidate = {
                    'id': 'candidate:' + hashlib.sha256(_bytes([entity['id'], eid])).hexdigest(),
                    'entity_id': entity['id'], 'entry_id': eid, 'relation': 'candidate_tool',
                    'status': 'candidate' if entry['platform'] in entity['platform_scope']['contexts'] else 'ambiguous',
                    'provenance': {'type': 'heuristic', 'source': source_projects[0] if len(source_projects) == 1 else 'ambiguous',
                                   'curator': 'agent', 'note': 'Exact leading command token only; no equivalence, runtime PATH, binary version or execution platform is proved.'},
                    'confidence': {'level': 'low'},
                    'evidence': {'matched_tokens': matched, 'entry_context': entry['platform'],
                                 'sources': source_projects,
                                 'commands': [{'template': command['template'], 'sha256': 'sha256:' + hashlib.sha256(command['template'].encode('utf-8')).hexdigest()} for command in entry.get('commands', []) if isinstance(command, dict) and isinstance(command.get('template'), str)]},
                }
                candidates.append(candidate)
    aliases = _aliases(registry['aliases'], indexed) if registry else []
    for references in entry_index.values():
        references.sort(key=lambda ref: (ref['entity_id'], ref['claim_id'], ref['relation']))
    result = {'version': 1, 'registry_revision': registry['revision'] if registry else None,
              'registry_checksum': registry['checksum'] if registry else None,
              'entities': entities, 'candidates': sorted(candidates, key=lambda value: value['id']),
              'aliases': aliases, 'entry_index': dict(sorted(entry_index.items())),
              'diagnostics': sorted(diagnostics, key=lambda value: (value['entity_id'], value['claim_id'])),
              'stats': {'entities': len(entities), 'active_memberships': sum(len(value) for value in entry_index.values()),
                        'inactive_memberships': len(diagnostics), 'candidates': len(candidates)}}
    return {**result, 'checksum': _digest(result)}


def validate_identities(data, entries, registry=None):
    if _bytes(data) != _bytes(build_identities(entries, registry)):
        raise ValueError('identity view differs from the evidence-preserving registry derivation')
