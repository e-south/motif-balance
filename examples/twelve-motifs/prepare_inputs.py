"""
--------------------------------------------------------------------------------
motif-balance
examples/twelve-motifs/prepare_inputs.py

Prepare publisher inputs for the source-checkout example.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

import argparse
from pathlib import Path

from motif_balance.examples.preparation import prepare_inputs

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepare the example's published motif inputs.")
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "inputs")
    prepare_inputs("twelve-motifs", parser.parse_args().out)
