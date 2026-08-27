from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from motif_balance import DesignSpec, design
from motif_balance.api import inspect_result, verify_bundle
from motif_balance.artifacts import bundle_id
from motif_balance.constants import MAX_INPUT_BYTES
from motif_balance.errors import ArtifactError
from motif_balance.model import ArtifactDigest, RunManifest


def _reseal(output: Path, changed_path: str) -> None:
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    payload = (output / changed_path).read_bytes()
    manifest["artifacts"][changed_path] = {
        "sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload),
    }
    records = tuple(
        ArtifactDigest(path=path, **record)
        for path, record in sorted(manifest["artifacts"].items())
    )
    manifest_model = RunManifest.model_validate({**manifest, "artifacts": records})
    manifest["bundle_id"] = bundle_id(manifest_model)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


def _bundle(pairwise_spec: DesignSpec, tmp_path: Path, name: str) -> Path:
    output = tmp_path / name
    design(pairwise_spec).write(output)
    return output


def test_verify_rejects_missing_directory(tmp_path: Path) -> None:
    with pytest.raises(ArtifactError, match="does not exist"):
        verify_bundle(tmp_path / "missing")


def test_verify_rejects_a_symlinked_bundle_root(
    pairwise_spec: DesignSpec,
    tmp_path: Path,
) -> None:
    output = _bundle(pairwise_spec, tmp_path, "target")
    link = tmp_path / "linked-bundle"
    link.symlink_to(output, target_is_directory=True)

    with pytest.raises(ArtifactError, match="unsafe"):
        verify_bundle(link)


def test_verify_rejects_inventory_and_unsafe_entries(
    pairwise_spec: DesignSpec,
    tmp_path: Path,
) -> None:
    output = _bundle(pairwise_spec, tmp_path, "inventory")
    (output / "extra.txt").write_text("extra")
    with pytest.raises(ArtifactError, match="inventory"):
        verify_bundle(output)

    (output / "extra.txt").unlink()
    (output / "unsafe").mkdir()
    with pytest.raises(ArtifactError, match="unsafe"):
        verify_bundle(output)


def test_verify_rejects_malformed_manifest_artifacts(
    pairwise_spec: DesignSpec,
    tmp_path: Path,
) -> None:
    output = _bundle(pairwise_spec, tmp_path, "manifest")
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["artifacts"] = []
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ArtifactError, match="path-keyed"):
        verify_bundle(output)

    output = _bundle(pairwise_spec, tmp_path, "record")
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["artifacts"]["candidates.fasta"] = "invalid"
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ArtifactError, match="malformed"):
        verify_bundle(output)


@pytest.mark.parametrize("payload", ["not json", "[]"])
def test_verify_rejects_invalid_json(
    pairwise_spec: DesignSpec,
    tmp_path: Path,
    payload: str,
) -> None:
    name = hashlib.sha256(payload.encode()).hexdigest()[:8]
    output = _bundle(pairwise_spec, tmp_path, name)
    (output / "manifest.json").write_text(payload)
    with pytest.raises(ArtifactError, match="canonical JSON"):
        verify_bundle(output)


def test_verify_rejects_resealed_motif_and_design_identity_drift(
    pairwise_spec: DesignSpec,
    tmp_path: Path,
) -> None:
    output = _bundle(pairwise_spec, tmp_path, "motif")
    motif_path = output / "motifs.json"
    motifs = json.loads(motif_path.read_text())
    motifs["motifs"][0]["model_digest"] = "0" * 64
    motif_path.write_text(json.dumps(motifs, indent=2, sort_keys=True) + "\n")
    _reseal(output, "motifs.json")
    with pytest.raises(ArtifactError, match="model digest"):
        verify_bundle(output)

    output = _bundle(pairwise_spec, tmp_path, "design")
    design_path = output / "design.json"
    design_payload = json.loads(design_path.read_text())
    design_payload["motifs"] = "invalid"
    design_path.write_text(json.dumps(design_payload, indent=2, sort_keys=True) + "\n")
    _reseal(output, "design.json")
    with pytest.raises(ArtifactError, match="motifs must be a list"):
        verify_bundle(output)


def test_verify_rejects_resealed_table_join_drift(
    pairwise_spec: DesignSpec,
    tmp_path: Path,
) -> None:
    output = _bundle(pairwise_spec, tmp_path, "table")
    candidates_path = output / "candidates.tsv"
    lines = candidates_path.read_text().splitlines()
    fields = lines[1].split("\t")
    fields[3] = "99"
    lines[1] = "\t".join(fields)
    candidates_path.write_text("\n".join(lines) + "\n")
    _reseal(output, "candidates.tsv")
    with pytest.raises(ArtifactError, match="length mismatch"):
        verify_bundle(output)


def test_verify_rejects_manifest_inventory_and_bundle_identity_drift(
    pairwise_spec: DesignSpec,
    tmp_path: Path,
) -> None:
    output = _bundle(pairwise_spec, tmp_path, "declared")
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["artifacts"].pop("candidates.fasta")
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ArtifactError, match="inventory is incomplete"):
        verify_bundle(output)

    output = _bundle(pairwise_spec, tmp_path, "identity")
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["bundle_id"] = "bundle-000000000000000000000000"
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ArtifactError, match="bundle identity"):
        verify_bundle(output)


def test_verify_rejects_noncanonical_and_oversized_manifest_bytes(
    pairwise_spec: DesignSpec,
    tmp_path: Path,
) -> None:
    output = _bundle(pairwise_spec, tmp_path, "noncanonical")
    manifest_path = output / "manifest.json"
    trusted_id = json.loads(manifest_path.read_text())["bundle_id"]
    manifest_path.write_bytes(manifest_path.read_bytes() + b" ")
    with pytest.raises(ArtifactError, match="canonical encoding"):
        verify_bundle(output, expected_bundle_id=trusted_id)


@pytest.mark.parametrize("json_name", ["design.json", "motifs.json"])
def test_public_inspection_rejects_oversized_canonical_json_before_parsing(
    pairwise_spec: DesignSpec,
    tmp_path: Path,
    json_name: str,
) -> None:
    output = _bundle(pairwise_spec, tmp_path, json_name.removesuffix(".json"))
    target = output / json_name
    target.write_bytes(target.read_bytes() + b" " * MAX_INPUT_BYTES)
    _reseal(output, json_name)

    with pytest.raises(ArtifactError, match=rf"{json_name}.*{MAX_INPUT_BYTES}-byte limit"):
        inspect_result(output, kind="bundle")

    output = _bundle(pairwise_spec, tmp_path, "oversized")
    manifest_path = output / "manifest.json"
    trusted_id = json.loads(manifest_path.read_text())["bundle_id"]
    manifest_path.write_bytes(manifest_path.read_bytes() + b" " * 2_000_000)
    with pytest.raises(ArtifactError, match="byte limit"):
        verify_bundle(output, expected_bundle_id=trusted_id)


@pytest.mark.parametrize("table_name", ["candidates.tsv", "matches.tsv"])
def test_verify_enforces_semantic_table_row_limits_before_materialization(
    pairwise_spec: DesignSpec,
    tmp_path: Path,
    table_name: str,
) -> None:
    output = _bundle(pairwise_spec, tmp_path, table_name.removesuffix(".tsv"))
    table = output / table_name
    lines = table.read_text().splitlines()
    table.write_text("\n".join([*lines, lines[-1]]) + "\n")
    _reseal(output, table_name)

    with pytest.raises(ArtifactError, match="row limit"):
        verify_bundle(output)
