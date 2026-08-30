from __future__ import annotations

import json
import os
import stat
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import yaml

from motif_balance.constants import MAX_INPUT_BYTES


class BoundedInputError(ValueError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def _identity(metadata: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


@contextmanager
def pinned_directory(path: Path) -> Iterator[int]:
    """Pin one real directory and reject link or inode substitution."""

    descriptor: int | None = None
    try:
        before = os.lstat(path)
        if not stat.S_ISDIR(before.st_mode):
            reason = "symbolic-link input" if stat.S_ISLNK(before.st_mode) else "unsafe input"
            raise BoundedInputError(reason)
        descriptor = os.open(
            path,
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0),
        )
        opened = os.fstat(descriptor)
        if not stat.S_ISDIR(opened.st_mode) or _identity(opened) != _identity(before):
            raise BoundedInputError("input directory changed before it was opened")
        yield descriptor
        after = os.fstat(descriptor)
        path_after = os.lstat(path)
        if _identity(opened) != _identity(after) or _identity(opened) != _identity(path_after):
            raise BoundedInputError("input directory changed while it was read")
    except BoundedInputError:
        raise
    except OSError as exc:
        raise BoundedInputError(f"unsafe or changed input directory: {exc}") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def read_bounded_regular_file_at(directory_fd: int, relative_path: Path) -> bytes:
    """Read a bounded file by descriptor-walking every contained path component."""

    components = relative_path.parts
    if (
        not components
        or relative_path.is_absolute()
        or any(part in {"", ".", ".."} for part in components)
    ):
        raise BoundedInputError("unsafe contained path")
    opened_directories: list[tuple[int, str, int, tuple[int, int, int, int, int, int]]] = []
    current_fd = os.dup(directory_fd)
    file_fd: int | None = None
    try:
        directory_flags = (
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0)
        )
        for component in components[:-1]:
            before = os.stat(component, dir_fd=current_fd, follow_symlinks=False)
            if not stat.S_ISDIR(before.st_mode):
                reason = "symbolic-link input" if stat.S_ISLNK(before.st_mode) else "unsafe input"
                raise BoundedInputError(reason)
            child_fd = os.open(component, directory_flags, dir_fd=current_fd)
            opened = os.fstat(child_fd)
            if not stat.S_ISDIR(opened.st_mode) or _identity(opened) != _identity(before):
                os.close(child_fd)
                raise BoundedInputError("input directory changed before it was opened")
            opened_directories.append((current_fd, component, child_fd, _identity(opened)))
            current_fd = child_fd

        name = components[-1]
        before = os.stat(name, dir_fd=current_fd, follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode):
            reason = "symbolic-link input" if stat.S_ISLNK(before.st_mode) else "unsafe input"
            raise BoundedInputError(reason)
        if before.st_size > MAX_INPUT_BYTES:
            raise BoundedInputError("byte limit")
        file_fd = os.open(
            name,
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0),
            dir_fd=current_fd,
        )
        opened_file = os.fstat(file_fd)
        if not stat.S_ISREG(opened_file.st_mode) or _identity(opened_file) != _identity(before):
            raise BoundedInputError("input changed before it was opened")
        chunks: list[bytes] = []
        remaining = MAX_INPUT_BYTES + 1
        while remaining:
            chunk = os.read(file_fd, remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        after_file = os.fstat(file_fd)
        path_after = os.stat(name, dir_fd=current_fd, follow_symlinks=False)
        if len(raw) > MAX_INPUT_BYTES:
            raise BoundedInputError("byte limit")
        if (
            _identity(opened_file) != _identity(after_file)
            or _identity(opened_file) != _identity(path_after)
            or len(raw) != opened_file.st_size
        ):
            raise BoundedInputError("input changed while it was read")
        for parent_fd, component, child_fd, opened_identity in reversed(opened_directories):
            current = os.fstat(child_fd)
            current_path = os.stat(component, dir_fd=parent_fd, follow_symlinks=False)
            if opened_identity != _identity(current) or opened_identity != _identity(current_path):
                raise BoundedInputError("input directory changed while it was read")
        return raw
    except BoundedInputError:
        raise
    except OSError as exc:
        raise BoundedInputError(f"unsafe or changed contained input: {exc}") from exc
    finally:
        if file_fd is not None:
            os.close(file_fd)
        for parent_fd, _component, child_fd, _identity_value in reversed(opened_directories):
            os.close(child_fd)
            if parent_fd != directory_fd and parent_fd not in {
                entry[2] for entry in opened_directories
            }:
                os.close(parent_fd)
        if not opened_directories:
            os.close(current_fd)


def read_bounded_regular_file(path: Path) -> bytes:
    """Read one immutable regular-file snapshot without following links."""

    descriptor: int | None = None
    try:
        before = os.lstat(path)
        if not stat.S_ISREG(before.st_mode):
            reason = "symbolic-link input" if stat.S_ISLNK(before.st_mode) else "unsafe input"
            raise BoundedInputError(reason)
        if before.st_size > MAX_INPUT_BYTES:
            raise BoundedInputError("byte limit")
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
            raise BoundedInputError("input changed before it was opened")
        chunks: list[bytes] = []
        remaining = MAX_INPUT_BYTES + 1
        while remaining:
            chunk = os.read(descriptor, remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
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
        if len(raw) > MAX_INPUT_BYTES:
            raise BoundedInputError("byte limit")
        if (
            opened_identity != after_identity
            or opened_identity != path_identity
            or len(raw) != opened.st_size
        ):
            raise BoundedInputError("input changed while it was read")
        return raw
    except BoundedInputError:
        raise
    except OSError as exc:
        raise BoundedInputError(f"unsafe or changed input: {exc}") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


class _UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(
    loader: yaml.SafeLoader,
    node: yaml.MappingNode,
    deep: bool = False,
) -> dict[object, object]:
    result: dict[object, object] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def load_yaml_unique(raw: bytes | str) -> object:
    return yaml.load(raw, Loader=_UniqueKeyLoader)


def _unique_json_object(pairs: list[tuple[str, object]]) -> Mapping[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise json.JSONDecodeError(f"duplicate key {key!r}", "", 0)
        result[key] = value
    return result


def load_json_unique(raw: bytes | str) -> Any:
    return json.loads(raw, object_pairs_hook=_unique_json_object)
