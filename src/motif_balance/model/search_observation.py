"""Bounded, opt-in observations of an unchanged directional search."""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from .base import FrozenModel
from .design import DesignSpec
from .evaluation import Evaluation

UnitScore = Annotated[float, Field(strict=True, ge=0.0, le=1.0, allow_inf_nan=False)]
Count = Annotated[int, Field(strict=True, ge=0)]


class ObservationSpec(FrozenModel):
    """Observation budgets are separate from scientific search inputs and RNG."""

    max_snapshots: Annotated[int, Field(strict=True, ge=2, le=256)] = 32
    score_targets: Annotated[tuple[UnitScore, ...], Field(max_length=32)] = ()
    quality_thresholds: Annotated[tuple[UnitScore, ...], Field(max_length=16)] = ()
    max_sequences_per_threshold: Annotated[int, Field(strict=True, ge=1, le=256)] = 64

    @model_validator(mode="after")
    def validate_targets(self) -> Self:
        if tuple(sorted(set(self.score_targets))) != self.score_targets:
            raise ValueError("score targets must be unique and increasing")
        if tuple(sorted(set(self.quality_thresholds))) != self.quality_thresholds:
            raise ValueError("quality thresholds must be unique and increasing")
        return self


class ChainState(FrozenModel):
    chain_id: Count
    evaluation: Evaluation


class SearchSnapshot(FrozenModel):
    """Post-transition states at the actual evaluation count, not a fictitious path."""

    evaluations: Annotated[int, Field(strict=True, gt=0)]
    incumbent: Evaluation
    states: Annotated[tuple[ChainState, ...], Field(max_length=8)]

    @model_validator(mode="after")
    def validate_states(self) -> Self:
        if tuple(row.chain_id for row in self.states) != tuple(range(len(self.states))):
            raise ValueError("snapshot chain identities must be complete and ordered")
        if any(
            row.evaluation.balance_score > self.incumbent.balance_score + 1e-12
            for row in self.states
        ):
            raise ValueError("a current state cannot exceed the incumbent")
        return self


class TargetHit(FrozenModel):
    target: UnitScore
    first_evaluation: Annotated[int, Field(strict=True, gt=0)] | None


class ObservedMoveCounts(FrozenModel):
    move: Literal["single", "block", "multi", "insertion"]
    attempted: Count
    accepted: Count
    changed: Count
    improved: Count
    decreased: Count

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        if not self.improved + self.decreased <= self.changed <= self.accepted <= self.attempted:
            raise ValueError("inconsistent observation move counts")
        return self


class QualitySample(FrozenModel):
    """Hash-ranked distinct sequences with balance >= threshold; thresholds overlap."""

    threshold: UnitScore
    qualifying_evaluations: Count
    unique_sequences: Count
    evaluations: Annotated[tuple[Evaluation, ...], Field(max_length=256)]

    @model_validator(mode="after")
    def validate_sample(self) -> Self:
        if not len(self.evaluations) <= self.unique_sequences <= self.qualifying_evaluations:
            raise ValueError("inconsistent quality sample counts")
        if len({row.sequence for row in self.evaluations}) != len(self.evaluations):
            raise ValueError("quality sample sequences must be distinct")
        if any(row.balance_score < self.threshold for row in self.evaluations):
            raise ValueError("quality sample contains a sequence below its threshold")
        return self


class SearchObservation(FrozenModel):
    schema_version: Literal["search-observation/v2"] = "search-observation/v2"
    spec: DesignSpec
    observation_spec: ObservationSpec
    engine: str
    engine_version: str
    evaluation_count: Annotated[int, Field(strict=True, gt=0)]
    snapshots: Annotated[tuple[SearchSnapshot, ...], Field(min_length=1, max_length=256)]
    target_hits: Annotated[tuple[TargetHit, ...], Field(max_length=32)]
    moves: Annotated[tuple[ObservedMoveCounts, ...], Field(max_length=4)]
    quality_samples: Annotated[tuple[QualitySample, ...], Field(max_length=16)]

    @model_validator(mode="after")
    def validate_observation(self) -> Self:
        if self.spec.schema_version != "design-spec/v3":
            raise ValueError("search observations require directional design-spec/v3")
        if len(self.snapshots) > self.observation_spec.max_snapshots:
            raise ValueError("observation exceeds its snapshot limit")
        if self.snapshots[-1].evaluations != self.evaluation_count:
            raise ValueError("final snapshot must equal evaluation count")
        previous_count, previous_score = 0, -1.0
        chains = len(self.snapshots[0].states)
        for frame in self.snapshots:
            if (
                frame.evaluations <= previous_count
                or frame.incumbent.balance_score < previous_score
            ):
                raise ValueError("snapshot evaluations must increase and incumbent cannot decrease")
            if len(frame.states) != chains:
                raise ValueError("snapshot chain identities cannot change")
            for evaluation in (frame.incumbent, *(state.evaluation for state in frame.states)):
                if len(evaluation.sequence) != self.spec.length:
                    raise ValueError("snapshot sequence length does not match the design")
                if any(match.spec_direction is None for match in evaluation.matches):
                    raise ValueError("snapshots require directional evaluations")
            previous_count, previous_score = frame.evaluations, frame.incumbent.balance_score
        if tuple(hit.target for hit in self.target_hits) != self.observation_spec.score_targets:
            raise ValueError("target-hit rows must match declared targets")
        for hit in self.target_hits:
            if hit.first_evaluation is not None and hit.first_evaluation > self.evaluation_count:
                raise ValueError("target-hit time exceeds the evaluation budget")
            if (hit.first_evaluation is None) != (hit.target > previous_score):
                raise ValueError("target-hit status contradicts the final incumbent")
        if len({row.move for row in self.moves}) != len(self.moves):
            raise ValueError("observation move identities must be unique")
        if (
            tuple(row.threshold for row in self.quality_samples)
            != self.observation_spec.quality_thresholds
        ):
            raise ValueError("quality samples must match declared thresholds")
        previous_qualifying, previous_unique = self.evaluation_count, self.evaluation_count
        for sample in self.quality_samples:
            if (
                sample.qualifying_evaluations > previous_qualifying
                or sample.unique_sequences > previous_unique
            ):
                raise ValueError("quality sample counts cannot increase with threshold")
            capacity = self.observation_spec.max_sequences_per_threshold
            if len(sample.evaluations) != min(sample.unique_sequences, capacity):
                raise ValueError("quality sample must fill its declared capacity when supported")
            if any(len(row.sequence) != self.spec.length for row in sample.evaluations):
                raise ValueError("quality sample sequence length does not match the design")
            previous_qualifying = sample.qualifying_evaluations
            previous_unique = sample.unique_sequences
        return self
