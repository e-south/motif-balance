"""
--------------------------------------------------------------------------------
motif-balance
tests/integration/test_quickstart_example.py

The public first-design example exercises the current directional contract.

Module Author(s): Eric J. South
Dunlop Lab
--------------------------------------------------------------------------------
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from motif_balance import design, score
from motif_balance.formats.design import load_design_spec
from motif_balance.inspection import inspect_result
from motif_balance.variants import load_library


def test_python_tutorial_runs_with_prepared_source_attributed_inputs(
    tmp_path: Path, argr_cra_example: Path
) -> None:
    root = Path(__file__).resolve().parents[2]
    guide = (root / "docs/python-api.md").read_text()
    blocks = re.findall(r"```python\n(.*?)```", guide, flags=re.DOTALL)
    assert blocks, "tutorial must contain runnable examples"

    shutil.copytree(argr_cra_example / "inputs", tmp_path / "inputs")
    result = subprocess.run(
        [sys.executable, "-c", "\n".join(blocks)], cwd=tmp_path, capture_output=True, text=True
    )

    assert result.returncode == 0, result.stderr
    assert "ArgR" in result.stdout and "Cra" in result.stdout
    assert "Returned 4 of 4" in result.stdout
    for engine in ("annealed", "greedy", "random"):
        assert f"{engine} 4096" in result.stdout
    assert (tmp_path / "candidate.svg").read_bytes().startswith(b"<svg")
    review = inspect_result(tmp_path / "result", kind="bundle")
    assert review.portfolio.best_observed_score == pytest.approx(0.855, abs=0.0005)
    library = load_library((tmp_path / "library.json").read_text())
    assert library.encoded_sequence_count == 16
    assert library.maximum_component_loss <= 0.02
    assert (tmp_path / "variants.fasta").read_text().count(">variant-") == 16
    assert (tmp_path / "variant-scores.tsv").is_file()


def test_quickstart_uses_directional_scoring_and_verified_inspection(tmp_path, argr_cra_example):
    spec = load_design_spec(argr_cra_example / "design.yaml")
    assert spec.length == max(s.motif.width for s in spec.specifications)
    assert spec.schema_version == "design-spec/v3"
    assert [item.direction for item in spec.specifications] == ["seek", "seek"]
    portfolio = design(spec)
    assert len(portfolio.candidates) == 4
    evaluation = score(portfolio.candidates[0].sequence, spec)
    assert evaluation.balance_score == portfolio.candidates[0].balance_score
    assert {match.motif_id for match in evaluation.matches} == {"ArgR", "Cra"}
    portfolio.write(tmp_path / "result")
    review = inspect_result(tmp_path / "result", kind="bundle")
    assert [motif.direction for motif in review.problem.motifs] == ["seek", "seek"]
    assert review.portfolio.best_observed_score == pytest.approx(0.855, abs=0.0005)


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
    assert portfolio.manifest.schema_version == "run-manifest/v7"
    assert portfolio.manifest.search_engine == "annealed_multistart_v1"
    assert portfolio.manifest.completion_status == "budget_exhausted"
    portfolio.write(tmp_path / "result")
    review = inspect_result(tmp_path / "result", kind="bundle")
    assert [motif.direction for motif in review.problem.motifs] == ["seek"] * motifs
