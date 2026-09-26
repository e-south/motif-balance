"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/playback/model.py

Describe bounded, verified search frames for presentation.

Module Author(s): Eric J. South
Dunlop Lab
--------------------------------------------------------------------------------
"""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from motif_balance.inspection.model import InspectionCandidate, InspectionProblem
from motif_balance.model.base import FrozenModel


class PlaybackFrame(FrozenModel):
    evaluations: Annotated[int, Field(strict=True, gt=0)]
    best_balance: Annotated[float, Field(strict=True, ge=0, le=1, allow_inf_nan=False)]
    candidate: InspectionCandidate
    search_candidate: InspectionCandidate | None = None
    search_evaluations: Annotated[int, Field(strict=True, gt=0)] | None = None


class PlaybackInspection(FrozenModel):
    """One sampled incumbent history or one identified chain, with the same best-score trace."""

    schema_version: Literal["playback-inspection/v1"] = "playback-inspection/v1"
    observation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    problem: InspectionProblem
    engine: str
    chain_id: Annotated[int, Field(strict=True, ge=0, lt=8)] | None = None
    search_chain_id: Annotated[int, Field(strict=True, ge=0, lt=8)] | None = None
    frames: Annotated[tuple[PlaybackFrame, ...], Field(min_length=1, max_length=256)]

    @model_validator(mode="after")
    def ordered_frames(self) -> Self:
        if self.chain_id is not None and self.search_chain_id is not None:
            raise ValueError("a search overlay requires an incumbent view, not another chain")
        counts = [frame.evaluations for frame in self.frames]
        scores = [frame.best_balance for frame in self.frames]
        if counts != sorted(set(counts)) or scores != sorted(scores):
            raise ValueError("playback frames must increase in effort and best score")
        previous_search_count = 0
        previous_search_candidate = None
        for frame in self.frames:
            if (frame.search_candidate is None) != (frame.search_evaluations is None):
                raise ValueError("a search candidate requires its recorded evaluation count")
            if frame.search_candidate is not None:
                assert frame.search_evaluations is not None
                if self.search_chain_id is None:
                    raise ValueError("a search candidate requires an identified chain")
                if frame.search_evaluations > frame.evaluations:
                    raise ValueError("a search overlay cannot show a future observation")
                if frame.search_candidate.balance_score > frame.best_balance + 1e-12:
                    raise ValueError("a search candidate cannot exceed the recorded best score")
                if frame.search_evaluations < previous_search_count or (
                    frame.search_evaluations == previous_search_count
                    and frame.search_candidate != previous_search_candidate
                ):
                    raise ValueError("search observations must retain their chronological identity")
                previous_search_count = frame.search_evaluations
                previous_search_candidate = frame.search_candidate
            elif previous_search_count:
                raise ValueError("a recorded search state cannot disappear from later frames")
            if frame.candidate.balance_score > frame.best_balance + 1e-12:
                raise ValueError("a displayed state cannot exceed the recorded best score")
            if self.chain_id is None and frame.candidate.balance_score != frame.best_balance:
                raise ValueError("incumbent frames must show the recorded best score")
        if self.search_chain_id is not None and not previous_search_count:
            raise ValueError("a search overlay requires at least one recorded chain state")
        return self
