from __future__ import annotations

from pathlib import Path

from motif_balance import DesignSpec, MotifModel, design
from motif_balance.inspection import inspect_result
from motif_balance.inspection.render import render_html, render_portfolio_svg, render_text


def _distance_blocked_best_spec() -> DesignSpec:
    motif = MotifModel(
        motif_id="adenine",
        probabilities=tuple((0.7, 0.1, 0.1, 0.1) for _ in range(4)),
        background=(0.25, 0.25, 0.25, 0.25),
    )
    return DesignSpec(
        motifs=(motif,),
        length=4,
        count=2,
        strands="forward",
        evaluations=8,
        seed=23,
        min_distance=0.5,
    )


def test_bundle_distinguishes_best_observed_from_selected_portfolio(
    tmp_path: Path,
) -> None:
    spec = _distance_blocked_best_spec()
    portfolio = design(spec)
    best_score = portfolio.manifest.search_diagnostics.best_score

    assert portfolio.manifest.schema_version == "run-manifest/v5"
    assert portfolio.best_observed is not None
    assert portfolio.best_observed.sequence == "ACAA"
    assert [candidate.sequence for candidate in portfolio.candidates] == ["ACAG", "ACCA"]

    bundle = tmp_path / "bundle"
    portfolio.write(bundle)
    inspection = inspect_result(bundle, kind="bundle")

    assert inspection.portfolio.best_observed_score == best_score
    assert inspection.portfolio.best_observed is not None
    assert inspection.portfolio.best_observed.sequence == "ACAA"
    assert inspection.portfolio.best_observed.selected_rank is None
    assert [candidate.sequence for candidate in inspection.portfolio.candidates] == [
        "ACAG",
        "ACCA",
    ]

    text = render_text(inspection)
    html = render_html(inspection).decode()
    svg = render_portfolio_svg(inspection).decode()
    assert "Best observed balance_score" in text
    assert "that sequence was not selected under the portfolio constraint" in text
    assert "not selected under the portfolio constraint" in text
    assert "Best observed" in html
    assert '<strong>Best observed candidate</strong> <code class="sequence">ACAA</code>' in html
    assert "not selected under the portfolio constraint" in html
    assert "best observed" in svg.casefold()
    assert 'data-best-observed-selected-rank="none"' in svg
