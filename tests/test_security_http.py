"""Contact and legacy API security contracts with the real PHP/WASM runtime."""
from pathlib import Path
import subprocess


def test_security_http():
    root = Path(__file__).resolve().parent.parent
    result = subprocess.run(["node", str(root / "tests/test_security_http.cjs")],
                            cwd=root, capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, result.stdout + result.stderr
