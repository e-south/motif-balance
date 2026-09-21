"""
--------------------------------------------------------------------------------
motif-balance
examples/argr-cra/prepare_inputs.py

Download and verify the publisher's ArgR/Cra records, then prepare local models.

Module Author(s): Eric J. South
Dunlop Lab
--------------------------------------------------------------------------------
"""

import argparse
import hashlib
import io
import json
import re
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile

from motif_balance import MotifModel
from motif_balance.model import MotifConversion

ROOT = Path(__file__).resolve().parent
MAX_ARCHIVE_BYTES = 32 * 1024 * 1024


def prepare(destination: Path) -> None:
    """Fetch pinned data and write a new local input directory."""
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"Choose a new input directory: {destination}")
    provenance = json.loads((ROOT / "SOURCE.json").read_text())
    with urlopen(provenance["url"], timeout=60) as response:  # Fixed publisher HTTPS URL.
        archive = response.read(MAX_ARCHIVE_BYTES + 1)
    if len(archive) > MAX_ARCHIVE_BYTES:
        raise ValueError("Publisher archive exceeds the declared size limit")
    if hashlib.sha256(archive).hexdigest() != provenance["archive_sha256"]:
        raise ValueError("Publisher archive differs from the pinned source")
    outputs = {}
    with ZipFile(io.BytesIO(archive)) as zipped:
        for profile in provenance["profiles"]:
            raw = zipped.read(profile["archive_member"])
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
            numeric = {
                "source_record": profile["record"],
                "background": background,
                "probabilities": rows,
            }
            source_bytes = (json.dumps(numeric, indent=2) + "\n").encode()
            if hashlib.sha256(source_bytes).hexdigest() != profile["numeric_extract_sha256"]:
                raise ValueError("Extracted probabilities differ from the pinned source")
            probabilities = tuple(
                tuple((value / sum(row) + 0.025) / 1.1 for value in row) for row in rows
            )
            model = MotifModel(
                motif_id=profile["protein"],
                probabilities=probabilities,
                background=(0.25,) * 4,
                source_name=profile["record"] + ".json",
                source_digest=profile["numeric_extract_sha256"],
                conversion=MotifConversion(
                    schema_version="motif-conversion/v2",
                    method="probability_matrix_target_background_v1",
                    prior_weight=0.1,
                    source_motif_id=profile["record"],
                    source_background=background,
                    target_background=(0.25,) * 4,
                    target_background_policy="explicit_target_background_v1",
                ),
            )
            if model.model_digest != profile["prepared_model_digest"]:
                raise ValueError("Prepared model differs from the declared conversion")
            outputs[f"source/{profile['record']}.json"] = source_bytes
            outputs[f"motifs/{profile['record']}.json"] = (
                model.model_dump_json(indent=2) + "\n"
            ).encode()
    destination.mkdir(parents=True, exist_ok=False)
    for relative, content in outputs.items():
        target = destination / relative
        target.parent.mkdir(exist_ok=True)
        with target.open("xb") as output:
            output.write(content)
    print(f"Prepared ArgR and Cra profiles in {destination}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare the publisher's ArgR and Cra profiles.")
    parser.add_argument("--out", type=Path, default=ROOT / "inputs")
    args = parser.parse_args()
    prepare(args.out)


if __name__ == "__main__":
    main()
