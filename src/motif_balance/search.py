from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from typing import Literal

import numpy as np

from motif_balance.compile import CompiledProblem
from motif_balance.constants import DNA_ALPHABET, RNG_NAME, SEARCH_ENGINE, SEARCH_ENGINE_VERSION
from motif_balance.model import Evaluation
from motif_balance.scoring import evaluate


@dataclass(frozen=True, slots=True)
class SearchResult:
    evaluations: tuple[Evaluation, ...]
    evaluations_used: int
    unique_evaluations: int
    completion_status: Literal["exhaustive", "budget_exhausted"]
    optimizer_parity_status: Literal["not_applicable", "not_established"]
    engine: str = SEARCH_ENGINE
    engine_version: str = SEARCH_ENGINE_VERSION
    rng: str = RNG_NAME


def _soft_min(evaluation: Evaluation, beta: float = 12.0) -> float:
    scores = np.asarray([match.normalized_score for match in evaluation.matches], dtype=float)
    floor = float(np.min(scores))
    return floor - math.log(float(np.exp(-beta * (scores - floor)).sum())) / beta


def _exhaustive(problem: CompiledProblem) -> SearchResult:
    evaluations = tuple(
        evaluate("".join(bases), problem)
        for bases in itertools.product(DNA_ALPHABET, repeat=problem.spec.length)
    )
    return SearchResult(
        evaluations=evaluations,
        evaluations_used=len(evaluations),
        unique_evaluations=len(evaluations),
        completion_status="exhaustive",
        optimizer_parity_status="not_applicable",
        engine="exhaustive_v1",
        rng="none",
    )


def _metropolis(problem: CompiledProblem) -> SearchResult:
    rng = np.random.Generator(np.random.PCG64(problem.spec.seed))
    bases = np.asarray(DNA_ALPHABET)
    current_sequence = "".join(rng.choice(bases, size=problem.spec.length).tolist())
    current = evaluate(current_sequence, problem)
    unique: dict[str, Evaluation] = {current.sequence: current}
    used = 1
    restart_interval = max(16, problem.spec.length * 8)
    while used < problem.spec.evaluations:
        if used % restart_interval == 0:
            proposed_sequence = "".join(rng.choice(bases, size=problem.spec.length).tolist())
        else:
            position = int(rng.integers(problem.spec.length))
            available = bases[bases != current.sequence[position]]
            replacement = str(rng.choice(available))
            proposed_sequence = (
                current.sequence[:position] + replacement + current.sequence[position + 1 :]
            )
        proposed = evaluate(proposed_sequence, problem)
        used += 1
        unique.setdefault(proposed.sequence, proposed)
        progress = used / problem.spec.evaluations
        beta = 0.5 + progress * 11.5
        delta = _soft_min(proposed, beta=beta) - _soft_min(current, beta=beta)
        if delta >= 0.0 or math.log(max(float(rng.random()), 1.0e-300)) < beta * delta:
            current = proposed
    return SearchResult(
        evaluations=tuple(unique.values()),
        evaluations_used=used,
        unique_evaluations=len(unique),
        completion_status="budget_exhausted",
        optimizer_parity_status="not_established",
    )


def search(problem: CompiledProblem) -> SearchResult:
    sequence_space = 4**problem.spec.length
    if sequence_space <= problem.spec.evaluations:
        return _exhaustive(problem)
    return _metropolis(problem)
