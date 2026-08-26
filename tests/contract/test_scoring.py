from __future__ import annotations

import itertools
import math

import numpy as np
import pytest

from motif_balance import DesignSpec, MotifModel, score
from motif_balance.compile import _null_mean, compile_design
from motif_balance.errors import IncompatibleDesign
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


def test_null_mean_matches_explicit_small_distribution_without_materializing_it() -> None:
    probabilities = np.asarray(
        (
            (0.61, 0.17, 0.13, 0.09),
            (0.11, 0.53, 0.19, 0.17),
            (0.07, 0.23, 0.59, 0.11),
        ),
        dtype=np.float64,
    )
    background = np.asarray((0.1, 0.2, 0.3, 0.4), dtype=np.float64)
    log_odds = np.log2(probabilities / background)
    scale = 1000.0 / math.log(2.0)
    discretized = np.round(log_odds * scale).astype(np.int64)
    explicit = 0.0
    for bases in itertools.product(range(4), repeat=len(probabilities)):
        probability = math.prod(float(background[base]) for base in bases)
        score = sum(int(discretized[position, base]) for position, base in enumerate(bases))
        explicit += probability * score / scale

    assert _null_mean(log_odds, background) == pytest.approx(explicit, abs=1.0e-14)


def test_compile_rejects_numerically_unstable_probability_ratios() -> None:
    smallest = float.fromhex("0x0.0000000000001p-1022")
    motif = MotifModel(
        motif_id="unstable",
        probabilities=((1.0 - 3 * smallest, smallest, smallest, smallest),),
        background=(smallest, 0.25, 0.25, 0.5),
    )
    spec = DesignSpec(
        motifs=(motif,),
        length=1,
        count=1,
        strands="forward",
        evaluations=1,
        seed=1,
    )

    with pytest.raises(IncompatibleDesign, match="non-finite log-odds"):
        compile_design(spec)
