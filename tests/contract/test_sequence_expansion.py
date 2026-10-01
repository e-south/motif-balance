"""
--------------------------------------------------------------------------------
motif-balance
tests/contract/test_sequence_expansion.py

Explicit expansion retains passing sequences without implying a Cartesian product.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from itertools import product

import pytest

from motif_balance import DesignSpec, MotifModel, MotifSpecification, score
from motif_balance.variants import expand, load_expansion


def request(length=2, *, both=False):
    return DesignSpec(
        specifications=(
            MotifSpecification(
                motif=MotifModel(
                    motif_id="wanted",
                    probabilities=((0.4, 0.35, 0.2, 0.05),) * 2,
                    background=(0.25,) * 4,
                ),
                direction="seek",
            ),
        ),
        length=length,
        count=1,
        evaluations=1,
        seed=7,
        strands="both" if both else "forward",
    )


def test_retains_passing_sequences_that_cannot_share_one_degenerate_template():
    result = expand("AA", request(), min_balance=0.96)
    assert {v.sequence for v in result.variants} == {"AA", "AC", "CA"}
    assert score("CC", request()).balance_score < 0.96
    assert not hasattr(result, "template")
    assert result.stop_reason == "frontier_exhausted"
    assert len(result.variants) == 1 + sum(t.status == "retained" for t in result.trials)
    assert load_expansion(result.model_dump_json()) == result


def test_small_case_matches_exhaustive_scoring_without_claiming_global_exhaustion():
    result = expand("AA", request(), min_balance=0.96)
    exact = {
        "".join(p)
        for p in product("ACGT", repeat=2)
        if score("".join(p), request()).balance_score >= 0.96
    }
    assert {v.sequence for v in result.variants} == exact


@pytest.mark.parametrize(
    "cap,budget,reason",
    [(1, 100, "variant_limit"), (16, 1, "evaluation_limit"), (2, 100, "variant_limit")],
)
def test_stops_before_scoring_another_passing_sequence_after_a_limit(cap, budget, reason):
    result = expand("AA", request(), min_balance=0.8, max_variants=cap, max_evaluations=budget)
    assert result.stop_reason == reason
    assert len(result.variants) <= cap and result.evaluations_used <= budget
    assert len(result.variants) == 1 + sum(t.status == "retained" for t in result.trials)


def test_reverse_sites_flanks_and_every_result_are_independently_rescored():
    spec = request(4, both=True)
    result = expand("GTTG", spec, min_balance=0.8, max_variants=32)
    assert result.parent.matches[0].strand == "-"
    for variant in result.variants:
        assert score(variant.sequence, spec) == variant
        assert variant.balance_score >= 0.8 - 1e-12
        assert variant.sequence[0] == "G" and variant.sequence[3] == "G"
        assert (variant.matches[0].start, variant.matches[0].end, variant.matches[0].strand) == (
            1,
            3,
            "-",
        )
    assert load_expansion(result.model_dump_json()) == result


@pytest.mark.parametrize(
    "settings",
    [
        {"max_evaluations": True},
        {"max_evaluations": 0},
        {"max_variants": 1025},
        {"min_balance": float("nan")},
        {"editable_mask": (True,)},
    ],
)
def test_invalid_settings_fail_before_any_scoring(monkeypatch, settings):
    import motif_balance.variants.expansion as implementation

    monkeypatch.setattr(
        implementation, "evaluate", lambda *a: pytest.fail("invalid input reached scorer")
    )
    with pytest.raises(ValueError):
        expand("AA", request(), **{"min_balance": 0.8, **settings})


def test_trace_tampering_and_missing_passing_member_are_rejected():
    from motif_balance.model.sequence_expansion import SequenceExpansion

    result = expand("AA", request(), min_balance=0.96)
    raw = result.model_dump(mode="json")
    raw["variants"].pop()
    with pytest.raises(ValueError):
        SequenceExpansion.model_validate(raw)
    raw = result.model_dump(mode="json")
    raw["trials"][0]["balance_score"] += 0.001
    with pytest.raises(ValueError):
        load_expansion(__import__("json").dumps(raw))


def test_collection_preflights_all_parents_and_preserves_separate_lists(pairwise_spec, monkeypatch):
    import motif_balance.variants.expansion_collection as implementation
    from motif_balance.alternatives import rank_architectures
    from motif_balance.formats.collection import collection_json
    from motif_balance.model.alternatives import CollectionReport
    from motif_balance.variants import expand_collection

    spec = pairwise_spec.model_copy(update={"min_distance": None})
    ranking = rank_architectures(tuple(map("".join, product("ACGT", repeat=4))), spec)
    report = CollectionReport.model_validate_json(
        collection_json(ranking, count=2, source_id="bundle-" + "0" * 24, anchored=False)
    )
    with monkeypatch.context() as patch:
        patch.setattr(
            implementation, "expand", lambda *a, **k: pytest.fail("construction before admission")
        )
        with pytest.raises(ValueError, match="total work"):
            expand_collection(report, min_balance=0, max_total_score_operations=1)
        with pytest.raises(ValueError, match="output"):
            expand_collection(report, min_balance=0, max_variants=8, max_evaluations=100000)
    result = expand_collection(report, min_balance=0, max_variants=8, max_evaluations=64)
    assert len(result.libraries) == report.collection.delivered_count
    for library, member in zip(result.libraries, report.collection.members, strict=True):
        assert library.parent == member.evaluation
        assert len(library.variants) <= 8
        assert load_expansion(library.model_dump_json()) == library


def test_exhausted_frontier_does_not_mean_every_qualifying_sequence_was_found():
    a, c = (0.8, 0.1, 0.05, 0.05), (0.1, 0.8, 0.05, 0.05)
    spec = DesignSpec(
        specifications=tuple(
            MotifSpecification(
                motif=MotifModel(motif_id=name, probabilities=columns, background=(0.25,) * 4),
                direction="seek",
            )
            for name, columns in [("left", (a, c)), ("right", (c, a))]
        ),
        length=2,
        count=1,
        evaluations=1,
        seed=7,
        strands="forward",
    )
    floor = score("AA", spec).balance_score
    assert score("CC", spec).balance_score >= floor - 1e-12
    result = expand("AA", spec, min_balance=floor)
    assert result.stop_reason == "frontier_exhausted"
    assert [v.sequence for v in result.variants] == ["AA"]


def test_high_score_does_not_override_selected_site_identity():
    motif = MotifModel(
        motif_id="one", probabilities=((0.4, 0.35, 0.2, 0.05),), background=(0.25,) * 4
    )
    spec = DesignSpec(
        specifications=(MotifSpecification(motif=motif, direction="seek"),),
        length=2,
        count=1,
        evaluations=1,
        seed=1,
        strands="forward",
    )
    result = expand("AA", spec, min_balance=0.8)
    assert len(result.variants) == 1
    assert all(t.status == "site_changed" and t.balance_score >= 0.8 for t in result.trials)


def test_no_duplicate_scoring_and_no_passes_lost(monkeypatch):
    import motif_balance.variants.expansion as implementation

    original = implementation.evaluate
    seen = {}

    def recording(sequence, problem):
        assert sequence not in seen
        seen[sequence] = original(sequence, problem)
        return seen[sequence]

    monkeypatch.setattr(implementation, "evaluate", recording)
    result = expand("AA", request(), min_balance=0.8, max_variants=16, max_evaluations=100)
    assert len(seen) == result.evaluations_used
    assert {v.sequence for v in result.variants} == {
        s for s, v in seen.items() if v.balance_score >= 0.8 - 1e-12
    }


def test_large_work_request_is_rejected_before_scoring(monkeypatch):
    import motif_balance.variants.expansion as implementation

    monkeypatch.setattr(implementation, "evaluate", lambda *a: pytest.fail("unsafe admission"))
    with pytest.raises(ValueError, match="bounded"):
        expand("A" * 2000, request(2000), min_balance=0.8, max_evaluations=100000)


def test_wide_match_output_is_bounded_before_scoring(monkeypatch):
    """Counting match records alone misses the DNA stored inside each record."""
    import motif_balance.variants.expansion as implementation

    spec = DesignSpec(
        specifications=tuple(
            MotifSpecification(
                motif=MotifModel(
                    motif_id=f"wide{index}",
                    probabilities=((0.4, 0.35, 0.2, 0.05),) * 3000,
                    background=(0.25,) * 4,
                ),
                direction="seek",
            )
            for index in range(20)
        ),
        length=3000,
        count=1,
        evaluations=1,
        seed=7,
    )
    monkeypatch.setattr(implementation, "evaluate", lambda *a: pytest.fail("oversize output"))
    with pytest.raises(ValueError, match="output"):
        expand("A" * 3000, spec, min_balance=0.8, max_variants=1024)
