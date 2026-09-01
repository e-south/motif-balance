from __future__ import annotations

import math

from motif_balance.errors import ArtifactError

from ..limits import MAX_SVG_MATCHES
from ..model import InspectionCandidate, InspectionMatch, InspectionProblem, ResultInspection
from .svg_primitives import candidate_id

_BASE_INDEX = {base: index for index, base in enumerate("ACGT")}


def select_candidate(inspection: ResultInspection, rank: int) -> InspectionCandidate:
    """Select one rank from an already verified result inspection."""

    for candidate in inspection.portfolio.candidates:
        if candidate.rank == rank:
            candidate_id(candidate.candidate_id)
            return candidate
    raise ArtifactError(f"candidate rank {rank} is not present in this result")


def shown_matches(candidate: InspectionCandidate) -> tuple[InspectionMatch, ...]:
    """Return the bounded deterministic match projection used by the SVG."""

    ordered = tuple(
        sorted(
            (*candidate.matches, *candidate.avoidance_matches),
            key=lambda match: (
                match.motif_id not in candidate.limiting_motif_ids,
                match.motif_id,
                match.start,
                match.strand,
            ),
        )
    )
    return ordered[:MAX_SVG_MATCHES]


def validate_candidate_projection(
    problem: InspectionProblem,
    candidate: InspectionCandidate,
) -> None:
    """Reject a candidate that is not bound to the supplied verified problem."""

    target_ids = {motif.motif_id for motif in problem.motifs}
    avoider_ids = {motif.motif_id for motif in problem.avoiders}
    if (
        len(candidate.sequence) != problem.length
        or {match.motif_id for match in candidate.matches} != target_ids
        or {match.motif_id for match in candidate.avoidance_matches} != avoider_ids
    ):
        raise ArtifactError("candidate render projection does not match its problem")
    motifs_by_id = {motif.motif_id: motif for motif in (*problem.motifs, *problem.avoiders)}
    for match in (*candidate.matches, *candidate.avoidance_matches):
        motif = motifs_by_id[match.motif_id]
        if match.end - match.start != motif.width:
            raise ArtifactError("candidate render projection does not match its problem")
        for support in match.position_support:
            base_index = _BASE_INDEX[support.observed_base]
            expected_base = (
                candidate.sequence[support.candidate_position]
                if match.strand == "+"
                else candidate.complement_sequence[support.candidate_position]
            )
            expected_probability = motif.probabilities[support.motif_position][base_index]
            expected_background = motif.background[base_index]
            if (
                support.observed_base != expected_base
                or not math.isclose(
                    support.model_probability,
                    expected_probability,
                    rel_tol=0.0,
                    abs_tol=1.0e-12,
                )
                or not math.isclose(
                    support.background_probability,
                    expected_background,
                    rel_tol=0.0,
                    abs_tol=1.0e-12,
                )
            ):
                raise ArtifactError("candidate render projection does not match its problem")
