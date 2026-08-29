from __future__ import annotations

import itertools
import math

import numpy as np
import pytest

from motif_balance import DesignSpec, MotifModel, score
from motif_balance.compile import _null_mean, compile_design
from motif_balance.errors import IncompatibleDesign, InvalidSequence
from motif_balance.scoring import evaluate


def test_relative_pwm_attainment_uses_attainable_score_extrema() -> None:
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

    compiled = problem.motifs[0]

    assert compiled.score_min == pytest.approx(math.log2(0.1 / 0.25))
    assert compiled.score_max == pytest.approx(math.log2(0.7 / 0.25))
    assert compiled.probability_consensus == "A"
    assert compiled.score_maximizing_sequence == "A"
    assert evaluate("A", problem).matches[0].normalized_score == pytest.approx(1.0)
    assert evaluate("C", problem).matches[0].normalized_score == pytest.approx(0.0)


def test_probability_consensus_is_distinct_from_score_maximizing_reference() -> None:
    motif = MotifModel(
        motif_id="background_sensitive",
        probabilities=((0.45, 0.40, 0.10, 0.05),),
        background=(0.80, 0.10, 0.05, 0.05),
    )
    spec = DesignSpec(
        motifs=(motif,),
        length=1,
        count=1,
        strands="forward",
        evaluations=4,
        seed=1,
    )
    compiled = compile_design(spec).motifs[0]

    assert compiled.probability_consensus == "A"
    assert compiled.score_maximizing_sequence == "C"
    assert evaluate("C", compile_design(spec)).matches[0].normalized_score == pytest.approx(1.0)


def test_v2_relative_attainment_fails_closed_outside_tolerance() -> None:
    motif = MotifModel(
        motif_id="bounded",
        probabilities=((0.7, 0.1, 0.1, 0.1),),
        background=(0.25, 0.25, 0.25, 0.25),
    )
    problem = compile_design(
        DesignSpec(
            motifs=(motif,),
            length=1,
            count=1,
            strands="forward",
            evaluations=4,
            seed=1,
        )
    )
    forged = problem.motifs[0]
    object.__setattr__(forged, "score_max", forged.score_max - 1.0)

    with pytest.raises(ValueError, match="outside the attainable range"):
        evaluate("A", problem)


@pytest.mark.parametrize(("excursion", "expected"), [(-5.0e-13, 0.0), (5.0e-13, 1.0)])
def test_v2_relative_attainment_snaps_only_endpoint_roundoff(
    excursion: float,
    expected: float,
) -> None:
    motif = MotifModel(
        motif_id="roundoff",
        probabilities=((0.7, 0.1, 0.1, 0.1),),
        background=(0.25, 0.25, 0.25, 0.25),
    )
    problem = compile_design(
        DesignSpec(
            motifs=(motif,),
            length=1,
            count=1,
            strands="forward",
            evaluations=4,
            seed=1,
        )
    )
    compiled = problem.motifs[0]
    sequence = "C" if expected == 0.0 else "A"
    raw = math.log2((0.1 if sequence == "C" else 0.7) / 0.25)
    denominator = compiled.score_max - compiled.score_min
    if expected == 0.0:
        object.__setattr__(compiled, "score_min", raw - excursion * denominator)
    else:
        object.__setattr__(
            compiled,
            "score_max",
            compiled.score_min + (raw - compiled.score_min) / (1.0 + excursion),
        )

    assert evaluate(sequence, problem).matches[0].normalized_score == expected


def test_explicit_v1_scoring_remains_readable_without_v2_reinterpretation() -> None:
    motif = MotifModel(
        schema_version="motif-model/v1",
        motif_id="legacy",
        probabilities=((0.7, 0.1, 0.1, 0.1),),
        background=(0.25, 0.25, 0.25, 0.25),
    )
    spec = DesignSpec(
        schema_version="design-spec/v1",
        motifs=(motif,),
        length=1,
        count=1,
        strands="forward",
        evaluations=4,
        seed=1,
        scoring_semantics="normalized_llr_v1",
    )

    assert evaluate("C", compile_design(spec)).matches[0].normalized_score == 0.0


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
    with pytest.raises(InvalidSequence, match="exactly 4"):
        score("ACG", pairwise_spec)
    with pytest.raises(InvalidSequence, match="A, C, G, and T"):
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
