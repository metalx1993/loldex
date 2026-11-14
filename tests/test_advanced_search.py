"""Execute the browser search engine's shared conformance vectors in Node."""
from pathlib import Path
import subprocess


def test_advanced_search_conformance():
    root = Path(__file__).resolve().parent.parent
    subprocess.run(['node', str(root / 'tests/test_advanced_search.cjs')], cwd=root,
                   check=True, capture_output=True, text=True)
