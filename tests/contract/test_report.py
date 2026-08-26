from __future__ import annotations

from motif_balance import DesignSpec, design
from motif_balance.report import render_report


def test_report_exposes_candidate_match_and_search_interpretation(
    pairwise_spec: DesignSpec,
) -> None:
    portfolio = design(pairwise_spec)

    report = render_report(pairwise_spec, portfolio.candidates).decode()

    assert "Candidate portfolio" in report
    assert "Limiting motif" in report
    assert "Per-motif matches" in report
    assert "0-based, half-open" in report
    assert "motif_a" in report
    assert "motif_b" in report
    assert portfolio.candidates[0].candidate_id in report
    assert "Computational scope" in report
    assert "does not establish binding" in report


def test_report_lists_every_tied_limiting_motif(pairwise_spec: DesignSpec) -> None:
    portfolio = design(pairwise_spec)

    report = render_report(pairwise_spec, portfolio.candidates).decode()

    assert "motif_a, motif_b" in report
