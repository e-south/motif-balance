"""Download the pinned probability records and prepare the twelve example models."""

import argparse
import hashlib
import io
import json
import math
import re
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile

from motif_balance import MotifModel

ROOT = Path(__file__).resolve().parent
MAX_BYTES = 32 * 1024 * 1024


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


def prepare(destination: Path) -> None:
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"Choose a new input directory: {destination}")
    provenance = json.loads((ROOT / "SOURCE.json").read_text())
    with urlopen(provenance["url"], timeout=60) as response:
        archive = response.read(MAX_BYTES + 1)
    if (
        len(archive) > MAX_BYTES
        or hashlib.sha256(archive).hexdigest() != provenance["archive_sha256"]
    ):
        raise ValueError("Publisher archive differs from the pinned source")
    outputs = {}
    with ZipFile(io.BytesIO(archive)) as zipped:
        for profile in provenance["profiles"]:
            raw = zipped.read(profile["archive_member"])
            if hashlib.sha256(raw).hexdigest() != profile["original_sha256"]:
                raise ValueError("Source record differs from its checksum")
            text = raw.decode()
            header = re.search(r"letter-probability matrix:.*?w=\s*(\d+).*?\n", text)
            if header is None or int(header[1]) != profile["width"]:
                raise ValueError("Unexpected motif width")
            rows = [
                list(map(float, line.split()))
                for line in text[header.end() :].splitlines()[: profile["width"]]
            ]
            prepared = [[(v / math.fsum(row) + 0.025) / 1.1 for v in row] for row in rows]
            probabilities = tuple(canonical_row(row) for row in prepared)
            model = MotifModel(
                motif_id=profile["record"],
                probabilities=probabilities,
                background=(0.25,) * 4,
                source_name=profile["record"] + ".txt",
                source_digest=profile["original_sha256"],
            )
            if model.model_digest != profile["prepared_model_digest"]:
                raise ValueError("Prepared model differs from the declared conversion")
            outputs[f"source/{profile['record']}.txt"] = raw
            outputs[f"motifs/{profile['record']}.json"] = (
                model.model_dump_json(indent=2) + "\n"
            ).encode()
    destination.mkdir(parents=True, exist_ok=False)
    for relative, content in outputs.items():
        target = destination / relative
        target.parent.mkdir(exist_ok=True)
        with target.open("xb") as stream:
            stream.write(content)
    print(f"Prepared {len(provenance['profiles'])} models in {destination}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "inputs")
    prepare(parser.parse_args().out)
