"""Independent regressions for adversarial source expansion and private quotas."""
from pathlib import Path
import subprocess

import pytest
from adapters import complete_data as detail


def test_tiny_alias_dag_cannot_expand_into_unbounded_json():
    leaf = ['tiny']
    for _ in range(25):
        leaf = [leaf, leaf]
    with pytest.raises(detail.SourceDataError) as caught:
        detail.json_detail({'root': leaf})
    assert caught.value.code == 'SOURCE_DETAIL_LIMIT'


def test_yaml_merge_aliases_are_bounded_before_construction():
    raw = ['v0: &v0 {original: value}']
    for index in range(1, 20):
        raw.append(f'v{index}: &v{index} {{<<: [*v{index-1}, *v{index-1}]}}')
    with pytest.raises(detail.SourceDataError) as caught:
        detail.parse_document('\n'.join(raw))
    assert caught.value.code == 'SOURCE_DETAIL_LIMIT'



@pytest.mark.parametrize("raw", ["value: !!int " + "7" * 4097, "value: 0x" + "F" * 4097])
def test_large_integer_spelling_is_rejected_before_conversion(raw):
    with pytest.raises(detail.SourceDataError) as caught:
        detail.parse_document(raw)
    assert caught.value.code == 'SOURCE_DETAIL_LIMIT'


def test_direct_large_integer_is_rejected_without_decimal_expansion():
    with pytest.raises(detail.SourceDataError) as caught:
        detail.json_detail({'value': 1 << 16384})
    assert caught.value.code == 'SOURCE_DETAIL_LIMIT'

def test_normal_alias_multiplicity_and_reserved_mapping_are_preserved():
    document = detail.parse_document('source: &value [one, two]\nrepeated: [*value, *value]\nreserved: {$yaml_type: literal}\n')
    converted = detail.json_detail(document)
    assert converted['repeated'] == [['one', 'two'], ['one', 'two']]
    assert converted['reserved'] == {'$yaml_type': 'mapping', 'entries': [['$yaml_type', 'literal']]}
    document['source'].append('three')
    assert converted['repeated'][0] == ['one', 'two']


def test_independent_guard_negative_cases():
    root = Path(__file__).resolve().parent.parent
    result = subprocess.run(['node', str(root / 'tests/test_security_adversarial.cjs')],
                            cwd=root, capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, result.stdout + result.stderr
