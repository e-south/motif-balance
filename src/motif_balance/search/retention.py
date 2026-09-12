"""Bounded hash-priority retention; no RNG or alternate scoring authority."""

from __future__ import annotations

import hashlib
from bisect import insort

from motif_balance.model import Evaluation
from motif_balance.model.search_observation import QualitySample


class QualityRetention:
    """Keep the lowest SHA-256 priorities among unique qualifying sequences.

    The existing search ledger supplies discovery identity; this observer adds no
    unbounded seen-set. A repeated scoring request counts as work, never as a new
    sequence. Exact sequences are the unit; strand equivalence is analysis-owned.
    """

    def __init__(self, thresholds: tuple[float, ...], capacity: int) -> None:
        self.capacity = capacity
        self.thresholds = thresholds
        self.qualifying = dict.fromkeys(thresholds, 0)
        self.unique = dict.fromkeys(thresholds, 0)
        self.rows: dict[float, list[tuple[str, str, Evaluation]]] = {
            threshold: [] for threshold in thresholds
        }

    def record(self, evaluation: Evaluation, *, is_new: bool) -> None:
        priority: str | None = None
        for threshold in self.thresholds:
            if evaluation.balance_score < threshold:
                break
            self.qualifying[threshold] += 1
            if not is_new:
                continue
            self.unique[threshold] += 1
            if priority is None:
                priority = hashlib.sha256(evaluation.sequence.encode()).hexdigest()
            row = (priority, evaluation.sequence, evaluation)
            retained = self.rows[threshold]
            if len(retained) < self.capacity or row[:2] < retained[-1][:2]:
                insort(retained, row, key=lambda item: item[:2])
                if len(retained) > self.capacity:
                    retained.pop()

    def finish(self) -> tuple[QualitySample, ...]:
        return tuple(
            QualitySample(
                threshold=threshold,
                qualifying_evaluations=self.qualifying[threshold],
                unique_sequences=self.unique[threshold],
                evaluations=tuple(row[2] for row in self.rows[threshold]),
            )
            for threshold in self.thresholds
        )
