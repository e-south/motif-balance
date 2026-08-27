from __future__ import annotations

from pathlib import Path

import yaml

from motif_balance.constants import MAX_INPUT_BYTES
from motif_balance.errors import InvalidDesign, InvalidMotif
from motif_balance.model import DesignSpec, MotifModel

from .motif import read_motif
from .structured import load_yaml_unique


def load_design_spec(path: str | Path) -> DesignSpec:
    """Read one bounded design specification and resolve contained motif references."""

    source = Path(path)
    if source.is_symlink():
        raise InvalidDesign(f"Refusing symbolic-link design specification '{source.name}'.")
    try:
        if source.stat().st_size > MAX_INPUT_BYTES:
            raise InvalidDesign(f"Design specification exceeds the {MAX_INPUT_BYTES}-byte limit.")
        raw = source.read_bytes()
        if len(raw) > MAX_INPUT_BYTES:
            raise InvalidDesign(f"Design specification exceeds the {MAX_INPUT_BYTES}-byte limit.")
        payload = load_yaml_unique(raw)
    except (OSError, yaml.YAMLError) as exc:
        raise InvalidDesign(f"Unable to read design specification: {exc}") from exc
    if not isinstance(payload, dict):
        raise InvalidDesign("Design specification must contain one mapping.")
    motifs = payload.get("motifs")
    if not isinstance(motifs, dict):
        raise InvalidDesign("Design specification motifs must be a name-to-model mapping.")
    resolved: dict[str, MotifModel] = {}
    for motif_id, motif_payload in motifs.items():
        if not isinstance(motif_id, str):
            raise InvalidDesign("Motif mapping keys must be strings.")
        if isinstance(motif_payload, str):
            reference = Path(motif_payload)
            if reference.is_absolute() or ".." in reference.parts:
                raise InvalidDesign(
                    f"Motif reference '{motif_payload}' must remain contained in the "
                    "specification directory."
                )
            candidate = source.parent / reference
            cursor = source.parent
            for component in reference.parts:
                cursor /= component
                if cursor.is_symlink():
                    raise InvalidDesign(
                        f"Motif reference '{motif_payload}' traverses a symbolic link."
                    )
            try:
                candidate.resolve(strict=False).relative_to(source.parent.resolve())
            except ValueError as exc:
                raise InvalidDesign(
                    f"Motif reference '{motif_payload}' is not contained in the "
                    "specification directory."
                ) from exc
            try:
                resolved[motif_id] = read_motif(candidate, motif_id=motif_id)
            except InvalidMotif as exc:
                raise InvalidDesign(str(exc), motif_id=motif_id, hint=exc.hint) from exc
        elif isinstance(motif_payload, dict):
            resolved[motif_id] = MotifModel.model_validate(
                {**motif_payload, "motif_id": motif_payload.get("motif_id", motif_id)}
            )
        else:
            raise InvalidDesign(f"Motif '{motif_id}' must be a path or model mapping.")
    payload["motifs"] = resolved
    return DesignSpec.model_validate(payload)
