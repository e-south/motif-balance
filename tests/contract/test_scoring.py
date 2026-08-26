from __future__ import annotations

import pytest

from motif_balance import DesignSpec, MotifModel, score
from motif_balance.compile import compile_design
from motif_balance.scoring import evaluate


def test_normalized_llr_is_one_at_consensus_and_zero_below_null_mean() -> None:
    motif = MotifModel(
        motif_id="single",
        probabilities=((0.7, 0.1, 0.1, 0.1),),
        background=(0.25, 0.25, 0.25, 0.25),
    )
    spec = DesignSpec(
        motifs=(motif,),
        length=1,
        count=1,
        strands="forward",
        evaluations=4,
        seed=1,
    )
    problem = compile_design(spec)

    assert evaluate("A", problem).matches[0].normalized_score == pytest.approx(1.0)
    assert evaluate("C", problem).matches[0].normalized_score == 0.0


def test_best_match_ties_are_leftmost_then_plus() -> None:
    motif = MotifModel(
        motif_id="tie",
        probabilities=((0.4, 0.1, 0.1, 0.4),),
        background=(0.25, 0.25, 0.25, 0.25),
    )
    spec = DesignSpec(
        motifs=(motif,),
        length=2,
        count=1,
        strands="both",
        evaluations=4,
        seed=1,
    )
    match = evaluate("AT", compile_design(spec)).matches[0]

    assert (match.start, match.end, match.strand) == (0, 1, "+")
    assert match.matched_sequence == "A"


def test_reverse_match_reports_candidate_coordinates_and_motif_orientation() -> None:
    motif = MotifModel(
        motif_id="reverse",
        probabilities=((0.7, 0.1, 0.1, 0.1), (0.1, 0.7, 0.1, 0.1)),
        background=(0.25, 0.25, 0.25, 0.25),
    )
    spec = DesignSpec(
        motifs=(motif,),
        length=3,
        count=1,
        strands="both",
        evaluations=8,
        seed=1,
    )
    match = evaluate("GTT", compile_design(spec)).matches[0]

    assert (match.start, match.end, match.strand) == (0, 2, "-")
    assert match.matched_sequence == "AC"


def test_public_score_uses_same_authoritative_evaluator(pairwise_spec: DesignSpec) -> None:
    evaluation = score("ACGT", pairwise_spec)
    assert evaluation.balance_score == min(match.normalized_score for match in evaluation.matches)


def test_scoring_rejects_wrong_length_and_alphabet(pairwise_spec: DesignSpec) -> None:
    with pytest.raises(ValueError, match="exactly 4"):
        score("ACG", pairwise_spec)
    with pytest.raises(ValueError, match="A, C, G, and T"):
        score("ACNT", pairwise_spec)
