"""Assess seek-pair base conflicts without generating or scoring DNA sequences."""

from __future__ import annotations

from typing import Literal

import numpy as np

from motif_balance.compile import _compile_motif
from motif_balance.constants import MAX_PAIR_ASSESSMENT_BASE_OPERATIONS, MAX_SEQUENCE_LENGTH
from motif_balance.errors import IncompatibleDesign
from motif_balance.model import MotifModel
from motif_balance.model.assessment import (
    AssessedMotif,
    PairArrangement,
    PairAssessment,
    assessment_work_bound,
)

__all__ = ["PairAssessment", "assess_pair"]


def _admit(left: MotifModel, right: MotifModel, length: int, strands: str) -> int:
    if not isinstance(left, MotifModel) or not isinstance(right, MotifModel):
        raise IncompatibleDesign("assess_pair requires two validated MotifModel values")
    if any(model.schema_version != "motif-model/v2" for model in (left, right)):
        raise IncompatibleDesign("pair assessment requires motif-model/v2 inputs")
    if type(length) is not int or not max(left.width, right.width) <= length <= MAX_SEQUENCE_LENGTH:
        raise IncompatibleDesign(
            f"length must be an integer from the widest motif through {MAX_SEQUENCE_LENGTH}",
            field="length",
            hint="Choose an admitted fixed length containing both motif windows.",
        )
    if strands not in ("forward", "both"):
        raise IncompatibleDesign("strands must be forward or both", field="strands")
    _, operations = assessment_work_bound(left.width, right.width, length, strands)
    if operations > MAX_PAIR_ASSESSMENT_BASE_OPERATIONS:
        raise IncompatibleDesign(
            "pair assessment exceeds its base-operation limit",
            field="length",
            hint="Use a smaller admitted length; no arrangements have been calculated.",
        )
    return operations


def _terms(model: MotifModel) -> tuple[np.ndarray, float, AssessedMotif]:
    odds = _compile_motif(model).log_odds
    spans = np.ptp(odds, axis=1)
    preferences = np.divide(
        odds - odds.min(axis=1)[:, None],
        spans[:, None],
        out=np.ones_like(odds),
        where=spans[:, None] > 0,
    )
    probabilities = np.asarray(model.probabilities, dtype=float)
    weights = np.clip(1 + np.sum(probabilities * np.log2(probabilities), axis=1) / 2, 0, 1)
    # A background-shaped column has no score preference, even when its entropy
    # differs from the uniform reference. It cannot create a base conflict.
    weights[spans == 0] = 0
    return (
        weights[:, None] * (1 - preferences),
        float(weights.sum()),
        AssessedMotif(
            motif_id=model.motif_id,
            model_digest=model.model_digest,
            width=model.width,
            zero_range_columns=tuple(int(i) for i in np.flatnonzero(spans == 0)),
        ),
    )


def assess_pair(
    left: MotifModel,
    right: MotifModel,
    *,
    length: int,
    strands: Literal["forward", "both"] = "both",
) -> PairAssessment:
    """Return information-weighted conflict for every relative seek arrangement.

    Length limits the allowed offsets. Translation-equivalent placements are
    counted once; with both strands, reverse-complement-equivalent placements
    are also counted once by fixing the left motif to the forward strand.
    The result is not a calibrated outcome prediction, sequence score, optimum
    bound, or estimate of how many sequence solutions exist.
    """
    operations = _admit(left, right, length, strands)
    a, weight_a, reference_a = _terms(left)
    b, weight_b, reference_b = _terms(right)
    total_weight = weight_a + weight_b
    if total_weight <= 0:
        raise IncompatibleDesign(
            "pair assessment requires positive effective information",
            hint="The uniform-entropy descriptor is undefined for these motif columns.",
        )
    arrangements = []
    orientations: tuple[tuple[Literal["+", "-"], np.ndarray], ...] = (
        (("+", b),) if strands == "forward" else (("+", b), ("-", b[::-1, ::-1]))
    )
    for strand, oriented in orientations:
        for offset in range(-(length - left.width), length - right.width + 1):
            left_start, right_start = max(0, -offset), max(0, offset)
            first = max(left_start, right_start)
            last = min(left_start + left.width, right_start + right.width)
            overlap = max(0, last - first)
            regret = 0.0
            if overlap:
                shared = (
                    a[first - left_start : last - left_start]
                    + oriented[first - right_start : last - right_start]
                )
                regret = float(shared.min(axis=1).sum())
            arrangements.append(
                PairArrangement(
                    left_start=left_start,
                    right_start=right_start,
                    right_strand=strand,
                    overlap_bases=overlap,
                    structural_score=float(np.clip(1 - regret / total_weight, 0, 1)),
                )
            )
    best = min(
        range(len(arrangements)),
        key=lambda i: (
            -arrangements[i].structural_score,
            arrangements[i].left_start,
            arrangements[i].right_start,
            arrangements[i].right_strand,
        ),
    )
    return PairAssessment(
        length=length,
        strands=strands,
        motifs=(reference_a, reference_b),
        equivalence="translation" if strands == "forward" else "translation_and_reverse_complement",
        effective_information_bits=2 * total_weight,
        base_operation_upper_bound=operations,
        arrangement_count=len(arrangements),
        arrangements=tuple(arrangements),
        structural_score=arrangements[best].structural_score,
        best_arrangement_index=best,
    )
