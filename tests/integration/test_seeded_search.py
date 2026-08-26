from __future__ import annotations

from motif_balance import DesignSpec, MotifModel, design


def test_seeded_partial_search_is_repeatable() -> None:
    motifs = (
        MotifModel(
            motif_id="left",
            probabilities=((0.7, 0.1, 0.1, 0.1), (0.1, 0.7, 0.1, 0.1)),
            background=(0.25, 0.25, 0.25, 0.25),
        ),
        MotifModel(
            motif_id="right",
            probabilities=((0.1, 0.1, 0.7, 0.1), (0.1, 0.1, 0.1, 0.7)),
            background=(0.25, 0.25, 0.25, 0.25),
        ),
    )
    spec = DesignSpec(
        motifs=motifs,
        length=8,
        count=4,
        strands="both",
        evaluations=128,
        seed=19,
        min_distance=0.125,
    )

    first = design(spec)
    second = design(spec)

    assert first == second
    assert first.manifest.evaluation_count == 128
    assert first.manifest.unique_evaluations <= 128
    assert first.manifest.completion_status == "budget_exhausted"
