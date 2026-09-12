"""Exhaustive literal-sequence oracle independent of the arrangement calculation."""

from __future__ import annotations

import itertools
import math

import pytest

from motif_balance import MotifModel
from motif_balance.assessment import assess_pair


def _literal_regret(model, sequence, start, strand):
    word = sequence[start : start + model.width]
    if strand == "-":
        word = word.translate(str.maketrans("ACGT", "TGCA"))[::-1]
    cost, weights = [], []
    for probabilities, base in zip(model.probabilities, word, strict=True):
        odds = [math.log2(p / q) for p, q in zip(probabilities, model.background, strict=True)]
        span = max(odds) - min(odds)
        weight = max(0, min(1, 1 + sum(p * math.log2(p) for p in probabilities) / 2)) if span else 0
        weights.append(weight)
        cost.append(weight * (max(odds) - odds["ACGT".index(base)]) / span if span else 0)
    return math.fsum(cost), math.fsum(weights)


@pytest.mark.parametrize("strands", ["forward", "both"])
@pytest.mark.parametrize("length", [3, 4])
def test_full_sequence_enumeration_agrees_with_each_arrangement_and_overall_score(length, strands):
    left = MotifModel(
        motif_id="left",
        probabilities=((0.55, 0.15, 0.2, 0.1), (0.1, 0.5, 0.3, 0.1)),
        background=(0.4, 0.3, 0.2, 0.1),
    )
    right = MotifModel(
        motif_id="right",
        probabilities=((0.1, 0.2, 0.15, 0.55), (0.1, 0.2, 0.6, 0.1), (0.7, 0.1, 0.1, 0.1)),
        background=(0.25, 0.25, 0.25, 0.25),
    )
    words = ["".join(bases) for bases in itertools.product("ACGT", repeat=length)]

    def exact_for_arrangement(a, b, sa, sb):
        losses = []
        for sequence in words:
            ca, wa = _literal_regret(left, sequence, a, sa)
            cb, wb = _literal_regret(right, sequence, b, sb)
            losses.append((ca + cb) / (wa + wb))
        return 1 - min(losses)

    result = assess_pair(left, right, length=length, strands=strands)
    for arrangement in result.arrangements:
        assert arrangement.structural_score == pytest.approx(
            exact_for_arrangement(
                arrangement.left_start,
                arrangement.right_start,
                arrangement.left_strand,
                arrangement.right_strand,
            ),
            abs=1e-12,
            rel=0,
        )
    orientations = ("+",) if strands == "forward" else ("+", "-")
    full_absolute_scores = [
        exact_for_arrangement(a, b, sa, sb)
        for a in range(length - left.width + 1)
        for b in range(length - right.width + 1)
        for sa in orientations
        for sb in orientations
    ]
    assert result.structural_score == pytest.approx(max(full_absolute_scores), abs=1e-12, rel=0)
    # Swapping caller labels cannot change the best conflict value.
    assert assess_pair(
        right, left, length=length, strands=strands
    ).structural_score == pytest.approx(result.structural_score, abs=1e-12, rel=0)
