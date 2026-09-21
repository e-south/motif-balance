"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/model/selection.py

Define immutable policies and results for constrained selection from supplied DNA.

Module Author(s): Eric J. South
Dunlop Lab
--------------------------------------------------------------------------------
"""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from motif_balance.constants import (
    MAX_ARCHITECTURE_DISTANCE_BASE_BUDGET,
    MAX_ARCHITECTURE_DISTANCE_PAIRS,
    MAX_ARCHITECTURE_POOL_RECORDS,
    MAX_ARCHITECTURE_PREPARED_PAIRS,
    MAX_CANDIDATE_COUNT,
    MAX_DISTANCE_BASE_COMPARISONS,
    MAX_PORTFOLIO_BASES,
)

from .alternatives import (
    ArchitectureKey,
    architecture_distance_work,
    architecture_key,
    validate_architecture_spec,
)
from .base import FrozenModel, _sha256
from .design import DesignSpec
from .evaluation import Evaluation, candidate_id_for_sequence

_Count = Annotated[int, Field(strict=True, ge=0)]
_Score = Annotated[float, Field(strict=True, ge=0, le=1, allow_inf_nan=False)]
_Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


def portfolio_architecture_bound(spec: DesignSpec) -> int | None:
    """Necessary pair-placement bound, never a count of attainable architectures."""
    if len(spec.specifications) != 2:
        return None
    widths = sum(item.motif.width for item in spec.specifications)
    return (2 * spec.length - widths + 1) * (2 if spec.strands == "both" else 1)


def portfolio_distance_work(classes: int, spec: DesignSpec, count: int) -> tuple[int, int, int]:
    """Conservative bounds including the selected-pair receipt measurement pass."""
    if count == 1 or classes < count:
        return 0, 0, 0
    pairs, terms, prepared = architecture_distance_work(classes, spec)
    selected_pairs, selected_terms, _ = architecture_distance_work(count, spec)
    return pairs + selected_pairs, terms + selected_terms, prepared


class PortfolioPolicy(FrozenModel):
    schema_version: Literal["portfolio-policy/v1"] = "portfolio-policy/v1"
    selector: Literal["bounded_bottleneck_v1"] = "bounded_bottleneck_v1"
    count: Annotated[int, Field(strict=True, gt=0, le=MAX_CANDIDATE_COUNT)]
    separation: Literal["selected_footprint", "hamming"]
    min_distance: _Score
    equivalence: Literal["forward", "reverse_complement"]
    architectures: Literal["distinct", "unrestricted"]
    work_limit: Annotated[int, Field(strict=True, gt=0, le=1_000_000)] = 1_000_000
    distance_base_budget: Annotated[
        int, Field(strict=True, gt=0, le=MAX_ARCHITECTURE_DISTANCE_BASE_BUDGET)
    ] = MAX_DISTANCE_BASE_COMPARISONS

    @property
    def policy_digest(self) -> str:
        return _sha256(self.model_dump(mode="json"))


class PortfolioMember(FrozenModel):
    candidate_id: str = Field(pattern=r"^candidate-[0-9a-f]{16}$")
    evaluation: Evaluation
    architecture: ArchitectureKey


class PortfolioSeparation(FrozenModel):
    left_id: str = Field(pattern=r"^candidate-[0-9a-f]{16}$")
    right_id: str = Field(pattern=r"^candidate-[0-9a-f]{16}$")
    value: _Score
    orientation: Literal["forward", "reverse_complement"]


class PortfolioSelection(FrozenModel):
    """Serializable result; scientific trust additionally requires pool replay."""

    schema_version: Literal["portfolio-selection/v2"] = "portfolio-selection/v2"
    spec: DesignSpec
    policy: PortfolioPolicy
    problem_id: str
    request_digest: _Digest
    pool_digest: _Digest
    coverage: Literal["supplied_pool"] = "supplied_pool"
    realization_policy: Literal["canonical_literal_then_selected_match_scoring"] = (
        "canonical_literal_then_selected_match_scoring"
    )
    status: Literal["optimal", "feasible", "unresolved", "pool_infeasible", "architecture_bound"]
    input_records: Annotated[int, Field(strict=True, ge=0, le=MAX_ARCHITECTURE_POOL_RECORDS)]
    literal_sequences: _Count
    sequence_classes: _Count
    scoring_evaluations: _Count
    search_evaluations: Literal[0] = 0
    distance_base_operations: _Count
    selection_work: _Count
    architecture_upper_bound: _Count | None
    members: tuple[PortfolioMember, ...]
    separations: tuple[PortfolioSeparation, ...]
    quality: _Score | None
    minimum_separation: _Score | None

    @property
    def delivered_count(self) -> int:
        return len(self.members)

    @property
    def result_digest(self) -> str:
        return _sha256(self.model_dump(mode="json"))

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        validate_architecture_spec(self.spec)
        both = self.spec.strands == "both"
        if (self.policy.equivalence == "reverse_complement") != both:
            raise ValueError("portfolio equivalence must match the scoring strand policy")
        if self.request_digest != _sha256(self.spec.model_dump(mode="json")):
            raise ValueError("portfolio request digest disagrees")
        bound = portfolio_architecture_bound(self.spec)
        bound_refusal = (
            self.policy.architectures == "distinct"
            and bound is not None
            and self.policy.count > bound
        )
        if (
            self.architecture_upper_bound != bound
            or (self.status == "architecture_bound") != bound_refusal
        ):
            raise ValueError("portfolio necessary architecture bound disagrees")
        if not (self.sequence_classes <= self.literal_sequences <= self.input_records):
            raise ValueError("portfolio pool counts disagree")
        if (
            bool(self.input_records) != bool(self.sequence_classes)
            or self.literal_sequences > self.sequence_classes * (2 if both else 1)
            or self.scoring_evaluations
            != (0 if self.status == "architecture_bound" else self.sequence_classes)
        ):
            raise ValueError("portfolio scoring and equivalence counts disagree")
        if self.input_records * self.spec.length > MAX_PORTFOLIO_BASES:
            raise ValueError("portfolio pool exceeds the total-base limit")
        pairs, terms, prepared = (
            (0, 0, 0)
            if bound_refusal
            else portfolio_distance_work(self.sequence_classes, self.spec, self.policy.count)
        )
        if (
            self.distance_base_operations != terms
            or pairs > MAX_ARCHITECTURE_DISTANCE_PAIRS
            or prepared > MAX_ARCHITECTURE_PREPARED_PAIRS
        ):
            raise ValueError("portfolio distance accounting or admission disagrees")
        if (self.selection_work == 0) != bound_refusal:
            raise ValueError("portfolio selection work disagrees with the completion status")
        if (
            self.status in {"feasible", "unresolved"}
            and self.selection_work != self.policy.work_limit
        ):
            raise ValueError("uncertified selection must have reached its work limit")
        if (
            self.selection_work > self.policy.work_limit
            or self.distance_base_operations > self.policy.distance_base_budget
        ):
            raise ValueError("portfolio work accounting exceeds the declared limits")
        delivered = self.status in {"optimal", "feasible"}
        if (
            len(self.members) != (self.policy.count if delivered else 0)
            or len(self.members) > self.sequence_classes
        ):
            raise ValueError("portfolio must deliver exactly the requested count or no members")
        expected_quality = min((m.evaluation.balance_score for m in self.members), default=None)
        if self.quality != expected_quality:
            raise ValueError("portfolio quality requires a full set and its weakest score")
        ids = [m.candidate_id for m in self.members]
        if len(set(ids)) != len(ids):
            raise ValueError("portfolio member identifiers must be unique")
        order = []
        for member in self.members:
            evaluation = member.evaluation
            if (
                member.candidate_id != candidate_id_for_sequence(evaluation.sequence)
                or len(evaluation.sequence) != self.spec.length
                or member.architecture != architecture_key(evaluation, both=both)
            ):
                raise ValueError("portfolio member identity or architecture disagrees")
            order.append((-evaluation.balance_score, evaluation.sequence))
        if order != sorted(order):
            raise ValueError("portfolio members require deterministic quality order")
        if self.policy.architectures == "distinct" and len(
            {m.architecture for m in self.members}
        ) != len(self.members):
            raise ValueError("portfolio requires distinct selected architectures")
        member_pairs = [(a, b) for i, a in enumerate(ids) for b in ids[i + 1 :]]
        if [(p.left_id, p.right_id) for p in self.separations] != member_pairs:
            raise ValueError("portfolio pairwise separation closure disagrees")
        if any(p.value + 1e-12 < self.policy.min_distance for p in self.separations):
            raise ValueError("portfolio violates its minimum separation")
        if self.minimum_separation != min((p.value for p in self.separations), default=None):
            raise ValueError("portfolio minimum separation disagrees")
        return self
