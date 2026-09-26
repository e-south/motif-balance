"""
--------------------------------------------------------------------------------
motif-balance
tests/integration/test_twelve_example.py

Example replay admits its declared package before starting an expensive search.

Module Author(s): Eric J. South
Dunlop Lab
--------------------------------------------------------------------------------
"""

import importlib.util
from pathlib import Path

import pytest

from motif_balance.constants import PACKAGE_VERSION


def test_example_checks_replay_version_without_rewriting_original_producer():
    path = Path(__file__).resolve().parents[2] / "examples/twelve-motifs/reproduce.py"
    spec = importlib.util.spec_from_file_location("twelve_example", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    expected = {"producer": "motif-balance 0.6.0a2", "replay_package_version": PACKAGE_VERSION}
    module.verify_replay_version(expected)
    expected["replay_package_version"] = "0.0.0"
    with pytest.raises(ValueError, match="replay package"):
        module.verify_replay_version(expected)
