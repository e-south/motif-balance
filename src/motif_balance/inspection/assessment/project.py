"""Bind the existing assessment calculation to inspectable physical-coordinate terms."""

from __future__ import annotations

from typing import Literal

from motif_balance.assessment import _terms, assess_pair
from motif_balance.model import MotifModel

from .model import AssessmentColumn, PairAssessmentInspection


def inspect_pair_assessment(
    left: MotifModel,
    right: MotifModel,
    *,
    length: int,
    strands: Literal["forward", "both"] = "both",
) -> PairAssessmentInspection:
    """Recompute from explicit models; no saved scores, sequences or paths are trusted."""
    result = assess_pair(left, right, length=length, strands=strands)
    a, _, _ = _terms(left)
    b, _, _ = _terms(right)
    best = result.best_arrangement
    columns = []
    for coordinate in range(length):
        i = (
            coordinate - best.left_start
            if best.left_start <= coordinate < best.left_start + left.width
            else None
        )
        j = (
            coordinate - best.right_start
            if best.right_start <= coordinate < best.right_start + right.width
            else None
        )
        if j is not None and best.right_strand == "-":
            j = right.width - 1 - j
        regrets = tuple(
            float(
                (a[i, base] if i is not None else 0)
                + (b[j, 3 - base if best.right_strand == "-" else base] if j is not None else 0)
            )
            for base in range(4)
        )
        minimum = min(regrets)
        columns.append(
            AssessmentColumn(
                coordinate=coordinate,
                left_position=i,
                right_position=j,
                base_regrets=(regrets[0], regrets[1], regrets[2], regrets[3]),
                minimum_regret=minimum,
                kind="unshared"
                if i is None or j is None
                else "conflict"
                if minimum > 1e-12
                else "agreement",
            )
        )
    return PairAssessmentInspection(assessment=result, motifs=(left, right), columns=tuple(columns))
