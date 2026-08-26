from __future__ import annotations

from dataclasses import replace

from motif_balance import DesignSpec, MotifModel
from motif_balance.compile import compile_design
from motif_balance.search import (
    AnnealedSearchEngine,
    ExhaustiveSearchEngine,
    SearchEngine,
    SearchResult,
    search,
)


def _problem(*, evaluations: int = 128, seed: int = 19):
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
    return compile_design(
        DesignSpec(
            motifs=motifs,
            length=8,
            count=4,
            strands="both",
            evaluations=evaluations,
            seed=seed,
            min_distance=0.125,
        )
    )


def test_search_engine_is_a_real_injection_seam() -> None:
    problem = _problem(evaluations=32)
    delegated = ExhaustiveSearchEngine().search(
        replace(problem, spec=problem.spec.model_copy(update={"length": 2, "evaluations": 16}))
    )

    class StubEngine:
        def search(self, _problem) -> SearchResult:
            return delegated

    engine: SearchEngine = StubEngine()

    assert search(problem, engine=engine) is delegated


def test_production_engine_uses_the_exact_public_evaluation_budget() -> None:
    result = AnnealedSearchEngine().search(_problem(evaluations=127))

    assert result.engine == "annealed_multistart_v1"
    assert result.engine_version == "1"
    assert result.evaluations_used == 127
    assert result.unique_evaluations == len({item.sequence for item in result.evaluations})
    assert result.completion_status == "budget_exhausted"
    assert result.search_validation_status == "contract_tested"
    assert result.diagnostics.restarts == 8
    assert result.diagnostics.checkpoints[-1].evaluations == 127
    assert result.diagnostics.checkpoints[-1].best_score == max(
        item.balance_score for item in result.evaluations
    )
    assert {item.move for item in result.diagnostics.proposals} == {
        "single",
        "block",
        "multi",
        "insertion",
    }


def test_production_engine_is_seeded_and_repeatable() -> None:
    problem = _problem(evaluations=160, seed=31)

    first = AnnealedSearchEngine().search(problem)
    second = AnnealedSearchEngine().search(problem)
    different = AnnealedSearchEngine().search(_problem(evaluations=160, seed=32))

    assert first == second
    assert first != different


def test_default_search_uses_exhaustive_only_when_the_budget_covers_the_space() -> None:
    problem = _problem(evaluations=16)
    tiny = replace(
        problem,
        spec=problem.spec.model_copy(update={"length": 2, "evaluations": 16}),
    )

    assert search(tiny).engine == "exhaustive_v1"
    assert search(problem).engine == "annealed_multistart_v1"
