from __future__ import annotations

import pytest

from motif_balance import DesignSpec, MotifModel, MotifSpecification


@pytest.fixture
def motif_a() -> MotifModel:
    return MotifModel(
        motif_id="motif_a",
        probabilities=((0.7, 0.1, 0.1, 0.1), (0.1, 0.7, 0.1, 0.1)),
        background=(0.25, 0.25, 0.25, 0.25),
    )


@pytest.fixture
def motif_b() -> MotifModel:
    return MotifModel(
        motif_id="motif_b",
        probabilities=((0.1, 0.1, 0.7, 0.1), (0.1, 0.1, 0.1, 0.7)),
        background=(0.25, 0.25, 0.25, 0.25),
    )


@pytest.fixture
def pairwise_spec(motif_a: MotifModel, motif_b: MotifModel) -> DesignSpec:
    return DesignSpec(
        specifications=(
            MotifSpecification(motif=motif_a, direction="seek"),
            MotifSpecification(motif=motif_b, direction="seek"),
        ),
        length=4,
        count=3,
        strands="both",
        evaluations=256,
        seed=7,
        min_distance=0.25,
    )
