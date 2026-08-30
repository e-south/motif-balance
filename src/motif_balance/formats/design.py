from __future__ import annotations

from pathlib import Path

import yaml

from motif_balance.constants import MAX_INPUT_BYTES
from motif_balance.errors import InvalidDesign, InvalidMotif
from motif_balance.model import DesignSpec, MotifModel

from .motif import read_motif
from .structured import BoundedInputError, load_yaml_unique, read_bounded_regular_file


def _resolve_motif(
    source: Path,
    *,
    motif_id: str,
    payload: object,
) -> MotifModel:
    if isinstance(payload, str):
        reference = Path(payload)
        if reference.is_absolute() or ".." in reference.parts:
            raise InvalidDesign(
                f"Motif reference '{payload}' must remain contained in the specification directory."
            )
        candidate = source.parent / reference
        cursor = source.parent
        for component in reference.parts:
            cursor /= component
            if cursor.is_symlink():
                raise InvalidDesign(f"Motif reference '{payload}' traverses a symbolic link.")
        try:
            candidate.resolve(strict=False).relative_to(source.parent.resolve())
        except ValueError as exc:
            raise InvalidDesign(
                f"Motif reference '{payload}' is not contained in the specification directory."
            ) from exc
        try:
            return read_motif(candidate, motif_id=motif_id)
        except InvalidMotif as exc:
            raise InvalidDesign(str(exc), motif_id=motif_id, hint=exc.hint) from exc
    if isinstance(payload, dict):
        if "schema_version" not in payload:
            raise InvalidDesign(
                f"Inline motif '{motif_id}' must declare schema_version explicitly."
            )
        return MotifModel.model_validate({**payload, "motif_id": payload.get("motif_id", motif_id)})
    raise InvalidDesign(f"Motif '{motif_id}' must be a path or model mapping.")


def load_design_spec(path: str | Path) -> DesignSpec:
    """Read one bounded design specification and resolve contained motif references."""

    source = Path(path)
    try:
        raw = read_bounded_regular_file(source)
        payload = load_yaml_unique(raw)
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
    except (OSError, yaml.YAMLError) as exc:
        raise InvalidDesign(f"Unable to read design specification: {exc}") from exc
    if not isinstance(payload, dict):
        raise InvalidDesign("Design specification must contain one mapping.")
    if "schema_version" not in payload:
        raise InvalidDesign(
            "Serialized design specifications must declare schema_version explicitly; "
            "use 'design-spec/v1' for historical scoring or 'design-spec/v2' for "
            "relative PWM attainment."
        )
    motifs = payload.get("motifs")
    if not isinstance(motifs, dict):
        raise InvalidDesign("Design specification motifs must be a name-to-model mapping.")
    resolved: dict[str, MotifModel] = {}
    for motif_id, motif_payload in motifs.items():
        if not isinstance(motif_id, str):
            raise InvalidDesign("Motif mapping keys must be strings.")
        resolved[motif_id] = _resolve_motif(source, motif_id=motif_id, payload=motif_payload)
    payload["motifs"] = resolved
    avoiders = payload.get("avoiders", {})
    if isinstance(avoiders, (list, tuple)):
        return DesignSpec.model_validate(payload)
    if not isinstance(avoiders, dict):
        raise InvalidDesign("Design specification avoiders must be a name-to-constraint mapping.")
    resolved_avoiders: dict[str, dict[str, object]] = {}
    for motif_id, constraint in avoiders.items():
        if not isinstance(motif_id, str):
            raise InvalidDesign("Avoider mapping keys must be strings.")
        if not isinstance(constraint, dict):
            raise InvalidDesign(f"Avoider '{motif_id}' must be a constraint mapping.")
        if "motif" not in constraint:
            raise InvalidDesign(f"Avoider '{motif_id}' must declare a motif.")
        resolved_avoiders[motif_id] = {
            **constraint,
            "motif": _resolve_motif(
                source,
                motif_id=motif_id,
                payload=constraint["motif"],
            ),
        }
    payload["avoiders"] = resolved_avoiders
    return DesignSpec.model_validate(payload)
