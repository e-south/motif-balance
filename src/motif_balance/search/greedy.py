"""Fixed-budget multi-start greedy coordinate search; never an optimum claim."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from motif_balance.compile import CompiledProblem, sequence_space_at_most
from motif_balance.constants import (
    DEFAULT_ELITE_CAPACITY,
    GREEDY_INDEPENDENT_SEARCH_ENGINE,
    GREEDY_SEARCH_ENGINE,
)
from motif_balance.errors import IncompatibleDesign
from motif_balance.model import ProposalSummary, SearchDiagnostics
from motif_balance.model.search import SearchInitialization
from motif_balance.scoring import evaluate

from .engine import ExhaustiveSearchEngine
from .initialization import initial_states
from .observation import SearchRecorder
from .policy import _sequence
from .recording import SearchResult, _retained_elites, _SearchLedger


@dataclass(frozen=True, slots=True)
class GreedySearchEngine:
    """Eight fixed starts, random coordinates, strict hard-minimum improvement.

    Score A/C/G/T at one position in that order (including the unchanged base).
    Break improving ties by lexical sequence; otherwise retain the current
    state. A partial last coordinate trial still retains every evaluation.
    Starts do not restart on stagnation; bounded repetition is measured, not
    interpreted as convergence. Both initialization choices reuse the annealed
    method's starting-sequence policy without sharing its acceptance rule.
    """

    observer: SearchRecorder | None = None
    initialization: SearchInitialization = "related"

    def __post_init__(self) -> None:
        if self.initialization not in ("related", "independent"):
            raise ValueError("initialization must be related or independent")

    def search(self, problem: CompiledProblem) -> SearchResult:
        if problem.spec.schema_version != "design-spec/v3":
            raise IncompatibleDesign(
                "greedy search requires directional design-spec/v3",
                field="method",
                hint="Use explicit seek/avoid specifications for this search method.",
            )
        if sequence_space_at_most(problem.spec.length, problem.spec.evaluations) is not None:
            return ExhaustiveSearchEngine(observer=self.observer).search(problem)
        rng = np.random.Generator(np.random.PCG64(problem.spec.seed))
        ledger = _SearchLedger(
            budget=problem.spec.evaluations, directional=True, observer=self.observer
        )
        states, current = initial_states(
            problem, rng=rng, ledger=ledger, initialization=self.initialization
        )
        if self.observer is not None:
            self.observer.snapshot(
                ledger.evaluations_used, ledger.best_evaluation, tuple(current), force=True
            )
        chain = attempted = accepted = 0
        while ledger.evaluations_used < ledger.budget:
            before = current[chain]
            position = int(rng.integers(problem.spec.length))
            trials = []
            for base in range(min(4, ledger.budget - ledger.evaluations_used)):
                state = states[chain].copy()
                state[position] = base
                result = evaluate(_sequence(state), problem)
                ledger.record(result)
                trials.append((result, state))
            proposed, proposal = min(
                trials, key=lambda item: (-item[0].balance_score, item[0].sequence)
            )
            improved = proposed.balance_score > before.balance_score
            attempted += 1
            if improved:
                states[chain], current[chain] = proposal, proposed
                accepted += 1
            if self.observer is not None:
                self.observer.moved("single", improved, before, proposed)
                self.observer.snapshot(
                    ledger.evaluations_used,
                    ledger.best_evaluation,
                    tuple(current),
                    force=ledger.evaluations_used == ledger.budget,
                )
            chain = (chain + 1) % len(states)
        evaluations = tuple(ledger.evaluations.values())
        diagnostics = SearchDiagnostics(
            schema_version="search-diagnostics/v3",
            restarts=len(states),
            best_score=ledger.best_feasible_score,
            checkpoints=tuple(ledger.checkpoints),
            restart_final_scores=tuple(item.balance_score for item in current),
            restart_final_constraint_statuses=tuple(item.constraint_status for item in current),
            proposals=(ProposalSummary(move="single", attempted=attempted, accepted=accepted),),
        )
        return SearchResult(
            evaluations=evaluations,
            first_evaluation_indices=tuple(ledger.first_evaluation_indices.values()),
            evaluations_used=ledger.evaluations_used,
            unique_evaluations=len(evaluations),
            completion_status="budget_exhausted",
            search_validation_status="contract_tested",
            diagnostics=diagnostics,
            elite_capacity=DEFAULT_ELITE_CAPACITY,
            elites=_retained_elites(evaluations),
            engine=GREEDY_INDEPENDENT_SEARCH_ENGINE
            if self.initialization == "independent"
            else GREEDY_SEARCH_ENGINE,
        )
