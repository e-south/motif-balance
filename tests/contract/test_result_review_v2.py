from __future__ import annotations

import hashlib
import json
import math
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from pydantic import ValidationError

from motif_balance.api import design, score
from motif_balance.artifacts import bundle_id, manifest_bytes
from motif_balance.errors import ArtifactError
from motif_balance.inspection import ResultInspection, inspect_result
from motif_balance.inspection.model import (
    DeliveryInspection,
    InspectionCandidate,
    InspectionMatch,
    InspectionMotif,
    InspectionPortfolio,
    InspectionProblem,
    IntegrityInspection,
    SearchInspection,
)
from motif_balance.inspection.project import project_candidate
from motif_balance.inspection.render import (
    render_candidate_svg,
    render_html,
    render_inspection_json,
    render_portfolio_svg,
    render_search_svg,
    render_text,
)
from motif_balance.model import (
    ArtifactDigest,
    Candidate,
    DesignSpec,
    MotifModel,
    RunManifest,
    SearchCheckpoint,
)


def _candidate_for(sequence: str, spec: DesignSpec) -> Candidate:
    evaluation = score(sequence, spec)
    return Candidate(
        candidate_id="candidate-0000000000000000",
        rank=1,
        sequence=evaluation.sequence,
        balance_score=evaluation.balance_score,
        matches=evaluation.matches,
    )


def _rewrite_as_v2_bundle(bundle: Path) -> str:
    """Add the report.html member required by released run-manifest/v2."""

    report = b"<!doctype html><title>Released Motif Balance v2 report</title>\n"
    (bundle / "report.html").write_bytes(report)
    payload = json.loads((bundle / "manifest.json").read_bytes())
    payload["schema_version"] = "run-manifest/v2"
    payload.pop("best_observed")
    payload["package_version"] = "0.2.0a3"
    design_payload = json.loads((bundle / "design.json").read_bytes())
    run_payload = {
        "problem_id": payload["problem_id"],
        "count": design_payload["count"],
        "min_distance": design_payload["min_distance"],
        "evaluations": design_payload["evaluations"],
        "seed": design_payload["seed"],
        "search_engine": payload["search_engine"],
        "search_engine_version": payload["search_engine_version"],
        "package_version": payload["package_version"],
    }
    run_digest = hashlib.sha256(
        json.dumps(run_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    payload["run_id"] = f"run-{run_digest[:24]}"
    payload["artifacts"]["report.html"] = {
        "bytes": len(report),
        "sha256": hashlib.sha256(report).hexdigest(),
    }
    artifacts = tuple(
        ArtifactDigest(path=path, **record) for path, record in sorted(payload["artifacts"].items())
    )
    provisional = RunManifest.model_validate({**payload, "artifacts": artifacts})
    sealed = provisional.model_copy(update={"bundle_id": bundle_id(provisional)})
    (bundle / "manifest.json").write_bytes(manifest_bytes(sealed))
    return sealed.bundle_id


def _rewrite_as_v3_bundle(bundle: Path) -> str:
    """Remove the best-observed record that did not exist in run-manifest/v3."""

    payload = json.loads((bundle / "manifest.json").read_bytes())
    payload["schema_version"] = "run-manifest/v3"
    payload.pop("best_observed")
    artifacts = tuple(
        ArtifactDigest(path=path, **record) for path, record in sorted(payload["artifacts"].items())
    )
    provisional = RunManifest.model_validate({**payload, "artifacts": artifacts})
    sealed = provisional.model_copy(update={"bundle_id": bundle_id(provisional)})
    (bundle / "manifest.json").write_bytes(manifest_bytes(sealed))
    return sealed.bundle_id


def test_projection_separates_delivery_search_and_integrity(
    tmp_path: Path,
    pairwise_spec: DesignSpec,
) -> None:
    bundle = tmp_path / "bundle"
    design(pairwise_spec).write(bundle)

    inspection = inspect_result(bundle, kind="bundle")

    assert inspection.schema_version == "motif-balance.result-inspection/v4"
    assert inspection.problem.scoring_semantics == "relative_pwm_attainment_v2"
    for motif in inspection.problem.motifs:
        assert motif.score_min < motif.score_max
        assert len(motif.probability_consensus) == motif.width
        assert len(motif.score_maximizing_sequence) == motif.width
    assert inspection.delivery.requested_count == pairwise_spec.count
    assert inspection.delivery.delivered_count == pairwise_spec.count
    assert inspection.delivery.status == "complete"
    assert inspection.search.completion == "exhaustive"
    assert inspection.search.stop_reason == "sequence_space_exhausted"
    assert inspection.integrity.state == "self_consistent"
    assert inspection.integrity.trust_basis == "self_consistent"
    assert inspection.integrity.checked_identities == ()


def test_new_writer_uses_v5_and_inspection_reads_strict_released_v2_bundle(
    tmp_path: Path,
    pairwise_spec: DesignSpec,
) -> None:
    bundle = tmp_path / "bundle"
    portfolio = design(pairwise_spec)
    assert portfolio.manifest.schema_version == "run-manifest/v5"
    portfolio.write(bundle)
    expected_bundle_id = _rewrite_as_v2_bundle(bundle)

    inspection = inspect_result(
        bundle,
        kind="bundle",
        expected_bundle_id=expected_bundle_id,
    )

    assert inspection.run.bundle_id == expected_bundle_id
    assert inspection.run.package_version == "0.2.0a3"
    assert "report.html" not in {artifact.path for artifact in inspection.artifacts}


def test_released_v2_inventory_remains_schema_strict(
    tmp_path: Path,
    pairwise_spec: DesignSpec,
) -> None:
    bundle = tmp_path / "bundle"
    design(pairwise_spec).write(bundle)
    expected_bundle_id = _rewrite_as_v2_bundle(bundle)
    (bundle / "unexpected.txt").write_text("not declared")

    with pytest.raises(ArtifactError, match="inventory mismatch"):
        inspect_result(bundle, kind="bundle", expected_bundle_id=expected_bundle_id)


def test_released_v3_remains_readable_without_inventing_best_observed_sequence(
    tmp_path: Path,
    pairwise_spec: DesignSpec,
) -> None:
    bundle = tmp_path / "bundle"
    portfolio = design(pairwise_spec)
    portfolio.write(bundle)
    expected_score = portfolio.manifest.search_diagnostics.best_score
    expected_bundle_id = _rewrite_as_v3_bundle(bundle)

    inspection = inspect_result(bundle, kind="bundle", expected_bundle_id=expected_bundle_id)

    assert inspection.portfolio.best_observed is None
    assert inspection.portfolio.best_observed_score == expected_score
    assert b"sequence unavailable in source schema" in render_portfolio_svg(inspection)


def test_projection_replays_position_support_and_reverse_coordinates() -> None:
    motif = MotifModel(
        motif_id="reverse",
        probabilities=((0.7, 0.1, 0.1, 0.1), (0.1, 0.7, 0.1, 0.1)),
        background=(0.25, 0.25, 0.25, 0.25),
    )
    spec = DesignSpec(
        motifs=(motif,),
        length=2,
        count=1,
        strands="both",
        evaluations=16,
        seed=7,
    )

    projected = project_candidate(spec, _candidate_for("GT", spec))
    match = projected.matches[0]

    assert projected.sequence == "GT"
    assert projected.complement_sequence == "CA"
    assert match.strand == "-"
    assert tuple(item.candidate_position for item in match.position_support) == (1, 0)
    assert "".join(item.observed_base for item in match.position_support) == "AC"
    assert math.isclose(
        sum(item.llr_contribution for item in match.position_support),
        match.raw_score,
        abs_tol=1.0e-12,
    )


def test_projection_represents_overlap_as_a_coordinate_union() -> None:
    first = MotifModel(
        motif_id="first",
        probabilities=((0.7, 0.1, 0.1, 0.1), (0.1, 0.7, 0.1, 0.1)),
        background=(0.25, 0.25, 0.25, 0.25),
    )
    second = MotifModel(
        motif_id="second",
        probabilities=((0.1, 0.7, 0.1, 0.1), (0.1, 0.1, 0.7, 0.1)),
        background=(0.25, 0.25, 0.25, 0.25),
    )
    spec = DesignSpec(
        motifs=(first, second),
        length=3,
        count=1,
        strands="forward",
        evaluations=64,
        seed=7,
    )

    projected = project_candidate(spec, _candidate_for("ACG", spec))

    assert projected.shared_coordinates == (1,)


def test_review_svg_views_are_semantic_accessible_and_truthful(
    tmp_path: Path,
    pairwise_spec: DesignSpec,
) -> None:
    bundle = tmp_path / "bundle"
    portfolio = design(pairwise_spec)
    portfolio.write(bundle)
    inspection = inspect_result(bundle, kind="bundle")

    candidate = render_candidate_svg(inspection, candidate_rank=1)
    balance = render_portfolio_svg(inspection)
    search_record = render_search_svg(inspection)

    for payload in (candidate, balance, search_record):
        assert payload is not None
        root = ET.fromstring(payload)
        assert root.tag.endswith("svg")
        assert root.attrib["role"] == "img"
        assert root.attrib["width"]
        assert root.attrib["height"]
        assert root.attrib["viewBox"]
        assert root.find("{http://www.w3.org/2000/svg}title") is not None
        assert root.find("{http://www.w3.org/2000/svg}desc") is not None
        assert b"<script" not in payload
        assert b"href=" not in payload
        assert b"url(" not in payload

    assert b'id="primary-sequence"' in candidate
    assert b'id="complementary-sequence"' in candidate
    assert b'id="motif-models"' in candidate
    assert b'class="motif-model"' in candidate
    assert b"data-model-digest=" in candidate
    assert b'data-probability="0.69999999999999996"' in candidate
    assert b'id="position-support"' in candidate
    assert "5\u2032\u21923\u2032".encode() in candidate
    assert "3\u2032\u21925\u2032".encode() in candidate
    assert b"score-maximizing PWM reference" in balance
    assert b"balance_score" in balance
    assert b"Evaluator calls" in search_record
    assert b"Best observed balance_score" in search_record
    assert b"running maximum" in search_record
    assert b"global optimality" in search_record


def test_one_html_compositor_uses_result_reading_order_and_scrolls_wide_figures(
    tmp_path: Path,
    pairwise_spec: DesignSpec,
) -> None:
    bundle = tmp_path / "bundle"
    design(pairwise_spec).write(bundle)
    inspection = inspect_result(bundle, kind="bundle")

    html = render_html(inspection).decode()

    headings = (
        "Result",
        "Design contract",
        "Portfolio balance",
        "Selected candidate",
        "Exact records",
        "Provenance and integrity",
    )
    positions = tuple(html.index(f">{heading}<") for heading in headings)
    assert positions == tuple(sorted(positions))
    assert "Portfolio delivery" in html
    assert "Search completion" in html
    assert "Artifact integrity" in html
    assert "overall-success" not in html
    assert '<div class="states"' not in html
    assert '<p class="status-line"' in html
    assert "<summary>Search diagnostics</summary>" in html
    assert "model-defined sequence evidence, not measurements" in html
    assert "figure-scroll" in html
    compact = "".join(html.split())
    assert ".figure-scrollsvg{display:block;max-width:none;min-width:60rem" in compact
    assert "@mediaprint" in compact
    assert ".figure-scrollsvg{min-width:0;width:100%;height:auto;}" in compact
    assert ".screen-records{display:none!important;}" in compact
    assert ".print-records{display:block;}" in compact
    assert "<script" not in html
    assert "https://" not in html


def test_chromium_print_contains_progressively_disclosed_exact_records(
    tmp_path: Path,
    pairwise_spec: DesignSpec,
) -> None:
    chrome = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    pdftotext = shutil.which("pdftotext")
    if not chrome.is_file() or pdftotext is None:
        pytest.skip("Chrome and pdftotext are required for print-behavior QA")
    bundle = tmp_path / "bundle"
    review = tmp_path / "review.html"
    pdf = tmp_path / "review.pdf"
    design(pairwise_spec).write(bundle)
    review.write_bytes(render_html(inspect_result(bundle, kind="bundle")))

    command = (
        str(chrome),
        "--headless",
        "--disable-gpu",
        "--disable-background-networking",
        "--no-first-run",
        "--no-pdf-header-footer",
        f"--user-data-dir={tmp_path / 'chrome-profile'}",
        f"--print-to-pdf={pdf}",
        review.as_uri(),
    )
    try:
        subprocess.run(command, check=True, capture_output=True, timeout=20)
    except subprocess.TimeoutExpired:
        if not pdf.is_file() or pdf.stat().st_size == 0:
            raise
    printed = subprocess.run(
        (pdftotext, str(pdf), "-"),
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    ).stdout

    assert "Oriented word" in printed
    assert "Model digest" in printed
    assert "candidates.tsv" in printed


def test_text_and_json_are_rendered_from_the_same_projection(
    tmp_path: Path,
    pairwise_spec: DesignSpec,
) -> None:
    bundle = tmp_path / "bundle"
    design(pairwise_spec).write(bundle)
    inspection = inspect_result(bundle, kind="bundle")

    text = render_text(inspection)
    payload = json.loads(render_inspection_json(inspection))

    assert f"Returned {pairwise_spec.count} of {pairwise_spec.count}" in text
    assert "Status: delivery complete · search exhaustive · integrity self consistent" in text
    assert "Portfolio delivery:" not in text
    assert "Search completion:" not in text
    assert payload == inspection.model_dump(mode="json")


def test_inspection_contracts_reject_internally_inconsistent_projection_rows(
    tmp_path: Path,
    pairwise_spec: DesignSpec,
) -> None:
    bundle = tmp_path / "bundle"
    design(pairwise_spec).write(bundle)
    inspection = inspect_result(bundle, kind="bundle")
    motif = inspection.problem.motifs[0]
    match = inspection.portfolio.candidates[0].matches[0]
    candidate = inspection.portfolio.candidates[0]

    invalid: tuple[tuple[type[object], dict[str, object], str], ...] = (
        (
            InspectionMotif,
            {**motif.model_dump(mode="python"), "width": motif.width + 1},
            "motif width",
        ),
        (
            InspectionProblem,
            {
                **inspection.problem.model_dump(mode="python"),
                "motifs": tuple(reversed(inspection.problem.motifs)),
            },
            "canonical",
        ),
        (
            SearchInspection,
            {
                **inspection.search.model_dump(mode="python"),
                "stop_reason": "evaluation_budget_exhausted",
            },
            "stop reason",
        ),
        (
            SearchInspection,
            {
                **inspection.search.model_dump(mode="python"),
                "unique_evaluations": inspection.search.evaluator_calls + 1,
            },
            "unique evaluations",
        ),
        (
            SearchInspection,
            {**inspection.search.model_dump(mode="python"), "checkpoints": ()},
            "checkpoints",
        ),
        (
            SearchInspection,
            {**inspection.search.model_dump(mode="python"), "restart_final_scores": ()},
            "restart scores",
        ),
        (
            IntegrityInspection,
            {
                "state": "readable_untrusted",
                "trust_basis": "self_consistent",
                "checked_identities": ("bundle_id",),
            },
            "untrusted inspection",
        ),
        (
            InspectionMatch,
            {**match.model_dump(mode="python"), "matched_sequence": "A"},
            "match coordinates",
        ),
        (
            InspectionMatch,
            {**match.model_dump(mode="python"), "position_support": match.position_support[:-1]},
            "one row",
        ),
        (
            InspectionMatch,
            {
                **match.model_dump(mode="python"),
                "raw_score": match.raw_score + 1.0,
            },
            "sum to the raw",
        ),
        (
            InspectionCandidate,
            {**candidate.model_dump(mode="python"), "complement_sequence": candidate.sequence},
            "coordinate-aligned",
        ),
        (
            InspectionCandidate,
            {**candidate.model_dump(mode="python"), "matches": ()},
            "requires motif matches",
        ),
        (
            InspectionCandidate,
            {**candidate.model_dump(mode="python"), "balance_score": candidate.balance_score + 1.0},
            "weakest normalized",
        ),
        (
            InspectionCandidate,
            {**candidate.model_dump(mode="python"), "limiting_motif_ids": ()},
            "hard minimum",
        ),
        (
            InspectionCandidate,
            {
                **candidate.model_dump(mode="python"),
                "shared_coordinates": () if candidate.shared_coordinates else (0,),
            },
            "shared coordinates",
        ),
        (
            InspectionPortfolio,
            {**inspection.portfolio.model_dump(mode="python"), "candidates": ()},
            "requires candidates",
        ),
        (
            InspectionPortfolio,
            {**inspection.portfolio.model_dump(mode="python"), "score_min": 0.123456789},
            "score_min",
        ),
        (
            InspectionPortfolio,
            {**inspection.portfolio.model_dump(mode="python"), "score_max": 9.0},
            "score_max",
        ),
    )

    for model, payload, message in invalid:
        with pytest.raises(ValidationError, match=message):
            model.model_validate(payload)  # type: ignore[attr-defined]


def test_result_contract_and_search_renderer_enforce_bounds(
    tmp_path: Path,
    pairwise_spec: DesignSpec,
) -> None:
    bundle = tmp_path / "bundle"
    design(pairwise_spec).write(bundle)
    inspection = inspect_result(bundle, kind="bundle")

    incomplete = DeliveryInspection(
        requested_count=inspection.delivery.requested_count,
        delivered_count=inspection.delivery.delivered_count - 1,
        status="incomplete",
    )
    readable = IntegrityInspection(
        state="readable_untrusted",
        trust_basis="self_consistent",
        checked_identities=(),
    )
    invalid_results = (
        ({"subject_kind": "execution"}, "kind and provenance"),
        ({"integrity": readable}, "readable_untrusted"),
        ({"delivery": incomplete}, "delivered count"),
        ({"artifacts": tuple(reversed(inspection.artifacts))}, "unique and sorted"),
    )
    for update, message in invalid_results:
        payload = inspection.model_copy(update=update).model_dump(mode="python")
        with pytest.raises(ValidationError, match=message):
            ResultInspection.model_validate(payload)

    empty_search = inspection.search.model_copy(update={"checkpoints": ()})
    assert render_search_svg(inspection.model_copy(update={"search": empty_search})) is None

    stable = tuple(SearchCheckpoint(evaluations=i, best_score=0.5) for i in range(1, 301))
    stable_search = inspection.search.model_copy(
        update={"checkpoints": stable, "evaluator_calls": 300, "evaluation_budget": 300}
    )
    stable_svg = render_search_svg(inspection.model_copy(update={"search": stable_search}))
    assert stable_svg is not None
    assert b'data-displayed-checkpoints="2"' in stable_svg

    improving = tuple(SearchCheckpoint(evaluations=i, best_score=i / 300) for i in range(1, 301))
    improving_search = inspection.search.model_copy(
        update={"checkpoints": improving, "evaluator_calls": 300, "evaluation_budget": 300}
    )
    improving_svg = render_search_svg(inspection.model_copy(update={"search": improving_search}))
    assert improving_svg is not None
    assert b'data-displayed-checkpoints="256"' in improving_svg
    assert b'id="best-observed-step"' not in improving_svg
    assert b'id="sampled-checkpoints"' in improving_svg
    assert b"sampled markers; omitted intervals are not connected" in improving_svg


def test_projection_rejects_support_rows_above_its_own_bound(
    tmp_path: Path,
    pairwise_spec: DesignSpec,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = tmp_path / "bundle"
    design(pairwise_spec).write(bundle)
    monkeypatch.setattr("motif_balance.inspection.project.MAX_INSPECTION_SUPPORT_ROWS", 1)

    with pytest.raises(ArtifactError, match=r"position-support rows.*requested=12.*limit=1"):
        inspect_result(bundle, kind="bundle")


def test_portfolio_view_keeps_limiting_motifs_when_columns_are_bounded(
    tmp_path: Path,
) -> None:
    common = ((0.97, 0.01, 0.01, 0.01),)
    limiting = ((0.3, 0.2, 0.1, 0.4),)
    motifs = tuple(
        MotifModel(
            motif_id=f"motif_{index:02d}",
            probabilities=limiting if index == 17 else common,
            background=(0.25, 0.25, 0.25, 0.25),
        )
        for index in range(18)
    )
    spec = DesignSpec(
        motifs=motifs,
        length=1,
        count=1,
        strands="forward",
        evaluations=4,
        seed=7,
    )
    bundle = tmp_path / "bundle"
    design(spec).write(bundle)

    svg = render_portfolio_svg(inspect_result(bundle, kind="bundle"))

    assert b'data-total-motifs="18"' in svg
    assert b'data-displayed-motifs="16"' in svg
    assert b'data-displayed-limiting="1"' in svg
    assert b'data-total-limiting="1"' in svg
    assert b">motif_17<" in svg
