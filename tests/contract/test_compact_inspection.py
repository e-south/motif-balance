"""
--------------------------------------------------------------------------------
motif-balance
tests/contract/test_compact_inspection.py

Compact drawings retain model scores, coordinates, and complete collection members.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from xml.etree import ElementTree as ET

import pytest
from PIL import Image
from typer.testing import CliRunner

from motif_balance import design
from motif_balance.alternatives import rank_architectures
from motif_balance.cli import app
from motif_balance.formats.collection import collection_json


def test_compact_png_is_written_from_a_verified_design(tmp_path, pairwise_spec):
    design(pairwise_spec).write(tmp_path / "result")
    result = CliRunner().invoke(
        app,
        [
            "inspect",
            str(tmp_path / "result"),
            "--format",
            "png",
            "--out",
            str(tmp_path / "candidate.png"),
        ],
    )
    assert result.exit_code == 0, result.output
    with Image.open(tmp_path / "candidate.png") as image:
        assert image.width == 1800
        assert 200 < image.height < 4000


def test_collection_can_be_inspected_without_a_search_bundle(tmp_path, pairwise_spec):
    portfolio = design(pairwise_spec)
    ranking = rank_architectures(
        [c.sequence for c in portfolio.candidates],
        pairwise_spec.model_copy(update={"min_distance": None}),
    )
    path = tmp_path / "collection.json"
    path.write_text(
        collection_json(ranking, count=2, source_id=portfolio.manifest.bundle_id, anchored=False)
    )
    out = tmp_path / "collection.svg"
    result = CliRunner().invoke(app, ["inspect", str(path), "--format", "svg", "--out", str(out)])
    assert result.exit_code == 0, result.output
    root = ET.fromstring(out.read_bytes())
    members = root.findall(".//*[@data-collection-rank]")
    assert len(members) == min(2, len(ranking.representatives))
    for node, representative in zip(members, ranking.representatives, strict=False):
        assert node.get("data-sequence") == representative.evaluation.sequence
    ids = [node.get("id") for node in root.iter() if node.get("id")]
    assert len(ids) == len(set(ids))


def test_compact_svg_keeps_scores_but_omits_detailed_annotations(pairwise_spec, tmp_path):
    from motif_balance.inspection import inspect_result
    from motif_balance.inspection.render import render_candidate_svg

    design(pairwise_spec).write(tmp_path / "result")
    inspected = inspect_result(tmp_path / "result", kind="bundle")
    raw = render_candidate_svg(inspected, compact=True)
    root = ET.fromstring(raw)
    labels = " ".join("".join(node.itertext()) for node in root.iter() if node.tag.endswith("text"))
    assert "Balance" in labels
    assert "q =" in labels
    assert "LLR" not in labels
    assert "attainment" not in labels
    assert "LIMITING" not in labels
    for match in inspected.portfolio.candidates[0].matches:
        lanes = root.findall(f".//*[@data-motif-id='{match.motif_id}'][@class='motif-match']")
        assert len(lanes) == 1
        assert lanes[0].get("data-start") == str(match.start)
        assert lanes[0].get("data-strand") == match.strand


def test_collection_rescores_stored_claims_before_writing(tmp_path, pairwise_spec):
    import json

    portfolio = design(pairwise_spec)
    spec = pairwise_spec.model_copy(update={"min_distance": None})
    ranking = rank_architectures([c.sequence for c in portfolio.candidates], spec)
    record = json.loads(
        collection_json(ranking, count=2, source_id=portfolio.manifest.bundle_id, anchored=False)
    )
    # Preserve schema consistency while making one stored raw score false.
    for member in [record["ranking"]["representatives"][0], record["collection"]["members"][0]]:
        member["evaluation"]["matches"][0]["raw_score"] += 0.25
    path, out = tmp_path / "collection.json", tmp_path / "false.svg"
    path.write_text(json.dumps(record))
    result = CliRunner().invoke(app, ["inspect", str(path), "--format", "svg", "--out", str(out)])
    assert result.exit_code != 0
    assert not out.exists()


def test_compact_reverse_and_avoid_keep_their_scoring_meaning():
    from motif_balance import Candidate, DesignSpec, MotifModel, MotifSpecification, score
    from motif_balance.inspection import inspect_candidate
    from motif_balance.inspection.render import render_candidate_svg
    from motif_balance.model import candidate_id_for_sequence

    motif = MotifModel(
        motif_id="reverse",
        background=(0.25,) * 4,
        probabilities=((0.7, 0.1, 0.1, 0.1), (0.1, 0.7, 0.1, 0.1)),
    )
    spec = DesignSpec(
        specifications=(MotifSpecification(motif=motif, direction="avoid"),),
        length=2,
        count=1,
        evaluations=1,
        seed=1,
    )
    evaluation = score("GT", spec)
    candidate = Candidate(
        candidate_id=candidate_id_for_sequence("GT"), rank=1, **evaluation.model_dump()
    )
    raw = render_candidate_svg(inspect_candidate(candidate, spec), compact=True)
    root = ET.fromstring(raw)
    assert root.find(".//*[@class='motif-match']").get("data-strand") == "-"
    assert b"(avoid)" in raw
    assert "min(1 \u2212 1.000) = 0.000" in raw.decode()


def test_png_rejects_excessive_pixels_and_external_references():
    from motif_balance.errors import ArtifactError
    from motif_balance.inspection.render.png import svg_to_png

    with pytest.raises(ArtifactError, match="pixels"):
        svg_to_png(b'<svg width="100" height="100000"/>')
    with pytest.raises(ArtifactError, match="external"):
        svg_to_png(b'<svg width="100" height="100"><image href="file:///etc/hosts"/></svg>')


def test_png_missing_extra_explains_installation(monkeypatch):
    import sys

    from motif_balance.errors import ArtifactError
    from motif_balance.inspection.render.png import svg_to_png

    monkeypatch.setitem(sys.modules, "resvg_py", None)
    with pytest.raises(ArtifactError, match="visualization"):
        svg_to_png(b'<svg width="100" height="100"/>')


@pytest.mark.parametrize("format_name", ["text", "json", "html", "svg", "png"])
def test_one_collection_member_is_available_in_each_format(tmp_path, pairwise_spec, format_name):
    from motif_balance.formats.collection import read_collection
    from motif_balance.inspection import inspect_collection

    portfolio = design(pairwise_spec)
    spec = pairwise_spec.model_copy(update={"min_distance": None})
    ranking = rank_architectures([c.sequence for c in portfolio.candidates], spec)
    path = tmp_path / "collection.json"
    path.write_text(
        collection_json(ranking, count=2, source_id=portfolio.manifest.bundle_id, anchored=False)
    )
    out = tmp_path / f"member.{format_name}"
    result = CliRunner().invoke(
        app, ["inspect", str(path), "--candidate", "1", "--format", format_name, "--out", str(out)]
    )
    assert result.exit_code == 0, result.output
    assert out.stat().st_size > 100
    assert len(inspect_collection(read_collection(path), candidate_rank=1)) == 1
    with pytest.raises(Exception, match="rank"):
        inspect_collection(read_collection(path), candidate_rank=1000)
    refused = CliRunner().invoke(
        app, ["inspect", str(path), "--expected-bundle-id", portfolio.manifest.bundle_id]
    )
    assert refused.exit_code != 0
    assert "result directory" in refused.output


def test_collection_drawing_checks_limits_before_allocating_views(monkeypatch, pairwise_spec):
    from motif_balance.errors import ArtifactError
    from motif_balance.inspection import inspect_candidate
    from motif_balance.inspection.render import collection

    members = tuple(
        inspect_candidate(c, pairwise_spec) for c in design(pairwise_spec).candidates[:2]
    )
    monkeypatch.setattr(collection, "MAX_SVG_CANDIDATES", 1, raising=False)
    monkeypatch.setattr(
        collection,
        "render_compact_candidate_svg",
        lambda *args: pytest.fail("drawing before admission"),
    )
    with pytest.raises(ArtifactError, match="select one"):
        collection.render_collection_svg(members)
