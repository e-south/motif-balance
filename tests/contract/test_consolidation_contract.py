from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

import motif_balance
import motif_balance.api as api
import motif_balance.inspection as inspection
import motif_balance.selection as selection
from motif_balance import DesignSpec, MotifModel, design
from motif_balance.errors import (
    ArtifactError,
    PortfolioInfeasible,
    SearchBudgetExhausted,
    SelectionLimitReached,
)
from motif_balance.model import Evaluation, MotifMatch, PortfolioRecord
from motif_balance.selection import select_candidates


def _evaluation(sequence: str, score: float) -> Evaluation:
    match = MotifMatch(
        motif_id="fixture",
        start=0,
        end=1,
        strand="+",
        matched_sequence=sequence[0],
        raw_score=score,
        normalized_score=score,
    )
    return Evaluation(sequence=sequence, balance_score=score, matches=(match,))


def test_public_exports_are_deliberate_and_bounded() -> None:
    assert motif_balance.__all__ == [
        "Candidate",
        "DesignSpec",
        "MotifMatch",
        "MotifModel",
        "Portfolio",
        "design",
        "score",
    ]
    assert api.__all__ == ["design", "score"]
    assert inspection.__all__ == ["ResultInspection", "inspect_result"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("length", "4"),
        ("count", "3"),
        ("evaluations", "256"),
        ("seed", "7"),
        ("min_distance", "0.25"),
    ],
)
def test_scientific_spec_rejects_quoted_numeric_scalars(
    pairwise_spec: DesignSpec,
    field: str,
    value: str,
) -> None:
    payload = pairwise_spec.model_dump(mode="python")
    payload[field] = value

    with pytest.raises(ValidationError, match=field):
        DesignSpec.model_validate(payload)


def test_motif_model_rejects_quoted_probability_values() -> None:
    with pytest.raises(ValidationError, match="probabilities"):
        MotifModel.model_validate(
            {
                "motif_id": "fixture",
                "probabilities": (("0.7", 0.1, 0.1, 0.1),),
                "background": (0.25, 0.25, 0.25, 0.25),
            }
        )


def test_selection_limit_is_not_reported_as_infeasibility(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(selection, "SELECTION_NODE_LIMIT", 1)

    with pytest.raises(SelectionLimitReached) as raised:
        select_candidates(
            (_evaluation("AAAA", 0.9), _evaluation("TTTT", 0.8)),
            count=2,
            min_distance=0.5,
            evaluations_used=2,
        )

    assert raised.value.nodes_explored == 2
    assert raised.value.node_limit == 1
    assert raised.value.candidate_pool_size == 2
    assert raised.value.requested_count == 2
    assert raised.value.minimum_distance == 0.5
    assert "does not establish" in str(raised.value)


def test_exhaustion_and_evaluated_pool_infeasibility_are_distinct() -> None:
    with pytest.raises(SearchBudgetExhausted):
        select_candidates(
            (_evaluation("AAAA", 0.9),),
            count=2,
            min_distance=None,
            evaluations_used=4,
        )
    with pytest.raises(PortfolioInfeasible):
        select_candidates(
            (_evaluation("AAAA", 0.9), _evaluation("AAAT", 0.8)),
            count=2,
            min_distance=0.5,
            evaluations_used=4,
        )


def test_candidate_identifier_collision_fails_before_portfolio_construction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(selection, "_candidate_id", lambda _sequence: "candidate-" + "0" * 16)

    with pytest.raises(ArtifactError, match="candidate identifiers must be unique"):
        select_candidates(
            (_evaluation("AAAA", 0.9), _evaluation("TTTT", 0.8)),
            count=2,
            min_distance=None,
            evaluations_used=2,
        )


def test_portfolio_rejects_duplicate_candidate_identifiers(pairwise_spec: DesignSpec) -> None:
    portfolio = design(pairwise_spec)
    candidates = list(portfolio.candidates)
    candidates[1] = candidates[1].model_copy(update={"candidate_id": candidates[0].candidate_id})

    with pytest.raises(ValidationError, match="candidate identifiers must be unique"):
        PortfolioRecord.model_validate(
            portfolio.model_dump(mode="python") | {"candidates": tuple(candidates)}
        )


def test_result_catalog_is_not_part_of_the_product_package() -> None:
    package_root = Path(motif_balance.__file__).parent

    assert not (package_root / "inspection" / "catalog.py").exists()
    assert not hasattr(inspection, "ResultCatalog")
