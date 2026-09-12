"""Path-free column evidence for one pre-search arrangement; never a candidate."""

from __future__ import annotations

import math
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from motif_balance.model import MotifModel
from motif_balance.model.assessment import PairAssessment
from motif_balance.model.base import FrozenModel

_Index = Annotated[int, Field(strict=True, ge=0)]
_Regret = Annotated[float, Field(strict=True, ge=0, le=2, allow_inf_nan=False)]


class AssessmentColumn(FrozenModel):
    coordinate: _Index
    left_position: _Index | None
    right_position: _Index | None
    base_regrets: tuple[_Regret, _Regret, _Regret, _Regret]
    minimum_regret: _Regret
    kind: Literal["unshared", "agreement", "conflict"]

    @model_validator(mode="after")
    def validate_minimum(self) -> Self:
        minimum = min(self.base_regrets)
        kind = (
            "unshared"
            if self.left_position is None or self.right_position is None
            else "conflict"
            if minimum > 1e-12
            else "agreement"
        )
        if self.minimum_regret != minimum or self.kind != kind:
            raise ValueError("column minimum or conflict classification disagrees")
        return self


class PairAssessmentInspection(FrozenModel):
    schema_version: Literal["pair-assessment-inspection/v1"] = "pair-assessment-inspection/v1"
    assessment: PairAssessment
    motifs: tuple[MotifModel, MotifModel]
    columns: tuple[AssessmentColumn, ...]

    @model_validator(mode="after")
    def validate_projection(self) -> Self:
        for motif, reference in zip(self.motifs, self.assessment.motifs, strict=True):
            if (motif.motif_id, motif.model_digest, motif.width) != (
                reference.motif_id,
                reference.model_digest,
                reference.width,
            ):
                raise ValueError("assessment projection does not match its model identities")
            if any(not math.isclose(b, 0.25, rel_tol=0, abs_tol=1e-12) for b in motif.background):
                raise ValueError(
                    "standard information-logo inspection requires uniform backgrounds"
                )
        if len(self.columns) != self.assessment.length:
            raise ValueError("assessment projection must retain every coordinate")
        best = self.assessment.best_arrangement
        left, right = self.motifs
        for i, column in enumerate(self.columns):
            a = i - best.left_start if best.left_start <= i < best.left_start + left.width else None
            b = (
                i - best.right_start
                if best.right_start <= i < best.right_start + right.width
                else None
            )
            if b is not None and best.right_strand == "-":
                b = right.width - 1 - b
            if (column.coordinate, column.left_position, column.right_position) != (i, a, b):
                raise ValueError("assessment columns disagree with the selected arrangement")
        score = (
            1
            - 2
            * sum(c.minimum_regret for c in self.columns)
            / self.assessment.effective_information_bits
        )
        if not math.isclose(score, self.assessment.structural_score, rel_tol=0, abs_tol=1e-12):
            raise ValueError("column regrets disagree with the reported structural score")
        return self
