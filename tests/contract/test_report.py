from __future__ import annotations

from pathlib import Path

import pytest

from motif_balance import DesignSpec, design
from motif_balance.api import render_bundle_report
from motif_balance.errors import ArtifactError
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


def test_derived_file_publication_does_not_leave_partial_output(
    tmp_path: Path,
    pairwise_spec: DesignSpec,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = tmp_path / "bundle"
    out = tmp_path / "review.html"
    design(pairwise_spec).write(bundle)

    def fail_publication(*_args: object, **_kwargs: object) -> None:
        raise OSError("simulated publication failure")

    monkeypatch.setattr("motif_balance.api.os.link", fail_publication)
    with pytest.raises(ArtifactError, match="Unable to write report"):
        render_bundle_report(bundle, out)

    assert not out.exists()
    assert not tuple(tmp_path.glob(".review.html.*.tmp"))


def test_derived_report_refuses_output_inside_verified_bundle(
    tmp_path: Path,
    pairwise_spec: DesignSpec,
) -> None:
    bundle = tmp_path / "bundle"
    out = bundle / "derived-review.html"
    design(pairwise_spec).write(bundle)

    with pytest.raises(ArtifactError, match="outside the verified bundle"):
        render_bundle_report(bundle, out)

    assert not out.exists()
