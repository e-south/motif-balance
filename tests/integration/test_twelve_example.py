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


def test_prepared_example_records_source_and_target_backgrounds(tmp_path, monkeypatch):
    import hashlib
    import io
    import json
    from zipfile import ZipFile

    from motif_balance import MotifModel

    path = Path(__file__).resolve().parents[2] / "examples/twelve-motifs/prepare_inputs.py"
    spec = importlib.util.spec_from_file_location("twelve_preparation", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    raw = (
        b"Background letter frequencies\nA 0.3 C 0.2 G 0.2 T 0.3\n"
        b"letter-probability matrix: alength= 4 w= 1\n0.7 0.1 0.1 0.1\n"
    )
    archive = io.BytesIO()
    with ZipFile(archive, "w") as zipped:
        zipped.writestr("motif.txt", raw)
    data = archive.getvalue()
    expected = MotifModel(
        motif_id="fixture",
        probabilities=(module.canonical_row([(v + 0.025) / 1.1 for v in (0.7, 0.1, 0.1, 0.1)]),),
        background=(0.25,) * 4,
    )
    (tmp_path / "SOURCE.json").write_text(
        json.dumps(
            {
                "url": "https://example.invalid/fixture.zip",
                "archive_sha256": hashlib.sha256(data).hexdigest(),
                "profiles": [
                    {
                        "archive_member": "motif.txt",
                        "record": "fixture",
                        "width": 1,
                        "original_sha256": hashlib.sha256(raw).hexdigest(),
                        "prepared_model_digest": expected.model_digest,
                    }
                ],
            }
        )
    )
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "urlopen", lambda *a, **kw: io.BytesIO(data))
    module.prepare(tmp_path / "output")
    model = MotifModel.model_validate_json((tmp_path / "output/motifs/fixture.json").read_text())
    assert model.model_digest == expected.model_digest
    assert model.conversion is not None
    assert model.conversion.prior_weight == 0.1
    assert model.conversion.source_background == (0.3, 0.2, 0.2, 0.3)
    assert model.conversion.target_background == (0.25,) * 4
