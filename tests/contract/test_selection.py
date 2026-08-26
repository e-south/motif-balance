from __future__ import annotations

import pytest

from motif_balance.errors import SearchExhausted
from motif_balance.model import Evaluation, MotifMatch
from motif_balance.selection import normalized_hamming_distance, select_candidates


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


def test_selection_is_score_descending_then_lexicographic() -> None:
    selected = select_candidates(
        (
            _evaluation("TT", 0.8),
            _evaluation("AA", 0.8),
            _evaluation("CC", 0.7),
        ),
        count=2,
        min_distance=None,
        evaluations_used=3,
    )
    assert [candidate.sequence for candidate in selected] == ["AA", "TT"]
    assert [candidate.rank for candidate in selected] == [1, 2]


def test_selection_enforces_observable_distance_and_exact_count() -> None:
    evaluations = (
        _evaluation("AAAA", 0.9),
        _evaluation("AAAT", 0.8),
        _evaluation("TTTT", 0.7),
    )
    selected = select_candidates(
        evaluations,
        count=2,
        min_distance=0.5,
        evaluations_used=3,
    )
    assert [candidate.sequence for candidate in selected] == ["AAAA", "TTTT"]
    assert normalized_hamming_distance(*[candidate.sequence for candidate in selected]) == 1.0

    with pytest.raises(SearchExhausted) as raised:
        select_candidates(
            evaluations,
            count=3,
            min_distance=0.5,
            evaluations_used=3,
        )
    assert raised.value.requested_count == 3
    assert raised.value.valid_count == 2


def test_selection_finds_feasible_subset_when_top_ranked_candidate_blocks_it() -> None:
    selected = select_candidates(
        (
            _evaluation("AAAA", 0.9),
            _evaluation("AATT", 0.8),
            _evaluation("TTAA", 0.7),
        ),
        count=2,
        min_distance=0.75,
        evaluations_used=3,
    )

    assert [candidate.sequence for candidate in selected] == ["AATT", "TTAA"]
