from __future__ import annotations

from pathlib import Path

import pytest

from motif_balance import DesignSpec, design
from motif_balance.errors import ArtifactError
from motif_balance.inspection import inspect_result
from motif_balance.inspection.render import render_candidate_svg


def test_candidate_renderer_consumes_the_verified_result_inspection(
    tmp_path: Path,
    pairwise_spec: DesignSpec,
) -> None:
    bundle = tmp_path / "bundle"
    portfolio = design(pairwise_spec)
    portfolio.write(bundle)
    inspection = inspect_result(bundle, kind="bundle")

    svg = render_candidate_svg(inspection, candidate_rank=1).decode("utf-8")

    assert 'id="candidate-realization-view"' in svg
    assert portfolio.candidates[0].candidate_id not in svg
    assert portfolio.manifest.bundle_id not in svg


def test_candidate_renderer_has_no_unbound_problem_candidate_entrypoint() -> None:
    with pytest.raises(ImportError):
        exec(
            "from motif_balance.inspection.render import render_candidate_projection_svg",
            {},
        )


def test_candidate_renderer_rejects_same_id_cross_matrix_projection(
    tmp_path: Path,
    pairwise_spec: DesignSpec,
) -> None:
    bundle = tmp_path / "bundle"
    design(pairwise_spec).write(bundle)
    inspection = inspect_result(bundle, kind="bundle")
    motif = inspection.problem.motifs[0]
    drifted_motif = motif.model_copy(
        update={"probabilities": tuple((0.25, 0.25, 0.25, 0.25) for _ in range(motif.width))}
    )
    drifted_problem = inspection.problem.model_copy(
        update={"motifs": (drifted_motif, *inspection.problem.motifs[1:])}
    )
    mixed = inspection.model_copy(update={"problem": drifted_problem})

    with pytest.raises(ArtifactError, match="does not match its problem"):
        render_candidate_svg(mixed, candidate_rank=1)
