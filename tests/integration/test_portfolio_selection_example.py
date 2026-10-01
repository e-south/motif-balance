"""The portfolio reference selects from the real tutorial's retained search pool."""

import re
import subprocess
import sys
from pathlib import Path

from motif_balance import design
from motif_balance.formats.design import load_design_spec


def test_portfolio_reference_continues_from_the_real_saved_design(tmp_path, argr_cra_example):
    design(load_design_spec(argr_cra_example / "design.yaml")).write(tmp_path / "result")
    guide = Path(__file__).resolve().parents[2] / "docs/reference/portfolio-selection.md"
    blocks = re.findall(r"```python\n(.*?)```", guide.read_text(), flags=re.DOTALL)
    assert len(blocks) == 1
    checks = """
assert saved.spec.length == 25
assert {s.motif.motif_id for s in saved.spec.specifications} == {"ArgR", "Cra"}
assert pool == tuple(item.sequence for item in saved.manifest.elites)
assert policy.min_distance == 0.05
assert policy.equivalence == "reverse_complement"
assert result.spec == saved.spec
assert result.search_evaluations == 0
assert result.status == "optimal" and result.delivered_count == 2
assert [round(m.evaluation.balance_score, 3) for m in result.members] == [0.855, 0.801]
assert result.minimum_separation == 0.52
assert verify_portfolio_selection(result, pool) == result
"""
    run = subprocess.run(
        [sys.executable, "-c", "\n".join([blocks[0], checks])],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stderr
    assert run.stdout.splitlines() == [
        "optimal: 2 candidates, weakest balance 0.801",
        "Minimum footprint separation: 0.520",
    ]
    assert {p.name for p in tmp_path.iterdir()} == {"result"}
