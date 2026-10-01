"""
--------------------------------------------------------------------------------
motif-balance
tests/contract/test_playback.py

Playback preserves verified recorded states and refuses misleading inputs.

Module Author(s): Eric J. South
Dunlop Lab
--------------------------------------------------------------------------------
"""

import importlib
import xml.etree.ElementTree as ET
from itertools import pairwise

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


@pytest.mark.parametrize("field", ["length", "direction", "probabilities", "width"])
def test_playback_rejects_frames_bound_to_another_problem(observation, field):
    view = inspect_playback(observation)
    raw = view.model_dump(mode="json")
    if field == "length":
        raw["problem"]["length"] += 1
    else:
        motif = raw["problem"]["motifs"][0]
        if field == "direction":
            motif["direction"] = "avoid"
        elif field == "probabilities":
            motif["probabilities"] = [[0.4, 0.2, 0.2, 0.2]] * motif["width"]
        else:
            motif["width"] += 1
            motif["probabilities"].append(motif["probabilities"][0])
            motif["probability_consensus"] += "A"
            motif["score_maximizing_sequence"] += "A"
    with pytest.raises(ValueError, match="problem"):
        type(view).model_validate(raw)


@pytest.mark.parametrize("chain", [None, 0, "all"])
def test_playback_checks_identity_of_best_and_gray_candidates(observation, chain):
    view = inspect_playback(observation, search_chain_id=chain)
    raw = view.model_dump(mode="json")
    frame = raw["frames"][-1]
    candidate = (
        frame["candidate"]
        if chain is None
        else frame["search_candidates"][-1]
        if chain == "all"
        else frame["search_candidate"]
    )
    candidate["candidate_id"] = "candidate-0000000000000000"
    with pytest.raises(ValueError, match="problem"):
        type(view).model_validate(raw)


def test_media_rejects_unbound_projection_before_loading_encoder(observation, monkeypatch):
    from motif_balance.playback import media

    view = inspect_playback(observation)
    wrong = view.model_copy(update={"problem": view.problem.model_copy(update={"length": 8})})

    def unexpected_dependency(_name):
        pytest.fail("invalid projections must fail before loading media dependencies")

    monkeypatch.setattr(media, "_dependency", unexpected_dependency)
    with pytest.raises(ValueError, match="problem"):
        media.render_playback_media(wrong, format_name="mp4")


def test_movie_validates_once_and_preserves_every_saved_drawing(observation, monkeypatch):
    renderer = pytest.importorskip("resvg_py")
    pytest.importorskip("PIL.Image")
    from motif_balance.playback import media, render

    view = inspect_playback(observation)
    expected = [render.render_playback_svg(view, frame=i) for i in range(len(view.frames))]
    actual_validate = render.validate_view
    actual_raster = renderer.svg_to_bytes
    validations = []
    drawings = []

    def checked(value):
        validations.append(value)
        return actual_validate(value)

    def raster(**kwargs):
        drawings.append(kwargs["svg_string"].encode())
        return actual_raster(**kwargs)

    monkeypatch.setattr(render, "validate_view", checked)
    monkeypatch.setattr(media, "validate_view", checked)
    monkeypatch.setattr(renderer, "svg_to_bytes", raster)
    payload = media.render_playback_media(view, format_name="gif", width=320)
    assert payload.startswith(b"GIF")
    assert drawings == expected
    # Dense movies must not revalidate the entire record for each saved drawing.
    assert len(validations) == 1


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


@pytest.mark.parametrize("motif_count", (9, 10, 11, 12))
def test_expanded_playback_keeps_one_duplex_right_of_a_fixed_recovery_panel(
    pairwise_spec, motif_count
):
    from motif_balance.model import MotifSpecification

    motif = pairwise_spec.specifications[0].motif
    items = tuple(
        MotifSpecification(
            motif=motif.model_copy(update={"motif_id": f"model-{i}"}), direction="seek"
        )
        for i in range(motif_count)
    )
    spec = pairwise_spec.model_copy(
        update={"specifications": items, "length": 60, "count": 1, "evaluations": 91}
    )
    observation = design_observed(spec, ObservationSpec(max_snapshots=8))[1]
    view = inspect_playback(observation)
    ns = {"s": "http://www.w3.org/2000/svg"}
    dimensions = set()
    for i, frame in enumerate(view.frames):
        root = ET.fromstring(render_playback_svg(view, frame=i))
        dimensions.add(root.attrib["viewBox"])
        height = float(root.attrib["viewBox"].split()[3])
        for text in root.findall("s:text", ns):
            assert float(text.attrib["y"]) + 0.25 * float(text.attrib["font-size"]) <= height
        panels = {p.attrib["data-panel"]: p for p in root.findall(".//s:rect[@data-panel]", ns)}
        assert panels["recovery"].attrib["width"] == panels["recovery"].attrib["height"]
        assert float(panels["recovery"].attrib["width"]) >= 0.75 * float(
            panels["molecule"].attrib["height"]
        )
        axis = next(
            t for t in root.findall(".//s:text", ns) if "DNA candidates evaluated" in (t.text or "")
        )
        assert float(axis.attrib["font-size"]) >= 44
        assert float(panels["molecule"].attrib["x"]) > float(
            panels["recovery"].attrib["x"]
        ) + float(panels["recovery"].attrib["width"])
        cursor = root.find(".//s:circle[@data-current-state]", ns)
        assert float(cursor.attrib["data-score"]) == frame.candidate.balance_score
        score = root.find(".//s:text[@data-current-score]", ns)
        assert score is not None
        assert f"{frame.candidate.balance_score:.3f}" in "".join(score.itertext())
        assert float(score.attrib["y"]) < float(cursor.attrib["cy"])
        assert float(score.attrib["font-size"]) >= 48
        assert len(root.findall(".//s:g[@data-motif-id]", ns)) == motif_count
    assert len(dimensions) == 1
    # A large endpoint must remain legible beside the nearest logarithmic tick.
    long_view = view.model_copy(
        update={"frames": (view.frames[-1].model_copy(update={"evaluations": 655360}),)}
    )
    root = ET.fromstring(render_playback_svg(long_view))
    labels = [t.text for t in root.findall(".//s:text", ns)]
    assert "655,360" in labels
    assert "100,000" not in labels


def test_playback_rejects_thirteen_models_before_replay(pairwise_spec, monkeypatch):
    from motif_balance.model import MotifSpecification
    from motif_balance.playback import api

    motif = pairwise_spec.specifications[0].motif
    items = tuple(
        MotifSpecification(
            motif=motif.model_copy(update={"motif_id": f"model-{i}"}), direction="seek"
        )
        for i in range(13)
    )
    spec = pairwise_spec.model_copy(
        update={"specifications": items, "length": 60, "count": 1, "evaluations": 16}
    )
    observation = design_observed(spec, ObservationSpec(max_snapshots=8))[1]
    monkeypatch.setattr(
        api, "verify_search_observation", lambda _: pytest.fail("oversized view reached replay")
    )
    with pytest.raises(ArtifactError, match="twelve"):
        inspect_playback(observation)


def test_resized_movie_supplies_complete_raster_frames(observation, monkeypatch):
    pytest.importorskip("resvg_py")
    pytest.importorskip("PIL.Image")
    from pathlib import Path
    from types import SimpleNamespace

    from motif_balance.playback import media, render_playback_media

    view = inspect_playback(observation)
    actual_dependency = media._dependency
    seen = []

    def write_frames(path, size, **kwargs):
        payload = yield
        try:
            while True:
                assert len(payload) == size[0] * size[1] * 3
                seen.append(size)
                payload = yield
        finally:
            Path(path).write_bytes(b"verified-frames")

    monkeypatch.setattr(
        media,
        "_dependency",
        lambda name: (
            SimpleNamespace(write_frames=write_frames)
            if name == "imageio_ffmpeg"
            else actual_dependency(name)
        ),
    )
    assert (
        render_playback_media(view, format_name="mp4", width=321, transition_frames=1)
        == b"verified-frames"
    )
    selected = [0]
    for i in range(1, len(view.frames)):
        old, new = view.frames[selected[-1]], view.frames[i]
        if (
            old.candidate != new.candidate
            or old.best_balance != new.best_balance
            or i == len(view.frames) - 1
        ):
            selected.append(i)
    transitions = sum(
        view.frames[a].candidate != view.frames[b].candidate for a, b in pairwise(selected)
    )
    assert len(seen) == len(selected) + transitions
    assert len(set(seen)) == 1


def test_mp4_total_work_is_bounded_before_loading_encoder(observation, monkeypatch):
    from motif_balance.playback import media, render_playback_media

    view = inspect_playback(observation)
    monkeypatch.setattr(media, "_MAX_TOTAL_PIXELS", 1, raising=False)

    def no_dependency(name):
        raise AssertionError("work must be admitted before media dependencies load")

    monkeypatch.setattr(media, "_dependency", no_dependency)
    with pytest.raises(ArtifactError, match="total"):
        render_playback_media(view, format_name="mp4", fps=30, transition_frames=30)


def test_incumbent_playback_includes_exact_early_checkpoints(pairwise_spec):
    spec = pairwise_spec.model_copy(update={"length": 7, "evaluations": 91, "count": 1})
    _, observation = design_observed(
        spec, ObservationSpec(max_snapshots=2, incumbent_evaluations=(8, 16, 32, 64, 91))
    )
    view = inspect_playback(observation)
    expected = {row.evaluations: row.incumbent for row in observation.snapshots}
    expected.update({row.evaluations: row.incumbent for row in observation.incumbents})
    assert [frame.evaluations for frame in view.frames] == sorted(expected)
    for frame in view.frames:
        assert frame.candidate.sequence == expected[frame.evaluations].sequence
        assert frame.best_balance == expected[frame.evaluations].balance_score
    chain = inspect_playback(observation, chain_id=0)
    assert [frame.evaluations for frame in chain.frames] == [
        r.evaluations for r in observation.snapshots
    ]


def test_combined_checkpoint_limit_precedes_expensive_replay(pairwise_spec, monkeypatch):
    from motif_balance.playback import api

    spec = pairwise_spec.model_copy(update={"length": 7, "evaluations": 1500, "count": 1})
    observation = design_observed(
        spec, ObservationSpec(max_snapshots=256, incumbent_evaluations=tuple(range(2, 34)))
    )[1]
    assert len({r.evaluations for r in observation.snapshots} | set(range(2, 34))) > 256
    monkeypatch.setattr(
        api, "verify_search_observation", lambda _: pytest.fail("oversized view reached replay")
    )
    with pytest.raises(ArtifactError, match="256 combined"):
        inspect_playback(observation)


def test_search_overlay_uses_one_actual_chain_and_preserves_the_best(observation):
    from motif_balance.playback.media import _movie_steps
    from motif_balance.playback.transition import blend_svgs

    view = inspect_playback(observation, search_chain_id=0)
    assert view.search_chain_id == 0
    for frame, recorded in zip(view.frames, observation.snapshots, strict=True):
        assert frame.candidate.sequence == recorded.incumbent.sequence
        assert frame.search_candidate.sequence == recorded.states[0].evaluation.sequence
        assert frame.search_evaluations == recorded.evaluations
    root = ET.fromstring(render_playback_svg(view))
    ns = {"s": "http://www.w3.org/2000/svg"}
    point = root.find(".//s:circle[@data-search-state]", ns)
    assert float(point.get("data-score")) == view.frames[-1].search_candidate.balance_score
    assert root.find(".//s:g[@data-duplex-layout='search']", ns) is not None
    assert root.find(".//s:g[@data-duplex-layout='best']", ns) is not None
    assert "Best so far" in "".join(root.itertext())
    ids = [n.get("id") for n in root.iter() if n.get("id")]
    assert len(ids) == len(set(ids))
    # Ongoing exploration remains visible even when the incumbent does not improve.
    for i in range(1, len(view.frames)):
        if view.frames[i].search_candidate != view.frames[i - 1].search_candidate:
            assert i in [index for index, _ in _movie_steps(view, 2)]
    tween = ET.fromstring(
        blend_svgs(render_playback_svg(view, frame=0), render_playback_svg(view, frame=1), 0.5)
    )
    assert len(tween.findall(".//s:g[@data-duplex-layout]", ns)) == 2
    assert tween.find(".//s:circle[@data-search-state]", ns).get("data-score") == str(
        view.frames[0].search_candidate.balance_score
    )


def test_search_overlay_never_invents_an_early_chain_state(pairwise_spec):
    spec = pairwise_spec.model_copy(update={"length": 7, "evaluations": 91, "count": 1})
    observation = design_observed(
        spec, ObservationSpec(max_snapshots=2, incumbent_evaluations=(1, 16, 32))
    )[1]
    view = inspect_playback(observation, search_chain_id=0)
    for frame in view.frames:
        previous = [r for r in observation.snapshots if r.evaluations <= frame.evaluations]
        if previous:
            assert frame.search_evaluations == previous[-1].evaluations
            assert frame.search_candidate.sequence == previous[-1].states[0].evaluation.sequence
        else:
            assert frame.search_candidate is None
            assert frame.search_evaluations is None
    with pytest.raises(ArtifactError, match="chain"):
        inspect_playback(observation, chain_id=0, search_chain_id=1)
    with pytest.raises(ArtifactError, match="chain"):
        inspect_playback(observation, search_chain_id=True)


def test_search_overlay_refuses_random_search_before_replay(pairwise_spec, monkeypatch):
    from motif_balance.playback import api

    observation = design_observed(
        pairwise_spec.model_copy(update={"count": 1}), ObservationSpec(), method="random"
    )[1]
    monkeypatch.setattr(
        api, "verify_search_observation", lambda _: pytest.fail("missing chain reached replay")
    )
    with pytest.raises(ArtifactError, match="chain"):
        inspect_playback(observation, search_chain_id=0)


def test_search_overlay_rejects_missing_future_and_reordered_records(observation):
    from motif_balance.playback.model import PlaybackInspection

    view = inspect_playback(observation, search_chain_id=0)
    for updates, message in (
        ({"search_evaluations": None}, "recorded evaluation count"),
        ({"search_evaluations": view.frames[-1].evaluations + 1}, "future"),
        ({"search_candidate": None, "search_evaluations": None}, "disappear"),
        ({"search_evaluations": 1}, "chronological"),
    ):
        bad = view.model_copy(
            update={"frames": (*view.frames[:-1], view.frames[-1].model_copy(update=updates))}
        )
        with pytest.raises(ValueError, match=message):
            PlaybackInspection.model_validate(bad.model_dump(mode="python"))


def test_all_search_chains_keep_their_recorded_identity(observation):
    from motif_balance.playback.transition import blend_svgs

    view = inspect_playback(observation, search_chain_id="all")
    for frame, recorded in zip(view.frames, observation.snapshots, strict=True):
        assert frame.search_candidate is None
        assert frame.search_evaluations == recorded.evaluations
        assert [c.sequence for c in frame.search_candidates] == [
            state.evaluation.sequence for state in recorded.states
        ]
    ns = {"s": "http://www.w3.org/2000/svg"}
    root = ET.fromstring(render_playback_svg(view))
    points = root.findall(".//s:circle[@data-search-state]", ns)
    assert len(points) == 8
    for chain, point in enumerate(points):
        assert point.get("data-chain") == str(chain)
        assert (
            float(point.get("data-score"))
            == observation.snapshots[-1].states[chain].evaluation.balance_score
        )
    assert len(root.findall(".//s:polyline[@data-search-trace]", ns)) == 8
    layers = root.findall(".//s:g[@data-duplex-layout]", ns)
    assert len(layers) == 9
    assert len({layer.get("data-duplex-layout") for layer in layers}) == 9
    tween = ET.fromstring(
        blend_svgs(render_playback_svg(view, frame=0), render_playback_svg(view, frame=1), 0.5)
    )
    assert len(tween.findall(".//s:g[@data-duplex-layout]", ns)) == 9


def test_showcase_stops_at_first_record_of_final_best_and_rescales_axis(observation):
    from motif_balance.playback import PlaybackInspection

    view = inspect_playback(observation, search_chain_id="all")
    # A known plateau after a best candidate must not add a closing search scene.
    end = view.frames[-1]
    plateau = end.model_copy(update={"evaluations": end.evaluations + 1000})
    extended = PlaybackInspection.model_validate(
        view.model_copy(update={"frames": (*view.frames, plateau)}).model_dump(mode="python")
    )
    short = extended.until_last_improvement()
    assert short.frames[-1].best_balance == end.best_balance
    assert short.frames[-1].evaluations <= end.evaluations
    assert all(f.best_balance < end.best_balance for f in short.frames[:-1])
    assert extended.frames[-1] == plateau
    root = ET.fromstring(render_playback_svg(short))
    ns = {"s": "http://www.w3.org/2000/svg"}
    panel = root.find(".//s:rect[@data-panel='recovery']", ns)
    point = root.find(".//s:circle[@data-current-state]", ns)
    assert float(point.get("cx")) == pytest.approx(
        float(panel.get("x")) + float(panel.get("width")), abs=0.001
    )
    assert str(plateau.evaluations) not in root.get("data-evaluations")
    single = short.model_copy(update={"frames": (short.frames[0],)})
    assert single.until_last_improvement().frames == single.frames


def test_accelerating_pacing_slows_opening_without_reordering_records(observation):
    from motif_balance.playback.media import _movie_steps

    view = inspect_playback(observation, search_chain_id="all")
    uniform = _movie_steps(view, 26)
    accelerating = _movie_steps(view, 26, pacing="accelerating")
    assert [i for i, _ in accelerating] == [i for i, _ in uniform]
    durations = [n for _, n in accelerating if n]
    assert durations[0] == 26
    assert durations[-1] <= 6
    assert durations == sorted(durations, reverse=True)


def test_accelerating_pacing_requires_a_tweened_movie(observation, monkeypatch):
    from motif_balance.playback import media, render_playback_media

    view = inspect_playback(observation)
    monkeypatch.setattr(
        media, "_dependency", lambda _: pytest.fail("invalid pacing reached encoder")
    )
    for settings in (
        {"format_name": "png", "transition_frames": 4, "pacing": "accelerating"},
        {"format_name": "mp4", "pacing": "accelerating"},
        {"format_name": "mp4", "transition_frames": 4, "pacing": "invented"},
    ):
        with pytest.raises(ArtifactError):
            render_playback_media(view, **settings)


def test_all_chain_projection_refuses_ambiguous_or_changing_membership(observation):
    from motif_balance.playback import PlaybackInspection

    view = inspect_playback(observation, search_chain_id="all")
    for change, message in (
        ({"search_chain_id": 0}, "all-chain"),
        ({"schema_version": "playback-inspection/v1"}, "playback-inspection/v2"),
        (
            {
                "frames": (
                    *view.frames[:-1],
                    view.frames[-1].model_copy(
                        update={
                            "search_candidates": view.frames[-1].search_candidates[:-1],
                        }
                    ),
                )
            },
            "appear or disappear",
        ),
    ):
        with pytest.raises(ValueError, match=message):
            PlaybackInspection.model_validate(
                view.model_copy(update=change).model_dump(mode="python")
            )
    with pytest.raises(ValueError, match="best-sequence"):
        inspect_playback(observation, chain_id=0).until_last_improvement()


def test_full_run_timing_is_optional_positive_and_retained_by_excerpt(observation):
    view = inspect_playback(observation)
    raw = view.model_dump(mode="json")
    for invalid in (True, 0, -1, float("nan"), float("inf"), "60"):
        with pytest.raises(ValueError):
            type(view).model_validate({**raw, "full_run_elapsed_seconds": invalid})
    timed = type(view).model_validate({**raw, "full_run_elapsed_seconds": 120.0})
    excerpt = timed.until_last_improvement()
    assert excerpt.full_run_elapsed_seconds == 120.0
    assert "Full search: 2.0 min elapsed" in render_playback_svg(excerpt).decode()
    assert "Full search:" not in render_playback_svg(view).decode()
