"""
--------------------------------------------------------------------------------
motif-balance
tests/contract/test_example_preparation.py

Installed examples produce editable requests from checked, cached source data.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from motif_balance.cli import app


def test_example_command_rejects_existing_destination_before_download(tmp_path: Path):
    destination = tmp_path / "existing"
    destination.mkdir()
    sentinel = destination / "keep.txt"
    sentinel.write_text("unchanged")
    result = CliRunner().invoke(app, ["example", "argr-cra", "--out", str(destination)])
    assert result.exit_code != 0
    assert "already exists" in result.output.lower()
    assert "No such command" not in result.output
    assert sentinel.read_text() == "unchanged"


def test_example_command_names_available_recipes():
    result = CliRunner().invoke(app, ["example", "--help"])
    assert result.exit_code == 0
    assert "argr-cra" in result.output
    assert "twelve-motifs" in result.output


def test_cached_example_writes_editable_inputs_and_checks_cache(tmp_path, monkeypatch):
    import hashlib
    import io
    import json
    from zipfile import ZipFile

    from motif_balance import MotifModel
    from motif_balance.examples import preparation, prepare_example
    from motif_balance.examples.profiles import canonical_row
    from motif_balance.formats.design import load_design_spec

    raw = (
        b"Background letter frequencies\nA 0.3 C 0.2 G 0.2 T 0.3\n"
        b"letter-probability matrix: alength= 4 w= 1\n0.7 0.1 0.1 0.1\n"
    )
    stream = io.BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr("motif.txt", raw)
    archive_bytes = stream.getvalue()
    digest = hashlib.sha256(archive_bytes).hexdigest()
    model = MotifModel(
        motif_id="fixture",
        background=(0.25,) * 4,
        probabilities=(canonical_row([(v + 0.025) / 1.1 for v in (0.7, 0.1, 0.1, 0.1)]),),
    )
    source = {
        "url": "https://example.invalid/motifs.zip",
        "archive_sha256": digest,
        "profiles": [
            {
                "archive_member": "motif.txt",
                "record": "fixture",
                "width": 1,
                "original_sha256": hashlib.sha256(raw).hexdigest(),
                "prepared_model_digest": model.model_digest,
            }
        ],
    }
    request = (
        "schema_version: design-spec/v3\nlength: 2\ncount: 1\n"
        "evaluations: 64\nseed: 7\nspecifications:\n"
        "  - motif: inputs/motifs/fixture.json\n    direction: seek\n"
    )
    monkeypatch.setattr(preparation, "recipe", lambda name: (source, request.encode()))
    downloads = []

    def download(url, timeout):
        downloads.append(url)
        return io.BytesIO(archive_bytes)

    monkeypatch.setattr("motif_balance.examples.download.urlopen", download)
    cache = tmp_path / "cache"
    prepare_example("twelve-motifs", tmp_path / "first", cache=cache)
    prepare_example("twelve-motifs", tmp_path / "second", cache=cache)
    assert len(downloads) == 1
    spec = load_design_spec(tmp_path / "second/design.yaml")
    assert spec.specifications[0].motif.model_digest == model.model_digest
    conversion = spec.specifications[0].motif.conversion
    assert conversion.source_background == (0.3, 0.2, 0.2, 0.3)
    assert conversion.target_background == (0.25,) * 4
    assert conversion.prior_weight == 0.1
    assert json.loads((tmp_path / "second/SOURCE.json").read_text()) == source
    (cache / f"{digest}.zip").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="checksum"):
        prepare_example("twelve-motifs", tmp_path / "third", cache=cache)
    assert not (tmp_path / "third").exists()
    assert len(downloads) == 1


@pytest.mark.parametrize(
    "payload, zip_signature",
    [(b"<html>Unavailable</html>", False), (b"PK\x03\x04changed archive", True)],
)
def test_download_checksum_error_identifies_the_received_bytes(
    tmp_path, monkeypatch, payload, zip_signature
):
    import hashlib
    import io

    from motif_balance.examples import download

    monkeypatch.setattr(download, "urlopen", lambda url, timeout: io.BytesIO(payload))
    cache = tmp_path / "cache"
    with pytest.raises(ValueError) as error:
        download.archive_bytes("https://example.invalid/motifs.zip", "0" * 64, cache)

    message = str(error.value)
    assert "checksum differs from the source record" in message
    assert f"received {len(payload)} bytes" in message
    assert f"sha256={hashlib.sha256(payload).hexdigest()}" in message
    assert f"zip_signature={zip_signature}" in message
    assert not cache.exists()
