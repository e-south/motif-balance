"""
--------------------------------------------------------------------------------
motif-balance
tests/contract/test_variant_precheck.py

Preserve verified products while separating limits from score and site failures.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from pathlib import Path

import pytest

from motif_balance import DesignSpec, MotifModel, MotifSpecification, score
from motif_balance.variants import diversify, load_library


def spec():
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
        length=2,
        count=1,
        evaluations=1,
        seed=7,
        strands="both",
    )


@pytest.mark.parametrize("parent", ["AA", "TT"])
def test_fixed_site_precheck_rejects_joint_loss_without_changing_the_product(parent):
    library = diversify(parent, spec(), min_balance=0.96)
    assert library.algorithm == "greedy_product_checked_v3"
    assert library.encoded_sequence_count == 2
    assert library.rejections.quality_precheck >= 1
    assert library.rejections.quality == library.score_rejected_expansions
    assert library.rejections.selected_site == 0
    assert all(score(v.sequence, spec()) == v for v in library.variants)
    assert load_library(library.model_dump_json()) == library


def test_legacy_library_replays_with_its_original_accounting():
    library = load_library(Path("tests/fixtures/variant-library-v2.json").read_bytes())
    assert library.algorithm == "greedy_product_checked_v2"
    assert library.evaluations_used == 8
    assert {v.sequence for v in library.variants} == {"AA", "CA"}


def test_size_limit_is_not_recorded_as_a_quality_failure():
    library = diversify("AA", spec(), min_balance=0.8, max_variants=1)
    assert library.rejections.size_limit > 0
    assert library.rejections.quality == 0
    assert library.rejections.selected_site == 0
    assert library.rejections.size_limit == library.size_rejected_expansions


def test_version_and_rejection_counters_cannot_be_reinterpreted():
    from motif_balance.model.variants import VariantLibrary

    library = diversify("AA", spec(), min_balance=0.96)
    wrong = library.model_dump(mode="json")
    wrong["algorithm"] = "greedy_product_checked_v2"
    with pytest.raises(ValueError, match="legacy construction"):
        VariantLibrary.model_validate(wrong)
    wrong = library.model_dump(mode="json")
    wrong["rejections"]["selected_site"] += 1
    with pytest.raises(ValueError, match="rejection categories"):
        VariantLibrary.model_validate(wrong)
