from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml

from motif_balance.constants import MAX_INPUT_BYTES
from motif_balance.errors import InvalidMotif
from motif_balance.model import MotifModel


def _read_structured(path: Path, raw: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(raw) if path.suffix.lower() == ".json" else yaml.safe_load(raw)
    except (OSError, json.JSONDecodeError, yaml.YAMLError) as exc:
        raise InvalidMotif(f"Unable to read motif file '{path.name}': {exc}") from exc
    if not isinstance(payload, dict):
        raise InvalidMotif(f"Motif file '{path.name}' must contain one object.")
    return payload


def _read_meme(text: str, *, requested_id: str | None) -> dict[str, Any]:
    background_match = re.search(
        r"Background letter frequencies[^\n]*\n\s*A\s+([0-9.eE+-]+)\s+C\s+([0-9.eE+-]+)"
        r"\s+G\s+([0-9.eE+-]+)\s+T\s+([0-9.eE+-]+)",
        text,
    )
    if background_match is None:
        raise InvalidMotif("MEME motif must declare A/C/G/T background frequencies.")
    motif_matches = list(re.finditer(r"^MOTIF\s+(\S+).*$", text, flags=re.MULTILINE))
    if not motif_matches:
        raise InvalidMotif("MEME file contains no MOTIF record.")
    selected = None
    for index, match in enumerate(motif_matches):
        motif_id = match.group(1)
        if requested_id is None or motif_id == requested_id:
            selected = (index, motif_id, match.end())
            break
    if selected is None:
        raise InvalidMotif(f"MEME file contains no motif named '{requested_id}'.")
    index, motif_id, start = selected
    end = motif_matches[index + 1].start() if index + 1 < len(motif_matches) else len(text)
    block = text[start:end]
    matrix_header = re.search(r"letter-probability matrix:.*\bw=\s*(\d+).*\n", block)
    if matrix_header is None:
        raise InvalidMotif(f"MEME motif '{motif_id}' lacks a probability matrix.")
    width = int(matrix_header.group(1))
    rows: list[tuple[float, float, float, float]] = []
    for line in block[matrix_header.end() :].splitlines():
        parts = line.split()
        if len(parts) != 4:
            if rows:
                break
            continue
        try:
            rows.append(tuple(float(part) for part in parts))  # type: ignore[arg-type]
        except ValueError:
            if rows:
                break
    if len(rows) != width:
        raise InvalidMotif(
            f"MEME motif '{motif_id}' declares width {width} but has {len(rows)} rows."
        )
    return {
        "motif_id": motif_id,
        "probabilities": tuple(rows),
        "background": tuple(float(value) for value in background_match.groups()),
    }


def read_motif(path: str | Path, *, motif_id: str | None = None) -> MotifModel:
    source = Path(path)
    if source.is_symlink():
        raise InvalidMotif(f"Refusing symbolic-link motif file '{source.name}'.")
    try:
        if source.stat().st_size > MAX_INPUT_BYTES:
            raise InvalidMotif(
                f"Motif file '{source.name}' exceeds the {MAX_INPUT_BYTES}-byte limit."
            )
        raw = source.read_bytes()
    except OSError as exc:
        raise InvalidMotif(f"Unable to read motif file '{source.name}': {exc}") from exc
    if len(raw) > MAX_INPUT_BYTES:
        raise InvalidMotif(f"Motif file '{source.name}' exceeds the {MAX_INPUT_BYTES}-byte limit.")
    if source.suffix.lower() in {".meme", ".txt"}:
        payload = _read_meme(raw.decode(), requested_id=motif_id)
    else:
        payload = _read_structured(source, raw)
        if motif_id is not None:
            existing = payload.get("motif_id")
            if existing is not None and existing != motif_id:
                raise InvalidMotif(
                    f"Requested motif id '{motif_id}' does not match file id '{existing}'."
                )
            payload["motif_id"] = motif_id
    payload["source_digest"] = hashlib.sha256(raw).hexdigest()
    payload["source_name"] = source.name
    try:
        return MotifModel.model_validate(payload)
    except ValueError as exc:
        raise InvalidMotif(f"Invalid motif model in '{source.name}': {exc}") from exc
