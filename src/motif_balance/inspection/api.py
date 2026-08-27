from __future__ import annotations

from pathlib import Path
from typing import Literal

from motif_balance.artifacts import BundleSnapshot, read_verified_portfolio_snapshot
from motif_balance.errors import ArtifactError
from motif_balance.execution import (
    _read_workspace_file,
    _verify_resource,
    verify_execution_workspace,
)
from motif_balance.model import ArtifactDigest
from motif_balance.receipt import parse_execution_receipt, parse_execution_workspace

from .model import ResultInspection
from .project import project_execution, project_result
from .verify import VerifiedResultSource


def _snapshot_artifacts(snapshot: BundleSnapshot) -> tuple[tuple[ArtifactDigest, bytes], ...]:
    return tuple(
        (record, snapshot.payload(record.path)) for record in snapshot.portfolio.manifest.artifacts
    )


def inspect_result(
    path: str | Path,
    *,
    kind: Literal["bundle", "execution"],
    expected_bundle_id: str | None = None,
    expected_workspace_id: str | None = None,
    expected_receipt_sha256: str | None = None,
    expected_release_sha256: str | None = None,
    expected_producer_revision: str | None = None,
) -> ResultInspection:
    """Return one immutable review projection after kind-appropriate verification."""

    root = Path(path)
    execution_anchors = (
        expected_workspace_id,
        expected_receipt_sha256,
        expected_release_sha256,
        expected_producer_revision,
    )
    if kind == "bundle":
        if any(value is not None for value in execution_anchors):
            raise ArtifactError("execution trust anchors cannot be used for a bundle inspection")
        portfolio, snapshot = read_verified_portfolio_snapshot(
            root,
            expected_bundle_id=expected_bundle_id,
        )
        return project_result(
            VerifiedResultSource(
                portfolio=portfolio,
                canonical_manifest=snapshot.payload("manifest.json"),
                artifacts=_snapshot_artifacts(snapshot),
                subject_kind=kind,
                integrity_state=(
                    "externally_verified" if expected_bundle_id else "self_consistent"
                ),
                trust_basis=("external_bundle_id" if expected_bundle_id else "self_consistent"),
                checked_identities=(("bundle_id",) if expected_bundle_id else ()),
            )
        )
    if kind != "execution":
        raise ArtifactError(f"unsupported inspection kind '{kind}'")
    if expected_bundle_id is not None:
        raise ArtifactError("bundle trust anchor cannot replace execution-workspace anchors")
    supplied = tuple(value is not None for value in execution_anchors)
    if any(supplied) and not all(supplied):
        raise ArtifactError("execution inspection requires all four external trust anchors or none")
    index_before = _read_workspace_file(root, "execution-workspace.json")
    workspace = parse_execution_workspace(index_before)
    anchors: tuple[str, str, str, str]
    trust_basis: Literal["self_consistent", "external_execution_identities"]
    checked: tuple[str, ...]
    integrity_status: Literal["verified", "readable_untrusted"]
    if all(supplied):
        assert expected_workspace_id is not None
        assert expected_receipt_sha256 is not None
        assert expected_release_sha256 is not None
        assert expected_producer_revision is not None
        anchors = (
            expected_workspace_id,
            expected_receipt_sha256,
            expected_release_sha256,
            expected_producer_revision,
        )
        trust_basis = "external_execution_identities"
        checked = ("workspace_id", "receipt_sha256", "release_sha256", "producer_revision")
        integrity_status = "verified"
    else:
        anchors = (
            workspace.workspace_id,
            workspace.receipt.sha256,
            workspace.release.sha256,
            workspace.release.producer_revision,
        )
        trust_basis = "self_consistent"
        checked = ()
        integrity_status = "readable_untrusted"
    verify_execution_workspace(
        root,
        expected_workspace_id=anchors[0],
        expected_receipt_sha256=anchors[1],
        expected_release_sha256=anchors[2],
        expected_producer_revision=anchors[3],
    )
    receipt_payload = _verify_resource(root, workspace.receipt)
    receipt = parse_execution_receipt(receipt_payload)
    portfolio, snapshot = read_verified_portfolio_snapshot(
        root / "bundle",
        expected_bundle_id=workspace.bundle.bundle_id,
    )
    verify_execution_workspace(
        root,
        expected_workspace_id=anchors[0],
        expected_receipt_sha256=anchors[1],
        expected_release_sha256=anchors[2],
        expected_producer_revision=anchors[3],
    )
    if _read_workspace_file(root, "execution-workspace.json") != index_before:
        raise ArtifactError("execution workspace changed during inspection")
    return project_result(
        VerifiedResultSource(
            portfolio=portfolio,
            canonical_manifest=snapshot.payload("manifest.json"),
            artifacts=_snapshot_artifacts(snapshot),
            subject_kind=kind,
            integrity_state=(
                "externally_verified" if integrity_status == "verified" else "readable_untrusted"
            ),
            trust_basis=trust_basis,
            checked_identities=checked,
            execution=project_execution(workspace, receipt),
        )
    )
