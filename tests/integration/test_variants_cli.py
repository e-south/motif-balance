"""
--------------------------------------------------------------------------------
motif-balance
tests/integration/test_variants_cli.py

The diversification handoff enumerates exactly its IUPAC template.

Module Author(s): Eric J. South
Dunlop Lab
--------------------------------------------------------------------------------
"""

import json
from pathlib import Path

from typer.testing import CliRunner

from motif_balance import DesignSpec
from motif_balance.cli import app
from motif_balance.model.variants import VariantLibrary

runner = CliRunner()


def test_diversification_exports_checked_scores_and_fasta(
    tmp_path: Path, pairwise_spec: DesignSpec
):
    source = tmp_path / "request.json"
    source.write_text(pairwise_spec.model_dump_json())
    output = tmp_path / "library.json"
    args = ["diversify", str(source), "ACGT", "--max-score-loss", "0.1", "--out", str(output)]
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    library = VariantLibrary.model_validate_json(output.read_text())
    assert library.parent.sequence == "ACGT"
    assert library.encoded_sequence_count <= 256
    result = runner.invoke(app, args)
    assert result.exit_code == 2
    assert "Refusing to replace" in result.output
    result = runner.invoke(app, ["diversify", str(source), "ACGT", "--format", "fasta"])
    assert result.exit_code == 0, result.output
    assert "\nACGT\n" in result.stdout
    assert result.stdout.startswith(">variant-1")
    result = runner.invoke(app, ["diversify", str(source), "ACGT", "--format", "text"])
    assert result.exit_code == 0, result.output
    assert "Encoded sequence count" in result.stdout
    result = runner.invoke(app, ["diversify", str(source), "ACGT", "--editable-mask", "0000"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["editable_positions"] == []
    result = runner.invoke(app, ["diversify", str(source), "ACGT", "--editable-mask", "0120"])
    assert result.exit_code == 2


def test_substitution_map_and_table_are_available(tmp_path: Path, pairwise_spec: DesignSpec):
    source = tmp_path / "request.json"
    source.write_text(pairwise_spec.model_dump_json())
    for format_name in ("tsv", "svg"):
        result = runner.invoke(app, ["diversify", str(source), "ACGT", "--format", format_name])
        assert result.exit_code == 0, result.output
        assert ("motif_id" if format_name == "tsv" else "Single substitutions") in result.stdout
