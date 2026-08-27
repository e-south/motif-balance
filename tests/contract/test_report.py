from __future__ import annotations

from pathlib import Path

import pytest

from motif_balance import DesignSpec, design
from motif_balance.api import inspect_result, render_bundle_report, render_inspection_html
from motif_balance.errors import ArtifactError


def test_bundle_report_uses_the_one_verified_html_compositor(
    tmp_path: Path,
    pairwise_spec: DesignSpec,
) -> None:
    bundle = tmp_path / "bundle"
    out = tmp_path / "review.html"
    portfolio = design(pairwise_spec)
    portfolio.write(bundle)

    bundle_id = render_bundle_report(bundle, out)

    assert bundle_id == portfolio.manifest.bundle_id
    assert out.read_bytes() == render_inspection_html(inspect_result(bundle, kind="bundle"))
    assert b"Candidate realization" in out.read_bytes()
    assert b"Portfolio balance" in out.read_bytes()
    assert b"Search record" in out.read_bytes()


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
