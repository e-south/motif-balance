"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/inspection/collection.py

Rescore selected collection members without inventing a search history.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from motif_balance.errors import ArtifactError
from motif_balance.model import Candidate, candidate_id_for_sequence
from motif_balance.model.alternatives import CollectionReport

from .candidate_model import CandidateInspection
from .limits import MAX_INSPECTION_SUPPORT_ROWS
from .supplied import inspect_candidate


def inspect_collection(
    report: CollectionReport, *, candidate_rank: int | None = None
) -> tuple[CandidateInspection, ...]:
    """Check every displayed member's scores and sites against the saved models."""
    if not isinstance(report, CollectionReport):
        raise ArtifactError("Collection inspection requires a CollectionReport")
    report = CollectionReport.model_validate(report.model_dump(mode="python"))
    members = report.collection.members
    if candidate_rank is not None:
        if type(candidate_rank) is not int or candidate_rank < 1:
            raise ArtifactError("candidate rank must be a positive integer")
        members = tuple(m for m in members if m.rank == candidate_rank)
    if not members:
        raise ArtifactError("No selected collection member has the requested rank")
    if (
        len(members) * sum(s.motif.width for s in report.ranking.spec.specifications)
        > MAX_INSPECTION_SUPPORT_ROWS
    ):
        raise ArtifactError(
            "Collection exceeds the projection limit; select one member with --candidate"
        )
    return tuple(
        inspect_candidate(
            Candidate(
                candidate_id=candidate_id_for_sequence(member.evaluation.sequence),
                rank=member.rank,
                **member.evaluation.model_dump(),
            ),
            report.ranking.spec,
        )
        for member in members
    )
