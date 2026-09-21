"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/execution/workspace_io.py

Resource reads detect path substitution and verify the recorded digest.

Module Author(s): Eric J. South
Dunlop Lab
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path, PurePosixPath

from motif_balance.constants import MAX_BUNDLE_ARTIFACT_BYTES
from motif_balance.errors import ArtifactError
from motif_balance.model import ExecutionResource


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
