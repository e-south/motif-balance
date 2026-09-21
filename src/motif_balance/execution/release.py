"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/execution/release.py

Bounded wheel ingestion, RECORD validation, and runtime source attestation.

Module Author(s): Eric J. South
Dunlop Lab
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import os
import re
import stat
import zipfile
from email import policy
from email.parser import BytesParser
from pathlib import Path, PurePosixPath

from motif_balance.constants import MAX_BUNDLE_ARTIFACT_BYTES, PACKAGE_VERSION
from motif_balance.errors import ArtifactError


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
    # Attest the complete installed package, not only the execution subpackage.
    package_root = Path(__file__).parents[1]
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
