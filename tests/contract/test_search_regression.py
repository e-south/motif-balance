from __future__ import annotations

import json
from pathlib import Path

from motif_balance import design
from motif_balance.formats.design import load_design_spec


def test_annealed_search_snapshot_is_stable_under_current_semantics() -> None:
    root = Path(__file__).resolve().parents[2]
    fixture = json.loads((root / "tests/fixtures/search/annealed-multistart-v1.json").read_text())
    portfolio = design(load_design_spec(root / fixture["fixture"]))
    expected = fixture["expected"]

    candidates = [
        {
            "candidate_id": item.candidate_id,
            "rank": str(item.rank),
            "sequence": item.sequence,
            "length": str(len(item.sequence)),
            "balance_score": format(item.balance_score, ".17g"),
        }
        for item in portfolio.candidates
    ]
    diagnostics = portfolio.manifest.search_diagnostics

    assert portfolio.problem_id == expected["problem_id"]
    assert portfolio.manifest.search_engine == expected["search_engine"]
    assert portfolio.manifest.search_engine_version == expected["search_engine_version"]
    assert portfolio.manifest.evaluation_count == expected["evaluation_count"]
    assert portfolio.manifest.unique_evaluations == expected["unique_evaluations"]
    assert diagnostics.best_score == expected["best_score"]
    assert list(diagnostics.restart_final_scores) == expected["restart_final_scores"]
    assert [item.model_dump(mode="json") for item in diagnostics.proposals] == expected[
        "proposal_summaries"
    ]
    assert candidates == expected["candidates"]
