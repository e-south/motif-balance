"""
--------------------------------------------------------------------------------
motif-balance
tests/contract/test_scoring.py

Verify scoring behavior.

Module Author(s): Eric J. South
Dunlop Lab
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import math

import pytest

from motif_balance import DesignSpec, MotifModel, MotifSpecification, score
from motif_balance.compile import compile_design
from motif_balance.errors import IncompatibleDesign, InvalidSequence
from motif_balance.scoring import evaluate


def test_relative_pwm_attainment_uses_attainable_score_extrema() -> None:
    motif = MotifModel(
        motif_id="single",
        probabilities=((0.7, 0.1, 0.1, 0.1),),
        background=(0.25, 0.25, 0.25, 0.25),
    )
    spec = DesignSpec(
        specifications=(MotifSpecification(motif=motif, direction="seek"),),
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
        specifications=(MotifSpecification(motif=motif, direction="seek"),),
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
            specifications=(MotifSpecification(motif=motif, direction="seek"),),
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
            specifications=(MotifSpecification(motif=motif, direction="seek"),),
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


def test_best_match_ties_are_leftmost_then_plus() -> None:
    motif = MotifModel(
        motif_id="tie",
        probabilities=((0.4, 0.1, 0.1, 0.4),),
        background=(0.25, 0.25, 0.25, 0.25),
    )
    spec = DesignSpec(
        specifications=(MotifSpecification(motif=motif, direction="seek"),),
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
        specifications=(MotifSpecification(motif=motif, direction="seek"),),
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


@pytest.mark.parametrize(
    ("direction", "expected"),
    [
        ("seek", 0.0),
        ("avoid", 1.0),
    ],
)
def test_scoring_does_not_require_a_feasible_portfolio(direction: str, expected: float) -> None:
    from motif_balance import design

    models = tuple(
        MotifModel(
            motif_id=name,
            probabilities=(tuple(0.7 if base == preferred else 0.1 for base in "ACGT"),),
            background=(0.25,) * 4,
        )
        for name, preferred in (("a", "A"), ("c", "C"))
    )
    requirements = {
        "specifications": (
            MotifSpecification(motif=models[0], direction="seek"),
            MotifSpecification(motif=models[1], direction=direction),
        )
    }
    spec = DesignSpec.model_validate(
        {
            "schema_version": "design-spec/v3",
            **requirements,
            "length": 2,
            "count": 17,
            "evaluations": 17,
            "strands": "forward",
            "seed": 7,
            "min_distance": 0.5,
        }
    )
    before = spec.model_dump_json()
    # AA contains an optimal A match and no preferred C. The 17-candidate
    # portfolio is impossible in the 16-sequence space, but scoring is not search.
    evaluation = score("aa", spec)
    assert evaluation.sequence == "AA"
    assert [match.normalized_score for match in evaluation.matches] == [1.0, 0.0]
    assert evaluation.balance_score == expected
    assert spec.model_dump_json() == before
    with pytest.raises(IncompatibleDesign, match="count exceeds the complete sequence space"):
        design(spec)


def test_scoring_rejects_wrong_length_and_alphabet(pairwise_spec: DesignSpec) -> None:
    with pytest.raises(InvalidSequence, match="exactly 4"):
        score("ACG", pairwise_spec)
    with pytest.raises(InvalidSequence, match="A, C, G, and T"):
        score("ACNT", pairwise_spec)


@pytest.mark.parametrize("sequence", [None, True, 123, b"ACGT", ["A", "C", "G", "T"]])
def test_scoring_reports_nontext_input_as_invalid_sequence(
    sequence: object, pairwise_spec: DesignSpec
) -> None:
    with pytest.raises(InvalidSequence, match="DNA string") as failure:
        score(sequence, pairwise_spec)  # type: ignore[arg-type]
    assert failure.value.code == "invalid_sequence"
    assert failure.value.field == "sequence"
    assert failure.value.hint


def test_compile_rejects_numerically_unstable_probability_ratios() -> None:
    smallest = float.fromhex("0x0.0000000000001p-1022")
    motif = MotifModel(
        motif_id="unstable",
        probabilities=((1.0 - 3 * smallest, smallest, smallest, smallest),),
        background=(smallest, 0.25, 0.25, 0.5),
    )
    spec = DesignSpec(
        specifications=(MotifSpecification(motif=motif, direction="seek"),),
        length=1,
        count=1,
        strands="forward",
        evaluations=1,
        seed=1,
    )

    with pytest.raises(IncompatibleDesign, match="non-finite log-odds"):
        compile_design(spec)
