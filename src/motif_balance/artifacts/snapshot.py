"""Bounded descriptor-pinned bundle reads and inventory closure."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path

from motif_balance.constants import (
    MAX_BUNDLE_ARTIFACT_BYTES,
    MAX_INPUT_BYTES,
    MAX_RUN_MANIFEST_BYTES,
)
from motif_balance.errors import ArtifactError
from motif_balance.model import (
    PortfolioRecord,
    RunManifest,
)

from .decoding import _json_object, _parse_manifest, _read_candidates, _read_spec
from .encoding import _digest, base_artifact_payloads, bundle_id, manifest_bytes

_CANONICAL_FILES = {
    "design.json",
    "motifs.json",
    "candidates.tsv",
    "matches.tsv",
    "manifest.json",
}
_DERIVED_FILES = {"candidates.fasta"}
_V3_FILES = _CANONICAL_FILES | _DERIVED_FILES
_V4_FILES = _V3_FILES
_V5_FILES = _V4_FILES
_V2_FILES = _V3_FILES | {"report.html"}


def _schema_files(manifest: RunManifest) -> set[str]:
    if manifest.schema_version == "run-manifest/v2":
        return _V2_FILES
    if manifest.schema_version == "run-manifest/v3":
        return _V3_FILES
    if manifest.schema_version == "run-manifest/v4":
        return _V4_FILES
    return _V5_FILES


@dataclass(frozen=True, slots=True)
class BundleSnapshot:
    """One descriptor-bound set of bundle bytes and its parsed portfolio."""

    portfolio: PortfolioRecord
    members: tuple[tuple[str, bytes], ...]

    def payload(self, path: str) -> bytes:
        for member_path, payload in self.members:
            if member_path == path:
                return payload
        raise ArtifactError(f"bundle snapshot does not contain '{path}'")


def _read_snapshot_member(
    directory_descriptor: int,
    path: str,
    *,
    limit: int,
    expected_bytes: int | None = None,
) -> bytes:
    descriptor: int | None = None
    try:
        before = os.stat(path, dir_fd=directory_descriptor, follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode):
            raise ArtifactError(f"bundle snapshot contains unsafe member '{path}'")
        if before.st_size > limit:
            raise ArtifactError(f"bundle member '{path}' exceeds the {limit}-byte limit")
        if expected_bytes is not None and before.st_size != expected_bytes:
            raise ArtifactError(f"artifact digest or size mismatch for '{path}'")
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags, dir_fd=directory_descriptor)
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)
            or opened.st_size != before.st_size
        ):
            raise ArtifactError(f"bundle member '{path}' changed during bundle snapshot")
        read_limit = (expected_bytes if expected_bytes is not None else limit) + 1
        chunks: list[bytes] = []
        remaining = read_limit
        while remaining:
            chunk = os.read(descriptor, remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        payload = b"".join(chunks)
        after = os.fstat(descriptor)
        if (
            (after.st_dev, after.st_ino) != (opened.st_dev, opened.st_ino)
            or after.st_size != opened.st_size
            or len(payload) != opened.st_size
        ):
            raise ArtifactError(f"bundle member '{path}' changed during bundle snapshot")
        return payload
    except OSError as exc:
        raise ArtifactError(
            f"bundle member '{path}' changed during bundle snapshot or is unsafe"
        ) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def read_bundle_snapshot(directory: str | Path) -> BundleSnapshot:
    """Read and validate every member once through a pinned directory descriptor."""

    root = Path(directory)
    directory_descriptor: int | None = None
    try:
        flags = (
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_DIRECTORY", 0)
        )
        directory_descriptor = os.open(root, flags)
        opened_root = os.fstat(directory_descriptor)
        if not stat.S_ISDIR(opened_root.st_mode):
            raise ArtifactError(f"bundle directory does not exist or is unsafe: {root}")
        files = set(os.listdir(directory_descriptor))
        for path in files:
            if not path or "/" in path or "\\" in path:
                raise ArtifactError("bundle inventory contains an unsafe member name")
            member_stat = os.stat(
                path,
                dir_fd=directory_descriptor,
                follow_symlinks=False,
            )
            if not stat.S_ISREG(member_stat.st_mode):
                raise ArtifactError(f"bundle contains unsafe non-file entry '{path}'")
    except OSError as exc:
        if directory_descriptor is not None:
            os.close(directory_descriptor)
        raise ArtifactError(f"bundle directory does not exist or is unsafe: {root}") from exc
    except ArtifactError:
        if directory_descriptor is not None:
            os.close(directory_descriptor)
        raise
    assert directory_descriptor is not None
    try:
        if "manifest.json" not in files:
            raise ArtifactError("bundle inventory mismatch; missing=['manifest.json'], extra=[]")
        canonical_manifest = _read_snapshot_member(
            directory_descriptor,
            "manifest.json",
            limit=MAX_RUN_MANIFEST_BYTES,
        )
        manifest_payload = _json_object(canonical_manifest, label="manifest.json")
        if (
            manifest_payload.get("schema_version") != "run-manifest/v6"
            and len(canonical_manifest) > MAX_INPUT_BYTES
        ):
            raise ArtifactError(
                f"bundle member 'manifest.json' exceeds the {MAX_INPUT_BYTES}-byte limit"
            )
        manifest = _parse_manifest(manifest_payload)
        expected_files = _schema_files(manifest)
        if files != expected_files:
            missing = sorted(expected_files - files)
            extra = sorted(files - expected_files)
            raise ArtifactError(f"bundle inventory mismatch; missing={missing}, extra={extra}")
        declared = {artifact.path: artifact for artifact in manifest.artifacts}
        if set(declared) != expected_files - {"manifest.json"}:
            raise ArtifactError("manifest artifact inventory is incomplete")
        members = {"manifest.json": canonical_manifest}
        for path, artifact in declared.items():
            member_limit = (
                MAX_INPUT_BYTES
                if path in {"design.json", "motifs.json"}
                else MAX_BUNDLE_ARTIFACT_BYTES
            )
            if artifact.bytes > member_limit:
                raise ArtifactError(f"bundle member '{path}' exceeds the {member_limit}-byte limit")
            payload = _read_snapshot_member(
                directory_descriptor,
                path,
                limit=member_limit,
                expected_bytes=artifact.bytes,
            )
            if _digest(payload) != artifact.sha256:
                raise ArtifactError(f"artifact digest mismatch for '{path}'")
            members[path] = payload
        if set(os.listdir(directory_descriptor)) != files:
            raise ArtifactError("bundle inventory changed during bundle snapshot")
        closed_root = os.fstat(directory_descriptor)
        if (closed_root.st_dev, closed_root.st_ino) != (opened_root.st_dev, opened_root.st_ino):
            raise ArtifactError("bundle directory changed during bundle snapshot")
    finally:
        os.close(directory_descriptor)

    spec = _read_spec(members)
    candidates = _read_candidates(members, spec)
    expected_payloads = base_artifact_payloads(spec, candidates)
    for path, payload in expected_payloads.items():
        if payload != members[path]:
            raise ArtifactError(f"artifact semantic replay mismatch for '{path}'")
    if bundle_id(manifest) != manifest.bundle_id:
        raise ArtifactError("bundle identity does not match its artifact digests")
    if canonical_manifest != manifest_bytes(manifest):
        raise ArtifactError("manifest does not use the canonical encoding")
    try:
        portfolio = PortfolioRecord(
            problem_id=manifest.problem_id,
            run_id=manifest.run_id,
            spec=spec,
            candidates=candidates,
            manifest=manifest,
        )
    except ValueError as exc:
        raise ArtifactError(
            "bundle scientific replay found internally inconsistent records"
        ) from exc
    return BundleSnapshot(portfolio=portfolio, members=tuple(sorted(members.items())))


def read_portfolio_record(directory: str | Path) -> PortfolioRecord:
    return read_bundle_snapshot(directory).portfolio
