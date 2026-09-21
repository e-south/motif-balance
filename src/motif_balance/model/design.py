"""Directional request semantics and pre-search resource admission.

Maintainer(s): Eric J. South, Dunlop Lab
"""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import Field, field_validator, model_validator

from motif_balance.constants import (
    DEFAULT_ELITE_CAPACITY,
    MAX_BUNDLE_ROWS,
    MAX_CANDIDATE_COUNT,
    MAX_DISTANCE_BASE_COMPARISONS,
    MAX_EVALUATED_BASES,
    MAX_EVALUATIONS,
    MAX_PORTFOLIO_BASES,
    MAX_RUN_MANIFEST_BYTES,
    MAX_SCORE_BASE_OPERATIONS,
    MAX_SEQUENCE_LENGTH,
    OBJECTIVE_SEMANTICS,
    SCORING_SEMANTICS,
    TIE_BREAK_SEMANTICS,
)

from .base import FrozenModel, _canonical_json
from .motif import MotifModel


class MotifSpecification(FrozenModel):
    """One motif model and its directional design intent."""

    motif: MotifModel
    direction: Literal["seek", "avoid"]


class DesignSpec(FrozenModel):
    schema_version: Literal["design-spec/v3"] = "design-spec/v3"
    specifications: tuple[MotifSpecification, ...]
    length: Annotated[int, Field(strict=True, gt=0, le=MAX_SEQUENCE_LENGTH)]
    count: Annotated[int, Field(strict=True, gt=0, le=MAX_CANDIDATE_COUNT)]
    strands: Literal["forward", "both"] = "both"
    evaluations: Annotated[int, Field(strict=True, gt=0, le=MAX_EVALUATIONS)]
    seed: Annotated[int, Field(strict=True, ge=0)]
    min_distance: Annotated[float, Field(strict=True, ge=0.0, le=1.0)] | None = None
    scoring_semantics: Literal["relative_pwm_attainment_v2"] = SCORING_SEMANTICS
    objective_semantics: Literal["weakest_directional_satisfaction_v1"] = OBJECTIVE_SEMANTICS
    tie_break_semantics: Literal["leftmost_plus_first_v1"] = TIE_BREAK_SEMANTICS

    @field_validator("specifications")
    @classmethod
    def validate_specifications(
        cls, value: tuple[MotifSpecification, ...]
    ) -> tuple[MotifSpecification, ...]:
        ordered = tuple(sorted(value, key=lambda item: item.motif.motif_id))
        ids = [item.motif.motif_id for item in ordered]
        if len(ids) != len(set(ids)):
            raise ValueError("specification motif identifiers must be unique")
        return ordered

    @model_validator(mode="after")
    def validate_budget(self) -> Self:
        if not self.specifications:
            raise ValueError("design-spec/v3 requires at least one motif specification")
        all_motifs = self.scored_motifs
        if any(motif.schema_version != "motif-model/v2" for motif in all_motifs):
            raise ValueError(f"{self.schema_version} requires motifs using 'motif-model/v2'")
        if self.count > self.evaluations:
            raise ValueError("evaluations must be at least count")
        motif_count = len(self.scored_motifs)
        if self.count * motif_count > MAX_BUNDLE_ROWS:
            raise ValueError("count times motif count exceeds the canonical match-row limit")
        if self.count * self.length > MAX_PORTFOLIO_BASES:
            raise ValueError("count times length exceeds the canonical portfolio-base limit")
        strand_factor = 2 if self.strands == "both" else 1
        scored_motifs = self.scored_motifs
        score_operations = self.evaluations * sum(
            (self.length - motif.width + 1) * motif.width * strand_factor
            for motif in scored_motifs
            if motif.width <= self.length
        )
        if score_operations > MAX_SCORE_BASE_OPERATIONS:
            raise ValueError("design exceeds the score-operation limit")
        if self.evaluations * self.length > MAX_EVALUATED_BASES:
            raise ValueError("evaluations times length exceeds the evaluated-base limit")
        elite_bound = min(DEFAULT_ELITE_CAPACITY, self.evaluations)
        space_bound = 1
        for _ in range(self.length):
            space_bound *= 4
            if space_bound >= elite_bound:
                break
        elite_bound = min(elite_bound, space_bound)
        identifier_sizes = [len(_canonical_json(motif.motif_id)) for motif in scored_motifs]
        # Conservative pretty-JSON allowances include keys, indentation, finite
        # float/integer spellings, and escaped identifiers. DNA words are ASCII.
        match_bytes = sum(
            1_024 + size + motif.width
            for size, motif in zip(identifier_sizes, scored_motifs, strict=True)
        )
        checkpoint_bytes = 512 + sum(512 + 2 * size for size in identifier_sizes)
        manifest_bound = (
            65_536
            + sum(1_024 + 3 * size for size in identifier_sizes)
            + elite_bound * (768 + self.length + match_bytes)
            + (self.evaluations.bit_length() + 1) * checkpoint_bytes
        )
        if manifest_bound > MAX_RUN_MANIFEST_BYTES:
            raise ValueError("design exceeds the conservative retained manifest-byte limit")
        if self.min_distance is not None and self.min_distance > 0.0:
            distance_comparisons = self.count * (self.count - 1) // 2 * self.length
            if distance_comparisons > MAX_DISTANCE_BASE_COMPARISONS:
                raise ValueError("design exceeds the distance-comparison limit")
        return self

    @property
    def scored_motifs(self) -> tuple[MotifModel, ...]:
        return tuple(item.motif for item in self.specifications)

    @property
    def specification_directions(self) -> tuple[Literal["seek", "avoid"], ...]:
        return tuple(item.direction for item in self.specifications)
