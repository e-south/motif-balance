from __future__ import annotations

from typing import Final, Literal

PACKAGE_VERSION: Final = "0.4.0a5"
RUNTIME_CONTRACT: Final = "python>=3.12,<3.15"
BUILD_LOCK_SHA256: Final = "30e8b5ac51d87549cbb0b6e88e5f62aa6470bee29093beb0ca5d59e25162b44b"
MAX_INPUT_BYTES: Final = 1_000_000
MAX_BUNDLE_ARTIFACT_BYTES: Final = 100_000_000
MAX_BUNDLE_ROWS: Final = 1_000_000
MAX_SEQUENCE_LENGTH: Final = 10_000
MAX_CANDIDATE_COUNT: Final = 100_000
MAX_EVALUATIONS: Final = 100_000
MAX_PORTFOLIO_BASES: Final = 10_000_000
MAX_EVALUATED_BASES: Final = 25_000_000
MAX_SCORE_BASE_OPERATIONS: Final = 100_000_000
MAX_DISTANCE_BASE_COMPARISONS: Final = 10_000_000
LEGACY_SCORING_SEMANTICS: Final[Literal["normalized_llr_v1"]] = "normalized_llr_v1"
SCORING_SEMANTICS: Final[Literal["relative_pwm_attainment_v2"]] = "relative_pwm_attainment_v2"
OBJECTIVE_SEMANTICS: Final[Literal["weakest_score_v1"]] = "weakest_score_v1"
TIE_BREAK_SEMANTICS: Final[Literal["leftmost_plus_first_v1"]] = "leftmost_plus_first_v1"
SEARCH_ENGINE = "annealed_multistart_v1"
SEARCH_ENGINE_VERSION = "1"
RNG_NAME = "PCG64"
DNA_ALPHABET: Final[tuple[Literal["A", "C", "G", "T"], ...]] = ("A", "C", "G", "T")
DNA_COMPLEMENT = str.maketrans("ACGT", "TGCA")
