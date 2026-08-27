from __future__ import annotations

import importlib
import json
import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from motif_balance import DesignSpec, design
from motif_balance.api import build_result_catalog, inspect_result
from motif_balance.artifacts import read_bundle_snapshot
from motif_balance.errors import ArtifactError
from motif_balance.inspection import (
    CatalogEntry,
    DeliveryInspection,
    DistanceInspection,
    IntegrityInspection,
    ResultCatalog,
    ResultInspection,
    VerifiedResultSource,
    project_result,
    render_catalog_html,
    render_html,
)
from motif_balance.inspection.project import _distance_inspection


def test_bundle_inspection_replays_every_product_plane(
    tmp_path: Path,
    pairwise_spec: DesignSpec,
) -> None:
    bundle = tmp_path / "bundle"
    portfolio = design(pairwise_spec)
    portfolio.write(bundle)

    inspection = inspect_result(bundle, kind="bundle")

    assert isinstance(inspection, ResultInspection)
    assert inspection.integrity.state == "self_consistent"
    assert inspection.problem.problem_id == portfolio.problem_id
    assert inspection.run.bundle_id == portfolio.manifest.bundle_id
    assert inspection.delivery.delivered_count == pairwise_spec.count
    assert inspection.portfolio.distance.status == "exact"
    assert inspection.portfolio.distance.actual_min_distance == pairwise_spec.min_distance
    assert {artifact.path for artifact in inspection.artifacts} == {
        "candidates.fasta",
        "candidates.tsv",
        "design.json",
        "manifest.json",
        "matches.tsv",
        "motifs.json",
    }
    html = render_html(inspection).decode()
    assert portfolio.manifest.bundle_id in html
    assert "Provenance and integrity" in html
    assert "Exact records" in html
    assert str(tmp_path) not in html
    assert "https://" not in html
    assert "<script" not in html


def test_external_bundle_identity_is_a_distinct_integrity_state(
    tmp_path: Path,
    pairwise_spec: DesignSpec,
) -> None:
    bundle = tmp_path / "bundle"
    portfolio = design(pairwise_spec)
    portfolio.write(bundle)

    inspection = inspect_result(
        bundle,
        kind="bundle",
        expected_bundle_id=portfolio.manifest.bundle_id,
    )

    assert inspection.integrity.state == "externally_verified"
    assert inspection.integrity.trust_basis == "external_bundle_id"
    assert inspection.integrity.checked_identities == ("bundle_id",)


def test_projection_consumes_only_the_frozen_bundle_snapshot(
    tmp_path: Path,
    pairwise_spec: DesignSpec,
) -> None:
    bundle = tmp_path / "bundle"
    design(pairwise_spec).write(bundle)
    snapshot = read_bundle_snapshot(bundle)
    (bundle / "candidates.fasta").write_text("changed after verification")

    source = VerifiedResultSource(
        portfolio=snapshot.portfolio,
        canonical_manifest=snapshot.payload("manifest.json"),
        artifacts=tuple(
            (record, snapshot.payload(record.path))
            for record in snapshot.portfolio.manifest.artifacts
        ),
        subject_kind="bundle",
        integrity_state="self_consistent",
        trust_basis="self_consistent",
        checked_identities=(),
    )
    inspection = project_result(source)
    fasta = next(item for item in inspection.artifacts if item.path == "candidates.fasta")
    assert fasta.bytes == len(snapshot.payload("candidates.fasta"))


def test_public_inspection_never_uses_path_read_bytes_after_snapshot(
    tmp_path: Path,
    pairwise_spec: DesignSpec,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = tmp_path / "bundle"
    design(pairwise_spec).write(bundle)

    def reject_path_read(_path: Path) -> bytes:
        raise RuntimeError("UNBOUNDED_PATH_READ_REACHED")

    monkeypatch.setattr(Path, "read_bytes", reject_path_read)
    inspection = inspect_result(bundle, kind="bundle")
    assert inspection.delivery.status == "complete"


@pytest.mark.parametrize("substitution", ["inode", "symlink"])
def test_public_inspection_rejects_member_substitution_during_snapshot(
    tmp_path: Path,
    pairwise_spec: DesignSpec,
    monkeypatch: pytest.MonkeyPatch,
    substitution: str,
) -> None:
    bundle = tmp_path / "bundle"
    design(pairwise_spec).write(bundle)
    artifacts_module = importlib.import_module("motif_balance.artifacts")
    real_open = os.open
    changed = False

    def substitute_then_open(
        file: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        *args: object,
        **kwargs: object,
    ) -> int:
        nonlocal changed
        if file == "candidates.tsv" and not changed:
            changed = True
            target = bundle / "candidates.tsv"
            original = bundle / "candidates-original.tsv"
            target.rename(original)
            if substitution == "symlink":
                target.symlink_to(original.name)
            else:
                target.write_bytes(original.read_bytes())
        return real_open(file, flags, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(artifacts_module.os, "open", substitute_then_open)
    with pytest.raises(ArtifactError, match=r"unsafe|changed during bundle snapshot"):
        inspect_result(bundle, kind="bundle")


def test_public_inspection_rejects_member_growth_during_snapshot(
    tmp_path: Path,
    pairwise_spec: DesignSpec,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = tmp_path / "bundle"
    design(pairwise_spec).write(bundle)
    artifacts_module = importlib.import_module("motif_balance.artifacts")
    target = bundle / "candidates.tsv"
    target_inode = target.stat().st_ino
    real_read = os.read
    changed = False

    def grow_then_read(descriptor: int, size: int) -> bytes:
        nonlocal changed
        if os.fstat(descriptor).st_ino == target_inode and not changed:
            changed = True
            with target.open("ab") as handle:
                handle.write(b"x")
        return real_read(descriptor, size)

    monkeypatch.setattr(artifacts_module.os, "read", grow_then_read)
    with pytest.raises(ArtifactError, match="changed during bundle snapshot"):
        inspect_result(bundle, kind="bundle")


def test_catalog_is_sorted_bounded_and_does_not_rank(
    tmp_path: Path,
    pairwise_spec: DesignSpec,
) -> None:
    bundle = tmp_path / "bundle"
    design(pairwise_spec).write(bundle)
    inspection = inspect_result(bundle, kind="bundle")

    catalog = build_result_catalog({"zeta": inspection, "alpha": inspection})

    assert catalog.schema_version == "motif-balance.result-catalog/v2"
    assert [entry.entry_id for entry in catalog.entries] == ["alpha", "zeta"]
    assert "candidates" not in catalog.model_dump_json()
    assert "does not rank" in render_catalog_html(catalog).decode()
    with pytest.raises(ValueError, match="entry_id"):
        build_result_catalog({"Not Portable": inspection})


def test_inspection_rejects_cross_kind_trust_options(
    tmp_path: Path,
    pairwise_spec: DesignSpec,
) -> None:
    bundle = tmp_path / "bundle"
    design(pairwise_spec).write(bundle)

    with pytest.raises(ArtifactError, match="execution trust anchors"):
        inspect_result(
            bundle,
            kind="bundle",
            expected_workspace_id="execution-" + "0" * 24,
        )
    with pytest.raises(ArtifactError, match="unsupported inspection kind"):
        inspect_result(bundle, kind="unknown")  # type: ignore[arg-type]


def test_distance_projection_refuses_unbounded_pairwise_work(
    pairwise_spec: DesignSpec,
) -> None:
    candidate = design(pairwise_spec).candidates[0]

    result = _distance_inspection((candidate,) * 2_500)

    assert result.status == "not_computed_limit"
    assert result.actual_min_distance is None
    assert result.base_comparisons > result.computation_limit


@pytest.mark.parametrize(
    ("model", "payload", "message"),
    [
        (
            DistanceInspection,
            {"status": "exact", "base_comparisons": 4},
            "requires a value and candidate pair",
        ),
        (
            DeliveryInspection,
            {"requested_count": 3, "delivered_count": 2, "status": "complete"},
            "must reflect",
        ),
        (
            IntegrityInspection,
            {
                "state": "self_consistent",
                "trust_basis": "external_bundle_id",
                "checked_identities": (),
            },
            "inconsistent",
        ),
    ],
)
def test_inspection_models_reject_incoherent_states(
    model: type[DistanceInspection] | type[DeliveryInspection] | type[IntegrityInspection],
    payload: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        model.model_validate(payload)


def test_catalog_models_reject_incoherent_or_unbounded_entries(
    tmp_path: Path,
    pairwise_spec: DesignSpec,
) -> None:
    bundle = tmp_path / "bundle"
    design(pairwise_spec).write(bundle)
    entry = build_result_catalog({"alpha": inspect_result(bundle, kind="bundle")}).entries[0]
    payload = entry.model_dump(mode="python")

    for update, message in (
        ({"subject_kind": "execution"}, "workspace identity"),
        ({"score_min": 2.0, "score_max": 1.0}, "score range"),
        ({"motif_ids": ("motif_a", "motif_a")}, "motif identifiers"),
    ):
        with pytest.raises(ValidationError, match=message):
            CatalogEntry.model_validate({**payload, **update})
    with pytest.raises(ValidationError, match=r"1\.\.100"):
        ResultCatalog(entries=())


def test_renderers_escape_forged_identifiers(
    tmp_path: Path,
    pairwise_spec: DesignSpec,
) -> None:
    bundle = tmp_path / "bundle"
    design(pairwise_spec).write(bundle)
    inspection = inspect_result(bundle, kind="bundle")
    candidate = inspection.portfolio.candidates[0]
    forged_candidate = candidate.model_copy(update={"candidate_id": '<script src="x"></script>'})
    forged_portfolio = inspection.portfolio.model_copy(
        update={"candidates": (forged_candidate, *inspection.portfolio.candidates[1:])}
    )
    forged = inspection.model_copy(update={"portfolio": forged_portfolio})

    with pytest.raises(ArtifactError, match="invalid candidate identifier"):
        render_html(forged)

    catalog = build_result_catalog({"alpha": inspection})
    entry = catalog.entries[0].model_copy(update={"problem_id": "<script>x</script>"})
    html = render_catalog_html(catalog.model_copy(update={"entries": (entry,)})).decode()
    assert "<script" not in html
    assert "&lt;script" in html


def test_public_result_schema_contains_only_supported_product_kinds() -> None:
    schema = json.dumps(ResultInspection.model_json_schema(), sort_keys=True)
    assert '"bundle"' in schema
    assert '"execution"' in schema
    assert '"unknown"' not in schema
