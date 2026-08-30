from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import os
import re
import shutil
import stat
import tempfile
import zipfile
from datetime import UTC, datetime
from email import policy
from email.parser import BytesParser
from pathlib import Path, PurePosixPath

from motif_balance.api import design
from motif_balance.artifacts import (
    _publish_directory_no_replace,
    manifest_bytes,
    read_verified_portfolio,
)
from motif_balance.constants import MAX_BUNDLE_ARTIFACT_BYTES, PACKAGE_VERSION
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


def _resolved_spec_bytes(spec: DesignSpec) -> bytes:
    payload = spec.model_dump(mode="json", exclude={"motifs"})
    payload["motifs"] = {motif.motif_id: motif.model_dump(mode="json") for motif in spec.motifs}
    return (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode()


def _resource(path: str, payload: bytes) -> ExecutionResource:
    return ExecutionResource(
        path=path,
        sha256=hashlib.sha256(payload).hexdigest(),
        bytes=len(payload),
    )


def _read_release(path: Path) -> bytes:
    descriptor: int | None = None
    try:
        before = os.lstat(path)
        if not stat.S_ISREG(before.st_mode):
            raise ArtifactError("release artifact must be a regular file, not a symbolic link")
        if before.st_size > MAX_BUNDLE_ARTIFACT_BYTES:
            raise ArtifactError(
                f"release artifact must be a file no larger than {MAX_BUNDLE_ARTIFACT_BYTES} bytes"
            )
        flags = (
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0)
        )
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)
            or opened.st_size != before.st_size
        ):
            raise ArtifactError("release artifact changed before it was opened")
        chunks: list[bytes] = []
        remaining = MAX_BUNDLE_ARTIFACT_BYTES + 1
        while remaining:
            chunk = os.read(descriptor, remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        payload = b"".join(chunks)
        after = os.fstat(descriptor)
        path_after = os.lstat(path)
        opened_identity = (
            opened.st_dev,
            opened.st_ino,
            opened.st_size,
            opened.st_mtime_ns,
            opened.st_ctime_ns,
        )
        after_identity = (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        path_identity = (
            path_after.st_dev,
            path_after.st_ino,
            path_after.st_size,
            path_after.st_mtime_ns,
            path_after.st_ctime_ns,
        )
        if len(payload) > MAX_BUNDLE_ARTIFACT_BYTES:
            raise ArtifactError(
                f"release artifact must be a file no larger than {MAX_BUNDLE_ARTIFACT_BYTES} bytes"
            )
        if (
            opened_identity != after_identity
            or opened_identity != path_identity
            or len(payload) != opened.st_size
        ):
            raise ArtifactError("release artifact changed while it was read")
    except ArtifactError:
        raise
    except OSError as exc:
        raise ArtifactError(f"release artifact is unsafe or changed while opening: {exc}") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
    return payload


def _canonical_json_bytes(payload: object) -> bytes:
    return (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _package_tree_digest(entries: dict[str, bytes]) -> str:
    records = [
        {"path": path, "sha256": hashlib.sha256(payload).hexdigest()}
        for path, payload in sorted(entries.items())
    ]
    return hashlib.sha256(_canonical_json_bytes(records)).hexdigest()


def _release_package_tree(payload: bytes) -> dict[str, bytes]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(payload))
    except zipfile.BadZipFile as exc:
        raise ArtifactError("release artifact is not a valid wheel archive") from exc
    entries: dict[str, bytes] = {}
    with archive:
        members = [member for member in archive.infolist() if not member.is_dir()]
        names = [member.filename for member in members]
        if len(names) != len(set(names)):
            raise ArtifactError("release artifact contains duplicate wheel members")
        if sum(member.file_size for member in members) > MAX_BUNDLE_ARTIFACT_BYTES:
            raise ArtifactError("release wheel contents exceed the byte limit")
        for member in members:
            path = PurePosixPath(member.filename)
            if (
                member.filename.startswith("/")
                or "\\" in member.filename
                or any(part in {"", ".", ".."} for part in path.parts)
            ):
                raise ArtifactError("release artifact contains an unsafe wheel path")
            if stat.S_ISLNK(member.external_attr >> 16):
                raise ArtifactError("release artifact contains a symbolic-link wheel member")
        metadata_members = [
            member for member in members if member.filename.endswith(".dist-info/METADATA")
        ]
        wheel_members = [
            member for member in members if member.filename.endswith(".dist-info/WHEEL")
        ]
        if len(metadata_members) != 1 or len(wheel_members) != 1:
            raise ArtifactError("release artifact does not contain one wheel metadata record")
        dist_info = metadata_members[0].filename.removesuffix("METADATA")
        if wheel_members[0].filename != f"{dist_info}WHEEL":
            raise ArtifactError("release artifact wheel metadata directories do not match")
        record_name = f"{dist_info}RECORD"
        if names.count(record_name) != 1:
            raise ArtifactError("release artifact does not contain one RECORD")
        for name in names:
            allowed_metadata = name in {
                f"{dist_info}METADATA",
                f"{dist_info}WHEEL",
                f"{dist_info}RECORD",
                f"{dist_info}entry_points.txt",
            } or name.startswith(f"{dist_info}licenses/")
            if not name.startswith("motif_balance/") and not allowed_metadata:
                raise ArtifactError(f"release artifact contains unexpected wheel member '{name}'")
        try:
            payloads = {member.filename: archive.read(member) for member in members}
        except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
            raise ArtifactError("release artifact contains unreadable wheel members") from exc
        metadata = BytesParser(policy=policy.default).parsebytes(
            payloads[metadata_members[0].filename]
        )
        normalized_name = re.sub(r"[-_.]+", "-", str(metadata.get("Name", ""))).lower()
        if normalized_name != "motif-balance" or metadata.get("Version") != PACKAGE_VERSION:
            raise ArtifactError("release wheel identity does not match this package build")
        expected_entry_points = b"[console_scripts]\nmotif-balance = motif_balance.cli:app\n"
        if payloads.get(f"{dist_info}entry_points.txt") != expected_entry_points:
            raise ArtifactError("release artifact console entry point is missing or unexpected")
        try:
            record_rows = list(csv.reader(io.StringIO(payloads[record_name].decode("utf-8"))))
        except (UnicodeDecodeError, csv.Error) as exc:
            raise ArtifactError("release artifact RECORD is not valid UTF-8 CSV") from exc
        if len(record_rows) != len(names) or any(len(row) != 3 for row in record_rows):
            raise ArtifactError("release artifact RECORD is malformed")
        if {row[0] for row in record_rows} != set(names):
            raise ArtifactError("release artifact RECORD inventory mismatch")
        for name, digest, size in record_rows:
            if name == record_name:
                if digest or size:
                    raise ArtifactError("release artifact RECORD must not hash itself")
                continue
            expected_digest = (
                base64.urlsafe_b64encode(hashlib.sha256(payloads[name]).digest())
                .rstrip(b"=")
                .decode()
            )
            if digest != f"sha256={expected_digest}" or size != str(len(payloads[name])):
                raise ArtifactError(f"release artifact RECORD mismatch for '{name}'")
        for name, member_payload in payloads.items():
            if not name.startswith("motif_balance/"):
                continue
            relative = name.removeprefix("motif_balance/")
            parts = Path(relative).parts
            if not relative or any(part in {"", ".", ".."} for part in parts):
                raise ArtifactError("release artifact contains an unsafe package path")
            entries[relative] = member_payload
    if "__init__.py" not in entries:
        raise ArtifactError("release artifact does not contain the motif_balance package")
    return entries


def _runtime_package_tree() -> dict[str, bytes]:
    package_root = Path(__file__).parent
    entries: dict[str, bytes] = {}
    for path in sorted(package_root.rglob("*")):
        if path.is_dir() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        if path.is_symlink() or not path.is_file():
            raise ArtifactError("runtime package tree contains an unsafe file")
        entries[path.relative_to(package_root).as_posix()] = path.read_bytes()
    return entries


def _attest_release_runtime(release_payload: bytes) -> str:
    release_tree = _release_package_tree(release_payload)
    runtime_tree = _runtime_package_tree()
    if release_tree != runtime_tree:
        raise ArtifactError("release artifact package tree does not match the running package")
    return _package_tree_digest(runtime_tree)


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


def _read_workspace_file(root: Path, relative: str) -> bytes:
    path = PurePosixPath(relative)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ArtifactError(f"execution workspace contains unsafe resource '{relative}'")
    root_descriptor: int | None = None
    directory_descriptors: list[int] = []
    descriptor: int | None = None
    try:
        directory_flags = (
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_DIRECTORY", 0)
        )
        root_descriptor = os.open(root, directory_flags)
        parent_descriptor = root_descriptor
        for component in path.parts[:-1]:
            before_directory = os.stat(
                component,
                dir_fd=parent_descriptor,
                follow_symlinks=False,
            )
            nested = os.open(component, directory_flags, dir_fd=parent_descriptor)
            opened_directory = os.fstat(nested)
            if not stat.S_ISDIR(opened_directory.st_mode) or (
                opened_directory.st_dev,
                opened_directory.st_ino,
            ) != (before_directory.st_dev, before_directory.st_ino):
                os.close(nested)
                raise ArtifactError(
                    f"execution resource '{relative}' changed while opening its directory"
                )
            directory_descriptors.append(nested)
            parent_descriptor = nested
        name = path.parts[-1]
        before = os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode):
            raise ArtifactError(f"execution workspace contains unsafe resource '{relative}'")
        if before.st_size > MAX_BUNDLE_ARTIFACT_BYTES:
            raise ArtifactError(f"execution resource '{relative}' exceeds the byte limit")
        file_flags = (
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0)
        )
        descriptor = os.open(name, file_flags, dir_fd=parent_descriptor)
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)
            or opened.st_size != before.st_size
        ):
            raise ArtifactError(f"execution resource '{relative}' changed before it was opened")
        chunks: list[bytes] = []
        remaining = MAX_BUNDLE_ARTIFACT_BYTES + 1
        while remaining:
            chunk = os.read(descriptor, remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        payload = b"".join(chunks)
        after = os.fstat(descriptor)
        path_after = os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
        opened_identity = (
            opened.st_dev,
            opened.st_ino,
            opened.st_size,
            opened.st_mtime_ns,
            opened.st_ctime_ns,
        )
        after_identity = (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        path_identity = (
            path_after.st_dev,
            path_after.st_ino,
            path_after.st_size,
            path_after.st_mtime_ns,
            path_after.st_ctime_ns,
        )
        if len(payload) > MAX_BUNDLE_ARTIFACT_BYTES:
            raise ArtifactError(f"execution resource '{relative}' exceeds the byte limit")
        if (
            opened_identity != after_identity
            or opened_identity != path_identity
            or len(payload) != opened.st_size
        ):
            raise ArtifactError(f"execution resource '{relative}' changed while it was read")
        return payload
    except ArtifactError:
        raise
    except OSError as exc:
        raise ArtifactError(
            f"execution resource '{relative}' is unsafe or changed while opening: {exc}"
        ) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        for directory_descriptor in reversed(directory_descriptors):
            os.close(directory_descriptor)
        if root_descriptor is not None:
            os.close(root_descriptor)


def _verify_resource(root: Path, resource: ExecutionResource) -> bytes:
    payload = _read_workspace_file(root, resource.path)
    if len(payload) != resource.bytes or hashlib.sha256(payload).hexdigest() != resource.sha256:
        raise ArtifactError(f"execution resource digest mismatch for '{resource.path}'")
    return payload


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
