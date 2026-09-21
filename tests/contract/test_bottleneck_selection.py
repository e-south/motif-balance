"""Finite-pool selection is checked against literal exhaustive subsets."""

from itertools import combinations
from math import fsum
from random import Random

import pytest

from motif_balance.model import Evaluation, MotifMatch


def evaluated(word, quality):
    # Assigned selector-only scores; these are not a motif experiment.
    return Evaluation(
        sequence=word,
        balance_score=quality,
        matches=(
            MotifMatch(
                motif_id="test",
                start=0,
                end=1,
                strand="+",
                matched_sequence=word[0],
                raw_score=quality,
                spec_direction="seek",
                spec_satisfaction=quality,
                normalized_score=quality,
            ),
        ),
    )


def objective(rows, indices):
    return (
        -min(rows[i].balance_score for i in indices),
        -fsum(rows[i].balance_score for i in indices),
        tuple(sorted(rows[i].sequence for i in indices)),
    )


def test_bottleneck_selector_does_not_stop_at_the_first_feasible_ranked_pair():
    from motif_balance.selection import _bottleneck_subset

    rows = tuple(
        evaluated(word, q)
        for word, q in (("AAAA", 0.99), ("CAAA", 0.90), ("ACAA", 0.89), ("TTTT", 0.30))
    )
    edges = tuple(
        sum(
            1 << j
            for j in range(i + 1, len(rows))
            if sum(a != b for a, b in zip(row.sequence, rows[j].sequence, strict=True)) >= 2
        )
        for i, row in enumerate(rows)
    )
    result = _bottleneck_subset(rows, edges, count=2, work_limit=100)
    assert result.indices == (1, 2)
    assert result.complete
    assert result.work_used <= 100


@pytest.mark.parametrize("count", [1, 2, 3, 4])
def test_bounded_solver_agrees_with_independent_exhaustive_subset_oracle(count):
    from motif_balance.selection import _bottleneck_subset

    rng = Random(29)
    words = ("AAA", "AAC", "AAG", "AAT", "ACA", "ACC", "ACG", "ACT")
    for _ in range(30):
        rows = tuple(
            sorted(
                (evaluated(w, rng.choice((0.3, 0.7, 0.9))) for w in words),
                key=lambda e: (-e.balance_score, e.sequence),
            )
        )
        allowed = {pair for pair in combinations(range(len(rows)), 2) if rng.random() < 0.65}
        edges = tuple(
            sum(1 << j for j in range(i + 1, len(rows)) if (i, j) in allowed)
            for i in range(len(rows))
        )
        valid = [
            subset
            for subset in combinations(range(len(rows)), count)
            if all(pair in allowed for pair in combinations(subset, 2))
        ]
        expected = min(valid, key=lambda subset: objective(rows, subset)) if valid else ()
        result = _bottleneck_subset(rows, edges, count=count, work_limit=100_000)
        assert result.complete
        assert result.indices == expected


def test_work_exhaustion_distinguishes_a_feasible_witness_from_no_witness():
    from motif_balance.selection import _bottleneck_subset

    rows = tuple(evaluated(w, 0.5) for w in ("AA", "AC", "AG", "AT"))
    edges = (14, 12, 8, 0)
    early = _bottleneck_subset(rows, edges, count=2, work_limit=1)
    found = _bottleneck_subset(rows, edges, count=2, work_limit=3)
    assert early.indices == () and not early.complete
    assert len(found.indices) == 2 and not found.complete
    assert early.work_used == 1 and found.work_used == 3


def test_infeasible_empty_and_undersized_pools_finish_without_a_false_witness():
    from motif_balance.selection import _bottleneck_subset

    for rows in ((), (evaluated("AA", 0.5),)):
        result = _bottleneck_subset(rows, (0,) * len(rows), count=2, work_limit=10)
        assert result.indices == () and result.complete
