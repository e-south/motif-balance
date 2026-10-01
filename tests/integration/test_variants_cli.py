"""
--------------------------------------------------------------------------------
motif-balance
tests/integration/test_variants_cli.py

The diversification handoff enumerates exactly its IUPAC template.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from motif_balance import DesignSpec, design
from motif_balance.cli import app
from motif_balance.model.variants import VariantLibrary

runner = CliRunner()


@pytest.mark.parametrize("source_kind", ["design", "collection", "request"])
@pytest.mark.parametrize(
    "options, message",
    [
        (["--out", "variants.unknown"], "Unrecognized output suffix"),
        (["--format", "all"], "--out is required"),
        (["--editable-mask", "01X0"], "editable mask must contain only"),
    ],
)
def test_invalid_options_fail_before_loading_or_rescoring_inputs(
    tmp_path, monkeypatch, source_kind, options, message
):
    from motif_balance.cli import variants

    def unexpected_read(*args, **kwargs):
        pytest.fail("Invalid output options must be rejected before loading saved results")

    for reader in ("read_verified_portfolio", "read_collection", "load_design_spec"):
        monkeypatch.setattr(variants, reader, unexpected_read)
    source = tmp_path / "source"
    if source_kind == "design":
        source.mkdir()
    else:
        source.write_text("{}")
    args = ["diversify", str(source)]
    if source_kind == "request":
        args.append("ACGT")
    if options[0] == "--out":
        options = ["--out", str(tmp_path / options[1])]
    result = runner.invoke(app, [*args, *options])
    assert result.exit_code == 2, result.output
    assert message in result.output
    assert not (tmp_path / "variants.unknown").exists()


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


def test_expand_all_keeps_separate_products_and_exports_atomically(tmp_path, pairwise_spec):
    saved = tmp_path / "saved"
    design(pairwise_spec.model_copy(update={"min_distance": None})).write(saved)
    source = tmp_path / "collection.json"
    assert (
        runner.invoke(app, ["collect", str(saved), "--count", "2", "--out", str(source)]).exit_code
        == 0
    )
    out = tmp_path / "expanded"
    args = [
        "diversify",
        str(source),
        "--all",
        "--min-balance",
        "0",
        "--max-variants",
        "4",
        "--out",
        str(out),
    ]
    run = runner.invoke(app, args)
    assert run.exit_code == 0, run.output
    data = json.loads((out / "collection.json").read_text())
    assert len(data["libraries"]) == len(data["source"]["collection"]["members"])
    assert all(x["min_balance"] == 0 and x["max_score_loss"] is None for x in data["libraries"])
    assert "template" not in data
    assert (out / "arrangement-1.fasta").exists()
    assert runner.invoke(app, args).exit_code == 2


@pytest.mark.parametrize("extra", [["--candidate", "1"], ["ACGT"], ["--format", "svg"]])
def test_all_rejects_ambiguous_selection_before_read(tmp_path, monkeypatch, extra):
    from motif_balance.cli import variants

    source = tmp_path / "collection.json"
    source.write_text("{}")
    monkeypatch.setattr(
        variants, "read_collection", lambda *a: pytest.fail("invalid options reached reader")
    )
    run = runner.invoke(app, ["diversify", str(source), *extra, "--all"])
    assert run.exit_code == 2, run.output


def test_collection_preflight_rejects_below_floor_before_constructing(pairwise_spec, monkeypatch):
    from motif_balance.alternatives import rank_architectures
    from motif_balance.formats.collection import collection_json
    from motif_balance.model.alternatives import CollectionReport
    from motif_balance.variants import collection as operation

    ranking = rank_architectures(("AAAA",), pairwise_spec.model_copy(update={"min_distance": None}))
    report = CollectionReport.model_validate_json(
        collection_json(ranking, count=2, source_id="bundle-" + "0" * 24, anchored=False)
    )
    monkeypatch.setattr(
        operation,
        "diversify",
        lambda *a, **k: pytest.fail("invalid collection reached construction"),
    )
    with pytest.raises(ValueError, match=r"member.*floor"):
        operation.diversify_collection(report, min_balance=1.0)


def test_collection_work_allowance_does_not_change_products(pairwise_spec, monkeypatch):
    from itertools import product

    from motif_balance.alternatives import rank_architectures
    from motif_balance.formats.collection import collection_json
    from motif_balance.model.alternatives import CollectionReport
    from motif_balance.variants import collection as operation

    spec = pairwise_spec.model_copy(update={"min_distance": None})
    ranking = rank_architectures(tuple(map("".join, product("ACGT", repeat=4))), spec)
    report = CollectionReport.model_validate_json(
        collection_json(ranking, count=2, source_id="bundle-" + "0" * 24, anchored=False)
    )
    expected = tuple(
        operation.diversify(m.evaluation.sequence, spec, min_balance=0, max_variants=4)
        for m in report.collection.members
    )
    with monkeypatch.context() as patch:
        patch.setattr(
            operation, "diversify", lambda *a, **k: pytest.fail("work was not preflighted")
        )
        with pytest.raises(ValueError, match=r"total.*work"):
            operation.diversify_collection(
                report, min_balance=0, max_variants=4, max_total_score_operations=1
            )
    result = operation.diversify_collection(
        report, min_balance=0, max_variants=4, max_total_score_operations=2_000_000_000
    )
    assert result.libraries == expected
    for invalid in (True, 1.5, 0, 16_000_000_001):
        with pytest.raises(ValueError, match=r"total.*work"):
            operation.diversify_collection(report, max_total_score_operations=invalid)


def test_collection_work_option_requires_all_before_read(tmp_path):
    source = tmp_path / "collection.json"
    source.write_text("{}")
    run = runner.invoke(
        app, ["diversify", str(source), "--max-total-score-operations", "2000000000"]
    )
    assert run.exit_code == 2
    assert "requires --all" in run.output
