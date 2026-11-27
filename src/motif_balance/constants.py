"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/constants.py

Define shared schema identities, search versions, and bounded resource limits.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import hashlib
import tomllib
from importlib.resources import files
from pathlib import Path
from typing import Final, Literal

# Exact model-only joint assessment bounds, checked before compiling columns.
MAX_JOINT_ASSESSMENT_MOTIFS: Final = 4
MAX_JOINT_ASSESSMENT_ARRANGEMENTS: Final = 100_000
MAX_JOINT_ASSESSMENT_BASE_OPERATIONS: Final = 20_000_000


def _build_lock_digest() -> str:
    """Identify the reviewed lockfile for this installation or source checkout."""
    packaged = files(__package__).joinpath("uv.lock")
    if packaged.is_file():
        return hashlib.sha256(packaged.read_bytes()).hexdigest()

    package_dir = Path(__file__).resolve().parent
    source_root = package_dir.parent.parent
    metadata = source_root / "pyproject.toml"
    if package_dir.parent.name == "src" and metadata.is_file():
        with metadata.open("rb") as stream:
            if tomllib.load(stream).get("project", {}).get("name") == "motif-balance":
                return hashlib.sha256((source_root / "uv.lock").read_bytes()).hexdigest()
    raise FileNotFoundError("The motif-balance installation is missing its build lockfile.")


PACKAGE_VERSION: Final = "0.9.3"
RUNTIME_CONTRACT: Final = "python>=3.12,<3.15"
BUILD_LOCK_SHA256: Final = _build_lock_digest()
MAX_INPUT_BYTES: Final = 1_000_000
MAX_RUN_MANIFEST_BYTES: Final = 64 * 1024 * 1024
MAX_SEARCH_OBSERVATION_BYTES: Final = 64 * 1024 * 1024
MAX_BUNDLE_ARTIFACT_BYTES: Final = 100_000_000
MAX_BUNDLE_ROWS: Final = 1_000_000
MAX_SEQUENCE_LENGTH: Final = 10_000
MAX_CANDIDATE_COUNT: Final = 100_000
MAX_EVALUATIONS: Final = 100_000
MAX_SINGLE_OUTPUT_EVALUATIONS: Final = 1_000_000
MAX_PORTFOLIO_BASES: Final = 10_000_000
MAX_EVALUATED_BASES: Final = 25_000_000
MAX_SINGLE_OUTPUT_EVALUATED_BASES: Final = 50_000_000
MAX_SCORE_BASE_OPERATIONS: Final = 100_000_000
MAX_SINGLE_OUTPUT_SCORE_BASE_OPERATIONS: Final = 15_000_000_000
MAX_DISTANCE_BASE_COMPARISONS: Final = 10_000_000
MAX_PAIR_ASSESSMENT_BASE_OPERATIONS: Final = 10_000_000
MAX_ARCHITECTURE_POOL_RECORDS: Final = 50_000
MAX_ARCHITECTURE_DISTANCE_BASE_BUDGET: Final = 500_000_000
MAX_ARCHITECTURE_DISTANCE_PAIRS: Final = 500_000
MAX_ARCHITECTURE_PREPARED_PAIRS: Final = 250_000
DEFAULT_ELITE_CAPACITY: Final = 256
SCORING_SEMANTICS: Final[Literal["relative_pwm_attainment_v2"]] = "relative_pwm_attainment_v2"
OBJECTIVE_SEMANTICS: Final[Literal["weakest_directional_satisfaction_v1"]] = (
    "weakest_directional_satisfaction_v1"
)
TIE_BREAK_SEMANTICS: Final[Literal["leftmost_plus_first_v1"]] = "leftmost_plus_first_v1"
SEARCH_ENGINE = "annealed_multistart_v1"
INDEPENDENT_SEARCH_ENGINE: Final = "annealed_independent_starts_v1"
GREEDY_SEARCH_ENGINE: Final = "greedy_multistart_v1"
GREEDY_INDEPENDENT_SEARCH_ENGINE: Final = "greedy_independent_starts_v1"
RANDOM_SEARCH_ENGINE: Final = "uniform_random_v1"
SEARCH_ENGINE_VERSION = "2"
RNG_NAME = "PCG64"
DNA_ALPHABET: Final[tuple[Literal["A", "C", "G", "T"], ...]] = ("A", "C", "G", "T")
DNA_COMPLEMENT = str.maketrans("ACGT", "TGCA")
