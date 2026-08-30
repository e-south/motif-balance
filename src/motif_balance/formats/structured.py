from __future__ import annotations

import json
import os
import stat
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from motif_balance.constants import MAX_INPUT_BYTES


class BoundedInputError(ValueError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


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
