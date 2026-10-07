"""
--------------------------------------------------------------------------------
motif-balance
tests/contract/test_release_metadata.py

Verify release metadata behavior.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import hashlib
import tomllib
from pathlib import Path

import yaml

from motif_balance.constants import BUILD_LOCK_SHA256, PACKAGE_VERSION, RUNTIME_CONTRACT


def test_package_and_project_identify_the_current_release() -> None:
    root = Path(__file__).resolve().parents[2]
    project = tomllib.loads((root / "pyproject.toml").read_text())["project"]

    assert PACKAGE_VERSION == project["version"] == "0.9.2"


def test_runtime_and_build_lock_contracts_match_repository() -> None:
    root = Path(__file__).resolve().parents[2]

    assert RUNTIME_CONTRACT == "python>=3.12,<3.15"
    assert hashlib.sha256((root / "uv.lock").read_bytes()).hexdigest() == BUILD_LOCK_SHA256


def test_software_citation_identifies_the_same_release() -> None:
    root = Path(__file__).resolve().parents[2]
    citation = yaml.safe_load((root / "CITATION.cff").read_text())

    assert citation["type"] == "software"
    assert citation["version"] == PACKAGE_VERSION
    assert citation["license"] == "MIT"
    assert citation["repository-code"] == "https://github.com/e-south/motif-balance"
    assert citation["authors"] == [{"family-names": "South", "given-names": "Eric J."}]
