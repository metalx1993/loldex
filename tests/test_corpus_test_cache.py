"""The phase2 test cache parses once and never shares mutable test inputs."""
from unittest.mock import patch

from tests import test_phase2 as corpus


def test_corpus_cache_parses_once_per_root_and_isolates_mutations(tmp_path, monkeypatch):
    roots = [tmp_path / 'first', tmp_path / 'second']
    for root in roots:
        entries = root / 'data/entries/windows'
        entries.mkdir(parents=True)
        (entries / 'a.yaml').write_text('id: lolbas/a\nnested: {values: [original]}\n')
        (entries / 'b.yaml').write_text('id: wadcoms/b\nnested: {values: [other]}\n')
    corpus._corpus_entries.cache_clear()
    original = corpus.yaml.safe_load
    try:
        with patch.object(corpus.yaml, 'safe_load', wraps=original) as parser:
            monkeypatch.setattr(corpus, 'ROOT', roots[0])
            first = corpus._entries('lolbas')
            first[0]['nested']['values'].append('mutated')
            first.append({'id': 'forged'})
            assert corpus._entries('lolbas') == [{'id': 'lolbas/a', 'nested': {'values': ['original']}}]
            assert corpus._entries('wadcoms')[0]['id'] == 'wadcoms/b'
            assert corpus._entries('absent') == []
            assert parser.call_count == 2
            monkeypatch.setattr(corpus, 'ROOT', roots[1])
            assert corpus._entries('lolbas')[0]['id'] == 'lolbas/a'
            assert parser.call_count == 4
    finally:
        corpus._corpus_entries.cache_clear()
