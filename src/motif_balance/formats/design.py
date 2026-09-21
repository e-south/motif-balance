"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/formats/design.py

Resolve design files and their motif references through bounded input reads.

Module Author(s): Eric J. South
Dunlop Lab
--------------------------------------------------------------------------------
"""

from __future__ import annotations

from pathlib import Path

import yaml

from motif_balance.constants import MAX_INPUT_BYTES
from motif_balance.errors import InvalidDesign, InvalidMotif
from motif_balance.model import DesignSpec, MotifModel

from .motif import _read_motif_snapshot
from .structured import (
    BoundedInputError,
    load_yaml_unique,
    pinned_directory,
    read_bounded_regular_file_at,
)


def _resolve_motif(
    source: Path,
    *,
    directory_fd: int,
    motif_id: str | None,
    payload: object,
) -> MotifModel:
    if isinstance(payload, str):
        reference = Path(payload)
        if reference.is_absolute() or ".." in reference.parts:
            raise InvalidDesign(
                f"Motif reference '{payload}' must remain contained in the specification directory."
            )
        try:
            raw = read_bounded_regular_file_at(directory_fd, reference)
            return _read_motif_snapshot(reference, raw, motif_id=motif_id)
        except BoundedInputError as exc:
            if exc.reason == "byte limit":
                raise InvalidDesign(
                    f"Motif file '{reference.name}' exceeds the {MAX_INPUT_BYTES}-byte limit."
                ) from exc
            raise InvalidDesign(
                f"Motif reference '{payload}' is unsafe or changed: {exc}."
            ) from exc
        except InvalidMotif as exc:
            raise InvalidDesign(str(exc), motif_id=motif_id, hint=exc.hint) from exc
    if isinstance(payload, dict):
        if "schema_version" not in payload:
            raise InvalidDesign(
                f"Inline motif '{motif_id}' must declare schema_version explicitly."
            )
        resolved_id = payload.get("motif_id", motif_id)
        return MotifModel.model_validate({**payload, "motif_id": resolved_id})
    label = motif_id or "specification"
    raise InvalidDesign(f"Motif '{label}' must be a path or model mapping.")


def _load_design_snapshot(source: Path, raw: bytes, *, directory_fd: int) -> DesignSpec:
    try:
        payload = load_yaml_unique(raw)
    except (OSError, yaml.YAMLError) as exc:
        raise InvalidDesign(f"Unable to read design specification: {exc}") from exc
    if not isinstance(payload, dict):
        raise InvalidDesign("Design specification must contain one mapping.")
    if "schema_version" not in payload:
        raise InvalidDesign(
            "Serialized design specifications must declare schema_version explicitly; "
            "use 'design-spec/v3' for directional specifications."
        )
    if payload["schema_version"] != "design-spec/v3":
        raise InvalidDesign("Unsupported design schema_version.", field="schema_version")
    specifications = payload.get("specifications")
    if not isinstance(specifications, list) or not specifications:
        raise InvalidDesign("Design specification specifications must be a nonempty list.")
    resolved_specifications: list[dict[str, object]] = []
    for item in specifications:
        if not isinstance(item, dict):
            raise InvalidDesign("Each motif specification must be a mapping.")
        if "motif" not in item:
            raise InvalidDesign("Each motif specification must declare a motif.")
        declared_id = item.get("motif_id")
        if declared_id is not None and not isinstance(declared_id, str):
            raise InvalidDesign("Specification motif_id must be a string when declared.")
        resolved_specifications.append(
            {
                **{key: value for key, value in item.items() if key != "motif_id"},
                "motif": _resolve_motif(
                    source,
                    directory_fd=directory_fd,
                    motif_id=declared_id,
                    payload=item["motif"],
                ),
            }
        )
    payload["specifications"] = resolved_specifications
    return DesignSpec.model_validate(payload)


def load_design_spec(path: str | Path) -> DesignSpec:
    """Read one bounded design specification and resolve contained motif references."""

    source = Path(path)
    try:
        with pinned_directory(source.parent) as directory_fd:
            raw = read_bounded_regular_file_at(directory_fd, Path(source.name))
            return _load_design_snapshot(source, raw, directory_fd=directory_fd)
    except BoundedInputError as exc:
        if exc.reason == "byte limit":
            raise InvalidDesign(
                f"Design specification exceeds the {MAX_INPUT_BYTES}-byte limit."
            ) from exc
        if exc.reason == "symbolic-link input":
            raise InvalidDesign(
                f"Refusing symbolic-link design specification '{source.name}'."
            ) from exc
        raise InvalidDesign(f"Unable to read design specification: {exc}") from exc
