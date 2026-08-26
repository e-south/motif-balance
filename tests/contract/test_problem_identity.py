from __future__ import annotations

from motif_balance import DesignSpec, MotifModel
from motif_balance.compile import compile_design


def _motif(motif_id: str, preferred: tuple[float, float, float, float]) -> MotifModel:
    return MotifModel(
        motif_id=motif_id,
        probabilities=(preferred,),
        background=(0.25, 0.25, 0.25, 0.25),
    )


def _problem_id(*motifs: MotifModel) -> str:
    return compile_design(
        DesignSpec(
            motifs=motifs,
            length=2,
            count=1,
            strands="both",
            evaluations=16,
            seed=1,
        )
    ).problem_id


def test_problem_identity_binds_motif_ids_to_model_content() -> None:
    first = _motif("first", (0.7, 0.1, 0.1, 0.1))
    second = _motif("second", (0.1, 0.7, 0.1, 0.1))
    renamed = first.model_copy(update={"motif_id": "renamed"})
    swapped_first = second.model_copy(update={"motif_id": "first"})
    swapped_second = first.model_copy(update={"motif_id": "second"})

    assert _problem_id(first, second) != _problem_id(renamed, second)
    assert _problem_id(first, second) != _problem_id(swapped_first, swapped_second)


def test_distinct_motif_identities_may_share_one_scoring_model() -> None:
    first = _motif("first", (0.7, 0.1, 0.1, 0.1))
    second = first.model_copy(update={"motif_id": "second"})

    problem = compile_design(
        DesignSpec(
            motifs=(first, second),
            length=2,
            count=1,
            strands="both",
            evaluations=16,
            seed=1,
        )
    )

    assert [motif.model.motif_id for motif in problem.motifs] == ["first", "second"]
