"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/selection.py

Select unchanged evaluated sequences under explicit count and separation constraints.

Module Author(s): Eric J. South
Dunlop Lab
--------------------------------------------------------------------------------
"""

from __future__ import annotations

from dataclasses import dataclass
from math import fsum

from motif_balance.errors import (
    ArtifactError,
    PortfolioInfeasible,
    SearchBudgetExhausted,
    SelectionLimitReached,
)
from motif_balance.model import Candidate, Evaluation, candidate_id_for_sequence

SELECTION_NODE_LIMIT = 1_000_000


@dataclass(frozen=True, slots=True)
class _SubsetResult:
    indices: tuple[int, ...]
    work_used: int
    complete: bool


def _bottleneck_subset(
    ranked: tuple[Evaluation, ...],
    forward_edges: tuple[int, ...],
    *,
    count: int,
    work_limit: int,
) -> _SubsetResult:
    """Bounded clique search on an admitted, quality-ordered finite pool.

    The caller supplies only edges satisfying all hard constraints, with bits
    pointing to later ranked indices. Rank by minimum quality, then total
    quality, then the lexical sorted sequence tuple. Bounds ignore conflicts
    and so can only overestimate what an unfinished branch could deliver.
    Each popped state is one work unit, including pruned and terminal states.
    This operation never scores, edits, or treats the pool as the sequence space.
    """
    best: tuple[int, ...] = ()
    best_key: tuple[float, float, tuple[str, ...]] | None = None
    stack: list[tuple[tuple[int, ...], int]] = [((), (1 << len(ranked)) - 1)]
    work = 0
    while stack and work < work_limit:
        selected, available = stack.pop()
        work += 1
        needed = count - len(selected)
        if not needed:
            key = (
                -min(ranked[i].balance_score for i in selected),
                -fsum(ranked[i].balance_score for i in selected),
                tuple(sorted(ranked[i].sequence for i in selected)),
            )
            if best_key is None or key < best_key:
                best, best_key = selected, key
            continue
        if available.bit_count() < needed:
            continue
        if best_key is not None:
            optimistic = list(selected)
            remaining = available
            for _ in range(needed):
                bit = remaining & -remaining
                optimistic.append(bit.bit_length() - 1)
                remaining ^= bit
            bound = (
                -min(ranked[i].balance_score for i in optimistic),
                -fsum(ranked[i].balance_score for i in optimistic),
            )
            if bound > best_key[:2]:
                continue
        bit = available & -available
        index = bit.bit_length() - 1
        remaining = available ^ bit
        if remaining.bit_count() >= needed:
            stack.append((selected, remaining))
        stack.append(((*selected, index), remaining & forward_edges[index]))
    return _SubsetResult(best, work, not stack)


def normalized_hamming_distance(left: str, right: str) -> float:
    if len(left) != len(right):
        raise ValueError("Hamming distance requires sequences of equal length")
    if not left:
        raise ValueError("Hamming distance requires nonempty sequences")
    return sum(a != b for a, b in zip(left, right, strict=True)) / len(left)


def _candidate_id(sequence: str) -> str:
    return candidate_id_for_sequence(sequence)


def _exact_distance_subset(
    ranked: list[Evaluation],
    *,
    count: int,
    min_distance: float,
) -> tuple[list[Evaluation] | None, int, int, bool]:
    best: list[Evaluation] = []
    nodes = 1
    # This is the same deterministic depth-first traversal as the recursive
    # formulation without coupling valid portfolio size to Python's call stack.
    stack: list[tuple[int, list[Evaluation]]] = [(0, [])]
    while stack and nodes <= SELECTION_NODE_LIMIT:
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
            return child, len(child), nodes, False
        child_position = next_index + 1
        if len(child) + len(ranked) - child_position >= count:
            stack.append((child_position, child))
    return None, len(best), nodes, nodes > SELECTION_NODE_LIMIT


def select_candidates(
    evaluations: tuple[Evaluation, ...],
    *,
    count: int,
    min_distance: float | None,
    evaluations_used: int,
    design_space_exhausted: bool = False,
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
        selected_result, valid_count, nodes_explored, selection_limited = _exact_distance_subset(
            ranked,
            count=count,
            min_distance=min_distance,
        )
        selected = [] if selected_result is None else selected_result
        if selected_result is not None:
            valid_count = len(selected)
    if len(selected) != count:
        best_score = ranked[0].balance_score if ranked else None
        if selection_limited:
            raise SelectionLimitReached(
                nodes_explored=nodes_explored,
                node_limit=SELECTION_NODE_LIMIT,
                candidate_pool_size=len(ranked),
                requested_count=count,
                minimum_distance=min_distance or 0.0,
            )
        if min_distance is not None and min_distance > 0.0:
            raise PortfolioInfeasible(
                requested_count=count,
                valid_count=valid_count,
                candidate_pool_size=len(ranked),
                minimum_distance=min_distance,
                evaluations_used=evaluations_used,
                best_score=best_score,
                design_space_exhausted=design_space_exhausted,
            )
        raise SearchBudgetExhausted(
            requested_count=count,
            valid_count=len(selected),
            evaluations_used=evaluations_used,
            best_score=best_score,
        )
    candidates = tuple(
        Candidate(
            candidate_id=_candidate_id(evaluation.sequence),
            rank=rank,
            sequence=evaluation.sequence,
            balance_score=evaluation.balance_score,
            matches=evaluation.matches,
        )
        for rank, evaluation in enumerate(selected, start=1)
    )
    if len({candidate.candidate_id for candidate in candidates}) != len(candidates):
        raise ArtifactError("candidate identifiers must be unique before portfolio construction")
    return candidates
