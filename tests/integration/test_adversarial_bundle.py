from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest
from pydantic import ValidationError

import motif_balance.artifacts as artifacts_module
from motif_balance import DesignSpec, Portfolio, design
from motif_balance.artifacts import (
    artifact_records,
    base_artifact_payloads,
    bundle_id,
    manifest_bytes,
    verify_bundle,
)
from motif_balance.errors import ArtifactError
from motif_balance.model import ArtifactDigest, RunManifest


class _SwappingRename:
    def __init__(self, source: Path, trusted: Path) -> None:
        self.source = source
        self.trusted = trusted
        self.argtypes: object = None
        self.restype: object = None

    def __call__(
        self,
        _source_fd: int,
        source_name: bytes,
        _destination_fd: int,
        destination_name: bytes,
        _flags: int,
    ) -> int:
        parent = self.source.parent
        source = parent / os.fsdecode(source_name)
        destination = parent / os.fsdecode(destination_name)
        if source == self.source:
            source.rename(self.trusted)
            source.mkdir()
        source.rename(destination)
        return 0


class _SwappingLibrary:
    def __init__(self, source: Path, trusted: Path) -> None:
        self.renameatx_np = _SwappingRename(source, trusted)


class _MutatingRename:
    def __init__(self, member: str) -> None:
        self.member = member
        self.mutated = False
        self.argtypes: object = None
        self.restype: object = None

    def __call__(
        self,
        source_fd: int,
        source_name: bytes,
        destination_fd: int,
        destination_name: bytes,
        _flags: int,
    ) -> int:
        directory_fd = os.open(
            source_name,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
            dir_fd=source_fd,
        )
        try:
            if not self.mutated:
                try:
                    member_fd = os.open(self.member, os.O_WRONLY | os.O_TRUNC, dir_fd=directory_fd)
                except FileNotFoundError:
                    pass
                else:
                    try:
                        os.write(member_fd, b"forged during publication\n")
                        self.mutated = True
                    finally:
                        os.close(member_fd)
        finally:
            os.close(directory_fd)
        os.rename(
            source_name,
            destination_name,
            src_dir_fd=source_fd,
            dst_dir_fd=destination_fd,
        )
        return 0


class _MutatingLibrary:
    def __init__(self, member: str) -> None:
        self.renameatx_np = _MutatingRename(member)


def test_bundle_publication_does_not_replace_a_concurrently_created_empty_directory(
    pairwise_spec: DesignSpec,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "result"
    publish = artifacts_module._publish_directory_no_replace

    def create_destination_then_publish(temporary: Path, destination: Path) -> None:
        destination.mkdir()
        publish(temporary, destination)

    monkeypatch.setattr(
        artifacts_module,
        "_publish_directory_no_replace",
        create_destination_then_publish,
    )

    with pytest.raises(ArtifactError, match="already exists or is unsafe"):
        design(pairwise_spec).write(output)

    assert output.is_dir()
    assert list(output.iterdir()) == []
    assert not list(tmp_path.glob(".result.tmp-*"))


def test_directory_publication_rejects_a_swapped_source_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "temporary"
    source.mkdir()
    (source / "trusted.txt").write_text("trusted")
    trusted = tmp_path / "original-temporary"
    destination = tmp_path / "published"
    library = _SwappingLibrary(source, trusted)
    monkeypatch.setattr(artifacts_module.ctypes, "CDLL", lambda *_args, **_kwargs: library)
    monkeypatch.setattr(artifacts_module.sys, "platform", "darwin")

    with pytest.raises(OSError, match=r"changed|identity"):
        artifacts_module._publish_directory_no_replace(source, destination)

    assert trusted.joinpath("trusted.txt").read_text() == "trusted"
    assert not destination.exists()


def test_portfolio_write_rejects_member_mutation_during_publication(
    pairwise_spec: DesignSpec,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "result"
    library = _MutatingLibrary("candidates.tsv")
    monkeypatch.setattr(artifacts_module.ctypes, "CDLL", lambda *_args, **_kwargs: library)
    monkeypatch.setattr(artifacts_module.sys, "platform", "darwin")

    with pytest.raises(ArtifactError, match="post-publication replay"):
        design(pairwise_spec).write(output)

    assert not output.exists()
    quarantines = list(tmp_path.glob(".result.rejected-*"))
    assert len(quarantines) == 1
    assert quarantines[0].joinpath("candidates.tsv").read_bytes() == b"forged during publication\n"


def test_resealed_derived_fasta_still_fails_semantic_replay(
    pairwise_spec: DesignSpec,
    tmp_path: Path,
) -> None:
    output = tmp_path / "result"
    design(pairwise_spec).write(output)
    fasta = output / "candidates.fasta"
    replacement = b">forged\nAAAA\n"
    fasta.write_bytes(replacement)

    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["artifacts"]["candidates.fasta"] = {
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
    payloads = base_artifact_payloads(pairwise_spec, forged_candidates)
    for path, payload in payloads.items():
        (output / path).write_bytes(payload)
    artifacts = artifact_records(payloads)
    manifest = portfolio.manifest.model_copy(update={"artifacts": artifacts})
    manifest = manifest.model_copy(update={"bundle_id": bundle_id(manifest)})
    (output / "manifest.json").write_bytes(manifest_bytes(manifest))

    with pytest.raises(ArtifactError, match="scientific replay"):
        verify_bundle(output)


def test_resealed_best_observed_sequence_fails_authoritative_scoring_replay(
    pairwise_spec: DesignSpec,
    tmp_path: Path,
) -> None:
    portfolio = design(pairwise_spec)
    output = tmp_path / "result"
    portfolio.write(output)
    payload = json.loads((output / "manifest.json").read_bytes())
    payload["best_observed"]["sequence"] = "T" * pairwise_spec.length
    artifacts = tuple(
        ArtifactDigest(path=path, **record) for path, record in sorted(payload["artifacts"].items())
    )
    provisional = RunManifest.model_validate({**payload, "artifacts": artifacts})
    sealed = provisional.model_copy(update={"bundle_id": bundle_id(provisional)})
    (output / "manifest.json").write_bytes(manifest_bytes(sealed))

    with pytest.raises(ArtifactError, match="best observed candidate"):
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
    payloads = base_artifact_payloads(pairwise_spec, forged_candidates)
    provisional = portfolio.manifest.model_copy(update={"artifacts": artifact_records(payloads)})
    forged_manifest = provisional.model_copy(update={"bundle_id": bundle_id(provisional)})
    output = tmp_path / "forged"

    with pytest.raises(ValidationError, match="cannot exceed the best observed score"):
        Portfolio.model_validate(
            {
                **portfolio.model_dump(mode="python"),
                "candidates": forged_candidates,
                "manifest": forged_manifest,
            }
        )
    assert not output.exists()


def test_artifact_records_reject_payloads_the_reader_would_refuse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("motif_balance.artifacts.MAX_BUNDLE_ARTIFACT_BYTES", 4)

    with pytest.raises(ArtifactError, match="bundle byte limit"):
        artifact_records({"oversized.tsv": b"12345"})
