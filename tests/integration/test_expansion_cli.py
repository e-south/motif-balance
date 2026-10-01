"""The expansion handoff exports all passing tests without an ambiguity template."""

import json

from typer.testing import CliRunner

from motif_balance import design
from motif_balance.cli import app
from motif_balance.variants import load_expansion

runner = CliRunner()


def test_explicit_expansion_export_and_no_overwrite(tmp_path, pairwise_spec):
    path = tmp_path / "request.json"
    path.write_text(pairwise_spec.model_dump_json())
    out = tmp_path / "expanded"
    args = [
        "expand",
        str(path),
        "ACGT",
        "--min-balance",
        "0",
        "--max-variants",
        "8",
        "--max-evaluations",
        "64",
        "--out",
        str(out),
    ]
    run = runner.invoke(app, args)
    assert run.exit_code == 0, run.output
    result = load_expansion((out / "expansion.json").read_bytes())
    assert (out / "sequences.fasta").read_text().count(">") == len(result.variants)
    assert "template" not in json.loads((out / "expansion.json").read_text())
    assert "retained" in run.output and "tested" in run.output
    assert runner.invoke(app, args).exit_code == 2


def test_collection_expansion_and_invalid_flags(tmp_path, pairwise_spec):
    saved = tmp_path / "result"
    design(pairwise_spec.model_copy(update={"min_distance": None})).write(saved)
    collection = tmp_path / "collection.json"
    assert (
        runner.invoke(
            app, ["collect", str(saved), "--count", "2", "--out", str(collection)]
        ).exit_code
        == 0
    )
    out = tmp_path / "expanded"
    run = runner.invoke(
        app,
        [
            "expand",
            str(collection),
            "--all",
            "--min-balance",
            "0",
            "--max-variants",
            "8",
            "--max-evaluations",
            "64",
            "--out",
            str(out),
        ],
    )
    assert run.exit_code == 0, run.output
    data = json.loads((out / "collection.json").read_text())
    assert len(list(out.glob("arrangement-*.fasta"))) == len(data["libraries"])
    for args in (
        ["--all", "--candidate", "1"],
        ["--max-total-score-operations", "10"],
        ["--editable-mask", "0X00"],
    ):
        bad = runner.invoke(app, ["expand", str(collection), "--min-balance", "0", *args])
        assert bad.exit_code == 2, bad.output
