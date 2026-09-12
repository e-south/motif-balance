"""Versioned result manifests and complete exact-count proofs."""

from __future__ import annotations

import math
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from .base import FrozenModel
from .evaluation import Evaluation
from .search import SearchDiagnostics


class ArtifactDigest(FrozenModel):
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    bytes: Annotated[int, Field(ge=0)]


class RunManifest(FrozenModel):
    schema_version: Literal[
        "run-manifest/v2",
        "run-manifest/v3",
        "run-manifest/v4",
        "run-manifest/v5",
        "run-manifest/v6",
    ] = "run-manifest/v5"
    package_version: str
    runtime_contract: str
    build_lock_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    problem_id: str = Field(pattern=r"^problem-[0-9a-f]{24}$")
    run_id: str = Field(pattern=r"^run-[0-9a-f]{24}$")
    bundle_id: str = Field(pattern=r"^bundle-[0-9a-f]{24}$")
    search_engine: str
    search_engine_version: str
    rng: str
    evaluation_count: Annotated[int, Field(gt=0)]
    unique_evaluations: Annotated[int, Field(gt=0)]
    completion_status: Literal["exhaustive", "budget_exhausted"]
    search_validation_status: Literal["not_applicable", "contract_tested"]
    search_diagnostics: SearchDiagnostics
    best_observed: Evaluation | None = None
    exact_completion_status: Literal["complete", "not_exact"] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    state_space_size: Annotated[int, Field(strict=True, gt=0)] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    expected_candidate_count: Annotated[int, Field(strict=True, gt=0)] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    completed_candidate_count: Annotated[int, Field(strict=True, gt=0)] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    score_operation_count: Annotated[int, Field(strict=True, gt=0)] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    elite_capacity: Annotated[int, Field(strict=True, gt=0)] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    elite_fill_count: Annotated[int, Field(strict=True, ge=0)] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    elites: tuple[Evaluation, ...] = Field(default=(), exclude_if=lambda value: not value)
    artifacts: tuple[ArtifactDigest, ...]

    @model_validator(mode="after")
    def validate_evaluation_counts(self) -> Self:
        if self.unique_evaluations > self.evaluation_count:
            raise ValueError("unique_evaluations cannot exceed evaluation_count")
        if self.search_diagnostics.checkpoints[-1].evaluations != self.evaluation_count:
            raise ValueError("final search checkpoint must equal evaluation_count")
        expected_diagnostics = (
            "search-diagnostics/v3"
            if self.schema_version == "run-manifest/v6"
            else "search-diagnostics/v2"
            if self.schema_version == "run-manifest/v5"
            else "search-diagnostics/v1"
        )
        if self.search_diagnostics.schema_version != expected_diagnostics:
            raise ValueError(f"{self.schema_version} requires {expected_diagnostics}")
        if self.completion_status == "exhaustive" and (
            self.unique_evaluations != self.evaluation_count
        ):
            raise ValueError("exhaustive manifests require one unique row per evaluation")
        if self.schema_version in {"run-manifest/v4", "run-manifest/v5", "run-manifest/v6"}:
            if self.best_observed is None:
                raise ValueError(
                    "run-manifest/v4 through v6 require the complete best observed evaluation"
                )
            if not math.isclose(
                self.best_observed.balance_score,
                self.search_diagnostics.best_score,
                abs_tol=1.0e-12,
            ):
                raise ValueError("best observed evaluation must match search diagnostics")
        elif self.best_observed is not None:
            raise ValueError("run-manifest/v2 and v3 cannot contain a best observed evaluation")
        if self.schema_version == "run-manifest/v6":
            if (
                self.exact_completion_status is None
                or self.score_operation_count is None
                or self.elite_capacity is None
                or self.elite_fill_count is None
            ):
                raise ValueError("run-manifest/v6 requires exact, operation, and elite metadata")
            if self.elite_fill_count != len(self.elites):
                raise ValueError("elite_fill_count must equal retained elite rows")
            if self.elite_fill_count > self.elite_capacity:
                raise ValueError("retained elites cannot exceed elite_capacity")
            elite_sequences = tuple(item.sequence for item in self.elites)
            if len(elite_sequences) != len(set(elite_sequences)):
                raise ValueError("retained elite sequences must be unique")
            if elite_sequences != tuple(
                item.sequence
                for item in sorted(
                    self.elites, key=lambda item: (-item.balance_score, item.sequence)
                )
            ):
                raise ValueError("retained elites must be sorted by score then sequence")
            exact_counts = (
                self.state_space_size,
                self.expected_candidate_count,
                self.completed_candidate_count,
            )
            if self.exact_completion_status == "complete":
                if any(value is None for value in exact_counts):
                    raise ValueError("exact completion requires complete candidate-count proof")
                if not (
                    self.state_space_size
                    == self.expected_candidate_count
                    == self.completed_candidate_count
                    == self.evaluation_count
                    == self.unique_evaluations
                ):
                    raise ValueError("exact candidate-count proof does not match evaluation counts")
            elif any(value is not None for value in exact_counts):
                raise ValueError("bounded runs cannot claim exact candidate-count proof")
        elif (
            any(
                value is not None
                for value in (
                    self.exact_completion_status,
                    self.state_space_size,
                    self.expected_candidate_count,
                    self.completed_candidate_count,
                    self.score_operation_count,
                    self.elite_capacity,
                    self.elite_fill_count,
                )
            )
            or self.elites
        ):
            raise ValueError("prospective run metadata requires run-manifest/v6")
        return self
