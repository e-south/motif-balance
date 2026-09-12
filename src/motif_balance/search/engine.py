from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from typing import cast

import numpy as np

from motif_balance.compile import CompiledProblem, sequence_space_at_most
from motif_balance.constants import (
    DEFAULT_ELITE_CAPACITY,
    DNA_ALPHABET,
    INDEPENDENT_SEARCH_ENGINE,
    SEARCH_ENGINE,
)
from motif_balance.errors import IncompatibleDesign
from motif_balance.model import (
    Evaluation,
    ProposalSummary,
    SearchDiagnostics,
)
from motif_balance.model.search import SearchInitialization
from motif_balance.scoring import evaluate

from .initialization import initial_states
from .moves import MoveName, SearchMoves
from .observation import SearchRecorder
from .policy import _annealing_beta, _move_probabilities, _soft_min
from .recording import SearchEngine, SearchResult, _retained_elites, _SearchLedger


@dataclass(frozen=True, slots=True)
class ExhaustiveSearchEngine:
    observer: SearchRecorder | None = None

    def search(self, problem: CompiledProblem) -> SearchResult:
        sequence_space = sequence_space_at_most(problem.spec.length, problem.spec.evaluations)
        if sequence_space is None:
            raise ValueError("exhaustive search requires a budget covering the sequence space")
        ledger = _SearchLedger(
            budget=sequence_space,
            directional=problem.spec.schema_version == "design-spec/v3",
            observer=self.observer,
        )
        for bases in itertools.product(DNA_ALPHABET, repeat=problem.spec.length):
            ledger.record(evaluate("".join(bases), problem))
            if self.observer is not None:
                self.observer.snapshot(
                    ledger.evaluations_used,
                    ledger.best_evaluation,
                    (),
                    force=ledger.evaluations_used in (1, sequence_space),
                )
        diagnostics = SearchDiagnostics(
            schema_version=(
                "search-diagnostics/v3"
                if problem.spec.schema_version == "design-spec/v3"
                else "search-diagnostics/v2"
            ),
            restarts=1,
            best_score=ledger.best_feasible_score,
            checkpoints=tuple(ledger.checkpoints),
            restart_final_scores=(ledger.best_feasible_score,),
            restart_final_constraint_statuses=(
                "feasible"
                if any(item.constraint_feasible for item in ledger.evaluations.values())
                else "infeasible",
            ),
            proposals=(),
        )
        evaluations = tuple(ledger.evaluations.values())
        return SearchResult(
            evaluations=evaluations,
            first_evaluation_indices=tuple(ledger.first_evaluation_indices.values()),
            evaluations_used=ledger.evaluations_used,
            unique_evaluations=len(ledger.evaluations),
            completion_status="exhaustive",
            search_validation_status="not_applicable",
            diagnostics=diagnostics,
            elite_capacity=DEFAULT_ELITE_CAPACITY,
            elites=_retained_elites(evaluations),
            engine="exhaustive_v1",
            engine_version="1",
            rng="none",
        )


@dataclass(frozen=True, slots=True)
class AnnealedSearchEngine(SearchMoves):
    """Bounded production search under the public evaluation contract.

    The fixed policy combines perturbed multi-chain starts, four-base single-position
    resampling, wider mutations, motif insertion, and annealed acceptance. It does
    not mutate evaluated candidates, relax result constraints, or retain raw
    optimizer-state traces.
    """

    restarts: int = 8
    observer: SearchRecorder | None = None
    initialization: SearchInitialization = "related"

    def __post_init__(self) -> None:
        if self.initialization not in ("related", "independent"):
            raise ValueError("initialization must be related or independent")

    def search(self, problem: CompiledProblem) -> SearchResult:
        if self.initialization == "independent" and problem.spec.schema_version != "design-spec/v3":
            raise IncompatibleDesign(
                "independent initialization requires directional design-spec/v3",
                field="initialization",
                hint="Use an explicit directional specification for method comparisons.",
            )
        if sequence_space_at_most(problem.spec.length, problem.spec.evaluations) is not None:
            return ExhaustiveSearchEngine(observer=self.observer).search(problem)
        rng = np.random.Generator(np.random.PCG64(problem.spec.seed))
        ledger = _SearchLedger(
            budget=problem.spec.evaluations,
            directional=problem.spec.schema_version == "design-spec/v3",
            observer=self.observer,
        )
        states, current = initial_states(
            problem,
            rng=rng,
            ledger=ledger,
            initialization=self.initialization,
            restarts=self.restarts,
        )
        if self.observer is not None:
            self.observer.snapshot(
                ledger.evaluations_used, ledger.best_evaluation, tuple(current), force=True
            )
        attempted: dict[MoveName, int] = {
            "single": 0,
            "block": 0,
            "multi": 0,
            "insertion": 0,
        }
        accepted = dict.fromkeys(attempted, 0)
        move_names: tuple[MoveName, ...] = ("single", "block", "multi", "insertion")
        chain = 0
        while ledger.evaluations_used < ledger.budget:
            progress = ledger.evaluations_used / ledger.budget
            remaining = ledger.budget - ledger.evaluations_used
            move = cast(MoveName, rng.choice(move_names, p=_move_probabilities(progress)))
            if move == "single" and remaining < 4:
                move = "multi"
            attempted[move] += 1
            state = states[chain]
            result = current[chain]
            if move == "single":
                proposal, proposed, was_accepted = self._single_move(
                    problem,
                    state=state,
                    current=result,
                    rng=rng,
                    ledger=ledger,
                    progress=progress,
                )
            elif move == "block":
                proposal, proposed = self._block_move(
                    problem,
                    state=state,
                    current=result,
                    rng=rng,
                    ledger=ledger,
                )
                was_accepted = self._accept(result, proposed, progress=progress, rng=rng)
            elif move == "multi":
                proposal, proposed = self._multi_move(
                    problem,
                    state=state,
                    current=result,
                    rng=rng,
                    ledger=ledger,
                )
                was_accepted = self._accept(result, proposed, progress=progress, rng=rng)
            else:
                proposal, proposed = self._insertion_move(
                    problem,
                    state=state,
                    current=result,
                    rng=rng,
                    ledger=ledger,
                )
                was_accepted = self._accept(result, proposed, progress=progress, rng=rng)
            if was_accepted:
                states[chain] = proposal
                current[chain] = proposed
                accepted[move] += 1
            if self.observer is not None:
                self.observer.moved(move, was_accepted, result, proposed)
                self.observer.snapshot(
                    ledger.evaluations_used,
                    ledger.best_evaluation,
                    tuple(current),
                    force=ledger.evaluations_used == ledger.budget,
                )
            chain = (chain + 1) % len(states)
        diagnostics = SearchDiagnostics(
            schema_version=(
                "search-diagnostics/v3"
                if problem.spec.schema_version == "design-spec/v3"
                else "search-diagnostics/v2"
            ),
            restarts=len(states),
            best_score=ledger.best_feasible_score,
            checkpoints=tuple(ledger.checkpoints),
            restart_final_scores=tuple(result.balance_score for result in current),
            restart_final_constraint_statuses=tuple(result.constraint_status for result in current),
            proposals=tuple(
                ProposalSummary(move=move, attempted=attempted[move], accepted=accepted[move])
                for move in move_names
            ),
        )
        evaluations = tuple(ledger.evaluations.values())
        return SearchResult(
            evaluations=evaluations,
            first_evaluation_indices=tuple(ledger.first_evaluation_indices.values()),
            evaluations_used=ledger.evaluations_used,
            unique_evaluations=len(ledger.evaluations),
            completion_status="budget_exhausted",
            search_validation_status="contract_tested",
            diagnostics=diagnostics,
            elite_capacity=DEFAULT_ELITE_CAPACITY,
            elites=_retained_elites(evaluations),
            engine=INDEPENDENT_SEARCH_ENGINE
            if self.initialization == "independent"
            else SEARCH_ENGINE,
        )

    @staticmethod
    def _accept(
        current: Evaluation,
        proposed: Evaluation,
        *,
        progress: float,
        rng: np.random.Generator,
    ) -> bool:
        if current.constraint_feasible != proposed.constraint_feasible:
            return proposed.constraint_feasible
        soft_beta = 0.5 + 11.5 * progress
        if proposed.constraint_feasible:
            delta = _soft_min(proposed, beta=soft_beta) - _soft_min(current, beta=soft_beta)
        elif not math.isclose(
            current.max_avoidance_excess,
            proposed.max_avoidance_excess,
            abs_tol=1.0e-12,
        ):
            delta = current.max_avoidance_excess - proposed.max_avoidance_excess
        elif not math.isclose(
            current.total_avoidance_excess,
            proposed.total_avoidance_excess,
            abs_tol=1.0e-12,
        ):
            delta = current.total_avoidance_excess - proposed.total_avoidance_excess
        else:
            delta = proposed.balance_score - current.balance_score
        return delta >= 0.0 or math.log(max(float(rng.random()), 1.0e-300)) < (
            _annealing_beta(progress) * delta
        )


def search(problem: CompiledProblem, *, engine: SearchEngine | None = None) -> SearchResult:
    selected = engine
    if selected is None:
        selected = (
            ExhaustiveSearchEngine()
            if sequence_space_at_most(problem.spec.length, problem.spec.evaluations) is not None
            else AnnealedSearchEngine()
        )
    return selected.search(problem)
