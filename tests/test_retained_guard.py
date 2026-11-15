"""Stable security enforcement across retained immutable PHP releases."""
from pathlib import Path
import subprocess


def test_retained_guard():
    root = Path(__file__).resolve().parent.parent
    result = subprocess.run(["node", str(root / "tests/test_retained_guard.cjs")],
                            cwd=root, capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, result.stdout + result.stderr
