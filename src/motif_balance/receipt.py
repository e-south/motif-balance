from __future__ import annotations

import hashlib
import json
import platform
from datetime import UTC, datetime
from importlib.metadata import version

from pydantic import ValidationError

from motif_balance.constants import MAX_INPUT_BYTES
from motif_balance.errors import ArtifactError
from motif_balance.model import (
    ExecutionDependency,
    ExecutionReceipt,
    ExecutionWorkspace,
    PortfolioRecord,
)


def _utc(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("execution timestamps must be timezone-aware")
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode()


def build_execution_receipt(
    portfolio: PortfolioRecord,
    *,
    manifest_payload: bytes,
    producer_revision: str,
    release_artifact_name: str,
    release_artifact_sha256: str,
    runtime_package_tree_sha256: str,
    normalized_design_sha256: str,
    started_at: datetime,
    finished_at: datetime,
) -> ExecutionReceipt:
    """Capture provenance in the same process that executed one design."""

    dependencies = tuple(
        ExecutionDependency(name=name, version=version(name))
        for name in ("numpy", "pydantic", "pyyaml", "typer")
    )
    return ExecutionReceipt(
        producer_revision=producer_revision,
        started_at_utc=_utc(started_at),
        finished_at_utc=_utc(finished_at),
        normalized_design_sha256=normalized_design_sha256,
        release_artifact_name=release_artifact_name,
        release_artifact_sha256=release_artifact_sha256,
        runtime_package_tree_sha256=runtime_package_tree_sha256,
        package_version=portfolio.manifest.package_version,
        build_lock_sha256=portfolio.manifest.build_lock_sha256,
        bundle_id=portfolio.manifest.bundle_id,
        problem_id=portfolio.problem_id,
        run_id=portfolio.run_id,
        manifest_sha256=hashlib.sha256(manifest_payload).hexdigest(),
        search_engine=portfolio.manifest.search_engine,
        search_engine_version=portfolio.manifest.search_engine_version,
        evaluation_count=portfolio.manifest.evaluation_count,
        unique_evaluations=portfolio.manifest.unique_evaluations,
        python_version=platform.python_version(),
        platform_system=platform.system(),
        platform_machine=platform.machine(),
        dependencies=dependencies,
    )


def receipt_bytes(receipt: ExecutionReceipt) -> bytes:
    return _json_bytes(receipt.model_dump(mode="json"))


def workspace_id(workspace: ExecutionWorkspace) -> str:
    payload = workspace.model_dump(mode="json", exclude={"workspace_id"})
    return f"execution-{hashlib.sha256(_json_bytes(payload)).hexdigest()[:24]}"


def workspace_bytes(workspace: ExecutionWorkspace) -> bytes:
    return _json_bytes(workspace.model_dump(mode="json"))


def _parse_model(
    payload: bytes,
    *,
    label: str,
    model: type[ExecutionReceipt] | type[ExecutionWorkspace],
) -> ExecutionReceipt | ExecutionWorkspace:
    if len(payload) > MAX_INPUT_BYTES:
        raise ArtifactError(f"{label} exceeds the {MAX_INPUT_BYTES}-byte limit")
    try:
        raw = json.loads(payload)
        parsed = model.model_validate(raw)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ArtifactError(f"invalid {label}: {exc}") from exc
    expected = (
        receipt_bytes(parsed) if isinstance(parsed, ExecutionReceipt) else workspace_bytes(parsed)
    )
    if payload != expected:
        raise ArtifactError(f"{label} does not use canonical JSON encoding")
    return parsed


def parse_execution_receipt(payload: bytes) -> ExecutionReceipt:
    parsed = _parse_model(payload, label="execution receipt", model=ExecutionReceipt)
    if not isinstance(parsed, ExecutionReceipt):  # pragma: no cover - type narrowing
        raise ArtifactError("execution receipt parser returned the wrong model")
    return parsed


def parse_execution_workspace(payload: bytes) -> ExecutionWorkspace:
    parsed = _parse_model(payload, label="execution workspace", model=ExecutionWorkspace)
    if not isinstance(parsed, ExecutionWorkspace):  # pragma: no cover - type narrowing
        raise ArtifactError("execution workspace parser returned the wrong model")
    if workspace_id(parsed) != parsed.workspace_id:
        raise ArtifactError("execution workspace identity mismatch")
    return parsed


def validate_receipt_against_portfolio(
    receipt: ExecutionReceipt,
    portfolio: PortfolioRecord,
    *,
    manifest_payload: bytes,
    expected_release_sha256: str,
    expected_producer_revision: str,
) -> None:
    expected = (
        portfolio.manifest.package_version,
        portfolio.manifest.build_lock_sha256,
        portfolio.manifest.bundle_id,
        portfolio.problem_id,
        portfolio.run_id,
        hashlib.sha256(manifest_payload).hexdigest(),
        portfolio.manifest.search_engine,
        portfolio.manifest.search_engine_version,
        portfolio.manifest.evaluation_count,
        portfolio.manifest.unique_evaluations,
        expected_release_sha256,
        expected_producer_revision,
    )
    actual = (
        receipt.package_version,
        receipt.build_lock_sha256,
        receipt.bundle_id,
        receipt.problem_id,
        receipt.run_id,
        receipt.manifest_sha256,
        receipt.search_engine,
        receipt.search_engine_version,
        receipt.evaluation_count,
        receipt.unique_evaluations,
        receipt.release_artifact_sha256,
        receipt.producer_revision,
    )
    if actual != expected:
        raise ArtifactError("execution receipt does not match trusted bundle or release identity")
