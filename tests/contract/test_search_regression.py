from __future__ import annotations

import json
from pathlib import Path

from motif_balance import DesignSpec, design


def test_explicit_v2_search_preserves_frozen_semantics() -> None:
    root = Path(__file__).resolve().parents[2]
    fixture = json.loads((root / "tests/fixtures/search/annealed-multistart-v1.json").read_text())
    assert fixture["schema_version"] == "annealed-search-regression/v2"
    spec = DesignSpec.model_validate(fixture["specification"])
    assert spec.schema_version == "design-spec/v2"
    portfolio = design(spec)
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
    assert (
        list(diagnostics.restart_final_constraint_statuses)
        == expected["restart_final_constraint_statuses"]
    )
    assert [item.model_dump(mode="json") for item in diagnostics.proposals] == expected[
        "proposal_summaries"
    ]
    assert candidates == expected["candidates"]
