"""Release-bound execution receipts and workspace resources."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal, Self

from pydantic import Field, field_validator, model_validator

from .base import FrozenModel


class ExecutionDependency(FrozenModel):
    name: str = Field(min_length=1, pattern=r"^[a-z0-9_.-]+$")
    version: str = Field(min_length=1)


class ExecutionReceipt(FrozenModel):
    schema_version: Literal["motif-balance.execution-receipt/v1"] = (
        "motif-balance.execution-receipt/v1"
    )
    producer_repository: Literal["motif-balance"] = "motif-balance"
    producer_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    operation: Literal["design"] = "design"
    execution_status: Literal["completed"] = "completed"
    started_at_utc: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
    finished_at_utc: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
    normalized_design_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    release_artifact_name: str
    release_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    runtime_package_tree_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    package_version: str
    build_lock_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    bundle_id: str = Field(pattern=r"^bundle-[0-9a-f]{24}$")
    problem_id: str = Field(pattern=r"^problem-[0-9a-f]{24}$")
    run_id: str = Field(pattern=r"^run-[0-9a-f]{24}$")
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    search_engine: str
    search_engine_version: str
    evaluation_count: Annotated[int, Field(gt=0)]
    unique_evaluations: Annotated[int, Field(gt=0)]
    python_version: str
    platform_system: str
    platform_machine: str
    dependencies: tuple[ExecutionDependency, ...]

    @field_validator("release_artifact_name")
    @classmethod
    def validate_release_artifact_name(cls, value: str) -> str:
        if not value or value in {".", ".."} or "/" in value or "\\" in value:
            raise ValueError("release_artifact_name must be a basename")
        return value

    @model_validator(mode="after")
    def validate_execution_receipt(self) -> Self:
        started = datetime.strptime(self.started_at_utc, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        finished = datetime.strptime(self.finished_at_utc, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        if finished < started:
            raise ValueError("execution finish cannot precede execution start")
        names = [item.name for item in self.dependencies]
        if names != sorted(names) or len(names) != len(set(names)):
            raise ValueError("execution dependencies must be unique and sorted by name")
        if self.unique_evaluations > self.evaluation_count:
            raise ValueError("unique_evaluations cannot exceed evaluation_count")
        return self


class ExecutionResource(FrozenModel):
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    bytes: Annotated[int, Field(ge=0)]

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        parts = value.split("/")
        if not value or value.startswith("/") or any(part in {"", ".", ".."} for part in parts):
            raise ValueError("execution resource path must be a normalized relative path")
        return value


class ExecutionReleaseResource(ExecutionResource):
    producer_revision: str = Field(pattern=r"^[0-9a-f]{40}$")


class ExecutionBundleResource(FrozenModel):
    path: Literal["bundle"] = "bundle"
    bundle_id: str = Field(pattern=r"^bundle-[0-9a-f]{24}$")
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ExecutionWorkspace(FrozenModel):
    schema_version: Literal["motif-balance.execution-workspace/v1"] = (
        "motif-balance.execution-workspace/v1"
    )
    workspace_id: str = Field(pattern=r"^execution-[0-9a-f]{24}$")
    input: ExecutionResource
    release: ExecutionReleaseResource
    checksums: ExecutionResource
    bundle: ExecutionBundleResource
    receipt: ExecutionResource
