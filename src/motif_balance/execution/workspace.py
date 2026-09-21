"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/execution/workspace.py

Coordinate attested execution without weakening atomic publication checks.

Module Author(s): Eric J. South
Dunlop Lab
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from motif_balance.api import design
from motif_balance.artifacts import manifest_bytes, read_verified_portfolio
from motif_balance.artifacts.publication import _publish_directory_no_replace
from motif_balance.errors import ArtifactError
from motif_balance.formats.design import load_design_spec
from motif_balance.model import (
    DesignSpec,
    ExecutionBundleResource,
    ExecutionReleaseResource,
    ExecutionResource,
    ExecutionWorkspace,
)
from motif_balance.receipt import (
    build_execution_receipt,
    parse_execution_receipt,
    parse_execution_workspace,
    receipt_bytes,
    validate_receipt_against_portfolio,
    workspace_bytes,
    workspace_id,
)

from .release import (
    _attest_release_runtime,
    _package_tree_digest,
    _read_release,
    _release_package_tree,
)
from .workspace_io import _read_workspace_file, _verify_resource


def _resolved_spec_bytes(spec: DesignSpec) -> bytes:
    payload = spec.model_dump(mode="json")
    return (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode()


def _resource(path: str, payload: bytes) -> ExecutionResource:
    return ExecutionResource(
        path=path,
        sha256=hashlib.sha256(payload).hexdigest(),
        bytes=len(payload),
    )


def _validate_execution_identity(release_path: Path, producer_revision: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", producer_revision):
        raise ArtifactError("producer revision must be a lowercase 40-character Git commit")
    if release_path.name in {"design-spec.json", "SHA256SUMS"}:
        raise ArtifactError("release artifact name collides with a reserved execution input")
    if release_path.suffix != ".whl":
        raise ArtifactError("release artifact must be a wheel file")


def execute_design_workspace(
    specification: str | Path,
    output: str | Path,
    *,
    producer_revision: str,
    release_artifact: str | Path,
) -> ExecutionWorkspace:
    """Execute and atomically publish input, release, bundle, and runtime receipt."""

    destination = Path(output).absolute()
    release_path = Path(release_artifact)
    _validate_execution_identity(release_path, producer_revision)
    if destination.exists() or destination.is_symlink():
        raise ArtifactError(
            f"execution workspace already exists or is unsafe: '{destination.name}'"
        )
    release_payload = _read_release(release_path)
    runtime_package_tree_sha256 = _attest_release_runtime(release_payload)
    started_at = datetime.now(UTC)
    spec = load_design_spec(specification)
    normalized_spec = _resolved_spec_bytes(spec)
    portfolio = design(spec)
    if _attest_release_runtime(release_payload) != runtime_package_tree_sha256:
        raise ArtifactError("runtime package tree changed during execution")
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(
            tempfile.mkdtemp(prefix=f".{destination.name}.tmp-", dir=destination.parent)
        )
    except OSError as exc:
        raise ArtifactError("unable to create the execution publication directory") from exc
    try:
        inputs = temporary / "inputs"
        inputs.mkdir()
        input_path = inputs / "design-spec.json"
        input_path.write_bytes(normalized_spec)
        copied_release = inputs / release_path.name
        copied_release.write_bytes(release_payload)
        portfolio.write(temporary / "bundle")
        finished_at = datetime.now(UTC)
        manifest_payload = manifest_bytes(portfolio.manifest)
        release_sha256 = hashlib.sha256(release_payload).hexdigest()
        input_sha256 = hashlib.sha256(normalized_spec).hexdigest()
        receipt = build_execution_receipt(
            portfolio,
            manifest_payload=manifest_payload,
            producer_revision=producer_revision,
            release_artifact_name=release_path.name,
            release_artifact_sha256=release_sha256,
            runtime_package_tree_sha256=runtime_package_tree_sha256,
            normalized_design_sha256=input_sha256,
            started_at=started_at,
            finished_at=finished_at,
        )
        receipt_payload = receipt_bytes(receipt)
        (temporary / "execution-receipt.json").write_bytes(receipt_payload)
        checksums_payload = (
            f"{input_sha256}  inputs/design-spec.json\n"
            f"{release_sha256}  inputs/{release_path.name}\n"
        ).encode()
        (inputs / "SHA256SUMS").write_bytes(checksums_payload)
        provisional = ExecutionWorkspace(
            workspace_id="execution-000000000000000000000000",
            input=_resource("inputs/design-spec.json", normalized_spec),
            release=ExecutionReleaseResource(
                path=f"inputs/{release_path.name}",
                sha256=release_sha256,
                bytes=len(release_payload),
                producer_revision=producer_revision,
            ),
            checksums=_resource("inputs/SHA256SUMS", checksums_payload),
            bundle=ExecutionBundleResource(
                bundle_id=portfolio.manifest.bundle_id,
                manifest_sha256=hashlib.sha256(manifest_payload).hexdigest(),
            ),
            receipt=_resource("execution-receipt.json", receipt_payload),
        )
        workspace = provisional.model_copy(update={"workspace_id": workspace_id(provisional)})
        (temporary / "execution-workspace.json").write_bytes(workspace_bytes(workspace))
        verified = verify_execution_workspace(
            temporary,
            expected_workspace_id=workspace.workspace_id,
            expected_receipt_sha256=workspace.receipt.sha256,
            expected_release_sha256=release_sha256,
            expected_producer_revision=producer_revision,
        )
        if verified != workspace.workspace_id:
            raise ArtifactError("execution workspace round-trip changed its identity")
        _publish_directory_no_replace(temporary, destination)
        try:
            published_workspace_id = verify_execution_workspace(
                destination,
                expected_workspace_id=workspace.workspace_id,
                expected_receipt_sha256=workspace.receipt.sha256,
                expected_release_sha256=release_sha256,
                expected_producer_revision=producer_revision,
            )
            if published_workspace_id != workspace.workspace_id:
                raise ArtifactError("published execution workspace changed its identity")
        except Exception as exc:
            raise ArtifactError(
                "published execution workspace failed post-publication verification; "
                "destination left untouched for inspection"
            ) from exc
        return workspace
    except FileExistsError as exc:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise ArtifactError(
            f"execution workspace already exists or is unsafe: '{destination.name}'"
        ) from exc
    except OSError as exc:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise ArtifactError("unable to publish the execution workspace") from exc
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise


def verify_execution_workspace(
    directory: str | Path,
    *,
    expected_workspace_id: str,
    expected_receipt_sha256: str,
    expected_release_sha256: str,
    expected_producer_revision: str,
) -> str:
    """Verify one closed execution workspace against all external trust anchors."""

    root = Path(directory)
    if root.is_symlink() or not root.is_dir():
        raise ArtifactError("execution workspace directory is missing or unsafe")
    root_names = {entry.name for entry in root.iterdir()}
    if root_names != {"bundle", "inputs", "execution-receipt.json", "execution-workspace.json"}:
        raise ArtifactError("execution workspace root inventory mismatch")
    index_payload = _read_workspace_file(root, "execution-workspace.json")
    workspace = parse_execution_workspace(index_payload)
    if workspace.workspace_id != expected_workspace_id:
        raise ArtifactError("execution workspace does not match the externally expected identity")
    if workspace.receipt.sha256 != expected_receipt_sha256:
        raise ArtifactError("execution receipt does not match the externally expected digest")
    if workspace.release.sha256 != expected_release_sha256:
        raise ArtifactError("release artifact does not match the externally expected digest")
    if workspace.release.producer_revision != expected_producer_revision:
        raise ArtifactError("release artifact does not match the expected producer revision")
    if workspace.input.path != "inputs/design-spec.json":
        raise ArtifactError("execution workspace input path is not canonical")
    if workspace.checksums.path != "inputs/SHA256SUMS":
        raise ArtifactError("execution workspace checksum path is not canonical")
    if workspace.receipt.path != "execution-receipt.json":
        raise ArtifactError("execution workspace receipt path is not canonical")
    release_name = Path(workspace.release.path).name
    if workspace.release.path != f"inputs/{release_name}":
        raise ArtifactError("execution workspace release path is not canonical")
    inputs = root / "inputs"
    if inputs.is_symlink() or not inputs.is_dir():
        raise ArtifactError("execution workspace inputs directory is unsafe")
    if {entry.name for entry in inputs.iterdir()} != {
        "design-spec.json",
        "SHA256SUMS",
        release_name,
    }:
        raise ArtifactError("execution workspace input inventory mismatch")
    input_payload = _verify_resource(root, workspace.input)
    release_payload = _verify_resource(root, workspace.release)
    checksums_payload = _verify_resource(root, workspace.checksums)
    receipt_payload = _verify_resource(root, workspace.receipt)
    expected_checksums = (
        f"{hashlib.sha256(input_payload).hexdigest()}  inputs/design-spec.json\n"
        f"{hashlib.sha256(release_payload).hexdigest()}  inputs/{release_name}\n"
    ).encode()
    if checksums_payload != expected_checksums:
        raise ArtifactError("execution workspace checksum file is not canonical")
    manifest_before = _read_workspace_file(root, "bundle/manifest.json")
    portfolio = read_verified_portfolio(
        root / "bundle",
        expected_bundle_id=workspace.bundle.bundle_id,
    )
    manifest_after = _read_workspace_file(root, "bundle/manifest.json")
    if manifest_before != manifest_after:
        raise ArtifactError("bundle manifest changed during execution-workspace verification")
    if hashlib.sha256(manifest_before).hexdigest() != workspace.bundle.manifest_sha256:
        raise ArtifactError("execution workspace bundle manifest digest mismatch")
    if _resolved_spec_bytes(portfolio.spec) != input_payload:
        raise ArtifactError("execution workspace input does not match the verified bundle")
    receipt = parse_execution_receipt(receipt_payload)
    if _package_tree_digest(_release_package_tree(release_payload)) != (
        receipt.runtime_package_tree_sha256
    ):
        raise ArtifactError("execution receipt runtime package-tree digest mismatch")
    if receipt.normalized_design_sha256 != workspace.input.sha256:
        raise ArtifactError("execution receipt input digest mismatch")
    if receipt.release_artifact_name != release_name:
        raise ArtifactError("execution receipt release name mismatch")
    validate_receipt_against_portfolio(
        receipt,
        portfolio,
        manifest_payload=manifest_before,
        expected_release_sha256=expected_release_sha256,
        expected_producer_revision=expected_producer_revision,
    )
    return workspace.workspace_id
