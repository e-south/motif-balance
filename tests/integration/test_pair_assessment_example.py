"""The assessment guide is executable from an empty caller directory."""

import re
import shlex
import subprocess
import sys
from pathlib import Path


def test_pair_assessment_guide_runs_without_search_or_checkout_inputs(tmp_path):
    root = Path(__file__).resolve().parents[2]
    guide = (root / "docs/pair-assessment.md").read_text()
    blocks = re.findall(r"```python\n(.*?)```", guide, flags=re.DOTALL)
    assert len(blocks) == 1
    completed = subprocess.run(
        [sys.executable, "-c", blocks[0]], cwd=tmp_path, capture_output=True, text=True
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.splitlines() == [
        "3 nt: structural score 0.500; 2 relative arrangements",
        "4 nt: structural score 0.667; 6 relative arrangements",
        "5 nt: structural score 0.833; 10 relative arrangements",
        "6 nt: structural score 1.000; 14 relative arrangements",
        "Best at 6 nt: left 0 +; right 3 +",
        "Sequence evaluations: 0",
    ]
    assert not list(tmp_path.iterdir())


def test_pair_assessment_cli_guide_from_a_caller_directory(tmp_path):
    root = Path(__file__).resolve().parents[2]
    guide = (root / "docs/pair-assessment.md").read_text()
    blocks = re.findall(r"```bash\n(.*?)```", guide, flags=re.DOTALL)
    assert len(blocks) == 1
    arguments = shlex.split(blocks[0].replace("\\\n", ""))
    assert arguments[:4] == ["uv", "run", "motif-balance", "assess"]
    arguments = [str(root / arg) if arg.startswith("examples/") else arg for arg in arguments[3:]]
    completed = subprocess.run(
        [sys.executable, "-m", "motif_balance.cli", *arguments],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "Structural score: 1" in completed.stdout
    assert "left start=0 strand=+; right start=0 strand=-" in completed.stdout
    assert "Sequence evaluations: 0" in completed.stdout
    assert not list(tmp_path.iterdir())
