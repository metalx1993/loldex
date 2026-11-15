"""Independent negative retained-release bridge integration."""
from pathlib import Path
import subprocess


def test_retained_release_adversarial_bridge():
    root = Path(__file__).resolve().parent.parent
    result = subprocess.run(['node', str(root / 'tests/test_retained_adversarial.cjs')],
                            cwd=root, capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, result.stdout + result.stderr
