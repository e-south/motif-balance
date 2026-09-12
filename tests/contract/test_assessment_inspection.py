"""Pre-search diagrams explain local conflict without inventing candidate sequences."""

import importlib
from xml.etree import ElementTree as ET

import pytest

from motif_balance import MotifModel

NS = "{http://www.w3.org/2000/svg}"


def motif(name, word):
    return MotifModel(
        motif_id=name,
        probabilities=tuple(
            tuple(0.7 if base == preferred else 0.1 for base in "ACGT") for preferred in word
        ),
        background=(0.25, 0.25, 0.25, 0.25),
    )


def inspect(left, right, length, strands="both"):
    return importlib.import_module("motif_balance.inspection.assessment").inspect_pair_assessment(
        left, right, length=length, strands=strands
    )


@pytest.mark.parametrize(
    "left,right,length,score,kinds",
    [
        ("AAA", "AAA", 3, 1.0, ["agreement"] * 3),
        ("AAA", "CCC", 3, 0.5, ["conflict"] * 3),
        ("AAA", "TTT", 3, 1.0, ["agreement"] * 3),
        ("AAA", "CCC", 6, 1.0, ["unshared"] * 6),
    ],
)
def test_presearch_projection_preserves_exact_controls(left, right, length, score, kinds):
    view = inspect(motif("left", left), motif("right", right), length)
    assert view.assessment.structural_score == pytest.approx(score)
    assert view.assessment.sequence_evaluations == 0
    assert [column.kind for column in view.columns] == kinds
    assert "candidate" not in type(view).model_fields
    assert "sequence" not in type(view).model_fields
    if right == "TTT":
        assert view.assessment.best_arrangement.right_strand == "-"
        assert [c.right_position for c in view.columns] == [2, 1, 0]


def test_rendered_presearch_logos_share_physical_base_coordinates_and_arial():
    view = inspect(motif("left", "AAA"), motif("right", "TTT"), 3)
    render = importlib.import_module("motif_balance.inspection.render").render_pair_assessment_svg
    root = ET.fromstring(render(view))
    assert "not a designed sequence" in " ".join(root.itertext())
    assert {e.get("font-family") for e in root.iter(NS + "text")} == {"Arial"}
    logos = root.findall(f".//{NS}g[@class='assessment-logo']")
    assert len(logos) == 2
    for logo in logos:
        columns = logo.findall(f"{NS}g[@class='assessment-logo-column']")
        assert [c.get("data-coordinate") for c in columns] == ["0", "1", "2"]
        for column in columns:
            maximum = max(
                column.findall(NS + "path"), key=lambda e: float(e.get("data-probability"))
            )
            assert maximum.get("data-base") == "A"
            assert maximum.get("data-font-family") == "Arial"
            assert maximum.get("data-font-weight") == "700"
            assert maximum.get("data-observed") is None
    ids = [e.get("id") for e in root.iter() if e.get("id")]
    assert len(ids) == len(set(ids))


def test_render_rejects_mutated_model_binding_and_incomplete_columns():
    view = inspect(motif("left", "AAA"), motif("right", "CCC"), 3)
    render = importlib.import_module("motif_balance.inspection.render").render_pair_assessment_svg
    for update in (
        {"motifs": (motif("left", "GGG"), view.motifs[1])},
        {"columns": view.columns[:-1]},
    ):
        with pytest.raises(ValueError):
            render(view.model_copy(update=update))


def test_nonuniform_background_is_not_mislabeled_as_standard_information_logo():
    left = motif("left", "AAA").model_copy(update={"background": (0.4, 0.2, 0.2, 0.2)})
    with pytest.raises(ValueError, match="uniform"):
        inspect(left, motif("right", "CCC"), 3)


def test_render_does_not_recompute_or_require_distinct_model_names(monkeypatch):
    view = inspect(motif("same", "AAA"), motif("same", "CCC"), 3)
    calculation = importlib.import_module("motif_balance.assessment")

    def forbidden(*args, **kwargs):
        pytest.fail("rendering must not calculate model terms or search")

    monkeypatch.setattr(calculation, "assess_pair", forbidden)
    monkeypatch.setattr(calculation, "_terms", forbidden)
    render = importlib.import_module("motif_balance.inspection.render").render_pair_assessment_svg
    root = ET.fromstring(render(view))
    ids = [e.get("id") for e in root.iter() if e.get("id")]
    assert len(ids) == len(set(ids))


def test_oversized_svg_refuses_without_truncating_the_inspection():
    view = inspect(motif("left", "AAA"), motif("right", "CCC"), 129)
    render = importlib.import_module("motif_balance.inspection.render").render_pair_assessment_svg
    with pytest.raises(ValueError, match="128"):
        render(view)
    assert len(view.columns) == 129
