"""
--------------------------------------------------------------------------------
motif-balance
tests/integration/test_twelve_example.py

Example replay admits its declared package before starting an expensive search.

Module Author(s): Eric J. South
Dunlop Lab
--------------------------------------------------------------------------------
"""

import hashlib
import importlib.util
import json
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from motif_balance.constants import PACKAGE_VERSION


def test_published_example_media_are_best_only_and_bound_to_assets():
    root = Path(__file__).resolve().parents[2] / "examples/twelve-motifs"
    media = json.loads((root / "media.json").read_text())
    expected = json.loads((root / "expected.json").read_text())
    assert media["displayed_chains"] == 0
    assert media["search_chain_id"] is None
    assert media["final_displayed_evaluations"] == expected["showcase_evaluations"][-1]
    assert media["balance"] == expected["balance"]
    assert "video_url" not in media
    for name in ("playback.mp4", "playback.gif", "final-frame.png"):
        record = media["assets"][name]
        content = (root / name).read_bytes()
        assert record["sha256"] == hashlib.sha256(content).hexdigest()
        assert record["bytes"] == len(content)


def test_example_selection_removes_overlays_without_changing_recorded_best(pairwise_spec):
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
    assert view.search_chain_id is None
    assert view.full_run_elapsed_seconds == 42.0
    assert all(not f.recorded_search_candidates for f in view.frames)
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
        ] == ["best"]


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


def test_prepared_example_records_source_and_target_backgrounds(tmp_path, monkeypatch):
    import hashlib
    import io
    import json
    from zipfile import ZipFile

    from motif_balance import MotifModel

    path = Path(__file__).resolve().parents[2] / "examples/twelve-motifs/prepare_inputs.py"
    spec = importlib.util.spec_from_file_location("twelve_preparation", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    raw = (
        b"Background letter frequencies\nA 0.3 C 0.2 G 0.2 T 0.3\n"
        b"letter-probability matrix: alength= 4 w= 1\n0.7 0.1 0.1 0.1\n"
    )
    archive = io.BytesIO()
    with ZipFile(archive, "w") as zipped:
        zipped.writestr("motif.txt", raw)
    data = archive.getvalue()
    expected = MotifModel(
        motif_id="fixture",
        probabilities=(module.canonical_row([(v + 0.025) / 1.1 for v in (0.7, 0.1, 0.1, 0.1)]),),
        background=(0.25,) * 4,
    )
    (tmp_path / "SOURCE.json").write_text(
        json.dumps(
            {
                "url": "https://example.invalid/fixture.zip",
                "archive_sha256": hashlib.sha256(data).hexdigest(),
                "profiles": [
                    {
                        "archive_member": "motif.txt",
                        "record": "fixture",
                        "width": 1,
                        "original_sha256": hashlib.sha256(raw).hexdigest(),
                        "prepared_model_digest": expected.model_digest,
                    }
                ],
            }
        )
    )
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "urlopen", lambda *a, **kw: io.BytesIO(data))
    module.prepare(tmp_path / "output")
    model = MotifModel.model_validate_json((tmp_path / "output/motifs/fixture.json").read_text())
    assert model.model_digest == expected.model_digest
    assert model.conversion is not None
    assert model.conversion.prior_weight == 0.1
    assert model.conversion.source_background == (0.3, 0.2, 0.2, 0.3)
    assert model.conversion.target_background == (0.25,) * 4
