"""Describe bounded, verified search frames for presentation.

Maintainer(s): Eric J. South, Dunlop Lab
"""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from motif_balance.inspection.model import InspectionCandidate, InspectionProblem
from motif_balance.model.base import FrozenModel


class PlaybackFrame(FrozenModel):
    evaluations: Annotated[int, Field(strict=True, gt=0)]
    best_balance: Annotated[float, Field(strict=True, ge=0, le=1, allow_inf_nan=False)]
    candidate: InspectionCandidate


class PlaybackInspection(FrozenModel):
    """One sampled incumbent history or one identified chain, with the same best-score trace."""

    schema_version: Literal["playback-inspection/v1"] = "playback-inspection/v1"
    observation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    problem: InspectionProblem
    engine: str
    chain_id: Annotated[int, Field(strict=True, ge=0, lt=8)] | None = None
    frames: Annotated[tuple[PlaybackFrame, ...], Field(min_length=1, max_length=256)]

    @model_validator(mode="after")
    def ordered_frames(self) -> Self:
        counts = [frame.evaluations for frame in self.frames]
        scores = [frame.best_balance for frame in self.frames]
        if counts != sorted(set(counts)) or scores != sorted(scores):
            raise ValueError("playback frames must increase in effort and best score")
        for frame in self.frames:
            if frame.candidate.balance_score > frame.best_balance + 1e-12:
                raise ValueError("a displayed state cannot exceed the recorded best score")
            if self.chain_id is None and frame.candidate.balance_score != frame.best_balance:
                raise ValueError("incumbent frames must show the recorded best score")
        return self
