from __future__ import annotations

from ..model import ResultInspection
from .candidate_projection import select_candidate
from .candidate_sections import render_candidate_projection_svg


def render_candidate_svg(
    inspection: ResultInspection,
    *,
    candidate_rank: int = 1,
) -> bytes:
    """Render the exact strand-aware realization for one selected candidate."""

    candidate = select_candidate(inspection, candidate_rank)
    return render_candidate_projection_svg(inspection.problem, candidate)
