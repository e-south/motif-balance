"""Strict immutable base and deterministic scalar identities."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _contains_boolean(value: object) -> bool:
    if isinstance(value, bool):
        return True
    if isinstance(value, Mapping):
        return any(_contains_boolean(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_boolean(item) for item in value)
    return False


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    @model_validator(mode="before")
    @classmethod
    def reject_boolean_numeric_values(cls, value: Any) -> Any:
        if _contains_boolean(value):
            raise ValueError("boolean values are not valid model values")
        return value
