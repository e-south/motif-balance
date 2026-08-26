from __future__ import annotations

import hashlib

from motif_balance.errors import SearchExhausted
from motif_balance.model import Candidate, Evaluation


def normalized_hamming_distance(left: str, right: str) -> float:
    if len(left) != len(right):
        raise ValueError("Hamming distance requires sequences of equal length")
    if not left:
        raise ValueError("Hamming distance requires nonempty sequences")
    return sum(a != b for a, b in zip(left, right, strict=True)) / len(left)


def _candidate_id(sequence: str) -> str:
    return f"candidate-{hashlib.sha256(sequence.encode()).hexdigest()[:16]}"


def candidate_id_for_sequence(sequence: str) -> str:
    return _candidate_id(sequence)


def _exact_distance_subset(
    ranked: list[Evaluation],
    *,
    count: int,
    min_distance: float,
) -> tuple[list[Evaluation] | None, int, bool]:
    best: list[Evaluation] = []
    nodes = 0
    node_limit = 1_000_000

    def visit(position: int, selected: list[Evaluation]) -> list[Evaluation] | None:
        nonlocal best, nodes
        nodes += 1
        if nodes > node_limit:
            return None
        if len(selected) > len(best):
            best = list(selected)
        if len(selected) == count:
            return list(selected)
        if len(selected) + len(ranked) - position < count:
            return None
        for index in range(position, len(ranked)):
            candidate = ranked[index]
            if all(
                normalized_hamming_distance(candidate.sequence, accepted.sequence) + 1.0e-12
                >= min_distance
                for accepted in selected
            ):
                found = visit(index + 1, [*selected, candidate])
                if found is not None and len(found) == count:
                    return found
            if nodes > node_limit:
                break
        return None

    found = visit(0, [])
    return found, len(best), nodes > node_limit


def select_candidates(
    evaluations: tuple[Evaluation, ...],
    *,
    count: int,
    min_distance: float | None,
    evaluations_used: int,
) -> tuple[Candidate, ...]:
    unique: dict[str, Evaluation] = {}
    for evaluation in evaluations:
        current = unique.get(evaluation.sequence)
        if current is None or evaluation.balance_score > current.balance_score:
            unique[evaluation.sequence] = evaluation
    ranked = sorted(unique.values(), key=lambda item: (-item.balance_score, item.sequence))
    if min_distance is None:
        selected = ranked[:count]
        selection_limited = False
    else:
        selected_result, valid_count, selection_limited = _exact_distance_subset(
            ranked,
            count=count,
            min_distance=min_distance,
        )
        selected = [] if selected_result is None else selected_result
        if selected_result is not None:
            valid_count = len(selected)
    if len(selected) != count:
        raise SearchExhausted(
            requested_count=count,
            valid_count=valid_count if min_distance is not None else len(selected),
            evaluations_used=evaluations_used,
            best_score=ranked[0].balance_score if ranked else None,
            limiting_condition=(
                "selection search node budget"
                if selection_limited
                else "minimum-distance constraint"
                if min_distance is not None
                else "unique candidates"
            ),
            hint="Increase evaluations, reduce count, or relax min_distance.",
        )
    return tuple(
        Candidate(
            candidate_id=_candidate_id(evaluation.sequence),
            rank=rank,
            sequence=evaluation.sequence,
            balance_score=evaluation.balance_score,
            matches=evaluation.matches,
        )
        for rank, evaluation in enumerate(selected, start=1)
    )
