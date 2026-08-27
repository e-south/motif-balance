from __future__ import annotations

import base64
import hashlib
import json
import zipfile
from pathlib import Path

import pytest
from pydantic import ValidationError

import motif_balance
import motif_balance.api as api_module
from motif_balance import DesignSpec
from motif_balance.api import (
    build_result_catalog,
    execute_design_workspace,
    inspect_result,
    render_inspection_html,
    verify_execution_workspace,
)
from motif_balance.errors import ArtifactError
from motif_balance.inspection import ResultInspection
from motif_balance.model import ExecutionWorkspace
from motif_balance.receipt import workspace_bytes, workspace_id


def _write_runtime_wheel(path: Path, *, alter_api: bool = False) -> None:
    package_root = Path(motif_balance.__file__).parent
    entries: dict[str, bytes] = {}
    for source in sorted(package_root.rglob("*")):
        if source.is_dir() or "__pycache__" in source.parts or source.suffix == ".pyc":
            continue
        payload = source.read_bytes()
        relative = source.relative_to(package_root).as_posix()
        if alter_api and relative == "api.py":
            payload += b"# substituted\n"
        entries[f"motif_balance/{relative}"] = payload
    dist_info = "motif_balance-0.3.0a1.dist-info/"
    entries[f"{dist_info}METADATA"] = (
        b"Metadata-Version: 2.4\nName: motif-balance\nVersion: 0.3.0a1\n"
    )
    entries[f"{dist_info}WHEEL"] = b"Wheel-Version: 1.0\n"
    entries[f"{dist_info}entry_points.txt"] = (
        b"[console_scripts]\nmotif-balance = motif_balance.cli:app\n"
    )
    record = "".join(
        f"{name},sha256={base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).rstrip(b'=').decode()},{len(payload)}\n"
        for name, payload in sorted(entries.items())
    )
    record += f"{dist_info}RECORD,,\n"
    with zipfile.ZipFile(path, "w") as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload)
        archive.writestr(f"{dist_info}RECORD", record)


@pytest.fixture
def design_path(tmp_path: Path, pairwise_spec: DesignSpec) -> Path:
    payload = pairwise_spec.model_dump(mode="json", exclude={"motifs"})
    payload["motifs"] = {
        motif.motif_id: motif.model_dump(mode="json") for motif in pairwise_spec.motifs
    }
    path = tmp_path / "design.json"
    path.write_text(json.dumps(payload))
    return path


def _execute(tmp_path: Path, specification: Path) -> tuple[Path, Path, dict[str, object]]:
    release = tmp_path / "motif_balance-0.3.0a1-py3-none-any.whl"
    output = tmp_path / "execution"
    _write_runtime_wheel(release)
    workspace = execute_design_workspace(
        specification,
        output,
        producer_revision="a" * 40,
        release_artifact=release,
    )
    return output, release, workspace.model_dump(mode="json")


def _rewrite_index(output: Path, index: dict[str, object]) -> str:
    index["workspace_id"] = "execution-000000000000000000000000"
    provisional = ExecutionWorkspace.model_validate(index)
    revised = provisional.model_copy(update={"workspace_id": workspace_id(provisional)})
    (output / "execution-workspace.json").write_bytes(workspace_bytes(revised))
    return revised.workspace_id


def _replace_resource(index: dict[str, object], name: str, payload: bytes) -> None:
    resource = index[name]
    assert isinstance(resource, dict)
    resource["sha256"] = hashlib.sha256(payload).hexdigest()
    resource["bytes"] = len(payload)


def _verification_arguments(
    output: Path,
    release: Path,
    index: dict[str, object],
) -> dict[str, str | Path]:
    receipt = index["receipt"]
    assert isinstance(receipt, dict)
    return {
        "directory": output,
        "expected_workspace_id": str(index["workspace_id"]),
        "expected_receipt_sha256": str(receipt["sha256"]),
        "expected_release_sha256": hashlib.sha256(release.read_bytes()).hexdigest(),
        "expected_producer_revision": "a" * 40,
    }


def test_execute_refuses_a_substituted_release_tree(
    tmp_path: Path,
    design_path: Path,
) -> None:
    release = tmp_path / "motif_balance-0.3.0a1-py3-none-any.whl"
    _write_runtime_wheel(release, alter_api=True)

    with pytest.raises(ArtifactError, match="does not match the running package"):
        execute_design_workspace(
            design_path,
            tmp_path / "execution",
            producer_revision="a" * 40,
            release_artifact=release,
        )

    assert not (tmp_path / "execution").exists()


def test_execute_refuses_invalid_release_identity_before_search(
    tmp_path: Path,
    design_path: Path,
) -> None:
    release = tmp_path / "release.tar.gz"
    release.write_bytes(b"not a wheel")

    with pytest.raises(ArtifactError, match="wheel file"):
        execute_design_workspace(
            design_path,
            tmp_path / "execution",
            producer_revision="a" * 40,
            release_artifact=release,
        )


def test_execution_verification_requires_external_trusted_values(
    tmp_path: Path,
    design_path: Path,
) -> None:
    output, release, workspace = _execute(tmp_path, design_path)
    receipt = workspace["receipt"]
    assert isinstance(receipt, dict)

    with pytest.raises(ArtifactError, match="externally expected digest"):
        verify_execution_workspace(
            output,
            expected_workspace_id=str(workspace["workspace_id"]),
            expected_receipt_sha256="0" * 64,
            expected_release_sha256=hashlib.sha256(release.read_bytes()).hexdigest(),
            expected_producer_revision="a" * 40,
        )

    arguments = _verification_arguments(output, release, workspace)
    with pytest.raises(ArtifactError, match="externally expected identity"):
        verify_execution_workspace(
            **{**arguments, "expected_workspace_id": "execution-" + "0" * 24}
        )
    with pytest.raises(ArtifactError, match="release artifact does not match"):
        verify_execution_workspace(**{**arguments, "expected_release_sha256": "0" * 64})
    with pytest.raises(ArtifactError, match="expected producer revision"):
        verify_execution_workspace(**{**arguments, "expected_producer_revision": "0" * 40})


def test_execution_inspection_distinguishes_internal_and_external_trust(
    tmp_path: Path,
    design_path: Path,
) -> None:
    output, release, workspace = _execute(tmp_path, design_path)
    arguments = _verification_arguments(output, release, workspace)

    internal = inspect_result(output, kind="execution")
    external = inspect_result(
        output,
        kind="execution",
        expected_workspace_id=str(arguments["expected_workspace_id"]),
        expected_receipt_sha256=str(arguments["expected_receipt_sha256"]),
        expected_release_sha256=str(arguments["expected_release_sha256"]),
        expected_producer_revision=str(arguments["expected_producer_revision"]),
    )

    assert internal.integrity.state == "readable_untrusted"
    assert internal.integrity.trust_basis == "self_consistent"
    assert external.integrity.state == "externally_verified"
    assert external.integrity.trust_basis == "external_execution_identities"
    assert external.execution is not None
    assert external.execution.workspace_id == workspace["workspace_id"]
    html = render_inspection_html(external).decode()
    assert "Execution provenance" in html
    assert "Runtime package tree SHA-256" in html
    catalog = build_result_catalog({"execution": external})
    assert catalog.entries[0].workspace_id == workspace["workspace_id"]

    external_payload = external.model_dump(mode="python")
    with pytest.raises(ValidationError, match="kind and provenance must agree"):
        ResultInspection.model_validate(
            {
                **external_payload,
                "subject_kind": "bundle",
            }
        )
    with pytest.raises(ValidationError, match="integrity fields are inconsistent"):
        ResultInspection.model_validate(
            {
                **external_payload,
                "integrity": {
                    **external_payload["integrity"],
                    "state": "readable_untrusted",
                },
            }
        )


def test_execution_inspection_binds_projected_receipt_bytes(
    tmp_path: Path,
    design_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output, release, workspace = _execute(tmp_path, design_path)
    arguments = _verification_arguments(output, release, workspace)
    genuine = (output / "execution-receipt.json").read_bytes()
    forged_record = json.loads(genuine)
    forged_record["platform_machine"] = "FORGED-INTERMEDIATE"
    forged = (json.dumps(forged_record, indent=2, sort_keys=True) + "\n").encode()
    original_read = api_module._read_workspace_file
    receipt_reads = 0

    def substitute_intermediate_receipt(root: Path, relative: str) -> bytes:
        nonlocal receipt_reads
        payload = original_read(root, relative)
        if relative == "execution-receipt.json":
            receipt_reads += 1
            if receipt_reads == 2:
                return forged
        return payload

    monkeypatch.setattr(api_module, "_read_workspace_file", substitute_intermediate_receipt)

    with pytest.raises(ArtifactError, match="resource digest mismatch"):
        inspect_result(
            output,
            kind="execution",
            expected_workspace_id=str(arguments["expected_workspace_id"]),
            expected_receipt_sha256=str(arguments["expected_receipt_sha256"]),
            expected_release_sha256=str(arguments["expected_release_sha256"]),
            expected_producer_revision=str(arguments["expected_producer_revision"]),
        )


def test_execution_inspection_rejects_partial_or_wrong_kind_anchors(
    tmp_path: Path,
    design_path: Path,
) -> None:
    output, _, _ = _execute(tmp_path, design_path)

    with pytest.raises(ArtifactError, match="all four external trust anchors"):
        inspect_result(
            output,
            kind="execution",
            expected_workspace_id="execution-" + "0" * 24,
        )
    with pytest.raises(ArtifactError, match="cannot replace execution-workspace anchors"):
        inspect_result(
            output,
            kind="execution",
            expected_bundle_id="bundle-" + "0" * 24,
        )


def test_execution_verification_detects_tampering(
    tmp_path: Path,
    design_path: Path,
) -> None:
    output, release, workspace = _execute(tmp_path, design_path)
    receipt_resource = workspace["receipt"]
    assert isinstance(receipt_resource, dict)
    receipt_path = output / "execution-receipt.json"
    receipt = json.loads(receipt_path.read_text())
    receipt["platform_machine"] = "substituted"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")

    with pytest.raises(ArtifactError, match="resource digest mismatch"):
        verify_execution_workspace(
            output,
            expected_workspace_id=str(workspace["workspace_id"]),
            expected_receipt_sha256=str(receipt_resource["sha256"]),
            expected_release_sha256=hashlib.sha256(release.read_bytes()).hexdigest(),
            expected_producer_revision="a" * 40,
        )


def test_execute_refuses_existing_destination(
    tmp_path: Path,
    design_path: Path,
) -> None:
    release = tmp_path / "motif_balance-0.3.0a1-py3-none-any.whl"
    output = tmp_path / "execution"
    _write_runtime_wheel(release)
    output.mkdir()

    with pytest.raises(ArtifactError, match="already exists"):
        execute_design_workspace(
            design_path,
            output,
            producer_revision="a" * 40,
            release_artifact=release,
        )


def test_execution_verification_rejects_inventory_drift(
    tmp_path: Path,
    design_path: Path,
) -> None:
    output, release, index = _execute(tmp_path, design_path)
    (output / "unexpected.txt").write_text("unexpected")

    with pytest.raises(ArtifactError, match="root inventory mismatch"):
        verify_execution_workspace(**_verification_arguments(output, release, index))


def test_execution_verification_rejects_input_inventory_drift(
    tmp_path: Path,
    design_path: Path,
) -> None:
    output, release, index = _execute(tmp_path, design_path)
    (output / "inputs" / "unexpected.txt").write_text("unexpected")

    with pytest.raises(ArtifactError, match="input inventory mismatch"):
        verify_execution_workspace(**_verification_arguments(output, release, index))


def test_execution_verification_rejects_noncanonical_checksums(
    tmp_path: Path,
    design_path: Path,
) -> None:
    output, release, index = _execute(tmp_path, design_path)
    payload = b"not canonical\n"
    (output / "inputs" / "SHA256SUMS").write_bytes(payload)
    _replace_resource(index, "checksums", payload)
    index["workspace_id"] = _rewrite_index(output, index)

    with pytest.raises(ArtifactError, match="checksum file is not canonical"):
        verify_execution_workspace(**_verification_arguments(output, release, index))


def test_execution_verification_binds_the_bundle_manifest_digest(
    tmp_path: Path,
    design_path: Path,
) -> None:
    output, release, index = _execute(tmp_path, design_path)
    bundle = index["bundle"]
    assert isinstance(bundle, dict)
    bundle["manifest_sha256"] = "0" * 64
    index["workspace_id"] = _rewrite_index(output, index)

    with pytest.raises(ArtifactError, match="bundle manifest digest mismatch"):
        verify_execution_workspace(**_verification_arguments(output, release, index))


def test_execution_verification_binds_the_resolved_input_to_the_bundle(
    tmp_path: Path,
    design_path: Path,
) -> None:
    output, release, index = _execute(tmp_path, design_path)
    input_path = output / "inputs" / "design-spec.json"
    payload = json.loads(input_path.read_text())
    payload["seed"] += 1
    input_bytes = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()
    input_path.write_bytes(input_bytes)
    _replace_resource(index, "input", input_bytes)
    release_resource = index["release"]
    assert isinstance(release_resource, dict)
    checksums = (
        f"{hashlib.sha256(input_bytes).hexdigest()}  inputs/design-spec.json\n"
        f"{release_resource['sha256']}  {release_resource['path']}\n"
    ).encode()
    (output / "inputs" / "SHA256SUMS").write_bytes(checksums)
    _replace_resource(index, "checksums", checksums)
    index["workspace_id"] = _rewrite_index(output, index)

    with pytest.raises(ArtifactError, match="input does not match"):
        verify_execution_workspace(**_verification_arguments(output, release, index))


@pytest.mark.parametrize(
    ("field", "replacement", "message"),
    [
        ("runtime_package_tree_sha256", "0" * 64, "package-tree digest mismatch"),
        ("normalized_design_sha256", "0" * 64, "input digest mismatch"),
        ("release_artifact_name", "other.whl", "release name mismatch"),
    ],
)
def test_execution_verification_cross_checks_receipt_fields(
    tmp_path: Path,
    design_path: Path,
    field: str,
    replacement: str,
    message: str,
) -> None:
    output, release, index = _execute(tmp_path, design_path)
    receipt_path = output / "execution-receipt.json"
    receipt = json.loads(receipt_path.read_text())
    receipt[field] = replacement
    receipt_bytes = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode()
    receipt_path.write_bytes(receipt_bytes)
    _replace_resource(index, "receipt", receipt_bytes)
    index["workspace_id"] = _rewrite_index(output, index)

    with pytest.raises(ArtifactError, match=message):
        verify_execution_workspace(**_verification_arguments(output, release, index))
