"""
--------------------------------------------------------------------------------
motif-balance
tests/integration/test_architecture_selection_example.py

The arrangement guide continues from the real ArgR/Cra saved design.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

from motif_balance import design
from motif_balance.formats.design import load_design_spec


@pytest.fixture
def saved_example(tmp_path, argr_cra_example):
    design(load_design_spec(argr_cra_example / "design.yaml")).write(tmp_path / "result")
    return tmp_path


def _guide_blocks():
    root = Path(__file__).resolve().parents[2]
    guide = (root / "docs/choose-alternatives.md").read_text()
    assert "## Continue from a saved design" in guide
    blocks = re.findall(r"```python\n(.*?)```", guide, flags=re.DOTALL)
    assert len(blocks) == 2, "one saved-design example and one optional inspection"
    return blocks


def test_arrangement_guide_uses_the_saved_real_search_pool(saved_example):
    blocks = _guide_blocks()
    checks = """
assert saved.spec.length == 25
assert [s.motif.motif_id for s in saved.spec.specifications] == ["ArgR", "Cra"]
assert saved.manifest.evaluation_count == 4096
assert pool == tuple(item.sequence for item in saved.manifest.elites)
assert ranking.grouping == "interval_topology"
assert ranking.spec == saved.spec
assert ranking.search_evaluations == 0
assert collection.requested_count == collection.delivered_count == 2
assert [round(m.evaluation.balance_score, 3) for m in collection.members] == [0.855, 0.801]
"""
    run = subprocess.run(
        [sys.executable, "-c", "\n".join([blocks[0], checks])],
        cwd=saved_example,
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stderr
    assert run.stdout.splitlines() == [
        "Returned 2 of 2 arrangements",
        "Arrangement 1: balance 0.855",
        "Arrangement 2: balance 0.801",
    ]
    assert {p.name for p in saved_example.iterdir()} == {"result"}


def test_optional_inspection_shows_the_second_real_arrangement(saved_example):
    blocks = _guide_blocks()
    checks = """
from xml.etree import ElementTree as ET
from motif_balance.inspection import CandidateInspection
assert candidate.rank == 2
assert candidate.matches == representative.evaluation.matches
assert round(candidate_review.candidate.balance_score, 3) == 0.801
assert candidate_review.rank_scope == "caller_supplied_order"
assert candidate_review.candidate.nearest_neighbor_distance is None
assert CandidateInspection.model_validate_json(review_json) == candidate_review
assert {m.motif_id for m in candidate_review.candidate.matches} == {"ArgR", "Cra"}
root = ET.fromstring(svg)
assert root.get("data-visual-contract") == "motif-balance.candidate-duplex/v2"
"""
    run = subprocess.run(
        [sys.executable, "-c", "\n".join([*blocks, checks])],
        cwd=saved_example,
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stderr
    assert {p.name for p in saved_example.iterdir()} == {"result"}
