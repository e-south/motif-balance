from __future__ import annotations

import math
from typing import Literal

import numpy as np

from motif_balance.admissibility import preference_key
from motif_balance.compile import CompiledMotif, CompiledProblem
from motif_balance.constants import (
    DNA_ALPHABET,
)
from motif_balance.model import (
    Evaluation,
    MotifMatch,
)
from motif_balance.scoring import evaluate, reverse_complement

from .policy import _annealing_beta, _sequence, _soft_min
from .recording import _SearchLedger

MoveName = Literal["single", "block", "multi", "insertion"]


def _worst_match(result: Evaluation) -> MotifMatch:
    return min(
        result.matches,
        key=lambda item: (
            item.spec_satisfaction if item.spec_satisfaction is not None else item.normalized_score,
            item.motif_id,
        ),
    )


def _target_bounds(result: Evaluation, problem: CompiledProblem, *, length: int) -> tuple[int, int]:
    ceilings = {item.motif.model.motif_id: item.score_ceiling for item in problem.avoiders}
    match = (
        max(
            result.avoidance_matches,
            key=lambda item: (
                item.normalized_score - ceilings[item.motif_id],
                item.motif_id,
            ),
        )
        if not result.constraint_feasible and result.avoidance_matches
        else _worst_match(result)
    )
    return max(0, match.start - 3), min(length, match.end + 3)


def _targeted_start(
    *,
    sequence_length: int,
    block_length: int,
    bounds: tuple[int, int] | None,
    rng: np.random.Generator,
) -> int:
    maximum = sequence_length - block_length
    if maximum <= 0:
        return 0
    if bounds is None:
        return int(rng.integers(maximum + 1))
    low = max(0, bounds[0] - block_length + 1)
    high = min(maximum, bounds[1] - 1)
    if high < low:
        return int(rng.integers(maximum + 1))
    return int(rng.integers(low, high + 1))


def _motif_for_match(problem: CompiledProblem, motif_id: str) -> CompiledMotif:
    return next(motif for motif in problem.motifs if motif.model.motif_id == motif_id)


def _motif_insertion_word(
    motif: CompiledMotif,
    *,
    direction: Literal["seek", "avoid"],
    rng: np.random.Generator,
) -> str:
    """Propose a word in the direction of the current limiting specification."""

    if rng.random() < 0.65:
        return (
            motif.probability_consensus if direction == "seek" else motif.score_minimizing_sequence
        )
    if direction == "seek":
        return "".join(
            DNA_ALPHABET[int(rng.choice(4, p=np.asarray(row, dtype=float)))]
            for row in motif.model.probabilities
        )
    words = []
    for row in motif.log_odds:
        logits = -np.asarray(row, dtype=float)
        weights = np.exp(logits - logits.max())
        weights /= weights.sum()
        words.append(DNA_ALPHABET[int(rng.choice(4, p=weights))])
    return "".join(words)


class SearchMoves:
    """Fixed-length proposal operators; no search scheduling or publication."""

    def _single_move(
        self,
        problem: CompiledProblem,
        *,
        state: np.ndarray,
        current: Evaluation,
        rng: np.random.Generator,
        ledger: _SearchLedger,
        progress: float,
    ) -> tuple[np.ndarray, Evaluation, bool]:
        bounds = (
            _target_bounds(current, problem, length=problem.spec.length)
            if rng.random() < 0.5
            else None
        )
        position = (
            int(rng.integers(problem.spec.length))
            if bounds is None
            else int(rng.integers(bounds[0], bounds[1]))
        )
        candidates: list[tuple[np.ndarray, Evaluation]] = []
        for base in range(4):
            proposal = state.copy()
            proposal[position] = base
            result = evaluate(_sequence(proposal), problem)
            ledger.record(result)
            candidates.append((proposal, result))
        soft_beta = 0.5 + 11.5 * progress
        has_feasible = any(result.constraint_feasible for _, result in candidates)
        if has_feasible:
            scores = np.asarray(
                [
                    _soft_min(result, beta=soft_beta) if result.constraint_feasible else -math.inf
                    for _, result in candidates
                ]
            )
        else:
            keys = tuple(preference_key(result) for _, result in candidates)
            ranks = {key: rank for rank, key in enumerate(sorted(set(keys)))}
            scores = np.asarray([float(ranks[key]) for key in keys])
        logits = _annealing_beta(progress) * scores
        logits -= logits.max()
        probabilities = np.exp(logits)
        probabilities /= probabilities.sum()
        inertia = 0.90 * progress
        current_base = int(state[position])
        probabilities *= 1.0 - inertia
        probabilities[current_base] += inertia
        probabilities /= probabilities.sum()
        selected = int(rng.choice(4, p=probabilities))
        proposal, result = candidates[selected]
        return proposal, result, True

    def _block_move(
        self,
        problem: CompiledProblem,
        *,
        state: np.ndarray,
        current: Evaluation,
        rng: np.random.Generator,
        ledger: _SearchLedger,
    ) -> tuple[np.ndarray, Evaluation]:
        block_length = int(rng.integers(2, min(5, problem.spec.length) + 1))
        bounds = (
            _target_bounds(current, problem, length=problem.spec.length)
            if rng.random() < 0.5
            else None
        )
        start = _targeted_start(
            sequence_length=problem.spec.length,
            block_length=block_length,
            bounds=bounds,
            rng=rng,
        )
        proposal = state.copy()
        proposal[start : start + block_length] = rng.integers(
            0, 4, size=block_length, dtype=np.int8
        )
        result = evaluate(_sequence(proposal), problem)
        ledger.record(result)
        return proposal, result

    def _multi_move(
        self,
        problem: CompiledProblem,
        *,
        state: np.ndarray,
        current: Evaluation,
        rng: np.random.Generator,
        ledger: _SearchLedger,
    ) -> tuple[np.ndarray, Evaluation]:
        count = int(rng.integers(1, min(2, problem.spec.length) + 1))
        bounds = (
            _target_bounds(current, problem, length=problem.spec.length)
            if rng.random() < 0.5
            else None
        )
        population = (
            np.arange(bounds[0], bounds[1])
            if bounds is not None and bounds[1] - bounds[0] >= count
            else np.arange(problem.spec.length)
        )
        positions = rng.choice(population, size=count, replace=False)
        proposal = state.copy()
        proposal[positions] = rng.integers(0, 4, size=count, dtype=np.int8)
        result = evaluate(_sequence(proposal), problem)
        ledger.record(result)
        return proposal, result

    def _insertion_move(
        self,
        problem: CompiledProblem,
        *,
        state: np.ndarray,
        current: Evaluation,
        rng: np.random.Generator,
        ledger: _SearchLedger,
    ) -> tuple[np.ndarray, Evaluation]:
        worst = _worst_match(current)
        motif = _motif_for_match(problem, worst.motif_id)
        inserted = _motif_insertion_word(
            motif,
            direction=worst.spec_direction or "seek",
            rng=rng,
        )
        if problem.spec.strands == "both" and rng.random() < 0.5:
            inserted = reverse_complement(inserted)
        bounds = (
            _target_bounds(current, problem, length=problem.spec.length)
            if rng.random() < 0.5
            else None
        )
        start = _targeted_start(
            sequence_length=problem.spec.length,
            block_length=len(inserted),
            bounds=bounds,
            rng=rng,
        )
        proposal = state.copy()
        proposal[start : start + len(inserted)] = [DNA_ALPHABET.index(base) for base in inserted]
        result = evaluate(_sequence(proposal), problem)
        ledger.record(result)
        return proposal, result
