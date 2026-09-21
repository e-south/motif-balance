"""
--------------------------------------------------------------------------------
motif-balance
tests/integration/test_search_observation_example.py

The observation guide is a file-free public caller journey.

Module Author(s): Eric J. South
Dunlop Lab
--------------------------------------------------------------------------------
"""

import re
import subprocess
import sys
from pathlib import Path


def test_observation_reference_from_an_empty_directory(tmp_path):
    guide = Path(__file__).resolve().parents[2] / "docs/reference/search-observations.md"
    blocks = re.findall(r"```python\n(.*?)```", guide.read_text(), flags=re.DOTALL)
    assert len(blocks) == 1
    run = subprocess.run(
        [sys.executable, "-c", blocks[0]], cwd=tmp_path, capture_output=True, text=True
    )
    assert run.returncode == 0, run.stderr
    assert run.stdout.splitlines() == ["127 evaluations; exact incumbent calls: 1, 127"]
    assert not list(tmp_path.iterdir())
