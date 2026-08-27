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
    nodes = 1
    node_limit = 1_000_000
    # This is the same deterministic depth-first traversal as the recursive
    # formulation without coupling valid portfolio size to Python's call stack.
    stack: list[tuple[int, list[Evaluation]]] = [(0, [])]
    while stack and nodes <= node_limit:
        next_index, selected = stack[-1]
        if next_index >= len(ranked):
            stack.pop()
            continue
        stack[-1] = (next_index + 1, selected)
        candidate = ranked[next_index]
        if not all(
            normalized_hamming_distance(candidate.sequence, accepted.sequence) + 1.0e-12
            >= min_distance
            for accepted in selected
        ):
            continue
        child = [*selected, candidate]
        nodes += 1
        if len(child) > len(best):
            best = child
        if len(child) == count:
            return child, len(child), False
        child_position = next_index + 1
        if len(child) + len(ranked) - child_position >= count:
            stack.append((child_position, child))
    return None, len(best), nodes > node_limit


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
    if min_distance is None or min_distance <= 0.0:
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
