"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/examples/profiles.py

Prepare the pinned example models without changing their recorded probabilities.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

import hashlib
import io
import json
import math
import re
from pathlib import PurePosixPath
from typing import Any, cast
from zipfile import ZipFile

from motif_balance.model import MotifConversion, MotifModel


def canonical_row(values: list[float]) -> tuple[float, ...]:
    """Resolve binary64 normalization exactly as the recorded preparation did."""
    row = [v / math.fsum(values) for v in values]
    seen = {tuple(row)}
    for _ in range(8):
        replay = [v / math.fsum(row) for v in row]
        if replay == row:
            return tuple(row)
        if tuple(replay) in seen:
            break
        seen.add(tuple(replay))
        row = replay
    row = list(min(seen))
    index = max(range(4), key=lambda i: (row[i], -i))
    row[index] = 1.0 - math.fsum(v for i, v in enumerate(row) if i != index)
    for _ in range(4):
        total = math.fsum(row)
        if total == 1.0:
            return tuple(row)
        row[index] = math.nextafter(row[index], math.inf if total < 1.0 else -math.inf)
    raise ValueError("Probability row does not have a stable representation")


def prepare_profiles(archive: bytes, provenance: dict[str, Any]) -> dict[str, bytes]:
    """Verify only the named, bounded members and preserve each recipe's conversion."""
    outputs: dict[str, bytes] = {}
    with ZipFile(io.BytesIO(archive)) as zipped:
        for profile in provenance["profiles"]:
            record = profile["record"]
            if not record or PurePosixPath(record).name != record or record in (".", ".."):
                raise ValueError("Source record must be a plain filename")
            member = zipped.getinfo(profile["archive_member"])
            if member.file_size > 1024 * 1024:
                raise ValueError("Source motif member exceeds the size limit")
            with zipped.open(member) as stream:
                raw = stream.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024:
                raise ValueError("Source motif member exceeds the size limit")
            if hashlib.sha256(raw).hexdigest() != profile["original_sha256"]:
                raise ValueError("Source record differs from its pinned checksum")
            text = raw.decode()
            header = re.search(r"letter-probability matrix:.*?w=\s*(\d+).*?\n", text)
            if header is None or int(header[1]) != profile["width"]:
                raise ValueError("Source probability matrix has an unexpected width")
            rows = [
                list(map(float, line.split()))
                for line in text[header.end() :].splitlines()[: profile["width"]]
            ]
            match = re.search(
                r"Background letter frequencies[^\n]*\n\s*A\s+([\d.]+)\s+C\s+([\d.]+)"
                r"\s+G\s+([\d.]+)\s+T\s+([\d.]+)",
                text,
            )
            if match is None:
                raise ValueError("Source background is missing")
            background = tuple(map(float, match.groups()))
            if "numeric_extract_sha256" in profile:
                # This pair recipe records the numeric extract as its source.
                numeric = {"source_record": record, "background": background, "probabilities": rows}
                source = (json.dumps(numeric, indent=2) + "\n").encode()
                digest = profile["numeric_extract_sha256"]
                if hashlib.sha256(source).hexdigest() != digest:
                    raise ValueError("Extracted probabilities differ from the pinned source")
                probabilities = tuple(
                    tuple((value / sum(row) + 0.025) / 1.1 for value in row) for row in rows
                )
                suffix = ".json"
            else:
                # Preserve the twelve-model recipe's exact binary64 normalization.
                source, digest, suffix = raw, profile["original_sha256"], ".txt"
                probabilities = tuple(
                    canonical_row([(value / math.fsum(row) + 0.025) / 1.1 for value in row])
                    for row in rows
                )
            model = MotifModel(
                motif_id=profile.get("protein", record),
                probabilities=cast(tuple[tuple[float, float, float, float], ...], probabilities),
                background=(0.25,) * 4,
                source_name=record + suffix,
                source_digest=digest,
                conversion=MotifConversion(
                    schema_version="motif-conversion/v2",
                    method="probability_matrix_target_background_v1",
                    prior_weight=0.1,
                    source_motif_id=record,
                    source_background=cast(tuple[float, float, float, float], background),
                    target_background=(0.25,) * 4,
                    target_background_policy="explicit_target_background_v1",
                ),
            )
            if model.model_digest != profile["prepared_model_digest"]:
                raise ValueError("Prepared model differs from the declared conversion")
            outputs[f"source/{record}{suffix}"] = source
            outputs[f"motifs/{record}.json"] = (model.model_dump_json(indent=2) + "\n").encode()
    return outputs
