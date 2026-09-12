"""Immutable scanned matches, evaluations, and selected candidates."""

from __future__ import annotations

import hashlib
import math
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from motif_balance.constants import (
    DNA_ALPHABET,
)

from .base import FrozenModel


def candidate_id_for_sequence(sequence: str) -> str:
    """Return the compact deterministic join identity for one candidate sequence."""

    return f"candidate-{hashlib.sha256(sequence.encode()).hexdigest()[:16]}"


class MotifMatch(FrozenModel):
    motif_id: str
    start: Annotated[int, Field(strict=True, ge=0)]
    end: Annotated[int, Field(strict=True, gt=0)]
    strand: Literal["+", "-"]
    matched_sequence: str
    raw_score: Annotated[float, Field(strict=True)]
    normalized_score: Annotated[float, Field(strict=True, ge=0.0)]
    spec_direction: Literal["seek", "avoid"] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    spec_satisfaction: (
        Annotated[float, Field(strict=True, ge=0.0, le=1.0, allow_inf_nan=False)] | None
    ) = Field(default=None, exclude_if=lambda value: value is None)

    @model_validator(mode="after")
    def validate_coordinates(self) -> Self:
        if self.end <= self.start:
            raise ValueError("match end must be greater than start")
        if self.end - self.start != len(self.matched_sequence):
            raise ValueError("match coordinates must equal matched-sequence width")
        if set(self.matched_sequence) - set(DNA_ALPHABET):
            raise ValueError("matched_sequence must contain only A, C, G, and T")
        if not math.isfinite(self.raw_score) or not math.isfinite(self.normalized_score):
            raise ValueError("match scores must be finite")
        if (self.spec_direction is None) != (self.spec_satisfaction is None):
            raise ValueError("specification direction and satisfaction must be declared together")
        if self.spec_satisfaction is not None:
            expected = (
                self.normalized_score
                if self.spec_direction == "seek"
                else 1.0 - self.normalized_score
            )
            if not math.isclose(self.spec_satisfaction, expected, abs_tol=1.0e-12):
                raise ValueError(
                    "specification satisfaction does not match direction and attainment"
                )
        return self


class Evaluation(FrozenModel):
    sequence: str
    balance_score: Annotated[float, Field(strict=True, ge=0.0)]
    matches: tuple[MotifMatch, ...]
    avoidance_matches: tuple[MotifMatch, ...] = ()
    constraint_status: Literal["feasible", "infeasible"] = "feasible"
    max_avoidance_excess: Annotated[float, Field(strict=True, ge=0.0)] = 0.0
    total_avoidance_excess: Annotated[float, Field(strict=True, ge=0.0)] = 0.0

    @model_validator(mode="after")
    def validate_balance(self) -> Self:
        if set(self.sequence) - set(DNA_ALPHABET):
            raise ValueError("sequence must contain only A, C, G, and T")
        if not self.matches:
            raise ValueError("evaluation must contain at least one motif match")
        has_directional = any(match.spec_satisfaction is not None for match in self.matches)
        if has_directional and any(match.spec_satisfaction is None for match in self.matches):
            raise ValueError("directional evaluations require satisfaction for every specification")
        weakest = min(
            match.spec_satisfaction
            if match.spec_satisfaction is not None
            else match.normalized_score
            for match in self.matches
        )
        if not math.isclose(self.balance_score, weakest, abs_tol=1.0e-12):
            raise ValueError("balance_score must equal the weakest specification satisfaction")
        target_ids = {match.motif_id for match in self.matches}
        avoider_ids = {match.motif_id for match in self.avoidance_matches}
        if len(target_ids) != len(self.matches) or len(avoider_ids) != len(self.avoidance_matches):
            raise ValueError("evaluation contains duplicate motif match identifiers")
        if target_ids & avoider_ids:
            raise ValueError("target and avoider matches must be disjoint")
        if not self.avoidance_matches and (
            self.constraint_status != "feasible"
            or self.max_avoidance_excess != 0.0
            or self.total_avoidance_excess != 0.0
        ):
            raise ValueError("an evaluation without avoiders must be constraint feasible")
        return self

    @property
    def constraint_feasible(self) -> bool:
        return self.constraint_status == "feasible"

    @property
    def limiting_specification_ids(self) -> tuple[str, ...]:
        return tuple(
            match.motif_id
            for match in self.matches
            if math.isclose(
                match.spec_satisfaction
                if match.spec_satisfaction is not None
                else match.normalized_score,
                self.balance_score,
                abs_tol=1.0e-12,
            )
        )


class Candidate(FrozenModel):
    candidate_id: str = Field(pattern=r"^candidate-[0-9a-f]{16}$")
    rank: Annotated[int, Field(strict=True, gt=0)]
    sequence: str
    balance_score: Annotated[float, Field(strict=True, ge=0.0)]
    matches: tuple[MotifMatch, ...]
    avoidance_matches: tuple[MotifMatch, ...] = ()
    constraint_status: Literal["feasible", "infeasible"] = "feasible"
    max_avoidance_excess: Annotated[float, Field(strict=True, ge=0.0)] = 0.0
    total_avoidance_excess: Annotated[float, Field(strict=True, ge=0.0)] = 0.0

    @model_validator(mode="after")
    def validate_candidate(self) -> Self:
        Evaluation(
            sequence=self.sequence,
            balance_score=self.balance_score,
            matches=self.matches,
            avoidance_matches=self.avoidance_matches,
            constraint_status=self.constraint_status,
            max_avoidance_excess=self.max_avoidance_excess,
            total_avoidance_excess=self.total_avoidance_excess,
        )
        return self

    @property
    def constraint_feasible(self) -> bool:
        return self.constraint_status == "feasible"

    @property
    def limiting_specification_ids(self) -> tuple[str, ...]:
        return self.as_evaluation().limiting_specification_ids

    def as_evaluation(self) -> Evaluation:
        return Evaluation(
            sequence=self.sequence,
            balance_score=self.balance_score,
            matches=self.matches,
            avoidance_matches=self.avoidance_matches,
            constraint_status=self.constraint_status,
            max_avoidance_excess=self.max_avoidance_excess,
            total_avoidance_excess=self.total_avoidance_excess,
        )
