from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

import yaml

from motif_balance.constants import MAX_INPUT_BYTES
from motif_balance.errors import InvalidMotif
from motif_balance.formats.structured import load_json_unique, load_yaml_unique
from motif_balance.model import MotifConversion, MotifModel


def _read_structured(path: Path, raw: bytes) -> dict[str, Any]:
    try:
        payload = load_json_unique(raw) if path.suffix.lower() == ".json" else load_yaml_unique(raw)
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
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise InvalidMotif(f"MEME motif '{source.name}' must be UTF-8 text.") from exc
        payload = _read_meme(text, requested_id=motif_id)
    else:
        payload = _read_structured(source, raw)
        if motif_id is not None:
            existing = payload.get("motif_id")
            if existing is not None and existing != motif_id:
                raise InvalidMotif(
                    f"Requested motif id '{motif_id}' does not match file id '{existing}'."
                )
            payload["motif_id"] = motif_id
    raw_digest = hashlib.sha256(raw).hexdigest()
    payload.setdefault("source_digest", raw_digest)
    payload.setdefault("source_name", source.name)
    payload["canonical_file_digest"] = raw_digest
    payload["canonical_file_name"] = source.name
    try:
        return MotifModel.model_validate(payload)
    except ValueError as exc:
        raise InvalidMotif(f"Invalid motif model in '{source.name}': {exc}") from exc


def convert_jaspar(
    path: str | Path,
    *,
    motif_id: str,
    background: tuple[float, float, float, float],
    prior_weight: float,
) -> MotifModel:
    """Explicitly convert one JASPAR count matrix into a canonical model."""

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
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InvalidMotif(f"JASPAR motif '{source.name}' must be UTF-8 text.") from exc
    header = re.search(r"^>(\S+)(?:\s+.*)?$", text, flags=re.MULTILINE)
    if header is None:
        raise InvalidMotif("JASPAR motif must contain one explicit '>identifier' header.")
    source_motif_id = header.group(1)
    base_rows: dict[str, tuple[float, ...]] = {}
    for base, values in re.findall(r"^\s*([ACGT])\s*\[([^\]]+)\]\s*$", text, re.MULTILINE):
        if base in base_rows:
            raise InvalidMotif(f"JASPAR motif repeats the '{base}' count row.")
        try:
            row = tuple(float(value) for value in values.split())
        except ValueError as exc:
            raise InvalidMotif(f"JASPAR '{base}' row contains a nonnumeric count.") from exc
        if not row or any(not math.isfinite(value) or value < 0.0 for value in row):
            raise InvalidMotif(f"JASPAR '{base}' row must contain finite nonnegative counts.")
        base_rows[base] = row
    if set(base_rows) != set("ACGT"):
        missing = sorted(set("ACGT") - set(base_rows))
        raise InvalidMotif(f"JASPAR motif is missing count rows: {missing}.")
    widths = {len(row) for row in base_rows.values()}
    if len(widths) != 1:
        raise InvalidMotif("JASPAR count rows must have equal widths.")
    try:
        conversion = MotifConversion(
            method="jaspar_counts_to_probabilities_v1",
            prior_weight=prior_weight,
            source_motif_id=source_motif_id,
        )
        validated_background = MotifModel(
            motif_id=motif_id,
            probabilities=((0.25, 0.25, 0.25, 0.25),),
            background=background,
        ).background
    except ValueError as exc:
        raise InvalidMotif(f"Invalid explicit conversion parameters: {exc}") from exc
    rows: list[tuple[float, float, float, float]] = []
    for position in range(widths.pop()):
        counts = tuple(base_rows[base][position] for base in "ACGT")
        total = sum(counts)
        if total <= 0.0:
            raise InvalidMotif(f"JASPAR position {position} has zero total count.")
        observed = tuple(value / total for value in counts)
        denominator = 1.0 + prior_weight
        converted = tuple(
            (value + prior_weight * validated_background[index]) / denominator
            for index, value in enumerate(observed)
        )
        rows.append((converted[0], converted[1], converted[2], converted[3]))
    try:
        return MotifModel(
            motif_id=motif_id,
            probabilities=tuple(rows),
            background=validated_background,
            source_digest=hashlib.sha256(raw).hexdigest(),
            source_name=source.name,
            conversion=conversion,
        )
    except ValueError as exc:
        raise InvalidMotif(f"Converted motif is invalid: {exc}") from exc
