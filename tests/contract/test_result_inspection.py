from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from motif_balance import DesignSpec, build_result_catalog, design, inspect_result, read_portfolio
from motif_balance.artifacts import manifest_bytes
from motif_balance.errors import ArtifactError
from motif_balance.inspection import (
    CatalogEntry,
    DistanceInspection,
    InspectionPortfolio,
    ResultCatalog,
    ResultIndex,
    ResultInspection,
    _distance_inspection,
    build_result_index,
    catalog_html,
    inspection_html,
)


def test_bundle_inspection_replays_and_summarizes_every_product_plane(
    tmp_path: Path,
    pairwise_spec: DesignSpec,
) -> None:
    bundle = tmp_path / "bundle"
    portfolio = design(pairwise_spec)
    portfolio.write(bundle)

    inspection = inspect_result(bundle, kind="bundle")

    assert inspection.integrity_status == "verified"
    assert inspection.trust_basis == "self_consistent"
    assert isinstance(inspection.result, ResultIndex)
    assert inspection.result.problem.problem_id == portfolio.problem_id
    assert inspection.result.run.bundle_id == portfolio.manifest.bundle_id
    assert inspection.result.portfolio.returned_count == pairwise_spec.count
    assert inspection.result.portfolio.distance.status == "exact"
    assert inspection.result.portfolio.distance.actual_min_distance == pairwise_spec.min_distance
    assert inspection.result.portfolio.distance.closest_candidate_ids is not None
    assert {artifact.path for artifact in inspection.result.artifacts} == {
        "candidates.fasta",
        "candidates.tsv",
        "design.json",
        "manifest.json",
        "matches.tsv",
        "motifs.json",
        "report.html",
    }
    html = inspection_html(inspection).decode()
    assert portfolio.manifest.bundle_id in html
    assert "Optimizer diagnostics" in html
    assert "Artifact integrity" in html
    assert "Per-candidate motif matches" in html
    assert "<details>" in html
    assert str(tmp_path) not in html
    assert "https://" not in html
    assert "<script" not in html


def test_bundle_inspection_distinguishes_an_external_identity(
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

    assert inspection.trust_basis == "external_bundle_id"
    assert inspection.trusted_identities_checked == ("bundle_id",)


def test_result_projection_rechecks_artifact_bytes_after_portfolio_read(
    tmp_path: Path,
    pairwise_spec: DesignSpec,
) -> None:
    bundle = tmp_path / "bundle"
    design(pairwise_spec).write(bundle)
    portfolio = read_portfolio(bundle)
    (bundle / "report.html").write_text("changed after verification")

    with pytest.raises(ArtifactError, match="changed during inspection"):
        build_result_index(
            bundle,
            portfolio,
            canonical_manifest=manifest_bytes(portfolio.manifest),
        )


def test_catalog_is_sorted_and_rejects_duplicate_or_invalid_ids(
    tmp_path: Path,
    pairwise_spec: DesignSpec,
) -> None:
    bundle = tmp_path / "bundle"
    design(pairwise_spec).write(bundle)
    inspection = inspect_result(bundle, kind="bundle")

    result = build_result_catalog({"zeta": inspection, "alpha": inspection})

    assert [entry.entry_id for entry in result.entries] == ["alpha", "zeta"]
    assert "candidates" not in result.model_dump_json()
    assert "does not rank" in catalog_html(result).decode()
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


def test_public_result_schema_contains_only_supported_product_kinds() -> None:
    schema = json.dumps(ResultInspection.model_json_schema(), sort_keys=True)

    assert '"bundle"' in schema
    assert '"execution"' in schema
    assert '"unknown"' not in schema


def test_distance_inspection_refuses_unbounded_exact_pairwise_work(
    pairwise_spec: DesignSpec,
) -> None:
    candidate = design(pairwise_spec).candidates[0]

    result = _distance_inspection((candidate,) * 2_500)

    assert result.status == "not_computed_limit"
    assert result.actual_min_distance is None
    assert result.base_comparisons > result.computation_limit


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (
            {"status": "exact", "base_comparisons": 4},
            "requires a value and candidate pair",
        ),
        (
            {
                "status": "not_applicable",
                "base_comparisons": 0,
                "actual_min_distance": 0.5,
            },
            "cannot report an exact result",
        ),
        (
            {"status": "not_computed_limit", "base_comparisons": 10},
            "requires work above",
        ),
    ],
)
def test_distance_inspection_rejects_incoherent_states(
    payload: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        DistanceInspection.model_validate(payload)


def test_inspection_models_reject_incoherent_summaries(
    tmp_path: Path,
    pairwise_spec: DesignSpec,
) -> None:
    bundle = tmp_path / "bundle"
    design(pairwise_spec).write(bundle)
    inspection = inspect_result(bundle, kind="bundle")
    portfolio_payload = inspection.result.portfolio.model_dump(mode="python")

    for field, value, message in (
        ("returned_count", 99, "returned_count"),
        ("score_min", 0.0, "score_min"),
        ("score_max", 99.0, "score_max"),
    ):
        with pytest.raises(ValidationError, match=message):
            InspectionPortfolio.model_validate({**portfolio_payload, field: value})

    inspection_payload = inspection.model_dump(mode="python")
    with pytest.raises(ValidationError, match="trust fields"):
        ResultInspection.model_validate(
            {**inspection_payload, "integrity_status": "readable_untrusted"}
        )
    with pytest.raises(ValidationError, match="requires execution provenance"):
        ResultInspection.model_validate(
            {
                **inspection_payload,
                "subject_kind": "execution",
                "integrity_status": "readable_untrusted",
                "trust_basis": "self_consistent",
            }
        )
    index_payload = inspection.result.model_dump(mode="python")
    with pytest.raises(ValidationError, match="unique and sorted"):
        ResultIndex.model_validate(
            {**index_payload, "artifacts": tuple(reversed(index_payload["artifacts"]))}
        )


def test_catalog_models_reject_incoherent_or_unbounded_entries(
    tmp_path: Path,
    pairwise_spec: DesignSpec,
) -> None:
    bundle = tmp_path / "bundle"
    design(pairwise_spec).write(bundle)
    inspection = inspect_result(bundle, kind="bundle")
    entry = build_result_catalog({"alpha": inspection}).entries[0]
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
    duplicate = entry.model_copy(update={"entry_id": "alpha"})
    with pytest.raises(ValidationError, match="unique and sorted"):
        ResultCatalog(entries=(duplicate, duplicate))


def test_catalog_html_escapes_a_forged_problem_identifier(
    tmp_path: Path,
    pairwise_spec: DesignSpec,
) -> None:
    bundle = tmp_path / "bundle"
    design(pairwise_spec).write(bundle)
    catalog = build_result_catalog({"alpha": inspect_result(bundle, kind="bundle")})
    forged_entry = catalog.entries[0].model_copy(
        update={"problem_id": '<script src="https://example.invalid/x.js"></script>'}
    )
    forged = catalog.model_copy(update={"entries": (forged_entry,)})

    html = catalog_html(forged).decode()

    assert "<script" not in html
    assert "&lt;script" in html


def test_html_progressive_view_bounds_large_tables(
    tmp_path: Path,
    pairwise_spec: DesignSpec,
) -> None:
    bundle = tmp_path / "bundle"
    design(pairwise_spec).write(bundle)
    inspection = inspect_result(bundle, kind="bundle")
    candidate = inspection.result.portfolio.candidates[0]
    expanded_portfolio = inspection.result.portfolio.model_copy(
        update={"returned_count": 501, "candidates": (candidate,) * 501}
    )
    expanded_result = inspection.result.model_copy(update={"portfolio": expanded_portfolio})
    expanded = inspection.model_copy(update={"result": expanded_result})

    html = inspection_html(expanded).decode()

    assert "Showing 500 of 501 candidates" in html
    assert "Showing 1000 of 1002 matches" in html


def test_html_rejects_a_forged_candidate_identifier(
    tmp_path: Path,
    pairwise_spec: DesignSpec,
) -> None:
    bundle = tmp_path / "bundle"
    design(pairwise_spec).write(bundle)
    inspection = inspect_result(bundle, kind="bundle")
    candidate = inspection.result.portfolio.candidates[0]
    forged_candidate = candidate.model_copy(
        update={"candidate_id": '<script src="https://example.invalid/x.js"></script>'}
    )
    forged_portfolio = inspection.result.portfolio.model_copy(
        update={
            "candidates": (forged_candidate, *inspection.result.portfolio.candidates[1:]),
        }
    )
    forged_result = inspection.result.model_copy(update={"portfolio": forged_portfolio})
    forged = inspection.model_copy(update={"result": forged_result})

    with pytest.raises(ArtifactError, match="invalid candidate identifier"):
        inspection_html(forged)
