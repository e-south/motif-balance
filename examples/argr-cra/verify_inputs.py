"""
--------------------------------------------------------------------------------
motif-balance
examples/argr-cra/verify_inputs.py

Verify the ArgR and Cra models against their attributed numerical source data.

Module Author(s): Eric J. South
Dunlop Lab
--------------------------------------------------------------------------------
"""

import hashlib
import json
from pathlib import Path

from motif_balance.formats.motif import read_motif


def main() -> None:
    root = Path(__file__).resolve().parent
    source_record = json.loads((root / "SOURCE.json").read_text())
    for profile in source_record["profiles"]:
        source = root / "source" / f"{profile['record']}.json"
        assert hashlib.sha256(source.read_bytes()).hexdigest() == profile["numeric_extract_sha256"]
        numeric = json.loads(source.read_text())
        model = read_motif(root / "motifs" / f"{profile['record']}.json")
        prepared = tuple(
            tuple((value / sum(row) + 0.025) / 1.1 for value in row)
            for row in numeric["probabilities"]
        )
        assert model.probabilities == prepared
        assert model.model_digest == profile["prepared_model_digest"]
        assert model.background == (0.25,) * 4
        assert model.conversion is not None
        assert model.conversion.source_background == tuple(numeric["background"])
        print(f"{model.motif_id}: {model.width} positions, source and preparation verified")


if __name__ == "__main__":
    main()
