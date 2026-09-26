"""Single-output searches retain exact winners without keeping every match record."""

import pytest
from pydantic import ValidationError

from motif_balance import DesignSpec, MotifModel, MotifSpecification
from motif_balance.compile import compile_design
from motif_balance.model.search_observation import ObservationSpec
from motif_balance.search import (
    AnnealedSearchEngine,
    ExhaustiveSearchEngine,
    GreedySearchEngine,
    UniformRandomSearchEngine,
)
from motif_balance.search.observation import SearchRecorder


def _spec(*, count=1, evaluations=2048, length=8):
    motif = MotifModel(
        motif_id="synthetic",
        probabilities=((0.7, 0.1, 0.1, 0.1), (0.1, 0.7, 0.1, 0.1)),
        background=(0.25, 0.25, 0.25, 0.25),
    )
    return DesignSpec(
        specifications=(MotifSpecification(motif=motif, direction="seek"),),
        length=length,
        count=count,
        evaluations=evaluations,
        seed=29,
    )


@pytest.mark.parametrize(
    "engine",
    [AnnealedSearchEngine, GreedySearchEngine, UniformRandomSearchEngine, ExhaustiveSearchEngine],
)
def test_single_output_retention_preserves_full_pool_winners_and_observation(engine):
    spec = _spec(
        length=5 if engine is ExhaustiveSearchEngine else 20,
        evaluations=1024 if engine is ExhaustiveSearchEngine else 2048,
    )
    full = spec.model_copy(update={"count": 2})
    config = ObservationSpec(
        max_snapshots=4, quality_thresholds=(0.5,), max_sequences_per_threshold=4
    )
    observers = [SearchRecorder(s, config) for s in (spec, full)]
    one = engine(observer=observers[0]).search(compile_design(spec))
    reference = engine(observer=observers[1]).search(compile_design(full))
    assert len(reference.evaluations) > 256
    assert len(one.evaluations) <= 256
    assert one.unique_evaluations == reference.unique_evaluations
    assert one.elites == reference.elites
    assert one.diagnostics == reference.diagnostics
    first = dict(
        zip(
            (e.sequence for e in reference.evaluations),
            reference.first_evaluation_indices,
            strict=True,
        )
    )
    assert one.first_evaluation_indices == tuple(first[e.sequence] for e in one.evaluations)
    assert observers[0].frames == observers[1].frames
    assert observers[0].hits == observers[1].hits
    assert observers[0].quality.finish() == observers[1].quality.finish()


def test_single_output_admits_longer_scoring_work_but_multicandidate_limit_stays():
    prototype = _spec().scored_motifs[0]
    models = tuple(
        prototype.model_copy(
            update={"motif_id": f"model-{i}", "probabilities": prototype.probabilities * 10}
        )
        for i in range(12)
    )
    values = {
        "specifications": tuple(MotifSpecification(motif=m, direction="seek") for m in models),
        "length": 60,
        "count": 1,
        "evaluations": 65536,
        "seed": 3,
    }
    spec = DesignSpec(**values)
    assert spec.evaluations == 65536
    with pytest.raises(ValidationError, match="score-operation limit"):
        DesignSpec(**{**values, "count": 2})
    with pytest.raises(ValidationError, match="score-operation limit"):
        DesignSpec(**{**values, "length": 10000, "evaluations": 100000})
