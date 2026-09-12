"""Immutable, path-free records for a pre-search seek-pair assessment."""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from motif_balance.constants import MAX_PAIR_ASSESSMENT_BASE_OPERATIONS, MAX_SEQUENCE_LENGTH

from .base import FrozenModel

_NonnegativeInt = Annotated[int, Field(strict=True, ge=0)]
_PositiveInt = Annotated[int, Field(strict=True, gt=0)]
_Score = Annotated[float, Field(strict=True, ge=0, le=1, allow_inf_nan=False)]


def assessment_work_bound(
    left_width: int, right_width: int, length: int, strands: str
) -> tuple[int, int]:
    """Count relative arrangements and bound compared base preferences, not CPU instructions."""
    count = (2 * length - left_width - right_width + 1) * (2 if strands == "both" else 1)
    return count, 4 * (left_width + right_width + count * min(left_width, right_width))


class AssessedMotif(FrozenModel):
    motif_id: str
    model_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    width: Annotated[int, Field(strict=True, gt=0, le=MAX_SEQUENCE_LENGTH)]
    zero_range_columns: tuple[_NonnegativeInt, ...]

    @model_validator(mode="after")
    def validate_columns(self) -> Self:
        if tuple(sorted(set(self.zero_range_columns))) != self.zero_range_columns or any(
            column >= self.width for column in self.zero_range_columns
        ):
            raise ValueError("zero-range columns must be distinct, ordered, and within the motif")
        return self


class PairArrangement(FrozenModel):
    left_start: _NonnegativeInt
    right_start: _NonnegativeInt
    left_strand: Literal["+"] = "+"
    right_strand: Literal["+", "-"]
    overlap_bases: _NonnegativeInt
    structural_score: _Score


class PairAssessment(FrozenModel):
    schema_version: Literal["pair-assessment/v1"] = "pair-assessment/v1"
    formula: Literal["information_weighted_shared_base_conflict_v1"] = (
        "information_weighted_shared_base_conflict_v1"
    )
    scope: Literal["seek_pair_arrangements"] = "seek_pair_arrangements"
    length: Annotated[int, Field(strict=True, gt=0, le=MAX_SEQUENCE_LENGTH)]
    strands: Literal["forward", "both"]
    motifs: tuple[AssessedMotif, AssessedMotif]
    equivalence: Literal["translation", "translation_and_reverse_complement"]
    effective_information_bits: Annotated[float, Field(strict=True, gt=0, allow_inf_nan=False)]
    base_operation_upper_bound: Annotated[
        int, Field(strict=True, gt=0, le=MAX_PAIR_ASSESSMENT_BASE_OPERATIONS)
    ]
    sequence_evaluations: Literal[0] = 0
    arrangement_count: _PositiveInt
    arrangements: tuple[PairArrangement, ...] = Field(
        min_length=1, max_length=4 * MAX_SEQUENCE_LENGTH
    )
    structural_score: _Score
    best_arrangement_index: _NonnegativeInt

    @model_validator(mode="after")
    def validate_projection(self) -> Self:
        left, right = (motif.width for motif in self.motifs)
        count, operations = assessment_work_bound(left, right, self.length, self.strands)
        if (
            max(left, right) > self.length
            or count != self.arrangement_count
            or len(self.arrangements) != count
            or operations != self.base_operation_upper_bound
            or self.effective_information_bits > 2 * (left + right)
        ):
            raise ValueError("pair assessment dimensions, counts, or work bound disagree")
        equivalence = (
            "translation" if self.strands == "forward" else "translation_and_reverse_complement"
        )
        if self.equivalence != equivalence:
            raise ValueError("pair assessment equivalence differs from strand policy")
        expected = (
            (max(0, -offset), max(0, offset), strand)
            for strand in (("+",) if self.strands == "forward" else ("+", "-"))
            for offset in range(-(self.length - left), self.length - right + 1)
        )
        for arrangement, key in zip(self.arrangements, expected, strict=True):
            a, b, _strand = key
            overlap = max(0, min(a + left, b + right) - max(a, b))
            if (
                arrangement.left_start,
                arrangement.right_start,
                arrangement.right_strand,
            ) != key or arrangement.overlap_bases != overlap:
                raise ValueError("pair assessment must retain each legal relative arrangement once")
        best = min(
            range(count),
            key=lambda i: (
                -self.arrangements[i].structural_score,
                self.arrangements[i].left_start,
                self.arrangements[i].right_start,
                self.arrangements[i].right_strand,
            ),
        )
        if (
            self.best_arrangement_index != best
            or self.structural_score != self.arrangements[best].structural_score
        ):
            raise ValueError(
                "pair assessment best score or deterministic best arrangement disagrees"
            )
        return self

    @property
    def best_arrangement(self) -> PairArrangement:
        """One deterministically chosen best arrangement, not a designed sequence."""
        return self.arrangements[self.best_arrangement_index]
