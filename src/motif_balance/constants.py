from __future__ import annotations

from typing import Final, Literal

PACKAGE_VERSION: Final = "0.5.0a2"
RUNTIME_CONTRACT: Final = "python>=3.12,<3.15"
BUILD_LOCK_SHA256: Final = "6c235bc5be9d8d6d9b0b17e0706ba507a0d819a2fd7a9a7eb276e3c987dab136"
MAX_INPUT_BYTES: Final = 1_000_000
MAX_RUN_MANIFEST_BYTES: Final = 64 * 1024 * 1024
MAX_SEARCH_OBSERVATION_BYTES: Final = 64 * 1024 * 1024
MAX_BUNDLE_ARTIFACT_BYTES: Final = 100_000_000
MAX_BUNDLE_ROWS: Final = 1_000_000
MAX_SEQUENCE_LENGTH: Final = 10_000
MAX_CANDIDATE_COUNT: Final = 100_000
MAX_EVALUATIONS: Final = 100_000
MAX_PORTFOLIO_BASES: Final = 10_000_000
MAX_EVALUATED_BASES: Final = 25_000_000
MAX_SCORE_BASE_OPERATIONS: Final = 100_000_000
MAX_DISTANCE_BASE_COMPARISONS: Final = 10_000_000
MAX_PAIR_ASSESSMENT_BASE_OPERATIONS: Final = 10_000_000
MAX_ARCHITECTURE_POOL_RECORDS: Final = 50_000
MAX_ARCHITECTURE_DISTANCE_BASE_BUDGET: Final = 500_000_000
MAX_ARCHITECTURE_DISTANCE_PAIRS: Final = 500_000
MAX_ARCHITECTURE_PREPARED_PAIRS: Final = 250_000
DEFAULT_ELITE_CAPACITY: Final = 256
LEGACY_SCORING_SEMANTICS: Final[Literal["normalized_llr_v1"]] = "normalized_llr_v1"
SCORING_SEMANTICS: Final[Literal["relative_pwm_attainment_v2"]] = "relative_pwm_attainment_v2"
OBJECTIVE_SEMANTICS: Final[Literal["weakest_score_v1"]] = "weakest_score_v1"
DIRECTIONAL_OBJECTIVE_SEMANTICS: Final[Literal["weakest_directional_satisfaction_v1"]] = (
    "weakest_directional_satisfaction_v1"
)
TIE_BREAK_SEMANTICS: Final[Literal["leftmost_plus_first_v1"]] = "leftmost_plus_first_v1"
SEARCH_ENGINE = "annealed_multistart_v1"
INDEPENDENT_SEARCH_ENGINE: Final = "annealed_independent_starts_v1"
GREEDY_SEARCH_ENGINE: Final = "greedy_multistart_v1"
GREEDY_INDEPENDENT_SEARCH_ENGINE: Final = "greedy_independent_starts_v1"
RANDOM_SEARCH_ENGINE: Final = "uniform_random_v1"
SEARCH_ENGINE_VERSION = "1"
RNG_NAME = "PCG64"
DNA_ALPHABET: Final[tuple[Literal["A", "C", "G", "T"], ...]] = ("A", "C", "G", "T")
DNA_COMPLEMENT = str.maketrans("ACGT", "TGCA")
