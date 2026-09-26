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

from motif_balance import DesignSpec, design
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


def test_saved_design_flows_through_collection_to_a_variant_directory(tmp_path, pairwise_spec):
    result = design(pairwise_spec.model_copy(update={"min_distance": None}))
    saved = tmp_path / "result"
    result.write(saved)
    collection = tmp_path / "collection.json"
    run = runner.invoke(app, ["collect", str(saved), "--count", "2", "--out", str(collection)])
    assert run.exit_code == 0, run.output
    report = json.loads(collection.read_text())
    assert (
        f"Selected {report['collection']['delivered_count']} of 2 requested arrangements"
        in run.output
    )
    assert "Rank 1:" in run.output
    assert report["source_bundle_id"] == result.manifest.bundle_id
    assert report["source_verification"] == "self_consistent"
    parent = report["collection"]["members"][0]["evaluation"]["sequence"]
    out = tmp_path / "variants"
    args = ["diversify", str(collection), "--candidate", "1", "--out", str(out)]
    run = runner.invoke(app, args)
    assert run.exit_code == 0, run.output
    assert {p.name for p in out.iterdir()} == {
        "library.json",
        "variants.fasta",
        "scores.tsv",
        "substitutions.svg",
    }
    assert json.loads((out / "library.json").read_text())["parent"]["sequence"] == parent
    assert runner.invoke(app, args).exit_code != 0
    direct = runner.invoke(app, ["diversify", str(saved), "--candidate", "1", "--format", "json"])
    assert direct.exit_code == 0, direct.output
    assert json.loads(direct.stdout)["parent"]["sequence"] == result.candidates[0].sequence


def test_saved_parent_selection_rejects_conflicts_and_out_of_range(tmp_path, pairwise_spec):
    saved = tmp_path / "result"
    design(pairwise_spec).write(saved)
    for args, message in (
        ([str(saved), "ACGT"], "omit the DNA argument"),
        ([str(saved), "--candidate", "999"], "candidate rank"),
        ([str(saved), "--out", str(saved / "variants")], "outside"),
        ([str(saved), "--out", str(tmp_path / "variants.xyz")], "output suffix"),
        ([str(saved), "--format", "all"], "--out"),
    ):
        run = runner.invoke(app, ["diversify", *args])
        assert run.exit_code == 2
        assert message in run.output, run.output
    assert not (saved / "variants").exists()


def test_collection_parent_is_rescored_before_diversification(tmp_path, pairwise_spec):
    from motif_balance.alternatives import rank_architectures
    from motif_balance.formats.collection import collection_json

    spec = pairwise_spec.model_copy(update={"min_distance": None})
    ranking = rank_architectures(("ACGT",), spec)
    # Preserve the report's internal relationships while falsifying a raw score.
    member = ranking.representatives[0]
    match = member.evaluation.matches[0]
    altered = member.evaluation.model_copy(
        update={
            "matches": (
                match.model_copy(update={"raw_score": match.raw_score + 0.01}),
                *member.evaluation.matches[1:],
            )
        }
    )
    ranking = ranking.model_copy(
        update={"representatives": (member.model_copy(update={"evaluation": altered}),)}
    )
    source = tmp_path / "collection.json"
    source.write_text(
        collection_json(ranking, count=1, source_id="bundle-" + "0" * 24, anchored=False)
    )
    out = tmp_path / "variants"
    run = runner.invoke(app, ["diversify", str(source), "--out", str(out)])
    assert run.exit_code == 2
    assert "does not match its rescored DNA" in run.output
    assert not out.exists()


def test_collection_reader_rejects_duplicate_keys_and_changed_selection(tmp_path, pairwise_spec):
    from motif_balance.alternatives import rank_architectures
    from motif_balance.formats.collection import collection_json

    spec = pairwise_spec.model_copy(update={"min_distance": None})
    ranking = rank_architectures(("ACGT",), spec)
    payload = collection_json(ranking, count=1, source_id="bundle-" + "0" * 24, anchored=False)
    source = tmp_path / "collection.json"
    altered = json.loads(payload)
    altered["collection"]["ranking_digest"] = "0" * 64
    for content in ('{"pool":"retained_elites",' + payload[1:], json.dumps(altered)):
        source.write_text(content)
        run = runner.invoke(app, ["diversify", str(source)])
        assert run.exit_code == 2
