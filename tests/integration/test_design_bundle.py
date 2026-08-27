from __future__ import annotations

import json
from pathlib import Path

import pytest

from motif_balance import DesignSpec, design
from motif_balance.artifacts import read_verified_portfolio, verify_bundle
from motif_balance.errors import ArtifactError


def test_synthetic_pairwise_design_is_deterministic_and_writes_canonical_bundle(
    pairwise_spec: DesignSpec,
    tmp_path: Path,
) -> None:
    first = design(pairwise_spec)
    second = design(pairwise_spec)
    assert first == second
    assert len(first.candidates) == pairwise_spec.count
    assert all(len(candidate.sequence) == pairwise_spec.length for candidate in first.candidates)
    assert first.manifest.completion_status == "exhaustive"
    assert not hasattr(first.manifest, "python_version")
    assert not hasattr(first.manifest, "platform")

    output = tmp_path / "result"
    first.write(output)
    assert {path.name for path in output.iterdir()} == {
        "design.json",
        "motifs.json",
        "candidates.tsv",
        "matches.tsv",
        "manifest.json",
        "candidates.fasta",
    }
    assert verify_bundle(output) == first.manifest.bundle_id
    assert (
        verify_bundle(output, expected_bundle_id=first.manifest.bundle_id)
        == first.manifest.bundle_id
    )
    assert read_verified_portfolio(output).model_dump(mode="python") == first.model_dump(
        mode="python"
    )

    with pytest.raises(ArtifactError, match="externally expected"):
        verify_bundle(output, expected_bundle_id="bundle-000000000000000000000000")

    manifest = json.loads((output / "manifest.json").read_text())
    assert set(manifest["artifacts"]) == {
        "candidates.tsv",
        "candidates.fasta",
        "design.json",
        "matches.tsv",
        "motifs.json",
    }


def test_bundle_refuses_overwrite_and_detects_tampering(
    pairwise_spec: DesignSpec,
    tmp_path: Path,
) -> None:
    output = tmp_path / "result"
    portfolio = design(pairwise_spec)
    portfolio.write(output)

    with pytest.raises(ArtifactError, match="already exists"):
        portfolio.write(output)

    (output / "candidates.tsv").write_text("tampered\n")
    with pytest.raises(ArtifactError, match="digest"):
        verify_bundle(output)


def test_manifest_provenance_is_bound_into_bundle_identity(
    pairwise_spec: DesignSpec,
    tmp_path: Path,
) -> None:
    output = tmp_path / "result"
    design(pairwise_spec).write(output)
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["package_version"] = "forged"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    with pytest.raises(ArtifactError, match="bundle identity"):
        verify_bundle(output)
