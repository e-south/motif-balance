"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/search/recording.py

Count evaluations and retain deterministic best candidates and search checkpoints.

Module Author(s): Eric J. South
Dunlop Lab
--------------------------------------------------------------------------------
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol

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
    observer: SearchRecorder | None = None
    retention_capacity: int | None = None
    evaluations: dict[str, Evaluation] = field(default_factory=dict)
    first_evaluation_indices: dict[str, int] = field(default_factory=dict)
    checkpoints: list[SearchCheckpoint] = field(default_factory=list)
    evaluations_used: int = 0
    best_evaluation: Evaluation | None = None
    best_score: float = 0.0
    _worst_retained: tuple[float, str] | None = None

    def __post_init__(self) -> None:
        if self.retention_capacity is not None and self.retention_capacity < 1:
            raise ValueError("retention capacity must be positive")

    @property
    def unique_evaluations(self) -> int:
        return len(self.first_evaluation_indices)

    @property
    def retained_first_indices(self) -> tuple[int, ...]:
        return tuple(self.first_evaluation_indices[sequence] for sequence in self.evaluations)

    def _retain(self, result: Evaluation) -> None:
        """For one output, exact top elites suffice; discovery identities stay complete."""
        capacity = self.retention_capacity
        if capacity is None or len(self.evaluations) < capacity:
            self.evaluations[result.sequence] = result
        else:
            key = (-result.balance_score, result.sequence)
            if self._worst_retained is None:
                raise RuntimeError("bounded retention lacks its worst candidate")
            if key >= self._worst_retained:
                return
            del self.evaluations[self._worst_retained[1]]
            self.evaluations[result.sequence] = result
        if capacity is not None and len(self.evaluations) == capacity:
            self._worst_retained = max(
                (-item.balance_score, item.sequence) for item in self.evaluations.values()
            )

    def record(self, result: Evaluation) -> None:
        if self.evaluations_used >= self.budget:
            raise RuntimeError("search engine exceeded the public evaluation budget")
        self.evaluations_used += 1
        is_new = result.sequence not in self.first_evaluation_indices
        if is_new:
            self.first_evaluation_indices[result.sequence] = self.evaluations_used
            self._retain(result)
        if self.best_evaluation is None or (-result.balance_score, result.sequence) < (
            -self.best_evaluation.balance_score,
            self.best_evaluation.sequence,
        ):
            self.best_evaluation = result
        if self.observer is not None:
            assert self.best_evaluation is not None
            self.observer.evaluated(
                result, self.evaluations_used, is_new=is_new, incumbent=self.best_evaluation
            )
        self.best_score = max(self.best_score, result.balance_score)
        logarithmic_checkpoint = self.evaluations_used & (self.evaluations_used - 1) == 0
        if self.evaluations_used == self.budget or logarithmic_checkpoint:
            assert self.best_evaluation is not None
            details = tuple(
                CheckpointSpecificationSatisfaction(
                    motif_id=match.motif_id,
                    direction=match.spec_direction,
                    attainment=match.normalized_score,
                    satisfaction=match.spec_satisfaction,
                )
                for match in self.best_evaluation.matches
            )
            checkpoint = SearchCheckpoint(
                evaluations=self.evaluations_used,
                best_score=self.best_score,
                specification_satisfactions=details,
                limiting_specification_ids=self.best_evaluation.limiting_specification_ids,
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
