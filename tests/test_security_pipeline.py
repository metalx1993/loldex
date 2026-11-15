"""Fail closed before legacy acquisition and expanded YAML amplification."""
import datetime
import importlib
from pathlib import Path
import subprocess

import pytest

import adapters.complete_data as complete
from phase5.canonical import canonical_bytes


@pytest.mark.parametrize('module,classname', [
    ('gtfobins', 'GTFOBinsAdapter'), ('lolbas', 'LOLBASAdapter'),
    ('loldrivers', 'LOLDriversAdapter'), ('lolad', 'LOLADAdapter'),
    ('wadcoms', 'WADComsAdapter'),
])
@pytest.mark.parametrize('explicit', [False, True])
def test_legacy_fetch_never_reads_or_executes(tmp_path, monkeypatch, module, classname, explicit):
    def forbidden(*args, **kwargs):
        raise AssertionError('legacy acquisition performed an operation')
    monkeypatch.setattr(subprocess, 'run', forbidden)
    monkeypatch.setattr(Path, 'read_text', forbidden)
    monkeypatch.setattr(Path, 'glob', forbidden)
    adapter = getattr(importlib.import_module('adapters.' + module), classname)(
        **({'clone_dir': tmp_path / 'poisoned'} if explicit else {}))
    with pytest.raises(RuntimeError, match='scripts.verified_refresh'):
        adapter.fetch()


def test_alias_dag_fails_before_json_expansion():
    node = ['leaf']
    for _ in range(22):
        node = [node, node]
    with pytest.raises(complete.SourceDataError) as error:
        complete.json_detail(node)
    assert error.value.code == 'SOURCE_DETAIL_LIMIT'


def test_yaml_merge_amplification_fails_before_construction(monkeypatch):
    source = 'a: &a {value: 1}\n'
    for n in range(1, 18):
        previous = 'a' if n == 1 else 'n' + str(n - 1)
        source += f'n{n}: &n{n} {{<<: [*{previous}, *{previous}]}}\n'
    def forbidden(*args):
        raise AssertionError('expanded YAML constructed before graph budget')
    monkeypatch.setattr(complete.yaml.SafeLoader, 'construct_document', forbidden)
    with pytest.raises(complete.SourceDataError) as error:
        complete.parse_document(source)
    assert error.value.code == 'SOURCE_DETAIL_LIMIT'


@pytest.mark.parametrize('kind', ['list', 'mapping'])
def test_depth_is_bounded(kind):
    node = 'leaf'
    for _ in range(complete.MAX_DETAIL_DEPTH + 1):
        node = [node] if kind == 'list' else {'nested': node}
    with pytest.raises(complete.SourceDataError, match='budget'):
        complete.json_detail(node)


def test_keys_and_shared_scalar_bytes_count(monkeypatch):
    monkeypatch.setattr(complete, 'MAX_DETAIL_BYTES', 2000)
    leaf = 'secret' * 20
    with pytest.raises(complete.SourceDataError, match='budget'):
        complete.json_detail([leaf] * 10)
    with pytest.raises(complete.SourceDataError, match='budget'):
        complete.json_detail({'x' * 500: 1})


def test_width_is_bounded_before_stack_expansion(monkeypatch):
    monkeypatch.setattr(complete, 'MAX_DETAIL_NODES', 5)
    with pytest.raises(complete.SourceDataError, match='budget'):
        complete.json_detail({'a': 1, 'b': 2, 'c': 3})


def test_small_aliases_and_tagged_values_keep_canonical_semantics():
    document = complete.parse_document('a: &a [one, two]\nb: *a\n')
    expected = {'a': ['one', 'two'], 'b': ['one', 'two']}
    assert canonical_bytes(complete.json_detail(document)) == canonical_bytes(expected)
    source = {'$yaml_type': 'float', 'value': '1.0'}
    assert complete.json_detail(source) == {
        '$yaml_type': 'mapping', 'entries': [['$yaml_type', 'float'], ['value', '1.0']]}
    assert complete.json_detail(datetime.date(2026, 11, 15)) == {
        '$yaml_type': 'date', 'value': '2026-11-15'}
    assert complete.json_detail(b'abc') == {'$yaml_type': 'binary', 'value': 'YWJj'}


def test_cyclic_yaml_fails_without_expansion():
    with pytest.raises(complete.SourceDataError, match='cyclic'):
        complete.parse_document('a: &a [*a]\n')


def test_huge_integer_rejected_before_expensive_yaml_constructor(monkeypatch):
    def forbidden(*args):
        raise AssertionError('huge integer parsed before budget')
    monkeypatch.setattr(complete.yaml.SafeLoader, 'construct_document', forbidden)
    with pytest.raises(complete.SourceDataError, match='integer'):
        complete.parse_document('id: !!int ' + '1' * (complete.MAX_YAML_INTEGER_CHARS + 1))
    with pytest.raises(complete.SourceDataError, match='integer'):
        complete.json_detail(1 << complete.MAX_DETAIL_INTEGER_BITS)
