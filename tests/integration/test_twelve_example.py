"""
--------------------------------------------------------------------------------
motif-balance
tests/integration/test_twelve_example.py

Example replay admits its declared package before starting an expensive search.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from motif_balance.constants import PACKAGE_VERSION


@pytest.mark.parametrize("script", ["prepare_inputs.py", "reproduce.py"])
def test_example_help_describes_the_task_without_module_banner(script):
    path = Path(__file__).resolve().parents[2] / "examples/twelve-motifs" / script
    result = subprocess.run(
        [sys.executable, str(path), "--help"], check=True, capture_output=True, text=True
    )
    assert "--out" in result.stdout
    assert "Module Author(s)" not in result.stdout
    assert "examples/twelve-motifs/" not in result.stdout


def test_published_example_media_keep_gray_activity_in_molecule_and_bind_assets():
    root = Path(__file__).resolve().parents[2] / "examples/twelve-motifs"
    media = json.loads((root / "media.json").read_text())
    expected = json.loads((root / "expected.json").read_text())
    assert media["displayed_chains"] == 8
    assert media["search_chain_id"] == "all"
    assert media["search_display"] == "molecule"
    assert media["assets"]["playback.gif"]["width"] >= 1000
    assert media["final_displayed_evaluations"] == expected["showcase_evaluations"][-1]
    assert media["balance"] == expected["balance"]
    assert media["displayed_elapsed_seconds"] is None
    assert media["full_run_elapsed_seconds"] > 0
    assert "video_url" not in media
    for name in ("playback.mp4", "playback.gif", "final-frame.png"):
        record = media["assets"][name]
        content = (root / name).read_bytes()
        assert record["sha256"] == hashlib.sha256(content).hexdigest()
        assert record["bytes"] == len(content)


def test_example_selection_preserves_molecular_activity_and_recorded_best(pairwise_spec):
    from motif_balance.api import design_observed
    from motif_balance.model.search_observation import ObservationSpec
    from motif_balance.playback import inspect_playback, render_playback_svg

    path = Path(__file__).resolve().parents[2] / "examples/twelve-motifs/reproduce.py"
    module_spec = importlib.util.spec_from_file_location("twelve_example", path)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    _, observation = design_observed(
        pairwise_spec.model_copy(update={"evaluations": 64}), ObservationSpec(max_snapshots=4)
    )
    source = inspect_playback(observation, search_chain_id="all").model_copy(
        update={"full_run_elapsed_seconds": 42.0}
    )
    view = module.best_progress(source)
    assert source.search_chain_id == "all"
    assert view.search_chain_id == "all"
    assert view.search_display == "molecule"
    assert source.full_run_elapsed_seconds == 42.0
    assert view.full_run_elapsed_seconds is None
    assert "min elapsed" not in render_playback_svg(view).decode()
    assert view.frames == source.until_last_improvement().frames
    assert [(f.evaluations, f.best_balance, f.candidate) for f in view.frames] == [
        (f.evaluations, f.best_balance, f.candidate) for f in source.until_last_improvement().frames
    ]
    ns = {"s": "http://www.w3.org/2000/svg"}
    for index in range(len(view.frames)):
        root = ET.fromstring(render_playback_svg(view, frame=index))
        assert not root.findall(".//*[@data-search-trace]")
        assert not root.findall(".//*[@data-search-state]")
        assert [
            node.get("data-duplex-layout")
            for node in root.findall(".//s:g[@data-duplex-layout]", ns)
        ] == [*(f"search-{i}" for i in range(8)), "best"]


def test_example_checks_replay_version_without_rewriting_original_producer():
    path = Path(__file__).resolve().parents[2] / "examples/twelve-motifs/reproduce.py"
    spec = importlib.util.spec_from_file_location("twelve_example", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    expected = {
        "producer": "motif-balance 0.6.0a2",
        "replay_package_version": "0.7.0",
        "recipe_package_version": PACKAGE_VERSION,
    }
    module.verify_replay_version(expected)
    assert expected["replay_package_version"] == "0.7.0"
    expected["recipe_package_version"] = "0.0.0"
    with pytest.raises(ValueError, match="recipe package"):
        module.verify_replay_version(expected)


def test_media_recipe_replays_and_records_published_gif_encoding(
    pairwise_spec, monkeypatch, tmp_path
):
    from motif_balance.api import design_observed
    from motif_balance.model.search_observation import ObservationSpec
    from motif_balance.playback import inspect_playback

    path = Path(__file__).resolve().parents[2] / "examples/twelve-motifs/reproduce.py"
    spec = importlib.util.spec_from_file_location("twelve_example", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    view = inspect_playback(
        design_observed(
            pairwise_spec.model_copy(update={"evaluations": 64}),
            ObservationSpec(max_snapshots=4),
        )[1],
        search_chain_id="all",
    )
    calls = {}

    def render(_view, **settings):
        calls[settings["format_name"]] = settings
        return settings["format_name"].encode()

    monkeypatch.setattr(module, "render_playback_media", render)
    module.write_media(view, tmp_path, source_evaluations=64)
    assert calls["gif"]["gif_palette_colors"] == 64
    assert calls["gif"]["final_frame_duration_ms"] == 2000
    for format_name in ("mp4", "png"):
        assert "gif_palette_colors" not in calls[format_name]
        assert "final_frame_duration_ms" not in calls[format_name]
    actual = json.loads((tmp_path / "media.json").read_text())["assets"]["playback.gif"]
    published = json.loads((path.parent / "media.json").read_text())["assets"]["playback.gif"]
    assert actual["encoding"] == published["encoding"]
    assert actual["final_frame_duration_ms"] == published["final_frame_duration_ms"]
