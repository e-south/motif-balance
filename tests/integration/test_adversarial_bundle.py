from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from motif_balance import DesignSpec, Portfolio, design, verify_bundle
from motif_balance.api import _bundle_payloads
from motif_balance.artifacts import artifact_records, bundle_id, manifest_bytes
from motif_balance.errors import ArtifactError
from motif_balance.model import ArtifactDigest, RunManifest


def test_resealed_derived_report_still_fails_semantic_replay(
    pairwise_spec: DesignSpec,
    tmp_path: Path,
) -> None:
    output = tmp_path / "result"
    design(pairwise_spec).write(output)
    report = output / "report.html"
    replacement = b"<html><body>unsupported claim</body></html>\n"
    report.write_bytes(replacement)

    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["artifacts"]["report.html"] = {
        "sha256": hashlib.sha256(replacement).hexdigest(),
        "bytes": len(replacement),
    }
    records = tuple(
        ArtifactDigest(path=path, **record)
        for path, record in sorted(manifest["artifacts"].items())
    )
    manifest_model = RunManifest.model_validate({**manifest, "artifacts": records})
    manifest["bundle_id"] = bundle_id(manifest_model)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    with pytest.raises(ArtifactError, match="semantic replay"):
        verify_bundle(output)


def test_resealed_scientific_scores_fail_authoritative_scoring_replay(
    pairwise_spec: DesignSpec,
    tmp_path: Path,
) -> None:
    portfolio = design(pairwise_spec)
    output = tmp_path / "result"
    portfolio.write(output)
    forged_candidates = tuple(
        candidate.model_copy(
            update={
                "balance_score": 9.0,
                "matches": tuple(
                    match.model_copy(update={"raw_score": 9.0, "normalized_score": 9.0})
                    for match in candidate.matches
                ),
            }
        )
        for candidate in portfolio.candidates
    )
    payloads = _bundle_payloads(pairwise_spec, forged_candidates)
    for path, payload in payloads.items():
        (output / path).write_bytes(payload)
    artifacts = artifact_records(payloads)
    manifest = portfolio.manifest.model_copy(update={"artifacts": artifacts})
    manifest = manifest.model_copy(update={"bundle_id": bundle_id(manifest)})
    (output / "manifest.json").write_bytes(manifest_bytes(manifest))

    with pytest.raises(ArtifactError, match="scientific replay"):
        verify_bundle(output)


def test_publication_rejects_caller_forged_scientific_state(
    pairwise_spec: DesignSpec,
    tmp_path: Path,
) -> None:
    portfolio = design(pairwise_spec)
    forged_candidates = tuple(
        candidate.model_copy(
            update={
                "balance_score": 9.0,
                "matches": tuple(
                    match.model_copy(update={"raw_score": 9.0, "normalized_score": 9.0})
                    for match in candidate.matches
                ),
            }
        )
        for candidate in portfolio.candidates
    )
    payloads = _bundle_payloads(pairwise_spec, forged_candidates)
    provisional = portfolio.manifest.model_copy(update={"artifacts": artifact_records(payloads)})
    forged_manifest = provisional.model_copy(update={"bundle_id": bundle_id(provisional)})
    forged = Portfolio.model_validate(
        {
            **portfolio.model_dump(mode="python"),
            "candidates": forged_candidates,
            "manifest": forged_manifest,
        }
    )
    output = tmp_path / "forged"

    with pytest.raises(ArtifactError, match="scientific replay"):
        forged.write(output)
    assert not output.exists()
