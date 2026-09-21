"""Shared column-regret calculation for pair and joint assessments.

Maintainer(s): Eric J. South, Dunlop Lab
"""

from __future__ import annotations

import numpy as np

from motif_balance.compile import _compile_motif
from motif_balance.model import MotifModel
from motif_balance.model.assessment import AssessedMotif


def column_regret(model: MotifModel) -> tuple[np.ndarray, float, AssessedMotif]:
    """Return each base's weighted column loss, total weight, and model identity."""
    odds = _compile_motif(model).log_odds
    spans = np.ptp(odds, axis=1)
    # Scale each column separately: its preferred base has no local loss.
    preferences = np.divide(
        odds - odds.min(axis=1)[:, None],
        spans[:, None],
        out=np.ones_like(odds),
        where=spans[:, None] > 0,
    )
    probabilities = np.asarray(model.probabilities, dtype=float)
    weights = np.clip(1 + np.sum(probabilities * np.log2(probabilities), axis=1) / 2, 0, 1)
    # A background-shaped column has no score preference, even when its entropy
    # differs from the uniform reference. It cannot create a base conflict.
    weights[spans == 0] = 0
    return (
        weights[:, None] * (1 - preferences),
        float(weights.sum()),
        AssessedMotif(
            motif_id=model.motif_id,
            model_digest=model.model_digest,
            width=model.width,
            zero_range_columns=tuple(int(i) for i in np.flatnonzero(spans == 0)),
        ),
    )
