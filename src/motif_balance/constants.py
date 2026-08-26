from __future__ import annotations

from typing import Final, Literal

PACKAGE_VERSION: Final = "0.2.0a1"
RUNTIME_CONTRACT: Final = "python>=3.12,<3.15"
BUILD_LOCK_SHA256: Final = "fe7cedacfaf65e12acf6c328f240ea4088494225c8175377dcf496822e12578c"
MAX_INPUT_BYTES: Final = 1_000_000
MAX_BUNDLE_ARTIFACT_BYTES: Final = 100_000_000
MAX_BUNDLE_ROWS: Final = 1_000_000
MAX_SEQUENCE_LENGTH: Final = 10_000
MAX_CANDIDATE_COUNT: Final = 100_000
MAX_EVALUATIONS: Final = 1_000_000
MAX_PORTFOLIO_BASES: Final = 10_000_000
SCORING_SEMANTICS: Final[Literal["normalized_llr_v1"]] = "normalized_llr_v1"
OBJECTIVE_SEMANTICS: Final[Literal["weakest_score_v1"]] = "weakest_score_v1"
TIE_BREAK_SEMANTICS: Final[Literal["leftmost_plus_first_v1"]] = "leftmost_plus_first_v1"
SEARCH_ENGINE = "annealed_multistart_v1"
SEARCH_ENGINE_VERSION = "1"
RNG_NAME = "PCG64"
DNA_ALPHABET: Final[tuple[Literal["A", "C", "G", "T"], ...]] = ("A", "C", "G", "T")
DNA_COMPLEMENT = str.maketrans("ACGT", "TGCA")
