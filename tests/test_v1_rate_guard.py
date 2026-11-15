"""Public V1 wrapper preserves its contract under anti-abuse responses."""
from pathlib import Path
import subprocess


def test_v1_rate_guard():
    root = Path(__file__).resolve().parent.parent
    result = subprocess.run(["node", str(root / "tests/test_v1_rate_guard.cjs")],
                            cwd=root, capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, result.stdout + result.stderr
