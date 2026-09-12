from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from motif_balance import DesignSpec, design
from motif_balance.errors import ArtifactError
from motif_balance.inspection import inspect_result
from motif_balance.inspection.render import render_candidate_svg


def test_inspection_visuals_use_arial_throughout(tmp_path: Path, pairwise_spec: DesignSpec) -> None:
    from motif_balance.inspection.render import (
        render_html,
        render_portfolio_svg,
        render_search_svg,
    )

    bundle = tmp_path / "bundle"
    design(pairwise_spec).write(bundle)
    inspection = inspect_result(bundle, kind="bundle")
    ns = "{http://www.w3.org/2000/svg}"
    for render in (render_candidate_svg, render_portfolio_svg, render_search_svg):
        root = ET.fromstring(render(inspection))
        assert {node.attrib["font-family"] for node in root.iter(f"{ns}text")} == {"Arial"}
    candidate = ET.fromstring(render_candidate_svg(inspection))
    glyphs = candidate.findall(f".//{ns}path[@class='information-logo-letter']")
    assert glyphs
    assert {node.attrib.get("data-font-family") for node in glyphs} == {"Arial"}
    assert {node.attrib.get("data-font-weight") for node in glyphs} == {"700"}
    html = render_html(inspection).decode()
    assert "font:16px/1.5 Arial;" in html
    assert "font:.82rem/1.4 Arial;" in html
    assert "monospace" not in html
    assert "system-ui" not in html


def test_candidate_visual_refuses_incomplete_molecular_lanes(
    tmp_path: Path,
    pairwise_spec: DesignSpec,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from motif_balance.inspection.render import candidate_projection

    bundle = tmp_path / "bundle"
    design(pairwise_spec).write(bundle)
    inspection = inspect_result(bundle, kind="bundle")
    monkeypatch.setattr(candidate_projection, "MAX_SVG_MATCHES", 1)
    with pytest.raises(ArtifactError, match=r"2 matches.*limit 1.*JSON"):
        render_candidate_svg(inspection)


def test_motif_colors_support_white_window_letters() -> None:
    from motif_balance.inspection.render.svg_primitives import _MOTIF_PALETTE

    for color in _MOTIF_PALETTE:
        rgb = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
        linear = [
            value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in rgb
        ]
        luminance = sum(
            weight * value for weight, value in zip((0.2126, 0.7152, 0.0722), linear, strict=True)
        )
        assert 1.05 / (luminance + 0.05) >= 4.5, color


def test_candidate_visual_is_a_molecular_view_with_explicit_information_axes(
    tmp_path: Path,
    pairwise_spec: DesignSpec,
) -> None:
    bundle = tmp_path / "bundle"
    design(pairwise_spec).write(bundle)
    inspection = inspect_result(bundle, kind="bundle")
    root = ET.fromstring(render_candidate_svg(inspection))
    ns = "{http://www.w3.org/2000/svg}"
    assert root.attrib["data-visual-contract"] == "motif-balance.candidate-duplex/v2"
    assert root.find(f".//{ns}g[@id='position-support']") is None
    for logo in root.findall(f".//{ns}g[@class='motif-information-logo']"):
        axis = logo.find(f"{ns}g[@class='information-axis']")
        assert axis is not None
        assert [node.text for node in axis.findall(f"{ns}text")] == ["0", "2 bits"]
        assert logo.findall(f".//{ns}path[@class='information-logo-letter']")
        assert not logo.findall(f".//{ns}text[@class='information-logo-letter']")


def test_selected_windows_show_white_bases_on_the_duplex_coordinate_grid(
    tmp_path: Path,
    pairwise_spec: DesignSpec,
) -> None:
    bundle = tmp_path / "bundle"
    design(pairwise_spec).write(bundle)
    inspection = inspect_result(bundle, kind="bundle")
    candidate = inspection.portfolio.candidates[0]
    root = ET.fromstring(render_candidate_svg(inspection))
    ns = "{http://www.w3.org/2000/svg}"
    for match in candidate.matches:
        group = root.find(f".//{ns}g[@class='motif-match'][@data-motif-id='{match.motif_id}']")
        assert group is not None
        rectangle = group.find(f"{ns}rect")
        assert rectangle is not None
        assert rectangle.attrib.get("fill-opacity", "1") == "1"
        assert rectangle.attrib["fill"] == group.attrib["data-motif-color"]
        bases = group.findall(f"{ns}text[@class='match-window-base']")
        assert len(bases) == match.end - match.start
        strand_id = "primary-sequence" if match.strand == "+" else "complementary-sequence"
        strand = root.find(f".//{ns}g[@id='{strand_id}']")
        assert strand is not None
        for position, base in zip(range(match.start, match.end), bases, strict=True):
            duplex_base = strand.find(f"{ns}text[@data-candidate-position='{position}']")
            assert duplex_base is not None
            assert base.text == duplex_base.text
            assert base.attrib["fill"] == "#FFFFFF"
            for attribute in ("x", "font-size", "font-family", "font-weight", "text-anchor"):
                assert base.attrib[attribute] == duplex_base.attrib[attribute]


def test_candidate_renderer_consumes_the_verified_result_inspection(
    tmp_path: Path,
    pairwise_spec: DesignSpec,
) -> None:
    bundle = tmp_path / "bundle"
    portfolio = design(pairwise_spec)
    portfolio.write(bundle)
    inspection = inspect_result(bundle, kind="bundle")

    svg = render_candidate_svg(inspection, candidate_rank=1).decode("utf-8")

    assert 'id="candidate-realization-view"' in svg
    assert portfolio.candidates[0].candidate_id not in svg
    assert portfolio.manifest.bundle_id not in svg


def test_candidate_facade_preserves_the_semantic_section_renderer_bytes(
    tmp_path: Path,
    pairwise_spec: DesignSpec,
) -> None:
    from motif_balance.inspection.render.candidate_sections import (
        render_candidate_projection_svg,
    )

    bundle = tmp_path / "bundle"
    design(pairwise_spec).write(bundle)
    inspection = inspect_result(bundle, kind="bundle")
    candidate = inspection.portfolio.candidates[0]

    assert render_candidate_svg(inspection, candidate_rank=1) == render_candidate_projection_svg(
        inspection.problem,
        candidate,
    )


def test_candidate_renderer_has_no_unbound_problem_candidate_entrypoint() -> None:
    with pytest.raises(ImportError):
        exec(
            "from motif_balance.inspection.render import render_candidate_projection_svg",
            {},
        )


def test_candidate_renderer_rejects_same_id_cross_matrix_projection(
    tmp_path: Path,
    pairwise_spec: DesignSpec,
) -> None:
    bundle = tmp_path / "bundle"
    design(pairwise_spec).write(bundle)
    inspection = inspect_result(bundle, kind="bundle")
    motif = inspection.problem.motifs[0]
    drifted_motif = motif.model_copy(
        update={"probabilities": tuple((0.25, 0.25, 0.25, 0.25) for _ in range(motif.width))}
    )
    drifted_problem = inspection.problem.model_copy(
        update={"motifs": (drifted_motif, *inspection.problem.motifs[1:])}
    )
    mixed = inspection.model_copy(update={"problem": drifted_problem})

    with pytest.raises(ArtifactError, match="does not match its problem"):
        render_candidate_svg(mixed, candidate_rank=1)
