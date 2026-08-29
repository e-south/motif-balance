from __future__ import annotations

import math
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from motif_balance.model import (
    ExecutionDependency,
    FrozenModel,
    MotifConversion,
    ProposalSummary,
    SearchCheckpoint,
)

_CLAIM_SCOPE = (
    "Scores are meaningful only under the declared motif models and semantics.",
    "Budget exhaustion does not establish convergence or global optimality.",
    "One result is not comparative evidence or a biological replicate.",
    "The result does not establish binding, occupancy, expression, or regulatory function.",
)


class InspectionMotif(FrozenModel):
    motif_id: str
    width: Annotated[int, Field(gt=0)]
    model_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    probabilities: tuple[tuple[float, float, float, float], ...]
    background: tuple[float, float, float, float]
    source_name: str | None = None
    source_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    canonical_file_name: str | None = None
    canonical_file_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    conversion: MotifConversion | None = None

    @model_validator(mode="after")
    def validate_width(self) -> Self:
        if self.width != len(self.probabilities):
            raise ValueError("motif width must equal the probability-matrix length")
        return self


class InspectionProblem(FrozenModel):
    problem_id: str = Field(pattern=r"^problem-[0-9a-f]{24}$")
    motifs: tuple[InspectionMotif, ...]
    length: Annotated[int, Field(gt=0)]
    strands: Literal["forward", "both"]
    scoring_semantics: str
    objective_semantics: str
    tie_break_semantics: str

    @model_validator(mode="after")
    def validate_motif_order(self) -> Self:
        ids = tuple(motif.motif_id for motif in self.motifs)
        if not ids or ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
            raise ValueError("inspection motifs must be nonempty, unique, and canonical")
        return self


class InspectionRun(FrozenModel):
    run_id: str = Field(pattern=r"^run-[0-9a-f]{24}$")
    bundle_id: str = Field(pattern=r"^bundle-[0-9a-f]{24}$")
    package_version: str
    runtime_contract: str
    build_lock_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    seed: Annotated[int, Field(ge=0)]
    min_distance_requested: Annotated[float, Field(ge=0.0, le=1.0)] | None


class DeliveryInspection(FrozenModel):
    requested_count: Annotated[int, Field(gt=0)]
    delivered_count: Annotated[int, Field(ge=0)]
    status: Literal["complete", "incomplete"]

    @model_validator(mode="after")
    def validate_status(self) -> Self:
        expected = "complete" if self.delivered_count == self.requested_count else "incomplete"
        if self.delivered_count > self.requested_count or self.status != expected:
            raise ValueError("delivery status must reflect requested and delivered counts")
        return self


class SearchInspection(FrozenModel):
    completion: Literal["exhaustive", "budget_exhausted"]
    stop_reason: Literal["sequence_space_exhausted", "evaluation_budget_exhausted"]
    search_engine: str
    search_engine_version: str
    rng: str
    validation_status: Literal["not_applicable", "contract_tested"]
    evaluation_budget: Annotated[int, Field(gt=0)]
    evaluator_calls: Annotated[int, Field(gt=0)]
    unique_evaluations: Annotated[int, Field(gt=0)]
    checkpoints: tuple[SearchCheckpoint, ...]
    restarts: Annotated[int, Field(gt=0)]
    restart_final_scores: tuple[Annotated[float, Field(ge=0.0)], ...]
    proposals: tuple[ProposalSummary, ...]

    @model_validator(mode="after")
    def validate_completion(self) -> Self:
        expected = (
            "sequence_space_exhausted"
            if self.completion == "exhaustive"
            else "evaluation_budget_exhausted"
        )
        if self.stop_reason != expected:
            raise ValueError("search stop reason must match completion state")
        if self.unique_evaluations > self.evaluator_calls:
            raise ValueError("unique evaluations cannot exceed evaluator calls")
        if not self.checkpoints or self.checkpoints[-1].evaluations != self.evaluator_calls:
            raise ValueError("search checkpoints must end at evaluator_calls")
        if len(self.restart_final_scores) != self.restarts:
            raise ValueError("restart scores must contain one value per restart")
        return self


class IntegrityInspection(FrozenModel):
    state: Literal["self_consistent", "externally_verified", "readable_untrusted"]
    trust_basis: Literal[
        "self_consistent",
        "external_bundle_id",
        "external_execution_identities",
    ]
    checked_identities: tuple[str, ...]

    @model_validator(mode="after")
    def validate_state(self) -> Self:
        expected = {
            "self_consistent": ("self_consistent", ()),
            "external_bundle_id": ("externally_verified", ("bundle_id",)),
            "external_execution_identities": (
                "externally_verified",
                ("workspace_id", "receipt_sha256", "release_sha256", "producer_revision"),
            ),
        }
        expected_state, expected_checked = expected[self.trust_basis]
        if self.trust_basis == "self_consistent" and self.state == "readable_untrusted":
            if self.checked_identities:
                raise ValueError("untrusted inspection cannot report checked identities")
            return self
        if self.state != expected_state or self.checked_identities != expected_checked:
            raise ValueError("integrity fields are inconsistent")
        return self


class PositionSupport(FrozenModel):
    motif_position: Annotated[int, Field(ge=0)]
    candidate_position: Annotated[int, Field(ge=0)]
    observed_base: Literal["A", "C", "G", "T"]
    model_probability: Annotated[float, Field(gt=0.0, le=1.0, allow_inf_nan=False)]
    background_probability: Annotated[float, Field(gt=0.0, le=1.0, allow_inf_nan=False)]
    llr_contribution: float = Field(allow_inf_nan=False)


class InspectionMatch(FrozenModel):
    motif_id: str
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    strand: Literal["+", "-"]
    matched_sequence: str
    raw_score: float = Field(allow_inf_nan=False)
    normalized_score: Annotated[float, Field(ge=0.0, allow_inf_nan=False)]
    position_support: tuple[PositionSupport, ...]

    @model_validator(mode="after")
    def validate_support(self) -> Self:
        width = self.end - self.start
        if width <= 0 or width != len(self.matched_sequence):
            raise ValueError("match coordinates must equal matched-sequence width")
        if len(self.position_support) != width:
            raise ValueError("position support must contain one row per motif position")
        if tuple(item.motif_position for item in self.position_support) != tuple(range(width)):
            raise ValueError("position support motif positions must be consecutive")
        if "".join(item.observed_base for item in self.position_support) != self.matched_sequence:
            raise ValueError("position support bases must reproduce the oriented match")
        if not math.isclose(
            math.fsum(item.llr_contribution for item in self.position_support),
            self.raw_score,
            abs_tol=1.0e-12,
        ):
            raise ValueError("position contributions must sum to the raw match score")
        expected_positions = (
            tuple(range(self.start, self.end))
            if self.strand == "+"
            else tuple(range(self.end - 1, self.start - 1, -1))
        )
        if tuple(item.candidate_position for item in self.position_support) != expected_positions:
            raise ValueError("position support does not follow strand-aware candidate coordinates")
        return self


class InspectionCandidate(FrozenModel):
    candidate_id: str = Field(pattern=r"^candidate-[0-9a-f]{16}$")
    rank: Annotated[int, Field(gt=0)]
    sequence: str
    complement_sequence: str
    balance_score: Annotated[float, Field(ge=0.0, allow_inf_nan=False)]
    limiting_motif_ids: tuple[str, ...]
    shared_coordinates: tuple[Annotated[int, Field(ge=0)], ...]
    nearest_neighbor_distance: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    matches: tuple[InspectionMatch, ...]

    @model_validator(mode="after")
    def validate_candidate(self) -> Self:
        if not self.sequence or len(self.complement_sequence) != len(self.sequence):
            raise ValueError("candidate duplex sequences must have equal nonzero length")
        complement = self.sequence.translate(str.maketrans("ACGT", "TGCA"))
        if self.complement_sequence != complement:
            raise ValueError("complement sequence must be coordinate-aligned to the primary strand")
        if not self.matches:
            raise ValueError("inspection candidate requires motif matches")
        weakest = min(match.normalized_score for match in self.matches)
        if not math.isclose(self.balance_score, weakest, abs_tol=1.0e-12):
            raise ValueError("balance_score must equal the weakest normalized score")
        limiting = tuple(
            sorted(
                match.motif_id
                for match in self.matches
                if math.isclose(match.normalized_score, weakest, abs_tol=1.0e-12)
            )
        )
        if self.limiting_motif_ids != limiting:
            raise ValueError("limiting motif identities do not match the hard minimum")
        coverage = [0] * len(self.sequence)
        for match in self.matches:
            if match.end > len(self.sequence):
                raise ValueError("match coordinates exceed the candidate sequence")
            for position in range(match.start, match.end):
                coverage[position] += 1
        expected_shared = tuple(index for index, count in enumerate(coverage) if count > 1)
        if self.shared_coordinates != expected_shared:
            raise ValueError("shared coordinates must be the union of multiply covered positions")
        return self


class BestObservedInspection(FrozenModel):
    candidate_id: str = Field(pattern=r"^candidate-[0-9a-f]{16}$")
    sequence: str
    complement_sequence: str
    balance_score: Annotated[float, Field(ge=0.0, allow_inf_nan=False)]
    limiting_motif_ids: tuple[str, ...]
    shared_coordinates: tuple[Annotated[int, Field(ge=0)], ...]
    selected_rank: Annotated[int, Field(gt=0)] | None = None
    matches: tuple[InspectionMatch, ...]

    @model_validator(mode="after")
    def validate_best_observed(self) -> Self:
        candidate = InspectionCandidate(
            candidate_id=self.candidate_id,
            rank=self.selected_rank or 1,
            sequence=self.sequence,
            complement_sequence=self.complement_sequence,
            balance_score=self.balance_score,
            limiting_motif_ids=self.limiting_motif_ids,
            shared_coordinates=self.shared_coordinates,
            matches=self.matches,
        )
        if candidate.nearest_neighbor_distance is not None:  # pragma: no cover - construction
            raise ValueError("best observed projection cannot carry portfolio distance")
        return self


class LimitingMotifCount(FrozenModel):
    motif_id: str
    candidates: Annotated[int, Field(gt=0)]


class DistanceInspection(FrozenModel):
    status: Literal["exact", "not_applicable", "not_computed_limit"]
    actual_min_distance: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    closest_candidate_ids: tuple[str, str] | None = None
    base_comparisons: Annotated[int, Field(ge=0)]
    computation_limit: Literal[10_000_000] = 10_000_000

    @model_validator(mode="after")
    def validate_state(self) -> Self:
        has_result = self.actual_min_distance is not None or self.closest_candidate_ids is not None
        if self.status == "exact" and (
            self.actual_min_distance is None or self.closest_candidate_ids is None
        ):
            raise ValueError("exact distance inspection requires a value and candidate pair")
        if self.status != "exact" and has_result:
            raise ValueError("non-exact distance inspection cannot report an exact result")
        if self.status == "not_computed_limit" and self.base_comparisons <= self.computation_limit:
            raise ValueError("distance limit state requires work above the declared limit")
        return self


class InspectionPortfolio(FrozenModel):
    best_observed_score: Annotated[float, Field(ge=0.0, allow_inf_nan=False)]
    best_observed: BestObservedInspection | None = None
    score_min: Annotated[float, Field(ge=0.0, allow_inf_nan=False)]
    score_max: Annotated[float, Field(ge=0.0, allow_inf_nan=False)]
    distance: DistanceInspection
    limiting_motifs: tuple[LimitingMotifCount, ...]
    candidates: tuple[InspectionCandidate, ...]

    @model_validator(mode="after")
    def validate_summary(self) -> Self:
        if not self.candidates:
            raise ValueError("inspection portfolio requires candidates")
        scores = [candidate.balance_score for candidate in self.candidates]
        if not math.isclose(self.score_min, min(scores), abs_tol=1.0e-12):
            raise ValueError("score_min does not match the candidate portfolio")
        if not math.isclose(self.score_max, max(scores), abs_tol=1.0e-12):
            raise ValueError("score_max does not match the candidate portfolio")
        if self.score_max > self.best_observed_score + 1.0e-12:
            raise ValueError("selected portfolio score cannot exceed the best observed score")
        if self.best_observed is not None:
            if not math.isclose(
                self.best_observed.balance_score,
                self.best_observed_score,
                abs_tol=1.0e-12,
            ):
                raise ValueError("best observed projection does not match its score")
            if self.best_observed.selected_rank is not None:
                selected = next(
                    (
                        candidate
                        for candidate in self.candidates
                        if candidate.rank == self.best_observed.selected_rank
                    ),
                    None,
                )
                if selected is None or (
                    selected.candidate_id != self.best_observed.candidate_id
                    or selected.sequence != self.best_observed.sequence
                    or selected.balance_score != self.best_observed.balance_score
                    or selected.matches != self.best_observed.matches
                ):
                    raise ValueError(
                        "best observed selected rank does not identify the same candidate"
                    )
        return self


class InspectionArtifact(FrozenModel):
    key: str
    role: Literal["canonical", "derived"]
    path: str
    format: str
    bytes: Annotated[int, Field(ge=0)]
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ExecutionInspection(FrozenModel):
    workspace_id: str = Field(pattern=r"^execution-[0-9a-f]{24}$")
    producer_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    release_artifact_name: str
    release_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    runtime_package_tree_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    started_at_utc: str
    finished_at_utc: str
    duration_seconds: Annotated[float, Field(ge=0.0)]
    python_version: str
    platform_system: str
    platform_machine: str
    dependencies: tuple[ExecutionDependency, ...]


class ResultInspection(FrozenModel):
    schema_version: Literal["motif-balance.result-inspection/v3"] = (
        "motif-balance.result-inspection/v3"
    )
    subject_kind: Literal["bundle", "execution"]
    integrity: IntegrityInspection
    problem: InspectionProblem
    run: InspectionRun
    delivery: DeliveryInspection
    search: SearchInspection
    portfolio: InspectionPortfolio
    artifacts: tuple[InspectionArtifact, ...]
    execution: ExecutionInspection | None = None
    claim_scope: tuple[str, ...] = _CLAIM_SCOPE

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        if (self.subject_kind == "execution") != (self.execution is not None):
            raise ValueError("execution inspection kind and provenance must agree")
        if self.subject_kind == "bundle" and self.integrity.state == "readable_untrusted":
            raise ValueError("verified bundle inspection cannot be readable_untrusted")
        if self.delivery.delivered_count != len(self.portfolio.candidates):
            raise ValueError("delivered count must equal the projected candidate count")
        paths = tuple(artifact.path for artifact in self.artifacts)
        if paths != tuple(sorted(paths)) or len(paths) != len(set(paths)):
            raise ValueError("inspection artifacts must be unique and sorted by path")
        return self
