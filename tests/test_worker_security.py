"""Exercise historical Worker with adversarial upstream/request mocks offline."""
from pathlib import Path
import subprocess


def test_worker_security():
    root = Path(__file__).resolve().parent.parent
    result = subprocess.run(['node', str(root / 'tests/test_worker_security.cjs')],
                            cwd=root, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
