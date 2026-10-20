"""Demo replay test: exercises the full message-processing flow against
sample_data/events.json and diffs responses against expected_outputs.json."""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.demo
def test_demo_replay_matches_expected_outputs():
    """Run scripts/demo.py and assert all demo checks pass."""
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "demo.py")],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    # Print demo output for visibility in CI logs
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    assert result.returncode == 0, "Demo replay found mismatches vs expected outputs"