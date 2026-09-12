"""Immutable ranked representatives of supplied selected-match architectures."""

from __future__ import annotations

import math
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from motif_balance.constants import (
    DNA_COMPLEMENT,
    MAX_ARCHITECTURE_DISTANCE_BASE_BUDGET,
    MAX_ARCHITECTURE_DISTANCE_PAIRS,
    MAX_ARCHITECTURE_POOL_RECORDS,
    MAX_ARCHITECTURE_PREPARED_PAIRS,
)

from .base import FrozenModel
from .design import DesignSpec
from .evaluation import Evaluation

_Count = Annotated[int, Field(strict=True, ge=0)]
_Positive = Annotated[int, Field(strict=True, gt=0)]
_Score = Annotated[float, Field(strict=True, ge=0, le=1, allow_inf_nan=False)]
_Distance = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]
ArchitectureKey = tuple[
    tuple[str, Annotated[int, Field(strict=True)], Literal["same", "opposite"]], ...
]


def architecture_distance_work(count: int, spec: DesignSpec) -> tuple[int, int, int]:
    """Return representative pairs, conservative base terms, and prepared motif pairs."""
    pairs = count * (count - 1) // 2
    motifs = len(spec.specifications)
    terms = pairs * (spec.length * (4 if spec.strands == "both" else 2) + motifs * (motifs - 1))
    prepared = count * motifs * (motifs - 1) // 2 if pairs else 0
    return pairs, terms, prepared


def validate_architecture_spec(spec: DesignSpec) -> None:
    if not isinstance(spec, DesignSpec) or spec.schema_version != "design-spec/v3":
        raise ValueError("architecture ranking requires a current directional design specification")
    if len(spec.specifications) < 2:
        raise ValueError("architecture ranking requires at least two motif specifications")
    if spec.min_distance is not None and spec.min_distance > 0:
        raise ValueError("architecture ranking does not enforce a minimum sequence distance")


def architecture_key(evaluation: Evaluation, *, both: bool) -> ArchitectureKey:
    """Relative selected sites, invariant to translation and permitted global reversal."""
    anchor, *others = evaluation.matches
    sign = -1 if both and anchor.strand == "-" else 1
    return tuple(
        (
            match.motif_id,
            sign * (match.start + match.end - anchor.start - anchor.end),
            "same" if match.strand == anchor.strand else "opposite",
        )
        for match in others
    )


class ArchitectureRepresentative(FrozenModel):
    rank: _Positive
    evaluation: Evaluation
    geometry: ArchitectureKey
    sequence_classes: _Positive


class ArchitecturePrefix(FrozenModel):
    architecture_count: _Positive
    minimum_balance: _Score
    mean_sequence_distance: _Score | None
    mean_selected_footprint_distance: _Score | None
    mean_spacing_distance_nt: _Distance | None
    mean_orientation_difference: _Score | None

    @model_validator(mode="after")
    def validate_pair_support(self) -> Self:
        distances = (
            self.mean_sequence_distance,
            self.mean_selected_footprint_distance,
            self.mean_spacing_distance_nt,
            self.mean_orientation_difference,
        )
        if any((value is None) != (self.architecture_count == 1) for value in distances):
            raise ValueError(
                "pairwise diversity is defined exactly when at least two architectures are included"
            )
        return self


class ArchitectureRanking(FrozenModel):
    schema_version: Literal["architecture-ranking/v2"] = "architecture-ranking/v2"
    spec: DesignSpec
    pool_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    coverage: Literal["supplied_pool"] = "supplied_pool"
    realization_policy: Literal["canonical_literal_then_selected_match_scoring"] = (
        "canonical_literal_then_selected_match_scoring"
    )
    input_records: Annotated[int, Field(strict=True, ge=0, le=MAX_ARCHITECTURE_POOL_RECORDS)]
    literal_sequences: _Count
    sequence_classes: _Count
    scoring_evaluations: _Count
    search_evaluations: Literal[0] = 0
    distance_base_budget: Annotated[
        int, Field(strict=True, gt=0, le=MAX_ARCHITECTURE_DISTANCE_BASE_BUDGET)
    ]
    distance_base_operations: _Count
    representatives: tuple[ArchitectureRepresentative, ...]
    prefixes: tuple[ArchitecturePrefix, ...]

    @model_validator(mode="after")
    def validate_ranking(self) -> Self:
        validate_architecture_spec(self.spec)
        pairs, terms, prepared = architecture_distance_work(len(self.representatives), self.spec)
        if (
            self.distance_base_operations != terms
            or terms > self.distance_base_budget
            or pairs > MAX_ARCHITECTURE_DISTANCE_PAIRS
            or prepared > MAX_ARCHITECTURE_PREPARED_PAIRS
        ):
            raise ValueError("architecture distance accounting or admission disagrees")
        if not (
            self.scoring_evaluations
            == self.sequence_classes
            <= self.literal_sequences
            <= self.input_records
            and len(self.representatives) == len(self.prefixes) <= self.sequence_classes
            and sum(row.sequence_classes for row in self.representatives) == self.sequence_classes
            and bool(self.input_records) == bool(self.sequence_classes)
        ):
            raise ValueError("architecture ranking counts disagree")
        both = self.spec.strands == "both"
        if self.literal_sequences > self.sequence_classes * (2 if both else 1):
            raise ValueError("sequence counts disagree with strand equivalence")
        seen, order = set(), []
        for rank, (representative, prefix) in enumerate(
            zip(self.representatives, self.prefixes, strict=True), 1
        ):
            evaluation = representative.evaluation
            if (
                representative.rank != rank
                or prefix.architecture_count != rank
                or prefix.minimum_balance != evaluation.balance_score
                or representative.geometry != architecture_key(evaluation, both=both)
                or representative.geometry in seen
            ):
                raise ValueError("architecture rank, geometry, or quality disagrees")
            seen.add(representative.geometry)
            sequence = evaluation.sequence
            if len(sequence) != self.spec.length or (
                both and sequence > sequence.translate(DNA_COMPLEMENT)[::-1]
            ):
                raise ValueError("representative must be fixed-length canonical DNA")
            if (
                len(evaluation.matches) != len(self.spec.specifications)
                or evaluation.avoidance_matches
            ):
                raise ValueError("representative specifications disagree")
            for match, item in zip(evaluation.matches, self.spec.specifications, strict=True):
                if (
                    match.motif_id != item.motif.motif_id
                    or match.spec_direction != item.direction
                    or match.end > self.spec.length
                    or match.end - match.start != item.motif.width
                    or (not both and match.strand != "+")
                ):
                    raise ValueError("representative match differs from the specification")
                word = sequence[match.start : match.end]
                if match.strand == "-":
                    word = word.translate(DNA_COMPLEMENT)[::-1]
                if word != match.matched_sequence:
                    raise ValueError("representative matched word differs from its sequence")
            weakest = min(
                match.spec_satisfaction
                for match in evaluation.matches
                if match.spec_satisfaction is not None
            )
            if not math.isclose(evaluation.balance_score, weakest, rel_tol=0, abs_tol=1e-12):
                raise ValueError("representative balance differs from its weakest requirement")
            if (
                prefix.mean_spacing_distance_nt is not None
                and prefix.mean_spacing_distance_nt > self.spec.length
            ):
                raise ValueError("spacing distance exceeds sequence length")
            order.append((-evaluation.balance_score, sequence))
        if order != sorted(order) or len(set(order)) != len(order):
            raise ValueError(
                "architecture representatives must have a unique deterministic quality order"
            )
        return self

    @property
    def quality_steps(self) -> tuple[ArchitecturePrefix, ...]:
        """Include every tied architecture at each observed quality breakpoint."""
        return tuple(
            row
            for index, row in enumerate(self.prefixes)
            if index + 1 == len(self.prefixes)
            or row.minimum_balance != self.prefixes[index + 1].minimum_balance
        )

    def select(self, count: int) -> tuple[Evaluation, ...]:
        """Return an exact ranked prefix without searching, editing, or rescoring."""
        if type(count) is not int or not 1 <= count <= len(self.representatives):
            raise ValueError(
                f"count must be an integer from 1 to {len(self.representatives)}; "
                "the supplied pool does not support a larger architecture collection"
            )
        return tuple(row.evaluation for row in self.representatives[:count])
