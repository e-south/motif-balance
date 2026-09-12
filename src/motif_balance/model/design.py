"""Directional request semantics and pre-search resource admission."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Any, Literal, Self

from pydantic import Field, field_validator, model_validator

from motif_balance.constants import (
    DEFAULT_ELITE_CAPACITY,
    DIRECTIONAL_OBJECTIVE_SEMANTICS,
    LEGACY_SCORING_SEMANTICS,
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


class AvoidanceConstraint(FrozenModel):
    """One hard upper bound on the best normalized score of an avoider motif."""

    motif: MotifModel
    score_ceiling: Annotated[float, Field(strict=True, ge=0.0, le=1.0, allow_inf_nan=False)]


class MotifSpecification(FrozenModel):
    """One motif model and its directional design intent."""

    motif: MotifModel
    direction: Literal["seek", "avoid"]


class DesignSpec(FrozenModel):
    schema_version: Literal["design-spec/v1", "design-spec/v2", "design-spec/v3"] = "design-spec/v2"
    motifs: tuple[MotifModel, ...] = Field(default=(), exclude_if=lambda value: not value)
    specifications: tuple[MotifSpecification, ...] = Field(
        default=(), exclude_if=lambda value: not value
    )
    avoiders: tuple[AvoidanceConstraint, ...] = Field(
        default=(), exclude_if=lambda value: not value
    )
    length: Annotated[int, Field(strict=True, gt=0, le=MAX_SEQUENCE_LENGTH)]
    count: Annotated[int, Field(strict=True, gt=0, le=MAX_CANDIDATE_COUNT)]
    strands: Literal["forward", "both"] = "both"
    evaluations: Annotated[int, Field(strict=True, gt=0, le=MAX_EVALUATIONS)]
    seed: Annotated[int, Field(strict=True, ge=0)]
    min_distance: Annotated[float, Field(strict=True, ge=0.0, le=1.0)] | None = None
    scoring_semantics: Literal["normalized_llr_v1", "relative_pwm_attainment_v2"] = (
        SCORING_SEMANTICS
    )
    objective_semantics: Literal["weakest_score_v1", "weakest_directional_satisfaction_v1"] = (
        OBJECTIVE_SEMANTICS
    )
    tie_break_semantics: Literal["leftmost_plus_first_v1"] = TIE_BREAK_SEMANTICS

    @model_validator(mode="before")
    @classmethod
    def canonicalize_motif_mapping(cls, value: Any) -> Any:
        if not isinstance(value, Mapping):
            return value
        result = dict(value)
        if "schema_version" not in result and result.get("specifications"):
            result["schema_version"] = "design-spec/v3"
        if result.get("schema_version") == "design-spec/v3" and "objective_semantics" not in result:
            result["objective_semantics"] = DIRECTIONAL_OBJECTIVE_SEMANTICS
        if "schema_version" not in result and result.get("avoiders"):
            result["schema_version"] = "design-spec/v2"
        motifs = result.get("motifs")
        if isinstance(motifs, Mapping):
            canonical: list[object] = []
            for key in sorted(motifs):
                if not isinstance(key, str):
                    raise ValueError("motif keys must be strings")
                motif = motifs[key]
                motif_id: str | None
                if isinstance(motif, MotifModel):
                    motif_id = motif.motif_id
                elif isinstance(motif, Mapping):
                    raw_motif_id = motif.get("motif_id")
                    motif_id = raw_motif_id if isinstance(raw_motif_id, str) else None
                else:
                    motif_id = None
                if motif_id != key:
                    raise ValueError(
                        f"motif key '{key}' does not match model motif_id '{motif_id}'"
                    )
                canonical.append(motif)
            result["motifs"] = tuple(canonical)
        avoiders = result.get("avoiders")
        if isinstance(avoiders, Mapping):
            canonical_avoiders: list[object] = []
            for key in sorted(avoiders):
                if not isinstance(key, str):
                    raise ValueError("avoider keys must be strings")
                constraint = avoiders[key]
                if not isinstance(constraint, Mapping):
                    raise ValueError(f"avoider '{key}' must be a constraint mapping")
                motif = constraint.get("motif")
                avoider_motif_id: str | None
                if isinstance(motif, MotifModel):
                    avoider_motif_id = motif.motif_id
                elif isinstance(motif, Mapping):
                    raw_motif_id = motif.get("motif_id")
                    avoider_motif_id = raw_motif_id if isinstance(raw_motif_id, str) else None
                else:
                    avoider_motif_id = None
                if avoider_motif_id != key:
                    raise ValueError(
                        f"avoider key '{key}' does not match model motif_id '{avoider_motif_id}'"
                    )
                canonical_avoiders.append(constraint)
            result["avoiders"] = tuple(canonical_avoiders)
        return result

    @field_validator("motifs")
    @classmethod
    def validate_motifs(cls, value: tuple[MotifModel, ...]) -> tuple[MotifModel, ...]:
        ordered = tuple(sorted(value, key=lambda motif: motif.motif_id))
        ids = [motif.motif_id for motif in ordered]
        if len(ids) != len(set(ids)):
            raise ValueError("motif identifiers must be unique")
        return ordered

    @field_validator("avoiders")
    @classmethod
    def validate_avoiders(
        cls, value: tuple[AvoidanceConstraint, ...]
    ) -> tuple[AvoidanceConstraint, ...]:
        ordered = tuple(sorted(value, key=lambda item: item.motif.motif_id))
        ids = [item.motif.motif_id for item in ordered]
        if len(ids) != len(set(ids)):
            raise ValueError("avoider motif identifiers must be unique")
        return ordered

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
        if self.schema_version == "design-spec/v3":
            if self.motifs:
                raise ValueError(
                    "design-spec/v3 uses specifications; migrate motifs to direction 'seek'"
                )
            if self.avoiders:
                raise ValueError(
                    "design-spec/v3 cannot mix directional specifications "
                    "with legacy hard avoidance"
                )
            if not self.specifications:
                raise ValueError("design-spec/v3 requires at least one motif specification")
            if self.objective_semantics != DIRECTIONAL_OBJECTIVE_SEMANTICS:
                raise ValueError(
                    "design-spec/v3 requires objective_semantics "
                    f"'{DIRECTIONAL_OBJECTIVE_SEMANTICS}'"
                )
        else:
            if self.specifications:
                raise ValueError("directional specifications require design-spec/v3")
            if not self.motifs:
                raise ValueError("motifs must contain at least one model")
            if self.objective_semantics != OBJECTIVE_SEMANTICS:
                raise ValueError(
                    f"{self.schema_version} requires objective_semantics '{OBJECTIVE_SEMANTICS}'"
                )
        if self.schema_version == "design-spec/v1" and self.avoiders:
            raise ValueError("design-spec/v1 cannot declare avoiders")
        expected_scoring = (
            LEGACY_SCORING_SEMANTICS
            if self.schema_version == "design-spec/v1"
            else SCORING_SEMANTICS
        )
        expected_motif_schema = (
            "motif-model/v1" if self.schema_version == "design-spec/v1" else "motif-model/v2"
        )
        if self.scoring_semantics != expected_scoring:
            raise ValueError(
                f"{self.schema_version} requires scoring_semantics '{expected_scoring}'"
            )
        all_motifs = (*self.scored_motifs, *(item.motif for item in self.avoiders))
        if any(motif.schema_version != expected_motif_schema for motif in all_motifs):
            raise ValueError(
                f"{self.schema_version} requires motifs using '{expected_motif_schema}'"
            )
        target_ids = {motif.motif_id for motif in self.scored_motifs}
        avoider_ids = {item.motif.motif_id for item in self.avoiders}
        if target_ids & avoider_ids:
            raise ValueError("target and avoider motif identifiers must be disjoint")
        if self.count > self.evaluations:
            raise ValueError("evaluations must be at least count")
        motif_count = len(self.scored_motifs) + len(self.avoiders)
        if self.count * motif_count > MAX_BUNDLE_ROWS:
            raise ValueError("count times motif count exceeds the canonical match-row limit")
        if self.count * self.length > MAX_PORTFOLIO_BASES:
            raise ValueError("count times length exceeds the canonical portfolio-base limit")
        strand_factor = 2 if self.strands == "both" else 1
        scored_motifs = (*self.scored_motifs, *(item.motif for item in self.avoiders))
        score_operations = self.evaluations * sum(
            (self.length - motif.width + 1) * motif.width * strand_factor
            for motif in scored_motifs
            if motif.width <= self.length
        )
        if score_operations > MAX_SCORE_BASE_OPERATIONS:
            raise ValueError("design exceeds the score-operation limit")
        if self.evaluations * self.length > MAX_EVALUATED_BASES:
            raise ValueError("evaluations times length exceeds the evaluated-base limit")
        if self.schema_version == "design-spec/v3":
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
        if self.schema_version == "design-spec/v3":
            return tuple(item.motif for item in self.specifications)
        return self.motifs

    @property
    def specification_directions(self) -> tuple[Literal["seek", "avoid"], ...]:
        if self.schema_version == "design-spec/v3":
            return tuple(item.direction for item in self.specifications)
        return tuple("seek" for _ in self.motifs)
