"""Playback preserves verified recorded states and refuses misleading inputs."""

import importlib
import xml.etree.ElementTree as ET

import pytest

from motif_balance.api import design_observed
from motif_balance.errors import ArtifactError
from motif_balance.model.search_observation import ObservationSpec
from motif_balance.playback import inspect_playback, render_playback_html, render_playback_svg


@pytest.fixture
def observation(pairwise_spec):
    spec = pairwise_spec.model_copy(update={"length": 7, "evaluations": 91, "count": 1})
    return design_observed(spec, ObservationSpec(max_snapshots=12))[1]


def test_playback_shows_recorded_incumbents_and_one_fixed_chain(observation):
    view = inspect_playback(observation)
    assert [f.candidate.sequence for f in view.frames] == [
        row.incumbent.sequence for row in observation.snapshots
    ]
    assert [f.evaluations for f in view.frames] == [r.evaluations for r in observation.snapshots]
    chain = inspect_playback(observation, chain_id=2)
    assert [f.candidate.sequence for f in chain.frames] == [
        row.states[2].evaluation.sequence for row in observation.snapshots
    ]
    assert [f.best_balance for f in chain.frames] == [
        row.incumbent.balance_score for row in observation.snapshots
    ]


def test_playback_rejects_false_record_and_missing_chain(observation):
    wrong = observation.model_copy(update={"engine": "invented"})
    with pytest.raises(ValueError, match="engine"):
        inspect_playback(wrong)
    for bad in (-1, True, 8):
        with pytest.raises(ArtifactError, match="chain"):
            inspect_playback(observation, chain_id=bad)


def test_render_is_valid_duplex_svg_and_self_contained_player(observation):
    view = inspect_playback(observation)
    svg = render_playback_svg(view, frame=0)
    root = ET.fromstring(svg)
    assert root.attrib["data-evaluations"] == str(observation.snapshots[0].evaluations)
    assert b"3\xe2\x80\xb2" in svg and b"5\xe2\x80\xb2" in svg
    assert b"data-strand=" in svg and b"information-logo-letter" in svg
    html = render_playback_html(view)
    assert b'type="range"' in html and b"prefers-reduced-motion" in html
    assert b"<script src=" not in html and b"http://" not in html.replace(
        b"http://www.w3.org/2000/svg", b""
    )
    assert b"sampled" in html
    with pytest.raises(ArtifactError, match="frame"):
        render_playback_svg(view, frame=len(view.frames))


def test_random_has_no_fictional_chain(pairwise_spec):
    observation = design_observed(
        pairwise_spec.model_copy(update={"count": 1}), ObservationSpec(), method="random"
    )[1]
    with pytest.raises(ArtifactError, match="chain"):
        inspect_playback(observation, chain_id=0)


def test_invalid_inputs_and_media_requirements_fail_before_rendering(observation, monkeypatch):
    from motif_balance.playback import media, render_playback_media

    view = inspect_playback(observation)
    with pytest.raises(ArtifactError, match="requires"):
        inspect_playback("not an observation")
    with pytest.raises(ArtifactError, match="inspected"):
        render_playback_svg(observation)
    for fps in (0, 31, True):
        with pytest.raises(ArtifactError, match="fps"):
            render_playback_html(view, fps=fps)
        with pytest.raises(ArtifactError, match="fps"):
            render_playback_media(view, format_name="png", fps=fps)
    with pytest.raises(ArtifactError, match="format"):
        render_playback_media(view, format_name="jpeg")

    actual_import = importlib.import_module

    def missing_extra(name):
        if name == "resvg_py":
            raise ImportError("optional dependency absent")
        return actual_import(name)

    monkeypatch.setattr(media.importlib, "import_module", missing_extra)
    with pytest.raises(ArtifactError, match="visualization"):
        render_playback_media(view, format_name="png")


def test_reverse_logos_grow_down_without_mirroring_letters(observation):
    view = inspect_playback(observation)
    svg = ET.fromstring(render_playback_svg(view))
    ns = {"s": "http://www.w3.org/2000/svg"}
    reverse_lanes = [g for g in svg.findall(".//s:g", ns) if g.attrib.get("data-strand") == "-"]
    assert reverse_lanes
    for lane in reverse_lanes:
        window = lane.find("s:rect", ns)
        baseline = float(window.attrib["y"]) + float(window.attrib["height"])
        paths = [
            p
            for p in lane.findall("s:path", ns)
            if p.attrib.get("class") == "information-logo-letter"
        ]
        assert paths
        for path in paths:
            transform = path.attrib["transform"]
            origin = transform.split("translate(")[1].split(")")[0].split()
            scale = transform.split("scale(")[1].split(")")[0].split()
            assert float(origin[1]) >= baseline - 1e-8
            assert all(float(value) > 0 for value in scale)


def test_square_panels_and_cursor_preserve_snapshot_semantics(observation):
    view = inspect_playback(observation)
    ns = {"s": "http://www.w3.org/2000/svg"}
    bounds = []
    for i, frame in enumerate(view.frames):
        root = ET.fromstring(render_playback_svg(view, frame=i))
        panels = root.findall(".//s:rect[@data-panel]", ns)
        assert len(panels) == 2
        assert all(p.attrib["width"] == p.attrib["height"] for p in panels)
        assert panels[0].attrib["width"] == panels[1].attrib["width"]
        bounds.append(root.attrib["viewBox"])
        cursor = root.find(".//s:circle[@data-current-state]", ns)
        assert cursor is not None
        assert float(cursor.attrib["data-score"]) == frame.candidate.balance_score
        assert cursor.attrib["data-evaluations"] == str(frame.evaluations)
        assert len(root.findall(".//s:circle", ns)) == 1
        assert "Motif logos:" not in "".join(root.itertext())
    assert len(set(bounds)) == 1


def test_chain_cursor_shows_chain_score_instead_of_running_best(observation):
    view = inspect_playback(observation, chain_id=2)
    for i, frame in enumerate(view.frames):
        root = ET.fromstring(render_playback_svg(view, frame=i))
        cursor = root.find(".//{http://www.w3.org/2000/svg}circle[@data-current-state]")
        assert float(cursor.attrib["data-score"]) == frame.candidate.balance_score
