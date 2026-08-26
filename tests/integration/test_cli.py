from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from motif_balance.cli import app

runner = CliRunner()

_DESIGN = """schema_version: design-spec/v1
motifs:
  motif_a:
    probabilities:
      - [0.7, 0.1, 0.1, 0.1]
    background: [0.25, 0.25, 0.25, 0.25]
  motif_b:
    probabilities:
      - [0.1, 0.1, 0.7, 0.1]
    background: [0.25, 0.25, 0.25, 0.25]
length: 2
count: 2
strands: both
evaluations: 16
seed: 7
min_distance: 0.5
"""


def test_cli_check_compiles_without_search_or_output(tmp_path: Path) -> None:
    spec = tmp_path / "design.yaml"
    spec.write_text(_DESIGN)

    result = runner.invoke(app, ["design", str(spec), "--check"])

    assert result.exit_code == 0
    assert result.stdout.startswith("valid problem-")
    assert {path.name for path in tmp_path.iterdir()} == {"design.yaml"}


def test_cli_design_writes_verified_bundle(tmp_path: Path) -> None:
    spec = tmp_path / "design.yaml"
    output = tmp_path / "result"
    spec.write_text(_DESIGN)

    result = runner.invoke(app, ["design", str(spec), "--out", str(output)])

    assert result.exit_code == 0
    assert result.stdout.startswith("complete bundle-")
    assert (output / "manifest.json").is_file()


def test_cli_rejects_unknown_scientific_fields(tmp_path: Path) -> None:
    spec = tmp_path / "design.yaml"
    spec.write_text(_DESIGN + "objective: soft-min\n")

    result = runner.invoke(app, ["design", str(spec), "--check"])

    assert result.exit_code == 2
    assert "extra_forbidden" in result.stderr
