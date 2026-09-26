"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/playback/model.py

Describe bounded, verified search frames for presentation.

Module Author(s): Eric J. South
Dunlop Lab
--------------------------------------------------------------------------------
"""

from typing import Annotated, Any, Literal, Self

from pydantic import Field, model_validator

from motif_balance.inspection.model import InspectionCandidate, InspectionProblem
from motif_balance.model.base import FrozenModel


class PlaybackFrame(FrozenModel):
    evaluations: Annotated[int, Field(strict=True, gt=0)]
    best_balance: Annotated[float, Field(strict=True, ge=0, le=1, allow_inf_nan=False)]
    candidate: InspectionCandidate
    search_candidate: InspectionCandidate | None = None
    search_candidates: Annotated[tuple[InspectionCandidate, ...], Field(max_length=8)] = ()
    search_evaluations: Annotated[int, Field(strict=True, gt=0)] | None = None

    @property
    def recorded_search_candidates(self) -> tuple[InspectionCandidate, ...]:
        return self.search_candidates or ((self.search_candidate,) if self.search_candidate else ())


class PlaybackInspection(FrozenModel):
    """One sampled incumbent history or one identified chain, with the same best-score trace."""

    schema_version: Literal["playback-inspection/v2"] = "playback-inspection/v2"
    observation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    problem: InspectionProblem
    engine: str
    chain_id: Annotated[int, Field(strict=True, ge=0, lt=8)] | None = None
    search_chain_id: Annotated[int, Field(strict=True, ge=0, lt=8)] | Literal["all"] | None = None
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
        previous_search_candidates: tuple[InspectionCandidate, ...] = ()
        for frame in self.frames:
            if frame.search_candidates and self.search_chain_id != "all":
                raise ValueError("multiple search candidates require the all-chain view")
            if self.search_chain_id == "all" and frame.search_candidate is not None:
                raise ValueError("the all-chain view requires an ordered candidate collection")
            candidates = frame.recorded_search_candidates
            if bool(candidates) != (frame.search_evaluations is not None):
                raise ValueError("a search candidate requires its recorded evaluation count")
            if candidates:
                assert frame.search_evaluations is not None
                if self.search_chain_id is None:
                    raise ValueError("a search candidate requires an identified chain")
                if frame.search_evaluations > frame.evaluations:
                    raise ValueError("a search overlay cannot show a future observation")
                if any(c.balance_score > frame.best_balance + 1e-12 for c in candidates):
                    raise ValueError("a search candidate cannot exceed the recorded best score")
                if previous_search_candidates and len(candidates) != len(
                    previous_search_candidates
                ):
                    raise ValueError("recorded search chains cannot appear or disappear")
                if frame.search_evaluations < previous_search_count or (
                    frame.search_evaluations == previous_search_count
                    and candidates != previous_search_candidates
                ):
                    raise ValueError("search observations must retain their chronological identity")
                previous_search_count = frame.search_evaluations
                previous_search_candidates = candidates
            elif previous_search_count:
                raise ValueError("a recorded search state cannot disappear from later frames")
            if frame.candidate.balance_score > frame.best_balance + 1e-12:
                raise ValueError("a displayed state cannot exceed the recorded best score")
            if self.chain_id is None and frame.candidate.balance_score != frame.best_balance:
                raise ValueError("incumbent frames must show the recorded best score")
        if self.search_chain_id is not None and not previous_search_count:
            raise ValueError("a search overlay requires at least one recorded chain state")
        return self

    def until_last_improvement(self) -> Self:
        """Keep the prefix ending at the first recorded occurrence of the final best.

        This selects observations, not the unknown evaluation at which a best
        candidate was discovered between checkpoints. The source stays unchanged.
        """
        checked = type(self).model_validate(self.model_dump(mode="python"))
        if checked.chain_id is not None:
            raise ValueError("last-improvement selection requires the best-sequence view")
        last_score = checked.frames[-1].best_balance
        index = next(i for i, f in enumerate(checked.frames) if f.best_balance == last_score)
        frames = checked.frames[: index + 1]
        updates: dict[str, Any] = {"frames": frames}
        if not any(f.recorded_search_candidates for f in frames):
            updates["search_chain_id"] = None
        return type(self).model_validate(
            checked.model_copy(update=updates).model_dump(mode="python")
        )
