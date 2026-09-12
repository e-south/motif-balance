"""Pre-search assessment uses explicit motif arrangements, not searched sequences."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from motif_balance import MotifModel
from motif_balance.errors import IncompatibleDesign


def motif(word: str, name: str) -> MotifModel:
    return MotifModel(
        motif_id=name,
        probabilities=tuple(
            tuple(0.7 if base == preferred else 0.1 for base in "ACGT") for preferred in word
        ),
        background=(0.25, 0.25, 0.25, 0.25),
    )


def test_pair_assessment_explains_conflict_space_and_reverse_orientation() -> None:
    from motif_balance.assessment import assess_pair

    left, right = motif("AAA", "left"), motif("CCC", "right")
    profiles = [assess_pair(left, right, length=n, strands="forward") for n in range(3, 7)]
    assert [p.structural_score for p in profiles] == pytest.approx([0.5, 2 / 3, 5 / 6, 1])
    assert [p.arrangement_count for p in profiles] == [1, 3, 5, 7]
    assert [p.length for p in profiles] == [3, 4, 5, 6]
    assert profiles[0].best_arrangement.left_start == 0
    assert profiles[0].best_arrangement.right_start == 0
    assert profiles[-1].best_arrangement.overlap_bases == 0
    assert profiles[0].motifs[0].model_digest == left.model_digest
    assert profiles[0].sequence_evaluations == 0

    reversed_pair = assess_pair(left, motif("TTT", "reverse"), length=3, strands="both")
    assert reversed_pair.structural_score == 1
    assert reversed_pair.arrangement_count == 2
    assert reversed_pair.best_arrangement.right_strand == "-"
    assert [a.structural_score for a in reversed_pair.arrangements] == pytest.approx([0.5, 1.0])


def test_nonuniform_background_constant_columns_have_no_artificial_conflict() -> None:
    from motif_balance.assessment import assess_pair

    background = (0.4, 0.3, 0.2, 0.1)
    left = MotifModel(
        motif_id="left",
        probabilities=(background, (0.7, 0.1, 0.1, 0.1)),
        background=background,
    )
    right = MotifModel.model_validate({**left.model_dump(), "motif_id": "right"})
    result = assess_pair(left, right, length=2)
    assert result.structural_score == 1
    assert result.motifs[0].zero_range_columns == (0,)
    assert result.motifs[1].zero_range_columns == (0,)
    # Only the second position contributes information to the conflict score.
    assert result.effective_information_bits == pytest.approx(1.286440701105921)


@pytest.mark.parametrize("length", [True, "3", 3.0, 0, -1, 2, 10_001])
def test_assessment_rejects_invalid_lengths_before_compilation(length, monkeypatch) -> None:
    from motif_balance import assessment

    def unexpected_compile(_model):
        pytest.fail("invalid assessment reached matrix compilation")

    monkeypatch.setattr(assessment, "_compile_motif", unexpected_compile)
    with pytest.raises(IncompatibleDesign, match="length"):
        assessment.assess_pair(motif("AAA", "a"), motif("CCC", "b"), length=length)


@pytest.mark.parametrize("strands", [None, True, "reverse", "BOTH"])
def test_assessment_rejects_unknown_strands(strands) -> None:
    from motif_balance.assessment import assess_pair

    with pytest.raises(IncompatibleDesign, match="strands"):
        assess_pair(motif("A", "a"), motif("C", "b"), length=1, strands=strands)


def test_assessment_rejects_unqualified_models_and_zero_information() -> None:
    from motif_balance.assessment import assess_pair

    a = motif("A", "a")
    with pytest.raises(IncompatibleDesign, match="MotifModel"):
        assess_pair(a.model_dump(), a, length=1)
    old = MotifModel.model_validate({**a.model_dump(), "schema_version": "motif-model/v1"})
    with pytest.raises(IncompatibleDesign, match="motif-model/v2"):
        assess_pair(old, a, length=1)
    # Uniform probabilities can have log-odds variation under a nonuniform
    # background, but supply no information under this descriptor's reference.
    unweighted = MotifModel(
        motif_id="unweighted",
        probabilities=((0.25, 0.25, 0.25, 0.25),),
        background=(0.4, 0.3, 0.2, 0.1),
    )
    with pytest.raises(IncompatibleDesign, match="positive effective information"):
        assess_pair(unweighted, unweighted, length=1)


def test_assessment_bounds_work_before_compiling_or_building_arrangements(monkeypatch) -> None:
    from motif_balance import assessment

    def unexpected_compile(_model):
        pytest.fail("over-limit assessment reached matrix compilation")

    monkeypatch.setattr(assessment, "_compile_motif", unexpected_compile)
    a = motif("A" * 1_000, "a")
    with pytest.raises(IncompatibleDesign, match="operation limit"):
        assessment.assess_pair(a, a, length=10_000)


@pytest.mark.parametrize(
    "fault",
    [
        "count",
        "missing",
        "duplicate",
        "outside",
        "overlap",
        "best",
        "score",
        "equivalence",
        "work",
        "columns",
    ],
)
def test_assessment_record_rejects_inconsistent_projections(fault) -> None:
    from motif_balance.assessment import PairAssessment, assess_pair

    result = assess_pair(motif("AA", "a"), motif("CC", "b"), length=3)
    payload = result.model_dump(mode="json")
    if fault == "count":
        payload["arrangement_count"] += 1
    elif fault == "missing":
        payload["arrangements"].pop()
    elif fault == "duplicate":
        payload["arrangements"][1] = payload["arrangements"][0]
    elif fault == "outside":
        payload["arrangements"][0]["left_start"] = 3
    elif fault == "overlap":
        payload["arrangements"][0]["overlap_bases"] = 0
    elif fault == "best":
        payload["best_arrangement_index"] = 100
    elif fault == "score":
        payload["structural_score"] = 0.99
    elif fault == "equivalence":
        payload["equivalence"] = "translation"
    elif fault == "work":
        payload["base_operation_upper_bound"] = 1
    else:
        payload["motifs"][0]["zero_range_columns"] = [0, 0]
    with pytest.raises(ValidationError):
        PairAssessment.model_validate(payload)


def test_assessment_record_is_strict_frozen_and_round_trips() -> None:
    from motif_balance.assessment import PairAssessment, assess_pair

    result = assess_pair(motif("AA", "a"), motif("CC", "b"), length=3)
    assert PairAssessment.model_validate_json(result.model_dump_json()) == result
    with pytest.raises(ValidationError):
        result.structural_score = 0.1
    with pytest.raises(ValidationError):
        PairAssessment.model_validate({**result.model_dump(), "length": "3"})
    with pytest.raises(ValidationError):
        PairAssessment.model_validate({**result.model_dump(), "predicted_balance": 0.9})
