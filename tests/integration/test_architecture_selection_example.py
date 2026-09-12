"""Selection works with a supplied pool and a verified, locally generated bundle."""

import re
import subprocess
import sys
from pathlib import Path


def _guide_blocks():
    root = Path(__file__).resolve().parents[2]
    guide = (root / "docs/choose-alternatives.md").read_text()
    return re.findall(r"```python\n(.*?)```", guide, flags=re.DOTALL)


def test_architecture_selection_guide_from_an_empty_directory(tmp_path):
    blocks = _guide_blocks()
    completed = subprocess.run(
        [sys.executable, "-c", blocks[0]], cwd=tmp_path, capture_output=True, text=True
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.splitlines() == [
        "1 architecture(s): minimum balance 1.000",
        "2 architecture(s): minimum balance 1.000",
        "3 architecture(s): minimum balance 0.500",
        "Selected: AACC, CCAA",
        "Sequence evaluations: 6; search evaluations: 0",
    ]
    assert not list(tmp_path.iterdir())


def test_verified_design_to_architecture_selection_guide(tmp_path):
    blocks = _guide_blocks()
    assert len(blocks) == 3, "the guide needs saved-design and supplied-candidate handoffs"
    checks = """
assert assessment.structural_score == 1.0
assert assessment.sequence_evaluations == 0
assert saved.manifest.completion_status == "exhaustive"
assert saved.manifest.evaluation_count == 256
assert len(saved.candidates) == 1
assert len(saved.manifest.elites) == 256
assert recovered.spec == saved.spec
assert recovered.scoring_evaluations == 256
assert recovered.search_evaluations == 0
assert [item.sequence for item in recovered.select(2)] == ["AACC", "CCAA"]
assert [item.balance_score for item in recovered.select(2)] == [1.0, 1.0]
assert review.run.bundle_id == saved.manifest.bundle_id
"""
    completed = subprocess.run(
        [sys.executable, "-c", "\n".join([*blocks, checks])],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "Recovered alternatives: AACC, CCAA" in completed.stdout
    assert "Search calls: 256; ranking calls: 256" in completed.stdout
    assert {path.name for path in tmp_path.iterdir()} == {"architecture-result"}


def test_supplied_architecture_review_guide_needs_no_bundle_or_new_search(tmp_path):
    blocks = _guide_blocks()
    assert len(blocks) == 3, "document how to inspect an actual alternative, not a run winner"
    checks = """
from xml.etree import ElementTree as ET
from motif_balance.inspection import CandidateInspection

assert candidate.rank == 2
assert candidate.sequence == "CCAA"
assert candidate.matches == representative.evaluation.matches
assert candidate_review.candidate.balance_score == 1.0
assert candidate_review.candidate.nearest_neighbor_distance is None
assert candidate_review.rank_scope == "caller_supplied_order"
assert candidate_review.problem.motifs[0].model_digest == left.model_digest
assert candidate_review.problem.motifs[1].model_digest == right.model_digest
assert CandidateInspection.model_validate_json(review_json) == candidate_review
assert "bundle_id" not in review_json
assert "portfolio" not in review_json
ns = "{http://www.w3.org/2000/svg}"
root = ET.fromstring(svg)
assert "Caller-supplied rank 2" in root.find(ns + "desc").text
assert root.get("data-visual-contract") == "motif-balance.candidate-duplex/v2"
assert [(m.motif_id, m.start, m.end) for m in candidate_review.candidate.matches] == [
    ("left", 2, 4), ("right", 0, 2)
]
"""
    completed = subprocess.run(
        [sys.executable, "-c", "\n".join([blocks[0], blocks[2], checks])],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert not list(tmp_path.iterdir()), "supplied candidate review must not invent a bundle"
