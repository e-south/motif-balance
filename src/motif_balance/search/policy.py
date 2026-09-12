from __future__ import annotations

import math
from typing import cast

import numpy as np
from numpy.typing import NDArray

from motif_balance.constants import (
    DNA_ALPHABET,
)
from motif_balance.model import (
    Evaluation,
)


def _soft_min(result: Evaluation, *, beta: float) -> float:
    scores = np.asarray(
        [
            match.spec_satisfaction
            if match.spec_satisfaction is not None
            else match.normalized_score
            for match in result.matches
        ],
        dtype=float,
    )
    floor = float(np.min(scores))
    return floor - math.log(float(np.exp(-beta * (scores - floor)).sum())) / beta


def _sequence(values: np.ndarray) -> str:
    return "".join(DNA_ALPHABET[int(value)] for value in values)


def _annealing_beta(progress: float) -> float:
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
