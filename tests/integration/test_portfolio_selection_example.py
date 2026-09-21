"""The current public portfolio example needs no neighboring checkout or files."""

import re
import subprocess
import sys
from pathlib import Path


def test_portfolio_reference_example_from_an_empty_directory(tmp_path):
    guide = Path(__file__).resolve().parents[2] / "docs/reference/portfolio-selection.md"
    blocks = re.findall(r"```python\n(.*?)```", guide.read_text(), flags=re.DOTALL)
    assert len(blocks) == 1
    run = subprocess.run(
        [sys.executable, "-c", blocks[0]], cwd=tmp_path, capture_output=True, text=True
    )
    assert run.returncode == 0, run.stderr
    assert run.stdout.splitlines() == [
        "optimal: 2 candidates, weakest balance 1.000",
        "AACC, CCAA",
        "Minimum footprint separation: 1.000",
    ]
    assert not list(tmp_path.iterdir())
