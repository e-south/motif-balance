"""Atomic no-replace bundle publication with post-publication replay."""

from __future__ import annotations

import ctypes
import errno
import os
import shutil
import stat
import sys
import tempfile
from pathlib import Path

from motif_balance.errors import ArtifactError
from motif_balance.model import (
    PortfolioRecord,
)

from .encoding import artifact_records, manifest_bytes
from .snapshot import _V5_FILES, read_portfolio_record

_PublicationIdentity = tuple[int, int, int]


def _publication_identity(metadata: os.stat_result) -> _PublicationIdentity:
    return (metadata.st_dev, metadata.st_ino, stat.S_IFMT(metadata.st_mode))


def _publish_directory_no_replace(
    source: Path,
    destination: Path,
) -> _PublicationIdentity:
    """Atomically publish one sibling directory without replacing any entry."""

    if source.parent != destination.parent:
        raise OSError(errno.EXDEV, "publication directories must share one parent")
    parent_descriptor: int | None = None
    source_descriptor: int | None = None
    try:
        flags = (
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_DIRECTORY", 0)
        )
        parent_descriptor = os.open(source.parent, flags)
        source_stat = os.stat(
            source.name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
        if not stat.S_ISDIR(source_stat.st_mode):
            raise OSError(errno.EINVAL, "publication source is not a directory")
        source_descriptor = os.open(source.name, flags, dir_fd=parent_descriptor)
        opened_source = os.fstat(source_descriptor)

        source_identity = _publication_identity(source_stat)
        if _publication_identity(opened_source) != source_identity:
            raise OSError(errno.EIO, "publication source changed before it was opened")
        library = ctypes.CDLL(None, use_errno=True)
        source_name = os.fsencode(source.name)
        destination_name = os.fsencode(destination.name)

        def rename_no_replace(from_name: bytes, to_name: bytes) -> int:
            ctypes.set_errno(0)
            return int(
                rename(
                    parent_descriptor,
                    from_name,
                    parent_descriptor,
                    to_name,
                    rename_flag,
                )
            )

        if sys.platform == "darwin":
            rename = library.renameatx_np
            rename.argtypes = [
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_uint,
            ]
            rename.restype = ctypes.c_int
            rename_flag = 0x00000004  # RENAME_EXCL
        elif sys.platform.startswith("linux") and hasattr(library, "renameat2"):
            rename = library.renameat2
            rename.argtypes = [
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_uint,
            ]
            rename.restype = ctypes.c_int
            rename_flag = 0x00000001  # RENAME_NOREPLACE
        else:
            raise OSError(
                errno.ENOTSUP,
                "atomic no-replace directory publication is unavailable",
            )
        result = rename_no_replace(source_name, destination_name)
        if result != 0:
            error = ctypes.get_errno()
            raise OSError(error, os.strerror(error), destination)
        published = os.stat(
            destination.name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
        if _publication_identity(os.fstat(source_descriptor)) != source_identity or (
            _publication_identity(published) != source_identity
        ):
            raise OSError(
                errno.EIO,
                "published directory identity changed during rename; destination left untouched",
            )
        return source_identity
    finally:
        if source_descriptor is not None:
            os.close(source_descriptor)
        if parent_descriptor is not None:
            os.close(parent_descriptor)


def write_bundle(
    portfolio: PortfolioRecord,
    output: Path,
    payloads: dict[str, bytes],
) -> Path:
    if output.exists() or output.is_symlink():
        raise ArtifactError(f"output directory already exists or is unsafe: '{output.name}'")
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ArtifactError("unable to create the bundle publication directory") from exc
    if portfolio.manifest.schema_version not in {"run-manifest/v5", "run-manifest/v6"}:
        raise ArtifactError("new bundle publication requires run-manifest/v5 or v6")
    if set(payloads) != _V5_FILES - {"manifest.json"}:
        raise ArtifactError("bundle payload inventory is incomplete")
    records = artifact_records(payloads)
    if records != portfolio.manifest.artifacts:
        raise ArtifactError("portfolio artifact digests do not match its semantic contents")
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.tmp-", dir=output.parent))
    try:
        for path, payload in payloads.items():
            (temporary / path).write_bytes(payload)
        (temporary / "manifest.json").write_bytes(manifest_bytes(portfolio.manifest))
        replay = read_portfolio_record(temporary)
        if replay.model_dump(mode="python") != portfolio.model_dump(mode="python"):
            raise ArtifactError("bundle round-trip validation changed portfolio semantics")
        _publish_directory_no_replace(temporary, output)
        try:
            published = read_portfolio_record(output)
            if published.model_dump(mode="python") != portfolio.model_dump(mode="python"):
                raise ArtifactError("published bundle replay changed portfolio semantics")
        except Exception as exc:
            raise ArtifactError(
                "published bundle failed post-publication replay; destination left untouched "
                "for inspection"
            ) from exc
    except FileExistsError as exc:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise ArtifactError(
            f"output directory already exists or is unsafe: '{output.name}'"
        ) from exc
    except OSError as exc:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise ArtifactError("unable to publish the canonical bundle") from exc
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    return output
