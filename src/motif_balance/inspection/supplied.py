"""Replay one caller-owned candidate through the existing score and projection authorities."""

from motif_balance.compile import compile_scoring
from motif_balance.errors import ArtifactError
from motif_balance.model import Candidate, DesignSpec

from . import project
from .candidate_model import CandidateInspection


def inspect_candidate(candidate: Candidate, spec: DesignSpec) -> CandidateInspection:
    """Explain a supplied directional candidate; its rank and provenance remain caller-owned.

    Replay every evaluation field exactly once, with no search or file access.
    This does not verify a search bundle, the pool's completeness, or its ranking.
    """
    if not isinstance(candidate, Candidate) or not isinstance(spec, DesignSpec):
        raise ArtifactError("candidate inspection requires a Candidate and a DesignSpec")
    # Revalidate copied models; model_copy(update=...) deliberately bypasses validation.
    spec = DesignSpec.model_validate(spec.model_dump(mode="python"))
    candidate = Candidate.model_validate(candidate.model_dump(mode="python"))
    if spec.schema_version != "design-spec/v3":
        raise ArtifactError("supplied candidate inspection requires a current directional request")
    project._check_support_limit(spec)
    problem = compile_scoring(spec)
    return CandidateInspection(
        problem=project._project_problem(spec, problem),
        candidate=project._project_candidate(spec, candidate, problem),
    )
