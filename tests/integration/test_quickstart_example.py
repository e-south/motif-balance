"""The public first-design example exercises the current directional contract."""

import re
import subprocess
import sys
from pathlib import Path

import pytest

from motif_balance import design, score
from motif_balance.formats.design import load_design_spec
from motif_balance.inspection import inspect_result


def test_python_tutorial_runs_without_checkout_local_inputs(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    guide = (root / "docs/python-api.md").read_text()
    blocks = re.findall(r"```python\n(.*?)```", guide, flags=re.DOTALL)
    assert len(blocks) == 2

    result = subprocess.run(
        [sys.executable, "-c", "\n".join(blocks)], cwd=tmp_path, capture_output=True, text=True
    )

    assert result.returncode == 0, result.stderr
    assert "AT balance: 0.5" in result.stdout
    assert "Returned 3 of 3" in result.stdout
    for engine in ("annealed_multistart_v1", "greedy_multistart_v1", "uniform_random_v1"):
        assert f"{engine} 127" in result.stdout
    assert (tmp_path / "candidate.svg").read_bytes().startswith(b"<svg")
    review = inspect_result(tmp_path / "result", kind="bundle")
    assert review.portfolio.best_observed_score == 0.5


def test_quickstart_uses_directional_scoring_and_verified_inspection(tmp_path):
    root = Path(__file__).resolve().parents[2]
    spec = load_design_spec(root / "examples/synthetic-pairwise/design.yaml")
    assert spec.schema_version == "design-spec/v3"
    assert [item.direction for item in spec.specifications] == ["seek", "seek"]
    evaluation = score("AT", spec)
    assert evaluation.balance_score == 0.5
    assert [match.spec_satisfaction for match in evaluation.matches] == [0.5, 0.5]
    portfolio = design(spec)
    assert len(portfolio.candidates) == 3
    portfolio.write(tmp_path / "result")
    review = inspect_result(tmp_path / "result", kind="bundle")
    assert [motif.direction for motif in review.problem.motifs] == ["seek", "seek"]
    assert review.portfolio.best_observed_score == 0.5


@pytest.mark.parametrize(
    "example,motifs,count,length,budget",
    [("production-pairwise", 2, 8, 12, 4096), ("synthetic-multimotif", 4, 4, 8, 2048)],
)
def test_bounded_examples_use_current_directional_contract(
    tmp_path, example, motifs, count, length, budget
):
    root = Path(__file__).resolve().parents[2]
    spec = load_design_spec(root / f"examples/{example}/design.yaml")
    assert spec.schema_version == "design-spec/v3"
    assert [item.direction for item in spec.specifications] == ["seek"] * motifs
    portfolio = design(spec)
    assert len(portfolio.candidates) == count
    assert all(len(candidate.sequence) == length for candidate in portfolio.candidates)
    assert portfolio.manifest.evaluation_count == budget
    assert portfolio.manifest.schema_version == "run-manifest/v6"
    assert portfolio.manifest.search_engine == "annealed_multistart_v1"
    assert portfolio.manifest.completion_status == "budget_exhausted"
    portfolio.write(tmp_path / "result")
    review = inspect_result(tmp_path / "result", kind="bundle")
    assert [motif.direction for motif in review.problem.motifs] == ["seek"] * motifs
