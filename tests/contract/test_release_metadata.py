from __future__ import annotations

import hashlib
from pathlib import Path

from motif_balance.constants import BUILD_LOCK_SHA256, RUNTIME_CONTRACT


def test_runtime_and_build_lock_contracts_match_repository() -> None:
    root = Path(__file__).resolve().parents[2]

    assert RUNTIME_CONTRACT == "python>=3.12,<3.15"
    assert hashlib.sha256((root / "uv.lock").read_bytes()).hexdigest() == BUILD_LOCK_SHA256
