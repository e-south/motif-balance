from __future__ import annotations

import math
from dataclasses import dataclass

from motif_balance.compile import CompiledProblem
from motif_balance.model import Evaluation


@dataclass(frozen=True, slots=True)
class Admissibility:
    feasible: bool
    max_excess: float
    total_excess: float


def assess(evaluation: Evaluation, problem: CompiledProblem) -> Admissibility:
    if not problem.avoiders:
        return Admissibility(feasible=True, max_excess=0.0, total_excess=0.0)
    scores = {match.motif_id: match.normalized_score for match in evaluation.avoidance_matches}
    excesses = tuple(
        max(0.0, scores[item.motif.model.motif_id] - item.score_ceiling)
        for item in problem.avoiders
    )
    maximum = max(excesses)
    return Admissibility(
        feasible=maximum <= 1.0e-12,
        max_excess=maximum,
        total_excess=math.fsum(excesses),
    )


def preference_key(evaluation: Evaluation) -> tuple[int, float, float, float]:
    """Return the hard feasibility-first ordering; sequence is a caller tie break."""

    return (
        1 if evaluation.constraint_feasible else 0,
        -evaluation.max_avoidance_excess,
        -evaluation.total_avoidance_excess,
        evaluation.balance_score,
    )


def is_preferred(left: Evaluation, right: Evaluation | None) -> bool:
    if right is None:
        return True
    left_key = preference_key(left)
    right_key = preference_key(right)
    if left_key != right_key:
        return left_key > right_key
    return left.sequence < right.sequence


def assert_evaluation_status(evaluation: Evaluation, problem: CompiledProblem) -> None:
    status = assess(evaluation, problem)
    if (
        evaluation.constraint_feasible != status.feasible
        or not math.isclose(evaluation.max_avoidance_excess, status.max_excess, abs_tol=1.0e-12)
        or not math.isclose(evaluation.total_avoidance_excess, status.total_excess, abs_tol=1.0e-12)
    ):
        raise ValueError("evaluation avoidance status does not match declared ceilings")
