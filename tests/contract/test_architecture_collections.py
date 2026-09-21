"""
--------------------------------------------------------------------------------
motif-balance
tests/contract/test_architecture_collections.py

Native ranking exposes qualified grouping and explicit up-to delivery.

Module Author(s): Eric J. South
Dunlop Lab
--------------------------------------------------------------------------------
"""

import pytest
from pydantic import ValidationError

from motif_balance import DesignSpec, MotifModel, MotifSpecification
from motif_balance.alternatives import rank_architectures


def specification(strands="forward"):
    return DesignSpec(
        schema_version="design-spec/v3",
        specifications=tuple(
            MotifSpecification(
                motif=MotifModel(
                    motif_id=name,
                    probabilities=(tuple(0.7 if base == preferred else 0.1 for base in "ACGT"),)
                    * 2,
                    background=(0.25,) * 4,
                ),
                direction="seek",
            )
            for name, preferred in (("a", "A"), ("b", "C"))
        ),
        length=8,
        count=1,
        strands=strands,
        seed=7,
        evaluations=1,
    )


WORDS = ("AAGCCGGG", "AAGGCCGG", "AACCGGGG", "CCAAGGGG", "ACACGGGG")


def test_topology_collapses_spacing_variants_and_retains_real_coordinates():
    result = rank_architectures(WORDS, specification(), grouping="interval_topology")
    assert result.grouping == "interval_topology"
    assert len(result.representatives) == 4
    assert [p.minimum_balance for p in result.prefixes] == [1, 1, 1, 0.5]
    gap = next(r for r in result.representatives if r.evaluation.sequence == "AAGCCGGG")
    assert gap.sequence_classes == 2
    assert gap.evaluation.matches[1].start == 3
    assert (
        result.prefixes[0].minimum_balance
        == rank_architectures(WORDS, specification()).prefixes[0].minimum_balance
    )
    # Exact-offset behavior remains available with its original default meaning.
    assert len(rank_architectures(WORDS, specification()).representatives) == 5
    assert rank_architectures(WORDS, specification()).grouping == "exact_offsets"


def test_up_to_selection_reports_complete_partial_and_empty_support():
    result = rank_architectures(WORDS, specification(), grouping="interval_topology")
    full = result.select_up_to(3)
    assert full.requested_count == full.delivered_count == 3
    assert full.available_count == 4 and full.status == "complete"
    assert full.quality == 1
    assert full.members == result.representatives[:3]
    partial = result.select_up_to(8)
    assert partial.requested_count == 8 and partial.delivered_count == 4
    assert partial.status == "insufficient_retained_architectures"
    assert partial.quality == 0.5 and partial.coverage == "supplied_pool"
    assert partial.grouping == result.grouping
    assert partial.ranking_digest == result.ranking_digest
    # Exact-count selection still refuses the same unsupported request.
    with pytest.raises(ValueError, match="does not support"):
        result.select(8)
    empty = rank_architectures((), specification(), grouping="interval_topology").select_up_to(8)
    assert empty.delivered_count == 0 and empty.quality is None
    assert empty.status == "insufficient_retained_architectures"


@pytest.mark.parametrize("count", [0, -1, True, 1.5, "4"])
def test_up_to_selection_rejects_invalid_requested_counts(count):
    ranking = rank_architectures(WORDS, specification(), grouping="interval_topology")
    with pytest.raises(ValueError, match="count"):
        ranking.select_up_to(count)


def test_literal_duplicates_flanks_and_tied_reverse_complements_do_not_add_classes():
    spec = specification("both")
    from motif_balance.scoring import reverse_complement

    words = ("AAGCCGGG", "AAGCCGGG", "AAGCCTGG")
    ranking = rank_architectures(words, spec, grouping="interval_topology")
    reverse = rank_architectures(
        tuple(reverse_complement(w) for w in words), spec, grouping="interval_topology"
    )
    assert len(ranking.representatives) == 1
    assert ranking.representatives == reverse.representatives


def test_palindromic_tied_sites_use_the_same_public_representative_after_reversal():
    from motif_balance.scoring import reverse_complement
    from tests.contract.test_pair_assessment import motif

    spec = specification("both").model_copy(
        update={
            "specifications": tuple(
                MotifSpecification(motif=motif(word, name), direction="seek")
                for name, word in (("a", "AT"), ("b", "CG"))
            )
        }
    )
    words = ("ATATCGCG", "ATATCGCC")
    forward = rank_architectures(words, spec, grouping="interval_topology")
    reversed_ = rank_architectures(
        tuple(reverse_complement(w) for w in words), spec, grouping="interval_topology"
    )
    assert forward.representatives == reversed_.representatives
    assert len(forward.representatives) == 1
    assert [(m.start, m.strand) for m in forward.representatives[0].evaluation.matches] == [
        (0, "+"),
        (4, "+"),
    ]


def test_a_small_model_perturbation_can_move_a_selected_tied_site_and_change_class():
    from tests.contract.test_pair_assessment import motif

    tied = MotifModel(motif_id="a", probabilities=((0.4, 0.4, 0.1, 0.1),), background=(0.25,) * 4)
    changed = MotifModel(
        motif_id="a", probabilities=((0.399999, 0.400001, 0.1, 0.1),), background=(0.25,) * 4
    )
    rankings = []
    for model in (tied, changed):
        spec = specification().model_copy(
            update={
                "length": 3,
                "specifications": (
                    MotifSpecification(motif=model, direction="seek"),
                    MotifSpecification(motif=motif("G", "b"), direction="seek"),
                ),
            }
        )
        rankings.append(rank_architectures(("AGC",), spec, grouping="interval_topology"))
    a, b = (r.representatives[0] for r in rankings)
    assert a.evaluation.matches[0].start == 0 and b.evaluation.matches[0].start == 2
    assert a.architecture_class != b.architecture_class
    assert a.evaluation.balance_score == b.evaluation.balance_score == 1


def test_grouping_and_class_identity_are_checked_before_trust(monkeypatch):
    from motif_balance.alternatives import api
    from motif_balance.model.alternatives import ArchitectureRanking

    result = rank_architectures(WORDS, specification(), grouping="interval_topology")
    altered = result.model_dump(mode="python")
    altered["representatives"][0]["architecture_class"] = (("wrong", 0, 1, "+"),)
    with pytest.raises(ValidationError, match="class"):
        ArchitectureRanking.model_validate(altered)
    monkeypatch.setattr(api, "compile_scoring", lambda *_: pytest.fail("invalid grouping compiled"))
    with pytest.raises(ValueError, match="grouping"):
        api.rank_architectures(WORDS, specification(), grouping="unknown")


@pytest.mark.parametrize(
    "field,value", [("delivered_count", 8), ("status", "complete"), ("quality", 1.0)]
)
def test_partial_delivery_cannot_be_serialized_as_fulfilled(field, value):
    from motif_balance.model.alternatives import ArchitectureCollection

    collection = rank_architectures(
        WORDS, specification(), grouping="interval_topology"
    ).select_up_to(8)
    payload = collection.model_dump(mode="json")
    assert payload["delivered_count"] == 4
    assert ArchitectureCollection.model_validate(payload) == collection
    payload[field] = value
    with pytest.raises(ValidationError):
        ArchitectureCollection.model_validate(payload)
