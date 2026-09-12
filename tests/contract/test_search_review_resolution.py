"""A result review cannot recover improvement times absent from its checkpoints."""

from xml.etree import ElementTree as ET

from motif_balance import design
from motif_balance.inspection import inspect_result
from motif_balance.inspection.render import render_search_svg
from motif_balance.model import SearchCheckpoint


def test_sparse_search_review_labels_checkpoint_resolution(tmp_path, pairwise_spec):
    design(pairwise_spec).write(tmp_path / "result")
    inspection = inspect_result(tmp_path / "result", kind="bundle")
    search = inspection.search.model_copy(
        update={
            "checkpoints": (
                SearchCheckpoint(evaluations=4, best_score=0.25),
                SearchCheckpoint(evaluations=16, best_score=0.5),
            ),
            "evaluator_calls": 16,
        }
    )
    payload = render_search_svg(inspection.model_copy(update={"search": search}))
    assert payload is not None
    root = ET.fromstring(payload)
    text = " ".join(root.itertext())
    assert "checkpoint-held steps" in text
    assert "Improvement times between checkpoints are unknown" in text
    assert "exact recorded step" not in text
    ns = "{http://www.w3.org/2000/svg}"
    path = root.find(f".//{ns}path[@id='best-observed-step']")
    assert path is not None
    assert path.get("data-display-mode") == "checkpoint-held-step"
    assert path.get("data-checkpoint-count") == "2"
