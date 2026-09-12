"""Independent whole-sequence sampling under the shared scoring and retention contract."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from motif_balance.compile import CompiledProblem
from motif_balance.constants import DEFAULT_ELITE_CAPACITY, RANDOM_SEARCH_ENGINE
from motif_balance.errors import IncompatibleDesign
from motif_balance.model import SearchDiagnostics
from motif_balance.scoring import evaluate

from .observation import SearchRecorder
from .policy import _sequence
from .recording import SearchResult, _retained_elites, _SearchLedger


@dataclass(frozen=True, slots=True)
class UniformRandomSearchEngine:
    """Draw with replacement, count every draw, and never substitute enumeration.

    Uses PCG64 and one int8 A/C/G/T vector draw per sequence. There are no local
    moves, acceptance decisions, or persistent chains. A single diagnostic
    search stream records the retained best, not a fictitious terminal chain.
    """

    observer: SearchRecorder | None = None

    def search(self, problem: CompiledProblem) -> SearchResult:
        if problem.spec.schema_version != "design-spec/v3":
            raise IncompatibleDesign(
                "uniform random search requires directional design-spec/v3",
                field="method",
                hint="Use explicit seek/avoid specifications for this search method.",
            )
        rng = np.random.Generator(np.random.PCG64(problem.spec.seed))
        ledger = _SearchLedger(
            budget=problem.spec.evaluations, directional=True, observer=self.observer
        )
        while ledger.evaluations_used < ledger.budget:
            state = rng.integers(0, 4, size=problem.spec.length, dtype=np.int8)
            ledger.record(evaluate(_sequence(state), problem))
            if self.observer is not None:
                self.observer.snapshot(
                    ledger.evaluations_used,
                    ledger.best_evaluation,
                    (),
                    force=ledger.evaluations_used in (1, ledger.budget),
                )
        evaluations = tuple(ledger.evaluations.values())
        diagnostics = SearchDiagnostics(
            schema_version="search-diagnostics/v3",
            restarts=1,
            best_score=ledger.best_feasible_score,
            checkpoints=tuple(ledger.checkpoints),
            restart_final_scores=(ledger.best_feasible_score,),
            restart_final_constraint_statuses=("feasible",),
            proposals=(),
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
            engine=RANDOM_SEARCH_ENGINE,
        )
