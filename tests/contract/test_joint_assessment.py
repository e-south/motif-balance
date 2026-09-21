"""
--------------------------------------------------------------------------------
motif-balance
tests/contract/test_joint_assessment.py

Exact small joint arrangements differ from constituent-pair agreement.

Module Author(s): Eric J. South
Dunlop Lab
--------------------------------------------------------------------------------
"""

from itertools import combinations, product
from math import log2

import pytest

from motif_balance import MotifModel
from motif_balance.errors import IncompatibleDesign
from tests.contract.test_pair_assessment import motif


def test_pairwise_agreement_does_not_imply_joint_agreement():
    from motif_balance.assessment import assess_motifs, assess_pair

    models = tuple(
        MotifModel(
            motif_id=f"m{i}",
            probabilities=(tuple(0.4 if b in allowed else 0.1 for b in "ACGT"),),
            background=(0.25,) * 4,
        )
        for i, allowed in enumerate(("AC", "CG", "AG"))
    )
    assert all(
        assess_pair(a, b, length=1, strands="forward").structural_score == 1
        for a, b in combinations(models, 2)
    )
    result = assess_motifs(models, length=1, strands="forward")
    assert result.structural_score == pytest.approx(2 / 3)
    assert result.arrangement_count == 1
    assert result.proof == "exact_minimum_over_admitted_arrangements"
    assert result.sequence_evaluations == 0
    assert result.best_arrangement.starts == (0, 0, 0)
    assert result.best_arrangement.strands == ("+", "+", "+")


@pytest.mark.parametrize("strands", ["forward", "both"])
def test_joint_scope_agrees_with_pair_authority_and_removes_only_valid_symmetries(strands):
    from motif_balance.assessment import assess_motifs, assess_pair

    models = (motif("AAA", "a"), motif("CC", "b"))
    for length in (3, 4, 5, 6):
        joint = assess_motifs(models, length=length, strands=strands)
        pair = assess_pair(*models, length=length, strands=strands)
        assert joint.structural_score == pytest.approx(pair.structural_score)
        assert joint.arrangement_count == pair.arrangement_count
        assert joint.effective_information_bits == pair.effective_information_bits


def test_length_and_orientation_controls_and_four_motif_scope():
    from motif_balance.assessment import assess_motifs

    models = tuple(motif(word, f"m{i}") for i, word in enumerate(("AA", "TT", "AA", "TT")))
    assert assess_motifs(models, length=2, strands="forward").structural_score == pytest.approx(0.5)
    assert assess_motifs(models, length=2, strands="both").structural_score == 1
    assert assess_motifs(models, length=4, strands="forward").structural_score == 1
    assert assess_motifs(
        models[::-1], length=3, strands="forward"
    ).structural_score == pytest.approx(0.75)


@pytest.mark.parametrize("fault", ["cardinality", "duplicate", "length", "strand", "work"])
def test_joint_admission_precedes_compilation(fault, monkeypatch):
    from motif_balance import assessment
    from motif_balance.assessment import joint

    models = tuple(motif("AA", f"m{i}") for i in range(3))
    length, strands = 3, "both"
    if fault == "cardinality":
        models = models * 2
    elif fault == "duplicate":
        models = models[:1] * 3
    elif fault == "length":
        length = True
    elif fault == "strand":
        strands = "reverse"
    else:
        length = 10_000
    monkeypatch.setattr(
        joint, "column_regret", lambda *_: pytest.fail("inadmissible joint request compiled")
    )
    with pytest.raises(IncompatibleDesign):
        assessment.assess_motifs(models, length=length, strands=strands)


@pytest.mark.parametrize("strands", ["forward", "both"])
def test_joint_minimum_matches_independent_complete_dna_enumeration(strands):
    """Maximize summed weighted preferences over all DNA, not the balance score."""
    from motif_balance.assessment import assess_motifs

    models = (
        motif("AC", "a"),
        MotifModel(
            motif_id="b",
            probabilities=((0.4, 0.3, 0.2, 0.1), (0.1, 0.1, 0.7, 0.1)),
            background=(0.4, 0.3, 0.2, 0.1),
        ),
        motif("GT", "c"),
    )
    terms, total = [], 0.0
    for model in models:
        columns = []
        for probabilities in model.probabilities:
            odds = [log2(p / b) for p, b in zip(probabilities, model.background, strict=True)]
            span = max(odds) - min(odds)
            weight = 1 + sum(p * log2(p) for p in probabilities) / 2 if span else 0
            columns.append([weight * (x - min(odds)) / span if span else 0 for x in odds])
            total += weight
        terms.append(columns)
    best = 0.0
    for dna in product(range(4), repeat=3):
        summed = 0.0
        for columns in terms:
            oriented = [columns]
            if strands == "both":
                oriented.append([row[::-1] for row in columns[::-1]])
            summed += max(
                sum(row[dna[start + i]] for i, row in enumerate(matrix))
                for matrix in oriented
                for start in range(3 - len(columns) + 1)
            )
        best = max(best, summed / total)
    result = assess_motifs(models, length=3, strands=strands)
    assert result.structural_score == pytest.approx(best, abs=1e-12)
    assert result.motifs[1].zero_range_columns == (0,)


@pytest.mark.parametrize(
    "fault", ["count", "operations", "length", "starts", "strands", "equivalence", "ids", "proof"]
)
def test_joint_result_rejects_inconsistent_scope_and_placements(fault):
    from pydantic import ValidationError

    from motif_balance.assessment import JointAssessment, assess_motifs

    result = assess_motifs(
        tuple(motif("AA", f"m{i}") for i in range(3)), length=3, strands="forward"
    )
    payload = result.model_dump(mode="json")
    assert JointAssessment.model_validate_json(result.model_dump_json()) == result
    if fault == "count":
        payload["arrangement_count"] += 1
    elif fault == "operations":
        payload["base_operation_upper_bound"] += 1
    elif fault == "length":
        payload["length"] = "3"
    elif fault == "starts":
        payload["best_arrangement"]["starts"] = [0, 0, 2]
    elif fault == "strands":
        payload["best_arrangement"]["strands"] = ["+", "+", "-"]
    elif fault == "equivalence":
        payload["equivalence"] = "translation_and_reverse_complement"
    elif fault == "ids":
        payload["motifs"][1]["motif_id"] = "m0"
    else:
        payload["proof"] = "best_found"
    with pytest.raises(ValidationError):
        JointAssessment.model_validate(payload)
