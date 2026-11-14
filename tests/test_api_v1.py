"""Run real PHP integration and independent adversarial checks as CI gates."""
from pathlib import Path
import subprocess

import pytest


@pytest.mark.parametrize("script", [
    "test_api_v1.cjs", "test_api_v1_adversarial.cjs", "test_a2_router.cjs", "test_api_v1_corpus.cjs",
])
def test_php_integration(script):
    root = Path(__file__).resolve().parent.parent
    result = subprocess.run(["node", str(root / "tests" / script)], cwd=root,
                            capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, result.stdout + result.stderr
