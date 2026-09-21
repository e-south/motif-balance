"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/model/search.py

Compact checkpoints and search diagnostics, without proposal history.

Module Author(s): Eric J. South
Dunlop Lab
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import math
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from .base import FrozenModel

SearchInitialization = Literal["related", "independent"]
SearchMethod = Literal["annealed", "greedy", "random"]


class SearchCheckpoint(FrozenModel):
    evaluations: Annotated[int, Field(gt=0)]
    best_score: Annotated[float, Field(ge=0.0)]
    specification_satisfactions: tuple[CheckpointSpecificationSatisfaction, ...] = Field(
        default=(), exclude_if=lambda value: not value
    )
    limiting_specification_ids: tuple[str, ...] = Field(
        default=(), exclude_if=lambda value: not value
    )


class CheckpointSpecificationSatisfaction(FrozenModel):
    motif_id: str = Field(min_length=1)
    direction: Literal["seek", "avoid"]
    attainment: Annotated[float, Field(strict=True, ge=0.0, le=1.0, allow_inf_nan=False)]
    satisfaction: Annotated[float, Field(strict=True, ge=0.0, le=1.0, allow_inf_nan=False)]

    @model_validator(mode="after")
    def validate_satisfaction(self) -> Self:
        expected = self.attainment if self.direction == "seek" else 1.0 - self.attainment
        if not math.isclose(self.satisfaction, expected, abs_tol=1.0e-12):
            raise ValueError("checkpoint satisfaction does not match direction and attainment")
        return self


class ProposalSummary(FrozenModel):
    move: Literal["single", "block", "multi", "insertion"]
    attempted: Annotated[int, Field(ge=0)]
    accepted: Annotated[int, Field(ge=0)]

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        if self.accepted > self.attempted:
            raise ValueError("accepted proposal count cannot exceed attempted count")
        return self


class SearchDiagnostics(FrozenModel):
    schema_version: Literal["search-diagnostics/v4"] = "search-diagnostics/v4"
    restarts: Annotated[int, Field(gt=0)]
    best_score: Annotated[float, Field(ge=0.0)]
    checkpoints: tuple[SearchCheckpoint, ...]
    restart_final_scores: tuple[Annotated[float, Field(ge=0.0)], ...]
    proposals: tuple[ProposalSummary, ...]

    @model_validator(mode="after")
    def validate_diagnostics(self) -> Self:
        if not self.checkpoints:
            raise ValueError("search diagnostics must contain at least one checkpoint")
        if len(self.restart_final_scores) != self.restarts:
            raise ValueError("restart_final_scores must contain one score per restart")
        previous_evaluations = 0
        previous_best = -math.inf
        for checkpoint in self.checkpoints:
            if checkpoint.evaluations <= previous_evaluations:
                raise ValueError("search checkpoints must have increasing evaluation counts")
            if checkpoint.best_score + 1.0e-12 < previous_best:
                raise ValueError("search checkpoint best scores cannot decrease")
            previous_evaluations = checkpoint.evaluations
            previous_best = checkpoint.best_score
            if not checkpoint.specification_satisfactions:
                raise ValueError(
                    "search-diagnostics/v4 checkpoints require specification satisfactions"
                )
            if not checkpoint.limiting_specification_ids:
                raise ValueError(
                    "search-diagnostics/v4 checkpoints require limiting specifications"
                )
            motif_ids = tuple(item.motif_id for item in checkpoint.specification_satisfactions)
            if motif_ids != tuple(sorted(motif_ids)) or len(motif_ids) != len(set(motif_ids)):
                raise ValueError("checkpoint specification satisfactions must be unique and sorted")
            if not math.isclose(
                checkpoint.best_score,
                min(item.satisfaction for item in checkpoint.specification_satisfactions),
                abs_tol=1.0e-12,
            ):
                raise ValueError(
                    "checkpoint best score must equal its weakest specification satisfaction"
                )
            expected_limiting = tuple(
                item.motif_id
                for item in checkpoint.specification_satisfactions
                if math.isclose(
                    item.satisfaction,
                    checkpoint.best_score,
                    abs_tol=1.0e-12,
                )
            )
            if checkpoint.limiting_specification_ids != expected_limiting:
                raise ValueError(
                    "checkpoint limiting specifications must exactly match its weakest "
                    "specification satisfactions"
                )
        if not math.isclose(self.checkpoints[-1].best_score, self.best_score, abs_tol=1.0e-12):
            raise ValueError("final checkpoint must equal the diagnostic best score")
        moves = [proposal.move for proposal in self.proposals]
        if len(moves) != len(set(moves)):
            raise ValueError("search proposal summaries must have unique move names")
        return self
