"""Score supplied DNA without portfolio admission or replacing caller output."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from motif_balance import DesignSpec
from motif_balance.cli import app
from motif_balance.cli import scoring as scoring_cli
from motif_balance.formats.design import load_design_spec
from motif_balance.model import Evaluation

SPECIFICATION = Path(__file__).resolve().parents[2] / "examples/synthetic-pairwise/design.yaml"
runner = CliRunner()


def test_cli_scores_supplied_dna_without_requiring_the_requested_portfolio(tmp_path: Path) -> None:
    original = load_design_spec(SPECIFICATION)
    spec = DesignSpec.model_validate(
        {**original.model_dump(mode="python"), "count": 17, "evaluations": 17}
    )
    source = tmp_path / "design.json"
    source.write_text(spec.model_dump_json())
    before = source.read_bytes()

    result = runner.invoke(app, ["score", str(source), "AT", "--format", "json"])

    assert result.exit_code == 0, result.output
    evaluation = json.loads(result.stdout)
    assert evaluation["sequence"] == "AT"
    # AT satisfies one of two equally informative positions in both AC and GT.
    assert evaluation["balance_score"] == 0.5
    assert source.read_bytes() == before
    assert list(tmp_path.iterdir()) == [source]
    rejected = runner.invoke(app, ["design", str(source), "--check"])
    assert rejected.exit_code == 2
    assert "count exceeds the complete sequence space" in rejected.output


@pytest.mark.parametrize("kind", ["file", "directory", "symlink", "dangling_symlink"])
def test_occupied_score_output_fails_before_evaluation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    output = tmp_path / "score.json"
    if kind == "directory":
        output.mkdir()
    elif kind == "file":
        output.write_text("keep me")
    else:
        output.symlink_to(SPECIFICATION if kind == "symlink" else tmp_path / "absent")
    before = output.lstat()

    def forbidden_score(sequence: str, spec: DesignSpec) -> Evaluation:
        pytest.fail("occupied score output must be rejected before evaluation")

    monkeypatch.setattr(scoring_cli, "score", forbidden_score)
    result = runner.invoke(
        app, ["score", str(SPECIFICATION), "AT", "--format", "json", "--out", str(output)]
    )

    assert result.exit_code == 2, result.output
    assert "Refusing to replace existing score output" in result.output
    assert "hint: Choose a new output path." in result.output
    assert output.lstat() == before
    if kind == "file":
        assert output.read_text() == "keep me"


def test_score_output_created_during_evaluation_is_not_replaced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "score.json"
    evaluate = scoring_cli.score

    def racing_score(sequence: str, spec: DesignSpec) -> Evaluation:
        result = evaluate(sequence, spec)
        output.write_text("another caller")
        return result

    monkeypatch.setattr(scoring_cli, "score", racing_score)
    result = runner.invoke(app, ["score", str(SPECIFICATION), "AT", "--out", str(output)])

    assert result.exit_code == 2, result.output
    assert "Refusing to replace existing score output" in result.output
    assert output.read_text() == "another caller"
    assert list(tmp_path.iterdir()) == [output]
