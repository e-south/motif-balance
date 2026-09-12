from __future__ import annotations

from motif_balance.errors import ArtifactError

from ..candidate_model import CandidateInspection
from ..model import ResultInspection
from .candidate_projection import select_candidate
from .candidate_sections import render_candidate_projection_svg


def render_candidate_svg(
    inspection: ResultInspection | CandidateInspection,
    *,
    candidate_rank: int | None = None,
) -> bytes:
    """Render one inspected candidate without rescoring or inventing a source result."""

    if candidate_rank is not None and (type(candidate_rank) is not int or candidate_rank < 1):
        raise ArtifactError("candidate rank must be a positive integer")
    if isinstance(inspection, CandidateInspection):
        if candidate_rank is not None and candidate_rank != inspection.candidate.rank:
            raise ArtifactError(
                f"candidate rank {candidate_rank} is not present in this inspection"
            )
        return render_candidate_projection_svg(
            inspection.problem, inspection.candidate, rank_scope=inspection.rank_scope
        )
    candidate = select_candidate(inspection, 1 if candidate_rank is None else candidate_rank)
    return render_candidate_projection_svg(inspection.problem, candidate)
