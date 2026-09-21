"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/alternatives/api.py

Score a supplied pool once, then rank its selected-match architectures.

Module Author(s): Eric J. South
Dunlop Lab
--------------------------------------------------------------------------------
"""

from __future__ import annotations

from collections import Counter

from motif_balance.compile import compile_scoring
from motif_balance.constants import (
    MAX_ARCHITECTURE_DISTANCE_BASE_BUDGET,
    MAX_ARCHITECTURE_DISTANCE_PAIRS,
    MAX_ARCHITECTURE_PREPARED_PAIRS,
    MAX_DISTANCE_BASE_COMPARISONS,
)
from motif_balance.model import DesignSpec, Evaluation
from motif_balance.model.alternatives import (
    ArchitectureClass,
    ArchitectureGrouping,
    ArchitecturePrefix,
    ArchitectureRanking,
    ArchitectureRepresentative,
    architecture_class,
    architecture_distance_work,
    architecture_key,
)
from motif_balance.scoring import evaluate

from .geometry import pair_distances, prepare_distances
from .pool import prepare_pool


def _distance_admission(count: int, spec: DesignSpec, budget: int) -> int:
    pairs, terms, prepared = architecture_distance_work(count, spec)
    if (
        terms > budget
        or pairs > MAX_ARCHITECTURE_DISTANCE_PAIRS
        or prepared > MAX_ARCHITECTURE_PREPARED_PAIRS
    ):
        raise ValueError("architecture ranking exceeds the distance-comparison limit")
    return terms


def _prefixes(evaluations: tuple[Evaluation, ...], *, both: bool) -> tuple[ArchitecturePrefix, ...]:
    prepared = [prepare_distances(e) for e in evaluations] if len(evaluations) > 1 else []
    totals, result = [0.0] * 4, []
    weakest = 1.0
    for index, evaluation in enumerate(evaluations):
        for prior in prepared[:index]:
            for axis, value in enumerate(pair_distances(prepared[index], prior, both=both)):
                totals[axis] += value
        count = index + 1
        denominator = count * (count - 1) // 2
        means = [value / denominator if denominator else None for value in totals]
        weakest = min(weakest, evaluation.balance_score)
        result.append(
            ArchitecturePrefix(
                architecture_count=count,
                minimum_balance=weakest,
                mean_sequence_distance=means[0],
                mean_selected_footprint_distance=means[1],
                mean_spacing_distance_nt=means[2],
                mean_orientation_difference=means[3],
            )
        )
    return tuple(result)


def measure_prefixes(
    ranking: ArchitectureRanking, order: tuple[str, ...] | list[str]
) -> tuple[ArchitecturePrefix, ...]:
    """Measure a complete explicit representative order, without scoring or editing.

    Order is caller-owned and need not descend by quality. Each prefix reports
    its actual weakest score. No subset, duplicate or new sequence is accepted.
    """
    if not isinstance(ranking, ArchitectureRanking):
        raise ValueError("prefix measurement requires a current architecture ranking")
    records = {r.evaluation.sequence: r.evaluation for r in ranking.representatives}
    if (
        not isinstance(order, (tuple, list))
        or len(order) != len(records)
        or any(not isinstance(word, str) for word in order)
        or len(set(order)) != len(order)
        or set(order) != set(records)
    ):
        raise ValueError("prefix order must be a complete permutation of the representatives")
    _distance_admission(len(records), ranking.spec, ranking.distance_base_budget)
    if tuple(order) == tuple(records):
        return ranking.prefixes
    return _prefixes(tuple(records[word] for word in order), both=ranking.spec.strands == "both")


def rank_architectures(
    sequences: tuple[str, ...] | list[str],
    spec: DesignSpec,
    *,
    grouping: ArchitectureGrouping = "exact_offsets",
    distance_base_budget: int = MAX_DISTANCE_BASE_COMPARISONS,
) -> ArchitectureRanking:
    """Score canonical sequence classes and expose every ranked architecture prefix.

    The pool is explicit, not sampled or searched here. Canonicalization precedes
    scoring so duplicate reverse complements cannot change selected-site ties.
    Selection subsequently returns unchanged evaluations, not edited candidates.
    An explicit distance budget changes admission only, never the measurements.
    Independent pair-count and preparation caps apply even at the maximum budget.
    """
    if grouping not in ("exact_offsets", "interval_topology"):
        raise ValueError("grouping must be exact_offsets or interval_topology")
    if (
        type(distance_base_budget) is not int
        or not 1 <= distance_base_budget <= MAX_ARCHITECTURE_DISTANCE_BASE_BUDGET
    ):
        raise ValueError("architecture distance budget must be an integer in [1, 500000000]")
    pool = prepare_pool(sequences, spec)
    both = spec.strands == "both"
    canonical = pool.canonical_sequences
    problem = compile_scoring(spec)
    best: dict[ArchitectureClass, Evaluation] = {}
    counts: Counter[ArchitectureClass] = Counter()
    for sequence in canonical:
        evaluation = evaluate(sequence, problem)
        geometry = architecture_class(evaluation, both=both, grouping=grouping)
        counts[geometry] += 1
        prior = best.get(geometry)
        if prior is None or (-evaluation.balance_score, sequence) < (
            -prior.balance_score,
            prior.sequence,
        ):
            best[geometry] = evaluation
    ranked = sorted(best.items(), key=lambda item: (-item[1].balance_score, item[1].sequence))
    terms = _distance_admission(len(ranked), spec, distance_base_budget)
    representatives = []
    prefixes = _prefixes(tuple(e for _, e in ranked), both=both)
    for index, (geometry, evaluation) in enumerate(ranked):
        count = index + 1
        representatives.append(
            ArchitectureRepresentative(
                rank=count,
                evaluation=evaluation,
                geometry=architecture_key(evaluation, both=both),
                architecture_class=geometry,
                sequence_classes=counts[geometry],
            )
        )
    return ArchitectureRanking(
        grouping=grouping,
        spec=spec,
        pool_digest=pool.digest,
        input_records=len(pool.sequences),
        literal_sequences=pool.literal_count,
        sequence_classes=len(canonical),
        scoring_evaluations=len(canonical),
        distance_base_budget=distance_base_budget,
        distance_base_operations=terms,
        representatives=tuple(representatives),
        prefixes=tuple(prefixes),
    )
