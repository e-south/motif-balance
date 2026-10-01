"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/inspection/render/candidate_projection.py

Select and validate the candidate and matches admitted to a molecular view.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from __future__ import annotations

from motif_balance.errors import ArtifactError

from ..candidate_model import validate_candidate_binding
from ..limits import MAX_SVG_MATCHES
from ..model import InspectionCandidate, InspectionMatch, InspectionProblem, ResultInspection
from .svg_primitives import candidate_id


def select_candidate(inspection: ResultInspection, rank: int) -> InspectionCandidate:
    """Select one rank from an already verified result inspection."""

    for candidate in inspection.portfolio.candidates:
        if candidate.rank == rank:
            candidate_id(candidate.candidate_id)
            return candidate
    raise ArtifactError(f"candidate rank {rank} is not present in this result")


def shown_matches(candidate: InspectionCandidate) -> tuple[InspectionMatch, ...]:
    """Return complete deterministic lanes or refuse an incomplete molecular view."""

    ordered = tuple(
        sorted(
            candidate.matches,
            key=lambda match: (
                match.motif_id not in candidate.limiting_motif_ids,
                match.motif_id,
                match.start,
                match.strand,
            ),
        )
    )
    if len(ordered) > MAX_SVG_MATCHES:
        raise ArtifactError(
            f"candidate visual has {len(ordered)} matches, exceeding limit {MAX_SVG_MATCHES}; "
            "use inspection JSON for complete records"
        )
    return ordered


def validate_candidate_projection(
    problem: InspectionProblem,
    candidate: InspectionCandidate,
) -> None:
    """Reject a candidate that is not bound to the supplied verified problem."""

    try:
        validate_candidate_binding(problem, candidate)
    except ValueError as exc:
        raise ArtifactError(
            f"candidate render projection does not match its problem: {exc}"
        ) from exc
