"""
--------------------------------------------------------------------------------
motif-balance
tests/conftest.py

Provide shared motif and request fixtures for tests.

Module Author(s): Eric J. South
Dunlop Lab
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from motif_balance import DesignSpec, MotifModel, MotifSpecification


@pytest.fixture
def motif_a() -> MotifModel:
    return MotifModel(
        motif_id="motif_a",
        probabilities=((0.7, 0.1, 0.1, 0.1), (0.1, 0.7, 0.1, 0.1)),
        background=(0.25, 0.25, 0.25, 0.25),
    )


@pytest.fixture
def motif_b() -> MotifModel:
    return MotifModel(
        motif_id="motif_b",
        probabilities=((0.1, 0.1, 0.7, 0.1), (0.1, 0.1, 0.1, 0.7)),
        background=(0.25, 0.25, 0.25, 0.25),
    )


@pytest.fixture
def pairwise_spec(motif_a: MotifModel, motif_b: MotifModel) -> DesignSpec:
    return DesignSpec(
        specifications=(
            MotifSpecification(motif=motif_a, direction="seek"),
            MotifSpecification(motif=motif_b, direction="seek"),
        ),
        length=4,
        count=3,
        strands="both",
        evaluations=256,
        seed=7,
        min_distance=0.25,
    )


@pytest.fixture(scope="session")
def argr_cra_example(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Prepare real tutorial inputs once from their checksum-pinned publisher archive."""
    source = Path(__file__).resolve().parents[1] / "examples/argr-cra"
    destination = tmp_path_factory.mktemp("real-motifs") / "argr-cra"
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns("inputs", "__pycache__"))
    subprocess.run(
        [sys.executable, str(destination / "prepare_inputs.py")],
        check=True,
        capture_output=True,
        text=True,
        timeout=90,
    )
    return destination
