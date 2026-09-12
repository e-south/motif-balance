"""Shared starting sequences; no optimizer-specific decision policy."""

from __future__ import annotations

import numpy as np

from motif_balance.compile import CompiledProblem
from motif_balance.model import Evaluation
from motif_balance.model.search import SearchInitialization
from motif_balance.scoring import evaluate

from .policy import _sequence
from .recording import _SearchLedger


def initial_states(
    problem: CompiledProblem,
    *,
    rng: np.random.Generator,
    ledger: _SearchLedger,
    initialization: SearchInitialization,
    restarts: int = 8,
) -> tuple[list[np.ndarray], list[Evaluation]]:
    chain_count = min(restarts, problem.spec.evaluations)
    base = (
        rng.integers(0, 4, size=problem.spec.length, dtype=np.int8)
        if initialization == "related"
        else None
    )
    mutation_count = max(1, round(problem.spec.length * 0.02))
    states: list[np.ndarray] = []
    results: list[Evaluation] = []
    for chain in range(chain_count):
        state = (
            base.copy()
            if base is not None
            else rng.integers(0, 4, size=problem.spec.length, dtype=np.int8)
        )
        if base is not None and chain:
            positions = rng.choice(
                problem.spec.length, size=min(mutation_count, problem.spec.length), replace=False
            )
            for position in positions:
                current = int(state[position])
                replacement = int(rng.integers(0, 3))
                if replacement >= current:
                    replacement += 1
                state[position] = replacement
        result = evaluate(_sequence(state), problem)
        ledger.record(result)
        states.append(state)
        results.append(result)
    return states, results
