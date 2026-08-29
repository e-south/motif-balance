from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field
from typing import Literal, Protocol, cast

import numpy as np
from numpy.typing import NDArray

from motif_balance.admissibility import is_preferred
from motif_balance.compile import CompiledMotif, CompiledProblem, sequence_space_at_most
from motif_balance.constants import DNA_ALPHABET, RNG_NAME, SEARCH_ENGINE, SEARCH_ENGINE_VERSION
from motif_balance.model import (
    Evaluation,
    MotifMatch,
    ProposalSummary,
    SearchCheckpoint,
    SearchDiagnostics,
)
from motif_balance.scoring import evaluate, reverse_complement

MoveName = Literal["single", "block", "multi", "insertion"]


@dataclass(frozen=True, slots=True)
class SearchResult:
    evaluations: tuple[Evaluation, ...]
    evaluations_used: int
    unique_evaluations: int
    completion_status: Literal["exhaustive", "budget_exhausted"]
    search_validation_status: Literal["not_applicable", "contract_tested"]
    diagnostics: SearchDiagnostics
    engine: str = SEARCH_ENGINE
    engine_version: str = SEARCH_ENGINE_VERSION
    rng: str = RNG_NAME


class SearchEngine(Protocol):
    """Substitution seam for production and tractable exhaustive search."""

    def search(self, problem: CompiledProblem) -> SearchResult: ...


@dataclass(slots=True)
class _SearchLedger:
    budget: int
    evaluations: dict[str, Evaluation] = field(default_factory=dict)
    checkpoints: list[SearchCheckpoint] = field(default_factory=list)
    evaluations_used: int = 0
    best_evaluation: Evaluation | None = None
    best_feasible_score: float = 0.0

    def record(self, result: Evaluation) -> None:
        if self.evaluations_used >= self.budget:
            raise RuntimeError("search engine exceeded the public evaluation budget")
        self.evaluations_used += 1
        self.evaluations.setdefault(result.sequence, result)
        if is_preferred(result, self.best_evaluation):
            self.best_evaluation = result
        if result.constraint_feasible:
            self.best_feasible_score = max(self.best_feasible_score, result.balance_score)
        interval = max(1, self.budget // 20)
        if (
            self.evaluations_used == 1
            or self.evaluations_used % interval == 0
            or self.evaluations_used == self.budget
        ):
            checkpoint = SearchCheckpoint(
                evaluations=self.evaluations_used,
                best_score=self.best_feasible_score,
            )
            if self.checkpoints and self.checkpoints[-1].evaluations == self.evaluations_used:
                self.checkpoints[-1] = checkpoint
            else:
                self.checkpoints.append(checkpoint)


def _soft_min(result: Evaluation, *, beta: float) -> float:
    scores = np.asarray([match.normalized_score for match in result.matches], dtype=float)
    floor = float(np.min(scores))
    return floor - math.log(float(np.exp(-beta * (scores - floor)).sum())) / beta


def _sequence(values: np.ndarray) -> str:
    return "".join(DNA_ALPHABET[int(value)] for value in values)


def _mcmc_beta(progress: float) -> float:
    if progress < 0.20:
        return 0.2
    if progress < 0.60:
        return 1.2
    if progress < 0.92:
        return 6.0
    if progress < 0.973:
        return 12.0
    return 24.0


def _move_probabilities(progress: float) -> NDArray[np.float64]:
    start = np.asarray((0.70, 0.15, 0.08, 0.07), dtype=float)
    end = np.asarray((0.50, 0.24, 0.14, 0.12), dtype=float)
    probabilities = start + min(max(progress, 0.0), 1.0) * (end - start)
    return cast(NDArray[np.float64], probabilities / probabilities.sum())


def _worst_match(result: Evaluation) -> MotifMatch:
    return min(result.matches, key=lambda item: (item.normalized_score, item.motif_id))


def _target_bounds(result: Evaluation, *, length: int) -> tuple[int, int]:
    match = (
        max(
            result.avoidance_matches,
            key=lambda item: (item.normalized_score, item.motif_id),
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


@dataclass(frozen=True, slots=True)
class ExhaustiveSearchEngine:
    def search(self, problem: CompiledProblem) -> SearchResult:
        sequence_space = sequence_space_at_most(problem.spec.length, problem.spec.evaluations)
        if sequence_space is None:
            raise ValueError("exhaustive search requires a budget covering the sequence space")
        ledger = _SearchLedger(budget=sequence_space)
        for bases in itertools.product(DNA_ALPHABET, repeat=problem.spec.length):
            ledger.record(evaluate("".join(bases), problem))
        diagnostics = SearchDiagnostics(
            restarts=1,
            best_score=ledger.best_feasible_score,
            checkpoints=tuple(ledger.checkpoints),
            restart_final_scores=(ledger.best_feasible_score,),
            proposals=(),
        )
        return SearchResult(
            evaluations=tuple(ledger.evaluations.values()),
            evaluations_used=ledger.evaluations_used,
            unique_evaluations=len(ledger.evaluations),
            completion_status="exhaustive",
            search_validation_status="not_applicable",
            diagnostics=diagnostics,
            engine="exhaustive_v1",
            engine_version="1",
            rng="none",
        )


@dataclass(frozen=True, slots=True)
class AnnealedSearchEngine:
    """Bounded production search under the public evaluation contract.

    The fixed policy combines perturbed multi-chain starts, Gibbs-style single-base
    updates, wider mutations, motif insertion, and annealed acceptance. It does
    not mutate evaluated candidates, relax result constraints, or retain raw
    optimizer-state traces.
    """

    restarts: int = 8

    def _initial_states(
        self,
        problem: CompiledProblem,
        *,
        rng: np.random.Generator,
        ledger: _SearchLedger,
    ) -> tuple[list[np.ndarray], list[Evaluation]]:
        chain_count = min(self.restarts, problem.spec.evaluations)
        base = rng.integers(0, 4, size=problem.spec.length, dtype=np.int8)
        mutation_count = max(1, round(problem.spec.length * 0.02))
        states: list[np.ndarray] = []
        results: list[Evaluation] = []
        for chain in range(chain_count):
            state = base.copy()
            if chain:
                positions = rng.choice(
                    problem.spec.length,
                    size=min(mutation_count, problem.spec.length),
                    replace=False,
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
        bounds = _target_bounds(current, length=problem.spec.length) if rng.random() < 0.5 else None
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
        scores = np.asarray(
            [
                (
                    _soft_min(result, beta=soft_beta)
                    if result.constraint_feasible
                    else -result.max_avoidance_excess
                )
                for _, result in candidates
            ]
        )
        logits = _mcmc_beta(progress) * scores
        if has_feasible:
            logits = np.asarray(
                [
                    value if result.constraint_feasible else -math.inf
                    for value, (_, result) in zip(logits, candidates, strict=True)
                ]
            )
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
        bounds = _target_bounds(current, length=problem.spec.length) if rng.random() < 0.5 else None
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
        bounds = _target_bounds(current, length=problem.spec.length) if rng.random() < 0.5 else None
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
        if rng.random() < 0.65:
            inserted = "".join(
                DNA_ALPHABET[int(np.argmax(row))] for row in motif.model.probabilities
            )
        else:
            inserted = "".join(
                DNA_ALPHABET[int(rng.choice(4, p=np.asarray(row, dtype=float)))]
                for row in motif.model.probabilities
            )
        if problem.spec.strands == "both" and rng.random() < 0.5:
            inserted = reverse_complement(inserted)
        bounds = _target_bounds(current, length=problem.spec.length) if rng.random() < 0.5 else None
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

    def search(self, problem: CompiledProblem) -> SearchResult:
        if sequence_space_at_most(problem.spec.length, problem.spec.evaluations) is not None:
            return ExhaustiveSearchEngine().search(problem)
        rng = np.random.Generator(np.random.PCG64(problem.spec.seed))
        ledger = _SearchLedger(budget=problem.spec.evaluations)
        states, current = self._initial_states(problem, rng=rng, ledger=ledger)
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
            chain = (chain + 1) % len(states)
        diagnostics = SearchDiagnostics(
            restarts=len(states),
            best_score=ledger.best_feasible_score,
            checkpoints=tuple(ledger.checkpoints),
            restart_final_scores=tuple(result.balance_score for result in current),
            proposals=tuple(
                ProposalSummary(move=move, attempted=attempted[move], accepted=accepted[move])
                for move in move_names
            ),
        )
        return SearchResult(
            evaluations=tuple(ledger.evaluations.values()),
            evaluations_used=ledger.evaluations_used,
            unique_evaluations=len(ledger.evaluations),
            completion_status="budget_exhausted",
            search_validation_status="contract_tested",
            diagnostics=diagnostics,
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
        delta = (
            _soft_min(proposed, beta=soft_beta) - _soft_min(current, beta=soft_beta)
            if proposed.constraint_feasible
            else current.max_avoidance_excess - proposed.max_avoidance_excess
        )
        return delta >= 0.0 or math.log(max(float(rng.random()), 1.0e-300)) < (
            _mcmc_beta(progress) * delta
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
