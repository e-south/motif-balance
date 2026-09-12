"""Path-free review of a supplied candidate, without invented search provenance."""

from typing import Literal, Self

from pydantic import model_validator

from motif_balance.model import FrozenModel, candidate_id_for_sequence

from .model import InspectionCandidate, InspectionProblem


class CandidateInspection(FrozenModel):
    schema_version: Literal["motif-balance.candidate-inspection/v1"] = (
        "motif-balance.candidate-inspection/v1"
    )
    subject_kind: Literal["caller_supplied_candidate"] = "caller_supplied_candidate"
    rank_scope: Literal["caller_supplied_order"] = "caller_supplied_order"
    validation_scope: Literal["score_replay"] = "score_replay"
    problem: InspectionProblem
    candidate: InspectionCandidate

    @model_validator(mode="after")
    def validate_binding(self) -> Self:
        candidate, problem = self.candidate, self.problem
        if (
            candidate.candidate_id != candidate_id_for_sequence(candidate.sequence)
            or len(candidate.sequence) != problem.length
            or tuple(match.motif_id for match in candidate.matches)
            != tuple(motif.motif_id for motif in problem.motifs)
            or candidate.avoidance_matches
            or problem.avoiders
            or candidate.nearest_neighbor_distance is not None
        ):
            raise ValueError(
                "supplied candidate projection is not bound to its directional problem"
            )
        if any(
            match.spec_direction != motif.direction or motif.direction is None
            for match, motif in zip(candidate.matches, problem.motifs, strict=True)
        ):
            raise ValueError("supplied candidate directions differ from the problem")
        return self
