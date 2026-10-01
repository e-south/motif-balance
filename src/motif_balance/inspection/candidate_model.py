"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/inspection/candidate_model.py

Path-free review of a supplied candidate, without invented search provenance.

Module Author(s): Eric J. South
Dunlop Lab
--------------------------------------------------------------------------------
"""

import math
from typing import Literal, Self

from pydantic import model_validator

from motif_balance.model import FrozenModel, candidate_id_for_sequence

from .model import InspectionCandidate, InspectionProblem


def validate_candidate_binding(problem: InspectionProblem, candidate: InspectionCandidate) -> None:
    """Check projected identities and positional support without scanning DNA.

    Scoring remains the producer's responsibility. This shared boundary prevents
    a renderer from combining an otherwise valid candidate with another request.
    """
    if (
        candidate.candidate_id != candidate_id_for_sequence(candidate.sequence)
        or len(candidate.sequence) != problem.length
        or set(candidate.sequence) - set("ACGT")
        or tuple(m.motif_id for m in candidate.matches) != tuple(m.motif_id for m in problem.motifs)
    ):
        raise ValueError("candidate projection does not match its problem")
    for match, motif in zip(candidate.matches, problem.motifs, strict=True):
        if (
            match.spec_direction != motif.direction
            or match.end - match.start != motif.width
            or (problem.strands == "forward" and match.strand != "+")
        ):
            raise ValueError("candidate site or direction differs from its problem")
        for support in match.position_support:
            base_index = "ACGT".index(support.observed_base)
            strand = candidate.sequence if match.strand == "+" else candidate.complement_sequence
            if (
                support.observed_base != strand[support.candidate_position]
                or not math.isclose(
                    support.model_probability,
                    motif.probabilities[support.motif_position][base_index],
                    rel_tol=0.0,
                    abs_tol=1e-12,
                )
                or not math.isclose(
                    support.background_probability,
                    motif.background[base_index],
                    rel_tol=0.0,
                    abs_tol=1e-12,
                )
            ):
                raise ValueError("candidate positional support differs from its problem")


class CandidateInspection(FrozenModel):
    schema_version: Literal["motif-balance.candidate-inspection/v2"] = (
        "motif-balance.candidate-inspection/v2"
    )
    subject_kind: Literal["caller_supplied_candidate"] = "caller_supplied_candidate"
    rank_scope: Literal["caller_supplied_order"] = "caller_supplied_order"
    validation_scope: Literal["score_replay"] = "score_replay"
    problem: InspectionProblem
    candidate: InspectionCandidate

    @model_validator(mode="after")
    def validate_binding(self) -> Self:
        try:
            validate_candidate_binding(self.problem, self.candidate)
            if self.candidate.nearest_neighbor_distance is not None:
                raise ValueError("a supplied candidate has no portfolio neighbors")
        except ValueError as exc:
            raise ValueError(f"supplied candidate projection: {exc}") from exc
        return self
