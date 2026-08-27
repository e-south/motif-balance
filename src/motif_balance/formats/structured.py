from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import yaml


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
