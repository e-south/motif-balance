from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol

from motif_balance.admissibility import is_preferred
from motif_balance.compile import CompiledProblem
from motif_balance.constants import (
    DEFAULT_ELITE_CAPACITY,
    RNG_NAME,
    SEARCH_ENGINE,
    SEARCH_ENGINE_VERSION,
)
from motif_balance.model import (
    CheckpointSpecificationSatisfaction,
    Evaluation,
    SearchCheckpoint,
    SearchDiagnostics,
)

from .observation import SearchRecorder


@dataclass(frozen=True, slots=True)
class SearchResult:
    evaluations: tuple[Evaluation, ...]
    first_evaluation_indices: tuple[int, ...]
    evaluations_used: int
    unique_evaluations: int
    completion_status: Literal["exhaustive", "budget_exhausted"]
    search_validation_status: Literal["not_applicable", "contract_tested"]
    diagnostics: SearchDiagnostics
    elite_capacity: int
    elites: tuple[Evaluation, ...]
    engine: str = SEARCH_ENGINE
    engine_version: str = SEARCH_ENGINE_VERSION
    rng: str = RNG_NAME

    def __post_init__(self) -> None:
        if len(self.evaluations) != len(self.first_evaluation_indices):
            raise ValueError("search evaluation rows and first-evaluation indices must align")
        if self.first_evaluation_indices != tuple(sorted(self.first_evaluation_indices)):
            raise ValueError("first-evaluation indices must follow unique discovery order")
        if len(set(self.first_evaluation_indices)) != len(self.first_evaluation_indices):
            raise ValueError("first-evaluation indices must be unique")
        if len(self.elites) > self.elite_capacity:
            raise ValueError("retained elites cannot exceed the declared capacity")
        sequences = tuple(item.sequence for item in self.elites)
        if len(sequences) != len(set(sequences)):
            raise ValueError("retained elite sequences must be unique")


class SearchEngine(Protocol):
    """Substitution seam for production and tractable exhaustive search."""

    def search(self, problem: CompiledProblem) -> SearchResult: ...


@dataclass(slots=True)
class _SearchLedger:
    budget: int
    directional: bool
    observer: SearchRecorder | None = None
    evaluations: dict[str, Evaluation] = field(default_factory=dict)
    first_evaluation_indices: dict[str, int] = field(default_factory=dict)
    checkpoints: list[SearchCheckpoint] = field(default_factory=list)
    evaluations_used: int = 0
    best_evaluation: Evaluation | None = None
    best_feasible_score: float = 0.0

    def record(self, result: Evaluation) -> None:
        if self.evaluations_used >= self.budget:
            raise RuntimeError("search engine exceeded the public evaluation budget")
        self.evaluations_used += 1
        if self.observer is not None:
            self.observer.evaluated(
                result, self.evaluations_used, is_new=result.sequence not in self.evaluations
            )
        if result.sequence not in self.evaluations:
            self.evaluations[result.sequence] = result
            self.first_evaluation_indices[result.sequence] = self.evaluations_used
        if is_preferred(result, self.best_evaluation):
            self.best_evaluation = result
        if result.constraint_feasible:
            self.best_feasible_score = max(self.best_feasible_score, result.balance_score)
        interval = max(1, self.budget // 20)
        logarithmic_checkpoint = self.evaluations_used & (self.evaluations_used - 1) == 0
        if self.evaluations_used == self.budget or (
            logarithmic_checkpoint
            if self.directional
            else self.evaluations_used == 1 or self.evaluations_used % interval == 0
        ):
            details = (
                tuple(
                    CheckpointSpecificationSatisfaction(
                        motif_id=match.motif_id,
                        direction=match.spec_direction,
                        attainment=match.normalized_score,
                        satisfaction=match.spec_satisfaction,
                    )
                    for match in self.best_evaluation.matches
                    if match.spec_direction is not None and match.spec_satisfaction is not None
                )
                if self.directional and self.best_evaluation is not None
                else ()
            )
            checkpoint = SearchCheckpoint(
                evaluations=self.evaluations_used,
                best_score=self.best_feasible_score,
                specification_satisfactions=details,
                limiting_specification_ids=(
                    self.best_evaluation.limiting_specification_ids
                    if self.directional and self.best_evaluation is not None
                    else ()
                ),
            )
            if self.checkpoints and self.checkpoints[-1].evaluations == self.evaluations_used:
                self.checkpoints[-1] = checkpoint
            else:
                self.checkpoints.append(checkpoint)


def _retained_elites(
    evaluations: tuple[Evaluation, ...], *, capacity: int = DEFAULT_ELITE_CAPACITY
) -> tuple[Evaluation, ...]:
    return tuple(
        sorted(evaluations, key=lambda item: (-item.balance_score, item.sequence))[:capacity]
    )
