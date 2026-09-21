from __future__ import annotations

import hashlib
import tomllib
from pathlib import Path

from motif_balance.constants import BUILD_LOCK_SHA256, PACKAGE_VERSION, RUNTIME_CONTRACT


def test_directional_only_contract_has_a_distinct_prerelease_identity() -> None:
    root = Path(__file__).resolve().parents[2]
    project = tomllib.loads((root / "pyproject.toml").read_text())["project"]

    assert PACKAGE_VERSION == project["version"] == "0.6.0a1"


def test_runtime_and_build_lock_contracts_match_repository() -> None:
    root = Path(__file__).resolve().parents[2]

    assert RUNTIME_CONTRACT == "python>=3.12,<3.15"
    assert hashlib.sha256((root / "uv.lock").read_bytes()).hexdigest() == BUILD_LOCK_SHA256
